"""A chain of effects and queries through the boundary, in order, with no model: what a method would send, without its
latency. LOOK_JSON is a file with [[name, args], ...] or [[name, args, "may_fail"], ...]; a name the contracts list as
a query is asked (an `observe` is the VLM reading a camera image), `view` drives to a surveyed view pose by name.
Effects get the per-call budget every method has (3 identical attempts); a step marked "may_fail" is one whose
failure is what the chain is checking (placing onto an occupied support), so the chain goes on after it. The
evaluator's mission state is logged at the end (evaluator only; the calls never see it). Run with
D0_CAPABILITY_SERVER=1 D0_CHECK=look_chain_check.py LOOK_JSON=<abs path> + the scenario.
"""
import yaml

from d0_boundary import cap, query
from d0_common import *  # noqa: F401,F403

QUERIES = yaml.safe_load((Path(__file__).resolve().parents[3] / "openral_ext/capability_server/contracts.yaml").read_text())["queries"]

ATTEMPTS = 3
for step in json.loads(Path(os.environ["LOOK_JSON"]).read_text()):
    name, args, may_fail = step[0], step[1], len(step) > 2
    if name == "view":
        v = query("site_map")["view_poses"][args["name"]]
        name, args = "navigate_to_pose", dict(x=v["x"], y=v["y"], yaw=v["yaw"])
    if name in QUERIES:
        log("QUERY", query=name, args=args, value=query(name, **args), sim_t=round(sim["t"], 1))
        continue
    for attempt in range(1, ATTEMPTS + 1):
        r = cap(name, **args)
        log("RESULT", capability=name, attempt=attempt, success=r["success"], reason=r["failure_reason"][:400],
            sim_s=r["sim_s"], wall_s=r["wall_s"], mission=dict(mission))
        if r["success"]:
            break
    else:
        if not may_fail:
            log("STOPPED", at=name)
            break
spin(3.0)
log("CHAIN_DONE", mission=dict(mission))
