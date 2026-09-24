"""Localization error over a run: the simulator's truth (srb/env0 -> srb/env0/robot) against the rover's own estimate
(map -> odom -> chassis_base_link), from a run's bag. Post-hoc evaluation only."""
import sys, math, bisect, rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=sys.argv[1], storage_id='sqlite3'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
yaw = lambda q: math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
truth, mo, oc = [], [], []
while r.has_next():
    topic, data, t = r.read_next()
    if topic != '/tf': continue
    for tr in deserialize_message(data, get_message(types[topic])).transforms:
        s = tr.header.stamp.sec + tr.header.stamp.nanosec * 1e-9; p = tr.transform.translation; y = yaw(tr.transform.rotation)
        k = (tr.header.frame_id, tr.child_frame_id)
        if k == ('srb/env0', 'srb/env0/robot'): truth.append((s, p.x, p.y, y))
        elif k == ('map', 'odom'): mo.append((s, p.x, p.y, y))
        elif k == ('odom', 'chassis_base_link'): oc.append((s, p.x, p.y, y))
def at(L, s):
    i = min(bisect.bisect_left([a[0] for a in L], s), len(L) - 1); return L[i]
step = max(1, len(oc) // 60)
for s, ox, oy, oyaw in oc[::step]:
    _, mx, my, myaw = at(mo, s); _, tx, ty, tyaw = at(truth, s)
    ex = mx + math.cos(myaw) * ox - math.sin(myaw) * oy; ey = my + math.sin(myaw) * ox + math.cos(myaw) * oy
    print(f'sim {s:6.1f} est ({ex:7.2f},{ey:6.2f}) truth ({tx:7.2f},{ty:6.2f}) err {math.hypot(ex-tx, ey-ty):.2f} m')
