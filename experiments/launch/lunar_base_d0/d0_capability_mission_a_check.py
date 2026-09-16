"""§21.4 proof: Mission A `covered` driven ONLY through the common capability boundary.

Every motion is a space_harness_msgs/ExecuteCapability call on /space/capability/execute and every target comes from
site knowledge (interaction points, in `map`) or a QueryCapability `locate_feature` (in the rover frame) -- the same
interface PLEXIL Commands/Lookups and Ours' tools use. The step sequence and parameters match
d0_mission_a_check.py, which dispatches the rSkills directly; equal verifier outcomes show the boundary adds no
behaviour. The evaluator side (verifier state, truth errors) comes from d0_common and never crosses the boundary.
Run with D0_CAPABILITY_SERVER=1.
"""
from d0_common import *  # noqa: F401,F403
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

cap_client = ActionClient(n, ExecuteCapability, "/space/capability/execute")
query_client = n.create_client(QueryCapability, "/space/capability/query")
assert cap_client.wait_for_server(timeout_sec=120) and query_client.wait_for_service(timeout_sec=60), "capability boundary not up"


def cap(name, deadline=0.0, **args):
    goal = ExecuteCapability.Goal(capability=name, args_json=json.dumps(args), deadline_s=float(deadline))
    t, sim0 = time.time(), sim["t"]
    f = cap_client.send_goal_async(goal)
    rclpy.spin_until_future_complete(n, f, timeout_sec=60)
    rf = f.result().get_result_async()
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.1)
    r = rf.result().result
    return dict(capability=name, success=r.success, failure_reason=r.failure_reason, failure_kind=r.failure_kind,
                evidence=json.loads(r.evidence_json or "{}"), wall_s=round(time.time() - t, 1), sim_s=round(sim["t"] - sim0, 1))


def query(name, **args):
    f = query_client.call_async(QueryCapability.Request(query=name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f, timeout_sec=10)
    r = f.result()
    assert r.success, r.failure_reason
    return json.loads(r.value_json)


def rover_tool_target(feature, offset_along_normal):
    """TCP target in the rover frame from a located feature: tool +Z into the surface, jaw axis vertical."""
    loc = query("locate_feature", name=feature)
    p, nrm = np.array(loc["position"]), np.array(loc["normal"])
    R = tool_frame(nrm[:2])
    return (p + np.array([nrm[0], nrm[1], 0.0]) / np.linalg.norm(nrm[:2]) * offset_along_normal).tolist(), mat_to_quat(R)


PDU = "pdu_2"
FEATURE = f"{PDU}_panel/press"
press = IX["points"][FEATURE]
p_press = np.array(press["xyz"])
wp, yaw_w, n_w = work_pose(p_press, press["normal"])
n3 = np.array([n_w[0], n_w[1], 0.0])
stage_xy, stage_yaw = staging(wp, yaw_w)
log("PLAN", boundary=True, pdu=PDU, work=[*wp.tolist()], contracts_probe=query("base_pose"))


def ee_step(offset, tol, **kw):
    pos, quat = rover_tool_target(FEATURE, offset)
    r = cap("move_ee_to_pose", position=pos, orientation_xyzw=quat, tolerance_m=tol, **kw)
    return {**r, "tcp_err_m": round(float(np.linalg.norm(tcp_pose()[0] - (p_press + n3 * offset))), 4)}


def moveit_step(offset):
    pos, quat = rover_tool_target(FEATURE, offset)
    r = cap("plan_ee_pose", position=pos, orientation_xyzw=quat, tolerance_m=0.01)
    spin(1.0)
    return {**r, "tcp_err_m": round(float(np.linalg.norm(tcp_pose()[0] - (p_press + n3 * offset))), 4)}


def close_jaws():
    r = cap("grasp")
    return {**r, "success": r["success"] or "fully-closed stroke" in r["failure_reason"]}


run("navigate_to_pose staging", lambda: {**cap("navigate_to_pose", x=float(stage_xy[0]), y=float(stage_xy[1]), yaw=float(stage_yaw)), **base_err(stage_xy, stage_yaw)})
run("dock_to_pose work", lambda: {**cap("dock_to_pose", x=float(wp[0]), y=float(wp[1]), yaw=float(yaw_w)), **base_err(wp, yaw_w)})
run("grasp (close jaws)", close_jaws)
run("move_joints READY", lambda: cap("move_joints", joint_targets=READY))
run("plan_ee_pose pre-press", lambda: moveit_step(0.12))
run("move_ee_to_pose pre-press", lambda: ee_step(0.12, 0.015))
run("move_ee_to_pose approach", lambda: ee_step(0.04, 0.01, max_linear_speed_m_s=0.05))
run("move_ee_to_pose press", lambda: {**ee_step(-0.01, 0.01, max_linear_speed_m_s=0.03, timeout_s=15.0), "mission": dict(mission)})
run("move_ee_to_pose retract", lambda: {**ee_step(0.12, 0.02, max_linear_speed_m_s=0.08), "mission": dict(mission)})
run("move_joints READY (unstow path)", lambda: cap("move_joints", joint_targets=READY, tolerance_rad=0.1))
run("stow", lambda: cap("stow", tolerance_rad=0.1))
run("dock_to_pose leave", lambda: cap("dock_to_pose", x=float(stage_xy[0]), y=float(stage_xy[1]), yaw=float(stage_yaw), approach_m=0.8))
run("navigate_to_pose dock", lambda: {**cap("navigate_to_pose", x=0.0, y=0.0, yaw=0.0), **base_err([0.0, 0.0], 0.0)})
# the boundary refuses what is off-contract instead of forwarding it
run("contract refusal probe", lambda: (lambda r: {**r, "success": (not r["success"]) and r["failure_kind"] == 20})(cap("dock_to_pose", x=1.0, y=2.0)))
spin(3.0)
log("RESULT", mission=dict(mission))
