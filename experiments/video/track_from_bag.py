"""Robot, held-item and gripper tracks, and Nav2's plans, from a run's closed bag, on the simulation clock.

    openral/.venv/bin/python experiments/video/track_from_bag.py <run>/bag <out.json>   (ROS sourced)

The mini-map in `mission_video.py` needs where the rover and the item in its jaws were at each moment, and the route
Nav2 was following; the bag holds both in the same clock as `ours/events.jsonl` and the frames' names. Evaluator truth
is used for drawing only: nothing here enters the mission, and the run it describes is already over.

The item in the jaws is the tracked item (`srb/env0/lb_*`) nearest the midpoint of the gripper's links, if within
`HELD_M`: measured on `step10_models/ours_qwen_l4_pdu1`, a held ORU's origin sits 0.47-0.50 m from that midpoint for
the whole carry (its base, below the handle the jaws close on), any other item >= 0.68 m.
"""
import json
import sys

import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

STEP_S = 0.2  # one sample every 0.2 s of simulation: smooth on a 30 fps mini-map
HELD_M = 0.55
PLAN_EVERY = 5  # every fifth pose of a Nav2 plan (poses are ~5 cm apart)


def rot(q) -> np.ndarray:
    w, x, y, z = q.w, q.x, q.y, q.z
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main(bag: str, out: str) -> None:
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/clock", "/tf", "/srb/env0/robot/joint_states", "/plan"]))
    clock, pose, jaw, arm = 0.0, None, None, None
    world, fingers = {}, {}  # item -> world position; gripper link -> position in the robot frame
    next_sample, track, plans = None, [], []
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
                    pose = (np.array([p.x, p.y, p.z]), rot(q))
                elif tr.child_frame_id.startswith("srb/env0/lb_"):
                    world[tr.child_frame_id.removeprefix("srb/env0/lb_")] = np.array([p.x, p.y, p.z])
                elif tr.child_frame_id.startswith("srb/env0/robot/eg2_link"):
                    fingers[tr.child_frame_id] = np.array([p.x, p.y, p.z])
        elif topic == "/plan":
            plans.append({"t": round(clock, 2), "xy": [[round(s.pose.position.x, 2), round(s.pose.position.y, 2)]
                                                       for s in msg.poses[::PLAN_EVERY]]})
        else:
            jaw, arm = msg.position[15], list(msg.position[8:15])
        if next_sample is not None and clock >= next_sample and pose is not None and fingers:
            grip = pose[0] + pose[1] @ np.mean(list(fingers.values()), axis=0)
            name, d = min(((k, float(np.linalg.norm(v - grip))) for k, v in world.items()), key=lambda kv: kv[1])
            yaw = float(np.arctan2(pose[1][1, 0], pose[1][0, 0]))
            track.append({"t": round(clock, 2), "robot": [round(float(pose[0][0]), 3), round(float(pose[0][1]), 3), round(yaw, 3)],
                          "held": {"name": name, "xyz": [round(float(v), 3) for v in world[name]]} if d < HELD_M else None,
                          "jaw": None if jaw is None else round(jaw, 4),
                          "arm": None if arm is None else [round(v, 3) for v in arm]})
            next_sample = clock + STEP_S
    with open(out, "w") as fh:
        json.dump({"bag": bag, "step_s": STEP_S, "track": track, "plans": plans}, fh)
    print(f"{len(track)} samples, sim {track[0]['t']:.1f} - {track[-1]['t']:.1f} s, {len(plans)} plans -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
