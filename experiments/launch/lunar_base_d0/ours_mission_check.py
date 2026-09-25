"""Ours on the live graph: the space-native mission agent (space_runtime) runs one Mission A/B case.

The agent receives the operator's mission brief (the same wording every method gets) and reaches the robot only
through the common capability boundary. This script is the evaluator: it starts the agent, waits for the autonomous
run to end, and reports the task verifier's state and the rover's truth error at the dock -- neither ever reaches
the agent. The agent's own record is <log>/ours/{events.jsonl,report.md,agent.log}.
Run with D0_CAPABILITY_SERVER=1 D0_CHECK=ours_mission_check.py (the scene and D0_SCENARIO pick the mission).
"""
import subprocess

from d0_common import *  # noqa: F401,F403

REPO = (HERE / "../../..").resolve()
# the operator's brief, exactly as the SRB task publishes it for every method (latched /srb/env0/mission_brief)
BRIEF = latched_string("/srb/env0/mission_brief")
run_dir = Path(os.environ["D0_LOG"]) / "ours"
run_dir.mkdir(parents=True, exist_ok=True)
# the run tag puts the agent under the graph's teardown (D0_GRAPH_LOG when attached to a held graph): an agent blocked
# in rclpy ignores SIGTERM, and two left over from stopped runs were still alive in the next run's ROS domain (2026-09-17)
env = dict(os.environ, PYTHONPATH=f"{REPO}:{os.environ.get('PYTHONPATH', '')}", D0_RUN_TAG=os.environ.get("D0_GRAPH_LOG", os.environ["D0_LOG"]))
# Step-wise development (research runs never use these): `d0_common.put_scene_back` restores the simulator's full
# state, saved before every agent step (<log>/snapshots/before_step_<n>.pt, with the rover's own localization
# estimate beside it). OURS_STOP_ON_FAILURE=1 stops the agent at the first failed capability or effect that does
# not hold, the graph held up (D0_HOLD=1). After the fix, attach_d0.sh with OURS_RESUME_FROM=<earlier log>
# OURS_RESUME_BEFORE_STEP=<n> puts the simulation back to before step n and continues the agent's record from there.

# The graph's own starting state, saved once while the scene is still untouched. A later run on the same held graph
# puts the site back to the start with OURS_RESET=1 instead of booting Isaac again, which costs minutes every time a
# mission is tried from the top. The scene starts with the jaws open and nothing in them, which is the only kind of
# state a restore can return to honestly: the contact that holds a payload is not in the saved state, so an item
# restored in the jaws falls straight out of them (research repo F60).
INITIAL = Path(os.environ.get("D0_GRAPH_LOG", os.environ["D0_LOG"])) / "snapshots/initial.pt"
if not os.environ.get("D0_ATTACH"):
    INITIAL.parent.mkdir(parents=True, exist_ok=True)
    p0, yaw0, _ = est_pose()
    INITIAL.with_suffix(".json").write_text(json.dumps(dict(x=float(p0[0]), y=float(p0[1]), yaw=float(yaw0), sim_t=sim["t"])))
    snapshot("save", INITIAL)
    log("INITIAL", snapshot=str(INITIAL))

RESUME_FROM = os.environ.get("OURS_RESUME_FROM")
if os.environ.get("OURS_RESET"):
    put_scene_back(INITIAL)
elif RESUME_FROM:
    record = (Path(RESUME_FROM) / "ours/events.jsonl").read_text()
    if os.environ.get("OURS_RESUME_BEFORE_STEP"):
        before = int(os.environ["OURS_RESUME_BEFORE_STEP"])
        keep, n_steps = [], 0
        for line in record.splitlines():
            if '"kind": "tool_proposed"' in line or '"kind": "reasoner_step_failed"' in line:
                n_steps += 1
            if n_steps >= before:
                break
            keep.append(line)
        (run_dir / "events.jsonl").write_text("\n".join(keep) + "\n")
        put_scene_back(Path(RESUME_FROM) / f"snapshots/before_step_{before}.pt")
    else:
        # Continue the held graph's current physical state and complete record,
        # including the failure. No teleport or contact reconstruction.
        (run_dir / "events.jsonl").write_text(record)
        log("CONTINUED", record=str(Path(RESUME_FROM) / "ours/events.jsonl"))
STOP_ON_FAILURE = bool(os.environ.get("OURS_STOP_ON_FAILURE"))
log("PLAN", method="ours", brief=BRIEF, run_dir=str(run_dir))
t0, sim0 = time.time(), sim["t"]
# Continuity probe (Phase E exit 1): OURS_RESTART_AT_STEP=N kills the agent process (SIGKILL, no goodbye) once its record
# holds N steps and restarts it on the same record with --resume, optionally on another model (OURS_RESTART_MODEL).
RESTART_AT = int(os.environ.get("OURS_RESTART_AT_STEP", "0"))


def steps():
    p = run_dir / "events.jsonl"
    return sum('"kind": "tool_proposed"' in line or '"kind": "reasoner_step_failed"' in line for line in p.read_text().splitlines()) if p.exists() else 0


# OURS_CONFIG=<path>: another harness configuration (e.g. another reasoner model), for development comparisons
CONFIG = ["--config", os.environ["OURS_CONFIG"]] if os.environ.get("OURS_CONFIG") else []


def start(extra):
    return subprocess.Popen([sys.executable, "-m", "space_runtime.agent", "--run-dir", str(run_dir), *CONFIG, *extra], cwd=REPO, env=env,
                            stdout=(run_dir / "agent.log").open("a"), stderr=subprocess.STDOUT)


agent = start(["--resume"] if RESUME_FROM else ["--mission", BRIEF])
last = time.time()
seen = len((run_dir / "events.jsonl").read_text().splitlines()) if RESUME_FROM else 0
pending_failure = None
saved = -1


def save_before_next_step(evs):
    """Once the last recorded step has ended (or none started), save the state the next step will start from."""
    global saved
    k = steps()
    last = max((i for i, x in enumerate(evs) if '"kind": "tool_proposed"' in x or '"kind": "reasoner_step_failed"' in x), default=-1)
    ended = last < 0 or '"reasoner_step_failed"' in evs[last] or any(
        m in x for x in evs[last + 1:] for m in ('"kind": "verification_finished"', '"kind": "query_answered"', '"kind": "local_tool"', '"outcome": "deny', '"outcome": "approval'))
    if ended and k != saved:
        path = snap_dir / f"before_step_{k + 1}.pt"
        p, yaw, _ = est_pose()
        path.with_suffix(".json").write_text(json.dumps(dict(x=float(p[0]), y=float(p[1]), yaw=float(yaw),
                                                            sim_t=sim["t"], arm=dict(arm))))
        snapshot("save", path)
        saved = k


# D0_TRACE_OBJECT=<name>: log the object's truth pose whenever it moves > 2 cm, with the agent's last recorded step
trace_prev = handle_pos(TRACE_OBJ) if TRACE_OBJ else None
while agent.poll() is None:
    rclpy.spin_once(n, timeout_sec=0.2)
    evs = (run_dir / "events.jsonl").read_text().splitlines() if (run_dir / "events.jsonl").exists() else []
    save_before_next_step(evs)
    if TRACE_OBJ:
        hp = handle_pos(TRACE_OBJ)
        if np.linalg.norm(hp - trace_prev) > 0.02:
            evs = (run_dir / "events.jsonl").read_text().splitlines()
            lastev = next((json.loads(x) for x in reversed(evs) if '"tool_proposed"' in x), {})
            log("OBJECT", name=TRACE_OBJ, sim_t=round(sim["t"], 2), handle=[round(float(v), 3) for v in hp],
                moved_m=round(float(np.linalg.norm(hp - trace_prev)), 3), last_tool=lastev.get("tool"), last_args=lastev.get("args"),
                tcp=[round(float(v), 3) for v in tcp_pose()[0]], jaw=round(float(jaw.get("q", -1)), 3))
            trace_prev = hp
    if STOP_ON_FAILURE:
        new_events = [json.loads(x) for x in evs[seen:]]
        failed = [e for e in new_events if (e["kind"] == "execution_finished" and not e["success"])
                  or (e["kind"] == "effect_verified" and not e["holds"])]
        pending_failure = pending_failure or (failed[0] if failed else None)
        seen = len(evs)
        # Development stopping must not interrupt the independent effect query/verification (g8b).
        if pending_failure and any(e["kind"] == "verification_finished" for e in new_events):
            agent.kill()
            agent.wait()
            log("STOPPED", at_step=steps(), failed=pending_failure, sim_s=round(sim["t"] - sim0, 1))
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
