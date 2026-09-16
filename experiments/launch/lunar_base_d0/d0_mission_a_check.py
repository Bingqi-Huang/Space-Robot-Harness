"""Phase D0: Mission A `covered` (PDU-2 reported faulted and is faulted: drive there, press its reset button,
verify, dock) through the shared capability stack. Helpers and graph readiness: d0_common.py.

The covered case needs no semantic inspection (the report names the faulted unit); the reset press is
verified by the task itself (`mission_state()['faulted']` clears when the TCP reaches the button cap).
"""
from d0_common import *  # noqa: F401,F403

# ---- mission A covered: PDU-2 reset ---------------------------------------------------------------------------------
PDU = os.environ.get("D0_PDU", "pdu_2")
press = IX["points"][f"{PDU}_panel/press"]
p_press = np.array(press["xyz"])
wp, yaw_w, n_w = work_pose(p_press, press["normal"])
n3 = np.array([n_w[0], n_w[1], 0.0])
R_t = tool_frame(n_w)  # tool z into the panel, jaw axis vertical (the oracle's press orientation, F45)
log("PLAN", pdu=PDU, press=p_press.tolist(), work=[*wp.tolist(), round(math.degrees(yaw_w))])


def press_state():
    return dict(mission=dict(mission), tcp_to_button_m=round(float(np.linalg.norm(tcp_pose()[0] - p_press)), 4))


# 1-2 base to the work pose: Nav2 delivers the rover to the docking staging pose (already on the work
# pose's axis, already facing the way it enters), then the dock skill backs it in.
stage_xy, stage_yaw = staging(wp, yaw_w)
run("nav approach", lambda: {**nav(stage_xy, stage_yaw), **base_err(stage_xy, stage_yaw)})
run("dock", lambda: {**dock(wp, yaw_w), **base_err(wp, yaw_w)})
# 3-7 arm: close the jaws (pressing with the closed gripper), READY, pre-press via MoveIt, approach, press, retract
run("grasp (close jaws)", lambda: dispatch("grasp", {"mode": "close", "timeout_s": 8.0}, deadline=20))
run("move_joints READY", lambda: dispatch("joints", {"joint_targets": READY, "timeout_s": 20.0}, deadline=40))
run("moveit pre-press", lambda: moveit(p_press + n3 * 0.12, R_t))
run("servo pre-press", lambda: ee(p_press + n3 * 0.12, R_t, tol=0.015))
run("servo approach", lambda: ee(p_press + n3 * 0.04, R_t, tol=0.01, max_linear_speed_m_s=0.05))
run("servo press", lambda: {**ee(p_press - n3 * 0.01, R_t, tol=0.01, max_linear_speed_m_s=0.03, timeout=15.0, hold_s=1.0), **press_state()})
run("servo retract", lambda: {**ee(p_press + n3 * 0.12, R_t, tol=0.02, max_linear_speed_m_s=0.08), **press_state()})
# back through READY (the arm crosses from the shoulder-back branch to the folded stow pose) with the
# mission's own notion of stowed in mind: the verifier accepts 0.35 rad, the skill defaulted to 0.05 in
# 15 s and missed by 0.086 rad (a8)
run("move_joints READY (unstow path)", lambda: dispatch("joints", {"joint_targets": READY, "tolerance_rad": 0.1, "timeout_s": 30.0}, deadline=60))
run("stow", lambda: dispatch("stow", {"tolerance_rad": 0.1, "timeout_s": 30.0}, deadline=60))
# 8-9 back to the dock
run("dock leave", lambda: dock(stage_xy, stage_yaw, approach_m=0.8))
run("nav dock", lambda: {**nav([0.0, 0.0], 0.0), **base_err([0.0, 0.0], 0.0)})
spin(3.0)
log("RESULT", mission=dict(mission))
