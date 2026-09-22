"""G0 (docs/semantic_to_metric_manipulation_plan.md §7): wrist RGB-D views of the spares on the depot stand.

Drives the rover through the common capability boundary to the depot, docks at slot 0 (spare ORU) and slot 1 (cargo
crate), and from a pre-grasp pose moves the wrist camera through a grid of viewpoints around the item's handle (tool
horizontal-ish, jaws open, distance / height / yaw / pitch varied). For each view it saves what the robot has --
colour, registered depth, intrinsics, the camera and tool poses in `chassis_base_link`, the jaw -- and, in a separate
`truth.json` for scoring G1/G2 only, the simulator's handle positions in the camera frame. A snapshot of the
simulation at each dock is saved for later G3 trials.

Run as a D0 check on a Mission B graph with the boundary:
    D0_CAPABILITY_SERVER=1 D0_CHECK=../../perception/record_rgbd.py G0_OUT=artifacts/perception/g0 \
    setsid nohup experiments/launch/lunar_base_d0/run_d0.sh <log> > <log>/runner.out 2>&1 < /dev/null &
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launch/lunar_base_d0"))
from d0_common import *  # noqa: E402,F401,F403
import cv2  # noqa: E402
from rclpy.qos import qos_profile_sensor_data  # noqa: E402
from sensor_msgs.msg import CameraInfo, Image  # noqa: E402
from space_harness_msgs.action import ExecuteCapability  # noqa: E402

OUT = Path(os.environ.get("G0_OUT", "artifacts/perception/g0")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
cap_client = ActionClient(n, ExecuteCapability, "/space/capability/execute")
assert cap_client.wait_for_server(timeout_sec=120), "boundary not up"
latest = {}
n.create_subscription(Image, "/openral/cameras/wrist/image", lambda m: latest.__setitem__("rgb", m), qos_profile_sensor_data)
n.create_subscription(Image, "/openral/cameras/wrist_depth/image", lambda m: latest.__setitem__("depth", m), qos_profile_sensor_data)
n.create_subscription(CameraInfo, "/openral/cameras/wrist/camera_info", lambda m: latest.__setitem__("info", m), qos_profile_sensor_data)
snap_pub = n.create_publisher(String, "/srb/envs/snapshot", 10)
snap_done = []
n.create_subscription(String, "/srb/envs/snapshot/done", lambda m: snap_done.append(m.data), 10)


def cap(name, **args):
    f = cap_client.send_goal_async(ExecuteCapability.Goal(capability=name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f, timeout_sec=60)
    rf = f.result().get_result_async()
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.1)
    r = rf.result().result
    return dict(capability=name, success=r.success, failure_reason=r.failure_reason[:200])


def snapshot(path):
    p, yaw, _ = est_pose()
    path.with_suffix(".json").write_text(json.dumps(dict(x=float(p[0]), y=float(p[1]), yaw=float(yaw), sim_t=sim["t"])))
    snap_done.clear()
    snap_pub.publish(String(data=json.dumps(dict(op="save", path=str(path)))))
    while not snap_done:
        spin(0.1)
    return {"snapshot": str(path)}


def T(p, R):
    M = np.eye(4)
    M[:3, :3], M[:3, 3] = R, p
    return M


def tool_R(theta, psi):
    """Tool +Z pointing away from the rover's rear (-x), pitched down by theta and yawed by psi; jaw axis horizontal."""
    d = np.array([-math.cos(theta) * math.cos(psi), -math.cos(theta) * math.sin(psi), -math.sin(theta)])
    x = np.cross([0.0, 0.0, 1.0], d)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(d, x), d], axis=1)


def capture(view_id, item, params):
    t_settle = sim["t"]
    while sim["t"] - t_settle < 1.0:
        spin(0.1)
    stamp0 = sim["t"]
    latest.pop("rgb", None), latest.pop("depth", None)
    while "rgb" not in latest or "depth" not in latest:
        spin(0.05)
    m, dm, info = latest["rgb"], latest["depth"], latest["info"]
    img = np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1)
    bgr = cv2.cvtColor(img, {"rgb8": cv2.COLOR_RGB2BGR, "rgba8": cv2.COLOR_RGBA2BGR}[m.encoding])
    depth = np.frombuffer(dm.data, np.float32).reshape(dm.height, dm.width)
    while not buf.can_transform("chassis_base_link", m.header.frame_id, Time.from_msg(m.header.stamp)):  # the frame can be a TF tick ahead
        spin(0.02)
    tr = buf.lookup_transform("chassis_base_link", m.header.frame_id, Time.from_msg(m.header.stamp)).transform
    R_cam = quat_to_mat(tr.rotation.x, tr.rotation.y, tr.rotation.z, tr.rotation.w)
    p_cam = np.array([tr.translation.x, tr.translation.y, tr.translation.z])
    p_tcp, R_tcp = tf("chassis_base_link", "tcp_frame")
    d = OUT / view_id
    d.mkdir(exist_ok=True)
    cv2.imwrite(str(d / "rgb.png"), bgr)
    np.save(d / "depth.npy", depth)
    meta = dict(view=view_id, item_slot=item, params=params, K=list(info.k), width=m.width, height=m.height,
                camera_frame=m.header.frame_id, stamp=m.header.stamp.sec + m.header.stamp.nanosec * 1e-9,
                T_base_camera=T(p_cam, R_cam).tolist(), T_base_tcp=T(p_tcp, R_tcp).tolist(), jaw_rad=round(float(jaw.get("q", -1)), 4))
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    # evaluator-only: handle points in this camera's frame, through the rover's true pose
    pb, _, Rb = truth_pose()
    Rwc, pwc = Rb @ R_cam, pb + Rb @ p_cam
    truth = {name: dict(handle_camera=(Rwc.T @ (handle_pos(name) - pwc)).round(4).tolist(), handle_world=handle_pos(name).round(4).tolist())
             for name in ("spare_oru", "spare_crate")}
    tp = OUT / "truth.json"
    all_truth = json.loads(tp.read_text()) if tp.exists() else {}
    all_truth[view_id] = truth
    tp.write_text(json.dumps(all_truth, indent=1))
    return dict(view=view_id, sim_wait_s=round(sim["t"] - stamp0, 2), handle_camera={k: v["handle_camera"] for k, v in truth.items()})


def views(slot, item, handle_rover):
    """Viewpoints around a handle seen from the rover: distance along the tool axis, pitch, yaw, lateral / height shifts."""
    grid = [(dist, th, ps, lat, up)
            for dist in (0.18, 0.28, 0.40)
            for th, ps in ((0, 0), (15, 0), (30, 0), (10, -15), (10, 15))
            for lat, up in ((0.0, 0.0),)]
    grid += [(0.28, 10, 0, lat, up) for lat, up in ((0.08, 0.0), (-0.08, 0.0), (0.0, 0.08), (0.0, -0.06))]
    grid += [(0.22, 20, 0, 0.05, 0.05), (0.35, 25, -10, -0.05, 0.10), (0.15, 0, 0, 0.0, 0.0)]
    for i, (dist, th, ps, lat, up) in enumerate(grid):
        R = tool_R(math.radians(th), math.radians(ps))
        p = np.asarray(handle_rover) - R[:, 2] * dist + np.array([0.0, lat, up])
        params = dict(dist=dist, pitch_deg=th, yaw_deg=ps, lateral=lat, up=up)
        r = run(f"view {slot} {i}", lambda: cap("move_ee_to_pose", position=p.tolist(), orientation_xyzw=mat_to_quat(R), tolerance_m=0.012,
                                               max_linear_speed_m_s=0.08, timeout_s=30.0))
        if r and r["success"]:
            log("VIEW", **capture(f"{item}_{i:02d}", slot, params))
        else:
            D0_FAILED.append((slot, i, params))


D0_FAILED = []
os.environ["D0_CONTINUE_ON_FAIL"] = "1"
ROAD_EAST_LEG = (6.0, -6.0)
ITEMS = os.environ.get("G0_ITEMS", "oru,crate").split(",")  # attach to a held graph for one item: G0_ITEMS=crate
run("release", lambda: cap("release"))
run("arm ready", lambda: cap("arm_ready"))
run("stow", lambda: cap("stow"))
if "D0_ATTACH" not in os.environ:
    run("road east leg", lambda: cap("navigate_to_pose", x=ROAD_EAST_LEG[0], y=ROAD_EAST_LEG[1], yaw=-1.5708))
for slot, item in [(s, i) for s, i in (("depot_stand/slot_0", "oru"), ("depot_stand/slot_1", "crate")) if i in ITEMS]:
    run(f"navigate {slot}", lambda: cap("navigate_to_feature", feature=slot))
    run(f"dock {slot}", lambda: cap("dock_at_feature", feature=slot))
    run(f"snapshot docked {slot}", lambda: snapshot(OUT / f"docked_{item}.pt"))
    run("arm ready", lambda: cap("arm_ready"))
    run("moveit pre-grasp", lambda: cap("plan_ee_to_feature", feature=slot, offset_m=0.18, lift_m=0.47, orientation="grip"))
    obj = "spare_oru" if item == "oru" else "spare_crate"
    pb, _, Rb = truth_pose()
    handle_rover = Rb.T @ (handle_pos(obj) - pb)  # evaluator knowledge, used only to place the recording viewpoints
    log("HANDLE", item=item, rover=handle_rover.round(3).tolist())
    views(slot, item, handle_rover)
    run("arm ready", lambda: cap("arm_ready"))
    run("stow", lambda: cap("stow"))
    run(f"undock {slot}", lambda: cap("dock_at_feature", feature=slot, standoff_m=1.0, approach_m=0.8))
log("RESULT", failed_views=D0_FAILED, saved=sorted(p.name for p in OUT.iterdir() if p.is_dir()))
