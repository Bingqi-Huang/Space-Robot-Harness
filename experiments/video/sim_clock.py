"""Wall-clock -> simulation-clock lookup from a run's own closed bag's `/clock` topic. Shared by
`plexil_timeline_from_logs.py` and `europa_timeline_from_logs.py`: both baselines log on the wall clock
(`d0_common.py`'s `t = time.time() - T0` convention every D0 evaluator script uses is sim-relative only for Ours;
PLEXIL's node trace and EUROPA host's `events.jsonl` are both plain `time.time()`), but the video plays sim time,
the same clock the mini-map's track (`track_from_bag.py`) is already on. Needs the ROS-sourced python (`rosbag2_py`).
"""
import bisect
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def wall_to_sim(bag: Path):
    """A monotone (wall_s, sim_s) table from the bag's own `/clock`, for linear lookup without a numpy dependency."""
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
