"""PLEXIL run -> a sim-time-stamped event list for `plexil_mission_video.py` (§14.6-adjacent, but a video-specific
reading of the logs, not the evaluation-schema normalizer -- same split as `mission_video.py`'s own `timeline()`,
which is deliberately not `space_runtime`'s fact reducer).

    /usr/bin/python3.10 experiments/video/plexil_timeline_from_logs.py <run dir> <out.json>

PLEXIL has no `events.jsonl`: `universalExec`'s own node-transition trace (`plexil_node_trace.log`,
`baselines/plexil/Debug.cfg`'s `Node:transition`) and the capability boundary's own call trace
(`capability_server.log`'s `"CAPABILITY {...}"` lines, the same log `evaluation/baselines/plexil_normalize.py`
reads) are both stamped on the wall clock, not the simulation clock the video plays on -- unlike Ours,
whose `events.jsonl` already carries `sim_t`. This script is the one place that resolves it: a wall->sim
lookup table built from the run's own closed bag's `/clock` topic (the same bag `track_from_bag.py` reads for
the mini-map), the same way a video's `.times` file resolves frame index to sim time.

Node-level granularity kept: the plan's five top-level Sequence children (ToDepot, Pick, ToShelf, Place, Return --
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

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

TOP = ["ToDepot", "Pick", "ToShelf", "Place", "Return"]
LIB = ["DriveAndDock", "PickItem", "PlaceItem", "StowAndReturn"]
_TRANSITION_RE = re.compile(r"Transitioning (\S+) (\S+) from (\S+) to (\S+) at ([\d.]+)")
_CAP_LOG_RE = re.compile(r"^\[INFO\] \[([\d.]+)\] \[space_capability_server\]: CAPABILITY (\{.*\})\s*$")


def wall_to_sim(bag: Path):
    """A monotone (wall_ns, sim_s) table from the bag's own `/clock`, for `np.interp`-free linear lookup."""
    import bisect
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/clock"]))
    msg_t = get_message(types["/clock"])
    wall, sim = [], []
    while reader.has_next():
        _, data, recv_ns = reader.read_next()
        msg = deserialize_message(data, msg_t)
        wall.append(recv_ns / 1e9)
        sim.append(msg.clock.sec + msg.clock.nanosec * 1e-9)

    def convert(w: float) -> float:
        i = bisect.bisect_left(wall, w)
        if i <= 0:
            return sim[0]
        if i >= len(wall):
            return sim[-1]
        w0, w1, s0, s1 = wall[i - 1], wall[i], sim[i - 1], sim[i]
        return s0 if w1 <= w0 else s0 + (s1 - s0) * (w - w0) / (w1 - w0)
    return convert


def parse_node_trace(trace_log: Path, to_sim) -> list[dict]:
    events, top_ptr = [], {}
    for line in trace_log.read_text(errors="replace").splitlines():
        m = _TRANSITION_RE.search(line)
        if not m:
            continue
        name, ptr, _frm, to, wall = m.group(1), m.group(2), m.group(3), m.group(4), float(m.group(5))
        if name in TOP:
            top_ptr.setdefault(name, ptr)
            if top_ptr[name] != ptr:
                continue  # a library-internal node that happens to share its top-level caller's name
            events.append({"kind": "node_status", "sim_t": to_sim(wall), "name": name, "level": "top", "state": to})
        elif name in LIB:
            events.append({"kind": "node_status", "sim_t": to_sim(wall), "name": name, "level": "lib", "state": to})
    return events


def parse_capability_log(log: Path, to_sim) -> list[dict]:
    events = []
    for line in log.read_text(errors="replace").splitlines():
        m = _CAP_LOG_RE.match(line)
        if not m:
            continue
        wall, data = float(m.group(1)), json.loads(m.group(2))
        end = to_sim(wall)
        start = end - float((data.get("evidence") or {}).get("sim_s") or 0.0)
        events.append({"kind": "capability", "sim_t_start": start, "sim_t_end": end, "capability": data.get("capability"),
                       "args": data.get("args"), "success": data.get("success"), "failure_reason": data.get("failure_reason")})
    return events


def main(run_dir: str, out: str) -> None:
    run = Path(run_dir)
    to_sim = wall_to_sim(run / "robot_motion")
    events = parse_node_trace(run / "plexil_node_trace.log", to_sim) + parse_capability_log(run / "capability_server.log", to_sim)
    events.sort(key=lambda e: e.get("sim_t", e.get("sim_t_start", 0.0)))
    Path(out).write_text(json.dumps({"run": run_dir, "events": events}))
    print(f"{len(events)} events -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
