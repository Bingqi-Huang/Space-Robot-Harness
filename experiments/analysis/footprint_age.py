"""One-shot, live: how far the local / global costmap footprints and AMCL's map->odom lag the sim clock."""
import time, rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PolygonStamped
from rosgraph_msgs.msg import Clock
from tf2_msgs.msg import TFMessage
rclpy.init(); n = Node('footprint_age'); s = {}
st = lambda h: h.stamp.sec + h.stamp.nanosec * 1e-9
n.create_subscription(Clock, '/clock', lambda m: s.update(clock=m.clock.sec + m.clock.nanosec * 1e-9), qos_profile_sensor_data)
n.create_subscription(PolygonStamped, '/local_costmap/published_footprint', lambda m: s.update(local=st(m.header)), 10)
n.create_subscription(PolygonStamped, '/global_costmap/published_footprint', lambda m: s.update(glob=st(m.header)), 10)
def tf(m):
    for t in m.transforms:
        if t.header.frame_id == 'map' and t.child_frame_id == 'odom': s['amcl'] = st(t.header)
n.create_subscription(TFMessage, '/tf', tf, 100)
t0 = time.time()
while time.time() - t0 < 15: rclpy.spin_once(n, timeout_sec=0.2)
c = s.get('clock', 0.0)
print({k: round(c - v, 1) for k, v in s.items() if k != 'clock'}, 'clock', round(c, 1))
