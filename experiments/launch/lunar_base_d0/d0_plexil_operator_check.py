"""Offline check: RequestOperator through ros/plexil_capability_adapter and the operator console
(execution_plan §13.2, operator mechanism only). Entirely off the live graph -- no d0_common, no
`openral deploy sim`. `CapabilityAdapter::start()` needs the two boundary ROS endpoints to exist
before universalExec will run any plan at all (even one that, like this one, never calls
ExecuteCapability), so this script also brings up a stub boundary that rejects everything -- the
real capability_server needs SRB assets this worktree's empty submodule doesn't have, and
RequestOperator's own path never touches the boundary anyway.

Persists universalExec's full stdout (node-transition trace included, baselines/plexil/Debug.cfg's
"Node:transition") to <log_dir>/plexil_node_trace.log, same convention as
d0_plexil_mission_a_check.py, so evaluation/baselines/plexil_normalize.py can recover plan_node_id
from either. Proves one request -> scripted answer -> resume round trip for the PLEXIL adapter.

Run (never ROS_DOMAIN_ID=77 -- this never touches the live graph):
    ROS_DOMAIN_ID=95 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PLEXIL_HOME=~/Programs/plexil \\
        python3 experiments/launch/lunar_base_d0/d0_plexil_operator_check.py <log_dir> ["canned answer"]
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = (HERE / "../../..").resolve()
PLAN_DIR = REPO / "baselines/plexil"
PLEXIL_HOME = Path(os.environ.get("PLEXIL_HOME", Path.home() / "Programs/plexil"))
LOG_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("D0_LOG", "/tmp/d0_plexil_operator_check"))
ANSWER = sys.argv[2] if len(sys.argv) > 2 else "proceed with contingency plan B"
LOG_DIR.mkdir(parents=True, exist_ok=True)
(LOG_DIR / "answers.txt").write_text(ANSWER + "\n")

STUB_BOUNDARY = """
import rclpy
from rclpy.action import ActionServer
from rclpy.node import Node
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability
rclpy.init()
n = Node("stub_boundary")
def execute_cb(gh):
    gh.abort()
    return ExecuteCapability.Result(success=False, failure_kind=20, failure_reason="stub boundary: no real backend", evidence_json="{}")
ActionServer(n, ExecuteCapability, "/space/capability/execute", execute_cb)
n.create_service(QueryCapability, "/space/capability/query",
                  lambda req, resp: QueryCapability.Response(success=False, value_json="null", failure_reason="stub boundary"))
print("stub_boundary: up", flush=True)
rclpy.spin(n)
"""


def log(kind, **kw):
    print(kind, json.dumps(kw), flush=True)


env = dict(os.environ, PYTHONUNBUFFERED="1")
console = subprocess.Popen([sys.executable, "-u", str(REPO / "experiments/operator_console/console.py"),
                            "--run-dir", str(LOG_DIR), "--answers-file", str(LOG_DIR / "answers.txt"),
                            "--default-authority-level", "tactical_goal"],
                           cwd=REPO, env=env, stdout=open(LOG_DIR / "console.log", "w"), stderr=subprocess.STDOUT)
boundary = subprocess.Popen([sys.executable, "-u", "-c", STUB_BOUNDARY], cwd=REPO, env=env,
                            stdout=open(LOG_DIR / "stub_boundary.log", "w"), stderr=subprocess.STDOUT)
try:
    time.sleep(4.0)  # rclpy init + DDS discovery on an idle offline domain -- no boot budget to wait on
    log("PLAN", executive="PLEXIL universalExec 6.1.3", plan="RequestOperatorSmoke.plx")
    t0 = time.time()
    exec_env = dict(os.environ, PLEXIL_HOME=str(PLEXIL_HOME),
                    LD_LIBRARY_PATH=f"{(REPO / 'ros/install/lib')}:{PLEXIL_HOME / 'lib'}:{os.environ.get('LD_LIBRARY_PATH', '')}")
    exec_proc = subprocess.run([str(PLEXIL_HOME / "bin/universalExec"), "-c", str(PLAN_DIR / "interface-config.xml"),
                                "-p", str(PLAN_DIR / "plans/smoke/RequestOperatorSmoke.plx")],
                               cwd=PLAN_DIR, env=exec_env, capture_output=True, text=True, timeout=30)
    # full node-transition trace (Debug.cfg picked up as ./Debug.cfg, cwd=PLAN_DIR): plan_node_id recoverable from it
    (LOG_DIR / "plexil_node_trace.log").write_text(exec_proc.stdout)
    log("EXEC", exit=exec_proc.returncode, wall_s=round(time.time() - t0, 1),
        tail=[line for line in exec_proc.stdout.splitlines() if line.strip()][-4:])
finally:
    for p in (console, boundary):
        p.terminate()
        p.wait(timeout=10)
ops = LOG_DIR / "operator/events.jsonl"
log("RESULT", operator_events=[json.loads(line) for line in ops.read_text().splitlines()] if ops.exists() else [])
