"""Non-wheel contact windows from a finished run's bag: /srb/env0/contacts_robot/force_norm (per-body |F|). Name the other body
from ground truth (bag_truth_at.py) and the site layout, never from the link name.

    python3 bag_contacts.py <run>/bag     (run-farm image, ROS sourced)"""
import sys
import rosbag2_py
from rclpy.serialization import deserialize_message
from std_msgs.msg import Float32MultiArray

bag = sys.argv[1]
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id=""), rosbag2_py.ConverterOptions("cdr", "cdr"))
r.set_filter(rosbag2_py.StorageFilter(topics=["/srb/env0/contacts_robot/force_norm"]))
t0, n, hits = None, 0, {}
while r.has_next():
    _, data, t = r.read_next()
    m = deserialize_message(data, Float32MultiArray)
    names = m.layout.dim[0].label.split(",")
    t0 = t0 or t
    n += 1
    for name, f in zip(names, m.data):
        if f > 1.0 and "wheel" not in name.lower():
            hits.setdefault(name, []).append(((t - t0) / 1e9, f))
print(f"{n} messages")
for name, v in hits.items():
    print(f"{name}: {len(v)} samples, max {max(f for _, f in v):.0f} N, from {v[0][0]:.0f} s to {v[-1][0]:.0f} s (bag time)")
if not hits:
    print("no non-wheel contact above 1 N")
