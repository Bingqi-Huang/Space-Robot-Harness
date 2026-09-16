"""Phase D0 held-out capability check: Mission A `heldout_cover_obstruction` (closed-capability rule, §13.2).

A valid solution needs capabilities the covered case never used: grasp the service cover's bar, pull it off the
button, carry it to the PDU's spares shelf (base re-dock with the cover in the jaws), place and release it, then
the covered press. This script is a capability probe, not a method: the order is the oracle's (C4,
srb_mission_a_run.py `remove_cover`), every motion an ExecuteRskill dispatch. Run with
D0_SCENARIO=heldout_cover_obstruction. Helpers and readiness: d0_common.py.
"""
from d0_common import *  # noqa: F401,F403

PDU = mission.get("faulted_pdu", "pdu_2")
press = IX["points"][f"{PDU}_panel/press"]
p_press = np.array(press["xyz"])
wp, yaw_w, n_w = work_pose(p_press, press["normal"])
n3 = np.array([n_w[0], n_w[1], 0.0])
R_t = tool_frame(n_w)
sp = IX["points"][f"{PDU}_shelf/shelf"]
ns3 = np.array([sp["normal"][0], sp["normal"][1], 0.0])


def cover_handle():
    p, R = tf("srb/world", "srb/env0/lb_service_cover")
    return p + R @ np.array([0.057, 0.0, 0.26])  # the bar centre (oracle cover_handle)


def cover_state():
    return dict(covered=dict(mission.get("covered", {})), cover_to_tcp_m=round(float(np.linalg.norm(cover_handle() - tcp_pose()[0])), 3))


def close_jaws():
    return dispatch("grasp", {"mode": "close", "timeout_s": 8.0}, deadline=20)


h = cover_handle()
g = h - n3 * 0.035  # fingertips ~2 cm past the bar centre: the closed jaws cage the 25 mm bar (C4)
up = np.array([0.0, 0.0, 0.05])
s_pt = np.array(sp["xyz"])
shift = (s_pt - ns3 * 0.21) - (p_press - n3 * 0.092)
handle_t = h + np.array([shift[0], shift[1], s_pt[2] - IX["points"][f"{PDU}_panel/cover_rest"]["xyz"][2] + 0.01]) + ns3 * 0.02
wp_s, yaw_s, n_s = work_pose(handle_t, sp["normal"])
log("PLAN", pdu=PDU, cover_bar=h.tolist(), shelf_handle_target=handle_t.tolist(), work=[*wp.tolist()], work_shelf=[*wp_s.tolist()])

stage_xy, stage_yaw = staging(wp, yaw_w)
run("nav approach", lambda: {**nav(stage_xy, stage_yaw), **base_err(stage_xy, stage_yaw)})
run("dock panel", lambda: {**dock(wp, yaw_w), **base_err(wp, yaw_w)})
run("release (open)", lambda: dispatch("release", {"mode": "open", "timeout_s": 8.0}, deadline=20))
run("move_joints READY", lambda: dispatch("joints", {"joint_targets": READY, "timeout_s": 20.0}, deadline=40))
run("moveit cover pre", lambda: {**moveit(h + n3 * 0.12, R_t), "cover_moved_m": round(float(np.linalg.norm(cover_handle() - h)), 3)})
# targets re-perceived at step time: a MoveIt plan that knows only the rover can nudge the object it reaches for (F51)
run("servo cover pre", lambda: ee(cover_handle() + n3 * 0.12, R_t, tol=0.02))
run("servo cover approach", lambda: ee(cover_handle() - n3 * 0.035, R_t, tol=0.012, max_linear_speed_m_s=0.05))
run("grasp cover bar", lambda: {**close_jaws(), **cover_state()})
run("servo cover lift", lambda: {**ee(tcp_pose()[0] + up, R_t, tol=0.02, max_linear_speed_m_s=0.05), **cover_state()})
run("servo cover pull", lambda: {**ee(tcp_pose()[0] + n3 * 0.15, R_t, tol=0.02, max_linear_speed_m_s=0.05), **cover_state()})
run("dock leave (cover)", lambda: {**dock(stage_xy, stage_yaw, approach_m=0.8), **cover_state()})
stage_s, stage_s_yaw = staging(wp_s, yaw_s)
run("dock shelf (cover)", lambda: {**dock(wp_s, yaw_s), **base_err(wp_s, yaw_s), **cover_state()})
Rs = tool_frame(ns3[:2])
pre = handle_t + ns3 * 0.12 + np.array([0.0, 0.0, 0.05])
run("servo shelf pre", lambda: {**ee(pre, Rs, tol=0.02, max_linear_speed_m_s=0.05, timeout=40.0), **cover_state()})
run("servo shelf place", lambda: {**ee(handle_t, Rs, tol=0.015, max_linear_speed_m_s=0.04), **cover_state()})
run("release cover", lambda: dispatch("release", {"mode": "open", "timeout_s": 8.0}, deadline=20))
run("servo shelf retract", lambda: {**ee(handle_t + ns3 * 0.12, Rs, tol=0.02, max_linear_speed_m_s=0.05), **cover_state()})
run("move_joints READY (after place)", lambda: dispatch("joints", {"joint_targets": READY, "tolerance_rad": 0.1, "timeout_s": 30.0}, deadline=60))
run("dock panel again", lambda: {**dock(wp, yaw_w), **base_err(wp, yaw_w), **cover_state()})
run("grasp (close jaws for pressing)", lambda: {**(lambda r: {**r, "success": r["success"] or "fully-closed stroke" in r["failure_reason"]})(close_jaws())})
run("moveit pre-press", lambda: moveit(p_press + n3 * 0.12, R_t))
run("servo pre-press", lambda: ee(p_press + n3 * 0.12, R_t, tol=0.015))
run("servo approach", lambda: ee(p_press + n3 * 0.04, R_t, tol=0.01, max_linear_speed_m_s=0.05))
run("servo press", lambda: {**ee(p_press - n3 * 0.01, R_t, tol=0.01, max_linear_speed_m_s=0.03, timeout=15.0, hold_s=1.0), "mission": dict(mission)})
run("servo retract", lambda: ee(p_press + n3 * 0.12, R_t, tol=0.02, max_linear_speed_m_s=0.08))
spin(3.0)
log("RESULT", mission=dict(mission))
