"""PLEXIL run -> a sim-time-stamped event list for `plexil_mission_video.py` (§14.6-adjacent, but a video-specific
reading of the logs, not the evaluation-schema normalizer -- same split as `mission_video.py`'s own `timeline()`,
which is deliberately not `space_runtime`'s fact reducer).

    openral/.venv/bin/python experiments/video/plexil_timeline_from_logs.py <run dir> <out.json>

PLEXIL has no `events.jsonl`: `universalExec`'s own node-transition trace (`plexil_node_trace.log`,
`baselines/plexil/Debug.cfg`'s `Node:transition`) is stamped on the wall clock, not the simulation clock the video
plays on -- unlike Ours, whose `events.jsonl` already carries `sim_t`. `sim_clock.wall_to_sim` resolves it from the
run's own evaluator record (every pose stamped with both clocks). The capability boundary's own call trace
(`capability_server.log`'s `"CAPABILITY {...}"` lines, the same log `evaluation/baselines/plexil_normalize.py` reads)
carries each call's `sim_t_start`/`sim_t_end` itself.

Node-level granularity kept: the plan's five top-level Sequence children (ToSource, Pick, ToDestination, Place, Return --
`baselines/plexil/plans/MissionB_Covered.ple`) and the four reusable library calls they invoke (DriveAndDock,
PickItem, PlaceItem, StowAndReturn -- `baselines/plexil/plans/lib/`). Finer leaf nodes (Nav, Dock, Ready, and the
library-internal nodes that share a name with their own top-level caller, e.g. PickItem's own `Pick`) are not
tracked: a viewer needs which step of the plan is running and which capability is in flight, not PLEXIL's own
node-state-machine detail. The five top-level names are told apart from their same-named library-internal children
by simple occurrence order: the Sequence declares all five as `INACTIVE` before any of them starts, so each's
*first* appearance in the trace is its own top-level pointer -- verified against this run's trace, not assumed.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_clock import wall_to_sim

# Mission B's five top-level Sequence children; a mission with a different plan shape (e.g. Mission A's
# ToUnit/Press/Return) passes its own list as main()'s third argument -- same names its own .ple declares.
TOP = ["ToSource", "Pick", "ToDestination", "Place", "Return"]
LIB = ["DriveAndDock", "PickItem", "PlaceItem", "StowAndReturn"]
_TRANSITION_RE = re.compile(r"Transitioning (\S+) (\S+) from (\S+) to (\S+) at ([\d.]+)")
_CAP_LOG_RE = re.compile(r"^\[INFO\] \[([\d.]+)\] \[space_capability_server\]: CAPABILITY (\{.*\})\s*$")


def parse_node_trace(trace_log: Path, to_sim, top: list[str] = TOP) -> list[dict]:
    events, top_ptr = [], {}
    for line in trace_log.read_text(errors="replace").splitlines():
        m = _TRANSITION_RE.search(line)
        if not m:
            continue
        name, ptr, _frm, to, wall = m.group(1), m.group(2), m.group(3), m.group(4), float(m.group(5))
        if name in top:
            top_ptr.setdefault(name, ptr)
            if top_ptr[name] != ptr:
                continue  # a library-internal node that happens to share its top-level caller's name
            events.append({"kind": "node_status", "sim_t": to_sim(wall), "name": name, "level": "top", "state": to})
        elif name in LIB:
            events.append({"kind": "node_status", "sim_t": to_sim(wall), "name": name, "level": "lib", "state": to})
    return events


def parse_capability_log(log: Path) -> list[dict]:
    events = []
    for line in log.read_text(errors="replace").splitlines():
        m = _CAP_LOG_RE.match(line)
        if not m:
            continue
        data = json.loads(m.group(2))
        events.append({"kind": "capability", "sim_t_start": data["sim_t_start"], "sim_t_end": data["sim_t_end"],
                       "capability": data.get("capability"), "args": data.get("args"), "success": data.get("success"),
                       "failure_reason": data.get("failure_reason")})
    return events


def main(run_dir: str, out: str, top: list[str] = TOP) -> None:
    run = Path(run_dir)
    events = parse_node_trace(run / "plexil_node_trace.log", wall_to_sim(run), top) + parse_capability_log(run / "capability_server.log")
    events.sort(key=lambda e: e.get("sim_t", e.get("sim_t_start", 0.0)))
    Path(out).write_text(json.dumps({"run": run_dir, "events": events}))
    print(f"{len(events)} events -> {out}")


if __name__ == "__main__":
    # optional 4th arg: comma-separated top-level node names for a plan whose shape isn't Mission B's
    main(sys.argv[1], sys.argv[2], sys.argv[3].split(",") if len(sys.argv) > 3 else TOP)
