"""§21.5: the PLEXIL baseline runs Mission A `covered` on the live graph.

The plan (baselines/plexil/plans/MissionA_Covered.plx) executes in PLEXIL's universalExec; its Commands reach the
robot only through ros/plexil_capability_adapter -> the common capability boundary -> ExecuteRskill (runner, kernel,
HAL, SRB) -- the same path the boundary-driven Ours check uses. This script is the evaluator: it starts the exec,
then reports each capability call from the boundary's trace, the base error at the dock and the verifier state. It
also persists universalExec's full stdout (node-transition trace included, baselines/plexil/Debug.cfg's
"Node:transition") to <D0_LOG>/plexil_node_trace.log -- the EXEC log line itself keeps only a 4-line tail.
Run with D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_a_check.py.
"""
import subprocess
import threading

from d0_common import *  # noqa: F401,F403
from space_harness_msgs.action import ExecuteCapability

REPO = HERE / "../../.."
PLAN_DIR = (REPO / "baselines/plexil").resolve()
PLEXIL_HOME = Path.home() / "Programs/plexil"
assert ActionClient(n, ExecuteCapability, "/space/capability/execute").wait_for_server(timeout_sec=120), "boundary not up"

env = dict(os.environ, PLEXIL_HOME=str(PLEXIL_HOME),
           LD_LIBRARY_PATH=f"{(REPO / 'ros/install/lib').resolve()}:{PLEXIL_HOME / 'lib'}:{os.environ.get('LD_LIBRARY_PATH', '')}")
log("PLAN", executive="PLEXIL universalExec 6.1.3", plan="MissionA_Covered.plx")
t0, sim0 = time.time(), sim["t"]
exec_proc = subprocess.Popen([str(PLEXIL_HOME / "bin/universalExec"), "-c", str(PLAN_DIR / "interface-config.xml"),
                              "-p", str(PLAN_DIR / "plans/MissionA_Covered.plx")],
                             cwd=PLAN_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
exec_out = []
# read the exec's output on a thread: a blocking readline here stopped the spin, and with it the sim clock
threading.Thread(target=lambda: exec_out.extend(l.rstrip() for l in exec_proc.stdout), daemon=True).start()
while exec_proc.poll() is None:
    rclpy.spin_once(n, timeout_sec=0.2)
spin(1.0)
# Full node-transition trace (PLAN_DIR/Debug.cfg enables universalExec's own "Node:transition" debug flag, picked up
# by default as ./Debug.cfg since cwd=PLAN_DIR): persisted whole, not just the EXEC line's tail, so
# evaluation/baselines/plexil_normalize.py can recover plan_node_id from it (§14.6 trace completeness).
(Path(os.environ["D0_LOG"]) / "plexil_node_trace.log").write_text("\n".join(exec_out) + "\n")
log("EXEC", exit=exec_proc.returncode, wall_s=round(time.time() - t0, 1), sim_s=round(sim["t"] - sim0, 1),
    tail=[l for l in exec_out if l.strip()][-4:])

step = 0
for line in (Path(os.environ["D0_LOG"]) / "capability_server.log").read_text().splitlines():
    if "CAPABILITY " in line:
        step += 1
        c = json.loads(line.split("CAPABILITY ", 1)[1])
        log("STEP", n=step, name=c["capability"], success=c["success"], failure_kind=c["failure_kind"],
            failure_reason=c["failure_reason"][:200], args=c["args"], sim_s=c["evidence"].get("sim_s"))
spin(3.0)
log("DOCK", **base_err([0.0, 0.0], 0.0))
log("RESULT", mission=dict(mission))
