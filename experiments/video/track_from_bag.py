"""Robot, payload and gripper tracks from a run's closed bag, on the simulation clock.

    /usr/bin/python3.10 experiments/video/track_from_bag.py <run>/bag <out.json>

The mini-map in `mission_video.py` needs where the rover and the carried item were at each moment; the bag holds
that in the same clock as `ours/events.jsonl` and the video's `.times`. Evaluator truth is used for drawing only:
nothing here enters the mission, and the run it describes is already over.
"""
import json
import sys

import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

STEP_S = 0.2  # one sample every 0.2 s of simulation: smooth on a 30 fps mini-map


def main(bag: str, out: str) -> None:
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/clock", "/tf", "/srb/env0/robot/joint_states"]))
    clock, pose, item, jaw, arm = 0.0, None, None, None, None
    next_sample, track = None, []
    while reader.has_next():
        topic, data, _ = reader.read_next()
        msg = deserialize_message(data, get_message(types[topic]))
        if topic == "/clock":
            clock = msg.clock.sec + msg.clock.nanosec * 1e-9
            next_sample = clock if next_sample is None else next_sample
        elif topic == "/tf":
            for tr in msg.transforms:
                p, q = tr.transform.translation, tr.transform.rotation
                if tr.child_frame_id == "srb/env0/robot":
                    pose = [p.x, p.y, float(np.arctan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2)))]
                elif tr.child_frame_id == "srb/env0/lb_spare_oru":
                    item = [p.x, p.y, p.z]
        else:
            jaw, arm = msg.position[15], list(msg.position[8:15])
        if next_sample is not None and clock >= next_sample and pose is not None:
            track.append({"t": round(clock, 2), "robot": [round(v, 3) for v in pose],
                          "item": None if item is None else [round(v, 3) for v in item],
                          "jaw": None if jaw is None else round(jaw, 4),
                          "arm": None if arm is None else [round(v, 3) for v in arm]})
            next_sample = clock + STEP_S
    with open(out, "w") as fh:
        json.dump({"bag": bag, "step_s": STEP_S, "track": track}, fh)
    print(f"{len(track)} samples, sim {track[0]['t']:.1f} - {track[-1]['t']:.1f} s -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
