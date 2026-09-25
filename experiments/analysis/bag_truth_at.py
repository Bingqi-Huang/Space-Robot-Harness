"""Truth poses (world frame) of frames whose name contains any of argv[3:], around bag time argv[2] (s from bag start)."""
import sys
import rosbag2_py
from rclpy.serialization import deserialize_message
from tf2_msgs.msg import TFMessage

bag, t_s, keys = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id=""), rosbag2_py.ConverterOptions("cdr", "cdr"))
r.set_filter(rosbag2_py.StorageFilter(topics=["/tf"]))
t0, names, printed = None, set(), {}
while r.has_next():
    _, data, t = r.read_next()
    t0 = t0 or t
    rel = (t - t0) / 1e9
    for tr in deserialize_message(data, TFMessage).transforms:
        f = tr.child_frame_id
        names.add(f)
        if any(k in f for k in keys) and abs(rel - t_s) < 6 and (f, round(rel)) not in printed:
            printed[(f, round(rel))] = 1
            p = tr.transform.translation
            print(f"{rel:7.1f} {tr.header.frame_id} -> {f}: {p.x:.3f} {p.y:.3f} {p.z:.3f}")
print("frames matching:", sorted(n for n in names if any(k in n for k in keys))[:20])
