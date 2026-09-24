"""Replay place's settle check (did the item stay behind? procedural_place.put_it_down, research repo F115) offline,
on a run's recorded settle depth frame, and print what the current code would decide. Runs from before the settle
record carried the camera pose need it rebuilt from the run's bag: first, in the run-farm image (ROS sourced),
    python3 replay_place_settle.py poses <run dir> <poses.json>
writes the wrist camera and the TCP in chassis_base_link at each place's settle frame (1 s into the settle stage, after
the arm is still, and 0.3 s before the call ends, to show the arm did not move in between); then, with openral's venv,
    .venv/bin/python replay_place_settle.py judge <run dir> <poses.json>
"""
import json
import sys
from pathlib import Path


def places(run: Path):
    for line in open(run / "capability_server.log"):
        if "CAPABILITY {" in line and '"capability": "place"' in line:
            d = json.loads(line[line.index("{"):])
            if any(s["stage"] == "settle" for s in d["evidence"]["skill"]["stages"]):
                yield d


def poses(run: Path, out: Path) -> None:
    import rosbag2_py
    from rclpy.duration import Duration
    from rclpy.serialization import deserialize_message
    from rclpy.time import Time
    from rosidl_runtime_py.utilities import get_message
    from tf2_ros import Buffer

    buf = Buffer(cache_time=Duration(seconds=100000))
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=str(run / "bag"), storage_id="sqlite3"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    r.set_filter(rosbag2_py.StorageFilter(topics=["/tf", "/tf_static"]))
    while r.has_next():
        topic, data, _ = r.read_next()
        for t in deserialize_message(data, get_message(types[topic])).transforms:
            (buf.set_transform_static if topic == "/tf_static" else buf.set_transform)(t, "bag")

    def pose(frame, t):
        tf = buf.lookup_transform("chassis_base_link", frame, Time(seconds=t))
        q, p = tf.transform.rotation, tf.transform.translation
        return [p.x, p.y, p.z, q.x, q.y, q.z, q.w]

    rows = []
    for d in places(run):
        settle = d["sim_t_start"] + {s["stage"]: s["t_sim"] for s in d["evidence"]["skill"]["stages"]}["settle"]
        rows.append({k: {"cam": pose("wrist_camera_optical_frame", t), "tcp": pose("tcp_frame", t)}
                     for k, t in (("a", settle + 1.0), ("late", d["sim_t_end"] - 0.3))})
    json.dump(rows, open(out, "w"), indent=1)


def matrix(p):
    import numpy as np

    x, y, z, w = p[3:]
    T = np.eye(4)
    T[:3, :3] = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                 [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                 [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    T[:3, 3] = p[:3]
    return T


def judge(run: Path, poses_json: Path) -> None:
    from types import SimpleNamespace

    import numpy as np
    from openral_rskill.procedural_pick import IN_JAWS_MIN_POINTS, in_jaws

    for d, ps in zip(places(run), json.load(open(poses_json))):
        st = d["evidence"]["skill"]["settle"]
        T_bc = np.array(st["T_base_cam"]) if "T_base_cam" in st else matrix(ps["a"]["cam"])
        moved = float(np.linalg.norm(matrix(ps["a"]["cam"])[:3, 3] - matrix(ps["late"]["cam"])[:3, 3]))
        K = np.array(st.get("K") or [[st["fx"], 0, 320.0], [0, st["fx"], 240.0], [0, 0, 1]])
        n = in_jaws(SimpleNamespace(depth=np.load(st["before_depth"]), K=K), np.linalg.inv(matrix(ps["a"]["tcp"])) @ T_bc)
        print(f"{run.parent.name}/{run.name:24s} {d['args']['support']:24s} reported {'ok' if d['success'] else 'FAIL'}; "
              f"{n:5d} points between the fingers -> {'CAME AWAY WITH THE TOOL' if n >= IN_JAWS_MIN_POINTS else 'passes'}"
              f"   [camera moved {moved * 1000:.1f} mm during settle]")


if __name__ == "__main__":
    {"poses": poses, "judge": judge}[sys.argv[1]](Path(sys.argv[2]), Path(sys.argv[3]))
