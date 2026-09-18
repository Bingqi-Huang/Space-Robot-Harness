"""G3 (plan v4 §7): `pick` live, one call per trial, with the item's placement and the dock perturbed.

Each trial restores the simulation docked at the depot (G0's `docked_oru.pt`) with the spare ORU moved on its slot
(dx, dy in m, dyaw in deg) and optionally the rover shifted (the dock perturbed, AMCL re-seeded with the same shift),
calls the common boundary once -- pick("the spare ORU ...", "its carry handle") -- and scores it as the evaluator:
the handle's truth height before/after, the TCP-handle distance, the jaw; plus Ours' independent `item_held`
verification on the returned evidence, and the stage the skill reports. Truth never reaches the robot.

    D0_CAPABILITY_SERVER=1 D0_HOLD=1 D0_CHECK=../../perception/g3_pick.py G3_TRIALS="0,0,0,0;0.08,0,20,0" run_d0.sh <log>
    (a trial is dx,dy,dyaw_deg,rover_dx; attach_d0.sh on a held graph runs further trials)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launch/lunar_base_d0"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from d0_common import *  # noqa: E402,F401,F403
import torch  # noqa: E402
import yaml  # noqa: E402
from geometry_msgs.msg import PoseWithCovarianceStamped  # noqa: E402
from space_harness_msgs.action import ExecuteCapability  # noqa: E402
from space_runtime.verification import verify  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
BASE_SNAP = REPO / "artifacts/perception/g0/docked_oru.pt"
TARGET = "the spare ORU (orbital replacement unit, a gold MLI-covered box)"
PART = "its carry handle"
LOG = Path(os.environ["D0_LOG"])
cfg = yaml.safe_load((REPO / "configs/space_runtime.yaml").read_text())["verification"]
cap_client = ActionClient(n, ExecuteCapability, "/space/capability/execute")
assert cap_client.wait_for_server(timeout_sec=120), "boundary not up"
snap_pub = n.create_publisher(String, "/srb/envs/snapshot", 10)
snap_done = []
n.create_subscription(String, "/srb/envs/snapshot/done", lambda m: snap_done.append(m.data), 10)
ip_pub = n.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
while snap_pub.get_subscription_count() == 0 or ip_pub.get_subscription_count() == 0:
    spin(0.5)


def restore(dx, dy, dyaw_deg, rover_dx):
    s = torch.load(BASE_SNAP, map_location="cpu")
    o = s["rigid_objects"]["lb_spare_oru"]
    o[0, 0] += dx
    o[0, 1] += dy
    w, x, y, z = o[0, 3:7].tolist()
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)) + math.radians(dyaw_deg)
    o[0, 3:7] = torch.tensor([math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)])
    est = json.loads(BASE_SNAP.with_suffix(".json").read_text())
    for k, a in s["articulations"].items():  # the rover shifted along the world x axis (across the dock corridor)
        a["root"][0, 0] += rover_dx
    est["x"] += rover_dx
    path = LOG / f"trial_{dx}_{dy}_{dyaw_deg}_{rover_dx}.pt"
    torch.save(s, path)
    snap_done.clear()
    snap_pub.publish(String(data=json.dumps(dict(op="restore", path=str(path)))))
    while not snap_done:
        spin(0.1)
    ip = PoseWithCovarianceStamped()
    ip.header.frame_id = "map"
    ip.pose.pose.position.x, ip.pose.pose.position.y = est["x"], est["y"]
    ip.pose.pose.orientation.z, ip.pose.pose.orientation.w = math.sin(est["yaw"] / 2), math.cos(est["yaw"] / 2)
    ip.pose.covariance[0] = ip.pose.covariance[7] = ip.pose.covariance[35] = 0.02 ** 2
    while True:
        ip_pub.publish(ip)
        t = sim["t"]
        while sim["t"] - t < 3.0:
            spin(0.2)
        p, _, _ = est_pose()
        if math.hypot(p[0] - est["x"], p[1] - est["y"]) < 0.03:
            return


def cap(name, **args):
    f = cap_client.send_goal_async(ExecuteCapability.Goal(capability=name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f, timeout_sec=60)
    rf = f.result().get_result_async()
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.1)
    r = rf.result().result
    return dict(success=r.success, failure_reason=r.failure_reason, evidence=json.loads(r.evidence_json or "{}"))


for spec in os.environ.get("G3_TRIALS", "0,0,0,0").split(";"):
    dx, dy, dyaw, rover_dx = (float(v) for v in spec.split(","))
    restore(dx, dy, dyaw, rover_dx)
    # the snapshot was taken at the old work pose; dock again so the rover stands where dock_at_feature puts it now
    d = cap("dock_at_feature", feature="depot_stand/slot_0")
    log("DOCK", **{k: d[k] for k in ("success", "failure_reason")}, **base_err(IX["work_poses"]["depot_stand/slot_0"]["xy"], math.radians(IX["work_poses"]["depot_stand/slot_0"]["yaw_deg"])))
    h0 = handle_pos("spare_oru")
    tcp0 = tcp_pose()[0]
    base0, yaw0, R0 = truth_pose()
    sim0, wall0 = sim["t"], time.time()
    # evaluator-only: sample the item's truth pose while the skill runs, so a push can be put beside the skill's stages
    track, stop = [], []

    def sample():
        # reads the TF buffer the main thread fills; it must not spin the node itself at all (rclpy is not re-entrant:
        # a second thread spinning the same node corrupts its wait set, and the next action goal never completes)
        last = h0
        while not stop:
            time.sleep(0.2)
            h = handle_pos("spare_oru", spin=False)
            if h is not None and float(np.linalg.norm(h - last)) > 0.01:
                track.append({"sim_t": round(sim["t"] - sim0, 1), "handle": [round(float(v), 3) for v in h],
                              "moved_m": round(float(np.linalg.norm(h - last)), 3)})
                last = h

    import threading
    th = threading.Thread(target=sample, daemon=True)
    th.start()
    r = cap("pick", target=TARGET, part=PART)
    stop.append(True)
    th.join(timeout=2)
    spin(2.0)
    h1 = handle_pos("spare_oru")
    tcp_w, _ = tcp_pose()
    base1, yaw1, R1 = truth_pose()
    pitch = lambda R: math.degrees(math.atan2(-R[2, 0], math.hypot(R[2, 1], R[2, 2])))  # noqa: E731
    sk = r["evidence"].get("skill", {})
    effects = verify("pick", {"target": TARGET, "part": PART}, r["evidence"], cfg)
    log("TRIAL", perturbation=dict(dx=dx, dy=dy, dyaw_deg=dyaw, rover_dx=rover_dx), success=r["success"], failure_reason=r["failure_reason"][:300],
        stage=sk.get("failed_stage") or sk.get("stage"), attempts=[a.get("outcome") for a in sk.get("attempts", [])],
        vlm=(sk.get("select") or {}).get("answers"), jaw=round(float(jaw.get("q", -1)), 3),
        handle_rise_m=round(float(h1[2] - h0[2]), 3), handle_moved_xy_m=round(float(np.linalg.norm(h1[:2] - h0[:2])), 3),
        tcp_to_handle_m=round(float(np.linalg.norm(tcp_w - h1)), 3), item_held=effects[-1] if effects else None,
        tcp_rise_world_m=round(float(tcp_w[2] - tcp0[2]), 3), rover_moved_m=round(float(np.linalg.norm(base1[:2] - base0[:2])), 3),
        rover_sank_m=round(float(base1[2] - base0[2]), 3), rover_pitch_change_deg=round(pitch(R1) - pitch(R0), 2),
        tcp_minus_handle_before=[round(float(v), 3) for v in (tcp0 - h0)], tcp_minus_handle_after=[round(float(v), 3) for v in (tcp_w - h1)],
        item_track=track,
        sim_s=round(sim["t"] - sim0, 1), wall_s=round(time.time() - wall0), evidence_dir=sk.get("evidence_dir"))
log("RESULT", done=True)
