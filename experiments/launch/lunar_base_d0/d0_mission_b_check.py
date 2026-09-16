"""Phase D0: Mission B `covered` (deliver the spare ORU from the depot stand to PDU-1's shelf) through the
shared capability stack. Helpers and graph readiness: d0_common.py."""
from d0_common import *  # noqa: F401,F403

# ---- mission B covered: ORU on depot slot_0 -> PDU-1 shelf ---------------------------------------------------------
oru = handle_pos("spare_oru")
slot = IX["points"]["depot_stand/slot_0"]
shelf = IX["points"]["pdu_1_shelf/shelf"]
wp_pick, yaw_pick, n_pick = work_pose(oru, slot["normal"])
wp_place, yaw_place, n_place = work_pose(shelf["xyz"], shelf["normal"])
flange_place = np.array(shelf["xyz"]) + np.array([0.0, 0.0, 0.005 + IX["objects"]["spare_oru"]["handle"]["xyz"][2]])
n3 = np.array([n_pick[0], n_pick[1], 0.0])
m3 = np.array([n_place[0], n_place[1], 0.0])
log("PLAN", oru_handle=oru.tolist(), work_pick=[*wp_pick.tolist(), round(math.degrees(yaw_pick))], work_place=[*wp_place.tolist(), round(math.degrees(yaw_place))])



# 1-2 base to the pick work pose. Nav2 is asked to arrive FACING the site (its natural heading after
# driving there); the docking skill then turns the arm end round and reverses -- a Nav2 goal that
# demands the reversed heading makes MPPI U-turn a base that turns poorly, and it drove 1.5 m past
# the goal into the stand's inflation (run 5).
stage_pick, stage_pick_yaw = staging(wp_pick, yaw_pick)
stage_place, stage_place_yaw = staging(wp_place, yaw_place)
# The depot is reached on the depot loop's east leg (layout.yaml `depot_loop`, the road built for it): a direct
# Nav2 goal cut the charging station's corner and wedged the rover against it (research repo F51, run b1).
ROAD_EAST_LEG = (6.0, -6.0)
leg_yaw = math.atan2(stage_pick[1] - ROAD_EAST_LEG[1], stage_pick[0] - ROAD_EAST_LEG[0])
run("nav road east leg", lambda: {**nav(ROAD_EAST_LEG, leg_yaw), **base_err(ROAD_EAST_LEG, leg_yaw)})
run("nav approach pick", lambda: {**nav(stage_pick, stage_pick_yaw), **base_err(stage_pick, stage_pick_yaw)})
run("dock pick", lambda: {**dock(wp_pick, yaw_pick), **base_err(wp_pick, yaw_pick)})
# 3-7 arm: open, READY, pre-grasp via MoveIt (checked), pre-grasp via servo, approach, grasp, lift
run("release (open)", lambda: dispatch("release", {"mode": "open"}, deadline=20))
run("move_joints READY", lambda: dispatch("joints", {"joint_targets": READY, "timeout_s": 20.0}, deadline=40))
R_g = grip_frame(n_pick)
oru = handle_pos("spare_oru")
run("moveit pre-grasp", lambda: {**moveit(oru + n3 * 0.18, R_g), "oru_moved_m": round(float(np.linalg.norm(handle_pos("spare_oru") - oru)), 3)})
# targets re-perceived at step time: a MoveIt plan that knows only the rover nudged the ORU 5 cm and the jaws closed on
# nothing (F51, run b5); relative perception would see the handle where it is
run("servo pre-grasp", lambda: ee(handle_pos("spare_oru") + n3 * 0.18, R_g))
run("servo approach", lambda: ee(handle_pos("spare_oru") - n3 * 0.015, R_g, tol=0.01, max_linear_speed_m_s=0.05))
run("grasp", lambda: dispatch("grasp", {"mode": "close", "timeout_s": 8.0}, deadline=20))
run("servo lift", lambda: {**ee(tcp_pose()[0] + np.array([0.0, 0.0, 0.10]), R_g, tol=0.015, max_linear_speed_m_s=0.05), "oru_handle_z": round(float(handle_pos("spare_oru")[2]), 3)})
# 8-10 carry: back out to the approach point, Nav2 to PDU-1, dock
run("dock leave pick", lambda: {**dock(stage_pick, stage_pick_yaw, approach_m=0.8), "held": round(float(np.linalg.norm(handle_pos("spare_oru") - tcp_pose()[0])), 3)})
run("nav road east leg (carry)", lambda: {**nav(ROAD_EAST_LEG, leg_yaw + math.pi), **base_err(ROAD_EAST_LEG, leg_yaw + math.pi),
                                            "held": round(float(np.linalg.norm(handle_pos("spare_oru") - tcp_pose()[0])), 3)})
run("nav approach place", lambda: {**nav(stage_place, stage_place_yaw), **base_err(stage_place, stage_place_yaw), "held": round(float(np.linalg.norm(handle_pos("spare_oru") - tcp_pose()[0])), 3)})
run("dock place", lambda: {**dock(wp_place, yaw_place), **base_err(wp_place, yaw_place), "held": round(float(np.linalg.norm(handle_pos("spare_oru") - tcp_pose()[0])), 3)})
# 11-14 place: over the shelf, lower, release, retreat, stow
R_p = grip_frame(n_place)
g = flange_place - m3 * 0.015
run("servo over shelf", lambda: ee(g + np.array([0.0, 0.0, 0.10]), R_p, tol=0.015, max_linear_speed_m_s=0.08, timeout=40.0))
run("servo lower", lambda: ee(g + np.array([0.0, 0.0, 0.01]), R_p, tol=0.01, max_linear_speed_m_s=0.04))
run("release", lambda: {**dispatch("release", {"mode": "open"}, deadline=20), **{"mission": dict(mission)}})
run("servo retreat", lambda: ee(g + m3 * 0.18 + np.array([0.0, 0.0, 0.02]), R_p, tol=0.02, max_linear_speed_m_s=0.08))
run("stow", lambda: dispatch("stow", {}, deadline=40))
# 15-16 back to the dock
run("dock leave place", lambda: dock(stage_place, stage_place_yaw, approach_m=0.8))
run("nav dock", lambda: {**nav([0.0, 0.0], 0.0), **base_err([0.0, 0.0], 0.0)})
spin(3.0)
log("RESULT", mission=dict(mission))
