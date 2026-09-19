"""Operator console mechanism -- execution_plan.md §13.2 "Human-interaction event logging".

A small rclpy node + CLI: subscribes `/space/operator/request` and `/space/operator/report`
(`openral_msgs/PromptStamped` -- the type `openral_core.EmitPromptTool` names in its own
docstring), lets an operator type an answer, and appends
`interaction_start`/`interaction_message`/`interaction_end`/`clarification_request`/
`escalation_request`/`human_command` events with an ALFUS `authority_level` and timestamps to
`<run_dir>/operator/events.jsonl`.

Today nothing actually publishes on those two topics: `space_runtime/agent.py`'s `dispatch()`
handles `EmitPromptTool` by logging a local `operator_report`/`operator_request` event and
returning -- it never calls into the generic OpenRAL path that would publish `PromptStamped`
(confirmed by reading `Agent.dispatch()`, not inferred). See `docs/operator_console.md` for
exactly what `space_runtime/` and `ros/plexil_capability_adapter` would need for this console to
receive anything from a live run; this module only builds the receiving/logging mechanism and
proves it against a synthetic publisher (`--selftest`), never against the simulation.

The operator PROTOCOL (when to escalate, what counts as which authority level, how an answer
flows back to the agent) is a pending user decision -- this file does not encode one. It logs
whatever the operator types, tagged with whatever `--authority-level` they pass.

Run (system ROS Humble Python, matching this project's other rclpy scripts):
    source /opt/ros/humble/setup.bash && source <openral>/install/setup.bash
    ROS_DOMAIN_ID=94 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \\
        python3 experiments/operator_console/console.py --run-dir <run_dir>
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

ALFUS_AUTHORITY_LEVELS = ("mission", "strategic_goal", "tactical_goal", "mission_task", "route", "autopilot", "servo")

REQUEST_TOPIC = "/space/operator/request"
REPORT_TOPIC = "/space/operator/report"


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
    with the `interaction_end` that closes it (see `evaluation/rows.py::_hir`)."""

    def __init__(self, log: OperatorEventLog, *, kind: str, authority_level: str, source_topic: str, text: str):
        if authority_level not in ALFUS_AUTHORITY_LEVELS:
            msg = f"authority_level must be one of {ALFUS_AUTHORITY_LEVELS}, got {authority_level!r}"
            raise ValueError(msg)
        self.log, self.interaction_id = log, uuid.uuid4().hex[:12]
        log.append("interaction_start", interaction_id=self.interaction_id, type=kind,
                    authority_level=authority_level, source_topic=source_topic)
        log.append("interaction_message", interaction_id=self.interaction_id, from_="agent", text=text)

    def operator_reply(self, text: str) -> None:
        self.log.append("interaction_message", interaction_id=self.interaction_id, from_="operator", text=text)

    def end(self) -> None:
        self.log.append("interaction_end", interaction_id=self.interaction_id)


def run_cli(run_dir: Path, *, default_authority: str) -> None:
    """Blocking loop: subscribes the two topics, prompts the operator for a reply on stdin for
    every message received, logs the full exchange. Ctrl+C to stop. Assumes `rclpy.init()` has
    already been called by the caller (so a self-test publisher can share one context)."""
    import rclpy
    from openral_msgs.msg import PromptStamped
    from rclpy.node import Node

    log = OperatorEventLog(run_dir)
    node = Node("space_operator_console")

    def on_message(topic: str, kind: str):
        def cb(msg: PromptStamped) -> None:
            interaction = Interaction(log, kind=kind, authority_level=default_authority, source_topic=topic, text=msg.text)
            print(f"\n[{kind}] {msg.text}\n> ", end="", flush=True)
            reply = input()
            interaction.operator_reply(reply)
            interaction.end()
        return cb

    node.create_subscription(PromptStamped, REQUEST_TOPIC, on_message(REQUEST_TOPIC, "request_operator"), 10)
    node.create_subscription(PromptStamped, REPORT_TOPIC, on_message(REPORT_TOPIC, "report_to_operator"), 10)
    print(f"space_operator_console: logging to {log.path}, listening on {REQUEST_TOPIC} and {REPORT_TOPIC}")
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


def _selftest(run_dir: Path) -> None:
    """Proves the receive/log mechanism with a synthetic publisher -- never the simulation.
    Caller is responsible for ROS_DOMAIN_ID (must not be 77, the live graph's domain) and for
    `rclpy.init()`/`shutdown()` (shared with `run_cli` so both use one context)."""
    import threading

    from openral_msgs.msg import PromptStamped
    from rclpy.node import Node

    pub_node = Node("selftest_publisher")
    pub = pub_node.create_publisher(PromptStamped, REQUEST_TOPIC, 10)

    def publish_once():
        time.sleep(1.0)
        m = PromptStamped()
        m.text = "selftest: does the console receive and log this?"
        pub.publish(m)

    threading.Thread(target=publish_once, daemon=True).start()
    print("(selftest) publishing one PromptStamped on", REQUEST_TOPIC, "-- reply on stdin, Ctrl+C after")
    try:
        run_cli(run_dir, default_authority="mission_task")
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
    rclpy.init(args=None)
    try:
        if args.selftest:
            _selftest(args.run_dir)
        else:
            run_cli(args.run_dir, default_authority=args.default_authority_level)
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
