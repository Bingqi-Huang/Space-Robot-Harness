"""Check scoped contact permissions against an idle, real MoveIt scene; send no motion.

Uses a measured triangle as the region fixture. Restores the acquired scene and
ACM on exit. Run with the same ROS domain/environment as the held graph.
"""
import json
import sys
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from moveit_msgs.msg import PlanningSceneComponents
from moveit_msgs.srv import GetPlanningScene
from openral_msgs.srv import ConfigureContact
from openral_rskill.grasp_perception import GripperGeometry
from openral_rskill._eye_in_hand import quat_to_mat
from std_srvs.srv import Trigger

rclpy.init()
node = Node('check_contact_permission')

def call(kind, name, request):
    client = node.create_client(kind, name)
    assert client.wait_for_service(timeout_sec=10), name
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=30)
    assert future.done(), name
    result = future.result()
    node.destroy_client(client)
    return result

def scene():
    req = GetPlanningScene.Request()
    req.components.components = (PlanningSceneComponents.ALLOWED_COLLISION_MATRIX |
                                  PlanningSceneComponents.WORLD_OBJECT_GEOMETRY)
    return call(GetPlanningScene, '/get_planning_scene', req).scene

def permission(phase):
    return call(ConfigureContact, '/space/configure_contact', ConfigureContact.Request(phase=phase))

def entry(acm, a, b):
    # MoveIt omits an all-false row when serializing its ACM.
    if a not in acm.entry_names or b not in acm.entry_names:
        assert a not in acm.default_entry_names and b not in acm.default_entry_names
        return False
    return acm.entry_values[acm.entry_names.index(a)].enabled[acm.entry_names.index(b)]

def faces(objects):
    return sum(len(m.triangles) for o in objects for m in o.meshes)

report = {}
assert not permission('insertion').success
acquired = call(Trigger, '/space/prepare_contact_scene', Trigger.Request())
assert acquired.success, acquired.message
try:
    before = scene()
    measured = next(o for o in before.world.collision_objects if o.id == 'measured/work_zone')
    mesh = next(m for m in measured.meshes if m.triangles)
    vertices = np.array([[mesh.vertices[i].x, mesh.vertices[i].y, mesh.vertices[i].z]
                         for i in mesh.triangles[len(mesh.triangles)//2].vertex_indices])
    mesh_pose = measured.mesh_poses[measured.meshes.index(mesh)]
    q, pos = mesh_pose.orientation, mesh_pose.position
    vertices = vertices @ quat_to_mat(q.x, q.y, q.z, q.w).T + [pos.x,pos.y,pos.z]
    q, pos = measured.pose.orientation, measured.pose.position
    vertices = vertices @ quat_to_mat(q.x, q.y, q.z, q.w).T + [pos.x,pos.y,pos.z]
    # A recorded sensor triangle plus one machine-representation unit, no grasp tuning.
    low, high = np.nextafter(vertices.min(axis=0), -np.inf), np.nextafter(vertices.max(axis=0), np.inf)
    dimensions = np.repeat(np.linalg.norm(high-low), 3)
    request = ConfigureContact.Request(phase='register', evidence_ref='live_measured_triangle')
    request.region.header.frame_id = measured.header.frame_id
    request.region.pose.position.x, request.region.pose.position.y, request.region.pose.position.z = map(float, (low+high)/2)
    request.dimensions.x, request.dimensions.y, request.dimensions.z = map(float, dimensions*2)
    result = call(ConfigureContact, '/space/configure_contact', request)
    assert result.success, result.evidence_json
    report['register'] = json.loads(result.evidence_json)
    assert not call(ConfigureContact, '/space/configure_contact', request).success
    for phase in ('endpoint_check', 'revoke', 'insertion', 'revoke'):
        result = permission(phase)
        assert result.success, result.evidence_json
        current = scene()
        acm = current.allowed_collision_matrix
        allowed = phase in ('endpoint_check', 'insertion')
        for name in acm.entry_names:
            assert entry(acm, 'measured/contact', name) == (allowed and name in GripperGeometry().contact_links), (phase, name)
        for a in before.allowed_collision_matrix.entry_names:
            for b in before.allowed_collision_matrix.entry_names:
                assert entry(acm, a, b) == entry(before.allowed_collision_matrix, a, b)
        objects = [o for o in current.world.collision_objects if o.id in ('measured/contact','measured/work_zone')]
        assert faces(objects) == faces([measured])
        report.setdefault('phases', []).append({'phase':phase, 'triangles_preserved':faces(objects), 'acm_scope_exact':True})
finally:
    released = call(Trigger, '/space/release_contact_scene', Trigger.Request())
    assert released.success, released.message
restored = scene()
assert restored.allowed_collision_matrix == before.allowed_collision_matrix
assert all(o.id != 'measured/contact' for o in restored.world.collision_objects)
report['release_restores_acm_and_removes_region'] = True
Path(sys.argv[1]).write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report), flush=True)
node.destroy_node()
rclpy.shutdown()
