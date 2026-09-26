"""Development check of `scan_label` (openral_ext/scan_label.py; docs/heldout_design.md §6, preflight checklist G1).

The capability is registered with no method, so this script calls the shared implementation directly, supplying the
robot through the same paths the boundary uses: the drive and the dock are the boundary's own `navigate_to_feature` /
`dock_at_feature` (3 attempts each, as every method gets), the arm's moves its `move_joints` / `stow` (the posture
skill's planned path), inverse kinematics MoveIt's collision-checked `/compute_ik`. Only afterwards does the evaluator's
truth say which serial stands at each support, to judge the reading (evaluation only; the scan never sees it).

    SCAN_SUPPORTS="depot_stand/slot_0,pdu_1_bay/tray" D0_CAPABILITY_SERVER=1 D0_CHECK=scan_label_check.py + the scenario

zxing-cpp must be importable (it is not in the openral venv yet): PYTHONPATH=<dir with zxingcpp>.
"""
import sys

from moveit_msgs.srv import GetPositionIK
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image

from d0_boundary import cap
from d0_common import *  # noqa: F401,F403

sys.path.insert(0, str(HERE.parents[2]))
from openral_ext.scan_label import scan  # noqa: E402
from openral_rskill._eye_in_hand import image_to_bgr  # noqa: E402

SUPPORTS = [s for s in os.environ["SCAN_SUPPORTS"].split(",") if s]
ATTEMPTS = 3
#: where the lid meets the handle column, above the support's surveyed point: the catalogued ORU's top (every ORU has
#: the same envelope; the Experiment II items are ORUs, heldout_design §6)
ORU = next(o for o in IX["objects"].values() if o["item"].startswith("orbital replacement unit"))
ITEM_TOP_M = round(ORU["top_z"] - IX["points"][ORU["support"]]["xyz"][2], 4)

wrist = {}
n.create_subscription(Image, "/openral/cameras/wrist/image", lambda m: wrist.__setitem__("img", m), qos_profile_sensor_data)
n.create_subscription(CameraInfo, "/openral/cameras/wrist/camera_info", lambda m: wrist.__setitem__("info", m), qos_profile_sensor_data)
ik_client = n.create_client(GetPositionIK, "/compute_ik")
assert ik_client.wait_for_service(timeout_sec=60), "MoveIt's IK service is not up"


def stamp_of(m):
    return m.header.stamp.sec + m.header.stamp.nanosec * 1e-9


class RobotIO:
    """The robot as `scan_label.scan` reaches it."""

    def tf(self, target, source):
        p, R = tf(target, source)
        T = np.eye(4)
        T[:3, :3], T[:3, 3] = R, p
        return T

    def arm_q(self):
        spin(0.1)
        return [arm[f"joint{i}"] for i in range(1, 8)]

    def ik(self, p, R, seed):
        req = GetPositionIK.Request()
        r = req.ik_request
        r.group_name, r.ik_link_name, r.avoid_collisions = "rm_group", "tcp_frame", True
        r.robot_state.joint_state.name = [f"joint{i}" for i in range(1, 8)]
        r.robot_state.joint_state.position = [float(v) for v in seed]
        r.robot_state.is_diff = True
        r.pose_stamped.header.frame_id = "chassis_base_link"
        pp = r.pose_stamped.pose
        pp.position.x, pp.position.y, pp.position.z = (float(v) for v in p)
        pp.orientation.x, pp.orientation.y, pp.orientation.z, pp.orientation.w = mat_to_quat(R)
        r.timeout.nanosec = 100_000_000
        f = ik_client.call_async(req)
        rclpy.spin_until_future_complete(n, f)
        res = f.result()
        if res.error_code.val != 1:
            return None
        js = res.solution.joint_state
        return [float(js.position[list(js.name).index(f"joint{i}")]) for i in range(1, 8)]

    def move_joints(self, q):
        r = cap("move_joints", joint_targets=[float(v) for v in q])
        log("ARM", capability="move_joints", success=r["success"], reason=r["failure_reason"][:300], sim_s=r["sim_s"])
        return r["success"], r["failure_reason"]

    def fold(self):
        r = cap("stow")
        log("ARM", capability="stow", success=r["success"], reason=r["failure_reason"][:300], sim_s=r["sim_s"])
        return r["success"], r["failure_reason"]

    def wrist_frame(self, after):
        while "info" not in wrist or "img" not in wrist or stamp_of(wrist["img"]) <= after:
            spin(0.05)
        m = wrist["img"]
        return image_to_bgr(m), np.array(wrist["info"].k, float).reshape(3, 3), m.header.frame_id, stamp_of(m)

    def now(self):
        spin(0.01)
        return sim["t"]

    def wait(self, sim_s):
        t = sim["t"]
        while sim["t"] - t < sim_s:
            spin(0.05)


def serials_at(support):
    """Evaluator only: the serials of the catalogued items whose base stands on this support now (truth)."""
    xy = np.array(IX["points"][support]["xyz"][:2])
    out = []
    for name, o in IX["objects"].items():
        if "serial" not in o:
            continue
        p, _ = tf("srb/world", f"srb/env0/lb_{name}")
        if np.linalg.norm(p[:2] - xy) < 0.25 and abs(p[2] - IX["points"][support]["xyz"][2]) < 0.1:
            out.append(o["serial"])
    return sorted(out)


io = RobotIO()
for support in SUPPORTS:
    for name, args in (("navigate_to_feature", {"feature": support}), ("dock_at_feature", {"feature": support, "standoff_m": 0.0})):
        for attempt in range(1, ATTEMPTS + 1):
            r = cap(name, **args)
            log("RESULT", capability=name, args=args, attempt=attempt, success=r["success"], reason=r["failure_reason"][:300],
                sim_s=r["sim_s"], wall_s=r["wall_s"])
            if r["success"]:
                break
        else:
            break
    else:
        pt = IX["points"][support]
        res = scan(io, support, pt["xyz"], pt["normal"], ITEM_TOP_M,
                   Path(os.environ["D0_LOG"]) / "evidence" / f"scan_label_{support.replace('/', '_')}_{int(sim['t'])}")
        expected = serials_at(support)
        log("SCAN", support=support, success=res["success"], reason=res["failure_reason"], serials=res["serials"],
            expected=expected, match=res["serials"] == expected, plates=res["plates"], evidence=res["evidence"])
        continue
    log("STOPPED", at=support)
    break
spin(3.0)
log("CHAIN_DONE")
