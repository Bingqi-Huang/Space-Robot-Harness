#!/usr/bin/env python3
"""The common capability boundary (execution_plan §21.4): one server every method calls identically.

    /space/capability/execute  space_harness_msgs/ExecuteCapability  (effects: PLEXIL Commands, Ours' effect tools)
    /space/capability/query    space_harness_msgs/QueryCapability    (queries: PLEXIL Lookups, Ours' query tools)

The contracts (names, typed inputs, meaning) are `contracts.yaml`. An effect is checked against its contract and lowered
to exactly one `openral_msgs/ExecuteRskill` dispatch on `/openral/execute_rskill`, so every route -- Ours, PLEXIL,
EUROPA->PLEXIL -- passes through the same OpenRAL runner, safety kernel, HAL and simulator. The result carries only
robot-observable evidence (estimated base pose, TCP in the rover frame, jaw); the mission verifier is evaluator-only and
never crosses this boundary. No mission logic lives here: one call, one skill, no retries, no orderings.

The lowering parameters are the ones the D0 checks used when they dispatched rSkills directly (research repo F51), so a
mission driven through this boundary exercises the same skills with the same settings.

Run inside a sourced graph (ROS Humble + openral install + ros/install):
    python3 openral_ext/capability_server/node.py
"""

import base64
import json
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
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from sensor_msgs.msg import Image, JointState
from std_msgs.msg import String
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability
from tf2_ros import Buffer, TransformListener

import yaml

from contracts import CONTRACTS, HERE, IX, check_args
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
REJECTED = 20  # failure_kind: refused at the boundary (unknown capability / arguments off-contract)
JAW_JOINT = "eg2_joint1"
HULL_M, REACH_M = IX["robot"]["hull_x_back_m"], IX["robot"]["reach_m"]["press"]  # arm reach past the hull (C3)


FIDUCIALS = yaml.safe_load((HERE / "../perception/fiducials.yaml").read_text())
INSTANCE_TYPE = {inst: kind for kind, insts in FIDUCIALS["static_carriers"].items() for inst in insts}
AUTHORED = HERE / "../../space_robotics_bench/assets/lunar_base/authored"
MOVABLE = FIDUCIALS["movable_carriers"]


def carrier_frame(kind: str, key: str) -> dict:
    return json.loads((AUTHORED / kind / "frames.json").resolve().read_text())[key]


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
        self.perceived, self.jaw, self.arm_q, self.sim_t = {}, None, None, 0.0
        # relative perception (openral_ext/perception/fiducial_node.py): carrier poses in `odom`
        self.create_subscription(String, "/space/perception/instances", lambda m: setattr(self, "perceived", json.loads(m.data)),
                                 QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL), callback_group=cb)
        self.create_subscription(JointState, "/srb/env0/robot/joint_states", self._on_joints, 10, callback_group=cb)
        self.create_subscription(Clock, "/clock", lambda m: setattr(self, "sim_t", m.clock.sec + m.clock.nanosec * 1e-9), 10, callback_group=cb)
        self.images = {}
        for cam in ("front", "wrist"):
            self.create_subscription(Image, f"/openral/cameras/{cam}/image", lambda m, cam=cam: self.images.__setitem__(cam, m),
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

    def observe(self, camera: str, question: str):
        m = self.images[camera]
        img = np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1)
        bgr = cv2.cvtColor(img, {"rgb8": cv2.COLOR_RGB2BGR, "rgba8": cv2.COLOR_RGBA2BGR, "bgra8": cv2.COLOR_BGRA2BGR}[m.encoding]) if m.encoding != "bgr8" else img
        stamp = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        path = self.evidence_dir / f"{camera}_{stamp:010.2f}.jpg"
        cv2.imwrite(str(path), bgr)
        b64 = base64.b64encode(path.read_bytes()).decode()
        r = self.vlm.chat.completions.create(model=VLM_MODEL, messages=[{"role": "user", "content": [
            {"type": "text", "text": f"{question}\nAnswer from this camera image only, briefly. If it cannot be seen clearly, say so."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}])
        return {"camera": camera, "answer": (r.choices[0].message.content or "").strip(), "frame_stamp_s": round(stamp, 2),
                "image": str(path), "model": VLM_MODEL}

    def tcp_pose(self):
        p, R = self._tf("chassis_base_link", "tcp_frame")
        return {"frame": "chassis_base_link", "position": [round(float(v), 4) for v in p]}

    def feature_geometry(self, name: str) -> dict:
        """Where a feature is: point, horizontal outward normal (the side the arm works from) and the frame they are in.

        Static equipment: the carrier pose the cameras last measured (`odom`), else the surveyed site point (`map`,
        placed by the rover's localization). Movable objects: measured only -- an object never seen is not locatable.
        """
        head, key = (name.split("/") + [""])[:2]
        seen = self.perceived.get(head)
        if head in MOVABLE:
            if seen is None:
                raise LookupError(f"{head} has not been seen by the rover's cameras; look at it first")
            T = np.eye(4)
            T[:3, :3], T[:3, 3] = quat_to_mat(*seen["quat_xyzw"]), seen["position"]
            if head == "service_cover":
                h = carrier_frame("service_cover", "handle")
                n = horizontal(T[:3, :3] @ np.array(h["normal"], float))
            else:
                h = IX["objects"][head]["handle"]
                axis = horizontal(T[:3, :3] @ np.array({"X": [1.0, 0, 0], "Y": [0, 1.0, 0]}[h["axis"]]))
                n = np.array([-axis[1], axis[0], 0.0])  # the jaws straddle the bail: approach across its axis ...
                rover, _ = self._tf("odom", "chassis_base_link")
                n = n if n @ (rover - T[:3, 3]) >= 0 else -n  # ... from the rover's side
            return dict(frame="odom", p=T[:3, :3] @ np.array(h["xyz"], float) + T[:3, 3], n=n, source="fiducial",
                        age_s=round(self.sim_t - seen["stamp"], 1), object=IX["objects"][head])
        pt = IX["points"][name]
        if seen is not None:
            f = carrier_frame(INSTANCE_TYPE[head], key)
            T = np.eye(4)
            T[:3, :3], T[:3, 3] = quat_to_mat(*seen["quat_xyzw"]), seen["position"]
            return dict(frame="odom", p=T[:3, :3] @ np.array(f["xyz"], float) + T[:3, 3], n=horizontal(T[:3, :3] @ np.array(f["normal"], float)),
                        source="fiducial", age_s=round(self.sim_t - seen["stamp"], 1))
        return dict(frame="map", p=np.array(pt["xyz"], float), n=horizontal(pt["normal"]), source="survey")

    def in_frame(self, g: dict, target: str):
        t, R = self._tf(target, g["frame"])
        return R @ g["p"] + t, R @ g["n"]

    def locate_feature(self, name):
        g = self.feature_geometry(name)
        p, n = self.in_frame(g, "chassis_base_link")
        out = {"frame": "chassis_base_link", "position": [round(float(v), 4) for v in p], "normal": [round(float(v), 4) for v in n],
               "source": g["source"]}
        if "age_s" in g:
            out["measured_s_ago"] = g["age_s"]
        if "object" in g:
            o = g["object"]
            out["object"] = {"size_m": o["size_m"], "handle_height_above_base_m": o.get("handle", {}).get("xyz", [0, 0, None])[2]}
        return out

    def feature_target(self, a: dict) -> dict:
        """TCP target for a feature capability, in the rover frame, from the feature's measured or surveyed geometry."""
        p, n = self.in_frame(self.feature_geometry(a["feature"]), "chassis_base_link")
        p = p + n * a["offset_m"] + np.array([0.0, 0.0, a.get("lift_m", 0.0)])
        return {"position": p.tolist(), "orientation_xyzw": mat_to_quat(tool_rotation(n, a.get("orientation", "press")))}

    def lower_effect(self, capability: str, a: dict) -> dict:
        if capability in ("navigate_to_feature", "dock_at_feature"):
            p, n = self.in_frame(self.feature_geometry(a["feature"]), "map")
            x, y, yaw = work_pose_from(p, n, a.get("standoff_m", 1.5 if capability == "navigate_to_feature" else 0.0))
            if capability == "navigate_to_feature":
                return lower("navigate_to_pose", dict(x=x, y=y, yaw=yaw))
            return lower("dock_to_pose", dict(x=x, y=y, yaw=yaw, **({"approach_m": a["approach_m"]} if "approach_m" in a else {})))
        if capability == "plan_ee_to_feature":
            return lower("plan_ee_pose", {**self.feature_target(a), **({"tolerance_m": a["tolerance_m"]} if "tolerance_m" in a else {})})
        if capability == "move_ee_to_feature":
            extra = {k: a[k] for k in ("tolerance_m", "max_linear_speed_m_s", "timeout_s") if k in a}
            return lower("move_ee_to_pose", {**self.feature_target(a), **extra})
        return lower(capability, a)

    def _query(self, req, res):
        try:
            args = json.loads(req.args_json or "{}")
            if req.query not in CONTRACTS["queries"]:
                raise KeyError(f"unknown query {req.query!r}")
            reason = check_args(CONTRACTS["queries"][req.query], args)
            if reason:
                raise ValueError(reason)
            value = {"observe": lambda: self.observe(args["camera"], args["question"]), "site_map": self.site_map, "arm_state": self.arm_state, "base_pose": self.base_pose, "tcp_pose": self.tcp_pose, "jaw": lambda: {"rad": self.jaw},
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
        try:
            params = self.lower_effect(g.capability, args)
        except LookupError as exc:  # the target cannot be located (an object not yet seen): a typed refusal, not a crash
            handle.succeed()
            res.success, res.failure_kind, res.failure_reason = False, REJECTED, str(exc)
            return res
        goal = ExecuteRskill.Goal(rskill_id=contract["lowers_to"], prompt=f"capability {g.capability}",
                                  goal_params_json=json.dumps(params), deadline_s=deadline)
        sim0 = self.sim_t
        handle.publish_feedback(ExecuteCapability.Feedback(state="dispatched", elapsed_s=0.0))
        sent = self.rskill.send_goal_async(goal)
        while not sent.done():
            time.sleep(0.05)
        gh = sent.result()
        if gh is None or not gh.accepted:
            handle.succeed()
            res.success, res.failure_kind, res.failure_reason = False, 255, "rskill runner rejected the goal"
            return res
        rf = gh.get_result_async()
        last = 0.0
        while not rf.done():
            time.sleep(0.1)
            if time.time() - last > 2.0:
                handle.publish_feedback(ExecuteCapability.Feedback(state="executing", elapsed_s=float(self.sim_t - sim0)))
                last = time.time()
        r = rf.result().result
        evidence = {"sim_s": round(self.sim_t - sim0, 2), "rskill": contract["lowers_to"], "goal": goal_summary(params)}
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
