"""Ours on the live graph: the space-native mission agent (space_runtime) runs one Mission A/B case.

The agent receives the operator's mission brief (the same wording every method gets) and reaches the robot only
through the common capability boundary. This script is the evaluator: it starts the agent, waits for the autonomous
run to end, and reports the task verifier's state and the rover's truth error at the dock -- neither ever reaches
the agent. The agent's own record is <log>/ours/{events.jsonl,report.md,agent.log}.
Run with D0_CAPABILITY_SERVER=1 D0_CHECK=ours_mission_check.py OURS_MISSION=a|b [OURS_DESTINATION/OURS_REPORTED].
"""
import subprocess

from d0_common import *  # noqa: F401,F403

REPO = (HERE / "../../..").resolve()
MISSION = os.environ.get("OURS_MISSION", "a")
if MISSION == "a":
    unit = os.environ.get("OURS_REPORTED", "pdu_2").replace("_", "-").upper()
    BRIEF = (f"Power distribution unit {unit} reported a fault. Inspect the power field, identify the failed unit, restore "
             "it if within your authority, verify the result, and return the rover to the dock with the arm stowed.")
else:
    dest = os.environ.get("OURS_DESTINATION", "pdu_1").replace("_", "-").upper()
    BRIEF = (f"Deliver the spare ORU staged at the depot stand (slot 0 per the manifest) to the spares shelf of {dest}, "
             "then return the rover to the dock with the arm stowed.")
run_dir = Path(os.environ["D0_LOG"]) / "ours"
run_dir.mkdir(parents=True, exist_ok=True)
# the run tag puts the agent under the graph's teardown (D0_GRAPH_LOG when attached to a held graph): an agent blocked
# in rclpy ignores SIGTERM, and two left over from stopped runs were still alive in the next run's ROS domain (2026-09-17)
env = dict(os.environ, PYTHONPATH=f"{REPO}:{os.environ.get('PYTHONPATH', '')}", D0_RUN_TAG=os.environ.get("D0_GRAPH_LOG", os.environ["D0_LOG"]))
# Step-wise development (attach_d0.sh on a held graph): OURS_RESUME_FROM=<earlier ours dir> continues that record from
# before its step OURS_RESUME_BEFORE_STEP (the failed one; default: after its last) in the live world as it is now;
# OURS_STOP_ON_FAILURE=1 stops the agent at the first failed capability or effect that does not hold, leaving the
# graph up for the fix.
RESUME_FROM = os.environ.get("OURS_RESUME_FROM")
if RESUME_FROM:
    keep, n_steps = [], 0
    before = int(os.environ.get("OURS_RESUME_BEFORE_STEP", "0"))
    for line in (Path(RESUME_FROM) / "events.jsonl").read_text().splitlines():
        if '"kind": "tool_proposed"' in line or '"kind": "reasoner_step_failed"' in line:
            n_steps += 1
        if before and n_steps >= before:
            break
        keep.append(line)
    (run_dir / "events.jsonl").write_text("\n".join(keep) + "\n")
STOP_ON_FAILURE = bool(os.environ.get("OURS_STOP_ON_FAILURE"))
log("PLAN", method="ours", brief=BRIEF, run_dir=str(run_dir))
t0, sim0 = time.time(), sim["t"]
# Continuity probe (Phase E exit 1): OURS_RESTART_AT_STEP=N kills the agent process (SIGKILL, no goodbye) once its record
# holds N steps and restarts it on the same record with --resume, optionally on another model (OURS_RESTART_MODEL).
RESTART_AT = int(os.environ.get("OURS_RESTART_AT_STEP", "0"))


def steps():
    p = run_dir / "events.jsonl"
    return sum('"kind": "tool_proposed"' in line for line in p.read_text().splitlines()) if p.exists() else 0


def start(extra):
    return subprocess.Popen([sys.executable, "-m", "space_runtime.agent", "--run-dir", str(run_dir), *extra], cwd=REPO, env=env,
                            stdout=(run_dir / "agent.log").open("a"), stderr=subprocess.STDOUT)


agent = start(["--resume"] if RESUME_FROM else ["--mission", BRIEF])
last = time.time()
seen = len((run_dir / "events.jsonl").read_text().splitlines()) if RESUME_FROM else 0
# D0_TRACE_OBJECT=<name>: log the object's truth pose whenever it moves > 2 cm, with the agent's last recorded step
trace_prev = handle_pos(TRACE_OBJ) if TRACE_OBJ else None
while agent.poll() is None:
    rclpy.spin_once(n, timeout_sec=0.2)
    if TRACE_OBJ:
        hp = handle_pos(TRACE_OBJ)
        if np.linalg.norm(hp - trace_prev) > 0.02:
            evs = (run_dir / "events.jsonl").read_text().splitlines()
            lastev = next((json.loads(x) for x in reversed(evs) if '"tool_proposed"' in x), {})
            log("OBJECT", name=TRACE_OBJ, sim_t=round(sim["t"], 2), handle=[round(float(v), 3) for v in hp],
                moved_m=round(float(np.linalg.norm(hp - trace_prev)), 3), last_tool=lastev.get("tool"), last_args=lastev.get("args"),
                tcp=[round(float(v), 3) for v in tcp_pose()[0]], jaw=round(float(jaw.get("q", -1)), 3))
            trace_prev = hp
    if STOP_ON_FAILURE and (run_dir / "events.jsonl").exists():
        evs = (run_dir / "events.jsonl").read_text().splitlines()
        failed = [json.loads(x) for x in evs[seen:] if ('"execution_finished"' in x and '"success": false' in x)
                  or ('"effect_verified"' in x and '"holds": false' in x)]
        seen = len(evs)
        if failed:
            agent.kill()
            agent.wait()
            log("STOPPED", at_step=steps(), failed=failed[0], sim_s=round(sim["t"] - sim0, 1))
            break
    if RESTART_AT and steps() >= RESTART_AT:
        agent.kill()
        agent.wait()
        model = os.environ.get("OURS_RESTART_MODEL")
        log("RESTART", at_steps=steps(), model=model or "same", sim_s=round(sim["t"] - sim0, 1))
        RESTART_AT = 0
        agent = start(["--resume", *(["--model", model] if model else [])])
    if time.time() - last > 120:
        log("PROGRESS", wall_s=round(time.time() - t0), sim_s=round(sim["t"] - sim0, 1), mission=dict(mission))
        last = time.time()
spin(3.0)
log("AGENT", exit=agent.returncode, wall_s=round(time.time() - t0, 1), sim_s=round(sim["t"] - sim0, 1))
log("DOCK", **base_err([0.0, 0.0], 0.0))
log("RESULT", mission=dict(mission))
