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
env = dict(os.environ, PYTHONPATH=f"{REPO}:{os.environ.get('PYTHONPATH', '')}")
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


agent = start(["--mission", BRIEF])
last = time.time()
while agent.poll() is None:
    rclpy.spin_once(n, timeout_sec=0.2)
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
