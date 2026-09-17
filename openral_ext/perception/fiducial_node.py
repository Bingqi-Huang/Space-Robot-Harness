#!/usr/bin/env python3
"""Relative perception for the shared stack (Phase E; replaces the simulator-truth stand-ins, execution_plan §13.2).

Site equipment and movable objects carry AprilTag 36h11 targets (the way servicing hardware carries visual targets for
a manipulator). This node detects them in the rover's front and wrist camera images, solves each tag's pose from its
known size (IPPE), chains it through the camera's TF at the image stamp, and publishes where each carrier is:

    /space/perception/instances  std_msgs/String (JSON), latched-style republish at 2 Hz
      {instance: {"carrier", "frame": "odom", "position", "quat_xyzw", "stamp", "camera", "tag", "range_m"}}

Poses are kept in `odom` (smooth wheel-inertial odometry): an arm target derived from them stays consistent through
the rover's own motion estimate, without the jumps of the map correction. A static carrier (a service panel, shelf,
stand) is associated with the surveyed instance nearest to where the rover's localization puts it; a movable object is
its own instance. Which tag is where on which carrier is `fiducials.yaml` (hardware documentation, not mission logic).
Nothing here reads simulator truth. Run inside a sourced graph:
    python3 openral_ext/perception/fiducial_node.py
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np
import rclpy
import yaml
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

HERE = Path(__file__).resolve().parent
LAYOUT = yaml.safe_load((HERE / "fiducials.yaml").read_text())
IX = json.loads((HERE / "../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json").resolve().read_text())
CAMERAS = ("front", "wrist")


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


def T(R, p):
    M = np.eye(4)
    M[:3, :3], M[:3, 3] = R, p
    return M


def tag_in_carrier(spec) -> np.ndarray:
    """Tag frame (OpenCV marker convention: x right, y up, z out of the face) in the carrier frame, from the face's
    outward normal and its up direction."""
    z = np.array(spec["normal"], float)
    y = np.array(spec.get("up", [0.0, 0.0, 1.0]), float)
    return T(np.stack([np.cross(y, z), y, z], axis=1), spec["xyz"])


INSTANCE_TYPE = {inst: kind for kind, insts in LAYOUT["static_carriers"].items() for inst in insts}
AUTHORED = HERE / "../../space_robotics_bench/assets/lunar_base/authored"


def carrier_frames(kind: str) -> dict:
    """Named interaction frames of a static carrier in its own frame (the authoring output)."""
    return json.loads((AUTHORED / kind / "frames.json").resolve().read_text())


def surveyed_instances() -> dict:
    """Map pose of every static carrier instance, from one surveyed interaction point and the carrier's own frames."""
    out = {}
    for name, pt in IX["points"].items():
        prop, feature = name.split("/")
        if prop in out or prop not in INSTANCE_TYPE or "object" in pt:
            continue
        off = np.array(carrier_frames(INSTANCE_TYPE[prop])[feature]["xyz"], float)
        yaw = math.atan2(pt["normal"][1], pt["normal"][0])
        R = np.array([[math.cos(yaw), -math.sin(yaw), 0.0], [math.sin(yaw), math.cos(yaw), 0.0], [0.0, 0.0, 1.0]])
        out[prop] = {"carrier": INSTANCE_TYPE[prop], "T_map": T(R, np.array(pt["xyz"], float) - R @ off)}
    return out


class FiducialNode(Node):
    def __init__(self):
        super().__init__("space_fiducial_perception", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.buf = Buffer()
        TransformListener(self.buf, self)
        self.detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11))
        self.tags = {int(k): v for k, v in LAYOUT["tags"].items()}
        self.survey = surveyed_instances()
        self.images, self.K, self.seen = {}, {}, {}
        for cam in CAMERAS:
            self.create_subscription(Image, f"/openral/cameras/{cam}/image", lambda m, c=cam: self.images.__setitem__(c, m), qos_profile_sensor_data)
            self.create_subscription(CameraInfo, f"/openral/cameras/{cam}/camera_info", lambda m, c=cam: self.K.__setitem__(c, m), qos_profile_sensor_data)
        self.pub = self.create_publisher(String, "/space/perception/instances",
                                         QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
        self.create_timer(0.25, self.detect)
        self.create_timer(0.5, self.publish)
        self.get_logger().info(f"fiducial perception: {len(self.tags)} tags, {len(self.survey)} surveyed static instances")

    def detect(self):
        for cam in CAMERAS:
            m, info = self.images.pop(cam, None), self.K.get(cam)
            if m is None or info is None:
                continue
            gray = cv2.cvtColor(np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1), cv2.COLOR_RGB2GRAY)
            corners, ids, _ = self.detector.detectMarkers(gray)
            if ids is None:
                continue
            stamp = Time.from_msg(m.header.stamp)
            if not self.buf.can_transform("odom", m.header.frame_id, stamp):
                continue
            tr = self.buf.lookup_transform("odom", m.header.frame_id, stamp).transform
            T_odom_cam = T(quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w),
                           [tr.translation.x, tr.translation.y, tr.translation.z])
            K = np.array(info.k).reshape(3, 3)
            for c, tag_id in zip(corners, ids.ravel()):
                spec = self.tags.get(int(tag_id))
                if spec is None:
                    continue
                s = spec["size_m"] / 2
                obj = np.array([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]], np.float32)
                ok, rvec, tvec = cv2.solvePnP(obj, c.reshape(4, 2), K, np.zeros(5), flags=cv2.SOLVEPNP_IPPE_SQUARE)
                T_cam_tag = T(cv2.Rodrigues(rvec)[0], tvec.ravel())
                T_odom_carrier = T_odom_cam @ T_cam_tag @ np.linalg.inv(tag_in_carrier(spec))
                instance = spec["carrier"] if spec["carrier"] in LAYOUT["movable_carriers"] else self.associate(spec["carrier"], T_odom_carrier)
                if instance is None:
                    continue
                self.seen[instance] = {"carrier": spec["carrier"], "frame": "odom",
                                       "position": [round(float(v), 4) for v in T_odom_carrier[:3, 3]],
                                       "quat_xyzw": [round(float(v), 5) for v in mat_to_quat(T_odom_carrier[:3, :3])],
                                       "stamp": round(stamp.nanoseconds * 1e-9, 3), "camera": cam, "tag": int(tag_id),
                                       "range_m": round(float(np.linalg.norm(tvec)), 3)}

    def associate(self, carrier: str, T_odom_carrier: np.ndarray):
        """The surveyed instance of this carrier type nearest to the detection, placed in `map` by the rover's localization."""
        tr = self.buf.lookup_transform("map", "odom", Time()).transform
        T_map_odom = T(quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w),
                       [tr.translation.x, tr.translation.y, tr.translation.z])
        p = (T_map_odom @ T_odom_carrier)[:2, 3]
        best = min(((np.linalg.norm(p - v["T_map"][:2, 3]), k) for k, v in self.survey.items() if v["carrier"] == carrier), default=None)
        return best[1] if best is not None and best[0] < LAYOUT["association_radius_m"] else None

    def publish(self):
        self.pub.publish(String(data=json.dumps(self.seen)))


def main():
    rclpy.init()
    rclpy.spin(FiducialNode())


if __name__ == "__main__":
    main()
