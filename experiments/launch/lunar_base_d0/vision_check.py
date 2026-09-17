"""Vision-guided contact check (Phase E: replaces the simulator-truth arm targets): can the wrist camera + VLM +
depth-guided servo press a button and bring the jaws to a bail handle, through the common boundary only?

PDU-2 (faulted in `covered`): dock by the survey, READY, MoveIt near the surveyed button, approach_target on the
button described in words, push with move_tool, retract; then the evaluator compares the RGB-D target with
the button's surveyed position in `srb/world` and reads the verifier's press count. Depot: dock at slot 0, READY,
MoveIt near the slot, approach_target on the ORU's handle (grip), jaws open, slide in, grasp, lift -- evaluated by the
jaw and the handle's truth height. Truth is the evaluator's only.
Run with D0_CAPABILITY_SERVER=1 on a scene with cameras.
"""
from d0_common import *  # noqa: F401,F403
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

cap_client = ActionClient(n, ExecuteCapability, "/space/capability/execute")
query_client = n.create_client(QueryCapability, "/space/capability/query")
assert cap_client.wait_for_server(timeout_sec=120) and query_client.wait_for_service(timeout_sec=60), "boundary not up"


def cap(name, **args):
    f = cap_client.send_goal_async(ExecuteCapability.Goal(capability=name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f, timeout_sec=60)
    rf = f.result().get_result_async()
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.1)
    r = rf.result().result
    return dict(capability=name, success=r.success, failure_reason=r.failure_reason[:200], evidence=json.loads(r.evidence_json or "{}"))


def ask(query_name, **args):
    f = query_client.call_async(QueryCapability.Request(query=query_name, args_json=json.dumps(args)))
    while not f.done():  # a VLM localisation with agreement checks can take minutes of wall time
        rclpy.spin_once(n, timeout_sec=0.1)
    r = f.result()
    return {"success": r.success, **(json.loads(r.value_json) if r.success else {"failure_reason": r.failure_reason})}


def target_error(res, world_point):
    """Evaluator: the RGB-D target (rover frame) vs a truth point in srb/world."""
    if res is None or "target_rover" not in res["evidence"]:  # step not selected (D0_STEPS) or target never reached
        return {}
    ev = res["evidence"]
    if "target_rover" not in ev:
        return {}
    pb, _, Rb = truth_pose()  # the rover's true pose: the target error must not include the localization error
    p = Rb @ np.array(ev["target_rover"]) + pb
    return {"target_err_m": round(float(np.linalg.norm(p - np.array(world_point))), 4), "depths_m": [v.get("depth_m") for v in ev.get("views", []) if "depth_m" in v],
            "correction_m": ev.get("correction_m"), "views": ev.get("views")}


BUTTON = IX["points"]["pdu_2_panel/press"]["xyz"]
run("navigate pdu_2", lambda: cap("navigate_to_feature", feature="pdu_2_panel/press"))
run("dock pdu_2", lambda: cap("dock_at_feature", feature="pdu_2_panel/press"))
run("close jaws", lambda: {**cap("grasp"), "success": True})
run("arm ready", lambda: cap("arm_ready"))
run("moveit near button", lambda: cap("plan_ee_to_feature", feature="pdu_2_panel/press", offset_m=0.20, orientation="grip"))  # camera level
run("locate button", lambda: ask("locate_in_view", camera="wrist", target="the red push button: the lower of the two red domes on the yellow panel (the upper one is the glowing status lamp)"))
res = run("approach button", lambda: cap("approach_target", target="the red push button: the lower of the two red domes on the yellow panel (the upper one is the glowing status lamp)", standoff_m=0.05, orientation="grip"))
log("TARGET", what="button", **target_error(res, BUTTON))
run("push", lambda: {**cap("move_tool", forward_m=0.065, max_linear_speed_m_s=0.03, timeout_s=20.0), "mission": dict(mission)})
run("retract", lambda: {**cap("move_tool", forward_m=-0.12, max_linear_speed_m_s=0.08), "mission": dict(mission)})
run("stow", lambda: cap("stow"))
run("undock", lambda: cap("dock_at_feature", feature="pdu_2_panel/press", standoff_m=1.5, approach_m=0.8))
ROAD_EAST_LEG = (6.0, -6.0)
run("road east leg", lambda: cap("navigate_to_pose", x=ROAD_EAST_LEG[0], y=ROAD_EAST_LEG[1], yaw=-1.5708))
run("navigate slot_0", lambda: cap("navigate_to_feature", feature="depot_stand/slot_0"))
run("dock slot_0", lambda: cap("dock_at_feature", feature="depot_stand/slot_0"))
run("open jaws", lambda: cap("release"))
run("arm ready (depot)", lambda: cap("arm_ready"))
run("moveit above slot", lambda: cap("plan_ee_to_feature", feature="depot_stand/slot_0", offset_m=0.18, lift_m=0.47, orientation="grip"))  # F51 b7's reachable pre-grasp
HANDLE = "the narrow vertical neck of the grey T-shaped carry handle on top of the gold box, just below its crossbar"
run("locate handle", lambda: ask("locate_in_view", camera="wrist", target=HANDLE))
res = run("approach handle", lambda: cap("approach_target", target=HANDLE, standoff_m=0.12, orientation="grip"))
log("TARGET", what="oru handle", **target_error(res, handle_pos("spare_oru")))
run("slide in", lambda: cap("move_tool", forward_m=0.135, max_linear_speed_m_s=0.04, timeout_s=25.0))
run("grasp", lambda: {**cap("grasp"), "jaw_rad": round(float(jaw.get("q", -1)), 3)})
run("lift", lambda: {**cap("move_tool", up_m=0.10, max_linear_speed_m_s=0.05), "oru_handle_z": round(float(handle_pos("spare_oru")[2]), 3)})
log("RESULT", mission=dict(mission), oru_handle=[round(float(v), 3) for v in handle_pos("spare_oru")])
