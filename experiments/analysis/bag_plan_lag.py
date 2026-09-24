"""Per global plan in a run's bag: its start point against the rover's AMCL pose at the plan's stamp and at receipt
(a planner start that stops following the rover shows here)."""
import sys, numpy as np, rosbag2_py, bisect
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=sys.argv[1], storage_id='sqlite3'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
st = lambda m: m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
amcl = []; plans = []
while r.has_next():
    topic, data, t = r.read_next()
    if topic == '/amcl_pose':
        m = deserialize_message(data, get_message(types[topic])); amcl.append((st(m), m.pose.pose.position.x, m.pose.pose.position.y))
    elif topic == '/plan':
        m = deserialize_message(data, get_message(types[topic]))
        if m.poses: plans.append((t * 1e-9, st(m), m.poses[0].pose.position.x, m.poses[0].pose.position.y))
A = np.array(amcl); ts = A[:, 0]
def at(tq):
    i = min(max(bisect.bisect_left(ts, tq), 0), len(ts) - 1); return A[i, 1:]
for k, (tb, th, sx, sy) in enumerate(plans):
    if k % 6: continue
    rb, rh = at(tb), at(th)
    print(f'plan {k:3d} recv {tb:6.1f} stamp {th:6.1f} start ({sx:5.2f},{sy:4.2f}) robot@stamp ({rh[0]:5.2f},{rh[1]:4.2f}) robot@recv ({rb[0]:5.2f},{rb[1]:4.2f})')
