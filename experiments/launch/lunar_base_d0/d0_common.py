"""Phase D0 (execution_plan §21.4) capability-path check helpers, shared by the Mission A/B scripts.

Every motion is an `ExecuteRskill` dispatch through the OpenRAL runner -> kernel -> HAL -> SRB
(no oracle, no direct simulator commands): Nav2 navigate_to_pose, move_base_to_pose (dock into
the work pose), move_joints / move_ee_to_pose / MoveIt eef_pose (arm), grasp / release. Success is
the task's own verifier (`/srb/env0/mission_state`).

Localization is realistic (F50 §4): `/odom` is wheel-inertial odometry and AMCL on the surveyed
map authors `map -> odom`. The base is driven and docked in `map` -- the robot's own estimate. The
simulator pose (`/openral/pose_truth`) is used for two things only: measuring errors, and the arm's
target relative to the rover, which stands in for the relative perception of Phase E (the arm owns
the terminal centimetres, user decision) -- objects' world poses are site knowledge, where the rover
is relative to them is not.

Importing this module connects to the graph and waits until Nav2, the rskill runner and TF are
ready. Each `run()` step prints one `STEP` JSON line with the dispatch result and the measured
precision (F50). D0_STEPS="1,2,3" limits the steps; D0_CONTINUE_ON_FAIL=1 keeps going after a
failed step.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.srv import GetState
from openral_msgs.action import ExecuteRskill
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.time import Time
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

HERE = Path(__file__).resolve().parent
IX = json.loads((HERE / "../../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json").resolve().read_text())
HULL = IX["robot"]["hull_x_back_m"]
REACH = IX["robot"]["reach_m"]["pick"]
READY = [0.0, -1.0, 0.0, -1.4, 0.0, 1.2, 0.0]
SKILL = dict(
    nav="OpenRAL/rskill-nav2-mobile_base-navigate_to_pose",
    dock="OpenRAL/rskill-procedural-mobile_base-move_base_to_pose",
    joints="OpenRAL/rskill-procedural-lunar_bot-move_joints",
    stow="OpenRAL/rskill-procedural-lunar_bot-stow",
    ee="OpenRAL/rskill-procedural-lunar_bot-move_ee_to_pose",
    moveit="OpenRAL/rskill-moveit-multi-eef_pose",
    grasp="OpenRAL/rskill-procedural-lunar_bot-grasp",
    release="OpenRAL/rskill-procedural-lunar_bot-release",
)
TRACE_OBJ = os.environ.get("D0_TRACE_OBJECT")  # e.g. spare_oru: sample its handle against the TCP during every step
STEPS = {int(s) for s in os.environ.get("D0_STEPS", "").split(",") if s.strip()} or set(range(1, 30))

rclpy.init()
n = Node("d0_mission_b_check", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
buf = Buffer()
TransformListener(buf, n)
mission = {}
n.create_subscription(String, "/srb/env0/mission_state", lambda m: mission.update(json.loads(m.data)), 10)
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
vel = dict(cmd=[], srb=[], odom=[])  # Nav2's /cmd_vel, what the HAL hands SRB, and measured /odom base speeds during a base step
n.create_subscription(Twist, "/cmd_vel", lambda m: vel["cmd"].append((round(m.linear.x, 3), round(m.angular.z, 3))), 50)
n.create_subscription(Twist, "/srb/env0/action/cmd_vel", lambda m: vel["srb"].append((round(m.linear.x, 3), round(m.angular.z, 3))), 50)
n.create_subscription(Odometry, "/odom", lambda m: vel["odom"].append((round(m.twist.twist.linear.x, 3), round(m.twist.twist.angular.z, 3))), 50)
truth = {}  # latest /openral/pose_truth: evaluator-only
from sensor_msgs.msg import JointState
jaw = {}  # EG2 jaw joint (rad): 0.10 closed on nothing, 0.82 open -- "clamped, not hanging" is measured, not inferred
n.create_subscription(JointState, "/srb/env0/robot/joint_states",
                      lambda m: jaw.update(q=m.position[m.name.index("eg2_joint1")]) if "eg2_joint1" in m.name else None, 10)
n.create_subscription(Odometry, "/openral/pose_truth", lambda m: truth.update(p=m.pose.pose.position, q=m.pose.pose.orientation), 10)
T0 = time.time()
sim = dict(t=0.0)  # SRB's /clock: a rendering graph runs at a fraction of real time, and every skill
n.create_subscription(Clock, "/clock", lambda m: sim.update(t=m.clock.sec + m.clock.nanosec * 1e-9), 10)  # timeout is measured on it (F50)


def log(kind, **kw):
    print(kind, json.dumps(dict(t=round(time.time() - T0, 1), **kw), default=lambda o: round(float(o), 4) if isinstance(o, (np.floating, float)) else str(o)), flush=True)


def spin(seconds):
    t = time.time()
    while time.time() - t < seconds:
        rclpy.spin_once(n, timeout_sec=0.05)


# ---- geometry ---------------------------------------------------------------------------------------------------
def quat_to_mat(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def mat_to_quat(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    i = int(np.argmax(np.diag(R)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = [0.0, 0.0, 0.0, 0.0]
    q[i], q[j], q[k], q[3] = 0.25 * s, (R[j, i] + R[i, j]) / s, (R[k, i] + R[i, k]) / s, (R[k, j] - R[j, k]) / s
    return q


def tf(target, source, timeout=10.0):
    t = time.time()
    while time.time() - t < timeout:
        rclpy.spin_once(n, timeout_sec=0.05)
        if buf.can_transform(target, source, Time()):
            tr = buf.lookup_transform(target, source, Time()).transform
            p = np.array([tr.translation.x, tr.translation.y, tr.translation.z])
            R = quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w)
            return p, R
    raise RuntimeError(f"no TF {target} <- {source}")


def tool_frame(n_xy):
    """Tool +Z into the surface (-n), jaw axis vertical: pressing / flat features (lunar_oracle.tool_frame)."""
    z = np.array([-n_xy[0], -n_xy[1], 0.0])
    z /= np.linalg.norm(z)
    x = np.array([0.0, 0.0, 1.0])
    return np.stack([x, np.cross(z, x), z], axis=1)


def grip_frame(n_xy):
    """Tool +Z into the surface (-n), jaw axis horizontal (lunar_oracle.grip_frame, F49)."""
    z = np.array([-n_xy[0], -n_xy[1], 0.0])
    z /= np.linalg.norm(z)
    x = np.cross([0.0, 0.0, 1.0], z)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z, x), z], axis=1)


def truth_pose():
    """The simulator's base pose (world = map by construction). Evaluation and the Phase-E relative-perception stand-in only."""
    rclpy.spin_once(n, timeout_sec=0.05)
    p, q = truth["p"], truth["q"]
    R = quat_to_mat(q.x, q.y, q.z, q.w)
    return np.array([p.x, p.y, p.z]), math.atan2(R[1, 0], R[0, 0]), R


def est_pose(frame="map"):
    """The robot's own estimate of its base pose: `map` (AMCL) or `odom` (wheel-inertial)."""
    p, R = tf(frame, "chassis_base_link")
    return p, math.atan2(R[1, 0], R[0, 0]), R


def tcp_pose():
    """TCP in the world, through the true base pose (evaluation)."""
    pb, _, Rb = truth_pose()
    pc, Rc = tf("chassis_base_link", "tcp_frame")
    return pb + Rb @ pc, Rb @ Rc


def to_rover(p_w, R_w):
    """A world target in chassis_base_link, as relative perception would report it (Phase E stand-in)."""
    pb, _, Rb = truth_pose()
    return Rb.T @ (np.asarray(p_w) - pb), Rb.T @ R_w


def handle_pos(name):
    p, R = tf("srb/world", f"srb/env0/lb_{name}")
    return p + R @ np.array(IX["objects"][name]["handle"]["xyz"])


def work_pose(point_xy, normal):
    nn = np.array(normal[:2], float)
    nn /= np.linalg.norm(nn)
    return np.array(point_xy[:2]) + nn * (HULL + REACH), math.atan2(nn[1], nn[0]), nn


# ---- dispatch -----------------------------------------------------------------------------------------------------
ac = ActionClient(n, ExecuteRskill, "/openral/execute_rskill")


def dispatch(key, params, deadline=120.0, prompt=""):
    goal = ExecuteRskill.Goal()
    goal.rskill_id = SKILL[key]
    goal.prompt = prompt or f"d0 {key} {int(time.time())}"
    goal.goal_params_json = json.dumps(params)
    goal.deadline_s = float(deadline)
    t, sim0 = time.time(), sim["t"]
    h = None
    for attempt in range(3):  # the runner's first goal response after boot has taken >30 s (run 7)
        f = ac.send_goal_async(goal)
        rclpy.spin_until_future_complete(n, f, timeout_sec=90)
        h = f.result()
        if h is not None:
            break
        log("RETRY", key=key, attempt=attempt + 1, waited_s=round(time.time() - t, 1))
    if h is None or not h.accepted:
        return dict(success=False, failure_reason="goal rejected" if h is not None else "no goal response", wall_s=round(time.time() - t, 1))
    rf = h.get_result_async()
    track, last, obj, last_obj = [], 0.0, [], 0.0
    # the hard deadline is on the sim clock like the skill's own budget: a rendering graph at 0.06x gave a 400 s
    # Nav2 goal 28 s of sim time on the wall and abandoned a rover still driving correctly (F51, run av1)
    while not rf.done() and sim["t"] - sim0 < deadline + 60:
        rclpy.spin_once(n, timeout_sec=0.1)
        if time.time() - last > 3.0 and truth and buf.can_transform("map", "chassis_base_link", Time()):  # sparse track: truth | map estimate
            tr = buf.lookup_transform("map", "chassis_base_link", Time()).transform
            pt, yt, _ = truth_pose()
            track.append((round(float(pt[0]), 2), round(float(pt[1]), 2), round(math.degrees(yt)),
                          round(tr.translation.x, 2), round(tr.translation.y, 2), round(math.degrees(2 * math.atan2(tr.rotation.z, tr.rotation.w)))))
            last = time.time()
        if TRACE_OBJ and time.time() - last_obj > 0.5 and truth and buf.can_transform("srb/world", f"srb/env0/lb_{TRACE_OBJ}", Time()) \
                and buf.can_transform("chassis_base_link", "tcp_frame", Time()):
            tr = buf.lookup_transform("srb/world", f"srb/env0/lb_{TRACE_OBJ}", Time()).transform
            Ro = quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w)
            hp = np.array([tr.translation.x, tr.translation.y, tr.translation.z]) + Ro @ np.array(IX["objects"][TRACE_OBJ]["handle"]["xyz"])
            tc = buf.lookup_transform("chassis_base_link", "tcp_frame", Time()).transform
            pt, _, Rt = truth_pose()
            tw = pt + Rt @ np.array([tc.translation.x, tc.translation.y, tc.translation.z])
            obj.append((round(sim["t"] - sim0, 1), round(float(hp[2]), 3), round(float(np.linalg.norm(hp - tw)), 3), round(float(pt[0]), 2), round(float(pt[1]), 2),
                        round(float(jaw.get("q", -1.0)), 3)))
            last_obj = time.time()
    out = dict(wall_s=round(time.time() - t, 1), sim_s=round(sim["t"] - sim0, 1),
               sim_rate=round((sim["t"] - sim0) / max(time.time() - t, 1e-6), 2))
    if obj:
        out["obj_track"] = obj  # (sim s, handle z, handle-TCP distance, base x, base y, jaw rad)
    out["jaw_rad"] = round(float(jaw.get("q", -1.0)), 3)
    if key in ("nav", "dock"):
        out["track"] = track
        for src in ("cmd", "srb", "odom"):
            s = vel[src]
            if s:
                v = [abs(a) for a, _ in s]; w = [abs(b) for _, b in s]
                out[f"{src}_v_max"], out[f"{src}_v_mean"], out[f"{src}_w_max"], out[f"{src}_n"] = round(max(v), 3), round(sum(v) / len(v), 3), round(max(w), 3), len(s)
    vel["cmd"].clear(); vel["srb"].clear(); vel["odom"].clear()
    if not rf.done():
        return dict(success=False, failure_reason="no result before hard deadline", **out)
    r = rf.result().result
    return dict(success=bool(r.success), failure_reason=r.failure_reason, failure_kind=int(r.failure_kind), **out)


def nav(xy, yaw):
    """Drive to a site pose with Nav2. The surveyed map is in site coordinates, so the goal goes to `map` as is."""
    return dispatch("nav", {"pose": {"header": {"frame_id": "map"}, "pose": {
        "position": {"x": float(xy[0]), "y": float(xy[1]), "z": 0.0},
        "orientation": {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)}}}}, deadline=400)


def staging(xy, yaw, approach_m=1.5):
    """Where the docking skill lines up: `approach_m` in front of the work pose, along its own axis,
    already facing the way it will enter. Handing Nav2 THIS pose (not the work pose facing the site)
    saves the dock a 180 deg in-place turn -- which cost 90 of its 180 s at PDU-2 (research repo F50)."""
    d = np.array([math.cos(yaw), math.sin(yaw)])
    return np.asarray(xy, float) + d * approach_m, yaw


def dock(xy, yaw, **kw):
    """Close the last metre on the site pose, in `map` (AMCL). The kernel bounds the base at 0.5 rad/s and the
    4WIS chassis realises ~2/3 of a commanded in-place turn (F43), so a 180 deg turn-in-place needs
    ~15 s -- hence the wide stall/overall timeouts."""
    params = dict(frame_id="map", position=[float(xy[0]), float(xy[1])], yaw=float(yaw),
                  max_angular_speed_rad_s=0.45, stall_timeout_s=20.0, timeout_s=180.0)
    params.update(kw)
    return dispatch("dock", params, deadline=240)


def ee(p_w, R_w, tol=0.015, timeout=25.0, hold_s=3.0, **kw):
    """Servo the TCP to a world pose via move_ee_to_pose; target expressed in chassis_base_link (to_rover)."""
    p_c, R_c = to_rover(p_w, R_w)
    res = dispatch("ee", dict(frame_id="chassis_base_link", position=p_c.tolist(), quaternion_xyzw=mat_to_quat(R_c),
                              pos_tolerance_m=tol, timeout_s=timeout, **kw), deadline=timeout + 20)
    p1, _ = tcp_pose()
    err_at_result = float(np.linalg.norm(p1 - p_w))
    spin(hold_s)
    p2, _ = tcp_pose()
    res.update(tcp_err_m=round(err_at_result, 4), tcp_err_after_hold_m=round(float(np.linalg.norm(p2 - p_w)), 4), hold_drift_m=round(float(np.linalg.norm(p2 - p1)), 4))
    return res


def moveit(p_w, R_w, tol=0.01):
    """Plan with MoveIt to a world TCP pose.

    The LunarBot self-model (`rm_75_config/config/lunarbot_body.xacro`) makes `chassis_base_link` the
    planning frame and carries `tcp_frame` as a link, so the goal is the TCP pose in the rover frame --
    no TF re-expression and no hand-applied tool offset.
    """
    p_c, R_c = to_rover(p_w, R_w)
    # posture preference: keep the shoulder on the working branch (joint1 near 0) and the wrist unspun
    res = dispatch("moveit", {"pose": {"frame_id": "chassis_base_link", "link_name": "tcp_frame", "position": p_c.tolist(), "orientation": mat_to_quat(R_c),
                                       "quaternion_order": "xyzw", "position_tolerance_m": tol, "orientation_tolerance_rad": 0.05},
                              "joint_constraints": [{"joint": "joint1", "position": 0.0, "tolerance_above": 1.5, "tolerance_below": 1.5},
                                                    {"joint": "joint7", "position": 0.0, "tolerance_above": 3.0, "tolerance_below": 3.0}],
                              "request": {"group_name": "rm_group", "allowed_planning_time": 10.0, "num_planning_attempts": 10}}, deadline=120)
    spin(1.0)
    p1, _ = tcp_pose()
    res.update(tcp_err_m=round(float(np.linalg.norm(p1 - p_w)), 4))
    return res


def _yaw_deg(a, b):
    return round(math.degrees((a - b + math.pi) % (2 * math.pi) - math.pi), 1)


def base_err(xy, yaw):
    """Where the base is against (xy, yaw): physically (pos_err, truth), in the robot's belief (map_pos_err, AMCL),
    and how wrong each estimate is (loc_err: AMCL vs truth; odom_err: wheel-inertial odometry vs truth -- odom
    starts at the dock, the map origin, so the two frames coincide at t=0)."""
    pt, yt, _ = truth_pose()
    pm, ym, _ = est_pose("map")
    po, yo, _ = est_pose("odom")
    goal = np.asarray(xy, float)
    return dict(pos_err_m=round(float(np.linalg.norm(pt[:2] - goal)), 3), yaw_err_deg=_yaw_deg(yt, yaw),
                map_pos_err_m=round(float(np.linalg.norm(pm[:2] - goal)), 3), map_yaw_err_deg=_yaw_deg(ym, yaw),
                loc_err_m=round(float(np.linalg.norm(pm[:2] - pt[:2])), 3), loc_yaw_err_deg=_yaw_deg(ym, yt),
                odom_err_m=round(float(np.linalg.norm(po[:2] - pt[:2])), 3), odom_yaw_err_deg=_yaw_deg(yo, yt),
                at=[round(float(pt[0]), 3), round(float(pt[1]), 3)], map_at=[round(float(pm[0]), 3), round(float(pm[1]), 3)])


# ---- readiness ---------------------------------------------------------------------------------------------------
def lifecycle_state(node):
    c = n.create_client(GetState, f"{node}/get_state")
    if not c.wait_for_service(timeout_sec=1.0):
        return None
    f = c.call_async(GetState.Request())
    rclpy.spin_until_future_complete(n, f, timeout_sec=3.0)
    return f.result().current_state.label if f.result() else None


t = time.time()
while time.time() - t < 1500:
    s = lifecycle_state("/bt_navigator")
    if s == "active" and ac.server_is_ready():
        break
    spin(3.0)
else:
    log("RESULT", error="graph never ready"); sys.exit(2)
log("READY", after_s=round(time.time() - t), bt_navigator="active")
tf("map", "chassis_base_link", timeout=600)
tf("odom", "tcp_frame", timeout=60)
while "p" not in truth:
    spin(0.5)
try:
    tf("chassis_base_link", "base_link", timeout=20)
    log("TF", arm_root="ok")
except RuntimeError as e:
    log("TF", arm_root=str(e))
# D0_ATTACH (attach_d0.sh): a held graph that is mid-mission -- probed at its boot, and opening the jaws now could drop
# what the robot holds
if not os.environ.get("D0_ATTACH"):
    spin(20.0)  # costmaps
    # Functional probe, not a presence check: `server_is_ready()` was True against a rskill runner left
    # over from an earlier run's incomplete teardown, and every real dispatch then went unanswered for
    # 90 s a piece (research repo F50). Opening the (empty) jaws is the harmless dispatch that proves the
    # runner in THIS graph answers.
    probe = dispatch("release", {"mode": "open", "timeout_s": 8.0}, deadline=15.0, prompt="d0 readiness probe")
    log("PROBE", **probe)
    if "no goal response" in probe.get("failure_reason", ""):
        log("RESULT", error="rskill runner does not answer — check for nodes left over from an earlier run on this ROS_DOMAIN_ID")
        sys.exit(2)
log("MISSION", **mission)

step = 0


def run(name, fn, *args, **kw):
    global step
    step += 1
    if step not in STEPS:
        return None
    res = fn(*args, **kw)
    log("STEP", n=step, name=name, **(res or {}))
    if res and not res.get("success", True) and os.environ.get("D0_CONTINUE_ON_FAIL") is None:
        log("RESULT", stopped_at=step, mission=dict(mission))
        sys.exit(1)
    return res

