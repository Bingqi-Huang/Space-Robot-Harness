"""scan_label -- read the serial data plates of the items at a surveyed support (Experiment II's new capability).

docs/heldout_design.md §6. Identical ORUs differ only by serial; every carried item wears flat data plates on its lid
beside the handle column (NASA-STD-6002: a Data Matrix of 2.5 mm modules plus the S/N in text, 40 x 56 mm). The vision
model cannot decode a Data Matrix; this reads it.

Shared low-level implementation, built before Experiment II and NOT registered with any method: no entry in
`openral_ext/capability_server/contracts.yaml` (so neither Ours' palette nor the PLEXIL adapter can reach it), no
PLEXIL Command, no EUROPA activity. Making it usable at mission level is the timed work of Experiment II
(research_content §5.6); until then only the development check calls it
(`experiments/launch/lunar_base_d0/scan_label_check.py`).

One whole operation, with the rover docked at the support:

1. view -- the wrist camera goes to its one scan view: it looks at the point where the item's handle column meets its lid
   (the support's surveyed point, raised by the catalogued item's height above it), from `SCAN_DISTANCE_M` out along
   the support's normal (the side the rover docks on), `SCAN_ELEVATION_DEG` below the horizontal, image up pointing away
   from the rover. The arm configuration is the robot's collision-checked inverse kinematics from the working seeds,
   the one with the least posture cost (as the skills' planned moves choose, `_eye_in_hand.EyeInHandSkill.ik`); the path
   to it is the posture skill's planned one, the same as `stow` and `arm_ready` take.
2. read -- one wrist frame once the arm has stopped; zxing-cpp on the frame upscaled 2x (a module is about 3 px at this
   view); every Data Matrix decoded, with its corners and how far it lies in the image from the aimed column foot.
3. fold -- the arm back to its travel posture. A fold that fails is reported beside the reading, not as a failed scan.

One view, one look. Reading no label is a result, not a failure -- an empty support and a plate the view does not show
both come back with no serials and the frame as evidence; what to do about it is the calling method's decision. The
operation fails only when the view cannot be taken, and says why.

The robot is reached through `io`, which the caller supplies (the development check today; the capability boundary once
a method registers the capability):
    io.tf(target, source) -> 4x4               transform from the robot's TF
    io.ik(p, R, seed) -> list[float] | None    collision-checked IK of the tool centre point in chassis_base_link
    io.arm_q() -> list[float]                  the seven arm joints now
    io.move_joints(q) -> (ok, why)             the planned move to a configuration (posture skill)
    io.fold() -> (ok, why)                     the planned move to the travel posture
    io.wrist_frame(after) -> (bgr, K, frame_id, stamp)   the next wrist colour frame stamped after `after` (sim s)
    io.now() -> float                          simulation time
    io.wait(sim_s)                             let simulation time pass
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
import zxingcpp
from openral_rskill._eye_in_hand import nearest_equivalent, posture_cost, working_seeds

#: The scan view. Pick's own view read 1 of 42 recorded labels (research repo F115): from there the handle column and
#: the palm cover the lid; from above and in front of the column the lid beside it is in the clear. The view that has
#: read labels on the robot is `check2/look_battery_scan`'s (F115's Isaac photos, ORU-0417 and ORU-0211): its camera
#: stood 0.356 m from the column foot at 67 deg below the horizontal (the bag's /tf). F115 wrote that view down as
#: 0.45 m / 70 deg, which puts the camera 0.10 m higher and has no arm configuration at the depot stand
#: (`artifacts/runs/pf/scan_label_1`, research repo F131). The measured view is the scan view.
SCAN_DISTANCE_M = 0.36
SCAN_ELEVATION_DEG = 67.0
#: zxing-cpp reads the upscaled frame; at the view's native ~3 px per module it misses symbols it reads at 2x (F115)
UPSCALE = 2
#: how long the arm is left to stop swinging before the frame is taken (sim s)
SETTLE_S = 1.0


def scan_camera_pose(foot_base: np.ndarray, normal_base: np.ndarray, distance_m: float) -> np.ndarray:
    """The wrist camera's optical frame (4x4 in chassis_base_link: x right, y down, z along the view) for the scan view
    of a column foot from `distance_m`, with the support's outward normal (towards the rover)."""
    n = np.array([normal_base[0], normal_base[1], 0.0])
    n /= np.linalg.norm(n)
    el = math.radians(SCAN_ELEVATION_DEG)
    c = foot_base + distance_m * (math.cos(el) * n + math.sin(el) * np.array([0.0, 0.0, 1.0]))
    z = (foot_base - c) / np.linalg.norm(foot_base - c)
    y = n - np.dot(n, z) * z  # image down = towards the rover, so image up points away from it
    y /= np.linalg.norm(y)
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = np.column_stack([np.cross(y, z), y, z]), c
    return T


def read_plates(bgr: np.ndarray) -> list[dict]:
    """Every Data Matrix zxing-cpp decodes in the frame upscaled `UPSCALE` times: its text and its corners (px of the
    original frame, top-left first)."""
    big = cv2.resize(bgr, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)
    out = []
    for r in zxingcpp.read_barcodes(big, formats=zxingcpp.BarcodeFormat.DataMatrix):
        p = r.position
        corners = [[round(q.x / UPSCALE, 1), round(q.y / UPSCALE, 1)] for q in (p.top_left, p.top_right, p.bottom_right, p.bottom_left)]
        out.append({"serial": r.text, "corners_px": corners})
    return out


def scan(io, support: str, support_xyz_map, support_normal_map, item_top_m: float, evidence_dir: Path) -> dict:
    """The whole operation at one support. Returns {success, failure_reason, serials, plates, evidence}."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    T_bm = io.tf("chassis_base_link", "map")
    foot = T_bm[:3, :3] @ (np.array(support_xyz_map, float) + [0.0, 0.0, item_top_m]) + T_bm[:3, 3]
    normal = T_bm[:3, :3] @ np.array(support_normal_map, float)
    ev = {"support": support, "column_foot_base": [round(float(v), 3) for v in foot]}

    # the camera's pose follows from the tool's through the wrist mount
    _, _, frame_id, _ = io.wrist_frame(-1.0)
    T_cam = scan_camera_pose(foot, normal, SCAN_DISTANCE_M)
    T_tool = T_cam @ np.linalg.inv(io.tf("tcp_frame", frame_id))
    ev["camera_base"] = [round(float(v), 3) for v in T_cam[:3, 3]]
    # the arm configuration for that one pose, chosen as the skills' planned moves choose it
    q_now, best = list(io.arm_q()), None
    for seed in [q_now] + working_seeds():
        sol = io.ik(T_tool[:3, 3], T_tool[:3, :3], seed)
        if sol is None:
            continue
        sol = nearest_equivalent(sol, q_now)
        key = (round(posture_cost(sol) / 0.05), max(abs(a - b) for a, b in zip(sol, q_now)))
        if best is None or key < best[0]:
            best = (key, sol)
    if best is None:
        return {"success": False, "failure_reason": f"the arm has no collision-free configuration for the scan view of {support} "
                                                    f"from where the rover stands", "serials": [], "plates": [], "evidence": ev}
    ok, why = io.move_joints(best[1])
    if not ok:
        return {"success": False, "failure_reason": f"could not move the camera to the scan view: {why}", "serials": [],
                "plates": [], "evidence": ev}
    io.wait(SETTLE_S)
    bgr, K, frame_id, stamp = io.wrist_frame(io.now())
    T_cam_now = io.tf("chassis_base_link", frame_id)
    plates = read_plates(bgr)
    # where the aimed column foot falls in this frame: which plate belongs to the item at the support, when a
    # neighbouring item's plate is in view too
    pc = T_cam_now[:3, :3].T @ (foot - T_cam_now[:3, 3])
    aim = np.array([K[0, 0] * pc[0] / pc[2] + K[0, 2], K[1, 1] * pc[1] / pc[2] + K[1, 2]])
    for p in plates:
        p["px_from_aim"] = round(float(np.linalg.norm(np.mean(p["corners_px"], axis=0) - aim)), 1)
    raw = str(evidence_dir / "scan_raw.jpg")
    cv2.imwrite(raw, bgr)
    img = bgr.copy()
    cv2.drawMarker(img, (int(aim[0]), int(aim[1])), (0, 255, 255), cv2.MARKER_CROSS, 24, 2)
    for p in plates:
        c = np.array(p["corners_px"], np.int32)
        cv2.polylines(img, [c], True, (0, 255, 0), 2)
        cv2.putText(img, p["serial"], (int(c[:, 0].min()), int(c[:, 1].min()) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
    ev.update(image=str(evidence_dir / "scan.jpg"), raw_image=raw, stamp=round(float(stamp), 2),
              camera_base_reached=[round(float(v), 3) for v in T_cam_now[:3, 3]],
              view_error_m=round(float(np.linalg.norm(T_cam_now[:3, 3] - T_cam[:3, 3])), 3))
    cv2.imwrite(ev["image"], img)
    ok, why = io.fold()
    ev["folded"] = ok if ok else f"not folded: {why}"
    return {"success": True, "failure_reason": "", "serials": sorted({p["serial"] for p in plates}), "plates": plates, "evidence": ev}
