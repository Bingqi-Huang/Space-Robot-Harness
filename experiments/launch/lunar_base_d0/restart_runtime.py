"""Restart the skill-owning process (or the measured planning-scene node) on a held graph, preserving its launch
configuration.

The capability server is an action client; restarting it cannot invalidate the
runner's Python module cache. Development resumes must restart runtime_node after
skill edits. Isaac, the HAL, and the independent safety kernel stay running.
"""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys


pid, graph, log = int(sys.argv[1]), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
proc = Path(f"/proc/{pid}")
argv = proc.joinpath("cmdline").read_bytes().rstrip(b"\0").decode().split("\0")
env = dict(s.split("=", 1) for s in proc.joinpath("environ").read_bytes().rstrip(b"\0").decode().split("\0"))
name = "planning_scene" if any(a.endswith("planning_scene/node.py") for a in argv) else "runtime"
# the tag is compared as a resolved path on both sides: the graph can be launched through a symlinked
# home while this is called with the real one, and the two spellings name the same run
if str(Path(env.get("D0_RUN_TAG", "/nonexistent")).resolve()) != str(graph) or not (name == "planning_scene" or any(Path(a).name == "runtime_node" for a in argv)):
    raise SystemExit(f"PID {pid} is not this graph's runtime_node or planning_scene node")
cwd = proc.joinpath("cwd").resolve()
executable = str(proc.joinpath("exe").resolve())
log.mkdir(parents=True, exist_ok=True)
fd = os.pidfd_open(pid)
os.kill(pid, signal.SIGINT)
if not select.select([fd], [], [], 10.0)[0]:
    os.kill(pid, signal.SIGKILL)
    select.select([fd], [], [], 10.0)
os.close(fd)
with (log / f"{name}.log").open("a") as out:
    child = subprocess.Popen(argv, executable=executable, cwd=cwd, env=env,
                             stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True)
record = {"old_pid": pid, "pid": child.pid, "argv": argv, "cwd": str(cwd), "graph": str(graph)}
(log / f"{name}_restart.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record), flush=True)
