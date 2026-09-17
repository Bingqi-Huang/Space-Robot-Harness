"""Independent effect verification (execution_plan §4.4): what physically happened after a capability call.

Answers effect questions ("is the base at the commanded pose?", "is the tool where it was sent?", "are the jaws
holding something?") from the robot-observable evidence the boundary returns, against the commanded goal. It does not
look at the skill's success flag, the agent's claims, the order of calls, or simulator truth.
"""
import math

BASE_NAV = {"navigate_to_pose", "navigate_to_feature"}
BASE_DOCK = {"dock_to_pose", "dock_at_feature"}
TCP = {"plan_ee_pose", "move_ee_to_pose", "plan_ee_to_feature", "move_ee_to_feature"}
TCP_DEFAULT_TOL = {"plan_ee_pose": 0.01, "plan_ee_to_feature": 0.01, "move_ee_to_pose": 0.015, "move_ee_to_feature": 0.015}


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
        d = math.dist(evidence["tcp_pose"]["position"], goal["position"])
        out.append(dict(effect="tool_at_commanded_position", holds=d <= tol, position_error_m=round(d, 4), band_m=round(tol, 4),
                        source="arm forward kinematics vs commanded TCP target (rover frame)"))
    arm = evidence.get("arm")
    if capability in ("grasp", "release") and isinstance(arm, dict):
        jaw = arm["jaw_rad"]
        state = "open" if jaw >= cfg["jaw"]["open_min_rad"] else "closed_empty" if jaw <= cfg["jaw"]["empty_max_rad"] else "holding_object"
        want = {"grasp": ("holding_object", "closed_empty"), "release": ("open",)}[capability]
        out.append(dict(effect=f"jaws_{state}", holds=state in want, jaw_rad=jaw, source="gripper jaw encoder"))
    if capability in ("arm_ready", "stow") and isinstance(arm, dict):
        want = {"arm_ready": "ready", "stow": "stowed"}[capability]
        out.append(dict(effect=f"arm_{want}", holds=arm["posture"] == want, posture=arm["posture"], source="arm joint encoders"))
    return out
