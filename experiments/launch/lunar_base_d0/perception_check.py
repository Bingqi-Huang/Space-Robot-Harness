"""Relative perception check (Phase E, replaces the truth stand-ins): does the fiducial pipeline see the targets, and
how far are its carrier poses from simulator truth?

Drives through the common boundary to where the arm works -- PDU-2's panel (dock, READY, the pre-press pose), then the
depot stand (dock, READY) -- and at each stop logs every perceived instance against truth: panel instances against
their surveyed pose in `srb/world`, movable objects against their simulator pose. Truth is the evaluator's only.
Run with D0_CAPABILITY_SERVER=1 D0_PERCEPTION=1 on a scene with cameras.
"""
from d0_common import *  # noqa: F401,F403
from rclpy.qos import QoSDurabilityPolicy, QoSProfile
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

sys.path.insert(0, str(HERE / "../../../openral_ext/perception"))
from fiducial_node import quat_to_mat, surveyed_instances  # noqa: E402

perceived = {}
n.create_subscription(String, "/space/perception/instances", lambda m: perceived.update(json.loads(m.data)),
                      QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
cap_client = ActionClient(n, ExecuteCapability, "/space/capability/execute")
query_client = n.create_client(QueryCapability, "/space/capability/query")
assert cap_client.wait_for_server(timeout_sec=120) and query_client.wait_for_service(timeout_sec=60), "boundary not up"
SURVEY = surveyed_instances()


def cap(name, **args):
    f = cap_client.send_goal_async(ExecuteCapability.Goal(capability=name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f, timeout_sec=60)
    rf = f.result().get_result_async()
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.1)
    r = rf.result().result
    return dict(capability=name, success=r.success, failure_reason=r.failure_reason[:160])


def query(name, **args):
    f = query_client.call_async(QueryCapability.Request(query=name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f, timeout_sec=30)
    return json.loads(f.result().value_json) if f.result().success else {"failed": f.result().failure_reason}


def compare(where):
    spin(3.0)
    out = {}
    for inst, s in perceived.items():
        p_odom, R_odom = np.array(s["position"]), quat_to_mat(*s["quat_xyzw"])
        t, R = tf("srb/world", "odom")  # odom in truth (evaluator): perceived pose -> world
        pw, Rw = R @ p_odom + t, R @ R_odom
        if inst in SURVEY:
            ref = SURVEY[inst]["T_map"]
        else:
            ref = np.eye(4)
            ref[:3, 3], ref[:3, :3] = tf("srb/world", f"srb/env0/lb_{inst}")
        yaw = math.degrees(math.atan2(Rw[1, 0], Rw[0, 0]) - math.atan2(ref[1, 0], ref[0, 0]))
        out[inst] = dict(err_m=round(float(np.linalg.norm(pw - ref[:3, 3])), 4), err_xy_m=round(float(np.linalg.norm(pw[:2] - ref[:2, 3])), 4),
                         yaw_err_deg=round((yaw + 180) % 360 - 180, 2), camera=s["camera"], tag=s["tag"], range_m=s["range_m"])
    log("PERCEPTION", where=where, instances=out)


run("navigate pdu_2 panel", lambda: cap("navigate_to_feature", feature="pdu_2_panel/press"))
run("dock pdu_2 panel", lambda: cap("dock_at_feature", feature="pdu_2_panel/press"))
compare("docked, arm stowed")
run("arm ready", lambda: cap("arm_ready"))
compare("arm ready")
run("plan pre-press", lambda: cap("plan_ee_to_feature", feature="pdu_2_panel/press", offset_m=0.12))
compare("pre-press")
run("locate press", lambda: {"success": True, **query("locate_feature", name="pdu_2_panel/press")})
run("stow", lambda: cap("stow"))
run("undock", lambda: cap("dock_at_feature", feature="pdu_2_panel/press", standoff_m=1.5, approach_m=0.8))
run("navigate depot", lambda: cap("navigate_to_pose", x=6.0, y=-6.0, yaw=-1.5708))
run("navigate depot slot_0", lambda: cap("navigate_to_feature", feature="depot_stand/slot_0"))
run("dock depot slot_0", lambda: cap("dock_at_feature", feature="depot_stand/slot_0"))
run("arm ready (depot)", lambda: cap("arm_ready"))
compare("depot, arm ready")
run("locate ORU", lambda: {"success": True, **query("locate_feature", name="spare_oru")})
log("RESULT", perceived=sorted(perceived))
