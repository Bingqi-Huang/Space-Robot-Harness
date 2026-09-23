"""Operator console mechanism -- execution_plan.md §13.2 "Human-interaction event logging".

A small rclpy node + CLI: subscribes `/space/operator/request` and `/space/operator/report`
(`openral_msgs/PromptStamped` -- the type `openral_core.EmitPromptTool` names in its own
docstring), lets an operator answer (typed on stdin, or read from a scripted-answers file for
development), publishes the answer back on `/space/operator/reply` (matched to the request by the
`request_id` its metadata_json carries, echoed from the request), and appends
`interaction_start`/`interaction_message`/`interaction_end`/`clarification_request`/
`escalation_request`/`human_command` events with an ALFUS `authority_level` and timestamps to
`<run_dir>/operator/events.jsonl`.

`space_runtime/agent.py`'s `Agent.dispatch()` publishes a `PromptStamped` per `EmitPromptTool` and,
for `request_operator`, blocks the reasoning loop on this console's reply; `ros/plexil_capability_adapter`'s
`RequestOperator` Command and `baselines/europa/host.py`'s operator escalation use the same three
topics, so one console serves all three methods.

The operator PROTOCOL (when to escalate, what counts as which authority level, what a given answer
means to the requester) is a pending user decision -- this file does not encode one. It logs
whatever the operator (or the scripted-answers file) says, tagged with whatever
`--authority-level` was passed, and echoes it back verbatim.

Run (system ROS Humble Python, matching this project's other rclpy scripts):
    source /opt/ros/humble/setup.bash && source <openral>/install/setup.bash
    ROS_DOMAIN_ID=94 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \\
        python3 experiments/operator_console/console.py --run-dir <run_dir> [--answers-file <file, one answer per line>]
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # the research repo: space_context
from space_context import link  # noqa: E402

ALFUS_AUTHORITY_LEVELS = ("mission", "strategic_goal", "tactical_goal", "mission_task", "route", "autopilot", "servo")

REQUEST_TOPIC = "/space/operator/request"
REPORT_TOPIC = "/space/operator/report"
REPLY_TOPIC = "/space/operator/reply"


class OperatorEventLog:
    """Append-only `<run_dir>/operator/events.jsonl` -- separate from `space_runtime`'s own
    `ours/events.jsonl` (that file is owned by space_runtime; this console never writes to it)."""

    def __init__(self, run_dir: Path):
        self.path = run_dir / "operator" / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = sum(1 for _ in self.path.read_text().splitlines()) if self.path.exists() else 0
        self._t0 = time.time()

    def append(self, kind: str, **fields) -> dict:
        ev = {"seq": self._seq, "kind": kind, "t": round(time.time() - self._t0, 3), "wall_t": time.time(), **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        self._seq += 1
        return ev


class Interaction:
    """One request/report -> operator-answer exchange. `interaction_id` pairs `interaction_start`
    with the `interaction_end` that closes it (see `evaluation/rows.py::_hir`). `request_id`, when
    the incoming message's metadata_json carried one, is echoed back on the reply so the requester
    (Ours, the PLEXIL adapter, the EUROPA host) can match it to the call it is blocked on."""

    def __init__(self, log: OperatorEventLog, *, kind: str, authority_level: str, source_topic: str, text: str,
                 request_id: str | None):
        if authority_level not in ALFUS_AUTHORITY_LEVELS:
            msg = f"authority_level must be one of {ALFUS_AUTHORITY_LEVELS}, got {authority_level!r}"
            raise ValueError(msg)
        self.log, self.interaction_id, self.authority_level, self.request_id = log, uuid.uuid4().hex[:12], authority_level, request_id
        start_ev = log.append("interaction_start", interaction_id=self.interaction_id, type=kind,
                              authority_level=authority_level, source_topic=source_topic)
        self.start_wall_t = start_ev["wall_t"]
        log.append("interaction_message", interaction_id=self.interaction_id, from_="agent", text=text)

    def operator_reply(self, text: str) -> None:
        self.log.append("interaction_message", interaction_id=self.interaction_id, from_="operator", text=text)

    def end(self) -> None:
        end_ev = self.log.append("interaction_end", interaction_id=self.interaction_id)
        self.end_wall_t = end_ev["wall_t"]


def run_cli(run_dir: Path, *, default_authority: str, answers: list[str] | None = None, decision_time_s: float = 0.0) -> None:
    """Blocking loop: subscribes the two request topics, gets a reply for every message received
    (operator stdin, or the next line of `answers` in scripted-answer mode for development), logs
    the full exchange and publishes the reply on `REPLY_TOPIC`. Ctrl+C to stop. Assumes
    `rclpy.init()` has already been called by the caller (so a self-test publisher can share one
    context)."""
    import rclpy
    from openral_msgs.msg import PromptStamped
    from rclpy.node import Node
    from rosgraph_msgs.msg import Clock

    log = OperatorEventLog(run_dir)
    node = Node("space_operator_console")
    reply_pub = node.create_publisher(PromptStamped, REPLY_TOPIC, 10)
    # the ground segment sits behind the Direct-with-Earth link (space_context/link.py): mission time is the simulator
    # clock; a message crosses in the one-way delay while Earth is up, and waits for the next pass while it is down
    clock = {"t": 0.0}
    node.create_subscription(Clock, "/clock", lambda m: clock.update(t=m.clock.sec + m.clock.nanosec * 1e-9), 10)

    def wait_until(t: float) -> None:
        while clock["t"] < t:
            time.sleep(0.05)

    def queued(request_id, text: str) -> None:
        """The robot's own communication node reports the message is held for the next pass -- a link status, not an
        answer from mission control, and not an operator interaction."""
        st = link.state(clock["t"])
        reply_pub.publish(PromptStamped(text=f"[link] not delivered: {text}; queued for the next Earth pass in "
                                             f"{st['reopens_in_s']:.0f} s", metadata_json=json.dumps(
            {"request_id": request_id, "link_status": "queued", "grants": [], **st})))

    def exchange(topic: str, kind: str, msg) -> None:
        meta = json.loads(msg.metadata_json or "{}")
        request_id, pending = meta.get("request_id"), meta.get("pending_approvals", [])
        if not link.state(clock["t"])["earth_visible"]:
            return queued(request_id, "Earth is below the horizon")
        wait_until(link.delivery_time(clock["t"]))
        interaction = Interaction(log, kind=kind, authority_level=default_authority, source_topic=topic,
                                  text=msg.text, request_id=request_id)
        held = "".join(f"\n  held for approval: {p['capability']} on {p['target']} ({p['reason']})" for p in pending)
        print(f"\n[{kind} at mission t={clock['t']:.0f} s] {msg.text}{held}\n> ", end="", flush=True)
        reply = answers.pop(0) if answers is not None else input()
        print(reply) if answers is not None else None  # scripted mode: echo what was "typed"
        wait_until(clock["t"] + decision_time_s)
        # an answer starting "GRANT:" authorizes exactly the calls this request carried as held for approval
        grants = [{"capability": p["capability"], "target": p["target"]} for p in pending] if reply.startswith("GRANT:") else []
        reply = reply.removeprefix("GRANT:").strip()
        interaction.operator_reply(reply)
        interaction.end()
        if not link.state(clock["t"])["earth_visible"]:
            return queued(request_id, "Earth set before mission control's answer was sent")
        wait_until(link.delivery_time(clock["t"]))
        reply_pub.publish(PromptStamped(text=reply, metadata_json=json.dumps({
            "request_id": request_id, "interaction_id": interaction.interaction_id,
            "authority_level": interaction.authority_level, "grants": grants,
            "start_wall_t": interaction.start_wall_t, "end_wall_t": interaction.end_wall_t})))

    def on_message(topic: str, kind: str):
        return lambda msg: threading.Thread(target=exchange, args=(topic, kind, msg), daemon=True).start()

    node.create_subscription(PromptStamped, REQUEST_TOPIC, on_message(REQUEST_TOPIC, "request_operator"), 10)
    node.create_subscription(PromptStamped, REPORT_TOPIC, on_message(REPORT_TOPIC, "report_to_operator"), 10)
    print(f"space_operator_console: logging to {log.path}, listening on {REQUEST_TOPIC} and {REPORT_TOPIC}, "
         f"replying on {REPLY_TOPIC}" + (f" (scripted, {len(answers)} canned answers)" if answers is not None else ""))
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()


def log_human_initiated(run_dir: Path, kind: str, authority_level: str, text: str) -> None:
    """CLI path for operator-initiated events that are not a reply to an agent message:
    `clarification_request`, `escalation_request`, `human_command`."""
    if authority_level not in ALFUS_AUTHORITY_LEVELS:
        msg = f"authority_level must be one of {ALFUS_AUTHORITY_LEVELS}, got {authority_level!r}"
        raise ValueError(msg)
    OperatorEventLog(run_dir).append(kind, authority_level=authority_level, text=text)


def _selftest(run_dir: Path, *, answers: list[str] | None = None) -> None:
    """Proves the receive/reply/log mechanism with a synthetic publisher -- never the simulation.
    Also subscribes `REPLY_TOPIC` itself and prints the round trip. Caller is responsible for
    ROS_DOMAIN_ID (must not be 77, the live graph's domain) and for `rclpy.init()`/`shutdown()`
    (shared with `run_cli` so both use one context)."""
    import threading

    from openral_msgs.msg import PromptStamped
    from rclpy.node import Node

    pub_node = Node("selftest_publisher")
    pub = pub_node.create_publisher(PromptStamped, REQUEST_TOPIC, 10)
    pub_node.create_subscription(PromptStamped, REPLY_TOPIC,
                                 lambda m: print(f"(selftest) reply received: {m.text!r} metadata={m.metadata_json}"), 10)

    def publish_once():
        time.sleep(1.0)
        m = PromptStamped()
        m.text = "selftest: does the console receive and log this?"
        m.metadata_json = json.dumps({"request_id": "selftest-1"})
        pub.publish(m)

    threading.Thread(target=publish_once, daemon=True).start()
    print("(selftest) publishing one PromptStamped on", REQUEST_TOPIC,
         "-- reply on stdin (or scripted), Ctrl+C after")
    try:
        run_cli(run_dir, default_authority="mission_task", answers=answers)
    finally:
        pub_node.destroy_node()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--ros-domain-id", default=None)
    ap.add_argument("--discovery-range", default=None)
    ap.add_argument("--default-authority-level", default="mission_task", choices=ALFUS_AUTHORITY_LEVELS)
    ap.add_argument("--log-event", choices=("clarification_request", "escalation_request", "human_command"),
                     help="Log one operator-initiated event and exit, instead of listening.")
    ap.add_argument("--authority-level", choices=ALFUS_AUTHORITY_LEVELS)
    ap.add_argument("--text")
    ap.add_argument("--selftest", action="store_true", help="Prove the mechanism with a synthetic publisher, no simulation.")
    ap.add_argument("--decision-time-s", type=float, default=0.0,
                    help="mission control's time to answer once a request has arrived (operator protocol)")
    ap.add_argument("--answers-file", type=Path,
                     help="Development mode: one canned answer per line, consumed in order instead of prompting stdin.")
    args = ap.parse_args()

    if args.log_event:
        if not (args.authority_level and args.text):
            ap.error("--log-event needs --authority-level and --text")
        log_human_initiated(args.run_dir, args.log_event, args.authority_level, args.text)
        return

    import os

    import rclpy

    if args.ros_domain_id:
        os.environ["ROS_DOMAIN_ID"] = args.ros_domain_id
    if args.discovery_range:
        os.environ["ROS_AUTOMATIC_DISCOVERY_RANGE"] = args.discovery_range
    answers = args.answers_file.read_text().splitlines() if args.answers_file else None
    rclpy.init(args=None)
    try:
        if args.selftest:
            _selftest(args.run_dir, answers=answers)
        else:
            run_cli(args.run_dir, default_authority=args.default_authority_level, answers=answers,
                    decision_time_s=args.decision_time_s)
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
