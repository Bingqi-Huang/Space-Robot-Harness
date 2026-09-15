"""F47 live Nav2 smoke check for the lunar base (driven by run_nav2_smoke.sh)."""
import math, sys, time
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from nav2_msgs.action import NavigateToPose
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import Odometry

import os
# NAV2_GOALS="x,y;x,y" (map frame, heading 0); default: two legs along the PDU aisle
GOALS = [(*map(float, g.split(",")), 0.0) for g in os.environ.get("NAV2_GOALS", "3.0,1.5;9.0,1.5").split(";")]
rclpy.init()
from rclpy.parameter import Parameter
n = Node("f37_nav2_goal_check", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
odom = {}
n.create_subscription(Odometry, "/odom", lambda m: odom.update(x=m.pose.pose.position.x, y=m.pose.pose.position.y, vx=m.twist.twist.linear.x, t=time.time()), 10)
from geometry_msgs.msg import Twist
stream = []  # (wall t, source, value) for the stop-latency trace
n.create_subscription(Twist, "/cmd_vel", lambda m: stream.append((time.time(), "cmd_vel", round(m.linear.x, 3), round(m.angular.z, 3))), 50)
n.create_subscription(Twist, "/srb/env0/action/cmd_vel", lambda m: stream.append((time.time(), "srb_cmd_vel", round(m.linear.x, 3), round(m.angular.z, 3))), 50)
t0 = time.time()

def state(node):
    c = n.create_client(GetState, f"{node}/get_state")
    if not c.wait_for_service(timeout_sec=1.0):
        return None
    f = c.call_async(GetState.Request())
    rclpy.spin_until_future_complete(n, f, timeout_sec=3.0)
    return f.result().current_state.label if f.result() else None

last = None
while time.time() - t0 < 2400:
    s = state("/bt_navigator")
    if s != last:
        print("WAIT", round(time.time() - t0), "bt_navigator", s, "odom", {k: round(v, 3) for k, v in odom.items() if k != "t"}, flush=True)
        last = s
    if s == "active":
        break
    rclpy.spin_once(n, timeout_sec=1.0)
    time.sleep(2.0)
else:
    print("RESULT bt_navigator never active", flush=True); sys.exit(2)
print("NAV2_ACTIVE after", round(time.time() - t0), "s; odom", odom, flush=True)
from tf2_ros import Buffer, TransformListener
from rclpy.time import Time
buf = Buffer(); TransformListener(buf, n)
ts = time.time()
while time.time() - ts < 900:
    rclpy.spin_once(n, timeout_sec=0.5)
    if buf.can_transform("map", "chassis_base_link", Time()) and buf.can_transform("odom", "chassis_base_link", Time()):
        break
print("TF_READY map->odom->chassis_base_link after", round(time.time() - ts), "s", flush=True)
ts = time.time()
while time.time() - ts < 20:  # let the costmaps take a few updates
    rclpy.spin_once(n, timeout_sec=0.5)
from rcl_interfaces.srv import GetParameters
for node_name in ("/planner_server", "/controller_server", "/bt_navigator", "/behavior_server", "/smoother_server", "/velocity_smoother", "/openral_slam_toolbox", "/openral_hal_lunar_bot_sensor_bridge"):
    c = n.create_client(GetParameters, f"{node_name}/get_parameters")
    if c.wait_for_service(timeout_sec=3.0):
        f = c.call_async(GetParameters.Request(names=["use_sim_time"]))
        rclpy.spin_until_future_complete(n, f, timeout_sec=5.0)
        print("PARAM", node_name, "use_sim_time", f.result().values[0].bool_value if f.result() else None, flush=True)
    else:
        print("PARAM", node_name, "no service", flush=True)
ac = ActionClient(n, NavigateToPose, "/navigate_to_pose")
assert ac.wait_for_server(timeout_sec=60)
for gx, gy, gyaw in GOALS:
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = "map"
    goal.pose.header.stamp = n.get_clock().now().to_msg()
    goal.pose.pose.position.x, goal.pose.pose.position.y = gx, gy
    goal.pose.pose.orientation.z, goal.pose.pose.orientation.w = math.sin(gyaw / 2), math.cos(gyaw / 2)
    f = ac.send_goal_async(goal)
    rclpy.spin_until_future_complete(n, f, timeout_sec=30)
    h = f.result()
    print("GOAL", (gx, gy), "accepted", bool(h and h.accepted), flush=True)
    if not h or not h.accepted:
        continue
    rf = h.get_result_async()
    ts = time.time()
    track, last_s = [], 0.0
    while not rf.done() and time.time() - ts < 300:
        rclpy.spin_once(n, timeout_sec=0.5)
        if time.time() - last_s > 2.0 and "x" in odom:  # sparse trajectory, e.g. to see a detour
            track.append((round(odom["x"], 2), round(odom["y"], 2)))
            last_s = time.time()
    print("TRACK", (gx, gy), track, flush=True)
    status = rf.result().status if rf.done() else "timeout"
    t_done = time.time()
    stop_pose = dict(odom)
    while time.time() - t_done < 8.0:  # watch the stop: commands and odometry after the result
        rclpy.spin_once(n, timeout_sec=0.1)
    for src in ("cmd_vel", "srb_cmd_vel"):
        after = [e for e in stream if e[1] == src and e[0] >= t_done - 1.0]
        print("STOP_TRACE", (gx, gy), src, "n", len(after), "last", after[-3:] and [(round(e[0] - t_done, 2), e[2], e[3]) for e in after[-3:]], flush=True)
    print("STOP_POSE", (gx, gy), "at_result", {k: round(v, 3) for k, v in stop_pose.items() if k != "t"}, "after_8s", {k: round(v, 3) for k, v in odom.items() if k != "t"}, flush=True)
    stream.clear()
    d = math.hypot(odom.get("x", 1e9) - gx, odom.get("y", 1e9) - gy)
    print("GOAL_RESULT", (gx, gy), "status", status, "odom", {k: round(v, 2) for k, v in odom.items() if k != "t"}, "dist", round(d, 2), "secs", round(time.time() - ts), flush=True)
print("RESULT done", flush=True)
