#!/usr/bin/env python3
"""The common capability boundary (execution_plan §21.4): one server every method calls identically.

    /space/capability/execute  space_harness_msgs/ExecuteCapability  (effects: PLEXIL Commands, Ours' effect tools)
    /space/capability/query    space_harness_msgs/QueryCapability    (queries: PLEXIL Lookups, Ours' query tools)

The contracts (names, typed inputs, meaning) are `contracts.yaml`. An effect is checked against its contract and lowered
to `openral_msgs/ExecuteRskill` dispatches on `/openral/execute_rskill`, so every route -- Ours, PLEXIL,
EUROPA->PLEXIL -- passes through the same OpenRAL runner, safety kernel, HAL and simulator. Most effects are one
dispatch; `approach_target` is the camera-in-the-loop controller (detect the named target in the wrist camera, move
sideways, detect again, triangulate, servo to a stand-off, detect and correct), i.e. several TCP servo dispatches
closed over vision -- a controller, not a mission step. The result carries only robot-observable evidence; the mission
verifier is evaluator-only and never crosses this boundary. No mission logic lives here: no orderings, no retries.

Targets come from the robot's own sensing: site interaction points from the survey placed by the rover's
localization (AMCL, errors of several centimetres), precise contact targets from vision (`approach_target`,
`locate_in_view`: a vision-language model locates a target described in words in the camera image). No simulator
truth.

Run inside a sourced graph (ROS Humble + openral install + ros/install):
    python3 openral_ext/capability_server/node.py
"""

import base64
import json
import sys
import re
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

import cv2
import numpy as np
import rclpy
from moveit_msgs.srv import GetPositionIK
from openral_msgs.action import ExecuteRskill
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workspace.footprint import DOCK_ERROR_M, clear_distance  # noqa: E402
from workspace.reach import reach_map  # noqa: E402

#: the pick skill's own goal defaults: the boundary and the skill must answer "how far off does the camera stand"
#: with the same number, the way they already share the gripper's jaw bands
PICK_GOAL = json.loads(yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "openral/rskills/rskill-procedural-pick/rskill.yaml"
     ).read_text())["procedural"]["default_goal_json"])
from rclpy.action import ActionClient, ActionServer, CancelResponse
from rclpy.duration import Duration
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.time import Time
from rosgraph_msgs.msg import Clock
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, JointState
from std_msgs.msg import String
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability
from tf2_ros import Buffer, TransformListener

from contracts import CONTRACTS, IX, check_args, item_catalogue
# The arm's ready posture (robot, not mission). The wrist roll is half a turn: that is the branch with the wrist camera
# above the tool axis, the one every view and every grasp works from (research repo F57), and it is the posture the
# manipulation skills start and end in. `openral_rskill._eye_in_hand.READY` is the same seven numbers.
READY = [0.0, -1.0, 0.0, -1.4, 0.0, 1.2, math.pi]
#: rskill-procedural-stow's pose, and what the arm holds whenever no operation owns it: reaching back over
#: the rear hull edge with the wrist camera level and facing the way the arm works. Measured from this
#: robot's own URDF: tool 1.089 m behind the rover origin at 0.951 m, look 0.0 deg from level, 180 deg from
#: forward, elbow bent 80 deg. It replaces a pose that folded the arm up over the deck looking forward and
#: 21 deg above the horizon (F89).
STOW = [0.0, 0.40, 0.0, -0.70, 0.0, -1.27, 3.14159265]
ARM_JOINTS = [f"joint{i}" for i in range(1, 8)]
# what each interaction-point type is, as the site's equipment documentation states it
POINT_TYPES = {
    "press": "push button on a service panel; actuates when the tool tip is pushed about 1 cm past its face (jaws closed)",
    "indicator": "status lamp on a service panel: red = unit faulted, green = nominal",
    "place": "surface point where an object can be set down",
}
# the shared scene VLM (same for every method): deepseek-flash on DeepSeek's own endpoint. The models were compared on
# real wrist frames through a shared gateway (GLM-5.3-Flash and Kimi-K3 15/15, Qwen3.8-Flash 14/15; research repo F54),
# but that gateway stalled image requests coming from the runner process for the full deadline while the same request
# from a shell answered in seconds (F58). deepseek-flash reads these frames: on the recorded marked views it names the
# handle's mark, a different one per view, and answers null on a blank image.
VLM_MODEL = os.environ.get("SPACE_VLM_MODEL", "deepseek-flash")
VLM_ENDPOINT = os.environ.get("SPACE_VLM_ENDPOINT", "https://api.deepseek.com")
LOCATE_PROMPT = ('Locate {target} in this {w}x{h} camera image. Reply with JSON only: {{"found": true or false, "center": [x, y], '
                 '"box": [x1, y1, x2, y2]}} in pixel coordinates, origin at the top-left. found=false if it is not clearly visible.')
#: How gently the rover drives while the jaws hold something. Nav2's smoother otherwise ramps at 2.5 m/s^2, which is
#: what every base move used regardless of what the arm was carrying; a payload held by the interlock of a handle's
#: head on the closed fingers comes off its neck when the base snatches like that (runs g4s, g5h, both dropped on the
#: first drive after a verified grasp). The scripted oracle carries at 0.2 m/s^2 for the same reason (F49 §3), and
#: these are the shared substrate's limits, applied by the boundary to every method's base moves, not Ours' guard
#: (plan v4 §2: hardware-protecting limits while driving or holding belong to the low-level safety everyone shares).
#: A turn puts `alpha * r` of acceleration on a load held `r` from the base's own centre of rotation, so the angular
#: limit is not a number to pick: it is whatever keeps that within the straight-line limit the load is known to take.
#: In g5m the payload rode 19 m of straight driving at 0.5 m/s^2 and came off while the rover slowed and turned to
#: dock, where 1.0 rad/s^2 on the 0.84 m lever it was carried at was 0.84 m/s^2 -- more than the straight line it had
#: just survived. `r` is measured from the tool each time, because how far in the arm brought the load is not fixed.
#:
#: The straight-line limit is not a number to pick either, and 0.5 was one. A load on a handle hangs like a
#: pendulum, and a base acceleration `a` leans it off vertical by atan(a/g): the same acceleration is six times
#: the lean here that it is on Earth. 0.5 m/s^2 is 17 deg of lean on the Moon and about twice that after the step
#: that starts it, which is what g9x measured -- the ORU reached 51 deg and came off the neck with these limits in
#: force, after sitting through 40 s of the arm's own swinging, base stationary, at up to 16 deg. The same bag puts
#: the onset of prying between 10.7 deg (jaw 0.170, untouched) and 16.3 deg (0.193, opening). So the swing this
#: grasp takes is measured, the gravity is where the robot is, and the acceleration follows from the two.
#: Only reached when the environment publishes no context. It is the smallest gravity any of these bodies has,
#: not the largest: the acceleration a hanging load takes scales with g, so not knowing where you are has to
#: buy the gentlest driving, never the fastest (Earth here would have permitted six times the lunar limit).
UNKNOWN_BODY_G_M_S2 = 0.14219  # srb.core.domain.Domain.ASTEROID, the least gravity in the table
CARRY_SWING_RAD = math.radians(10.0)  # the largest swing the jaw was never disturbed by (g9x, base stationary)
#: Straight line and turn are not two separate allowances: g9x drove at 0.5 m/s^2 with 0.64 rad/s^2 on a 0.787 m
#: lever, which is another 0.50 m/s^2 at the load, and 1.0 m/s^2 together leans it 32 deg and overshoots to about
#: 51 -- the angle the bag recorded when the ORU came off. The budget is what reaches the load, so each gets half.
def carry_budget(gravity_m_s2: float) -> float:
    """The acceleration a load hanging from the jaws may be given, on the body the robot is standing on."""
    return gravity_m_s2 * math.tan(CARRY_SWING_RAD / 2)
#: A turn is the one move that spends the budget continuously, and `CARRY_SWING_RAD` is a *transient* tolerance --
#: the largest swing the jaw rode out, measured with the base standing still. Held for seconds it is not ridden
#: out: the load slips round the neck instead, and the slip does not come back. In ga4 the same grasp carried the
#: ORU through 185 and 173 deg of heading and held (median yaw rate 0.02 and 0.03 rad/s, brief peaks at 0.35), then
#: lost it in 9 s of turning at a median of 0.29 -- 23 deg of twist about the neck, jaws pried 0.188 -> 0.232, ORU
#: on the ground (F83). The two populations separate at 0.15 rad/s: the drives that held spent 8% and 11% of their
#: samples above it, the one that slipped spent 64%. This is that separation, not a derivation; what sets it is the
#: friction a flat 12 x 30 mm neck offers against twist, and that is still owed a model.
CARRY_SUSTAINED_YAW_RAD_S = 0.15
CARRY_MAX_SPEED = [0.25, 0.0, 1.0]
FREE_MAX_VELOCITY = [0.5, 0.0, 2.0]
FREE_MAX_ACCEL = [2.5, 0.0, 3.2]
FREE_MAX_DECEL = [-2.5, 0.0, -3.2]
BASE_MOVES = ("navigate_to_pose", "navigate_to_feature", "dock_to_pose", "dock_at_feature", "move_base_delta")

HELD_PROMPT = ("This camera is mounted on a robot's own gripper and looks out past its fingers; the fingers are the "
               "dark shapes along the bottom of the frame. Say whether anything is held between them, and what it is. "
               'Reply with JSON only: {"holding": true or false, "what": "<what is between the fingers, a few words, '
               'or an empty string>"}')
VLM_LOCATE_ASKS, VLM_LOCATE_MIN_FOUND = 3, 2  # concurrent localisation asks; how many must find the target
DEPTH_WINDOW_PX = 3  # half-width of the depth patch around the located pixel (median of the valid depths)
ARM_WORKING_RADIUS_M = 0.61  # RealMan RM-75 datasheet (docs/lunar_bot_rm75_spec.md)
ARM_JOINT_LIMITS_RAD = (3.107, 2.269, 3.107, 2.356, 3.107, 2.234, 6.283)  # same datasheet, joint1..7
REJECTED = 20  # failure_kind: refused at the boundary (unknown capability / arguments off-contract)
JAW_JOINT = "eg2_joint1"
# the jaw bands come from the skills' own definition (openral_rskill._eye_in_hand): the boundary and the skills must
# read one gripper the same way, or an open jaw is a held item on one side of the call and not the other (run g4p)
from openral_rskill._eye_in_hand import JAW_EMPTY_MAX_RAD, JAW_OPEN_MIN_RAD  # noqa: E402
from openral_rskill.grasp_perception import GripperGeometry  # noqa: E402
#: how high above a support the tool works: the item is held by its handle, so the tool never goes to the shelf itself
ITEM_HANDLE_M = max(o["handle"]["xyz"][2] for o in IX["objects"].values() if o.get("handle"))


def horizontal(v) -> np.ndarray:
    v = np.array([v[0], v[1], 0.0])
    return v / np.linalg.norm(v)


def work_heights(feature: str) -> list[float]:
    """Where the tool itself has to be to do the work at a site point: at the point for a panel or a handle, and a
    handle's height above a support, because an item is carried by its handle and never set down by the tool's own
    tip."""
    pt = IX["points"][feature]
    return [float(pt["xyz"][2]) + (ITEM_HANDLE_M if pt["type"] == "place" else 0.0)]


def stand_at(p_map: np.ndarray, n_map: np.ndarray, d: float, standoff_m: float):
    xy = p_map[:2] + n_map[:2] * (d + standoff_m)
    return float(xy[0]), float(xy[1]), math.atan2(n_map[1], n_map[0])


def approach_rotations(elevations_deg=(0.0, -20.0, -40.0)) -> list[np.ndarray]:
    """Tool orientations a job at a site point could need, in the frame where the point lies on the rover's -x axis:
    coming at it level and from above, jaws across. Which one a grasp actually takes is measured from the part when
    the robot is there; this is only what the stand has to keep possible."""
    out = []
    for deg in elevations_deg:
        th = math.radians(deg)
        z = np.array([-math.cos(th), 0.0, math.sin(th)])
        x = np.array([0.0, 1.0, 0.0])
        out.append(np.stack([x, np.cross(z, x), z], axis=1))
    return out


def tool_rotation(n: np.ndarray, orientation: str) -> np.ndarray:
    """Tool +Z into the surface; jaw axis vertical ("press") or horizontal ("grip") -- d0_common / lunar_oracle."""
    z = np.array([-n[0], -n[1], 0.0])
    x = np.array([0.0, 0.0, 1.0]) if orientation == "press" else np.cross([0.0, 0.0, 1.0], z)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z, x), z], axis=1)


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


def quat_to_mat(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


#: the logistics record's item names (the equipment catalogue is keyed by them)
ITEM_NAMES = {"spare_oru": "spare ORU (orbital replacement unit, gold MLI-covered box)", "spare_crate": "cargo crate (white case)"}


def held_item(a: dict) -> dict:
    """The named catalogue item's envelope, for the skill to keep the carried item clear of the rover and supports."""
    if "item" not in a:
        return {}
    key = next(k for k, n in ITEM_NAMES.items() if a["item"] in (k, n))
    c = item_catalogue(IX["objects"][key])
    return {"held_item": {"size_m": c["size_m"], "handle_above_base_m": c["handle_height_above_base_m"],
                          "neck_height_m": c["grasp_interface"]["dimensions_m"]["neck_height"],
                          "closing_width_m": c["grasp_interface"]["closing_width_m"]}}


def lower(capability: str, a: dict) -> dict:
    """Contract arguments -> the rSkill's goal_params (the D0 checks' settings, F51)."""
    if capability == "navigate_to_pose":
        return {"pose": {"header": {"frame_id": "map"}, "pose": {
            "position": {"x": float(a["x"]), "y": float(a["y"]), "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": math.sin(a["yaw"] / 2), "w": math.cos(a["yaw"] / 2)}}}}
    if capability == "dock_to_pose":
        p = dict(frame_id="map", position=[float(a["x"]), float(a["y"])], yaw=float(a["yaw"]),
                 max_angular_speed_rad_s=0.45, stall_timeout_s=20.0, timeout_s=180.0)
        if "approach_m" in a:
            p["approach_m"] = float(a["approach_m"])
        return p
    if capability == "move_joints":
        return {"joint_targets": a["joint_targets"], "tolerance_rad": a.get("tolerance_rad", 0.05), "timeout_s": 30.0}
    if capability in ("arm_ready", "stow"):
        # a planned path, so the arm goes round what the cameras measured standing beside the rover (F57)
        return {"joint_targets": READY if capability == "arm_ready" else STOW,
                "tolerance_rad": a.get("tolerance_rad", 0.08)}
    if capability == "plan_ee_pose":
        return {"pose": {"frame_id": "chassis_base_link", "link_name": "tcp_frame", "position": a["position"],
                         "orientation": a["orientation_xyzw"], "quaternion_order": "xyzw",
                         "position_tolerance_m": a.get("tolerance_m", 0.01), "orientation_tolerance_rad": 0.05},
                # posture preference of this arm (shoulder on its working branch, wrist unspun) -- robot, not mission
                "joint_constraints": [{"joint": "joint1", "position": 0.0, "tolerance_above": 1.5, "tolerance_below": 1.5},
                                      {"joint": "joint7", "position": 0.0, "tolerance_above": 3.0, "tolerance_below": 3.0}],
                "request": {"group_name": "rm_group", "allowed_planning_time": 10.0, "num_planning_attempts": 10}}
    if capability == "move_ee_to_pose":
        p = dict(frame_id="chassis_base_link", position=a["position"], quaternion_xyzw=a["orientation_xyzw"],
                 pos_tolerance_m=a.get("tolerance_m", 0.015), timeout_s=a.get("timeout_s", 25.0))
        if "max_linear_speed_m_s" in a:
            p["max_linear_speed_m_s"] = a["max_linear_speed_m_s"]
        return p
    if capability == "grasp":
        return {"mode": "close", "timeout_s": 8.0}
    if capability == "release":
        return {"mode": "open", "timeout_s": 8.0}
    if capability == "pick":
        # Where the work is, when the caller names it: the same surveyed point `place` already gets. The skill has
        # to put its camera level with the part to measure what the jaws close on, and a pose written into its
        # manifest cannot do that -- it assumes a parking distance that this boundary, not the skill, decides, and
        # it would have to be rewritten for every item and every support (research F79).
        # Where the work is: the caller's own arithmetic over the catalogue and the site, because only the caller
        # knows which item this pick is for. The boundary's own work height is a maximum over every catalogued
        # handle -- right for deciding where a rover can park for any of them, wrong for aiming a camera at one.
        at = {}
        if "support" in a:
            at = {"support": a["support"], "support_xyz_map": IX["points"][a["support"]]["xyz"]}
            at["work_z_m"] = float(a["grasp_height_m"]) if "grasp_height_m" in a else work_heights(a["support"])[0]
        return {"target": a["target"], "part": a["part"], **held_item(a), **at}
    if capability == "place":
        # a named support is fixed infrastructure: its surveyed point and the direction it faces go to the skill,
        # which puts both in the rover frame. The normal is what tells a skill which way is *off* the support: a
        # shelf on a wall has the wall behind it, and an item whose envelope is nearly as deep as the shelf has to
        # sit forward of the surveyed centre or its back corner is inside the structure (ga5, F85).
        return {"support": a["support"], "support_xyz_map": IX["points"][a["support"]]["xyz"],
                "support_normal_map": IX["points"][a["support"]]["normal"], **held_item(a),
                **({"release_constraint": a["release_constraint"]} if "release_constraint" in a else {})}
    if capability == "press":
        # nothing to lower: the skill finds the target in its own camera, and where to stand off and how far to press
        # past the face are its own defaults
        return {"target": a["target"]}
    raise KeyError(capability)


def goal_summary(p: dict) -> dict:
    """The commanded target of a lowered effect, in the frame it was commanded (evidence for effect verification)."""
    if "pose" in p and "header" in p["pose"]:
        q = p["pose"]["pose"]["orientation"]
        return {"frame": "map", "x": p["pose"]["pose"]["position"]["x"], "y": p["pose"]["pose"]["position"]["y"],
                "yaw": round(2 * math.atan2(q["z"], q["w"]), 4)}
    if "yaw" in p:
        return {"frame": p["frame_id"], "x": p["position"][0], "y": p["position"][1], "yaw": p["yaw"]}
    if "pose" in p:
        return {"frame": p["pose"]["frame_id"], "position": [round(v, 4) for v in p["pose"]["position"]]}
    if "quaternion_xyzw" in p:
        return {"frame": p["frame_id"], "position": [round(v, 4) for v in p["position"]]}
    if "joint_targets" in p:
        return {"joint_targets": p["joint_targets"]}
    return {k: v for k, v in p.items() if k in ("mode", "target", "part", "support", "held_item", "work_z_m")}


class CapabilityServer(Node):
    def __init__(self):
        super().__init__("space_capability_server", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        cb = ReentrantCallbackGroup()
        self.buf = Buffer()
        TransformListener(self.buf, self)
        self.jaw, self.arm_q, self.sim_t, self.calls = None, None, 0.0, 0
        self.infos, self.depths = {}, {}
        self._space_context: dict = {}
        #: what the last pick that succeeded took, and from where. The boundary dispatched that call and saw it
        #: succeed, so this is its own record, not an observation and not simulator truth.
        self._picked: dict | None = None
        self.create_subscription(
            String, "/srb/env0/space_context", lambda m: self._space_context.update(json.loads(m.data)),
            QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL),
            callback_group=cb)
        self.create_subscription(JointState, "/srb/env0/robot/joint_states", self._on_joints, 10, callback_group=cb)
        self.create_subscription(Clock, "/clock", lambda m: setattr(self, "sim_t", m.clock.sec + m.clock.nanosec * 1e-9), 10, callback_group=cb)
        self.images = {}
        for cam in ("front", "wrist"):
            self.create_subscription(Image, f"/openral/cameras/{cam}/image", lambda m, cam=cam: self.images.__setitem__(cam, m),
                                     qos_profile_sensor_data, callback_group=cb)
            self.create_subscription(CameraInfo, f"/openral/cameras/{cam}/camera_info", lambda m, cam=cam: self.infos.__setitem__(cam, m),
                                     qos_profile_sensor_data, callback_group=cb)
            # both cameras are RealSense D435i: depth registered to the colour image, metres along the optical axis
            self.create_subscription(Image, f"/openral/cameras/{cam}_depth/image", lambda m, cam=cam: self.depths.__setitem__(cam, m),
                                     qos_profile_sensor_data, callback_group=cb)
        self._stands: dict[str, float] = {}  # where the rover parks for a feature, settled once with the arm's own IK
        self.evidence_dir = Path(os.environ.get("SPACE_EVIDENCE_DIR", os.environ.get("D0_LOG", "/tmp"))) / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        from rcl_interfaces.srv import SetParameters  # noqa: E402  (ROS message packages import at node construction)

        # reentrant like every other client here: this is called from inside an action's own execution, and a client
        # on the default group would wait on a future its own executor thread is blocked from completing
        self._smoother_params = self.create_client(SetParameters, "/velocity_smoother/set_parameters", callback_group=cb)
        self._drive_limits: dict | None = None  # what the smoother was last set to (see drive_limits)
        from openai import OpenAI
        self.vlm = OpenAI(api_key=os.environ["SPACE_LLM_API_KEY"], base_url=VLM_ENDPOINT, timeout=120)
        self.vlm_pool = ThreadPoolExecutor(8)
        self.rskill = ActionClient(self, ExecuteRskill, "/openral/execute_rskill", callback_group=cb)
        self.ik = self.create_client(GetPositionIK, "/compute_ik", callback_group=cb)
        ActionServer(self, ExecuteCapability, "/space/capability/execute", self._execute,
                     cancel_callback=lambda _: CancelResponse.ACCEPT, callback_group=cb)
        self.create_service(QueryCapability, "/space/capability/query", self._query, callback_group=cb)
        self.get_logger().info(f"capability boundary up: effects {sorted(CONTRACTS['effects'])}, queries {sorted(CONTRACTS['queries'])}")

    def _on_joints(self, m):
        if JAW_JOINT in m.name:
            self.jaw = float(m.position[m.name.index(JAW_JOINT)])
        if ARM_JOINTS[0] in m.name:
            self.arm_q = [float(m.position[m.name.index(j)]) for j in ARM_JOINTS]

    def arm_state(self):
        """Arm posture from the joint encoders: `stowed` / `ready` within 0.15 rad of those postures, else `other`."""
        q = np.array(self.arm_q)
        posture = next((name for name, ref in (("stowed", STOW), ("ready", READY)) if np.max(np.abs(q - ref)) < 0.15), "other")
        return {"posture": posture, "joints_rad": [round(v, 3) for v in self.arm_q], "jaw_rad": round(self.jaw, 3)}

    # ---- queries ------------------------------------------------------------------------------------------------
    def _tf(self, target, source):
        tr = self.buf.lookup_transform(target, source, Time()).transform
        return np.array([tr.translation.x, tr.translation.y, tr.translation.z]), quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w)

    def base_pose(self):
        p, R = self._tf("map", "chassis_base_link")
        return {"frame": "map", "x": round(float(p[0]), 4), "y": round(float(p[1]), 4), "yaw": round(math.atan2(R[1, 0], R[0, 0]), 4)}

    def manifest(self):
        """The logistics record as mission control holds it: the depot slots as staged, the items' catalogue data."""
        names = ITEM_NAMES
        slots = {IX["objects"][k]["support"].split("/")[1]: names[k] for k in names}
        items = {names[k]: item_catalogue(IX["objects"][k]) for k in names}
        return {"depot_stand": slots, "items": items}

    def site_map(self):
        fixed = {k: v for k, v in IX["points"].items() if "object" not in v}
        return {"frame": "map", "point_types": POINT_TYPES,
                "equipment_catalogue": self.manifest()["items"],
                "points": {k: {"type": v["type"], "equipment": v["asset"], "xyz": v["xyz"], "normal": [round(c, 3) for c in v["normal"]]}
                           for k, v in fixed.items()},
                "view_poses": {k: {"x": v["xy"][0], "y": v["xy"][1], "yaw": round(math.radians(v["yaw_deg"]), 4), "looks_at": v["target"]}
                               for k, v in IX["view_poses"].items()},
                # the graded network the site was built with: the rover drives along it. A goal set straight across the
                # site cuts the corners of what stands between (research repo F53), which the costmap only sees late.
                "roads": {k: [[p[0], p[1]] for p in v] for k, v in IX.get("roads", {}).items()},
                "dock": {"x": 0.0, "y": 0.0, "yaw": 0.0}}

    def frame(self, camera: str):
        """The latest image of a camera, saved as evidence, with the camera's pose in `odom` at its stamp."""
        m, info, dm = self.images[camera], self.infos[camera], self.depths[camera]
        depth = np.frombuffer(dm.data, np.float32).reshape(dm.height, dm.width)
        img = np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1)
        bgr = cv2.cvtColor(img, {"rgb8": cv2.COLOR_RGB2BGR, "rgba8": cv2.COLOR_RGBA2BGR, "bgra8": cv2.COLOR_BGRA2BGR}[m.encoding]) if m.encoding != "bgr8" else img
        stamp = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        # the frame can be a tick newer than the latest TF (ob6_s19c: 20 ms): wait for the pose at its stamp
        tr = self.buf.lookup_transform("odom", m.header.frame_id, Time.from_msg(m.header.stamp), timeout=Duration(seconds=1.0)).transform
        pose = (np.array([tr.translation.x, tr.translation.y, tr.translation.z]), quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w))
        # gravity-upright image for the VLM: "above"/"below" in a description then mean what they mean on the equipment,
        # whatever the wrist's roll (quarter turns; pixels are mapped back to the raw image)
        up = pose[1].T @ np.array([0.0, 0.0, 1.0])
        turn = {0: None, 1: cv2.ROTATE_90_COUNTERCLOCKWISE, 2: cv2.ROTATE_180, 3: cv2.ROTATE_90_CLOCKWISE}[
            round(math.atan2(up[0], -up[1]) / (math.pi / 2)) % 4]
        upright = bgr if turn is None else cv2.rotate(bgr, turn)
        path = self.evidence_dir / f"{camera}_{stamp:010.2f}.jpg"
        cv2.imwrite(str(path), upright)
        return dict(camera=camera, path=path, stamp=stamp, K=np.array(info.k).reshape(3, 3), w=m.width, h=m.height, pose_odom=pose,
                    turn=turn, uw=upright.shape[1], uh=upright.shape[0], depth=depth)

    def ask_vlm(self, path: Path, text: str) -> str:
        b64 = base64.b64encode(path.read_bytes()).decode()
        r = self.vlm.chat.completions.create(model=VLM_MODEL, messages=[{"role": "user", "content": [
            {"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}])
        return (r.choices[0].message.content or "").strip()

    def observe(self, camera: str, question: str):
        f = self.frame(camera)
        answer = self.ask_vlm(f["path"], f"{question}\nAnswer from this camera image only, briefly. If it cannot be seen clearly, say so.")
        return {"camera": camera, "answer": answer, "frame_stamp_s": round(f["stamp"], 2), "image": str(f["path"]), "model": VLM_MODEL}

    def drive_limits(self, carrying: bool) -> dict:
        """Set Nav2's velocity smoother to the carrying or the free limits, and say what was set.

        Read from the jaw alone -- the robot's own state, not any method's record of what it is doing -- so every
        method's base moves are ramped the same way."""
        from rcl_interfaces.msg import Parameter as ParamMsg, ParameterType, ParameterValue
        from rcl_interfaces.srv import SetParameters

        if carrying:
            p = self.tcp_pose()["position"]
            lever = max(math.hypot(p[0], p[1]), 0.2)  # how far out the load is riding, measured
            budget = carry_budget(self.space_context()["gravity_m_s2"])
            linear = round(budget / 2, 3)  # the straight line and the turn each get half of what reaches the load
            az = round(linear / lever, 2)
            # A sustained turn is not a step: it holds w^2 * r on the load for as long as it lasts, and 1 rad/s on
            # the 0.787 m lever g9x carried at is 0.79 m/s^2, a 26 deg lean all by itself -- past the angle the bag
            # says this grasp starts opening at. The turn rate comes out of the same budget as the accelerations,
            # and out of the *half* of it the turn gets, not the whole -- the line above says each gets half and
            # this did not. Then it is held down to what a grasp survives while the load slips rather than swings.
            wz = round(min(math.sqrt(linear / lever), CARRY_SUSTAINED_YAW_RAD_S), 2)
            want = {"max_velocity": [CARRY_MAX_SPEED[0], 0.0, wz], "max_accel": [linear, 0.0, az],
                    "max_decel": [-linear, 0.0, -az], "lever_m": round(lever, 3),
                    "gravity_m_s2": round(self.space_context()["gravity_m_s2"], 4)}
        else:
            want = {"max_velocity": FREE_MAX_VELOCITY, "max_accel": FREE_MAX_ACCEL, "max_decel": FREE_MAX_DECEL}
        if want == self._drive_limits:
            return {"carrying": carrying, "changed": False}
        cli = self._smoother_params
        if not cli.wait_for_service(timeout_sec=2.0):
            return {"carrying": carrying, "changed": False, "why": "the velocity smoother is not accepting parameters"}
        req = SetParameters.Request(parameters=[
            ParamMsg(name=n, value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE_ARRAY, double_array_value=v))
            for n, v in want.items() if n not in ("lever_m", "gravity_m_s2")])  # evidence, not smoother parameters
        fut = cli.call_async(req)
        t0 = time.time()
        while not fut.done() and time.time() - t0 < 3.0:
            time.sleep(0.02)
        if not fut.done():
            return {"carrying": carrying, "changed": False, "why": "the velocity smoother did not answer"}
        self._drive_limits = want
        self.get_logger().info(f"drive limits: {'carrying' if carrying else 'free'} {want['max_velocity'][0]} m/s, "
                               f"{want['max_accel'][0]} m/s^2")
        return {"carrying": carrying, "changed": True, **want}

    def held_item(self) -> dict:
        """What the gripper has between its fingers, from its own camera, with the jaw angle beside it.

        The jaw angle measures how far apart the fingers are, not whether anything is between them: closed on nothing
        reads 0.10 rad and closed on a thin edge 0.17, and an item that has slipped out leaves the jaws exactly where
        the grasp left them. The picture settles it. Nothing is said to the model about what is expected to be there:
        an answer shaped by the question is not evidence (research repo F57, F58), and the comparison with what the
        record says is carried belongs to whoever asked, not to the model.

        That record is returned beside the observation, because withholding it left the caller with only a camera
        that cannot answer: held by a handle, the item's body hangs below the wrist camera's frame and what fills
        it is the handle head. The two are labelled separately and are not reconciled here.
        """
        f = self.frame("wrist")
        reply = self.ask_vlm(f["path"], HELD_PROMPT)
        found = re.search(r"\{.*\}", reply, re.S)
        if not found:
            raise ValueError(f"the model did not answer with JSON: {reply[:200]!r}")
        j = json.loads(found.group(0))
        return {"observed": {"holding": bool(j.get("holding")), "what": str(j.get("what") or ""),
                             "frame_stamp_s": round(f["stamp"], 2), "image": str(f["path"]), "model": VLM_MODEL},
                "record": self._picked or "no pick has succeeded since the last place or release",
                "jaw_rad": round(self.jaw, 3)}

    def detect(self, camera: str, target: str) -> dict:
        """Where a target described in words is in the current image of a camera: pixel, and its 3-D point in `odom` from the
        registered depth."""
        f = self.frame(camera)
        # A single VLM answer is not stable: the same frame gave the button once and a rail point below it the next time,
        # and pointing at an elongated part wanders along it by tens of pixels (research repo F53). Ask several times
        # concurrently and take the per-axis median of the answers that found the target.
        prompt = LOCATE_PROMPT.format(target=target, w=f["uw"], h=f["uh"])
        centres, boxes, errors = [], [], []

        def ask(_):  # the gateway times out now and then (ob6_s15d): an unanswered ask is not an answer
            try:
                return self.ask_vlm(f["path"], prompt)
            except Exception as exc:  # reason: any transport/API error of the external model service
                errors.append(f"{type(exc).__name__}: {exc}")
                return ""

        for reply in self.vlm_pool.map(ask, range(VLM_LOCATE_ASKS)):
            found = re.search(r"\{.*\}", reply, re.S)
            j = json.loads(found.group(0)) if found else {"found": False}
            if j.get("found"):
                box = j.get("box")
                centres.append(j["center"] if not (box and len(box) == 4) else [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
                boxes.append(box)
        out = dict(camera=camera, image=str(f["path"]), frame_stamp_s=round(f["stamp"], 2), found=len(centres) >= VLM_LOCATE_MIN_FOUND,
                   vlm_found=f"{len(centres)}/{VLM_LOCATE_ASKS}")
        if len(errors) == VLM_LOCATE_ASKS:
            out["why"] = f"the vision-language model did not answer ({errors[0][:120]})"
        if out["found"]:
            c = np.array(centres, float)
            med = np.median(c, axis=0)
            out["pixel_spread"] = [round(float(v), 1) for v in np.median(np.abs(c - med), axis=0)]
            j = {"box": boxes[int(np.argmin(np.linalg.norm(c - med, axis=1)))]}
            x, y = med  # upright image -> raw image pixel
            w, h = f["w"], f["h"]
            u, v = {None: (x, y), cv2.ROTATE_90_COUNTERCLOCKWISE: (w - 1 - y, x), cv2.ROTATE_180: (w - 1 - x, h - 1 - y),
                    cv2.ROTATE_90_CLOCKWISE: (y, h - 1 - x)}[f["turn"]]
            ui, vi, k = int(round(u)), int(round(v)), DEPTH_WINDOW_PX
            patch = f["depth"][max(vi - k, 0):vi + k + 1, max(ui - k, 0):ui + k + 1]
            patch = patch[np.isfinite(patch) & (patch > 0)]
            t, R = f["pose_odom"]
            out.update(pixel=[ui, vi], box=j.get("box"), origin=t)
            if patch.size:
                z = float(np.percentile(patch, 25))  # the target is the foreground at its pixel, not what is behind a thin part
                p_cam = np.linalg.inv(f["K"]) @ np.array([u, v, 1.0]) * z
                out.update(depth_m=round(z, 4), point=R @ p_cam + t)
            else:
                out["found"], out["why"] = False, "no valid depth at the located pixel"
        return out

    def locate_in_view(self, camera: str, target: str):
        d = self.detect(camera, target)
        out = {k: d[k] for k in ("camera", "found", "image", "frame_stamp_s", "why") if k in d}
        if d["found"]:
            t, R = self._tf("chassis_base_link", "odom")
            out.update(pixel=d["pixel"], box=d["box"], depth_m=d["depth_m"], frame="chassis_base_link",
                       position=[round(float(v), 4) for v in R @ d["point"] + t])
        return out

    def tcp_pose(self):
        p, R = self._tf("chassis_base_link", "tcp_frame")
        return {"frame": "chassis_base_link", "position": [round(float(v), 4) for v in p]}

    def feature_geometry(self, name: str):
        """A surveyed site interaction point in `map` (placed by the rover's localization) and its horizontal outward normal."""
        pt = IX["points"][name]
        return np.array(pt["xyz"], float), horizontal(pt["normal"])

    def to_rover(self, p_map, n_map):
        t, R = self._tf("chassis_base_link", "map")
        return R @ p_map + t, R @ n_map

    def locate_feature(self, name):
        p, n = self.to_rover(*self.feature_geometry(name))
        return {"frame": "chassis_base_link", "position": [round(float(v), 4) for v in p], "normal": [round(float(v), 4) for v in n],
                "source": "site survey placed by the rover's localization (expect several cm of error)"}

    def space_context(self):
        """The body this robot is standing on and what it does to physics, as the environment publishes it.

        Gravity is not a property of the software. A load hanging from the jaws leans atan(a/g) off vertical under a
        base acceleration `a`, so the same driving that is gentle on Earth is six times the lean on the Moon and
        twice it again on an asteroid; and what a grasp can hold through is a property of the grasp, which the
        equipment catalogue describes. Both are facts here, for any method to use; none of them is a rule."""
        if not self._space_context:
            return {"body": "unknown", "gravity_m_s2": UNKNOWN_BODY_G_M_S2,
                    "note": "the environment published no space context, so the least gravity in the table is "
                            "assumed: what a hanging load takes scales with gravity, and not knowing where you "
                            "are must buy the gentlest driving, not the fastest"}
        return dict(self._space_context)

    def work_stands(self, feature: str, grasp_height_m: float | None = None):
        """Where the rover can stand to work at a site point, and how squarely the arm can look at it from each.

        The arm's own answer, not a table. For every distance the reach model offers, this reports whether the tool
        can be at the work, and the shallowest angle above horizontal from which the wrist camera can look at it --
        the camera rides behind the tool, so looking at all means standing the tool off by that much and more.

        The angle matters because an upright graspable feature is measured across: a handle neck with a head
        overhanging it reads as its own width only from the side, and from above the head hides it (research F60).
        Which parts need that is in the equipment catalogue's grasp interface, and choosing the stand is the
        caller's: `dock_at_feature` adds its `standoff_m` to the nearest distance reported here.
        """
        p, n_out = self.feature_geometry(feature)
        z = float(grasp_height_m) if grasp_height_m is not None else work_heights(feature)[0]
        near = clear_distance(p[:2], n_out[:2])
        # The stand-off the skill will actually use, from the one place it is written: the depth this wrist measures
        # a part at, less the distance the camera rides behind the tool. Asking the question at any other distance
        # would answer about a look nobody takes.
        behind = float(np.linalg.norm(self._tf("tcp_frame", "wrist_camera_optical_frame")[0]))
        back = float(PICK_GOAL["view_part_depth_m"][0]) - behind
        out, base = [], None
        # Where the tool has to *end up*, not where the part is. The close-in drives the contact to the middle of
        # the pads, so the tool finishes that much further out than the work point, and a stand that reaches the
        # point can still be short of the grasp: gb2 docked where this query said the work was reached and the
        # approach stalled 2.6 cm out (F88). The depth is the gripper's own, from the same place the skill takes
        # it, the way `view_part_depth_m` is already shared.
        seat = float(GripperGeometry().seat_depth_m)
        for d, _room in reach_map().stand_candidates([z], near)[:12]:
            at = np.array([-d, 0.0, z])
            grasp_at = np.array([-(d + seat), 0.0, z])
            reaches = any(self.ik_reaches(grasp_at, R) for R in approach_rotations())
            shallowest = None
            for deg in (0.0, 10.0, 20.0, 30.0, 40.0):
                R = approach_rotations((-deg,))[0]
                if self.ik_reaches(at - R[:, 2] * back, R):
                    shallowest = deg
                    break
            base = d if base is None else min(base, d)
            out.append({"distance_m": round(d, 3), "reaches_the_work": reaches,
                        "reach_is_checked_at_m": round(d + seat, 3),
                        "shallowest_look_deg_above_horizontal": shallowest,
                        "level_look": shallowest == 0.0})
        out.sort(key=lambda r: r["distance_m"])
        try:  # what standoff_m counts from; "none" is the answer this query exists to be able to give
            chosen = round(self.stand_distance(feature), 3)
        except self.NoStand:
            chosen = None
        for row in out:  # the number to pass, not a subtraction to do: asked to work it out, the model stood
            row["standoff_m"] = None if chosen is None else round(row["distance_m"] - chosen, 3)  # at 1.92 m
        return {"feature": feature, "work_height_m": round(z, 4), "camera_behind_tool_m": round(behind, 4),
                "nearest_stand_m": round(base, 3) if base is not None else None,
                "standoff_m_the_boundary_would_choose_on_its_own": chosen,
                "stands": out,
                "note": "a part whose head overhangs the neck the jaws close on can only be measured from a level "
                        "look; from above the head hides it"}

    def feature_target(self, a: dict) -> dict:
        """TCP target for a feature capability, in the rover frame, from the surveyed feature and the rover's localization."""
        p, n = self.to_rover(*self.feature_geometry(a["feature"]))
        p = p + n * a["offset_m"] + np.array([0.0, 0.0, a.get("lift_m", 0.0)])
        return {"position": p.tolist(), "orientation_xyzw": mat_to_quat(tool_rotation(n, a.get("orientation", "press")))}

    def move_tool_target(self, a: dict) -> dict:
        """A straight-line TCP displacement: `forward_m` along the tool axis, `up_m` vertical, `left_m` horizontal across."""
        p, R = self._tf("chassis_base_link", "tcp_frame")
        fwd = R[:, 2]
        left = np.cross([0.0, 0.0, 1.0], fwd)
        left = left / np.linalg.norm(left) if np.linalg.norm(left) > 1e-6 else R[:, 0]
        goal = p + fwd * a.get("forward_m", 0.0) + np.array([0.0, 0.0, a.get("up_m", 0.0)]) + left * a.get("left_m", 0.0)
        return {"position": goal.tolist(), "orientation_xyzw": mat_to_quat(R)}

    def lower_effect(self, capability: str, a: dict) -> dict:
        if capability == "move_base_delta":
            # the rover's own frame -> the map pose the base skill drives to, through the rover's localization
            b = self.base_pose()
            c, s = math.cos(b["yaw"]), math.sin(b["yaw"])
            dx, dy = float(a.get("dx_m", 0.0)), float(a.get("dy_m", 0.0))
            return lower("dock_to_pose", dict(x=b["x"] + c * dx - s * dy, y=b["y"] + s * dx + c * dy,
                                              yaw=b["yaw"] + float(a.get("dyaw_rad", 0.0)), approach_m=0.0))
        if capability in ("navigate_to_feature", "dock_at_feature"):
            p, n = self.feature_geometry(a["feature"])
            x, y, yaw = stand_at(p, n, self.stand_distance(a["feature"]),
                                 a.get("standoff_m", 1.5 if capability == "navigate_to_feature" else 0.0))
            if capability == "navigate_to_feature":
                return lower("navigate_to_pose", dict(x=x, y=y, yaw=yaw))
            return lower("dock_to_pose", dict(x=x, y=y, yaw=yaw, **({"approach_m": a["approach_m"]} if "approach_m" in a else {})))
        if capability == "plan_ee_to_feature":
            return lower("plan_ee_pose", {**self.feature_target(a), **({"tolerance_m": a["tolerance_m"]} if "tolerance_m" in a else {})})
        if capability == "move_ee_to_feature":
            extra = {k: a[k] for k in ("tolerance_m", "max_linear_speed_m_s", "timeout_s") if k in a}
            return lower("move_ee_to_pose", {**self.feature_target(a), **extra})
        if capability == "move_tool":
            extra = {k: a[k] for k in ("tolerance_m", "max_linear_speed_m_s", "timeout_s") if k in a}
            return lower("move_ee_to_pose", {**self.move_tool_target(a), **extra})
        return lower(capability, a)

    # ---- the camera-in-the-loop controller ------------------------------------------------------------------------
    def approach_target(self, a: dict, handle) -> tuple[bool, str, dict]:
        """Bring the tool to `standoff_m` in front of a target described in words, facing it, from the wrist camera (RGB-D)."""
        target, standoff, orientation = a["target"], a.get("standoff_m", 0.10), a.get("orientation", "press")
        ev = {"target": target, "views": []}

        def view(tag):
            d = self.detect("wrist", target)
            ev["views"].append({"at": tag, "found": d["found"], "pixel": d.get("pixel"), "depth_m": d.get("depth_m"), "image": d["image"]})
            return d

        d0 = view("start")
        if not d0["found"]:
            return False, f"target not found in the wrist camera (RGB-D): {target!r} {d0.get('why', '')}".strip(), ev
        X = d0["point"]
        n_odom = horizontal(d0["origin"] - X)  # approach from the camera's side, horizontally
        t_ro, R_ro = self._tf("chassis_base_link", "odom")

        def servo(Xo, tag):
            p, n = R_ro @ Xo + t_ro, R_ro @ n_odom
            goal = {"position": (p + n * standoff).tolist(), "orientation_xyzw": mat_to_quat(tool_rotation(n, orientation))}
            ok, why = self.run_rskill(handle, "move_ee_to_pose", {**goal, "tolerance_m": 0.008, "max_linear_speed_m_s": 0.06, "timeout_s": 30.0})
            ev["views"].append({"at": tag, "servo_ok": ok, "goal_rover": [round(v, 4) for v in goal["position"]]})
            return ok, why

        ok, why = servo(X, "stand-off")
        if not ok:
            return False, f"servo to the stand-off failed: {why}", ev
        d1 = view("stand-off")  # closer, the target is seen larger and its depth better: correct once
        if d1["found"]:
            ev["correction_m"] = round(float(np.linalg.norm(d1["point"] - X)), 4)
            if ev["correction_m"] > 0.004:
                X = d1["point"]
                ok, why = servo(X, "corrected stand-off")
                if not ok:
                    return False, f"corrective servo failed: {why}", ev
        ev["target_rover"] = [round(float(v), 4) for v in R_ro @ X + t_ro]
        return True, "", ev

    class NoStand(Exception):
        """There is no place to park where the rover is clear of the site and the arm reaches the work."""

    def ik_reaches(self, p_base: np.ndarray, R: np.ndarray) -> bool:
        """Whether some arm configuration puts the tool at this pose in the rover's own frame. Kinematics only: what
        stands in the way when the robot is actually there is the planner's business, and the rover is not there yet."""
        req = GetPositionIK.Request()
        req.ik_request.group_name, req.ik_request.ik_link_name, req.ik_request.avoid_collisions = "rm_group", "tcp_frame", False
        req.ik_request.pose_stamped.header.frame_id = "chassis_base_link"
        pp = req.ik_request.pose_stamped.pose
        pp.position.x, pp.position.y, pp.position.z = (float(v) for v in p_base)
        q = mat_to_quat(R)
        pp.orientation.x, pp.orientation.y, pp.orientation.z, pp.orientation.w = q
        req.ik_request.timeout.nanosec = 100_000_000
        f = self.ik.call_async(req)
        t0 = time.time()
        while not f.done():
            if time.time() - t0 > 5.0:
                return False
            time.sleep(0.02)
        return f.result() is not None and f.result().error_code.val == 1

    def arm_reaches(self, d: float, heights: list[float]) -> bool:
        """Standing `d` from a site point, can the arm put its tool where the work is?"""
        return all(any(self.ik_reaches(np.array([-d, 0.0, z]), R) for R in approach_rotations()) for z in heights)

    def stand_distance(self, feature: str) -> float:
        """How far from a site point this rover parks to work there.

        The arm decides, not a table: the reach model proposes the stand-offs where its tool can be at the work
        heights, the footprint rules out the ones where the rover would be in the furniture, and the robot's own IK
        settles each candidate -- including one docking error nearer and further, because that is how accurately a dock
        lands. The first that survives all three is the stand. When none does, the robot cannot do that job from any
        parking place, which is a fact the caller needs before driving there (research repo F58)."""
        if feature in self._stands:
            return self._stands[feature]
        p, n = self.feature_geometry(feature)
        heights = work_heights(feature)
        near = clear_distance(p[:2], n[:2])
        cands = reach_map().stand_candidates(heights, near)
        for d, _room in cands[:8]:
            if all(self.arm_reaches(d + e, heights) for e in (0.0, -DOCK_ERROR_M, DOCK_ERROR_M)):
                self.get_logger().info(f"stand at {feature}: {d:.3f} m from the point (hull clear from {near:.3f} m, "
                                       f"work at z {[round(z, 3) for z in heights]})")
                self._stands[feature] = d
                return d
        raise self.NoStand(
            f"the rover cannot park anywhere that lets the arm work at {feature}: its hull clears the site's "
            f"structures no closer than {near:.2f} m from the point, and from there the arm cannot put its tool at "
            f"the working height ({', '.join(f'{z:.2f} m' for z in heights)})")

    def explain_arm_goal(self, params: dict) -> str:
        """Why an arm goal may have failed, from the robot model: the goal's distance from the arm mount, whether a
        collision-free arm configuration puts the TCP there (MoveIt IK against the current planning scene), and which
        joints are at their stops now."""
        pose = params["pose"] if "pose" in params else {"position": params["position"], "orientation": params["quaternion_xyzw"]}
        mount, _ = self._tf("chassis_base_link", "base_link")
        out = f"TCP goal {np.linalg.norm(np.array(pose['position']) - mount):.2f} m from the arm mount, working radius {ARM_WORKING_RADIUS_M} m"
        req = GetPositionIK.Request()
        req.ik_request.group_name, req.ik_request.ik_link_name, req.ik_request.avoid_collisions = "rm_group", "tcp_frame", True
        req.ik_request.pose_stamped.header.frame_id = "chassis_base_link"
        pp = req.ik_request.pose_stamped.pose
        pp.position.x, pp.position.y, pp.position.z = (float(v) for v in pose["position"])
        pp.orientation.x, pp.orientation.y, pp.orientation.z, pp.orientation.w = (float(v) for v in pose["orientation"])
        req.ik_request.timeout.sec = 1
        f = self.ik.call_async(req)
        while not f.done():
            time.sleep(0.05)
        out += ("; a collision-free arm configuration reaches that TCP pose" if f.result().error_code.val == 1
                else "; no collision-free arm configuration reaches that TCP pose with that tool orientation")
        at_stop = [f"joint{i + 1} {v:+.2f} rad (limit +-{lim})" for i, (v, lim) in enumerate(zip(self.arm_state()["joints_rad"], ARM_JOINT_LIMITS_RAD))
                   if abs(v) > lim - 0.08]
        return out + ("; now at a joint stop: " + ", ".join(at_stop) if at_stop else "")

    def run_rskill(self, handle, capability: str, a: dict, deadline: float = 60.0) -> tuple[bool, str]:
        r = self.dispatch(handle, CONTRACTS["effects"]["move_ee_to_pose"]["lowers_to"], lower(capability, a), deadline)
        return bool(r.success), r.failure_reason

    def _query(self, req, res):
        try:
            args = json.loads(req.args_json or "{}")
            if req.query not in CONTRACTS["queries"]:
                raise KeyError(f"unknown query {req.query!r}")
            reason = check_args(CONTRACTS["queries"][req.query], args)
            if reason:
                raise ValueError(reason)
            value = {"observe": lambda: self.observe(args["camera"], args["question"]),
                     "locate_in_view": lambda: self.locate_in_view(args["camera"], args["target"]), "site_map": self.site_map,
                     "manifest": self.manifest, "arm_state": self.arm_state, "base_pose": self.base_pose, "tcp_pose": self.tcp_pose, "jaw": lambda: {"rad": self.jaw},
                     "held_item": self.held_item,
                     "space_context": self.space_context,
                     "work_stands": lambda: self.work_stands(args["feature"], args.get("grasp_height_m")),
                     "locate_feature": lambda: self.locate_feature(args["name"])}[req.query]()
            res.success, res.value_json = True, json.dumps(value)
        except Exception as exc:  # reason: every failure is a typed answer to the caller, not a dead service
            res.success, res.failure_reason = False, f"{type(exc).__name__}: {exc}"
        return res

    # ---- effects ------------------------------------------------------------------------------------------------
    def _execute(self, handle):
        g, res = handle.request, ExecuteCapability.Result()
        contract = CONTRACTS["effects"].get(g.capability)
        try:
            args = json.loads(g.args_json or "{}")
        except json.JSONDecodeError as exc:
            args, contract_reason = {}, f"args_json is not JSON: {exc}"
        else:
            if isinstance(args, list) and contract is not None:
                # positional form (typed PLEXIL Commands): values in the contract's declared input order
                keys = list(contract.get("inputs") or {})
                args = dict(zip(keys, args)) if len(args) <= len(keys) else {"_too_many_arguments": args}
            contract_reason = "" if contract is None else check_args(contract, args)
        if contract is None or contract_reason:
            handle.succeed()
            res.success, res.failure_kind = False, REJECTED
            res.failure_reason = contract_reason or f"unknown capability {g.capability!r} (effects: {sorted(CONTRACTS['effects'])})"
            return res
        # folding the arm with something in the jaws puts the item through the rover: a hardware limit, shared by every
        # method, so it is refused here and not in any one method's guard
        # how hard the base may be driven is decided by what the jaws hold, for every method and every base move
        drive = self.drive_limits(JAW_EMPTY_MAX_RAD < self.jaw < JAW_OPEN_MIN_RAD) if g.capability in BASE_MOVES else None
        if g.capability in ("stow", "arm_ready") and JAW_EMPTY_MAX_RAD < self.jaw < JAW_OPEN_MIN_RAD:
            handle.succeed()
            res.success, res.failure_kind = False, REJECTED
            res.failure_reason = (f"the jaws are holding something (jaw {self.jaw:.3f} rad): {g.capability} takes the arm "
                                  "to a fixed posture in one joint-space move, which swings a hanging load through "
                                  "whatever is between here and there without looking. Put the item down first, or "
                                  "drive with the arm as the pick left it.")
            return res
        deadline = g.deadline_s or float(contract["default_deadline_s"])
        sim0 = self.sim_t
        if g.capability == "approach_target":
            ok, reason, evidence = self.approach_target(args, handle)
            r = ExecuteRskill.Result(success=ok, failure_kind=0 if ok else 3, failure_reason=reason)
        else:
            try:
                params = self.lower_effect(g.capability, args)
            except self.NoStand as exc:
                handle.succeed()
                res.success, res.failure_kind, res.failure_reason = False, 3, str(exc)
                return res
            # the skills that keep a record of what they saw are handed the run's evidence directory: where a skill
            # writes belongs to the harness, not to the skill. Which ones those are is in the contract, because a goal
            # param an rSkill does not declare is an error, not a spare field (a nav2 action goal has no such field)
            if contract.get("records_evidence"):
                params["evidence_dir"] = str(self.evidence_dir)
            r = self.dispatch(handle, contract["lowers_to"], params, deadline)
            evidence = {"rskill": contract["lowers_to"], "goal": goal_summary(params)}
            if r.evidence_json and r.evidence_json != "{}":
                evidence["skill"] = json.loads(r.evidence_json)  # the skill's own record: raw evidence, not a verdict
            if not r.success and "position" in evidence["goal"]:  # a planner error code does not say what was wrong (ob5, ob6)
                r.failure_reason += " (" + self.explain_arm_goal(params) + ")"
        # What the robot is carrying is something the boundary knows and the wrist camera cannot see: at the carry
        # pose that camera looks straight at the handle head the jaws are clamped to, and the item's body hangs
        # below, out of frame. In ga4 the model carried the ORU the whole way, asked what was in the jaws, was told
        # (accurately) "a smooth light-grey case, no lifting eye, no gold foil" -- the handle head -- concluded it
        # had the wrong payload and drove back to put it down. The record of the call it made itself settles it.
        if r.success and g.capability == "pick":
            self._picked = {"item": args.get("item") or args.get("target"), "from_support": args.get("support"),
                            "jaw_rad_at_pick": None if self.jaw is None else round(self.jaw, 3),
                            "picked_at_sim_s": round(self.sim_t, 2)}
        elif r.success and g.capability in ("place", "release"):
            self._picked = None
        evidence["sim_s"] = round(self.sim_t - sim0, 2)
        for key, fn in (("base_pose", self.base_pose), ("tcp_pose", self.tcp_pose)):
            try:
                evidence[key] = fn()
            except Exception as exc:  # reason: evidence is best-effort; a missing TF must not hide the skill result
                evidence[key] = f"unavailable: {exc}"
        evidence["arm"] = self.arm_state()
        if drive is not None:
            evidence["drive_limits"] = drive
        if handle.is_cancel_requested:
            handle.canceled()
        elif r.success:
            handle.succeed()
        else:
            handle.abort()
        res.success, res.failure_kind, res.failure_reason = bool(r.success), int(r.failure_kind), r.failure_reason
        res.evidence_json = json.dumps(evidence)
        # the call trace (§4.6): one line per effect, whoever called it
        self.get_logger().info("CAPABILITY " + json.dumps(dict(capability=g.capability, args=args, success=res.success,
                                                               failure_kind=res.failure_kind, failure_reason=res.failure_reason,
                                                               evidence=evidence)))
        return res

    def dispatch(self, handle, rskill_id: str, params: dict, deadline: float):
        """One ExecuteRskill goal through the OpenRAL runner, waited for; feedback keeps the caller informed."""
        # a distinct prompt per call: the runner reuses a resident skill for a byte-identical request, which would replay a
        # finished goal's state (a repeated identical call must run again)
        self.calls += 1
        goal = ExecuteRskill.Goal(rskill_id=rskill_id, prompt=f"capability boundary call {self.calls}", goal_params_json=json.dumps(params), deadline_s=deadline)
        sim0 = self.sim_t
        handle.publish_feedback(ExecuteCapability.Feedback(state="dispatched", elapsed_s=0.0))
        def feedback(msg):
            fb = msg.feedback
            handle.publish_feedback(ExecuteCapability.Feedback(
                state=fb.state, elapsed_s=float(self.sim_t - sim0), evidence_json=fb.evidence_json))

        sent = self.rskill.send_goal_async(goal, feedback_callback=feedback)
        while not sent.done():
            time.sleep(0.05)
        gh = sent.result()
        if gh is None or not gh.accepted:
            return ExecuteRskill.Result(success=False, failure_kind=255, failure_reason="rskill runner rejected the goal")
        rf = gh.get_result_async()
        cancel_sent = False
        while not rf.done():
            if handle.is_cancel_requested and not cancel_sent:
                gh.cancel_goal_async()
                cancel_sent = True
            time.sleep(0.1)
        return rf.result().result


def main():
    rclpy.init()
    node = CapabilityServer()
    ex = MultiThreadedExecutor(num_threads=8)
    ex.add_node(node)
    t = threading.Thread(target=ex.spin, daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(1.0)
    except KeyboardInterrupt:
        pass
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
