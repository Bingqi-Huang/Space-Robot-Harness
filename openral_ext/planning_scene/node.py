#!/usr/bin/env python3
"""World geometry for arm planning: the worksite and what the robot measures standing in it (research repo F51 gap 1,
F57). MoveIt's self-model knows the rover only, so a plan to a pre-grasp pose swept through the ORU (5 cm), knocked the
service cover 0.21 m off its panel, and -- with the arm raised straight out of its travel pose while docked at the
depot -- pushed the ORU off its slot. This node publishes `moveit_msgs/CollisionObject`s on `/collision_object`:

- static structures: the surveyed site boxes (`site_structures.json`, the same structures the lidar map shows) in
  `map`, so they land where the robot's own localization puts them -- site knowledge, like the navigation map;
- measured obstacles: what the robot's own depth cameras see standing in the arm's work zone, as one collision object
  of coarse columns rebuilt every cycle. Movable items (a staged ORU, a crate, a service cover a moment after it was
  set down) are in nobody's map; they are in the depth image. The arm's own links and the rover's hull are filtered
  out by TF, so the arm never plans around itself.

Truth is never read: the obstacles come from the same cameras every method has, so every method's MoveIt calls see the
same scene. Run inside a sourced graph:
    python3 openral_ext/planning_scene/node.py
"""

import json
import math
import time
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import Pose
from moveit_msgs.msg import CollisionObject
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from shape_msgs.msg import SolidPrimitive
from tf2_ros import Buffer, TransformListener

SITE = Path(__file__).resolve().parent / "../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base"
STRUCTURES = json.loads((SITE / "site_structures.json").read_text())["structures"]
IX = json.loads((SITE / "interaction.json").read_text())

#: the arm's own links, from its base to the tool: their measured pixels are the robot, not the world
ARM_LINKS = ("base_link", "Link1", "Link2", "Link3", "Link4", "Link5", "Link6", "Link7", "tcp_frame")
LINK_CLEAR_M = 0.18  # a measured point this close to an arm link is the arm itself (its links are ~0.1 m across)
CELL_M = 0.08  # one column per cell: coarse enough that a work zone is tens of boxes, fine enough for a handle
ZONE_M = 1.4  # how far around the arm's base the work zone reaches (RM-75 works to 0.61 m; the rest is margin)
GROUND_CLEAR_M = 0.06  # a column this low is the ground the wheels stand on, not an obstacle
MAX_RANGE_M = 2.5


def box(obj_id: str, size, x, y, z, qx, qy, qz, qw, frame="map") -> CollisionObject:
    o = CollisionObject()
    o.header.frame_id = frame
    o.id = obj_id
    o.operation = CollisionObject.ADD
    o.primitives.append(SolidPrimitive(type=SolidPrimitive.BOX, dimensions=[float(v) for v in size]))
    p = Pose()
    p.position.x, p.position.y, p.position.z = float(x), float(y), float(z)
    p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = float(qx), float(qy), float(qz), float(qw)
    o.primitive_poses.append(p)
    return o


def rotate(q, v):
    x, y, z, w = q
    ux, uy, uz = y * v[2] - z * v[1], z * v[0] - x * v[2], x * v[1] - y * v[0]
    return [v[0] + 2 * (w * ux + y * uz - z * uy), v[1] + 2 * (w * uy + z * ux - x * uz), v[2] + 2 * (w * uz + x * uy - y * ux)]


def quat_to_mat(x, y, z, w) -> np.ndarray:
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def columns(points: np.ndarray, floor: float) -> list[tuple[float, float, float, float]]:
    """Measured points -> one column per occupied cell: (x, y, top, height). A column runs from the ground to the
    highest point measured in its cell, which is what an arm must go around whatever the thing is."""
    if not len(points):
        return []
    keys = np.floor(points[:, :2] / CELL_M).astype(int)
    out: dict[tuple[int, int], float] = {}
    for (cx, cy), z in zip(map(tuple, keys), points[:, 2]):
        if z > out.get((cx, cy), -np.inf):
            out[(cx, cy)] = float(z)
    cols = []
    for (cx, cy), top in out.items():
        height = top - floor
        if height < GROUND_CLEAR_M:
            continue
        cols.append(((cx + 0.5) * CELL_M, (cy + 0.5) * CELL_M, top, height))
    return cols


class PlanningSceneNode(Node):
    def __init__(self):
        super().__init__("space_planning_scene", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.pub = self.create_publisher(CollisionObject, "/collision_object", 50)
        self.static = [box(f"site/{s['name']}", [s["size_xy"][0], s["size_xy"][1], s["z1"] - s["z0"]],
                           s["center"][0], s["center"][1], (s["z0"] + s["z1"]) / 2, 0.0, 0.0, math.sin(s["yaw"] / 2), math.cos(s["yaw"] / 2))
                       for s in STRUCTURES]
        self.last_static = 0.0
        self.buf = Buffer()
        self.tf = TransformListener(self.buf, self)
        self.depth: dict[str, Image] = {}
        self.info: dict[str, CameraInfo] = {}
        for cam in ("wrist", "front"):
            self.create_subscription(Image, f"/openral/cameras/{cam}_depth/image",
                                     lambda m, c=cam: self.depth.__setitem__(c, m), qos_profile_sensor_data)
            self.create_subscription(CameraInfo, f"/openral/cameras/{cam}/camera_info",
                                     lambda m, c=cam: self.info.__setitem__(c, m), qos_profile_sensor_data)
        # what a skill is working on: the sphere it says its tool is about to occupy (`_eye_in_hand.working_on`).
        # An item the planner treats as an obstacle is an item the robot can never take hold of (research repo F58).
        self.working_on: tuple[float, np.ndarray, float] | None = None
        self.create_subscription(CollisionObject, "/space/manipulation_target", self.on_working_on, 10)
        self.create_timer(0.5, self.tick)
        self.create_timer(1.0, self.measure)
        self.get_logger().info(f"planning scene: {len(self.static)} site structures, measured obstacles from wrist + front depth")

    def on_working_on(self, m: CollisionObject) -> None:
        if m.operation == CollisionObject.REMOVE or not m.primitives:
            self.working_on = None
            return
        p = m.primitive_poses[0].position
        self.working_on = (m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, np.array([p.x, p.y, p.z]),
                           float(m.primitives[0].dimensions[0]))
        self.working_frame = m.header.frame_id

    def T(self, target: str, source: str):
        try:
            tr = self.buf.lookup_transform(target, source, rclpy.time.Time()).transform
        except Exception:
            return None
        M = np.eye(4)
        M[:3, :3] = quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w)
        M[:3, 3] = [tr.translation.x, tr.translation.y, tr.translation.z]
        return M

    def arm_segments(self) -> np.ndarray:
        """The arm as it stands now, in `map`: the segments between consecutive link origins. A link is a metre of
        steel, not a point -- filtering by the origins alone leaves the middle of every link in the depth image, and
        the arm then plans around itself."""
        pts = [M[:3, 3] for M in (self.T("map", link) for link in ARM_LINKS) if M is not None]
        return np.array([[a, b] for a, b in zip(pts[:-1], pts[1:])]) if len(pts) > 1 else np.zeros((0, 2, 3))

    def measured(self, cam: str) -> np.ndarray:
        """The depth image of one camera as points in `map`, thinned, in range, and clear of the arm's own links."""
        m, info = self.depth.get(cam), self.info.get(cam)
        if m is None or info is None:
            return np.zeros((0, 3))
        T = self.T("map", m.header.frame_id)
        if T is None:
            return np.zeros((0, 3))
        z = np.frombuffer(m.data, np.float32).reshape(m.height, m.width)[::6, ::6]
        K = np.array(info.k, float).reshape(3, 3)
        vs, us = np.nonzero(np.isfinite(z) & (z > 0.05) & (z < MAX_RANGE_M))
        if not us.size:
            return np.zeros((0, 3))
        d = z[vs, us]
        pc = np.stack([(us * 6 - K[0, 2]) / K[0, 0] * d, (vs * 6 - K[1, 2]) / K[1, 1] * d, d], axis=1)
        pm = (T[:3, :3] @ pc.T).T + T[:3, 3]
        seg = self.arm_segments()
        if len(seg):
            a, b = seg[:, 0, :], seg[:, 1, :]
            ab = b - a
            t = np.clip(np.einsum("pd,sd->ps", pm, ab) - (a * ab).sum(1), 0, None) / np.maximum((ab * ab).sum(1), 1e-9)
            near = a[None, :, :] + np.clip(t, 0, 1)[:, :, None] * ab[None, :, :]
            keep = np.min(np.linalg.norm(pm[:, None, :] - near, axis=2), axis=1) > LINK_CLEAR_M
            pm = pm[keep]
        return pm

    def minus_the_job(self, pts: np.ndarray) -> np.ndarray:
        """Drop what a skill says its tool is about to be inside. A declaration that stops being renewed within two of
        this node's own cycles is gone: a skill that ended, or died, leaves no hole in the world."""
        if self.working_on is None:
            return pts
        stamp, centre, radius = self.working_on
        if self.get_clock().now().nanoseconds * 1e-9 - stamp > 2.0:
            self.working_on = None
            return pts
        T = self.T("map", getattr(self, "working_frame", "chassis_base_link"))
        if T is None:
            return pts
        c = T[:3, :3] @ centre + T[:3, 3]
        return pts[np.linalg.norm(pts - c, axis=1) > radius]

    def measure(self):
        """Publish what the cameras see standing in the arm's work zone as one rebuilt collision object."""
        base = self.T("map", "chassis_base_link")
        if base is None:
            return
        pts = np.vstack([self.measured("wrist"), self.measured("front")])
        if not len(pts):
            return
        near = np.linalg.norm(pts[:, :2] - base[:3, 3][:2], axis=1) < ZONE_M
        pts = pts[near]
        pts = self.minus_the_job(pts)
        if not len(pts):
            return
        floor = float(np.percentile(pts[:, 2], 5))  # the ground, as these very points measured it
        cols = columns(pts, floor)
        o = CollisionObject()
        o.header.frame_id = "map"
        o.id = "measured/work_zone"
        # one object, rebuilt each cycle so nothing stale is left standing; an empty measurement means "nothing is
        # there any more", which is a removal -- an ADD with no shapes is an error to MoveIt, not an empty scene
        o.operation = CollisionObject.ADD if cols else CollisionObject.REMOVE
        for x, y, top, height in cols:
            o.primitives.append(SolidPrimitive(type=SolidPrimitive.BOX, dimensions=[CELL_M, CELL_M, float(height)]))
            p = Pose()
            p.position.x, p.position.y, p.position.z = float(x), float(y), float(top - height / 2)
            p.orientation.w = 1.0
            o.primitive_poses.append(p)
        self.pub.publish(o)

    def tick(self):
        if time.time() - self.last_static > 5.0:
            for o in self.static:
                self.pub.publish(o)
            self.last_static = time.time()


def main():
    rclpy.init()
    rclpy.spin(PlanningSceneNode())


if __name__ == "__main__":
    main()
