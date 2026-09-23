"""A chain of capability calls through the boundary, in order, with no model: what the agent would send, without its latency.

For developing one skill on a held graph (boot_only_check.py under D0_HOLD=1, then attach_d0.sh with
D0_CHECK=scripted_chain_check.py): CHAIN_JSON is a file with [[capability, args], ...]. It stops at the first failure, prints each
call's result, the servo traces' worst deviation, the jaw, and what the evaluator says of the mission (evaluator only; the
calls never see it).
"""
import json

import yaml

from d0_common import *  # noqa: F401,F403
from rclpy.action import ActionClient
from space_harness_msgs.action import ExecuteCapability

cap = ActionClient(n, ExecuteCapability, "/space/capability/execute")
while not cap.wait_for_server(timeout_sec=1.0):
    spin(0.5)


# the capability's own deadline is the contract's default; this one only catches a call that never answers
DEADLINE_S = {k: float(v["default_deadline_s"]) for k, v in yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "openral_ext/capability_server/contracts.yaml").read_text())["effects"].items()}


def call(name, args):
    hard_sim_s = DEADLINE_S[name] + 120.0
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
# the simulator can be put back to a saved state first (RESUME_SNAPSHOT=<log>/snapshots/before_step_<n>.pt: jaws open
# only, F60); `d0_common.put_scene_back` does the restore, shared with ours_mission_check.py.
if os.environ.get("RESUME_SNAPSHOT"):
    put_scene_back(Path(os.environ["RESUME_SNAPSHOT"]))
# every call gets the per-call budget every method has (tier 1: the identical call, at most 3 attempts), so a chain
# fails only on what no method could get past; the attempts are logged as the per-leg reliability record
ATTEMPTS = 3
for name, args in chain:
    for attempt in range(1, ATTEMPTS + 1):
        t0 = sim["t"]
        log("CALL", capability=name, attempt=attempt, args=args, sim_t=round(t0, 1), jaw=round(float(jaw.get("q", -1.0)), 3))
        r = call(name, args)
        log("RESULT", capability=name, attempt=attempt, success=r["success"], reason=(r.get("failure_reason") or "")[:400],
            sim_s=round(sim["t"] - t0, 1), servo=worst(r.get("evidence") or {}), jaw=round(float(jaw.get("q", -1.0)), 3),
            arm={k: round(float(v), 3) for k, v in arm.items()}, mission=dict(mission))
        if r["success"]:
            break
    else:
        log("STOPPED", at=name)
        break
spin(3.0)
log("CHAIN_DONE", mission=dict(mission))
