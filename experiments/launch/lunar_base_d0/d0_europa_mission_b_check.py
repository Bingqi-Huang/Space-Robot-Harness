"""The EUROPA->PLEXIL baseline runs Mission B `covered` on the live graph (execution_plan §11.2, §21.6).

Mirrors d0_plexil_mission_b_check.py's shape, but three processes instead of one: `host.py` (EUROPA -- solves,
dispatches, replans, exactly its offline `run_offline_mission_b.sh` invocation except talking to the *real* boundary
instead of `sim_boundary.py`), `universalExec` running the generic `ActivityDispatch.plx` (no mission logic of its
own -- forwards whatever host.py sends), and the common boundary (already up: D0_CAPABILITY_SERVER=1). Every
capability call still crosses only `ros/plexil_capability_adapter` -> `/space/capability/execute` -> ExecuteRskill,
the same path PLEXIL's and Ours' checks use and the same evaluator (`mission` dict, `d0_common.py`).
Run with D0_CAPABILITY_SERVER=1 D0_CHECK=d0_europa_mission_b_check.py.
"""
import subprocess
import sys
import threading

from d0_common import *  # noqa: F401,F403
from space_harness_msgs.action import ExecuteCapability

REPO = HERE / "../../.."
EUROPA_DIR = (REPO / "baselines/europa").resolve()
PLEXIL_HOME = Path.home() / "Programs/plexil"
assert ActionClient(n, ExecuteCapability, "/space/capability/execute").wait_for_server(timeout_sec=120), "boundary not up"

env = dict(os.environ, PLEXIL_HOME=str(PLEXIL_HOME),
           LD_LIBRARY_PATH=f"{(REPO / 'ros/install/lib').resolve()}:{EUROPA_DIR / 'plexil/build'}:{PLEXIL_HOME / 'lib'}:{os.environ.get('LD_LIBRARY_PATH', '')}")
# ActivityDispatch.plx is pre-compiled offline (baselines/europa/run_offline_mission_b.sh does this every run;
# recompile the same way -- `plexilc` -- if ActivityDispatch.ple ever changes) -- not recompiled here to avoid
# needing a conda-free PATH inside this already-running graph process.
assert (EUROPA_DIR / "plexil/plans/ActivityDispatch.plx").exists(), "compile ActivityDispatch.ple first (plexilc)"

log("PLAN", host="EUROPA host.py", model="mission-b-model.nddl",
    goals=["spare_oru@pdu_1_shelf/shelf", "stowed", "final:dock"])
t0, sim0 = time.time(), sim["t"]
D0_LOG = Path(os.environ["D0_LOG"])
host_proc = subprocess.Popen([sys.executable, str(EUROPA_DIR / "host.py"), "--run-dir", str(D0_LOG),
                              "--model", str(EUROPA_DIR / "domain/mission-b-model.nddl"),
                              "--item", "spare_oru:depot_stand/slot_0",
                              "--goal", "spare_oru@pdu_1_shelf/shelf", "--goal", "stowed", "--final", "dock"],
                             cwd=EUROPA_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
host_out = []
threading.Thread(target=lambda: host_out.extend(l.rstrip() for l in host_proc.stdout), daemon=True).start()
spin(2.0)  # host.py opens the HostLink server socket before the exec can connect to it
exec_proc = subprocess.Popen([str(PLEXIL_HOME / "bin/universalExec"), "-c", str(EUROPA_DIR / "plexil/interface-config.xml"),
                              "-p", str(EUROPA_DIR / "plexil/plans/ActivityDispatch.plx")],
                             cwd=EUROPA_DIR / "plexil", env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
exec_out = []
threading.Thread(target=lambda: exec_out.extend(l.rstrip() for l in exec_proc.stdout), daemon=True).start()
while host_proc.poll() is None or exec_proc.poll() is None:
    rclpy.spin_once(n, timeout_sec=0.2)
spin(1.0)
(D0_LOG / "host_stdout.log").write_text("\n".join(host_out) + "\n")
log("EXEC", host_exit=host_proc.returncode, exec_exit=exec_proc.returncode,
    wall_s=round(time.time() - t0, 1), sim_s=round(sim["t"] - sim0, 1),
    tail=[l for l in exec_out if l.strip()][-4:])

# host.py's own events.jsonl already has one line per mission/plan/dispatch/result/done (§11.2 steps 2-7); this
# check script does not re-derive step-by-step progress from it the way the PLEXIL script reconstructs STEP lines
# from capability_server.log -- host.py's own record is already the trace (europa_timeline_from_logs.py reads it
# directly for the video panel).
step = 0
for line in (D0_LOG / "events.jsonl").read_text().splitlines():
    e = json.loads(line)
    if e["kind"] == "result":
        step += 1
        log("STEP", n=step, name=e["capability"], success=e["success"], failure_reason=(e.get("failure_reason") or "")[:200])
spin(3.0)
log("DOCK", **base_err([0.0, 0.0], 0.0))
log("RESULT", mission=dict(mission))
