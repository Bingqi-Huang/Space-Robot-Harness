#!/usr/bin/env python3
"""World geometry for arm planning: the worksite in MoveIt's planning scene (research repo F51 gap 1).

MoveIt's self-model knows the rover only, so a plan to a pre-grasp pose swept through the ORU (5 cm) and knocked
the service cover 0.21 m off its panel. This node publishes `moveit_msgs/CollisionObject`s on `/collision_object`,
all in `map` so they land where the robot's own localization puts them:

- static structures: the surveyed site boxes (`site_structures.json`, the same structures the lidar map shows) --
  site knowledge, like the navigation map;
- movable objects (spare ORU, cargo crate, service cover): where the rover's cameras last measured them
  (openral_ext/perception/fiducial_node.py, in `odom`); an object not yet seen is not in the scene.

Part of the shared stack: every method's MoveIt calls see the same scene. Run inside a sourced graph:
    python3 openral_ext/planning_scene/node.py
"""

import json
import math
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import Pose
from moveit_msgs.msg import CollisionObject
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from shape_msgs.msg import SolidPrimitive
from std_msgs.msg import String

SITE = Path(__file__).resolve().parent / "../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base"
STRUCTURES = json.loads((SITE / "site_structures.json").read_text())["structures"]
IX = json.loads((SITE / "interaction.json").read_text())
# movable objects: box size from the interaction layer, box centre in the object's own frame (ORU and crate sit on
# their bottom centre; the cover's origin is its back-bottom centre, the bar towards +x -- lunar_base_mission_a)
MOVABLE = {name: [IX["objects"][name]["size_m"][0] / 2 if name == "service_cover" else 0.0, 0.0, IX["objects"][name]["size_m"][2] / 2]
           for name in ("spare_oru", "spare_crate", "service_cover") if name in IX["objects"]}


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


class PlanningSceneNode(Node):
    def __init__(self):
        super().__init__("space_planning_scene", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.pub = self.create_publisher(CollisionObject, "/collision_object", 50)
        self.perceived = {}
        self.create_subscription(String, "/space/perception/instances", lambda m: setattr(self, "perceived", json.loads(m.data)),
                                 QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
        self.static = [box(f"site/{s['name']}", [s["size_xy"][0], s["size_xy"][1], s["z1"] - s["z0"]],
                           s["center"][0], s["center"][1], (s["z0"] + s["z1"]) / 2, 0.0, 0.0, math.sin(s["yaw"] / 2), math.cos(s["yaw"] / 2))
                       for s in STRUCTURES]
        self.last_static = 0.0
        self.create_timer(0.5, self.tick)
        self.get_logger().info(f"planning scene: {len(self.static)} site structures, movable {sorted(MOVABLE)} (perceived)")

    def tick(self):
        if time.time() - self.last_static > 5.0:
            for o in self.static:
                self.pub.publish(o)
            self.last_static = time.time()
        for name, centre in MOVABLE.items():
            seen = self.perceived.get(name)
            if seen is None:
                continue
            q, p = seen["quat_xyzw"], seen["position"]
            c = rotate(q, centre)
            self.pub.publish(box(f"object/{name}", IX["objects"][name]["size_m"], p[0] + c[0], p[1] + c[1], p[2] + c[2], *q, frame="odom"))


def main():
    rclpy.init()
    rclpy.spin(PlanningSceneNode())


if __name__ == "__main__":
    main()
