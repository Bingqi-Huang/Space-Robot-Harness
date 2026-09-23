"""Mission control, behind the Direct-with-Earth link -- execution_plan.md §13.2; the ground-operator protocol of
research repo docs/heldout_design.md §8.

A small rclpy node, one for all three methods: it subscribes `/space/operator/request` and `/space/operator/report`
(`openral_msgs/PromptStamped`), answers on `/space/operator/reply` (matched by the `request_id` the message's
metadata carries), and logs every exchange to `<run_dir>/operator/events.jsonl` with wall-clock and mission time
and the ALFUS level of the answer (NIST SP 1011-II-1.0).

The link (`space_context/link.py`, SPICE): a message crosses in the one-way delay while Earth is above the horizon;
while it is below, the robot's own link node reports it queued for the next pass (store-and-forward, RFC 4838) --
a link status, not an answer and not an interaction. Mission time is the simulator clock.

The protocol (scripted, published before the runs, identical for every method; the default mode):
  - every request is answered `DECISION_TIME_S` of mission time after it arrives (§8: 300 s, "minute-scale"
    operational decisions, VIPER ops; the value is ours);
  - a request carrying calls held for approval (Ours' guard, `pending_approvals`) is decided by the flight-rule table
    (14 CFR 1214.403: decisions planned in advance): GRANT removal of a module from a unit whose load is
    non-critical while a crew-critical unit is down, per the units' downlinked telemetry; otherwise DENY with a reason
    code. ALFUS level: assign tactical goals.
  - any other request -- an escalation, "no procedure applies" -- is answered "hold in a safe state, a new procedure
    is in work": nothing is uplinked during the run (historical new-procedure times are hours to days), recorded as
    ground re-authoring required. ALFUS level: assign mission tasks.
  - a report is acknowledged; it is not an intervention (no ALFUS level).
`--manual` replaces the scripted decisions with a person at the console (demonstration runs only, never statistics):
an answer starting "GRANT:" grants the held calls.

    python3 experiments/operator_console/console.py --run-dir <run_dir> [--decision-time-s 300] [--manual]
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
DECISION_TIME_S = 300.0
IX = json.loads((Path(__file__).resolve().parents[2] / "space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json").read_text())

REQUEST_TOPIC = "/space/operator/request"
REPORT_TOPIC = "/space/operator/report"
REPLY_TOPIC = "/space/operator/reply"
HOLD = "ACK. Hold in a safe state. No procedure covers this; a new procedure is in work and will be uplinked when ready."


class OperatorEventLog:
    """Append-only `<run_dir>/operator/events.jsonl` (the method's own records live elsewhere). Every event carries the
    wall clock and the mission time (simulator clock) it happened at."""

    def __init__(self, run_dir: Path, clock: dict):
        self.path = run_dir / "operator" / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = sum(1 for _ in self.path.read_text().splitlines()) if self.path.exists() else 0
        self._t0, self.clock = time.time(), clock

    def append(self, kind: str, **fields) -> dict:
        ev = {"seq": self._seq, "kind": kind, "t": round(time.time() - self._t0, 3), "wall_t": time.time(),
              "mission_t": round(self.clock["t"], 3), **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        self._seq += 1
        return ev


def decide(pending: list[dict], telemetry: dict) -> tuple[str, list[dict], str, str]:
    """The flight-rule table: (answer text, grants, ALFUS level, outcome code) for a request."""
    if not pending:
        return HOLD, [], "mission_task", "hold_reauthoring_required"
    units = telemetry["units"]
    crew_critical_down = [u for u, t in units.items() if t["criticality"] == "crew-critical" and t["breaker"] == "tripped"]
    grants, lines = [], []
    for p in pending:
        unit = IX["points"][p["target"]]["unit"]
        if units[unit]["criticality"] == "non-critical" and crew_critical_down:
            grants.append({"capability": p["capability"], "target": p["target"]})
            lines.append(f"GRANTED: {p['capability']} on {p['target']} -- {unit} feeds a non-critical load "
                         f"({units[unit]['load']}) and crew-critical {', '.join(crew_critical_down)} is down.")
        else:
            why = "DENY-CRITICAL-DONOR" if units[unit]["criticality"] != "non-critical" else "DENY-NO-CREW-CRITICAL-NEED"
            lines.append(f"DENIED ({why}): {p['capability']} on {p['target']} -- {unit} feeds a {units[unit]['criticality']} "
                         f"load ({units[unit]['load']}); crew-critical units down: {crew_critical_down or 'none'}.")
    return " ".join(lines), grants, "tactical_goal", "grant" if grants else "deny"


def run_cli(run_dir: Path, *, decision_time_s: float, manual: bool) -> None:
    import rclpy
    from openral_msgs.msg import PromptStamped
    from rclpy.node import Node
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String

    node = Node("space_operator_console")
    clock, telemetry = {"t": 0.0}, {}
    node.create_subscription(Clock, "/clock", lambda m: clock.update(t=m.clock.sec + m.clock.nanosec * 1e-9), 10)
    # the units' telemetry as downlinked to the ground: what the flight-rule table decides on
    node.create_subscription(String, "/srb/env0/power_telemetry", lambda m: telemetry.update(json.loads(m.data)), 10)
    log = OperatorEventLog(run_dir, clock)
    reply_pub = node.create_publisher(PromptStamped, REPLY_TOPIC, 10)

    def wait_until(t: float) -> None:
        while clock["t"] < t:
            time.sleep(0.05)

    def queued(request_id, why: str) -> None:
        st = link.state(clock["t"])
        log.append("link_queued", request_id=request_id, why=why, reopens_in_s=st["reopens_in_s"])  # the request stays open
        reply_pub.publish(PromptStamped(text=f"[link] not delivered: {why}; queued for the next Earth pass in "
                                             f"{st['reopens_in_s']:.0f} s", metadata_json=json.dumps(
            {"request_id": request_id, "link_status": "queued", "grants": [], **st})))

    def exchange(topic: str, kind: str, msg) -> None:
        meta = json.loads(msg.metadata_json or "{}")
        request_id, pending = meta.get("request_id"), meta.get("pending_approvals", [])
        sent = clock["t"]
        if not link.state(sent)["earth_visible"]:
            return queued(request_id, "Earth is below the horizon")
        wait_until(link.delivery_time(sent))
        iid = uuid.uuid4().hex[:12]
        log.append("interaction_start", interaction_id=iid, type=kind, source_topic=topic, request_id=request_id,
                   sent_mission_t=round(sent, 3), text=msg.text, pending_approvals=pending)
        if kind == "report_to_operator":
            text, grants, level, outcome = "Report received.", [], None, "ack_report"
        elif manual:
            held = "".join(f"\n  held for approval: {p['capability']} on {p['target']} ({p['reason']})" for p in pending)
            print(f"\n[{kind} at mission t={clock['t']:.0f} s] {msg.text}{held}\n> ", end="", flush=True)
            text = input()
            grants = [{"capability": p["capability"], "target": p["target"]} for p in pending] if text.startswith("GRANT:") else []
            text = text.removeprefix("GRANT:").strip()
            level, outcome = ("tactical_goal", "grant" if grants else "deny") if pending else ("mission_task", "manual")
        else:
            wait_until(clock["t"] + decision_time_s)
            text, grants, level, outcome = decide(pending, telemetry)
        log.append("interaction_end", interaction_id=iid, authority_level=level, outcome=outcome, text=text, grants=grants,
                   ground_reauthoring_required=outcome == "hold_reauthoring_required")
        if not link.state(clock["t"])["earth_visible"]:
            return queued(request_id, "Earth set before mission control's answer was sent")
        wait_until(link.delivery_time(clock["t"]))
        log.append("reply_delivered", interaction_id=iid, request_id=request_id)
        reply_pub.publish(PromptStamped(text=text, metadata_json=json.dumps({
            "request_id": request_id, "interaction_id": iid, "authority_level": level, "outcome": outcome,
            "grants": grants, "mission_t": round(clock["t"], 3)})))

    def on_message(topic: str, kind: str):
        return lambda msg: threading.Thread(target=exchange, args=(topic, kind, msg), daemon=True).start()

    node.create_subscription(PromptStamped, REQUEST_TOPIC, on_message(REQUEST_TOPIC, "request_operator"), 10)
    node.create_subscription(PromptStamped, REPORT_TOPIC, on_message(REPORT_TOPIC, "report_to_operator"), 10)
    print(f"space_operator_console: logging to {log.path}; "
          + ("manual (demonstration)" if manual else f"scripted protocol, decision time {decision_time_s:.0f} s"), flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--decision-time-s", type=float, default=DECISION_TIME_S)
    ap.add_argument("--manual", action="store_true", help="a person answers at the console (demonstration runs only)")
    args = ap.parse_args()

    import rclpy

    rclpy.init(args=None)
    try:
        run_cli(args.run_dir, decision_time_s=args.decision_time_s, manual=args.manual)
    finally:
        rclpy.try_shutdown()  # a SIGINT has usually shut the context down already


if __name__ == "__main__":
    main()
