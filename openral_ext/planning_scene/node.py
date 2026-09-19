#!/usr/bin/env python3
"""World geometry for arm planning: the worksite and what the robot measures standing in it (research repo F51 gap 1,
F57). MoveIt's self-model knows the rover only, so a plan to a pre-grasp pose swept through the ORU (5 cm), knocked the
service cover 0.21 m off its panel, and -- with the arm raised straight out of its travel pose while docked at the
depot -- pushed the ORU off its slot. This node publishes `moveit_msgs/CollisionObject`s on `/collision_object`:

- static structures: the surveyed site boxes (`site_structures.json`, the same structures the lidar map shows) in
  `map`, so they land where the robot's own localization puts them -- site knowledge, like the navigation map;
- measured obstacles: what the robot's own depth cameras see standing in the arm's work zone, as one collision object
  of observed surface triangles rebuilt every cycle. Movable items (a staged ORU, a crate, a service cover a moment after it was
  set down) are in nobody's map; they are in the depth image. The arm's own links are filtered
  out by TF, so the arm never plans around itself.

Truth is never read: the obstacles come from the same cameras every method has, so every method's MoveIt calls see the
same scene. Run inside a sourced graph:
    python3 openral_ext/planning_scene/node.py
"""

from collections import deque
import copy
import json
import math
import time
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import Pose, Point
from moveit_msgs.msg import AllowedCollisionEntry, CollisionObject, PlanningScene, PlanningSceneComponents
from moveit_msgs.srv import ApplyPlanningScene, GetPlanningScene
from openral_msgs.srv import ConfigureContact
from std_srvs.srv import Trigger
from rclpy.callback_groups import ReentrantCallbackGroup
from openral_rskill.grasp_perception import GripperGeometry
from surfaces import depth_surface
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from shape_msgs.msg import SolidPrimitive, Mesh, MeshTriangle
from tf2_ros import Buffer, TransformListener

SITE = Path(__file__).resolve().parent / "../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base"
STRUCTURES = json.loads((SITE / "site_structures.json").read_text())["structures"]
IX = json.loads((SITE / "interaction.json").read_text())

#: the arm's own links, from its base to the tool: their measured pixels are the robot, not the world
ARM_LINKS = ("base_link", "Link1", "Link2", "Link3", "Link4", "Link5", "Link6", "Link7", "tcp_frame")
LINK_CLEAR_M = 0.18  # a measured point this close to an arm link is the arm itself (its links are ~0.1 m across)
ZONE_M = 1.4  # how far around the arm's base the work zone reaches (RM-75 works to 0.61 m; the rest is margin)
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
        self.depth = {cam: deque(maxlen=qos_profile_sensor_data.depth) for cam in ("wrist", "front")}
        self.info: dict[str, CameraInfo] = {}
        for cam in ("wrist", "front"):
            self.create_subscription(Image, f"/openral/cameras/{cam}_depth/image",
                                     lambda m, c=cam: self.depth[c].append(m), qos_profile_sensor_data)
            self.create_subscription(CameraInfo, f"/openral/cameras/{cam}/camera_info",
                                     lambda m, c=cam: self.info.__setitem__(c, m), qos_profile_sensor_data)
        self.frozen = False
        self.contact_region = None
        self.scene_revision = 0
        self.scene_evidence = {}
        self.apply_client = self.create_client(ApplyPlanningScene, "/apply_planning_scene",
                                               callback_group=ReentrantCallbackGroup())
        self.get_scene_client = self.create_client(GetPlanningScene, "/get_planning_scene",
                                                   callback_group=ReentrantCallbackGroup())
        self.create_service(ConfigureContact, "/space/configure_contact", self.configure_contact)
        self.create_service(Trigger, "/space/prepare_contact_scene", self.prepare_contact)
        self.create_service(Trigger, "/space/release_contact_scene", self.release_contact)
        self.create_timer(0.5, self.tick)
        self.create_timer(1.0, self.measure)
        self.get_logger().info("shared planning scene: measured 3-D surfaces; no target deletion")

    async def prepare_contact(self, request, response):
        # This service returns only after the collision consumer applied the scene.
        # Frozen geometry is a stationary-workpiece snapshot for one serial operation.
        if self.frozen:
            response.message = "contact scene already owned by an operation"
            return response
        request = GetPlanningScene.Request()
        request.components.components = PlanningSceneComponents.ALLOWED_COLLISION_MATRIX
        snapshot = await self.get_scene_client.call_async(request)
        self.original_acm = snapshot.scene.allowed_collision_matrix
        response.success = await self.measure()
        self.frozen = response.success
        response.message = json.dumps(self.scene_evidence)
        return response

    async def release_contact(self, request, response):
        # Restore both geometry and the exact prior ACM before admitting another operation.
        scene = PlanningScene(is_diff=True)
        scene.allowed_collision_matrix = self.original_acm
        scene.world.collision_objects = [self.measured_object]
        if self.contact_region is not None and self.contact_region["contact_triangles"] > 0:
            scene.world.collision_objects.append(
                CollisionObject(id="measured/contact", operation=CollisionObject.REMOVE))
        result = await self.apply_client.call_async(ApplyPlanningScene.Request(scene=scene))
        response.success = result.success
        if result.success:
            self.contact_region = None
            self.frozen = False
        response.message = "contact geometry and permissions restored" if result.success else "contact release not applied"
        return response

    async def configure_contact(self, request, response):
        phase = request.phase
        evidence = {"phase": phase, "scene": self.scene_evidence.get("scene"), "applied": False}
        if not self.frozen or phase not in ("register", "endpoint_check", "insertion", "revoke"):
            evidence["reason"] = "requires an acquired scene and a declared contact phase"
        elif phase == "register" and self.contact_region is not None:
            evidence["reason"] = "selected region is immutable until operation release"
        elif phase != "register" and self.contact_region is None:
            evidence["reason"] = "no selected measured contact region"
        elif phase != "register" and self.contact_region["contact_triangles"] == 0:
            evidence.update(applied=True, reason="nothing exempted for this region")
            response.success = True
        else:
            scene = PlanningScene(is_diff=True)
            if phase == "register":
                pose = request.region.pose
                q = pose.orientation
                region = np.eye(4)
                region[:3, :3] = quat_to_mat(q.x, q.y, q.z, q.w)
                region[:3, 3] = [pose.position.x, pose.position.y, pose.position.z]
                transform = self.T("map", request.region.header.frame_id)
                dimensions = np.array([request.dimensions.x, request.dimensions.y, request.dimensions.z])
                if transform is None or not np.all(dimensions > 0) or not request.evidence_ref:
                    evidence["reason"] = "region requires TF, positive measured dimensions and evidence"
                    response.evidence_json = json.dumps(evidence)
                    return response
                region = transform @ region
                remainder = copy.deepcopy(self.measured_object)
                target = CollisionObject(id="measured/contact", operation=CollisionObject.ADD)
                target.header.frame_id = "map"
                count = 0
                for mesh, mesh_pose in zip(remainder.meshes, remainder.mesh_poses):
                    vertices = np.array([[v.x, v.y, v.z] for v in mesh.vertices])
                    local = (vertices - region[:3, 3]) @ region[:3, :3]
                    inside = np.all(abs(local) <= dimensions / 2, axis=1)
                    # Keep boundary-crossing triangles protected. No triangle is removed.
                    selected = [t for t in mesh.triangles if np.all(inside[t.vertex_indices])]
                    mesh.triangles = [t for t in mesh.triangles if not np.all(inside[t.vertex_indices])]
                    if selected:
                        target.meshes.append(Mesh(vertices=mesh.vertices, triangles=selected))
                        target.mesh_poses.append(mesh_pose)
                        count += len(selected)
                evidence.update(region_map=region.tolist(), dimensions_m=dimensions.tolist(),
                                evidence_ref=request.evidence_ref, contact_triangles=count,
                                contact_links=list(GripperGeometry().contact_links))
                if count == 0:
                    # No measured surface there means nothing to exempt, not an unsafe contact: every other
                    # check stays in force, and the later phases have no permission to change (g8u, F78).
                    evidence.update(applied=True, reason="no measured surface in the selected region; nothing exempted")
                    self.contact_region = evidence
                    response.success = True
                    response.evidence_json = json.dumps(evidence)
                    return response
                scene.world.collision_objects = [remainder, target]
            allowed = phase in ("endpoint_check", "insertion")
            acm = copy.deepcopy(self.original_acm)
            for name in ("measured/contact", *GripperGeometry().contact_links):
                if name not in acm.entry_names:
                    acm.entry_names.append(name)
                    for entry in acm.entry_values:
                        entry.enabled.append(False)
                    acm.entry_values.append(AllowedCollisionEntry(enabled=[False] * len(acm.entry_names)))
            target_index = acm.entry_names.index("measured/contact")
            # This new object has no inherited world-wide/default exemptions.
            acm.entry_values[target_index].enabled = [False] * len(acm.entry_names)
            for entry in acm.entry_values:
                entry.enabled[target_index] = False
            for link in GripperGeometry().contact_links:
                index = acm.entry_names.index(link)
                acm.entry_values[index].enabled[target_index] = allowed
                acm.entry_values[target_index].enabled[index] = allowed
            scene.allowed_collision_matrix = acm
            result = await self.apply_client.call_async(ApplyPlanningScene.Request(scene=scene))
            response.success = result.success
            evidence.update(applied=result.success, contact_allowed=allowed,
                            contact_links=list(GripperGeometry().contact_links))
            if result.success and phase == "register":
                self.contact_region = evidence
        response.evidence_json = json.dumps(evidence)
        return response

    def T(self, target: str, source: str, stamp=None):
        try:
            tr = self.buf.lookup_transform(target, source, rclpy.time.Time() if stamp is None else rclpy.time.Time.from_msg(stamp)).transform
        except Exception as exc:
            self.tf_failure = str(exc)
            return None
        M = np.eye(4)
        M[:3, :3] = quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w)
        M[:3, 3] = [tr.translation.x, tr.translation.y, tr.translation.z]
        return M

    def arm_segments(self, stamp=None) -> np.ndarray:
        """The arm as it stands now, in `map`: the segments between consecutive link origins. A link is a metre of
        steel, not a point -- filtering by the origins alone leaves the middle of every link in the depth image, and
        the arm then plans around itself."""
        pts = [M[:3, 3] for M in (self.T("map", link, stamp) for link in ARM_LINKS) if M is not None]
        return np.array([[a, b] for a, b in zip(pts[:-1], pts[1:])]) if len(pts) > 1 else np.zeros((0, 2, 3))

    def measured_mesh(self, cam: str):
        info = self.info.get(cam)
        if info is None:
            return None
        # Sensor and TF messages arrive independently. Use the newest image with
        # its own timestamped transforms, within the sensor QoS history.
        for m in reversed(self.depth[cam]):
            T = self.T("map", m.header.frame_id, m.header.stamp)
            base = self.T("map", "chassis_base_link", m.header.stamp)
            if T is not None and base is not None:
                break
        else:
            return None
        z = np.frombuffer(m.data, np.float32).reshape(m.height, m.width)
        K = np.array(info.k, float).reshape(3, 3)
        valid = np.isfinite(z) & (z > 0.05) & (z < MAX_RANGE_M)
        vs, us = np.nonzero(valid)
        d = z[vs, us]
        pc = np.stack([(us - K[0, 2]) / K[0, 0] * d, (vs - K[1, 2]) / K[1, 1] * d, d], axis=1)
        pm = pc @ T[:3, :3].T + T[:3, 3]
        keep = np.linalg.norm(pm[:, :2] - base[:3, 3][:2], axis=1) < ZONE_M
        # The existing arm self-filter only removes measurements; it never
        # certifies the resulting holes as free space.
        for a, b in self.arm_segments(m.header.stamp):
            ab = b - a
            t = np.clip((pm - a) @ ab / max(float(ab @ ab), 1e-9), 0, 1)
            keep &= np.linalg.norm(pm - (a + t[:, None] * ab), axis=1) > LINK_CLEAR_M
        valid[vs, us] = keep
        vertices, faces = depth_surface(z, K, T, valid, GripperGeometry().min_part_width_m)
        mesh = Mesh()
        mesh.vertices = [Point(x=float(x), y=float(y), z=float(z)) for x, y, z in vertices]
        mesh.triangles = [MeshTriangle(vertex_indices=list(map(int, face))) for face in faces]
        return mesh, {"camera": cam, "stamp_s": m.header.stamp.sec + m.header.stamp.nanosec * 1e-9,
                      "triangles": len(faces), "unknown_is_free": False}

    async def measure(self):
        if self.frozen or not self.apply_client.service_is_ready():
            return False
        meshes = [self.measured_mesh(cam) for cam in ("wrist", "front")]
        if any(value is None for value in meshes):
            self.scene_evidence = {"reason": "camera or timestamped TF unavailable",
                                   "cameras": list(self.depth), "camera_info": list(self.info),
                                   "tf_failure": getattr(self, "tf_failure", None)}
            return False
        o = CollisionObject()
        o.header.frame_id, o.id = "map", "measured/work_zone"
        o.operation = CollisionObject.ADD
        for mesh, evidence in meshes:
            if mesh.triangles:
                o.meshes.append(mesh)
                pose = Pose()
                pose.orientation.w = 1.0
                o.mesh_poses.append(pose)
        if not o.meshes:
            self.scene_evidence = {"reason": "no measured surface; previous obstacles retained"}
            return False
        req = ApplyPlanningScene.Request()
        req.scene.is_diff = True
        req.scene.world.collision_objects = [*self.static, o]
        self.scene_revision += 1
        req.scene.name = f"measured_scene_{self.scene_revision}"
        result = await self.apply_client.call_async(req)
        if result.success:
            self.measured_object = o
        self.scene_evidence = {"scene": req.scene.name, "applied": result.success,
                               "observations": [e for _, e in meshes], "target_excluded": False}
        return result.success

    def tick(self):
        if time.time() - self.last_static > 5.0:
            for o in self.static:
                self.pub.publish(o)
            self.last_static = time.time()


def main():
    rclpy.init()
    from rclpy.executors import MultiThreadedExecutor
    executor = MultiThreadedExecutor()
    executor.add_node(PlanningSceneNode())
    executor.spin()


if __name__ == "__main__":
    main()
