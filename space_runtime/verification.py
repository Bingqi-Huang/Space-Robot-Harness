"""Independent effect verification (execution_plan §4.4): what physically happened after a capability call.

Answers effect questions ("is the base at the commanded pose?", "is the tool where it was sent?", "is the item in the
jaws?", "is it resting where it was set down?") from the robot-observable evidence the boundary returns, against the
commanded goal. It does not look at the skill's success flag, the agent's claims, the order of calls, or simulator
truth. For `pick` and `place` it recomputes the image checks itself from the raw frames the skill recorded (the
skill's own verdict is not evidence), with the jaw encoder and the arm kinematics.
"""
import math

import cv2
import numpy as np

BASE_NAV = {"navigate_to_pose", "navigate_to_feature"}
BASE_DOCK = {"dock_to_pose", "dock_at_feature"}
TCP = {"plan_ee_pose", "move_ee_to_pose", "plan_ee_to_feature", "move_ee_to_feature", "move_tool"}
TCP_DEFAULT_TOL = {"plan_ee_pose": 0.01, "plan_ee_to_feature": 0.01, "move_ee_to_pose": 0.015, "move_ee_to_feature": 0.015, "move_tool": 0.015}


def image_motion(before_png: str, after_png: str, before_depth: str, near_m: float, item_rows_px: int = 216) -> tuple[float, float, int]:
    """Median dense optical flow (px) over what is in front of the wrist camera in the part of the frame the fingers do
    not fill (they are static in it and would mask any motion), the region's median depth, and how many pixels it has."""
    a, b = (cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY) for p in (before_png, after_png))
    z = np.load(before_depth)
    near = np.isfinite(z) & (z > 0.05) & (z < near_m)
    near[item_rows_px:, :] = False
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 4, 31, 5, 7, 1.5, 0)
    if near.sum() == 0:
        return float("nan"), float("nan"), 0
    return float(np.median(np.linalg.norm(flow[near], axis=1))), float(np.median(z[near])), int(near.sum())


def jaw_state(jaw: float, cfg: dict) -> str:
    return "open" if jaw >= cfg["jaw"]["open_min_rad"] else "closed_empty" if jaw <= cfg["jaw"]["empty_max_rad"] else "holding_object"


def verify(capability: str, args: dict, evidence: dict, cfg: dict) -> list[dict]:
    goal, out = evidence.get("goal") or {}, []
    if capability in BASE_NAV | BASE_DOCK and isinstance(evidence.get("base_pose"), dict):
        band = cfg["base"]["navigate" if capability in BASE_NAV else "dock"]
        b = evidence["base_pose"]
        d = math.hypot(b["x"] - goal["x"], b["y"] - goal["y"])
        dyaw = abs((b["yaw"] - goal["yaw"] + math.pi) % (2 * math.pi) - math.pi)
        out.append(dict(effect="base_at_commanded_pose", holds=d <= band["position_m"] and dyaw <= band["yaw_rad"],
                        position_error_m=round(d, 3), yaw_error_rad=round(dyaw, 3), band=band,
                        source="rover localization estimate (AMCL) vs commanded goal"))
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
            flow, depth, n = image_motion(hc["before"], hc["after"], hc["before_depth"], cfg["hold"]["near_m"], hc.get("item_rows_px", 216))
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
                 source="jaw encoder + arm kinematics (tool clear of the release point) + wrist images after the retreat (flow recomputed here)")
        if st and contact and isinstance(evidence.get("tcp_pose"), dict):
            clear = math.dist(evidence["tcp_pose"]["position"], contact["tcp"])
            flow, _, n = image_motion(st["before"], st["after"], st["before_depth"], cfg["place"]["near_m"])
            still = n == 0 or flow < cfg["place"]["still_flow_px"]
            m.update(tool_clear_of_release_m=round(clear, 3), image_flow_px=round(flow, 2), item_still=bool(still))
            m["holds"] = state == "open" and clear >= cfg["place"]["min_clear_m"] and bool(still)
        else:
            m["holds"] = False
        out.append(m)
    return out
