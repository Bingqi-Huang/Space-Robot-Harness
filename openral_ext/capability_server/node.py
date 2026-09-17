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
import re
import math
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from openral_msgs.action import ExecuteRskill
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.time import Time
from rosgraph_msgs.msg import Clock
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, JointState
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability
from tf2_ros import Buffer, TransformListener

from contracts import CONTRACTS, IX, check_args
READY = [0.0, -1.0, 0.0, -1.4, 0.0, 1.2, 0.0]  # the arm's ready posture (robot, not mission)
STOW = [0.0, -0.6, 0.0, 1.2, 0.0, 0.6, 0.0]  # rskill-procedural-stow's travel pose
ARM_JOINTS = [f"joint{i}" for i in range(1, 8)]
# what each interaction-point type is, as the site's equipment documentation states it
POINT_TYPES = {
    "press": "push button on a service panel; actuates when the tool tip is pushed about 1 cm past its face (jaws closed)",
    "indicator": "status lamp on a service panel: red = unit faulted, green = nominal",
    "place": "surface point where an object can be set down",
}
VLM_MODEL = os.environ.get("SPACE_VLM_MODEL", "DeepSeek-V4.1-Flash")  # the shared scene VLM (same for every method)
VLM_ENDPOINT = os.environ.get("SPACE_VLM_ENDPOINT", "https://llmapi.paratera.com/v1")
LOCATE_PROMPT = ('Locate {target} in this {w}x{h} camera image. Reply with JSON only: {{"found": true or false, "center": [x, y], '
                 '"box": [x1, y1, x2, y2]}} in pixel coordinates, origin at the top-left. found=false if it is not clearly visible.')
VLM_LOCATE_ASKS, VLM_AGREE_PX = 3, 15  # localisation answers must agree within this many pixels
DEPTH_WINDOW_PX = 3  # half-width of the depth patch around the located pixel (median of the valid depths)
REJECTED = 20  # failure_kind: refused at the boundary (unknown capability / arguments off-contract)
JAW_JOINT = "eg2_joint1"
HULL_M, REACH_M = IX["robot"]["hull_x_back_m"], IX["robot"]["reach_m"]["press"]  # arm reach past the hull (C3)


def horizontal(v) -> np.ndarray:
    v = np.array([v[0], v[1], 0.0])
    return v / np.linalg.norm(v)


def work_pose_from(p_map: np.ndarray, n_map: np.ndarray, standoff_m: float):
    """Base pose from which the arm reaches a point: hull + reach out along its normal, heading along it; `standoff_m`
    further out on the same axis (the docking corridor's entry)."""
    xy = p_map[:2] + n_map[:2] * (HULL_M + REACH_M + standoff_m)
    return float(xy[0]), float(xy[1]), math.atan2(n_map[1], n_map[0])


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
    if capability == "arm_ready":
        return lower("move_joints", dict(joint_targets=READY, tolerance_rad=a.get("tolerance_rad", 0.05)))
    if capability == "stow":
        return {"tolerance_rad": a.get("tolerance_rad", 0.1), "timeout_s": 30.0}
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
    return {k: v for k, v in p.items() if k in ("mode",)}


class CapabilityServer(Node):
    def __init__(self):
        super().__init__("space_capability_server", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        cb = ReentrantCallbackGroup()
        self.buf = Buffer()
        TransformListener(self.buf, self)
        self.jaw, self.arm_q, self.sim_t = None, None, 0.0
        self.infos, self.depths = {}, {}
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
        self.evidence_dir = Path(os.environ.get("SPACE_EVIDENCE_DIR", os.environ.get("D0_LOG", "/tmp"))) / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        from openai import OpenAI
        self.vlm = OpenAI(api_key=os.environ["SPACE_LLM_API_KEY"], base_url=VLM_ENDPOINT, timeout=120)
        self.rskill = ActionClient(self, ExecuteRskill, "/openral/execute_rskill", callback_group=cb)
        ActionServer(self, ExecuteCapability, "/space/capability/execute", self._execute, callback_group=cb)
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

    def site_map(self):
        fixed = {k: v for k, v in IX["points"].items() if "object" not in v}
        return {"frame": "map", "point_types": POINT_TYPES,
                "points": {k: {"type": v["type"], "equipment": v["asset"], "xyz": v["xyz"], "normal": [round(c, 3) for c in v["normal"]]}
                           for k, v in fixed.items()},
                "view_poses": {k: {"x": v["xy"][0], "y": v["xy"][1], "yaw": round(math.radians(v["yaw_deg"]), 4), "looks_at": v["target"]}
                               for k, v in IX["view_poses"].items()},
                "dock": {"x": 0.0, "y": 0.0, "yaw": 0.0}}

    def frame(self, camera: str):
        """The latest image of a camera, saved as evidence, with the camera's pose in `odom` at its stamp."""
        m, info, dm = self.images[camera], self.infos[camera], self.depths[camera]
        depth = np.frombuffer(dm.data, np.float32).reshape(dm.height, dm.width)
        img = np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1)
        bgr = cv2.cvtColor(img, {"rgb8": cv2.COLOR_RGB2BGR, "rgba8": cv2.COLOR_RGBA2BGR, "bgra8": cv2.COLOR_BGRA2BGR}[m.encoding]) if m.encoding != "bgr8" else img
        stamp = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        tr = self.buf.lookup_transform("odom", m.header.frame_id, Time.from_msg(m.header.stamp)).transform
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

    def detect(self, camera: str, target: str) -> dict:
        """Where a target described in words is in the current image of a camera: pixel, and its 3-D point in `odom` from the
        registered depth."""
        f = self.frame(camera)
        # A single VLM answer is not stable (the same frame gave the button once and a point on the rail below it the next
        # time, research repo F53): ask until two answers agree, at most three times, and use the agreeing pair.
        answers = []
        for _ in range(VLM_LOCATE_ASKS):
            found = re.search(r"\{.*\}", self.ask_vlm(f["path"], LOCATE_PROMPT.format(target=target, w=f["uw"], h=f["uh"])), re.S)
            j = json.loads(found.group(0)) if found else {"found": False}
            if j.get("found"):
                box = j.get("box")
                c = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2] if box and len(box) == 4 else j["center"]
                answers.append((np.array(c, float), box))
            else:
                answers.append(None)
            pair = [(a1, a2) for i, a1 in enumerate(answers) for a2 in answers[i + 1:]
                    if a1 is not None and a2 is not None and np.linalg.norm(a1[0] - a2[0]) <= VLM_AGREE_PX]
            if pair or answers.count(None) >= 2:
                break
        out = dict(camera=camera, image=str(f["path"]), frame_stamp_s=round(f["stamp"], 2), found=bool(pair), vlm_answers=len(answers))
        if out["found"]:
            (c1, box), (c2, _) = pair[0]
            j = {"box": box}
            x, y = (c1 + c2) / 2  # upright image -> raw image pixel
            w, h = f["w"], f["h"]
            u, v = {None: (x, y), cv2.ROTATE_90_COUNTERCLOCKWISE: (w - 1 - y, x), cv2.ROTATE_180: (w - 1 - x, h - 1 - y),
                    cv2.ROTATE_90_CLOCKWISE: (y, h - 1 - x)}[f["turn"]]
            ui, vi, k = int(round(u)), int(round(v)), DEPTH_WINDOW_PX
            patch = f["depth"][max(vi - k, 0):vi + k + 1, max(ui - k, 0):ui + k + 1]
            patch = patch[np.isfinite(patch) & (patch > 0)]
            t, R = f["pose_odom"]
            out.update(pixel=[ui, vi], box=j.get("box"), origin=t)
            if patch.size:
                z = float(np.median(patch))
                p_cam = np.linalg.inv(f["K"]) @ np.array([u, v, 1.0]) * z
                out.update(depth_m=round(z, 4), point=R @ p_cam + t)
            else:
                out["found"], out["why"] = False, "no valid depth at the located pixel"
        return out

    def locate_in_view(self, camera: str, target: str):
        d = self.detect(camera, target)
        out = {k: d[k] for k in ("camera", "found", "image", "frame_stamp_s")}
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
        if capability in ("navigate_to_feature", "dock_at_feature"):
            p, n = self.feature_geometry(a["feature"])
            x, y, yaw = work_pose_from(p, n, a.get("standoff_m", 1.5 if capability == "navigate_to_feature" else 0.0))
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
                     "locate_in_view": lambda: self.locate_in_view(args["camera"], args["target"]), "site_map": self.site_map, "arm_state": self.arm_state, "base_pose": self.base_pose, "tcp_pose": self.tcp_pose, "jaw": lambda: {"rad": self.jaw},
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
        deadline = g.deadline_s or float(contract["default_deadline_s"])
        sim0 = self.sim_t
        if g.capability == "approach_target":
            ok, reason, evidence = self.approach_target(args, handle)
            r = ExecuteRskill.Result(success=ok, failure_kind=0 if ok else 3, failure_reason=reason)
        else:
            params = self.lower_effect(g.capability, args)
            r = self.dispatch(handle, contract["lowers_to"], params, deadline)
            evidence = {"rskill": contract["lowers_to"], "goal": goal_summary(params)}
        evidence["sim_s"] = round(self.sim_t - sim0, 2)
        for key, fn in (("base_pose", self.base_pose), ("tcp_pose", self.tcp_pose)):
            try:
                evidence[key] = fn()
            except Exception as exc:  # reason: evidence is best-effort; a missing TF must not hide the skill result
                evidence[key] = f"unavailable: {exc}"
        evidence["arm"] = self.arm_state()
        handle.succeed()
        res.success, res.failure_kind, res.failure_reason = bool(r.success), int(r.failure_kind), r.failure_reason
        res.evidence_json = json.dumps(evidence)
        # the call trace (§4.6): one line per effect, whoever called it
        self.get_logger().info("CAPABILITY " + json.dumps(dict(capability=g.capability, args=args, success=res.success,
                                                               failure_kind=res.failure_kind, failure_reason=res.failure_reason,
                                                               evidence=evidence)))
        return res

    def dispatch(self, handle, rskill_id: str, params: dict, deadline: float):
        """One ExecuteRskill goal through the OpenRAL runner, waited for; feedback keeps the caller informed."""
        goal = ExecuteRskill.Goal(rskill_id=rskill_id, prompt="capability boundary", goal_params_json=json.dumps(params), deadline_s=deadline)
        sim0 = self.sim_t
        handle.publish_feedback(ExecuteCapability.Feedback(state="dispatched", elapsed_s=0.0))
        sent = self.rskill.send_goal_async(goal)
        while not sent.done():
            time.sleep(0.05)
        gh = sent.result()
        if gh is None or not gh.accepted:
            return ExecuteRskill.Result(success=False, failure_kind=255, failure_reason="rskill runner rejected the goal")
        rf = gh.get_result_async()
        last = 0.0
        while not rf.done():
            time.sleep(0.1)
            if time.time() - last > 2.0:
                handle.publish_feedback(ExecuteCapability.Feedback(state="executing", elapsed_s=float(self.sim_t - sim0)))
                last = time.time()
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
