"""From a run's bag: the intervals where a Nav2 robot-pose source stops following the sim clock by > 3 s -- the local
costmap's footprint (controller_server's TF), the global costmap's footprint (planner_server's), AMCL's map->odom."""
import sys, rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=sys.argv[1], storage_id='sqlite3'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
last = {'local': None, 'global': None, 'amcl': None}; clock = 0.0; frozen = {}
st = lambda h: h.stamp.sec + h.stamp.nanosec * 1e-9
while r.has_next():
    topic, data, t = r.read_next()
    if topic == '/clock':
        clock = deserialize_message(data, get_message(types[topic])).clock.sec + 0.0
        for k, v in last.items():
            if v is not None and clock - v > 3.0 and k not in frozen: frozen[k] = (v, clock); print(f'{k} stops at {v:.1f} (clock {clock:.1f})')
            if k in frozen and v is not None and clock - v <= 3.0: print(f'{k} resumes at clock {clock:.1f} (was frozen from {frozen.pop(k)[0]:.1f})')
    elif topic == '/local_costmap/published_footprint': last['local'] = st(deserialize_message(data, get_message(types[topic])).header)
    elif topic == '/global_costmap/published_footprint': last['global'] = st(deserialize_message(data, get_message(types[topic])).header)
    elif topic == '/tf':
        for tr in deserialize_message(data, get_message(types[topic])).transforms:
            if tr.header.frame_id == 'map' and tr.child_frame_id == 'odom': last['amcl'] = st(tr.header)
print('end clock', clock, 'still frozen', {k: round(v[0], 1) for k, v in frozen.items()})
