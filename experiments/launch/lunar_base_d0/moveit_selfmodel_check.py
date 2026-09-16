"""Offline MoveIt check of the LunarBot self-model (no simulator): standalone move_group on its own ROS domain,
a fake /joint_states publisher, state-validity queries for the arm's reference poses and plan_only requests
for the work-pose targets the missions use.

    ROS_DOMAIN_ID=79 python moveit_selfmodel_check.py    # after `ros2 launch rm_75_config move_group.launch.py`

Prints one JSON line per check: VALID (is the pose collision-free in the self-model?) and PLAN (did MoveIt
find a path, how long, where does the last waypoint put the TCP).
"""
import json
import math
import sys
import time

import numpy as np
import rclpy
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint, OrientationConstraint, PositionConstraint, RobotState
from moveit_msgs.srv import GetStateValidity
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive

ARM = [f"joint{i}" for i in range(1, 8)]
POSES = dict(zero=[0.0] * 7, stow=[0.0, -0.6, 0.0, 1.2, 0.0, 0.6, 0.0], ready=[0.0, -1.0, 0.0, -1.4, 0.0, 1.2, 0.0])
MOUNT = np.array([-0.4475, 0.0, 0.727])


def grip_frame(n_xy):
    z = np.array([-n_xy[0], -n_xy[1], 0.0]); z /= np.linalg.norm(z)
    x = np.cross([0.0, 0.0, 1.0], z); x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z, x), z], axis=1)


def tool_frame(n_xy):
    z = np.array([-n_xy[0], -n_xy[1], 0.0]); z /= np.linalg.norm(z)
    x = np.array([0.0, 0.0, 1.0])
    return np.stack([x, np.cross(z, x), z], axis=1)


def mat_to_quat(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = [0.0] * 4
    q[i], q[j], q[k], q[3] = 0.25 * s, (R[j, i] + R[i, j]) / s, (R[k, i] + R[i, k]) / s, (R[k, j] - R[j, k]) / s
    return q


rclpy.init()
n = Node("moveit_selfmodel_check")
js_pub = n.create_publisher(JointState, "/joint_states", 10)
current = list(POSES["stow"])


def tick():
    m = JointState(); m.header.stamp = n.get_clock().now().to_msg(); m.name = ARM; m.position = list(current); m.velocity = [0.0] * 7
    js_pub.publish(m)


timer = n.create_timer(0.05, tick)


def spin(s):
    t = time.time()
    while time.time() - t < s:
        rclpy.spin_once(n, timeout_sec=0.05)


def log(kind, **kw):
    print(kind, json.dumps(kw, default=lambda o: round(float(o), 4)), flush=True)


validity = n.create_client(GetStateValidity, "/check_state_validity")
if not validity.wait_for_service(timeout_sec=60):
    log("RESULT", error="no /check_state_validity"); sys.exit(2)
spin(2.0)
for name, q in POSES.items():
    req = GetStateValidity.Request(); req.group_name = "rm_group"
    req.robot_state.joint_state.name = ARM; req.robot_state.joint_state.position = q
    f = validity.call_async(req); rclpy.spin_until_future_complete(n, f, timeout_sec=10)
    r = f.result()
    log("VALID", pose=name, valid=bool(r.valid) if r else None, contacts=[(c.contact_body_1, c.contact_body_2) for c in (r.contacts if r else [])][:6])

ac = ActionClient(n, MoveGroup, "/move_action")
assert ac.wait_for_server(timeout_sec=60)


def plan(name, start, tcp_c, R_c, link="Link7", tol=0.01):
    global current
    current = list(start); spin(1.0)
    p = np.asarray(tcp_c) - (R_c @ np.array([0.0, 0.0, 0.14]) if link == "Link7" else 0.0)
    q = mat_to_quat(R_c)
    goal = MoveGroup.Goal()
    req = goal.request
    req.group_name = "rm_group"; req.num_planning_attempts = 10; req.allowed_planning_time = 10.0
    req.max_velocity_scaling_factor = 0.3; req.max_acceleration_scaling_factor = 0.3
    req.start_state.joint_state.name = ARM; req.start_state.joint_state.position = list(start); req.start_state.is_diff = False
    c = Constraints()
    pc = PositionConstraint(); pc.header.frame_id = "chassis_base_link"; pc.link_name = link
    pc.constraint_region.primitives.append(SolidPrimitive(type=SolidPrimitive.SPHERE, dimensions=[tol]))
    from geometry_msgs.msg import Pose
    pose = Pose(); pose.position.x, pose.position.y, pose.position.z = map(float, p); pose.orientation.w = 1.0
    pc.constraint_region.primitive_poses.append(pose); pc.weight = 1.0
    oc = OrientationConstraint(); oc.header.frame_id = "chassis_base_link"; oc.link_name = link
    oc.orientation.x, oc.orientation.y, oc.orientation.z, oc.orientation.w = map(float, q)
    oc.absolute_x_axis_tolerance = oc.absolute_y_axis_tolerance = oc.absolute_z_axis_tolerance = 0.05; oc.weight = 1.0
    c.position_constraints.append(pc); c.orientation_constraints.append(oc)
    req.goal_constraints.append(c)
    goal.planning_options.plan_only = True
    t = time.time()
    f = ac.send_goal_async(goal); rclpy.spin_until_future_complete(n, f, timeout_sec=30)
    h = f.result()
    if not h or not h.accepted:
        log("PLAN", name=name, accepted=False); return
    rf = h.get_result_async(); rclpy.spin_until_future_complete(n, rf, timeout_sec=60)
    r = rf.result().result
    traj = r.planned_trajectory.joint_trajectory
    last = list(traj.points[-1].positions) if traj.points else None
    log("PLAN", name=name, link=link, error_code=r.error_code.val, n_points=len(traj.points), planning_time_s=round(r.planning_time, 2), wall_s=round(time.time() - t, 1),
        last_q=[round(v, 3) for v in last] if last else None, max_joint_travel=round(max(abs(a - b) for a, b in zip(last, start)), 3) if last else None)


R_g = grip_frame((1.0, 0.0))  # jaws horizontal, tool z = -X (a payload handle behind the rover)
R_t = tool_frame((1.0, 0.0))  # jaws vertical, tool z = -X (a button/panel behind the rover)
plan("ready->pre-grasp 0.45m past hull z0.90", POSES["ready"], [-1.118, 0.0, 0.90], R_g)
plan("stow->pre-grasp 0.45m past hull z0.90", POSES["stow"], [-1.118, 0.0, 0.90], R_g)
plan("ready->press pose z0.85 tool_frame", POSES["ready"], [-1.118, 0.0, 0.85], R_t)
plan("ready->pre-grasp via tcp_frame link", POSES["ready"], [-1.118, 0.0, 0.90], R_g, link="tcp_frame")
plan("ready->over deck (should fail: deck collision)", POSES["ready"], [0.1, 0.0, 0.70], R_t)
log("RESULT", done=True)
