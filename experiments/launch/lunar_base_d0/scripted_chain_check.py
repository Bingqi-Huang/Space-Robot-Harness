"""A chain of capability calls through the boundary, in order, with no model: what the agent would send, without its latency.

For developing one skill on a held graph (boot_only_check.py under D0_HOLD=1, then attach_d0.sh with
D0_CHECK=scripted_chain_check.py): CHAIN_JSON is a file with [[capability, args], ...]. It stops at the first failure, prints each
call's result, the servo traces' worst deviation, the jaw, and what the evaluator says of the mission (evaluator only; the
calls never see it).
"""
import json

from d0_common import *  # noqa: F401,F403
from rclpy.action import ActionClient
from space_harness_msgs.action import ExecuteCapability

cap = ActionClient(n, ExecuteCapability, "/space/capability/execute")
while not cap.wait_for_server(timeout_sec=1.0):
    spin(0.5)


def call(name, args, hard_sim_s=900.0):
    f = cap.send_goal_async(ExecuteCapability.Goal(capability=name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f, timeout_sec=90)
    gh = f.result()
    if gh is None or not gh.accepted:
        return dict(success=False, failure_reason="goal rejected", evidence={})
    rf, sim0 = gh.get_result_async(), sim["t"]
    while not rf.done() and sim["t"] - sim0 < hard_sim_s:
        rclpy.spin_once(n, timeout_sec=0.1)
    if not rf.done():
        return dict(success=False, failure_reason="no result before the hard deadline", evidence={})
    r = rf.result().result
    return dict(success=bool(r.success), failure_kind=int(r.failure_kind), failure_reason=r.failure_reason,
                evidence=json.loads(r.evidence_json or "{}"))


def worst(evidence):
    out = {}
    skill = evidence.get("skill") or {}
    for name, trace in (skill.get("servo_traces") or {}).items():
        zs = [abs(r["tcp_minus_goal_mm"][2]) for r in trace]
        out[name] = dict(samples=len(trace), worst_z_mm=max(zs) if zs else None, end_err_m=trace[-1]["err_m"] if trace else None)
    return out


chain = json.loads(Path(os.environ["CHAIN_JSON"]).read_text())
for name, args in chain:
    t0 = sim["t"]
    log("CALL", capability=name, args=args, sim_t=round(t0, 1), jaw=round(float(jaw.get("q", -1.0)), 3))
    r = call(name, args)
    log("RESULT", capability=name, success=r["success"], reason=(r.get("failure_reason") or "")[:400], sim_s=round(sim["t"] - t0, 1),
        servo=worst(r.get("evidence") or {}), jaw=round(float(jaw.get("q", -1.0)), 3), mission=dict(mission))
    if not r["success"]:
        log("STOPPED", at=name)
        break
spin(3.0)
log("CHAIN_DONE", mission=dict(mission))
