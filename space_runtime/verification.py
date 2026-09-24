"""Independent effect verification (execution_plan §4.4): what physically happened after a capability call.

Answers effect questions ("is the base at the commanded pose?", "is the tool where it was sent?", "is the item in the
jaws?", "is it resting where it was set down?") from the robot-observable evidence the boundary returns, against the
commanded goal. It does not look at the skill's success flag, the agent's claims, the order of calls, or simulator
truth. For `pick` and `place` it recomputes the image checks itself from the raw frames the skill recorded (the
skill's own verdict is not evidence), with the jaw encoder and the arm kinematics.
"""
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from openral_rskill.procedural_pick import IN_JAWS_MIN_POINTS, in_jaws

BASE_NAV = {"navigate_to_pose", "navigate_to_feature"}
BASE_DOCK = {"dock_to_pose", "dock_at_feature"}
TCP = {"plan_ee_pose", "move_ee_to_pose", "plan_ee_to_feature", "move_ee_to_feature", "move_tool"}
TCP_DEFAULT_TOL = {"plan_ee_pose": 0.01, "plan_ee_to_feature": 0.01, "move_ee_to_pose": 0.015, "move_ee_to_feature": 0.015, "move_tool": 0.015}


def image_motion(before_png: str, after_png: str, before_depth: str, near_m: float,
                 gripper_mask: str | None = None) -> tuple[float, float, int]:
    """Median dense optical flow (px) over what is in front of the wrist camera and is not the gripper's own body (it is
    static in the frame and would mask any motion), the region's median depth, and how many pixels it has. The mask is
    the skill's own record of where its gripper falls in its camera, from the mount's geometry; the flow itself is
    recomputed here from the raw images and depth."""
    a, b = (cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY) for p in (before_png, after_png))
    z = np.load(before_depth)
    near = np.isfinite(z) & (z > 0.05) & (z < near_m)
    if gripper_mask and Path(gripper_mask).exists():
        near &= ~np.load(gripper_mask)
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 4, 31, 5, 7, 1.5, 0)
    if near.sum() == 0:
        return float("nan"), float("nan"), 0
    return float(np.median(np.linalg.norm(flow[near], axis=1))), float(np.median(z[near])), int(near.sum())


def jaw_state(jaw: float, cfg: dict) -> str:
    return "open" if jaw >= cfg["jaw"]["open_min_rad"] else "closed_empty" if jaw <= cfg["jaw"]["empty_max_rad"] else "holding_object"


def verify(capability: str, args: dict, evidence: dict, cfg: dict, held: list[str] | None = None,
           look: dict | None = None) -> list[dict]:
    goal, out = evidence.get("goal") or {}, []
    # An effect that was verified once is not a fact for the rest of the mission. Whatever the record says is being
    # carried is looked at again after each call (`look`, the boundary's `held_item`): a payload that leaves the jaws
    # while the rover drives is a mission fact, and without this nothing notices until something unrelated fails for
    # a reason that hides it -- in run g4s the ORU dropped back onto the depot stand as the rover pulled away, and
    # `place` reached out at the shelf holding nothing and stalled against the panel.
    # The jaw angle is not the evidence: it measures how far apart the fingers are, not whether anything is between
    # them, and a payload that slips out leaves them wherever the grasp left them. The picture is, and it is the same
    # picture a person would be shown; the angle rides along in the record. `place` and `release` exist to let go --
    # their own effects say what happened, and this check would only contradict them.
    if held and capability not in ("place", "release") and look is not None:
        # The picture says what is between the fingers; the encoder says whether they are apart at all. Jaws closed on
        # nothing cannot be holding anything, whatever is in the frame behind them -- the model called a solar panel
        # in the background a held item once (g5m), and the harness let a dropped payload through on that answer. The
        # angle cannot confirm a grip (a thin edge and an empty jaw are 0.17 and 0.10), but it can refuse one.
        seen = look["observed"]
        shut = jaw_state(float(look["jaw_rad"]), cfg) == "closed_empty"
        # One reading is a sample. The boundary read the picture once, compared it with what it knows (a pick
        # succeeded, the jaw is in the held range) and, when they disagreed or the reading was unsure, read it again with
        # the facts that say what a held handle looks like from this camera. Both readings are kept in the record; what
        # they finally say is the verdict, and a disagreement that survives is the reasoner's to resolve.
        out.append({"effect": "item_still_held", "holds": bool(seen["holding"]) and not shut, "items": list(held),
                    "seen": seen["what"], "confidence": seen.get("confidence"),
                    "first_reading": seen.get("first_reading"), "second_reading": seen.get("second_reading"),
                    "record_and_jaw_expect_held": seen.get("record_and_jaw_expect_held"),
                    "jaw_rad": look["jaw_rad"], "image": seen["image"],
                    "jaw": "closed_empty" if shut else "open_or_holding",
                    "source": "the gripper's own camera read by the vision model against the pick record and the jaw "
                              "encoder, read again with context when they disagree; refused by the jaw encoder when the "
                              "fingers are shut on nothing"})
    if capability in BASE_NAV | BASE_DOCK and isinstance(evidence.get("base_pose"), dict):
        band = cfg["base"]["navigate" if capability in BASE_NAV else "dock"]
        b = evidence["base_pose"]
        d = math.hypot(b["x"] - goal["x"], b["y"] - goal["y"])
        dyaw = abs((b["yaw"] - goal["yaw"] + math.pi) % (2 * math.pi) - math.pi)
        out.append(dict(effect="base_at_commanded_pose", holds=d <= band["position_m"] and dyaw <= band["yaw_rad"],
                        position_error_m=round(d, 3), yaw_error_rad=round(dyaw, 3), band=band,
                        source="rover localization estimate (AMCL) vs commanded goal",
                        **({"stand_advice": evidence["stand_advice"]} if evidence.get("stand_advice") else {})))
    if capability in TCP and isinstance(evidence.get("tcp_pose"), dict):
        tol = args.get("tolerance_m", TCP_DEFAULT_TOL[capability]) * cfg["tcp"]["tolerance_factor"]
        if capability.startswith("plan_"):
            tol += cfg["tcp"]["plan_execution_m"]
        d = math.dist(evidence["tcp_pose"]["position"], goal["position"])
        out.append(dict(effect="tool_at_commanded_position", holds=d <= tol, position_error_m=round(d, 4), band_m=round(tol, 4),
                        source="arm forward kinematics vs commanded TCP target (rover frame)"))
    if capability == "approach_target" and "target_rover" in evidence and isinstance(evidence.get("tcp_pose"), dict):
        standoff = args.get("standoff_m", 0.10)
        d = math.dist(evidence["tcp_pose"]["position"], evidence["target_rover"])
        out.append(dict(effect="tool_at_standoff_from_seen_target", holds=abs(d - standoff) <= cfg["tcp"]["approach_band_m"],
                        tool_to_target_m=round(d, 4), standoff_m=standoff, source="arm kinematics vs wrist-camera triangulated target"))
    arm = evidence.get("arm")
    if capability in ("grasp", "release") and isinstance(arm, dict):
        state = jaw_state(arm["jaw_rad"], cfg)
        want = {"grasp": ("holding_object", "closed_empty"), "release": ("open",)}[capability]
        out.append(dict(effect=f"jaws_{state}", holds=state in want, jaw_rad=arm["jaw_rad"], source="gripper jaw encoder"))
    if capability in ("arm_ready", "stow") and isinstance(arm, dict):
        want = {"arm_ready": "ready", "stow": "stowed"}[capability]
        out.append(dict(effect=f"arm_{want}", holds=arm["posture"] == want, posture=arm["posture"], source="arm joint encoders"))
    if capability == "pick" and isinstance(arm, dict):
        # held = jaws stopped on something + the item rose with the gripper during the lift (its image stayed put while a
        # left-behind item would have shifted by the lift's image displacement)
        hc = (evidence.get("skill") or {}).get("hold_check")
        state = jaw_state(arm["jaw_rad"], cfg)
        m = dict(effect="item_held", target=args["target"], jaw_rad=arm["jaw_rad"], jaw=state,
                 source="jaw encoder + wrist images before/after the lift (flow recomputed here) + arm kinematics")
        if hc:
            near_m = float(hc.get("self_depth_m", 0.0)) + cfg["hold"]["beyond_gripper_m"] if hc.get("self_depth_m") else cfg["hold"]["near_m"]
            flow, depth, n = image_motion(hc["before"], hc["after"], hc["before_depth"], near_m, hc.get("gripper_mask"))
            expected = hc["fx"] * hc["lift_m"] / depth if n else float("nan")
            moved_with = n >= cfg["hold"]["min_pixels"] and flow < cfg["hold"]["flow_fraction"] * expected
            m.update(lift_m=hc["lift_m"], image_flow_px=round(flow, 1), left_behind_flow_px=round(expected, 1), rose_with_gripper=bool(moved_with))
            m["holds"] = state == "holding_object" and hc["lift_m"] >= cfg["hold"]["min_lift_m"] and bool(moved_with)
        else:
            m["holds"] = False
        out.append(m)
    if capability == "place" and isinstance(arm, dict):
        sk = evidence.get("skill") or {}
        st, contact = sk.get("settle"), sk.get("contact")
        state = jaw_state(arm["jaw_rad"], cfg)
        m = dict(effect="item_placed", support=args["support"], jaw=state, jaw_rad=arm["jaw_rad"],
                 source="jaw encoder + arm kinematics (tool clear of the release point) + wrist images and depth after the retreat "
                        "(flow and the points between the open fingers recomputed here)")
        # What the skill got as far as, kept whether or not it finished: a skill that let go and then stopped in its retreat
        # (gc1) leaves the model asking a camera whether the item is there, when the record says where it was let go
        if contact:
            m.update(let_go_at=contact["tcp"], let_go_above_expected_m=contact.get("stopped_above_expected_m"),
                     skill_stopped_at=sk.get("failed_stage"))
        if st and contact and isinstance(evidence.get("tcp_pose"), dict):
            clear = math.dist(evidence["tcp_pose"]["position"], contact["tcp"])
            flow, depth, n = image_motion(st["before"], st["after"], st["before_depth"], cfg["place"]["near_m"],
                                          st.get("gripper_mask"))
            # a distance, not a pixel count: `settle_moved_mm` at the region's own depth through the camera's focal length
            limit = st["fx"] * cfg["place"]["settle_moved_mm"] / 1000.0 / depth if n else float("nan")
            still = n >= cfg["hold"]["min_pixels"] and flow < limit
            # still and clear is not enough: an item caught on the open fingers hangs still from the retreated tool
            # (step10_r1/ours_l2b_habitat: "item_placed HOLDS" with the container on the fingers, dropped at the stow).
            # The settle frame's own depth, counted inside the fingers' grip space; absent when the skill stopped first.
            between = (in_jaws(SimpleNamespace(depth=np.load(st["before_depth"]), K=np.array(st["K"])), np.array(st["T_tool_cam"]))
                       if "T_tool_cam" in st else None)
            m.update(tool_clear_of_release_m=round(clear, 3), image_flow_px=round(flow, 2), item_still=bool(still),
                     points_between_open_fingers=between)
            m["holds"] = (state == "open" and clear >= cfg["place"]["min_clear_m"] and bool(still)
                          and between is not None and between < IN_JAWS_MIN_POINTS)
        else:
            m["holds"] = False
        out.append(m)
    if capability == "press":
        # A press is over when the tool, jaws closed, met the button and came back off it. Every half is the robot's own
        # measurement against the button the skill fitted from the catalogue's declared shape -- never the skill's success
        # flag: the jaws were closed (encoder), the tool went in past the button's tip, it was on the button's axis to
        # within the declared cap radius, and it is clear of it again afterwards. mc1's two presses had the jaws open at
        # 0.82 rad and the tool a hand's width off the button, and the check that only looked at depth passed both.
        sk = evidence.get("skill") or {}
        contact, target = sk.get("contact"), sk.get("target_rover")
        m = dict(effect="pressed", target=args.get("target"),
                 source="arm kinematics and the jaw encoder against the button the wrist depth fitted (jaws closed, on the button, "
                        "past its tip, and back off it)")
        if contact and target and isinstance(evidence.get("tcp_pose"), dict) and "off_axis_m" in contact:
            past, off, jaw = float(contact.get("past_face_m", 0.0)), float(contact["off_axis_m"]), float(contact["jaw_rad"])
            back = math.dist(evidence["tcp_pose"]["position"], contact["tcp"])
            m.update(past_face_m=round(past, 4), off_axis_m=round(off, 4), cap_radius_m=contact["cap_radius_m"],
                     jaw_at_contact=jaw_state(jaw, cfg), retreated_m=round(back, 3))
            m["holds"] = (past >= cfg["press"]["min_contact_m"] and back >= cfg["press"]["min_retreat_m"]
                          and off <= float(contact["cap_radius_m"]) and jaw_state(jaw, cfg) == "closed_empty")
        else:
            m["holds"] = False
        out.append(m)
    return out
