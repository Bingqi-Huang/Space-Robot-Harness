"""Per /tf edge in a run's bag: first and last stamp (which edges stopped updating, and when)."""
import sys, rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=sys.argv[1], storage_id='sqlite3'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
last = {}; first = {}
while r.has_next():
    topic, data, t = r.read_next()
    if topic not in ('/tf', '/tf_static'): continue
    m = deserialize_message(data, get_message(types[topic]))
    for tr in m.transforms:
        k = (topic, tr.header.frame_id, tr.child_frame_id)
        s = tr.header.stamp.sec + tr.header.stamp.nanosec * 1e-9
        first.setdefault(k, s); last[k] = s
for k in sorted(last, key=lambda k: last[k]):
    if 'Link' in k[2] or 'eg2' in k[2] or 'finger' in k[2]: continue
    print(f'{k[0]:10s} {k[1]:>24s} -> {k[2]:<28s} first {first[k]:7.1f} last {last[k]:7.1f}')
