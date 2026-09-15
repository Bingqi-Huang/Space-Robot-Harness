"""Independent effect-verification logic for the `panel_remount` task.

Pure functions, no ROS/rclpy/torch import -- so they run and are testable
offline (`python3 -m openral_ext.mission_verifier.tests.smoke`, no sim, no
ROS graph). `node.py` is the only place that touches ROS; it calls these.

Independence from the task's own self-report (the actual point of §4.4):
`space_robotics_bench/srb/tasks/mobile_manipulation/panel_remount_v2/task.py`
computes `termination_success` from `tf_pos_panel`/`tf_quat_panel` that are
already resident in the running Isaac Lab process (`RigidObject.data.
root_pos_w`), using its own reward/termination scaffolding
(`torch.jit.script`-compiled `_compute_step_return`). This module
recomputes the identical geometric test (same target pose, same
tolerances -- transcribed below from that file, cited per line) from
scratch against the pose the simulator broadcasts externally over `/tf`
(`srb/env{i} -> srb/env{i}/panel`, `RosInterface._broadcast_transforms`) --
a completely separate code path reading a completely separate transport,
so a bug in the task's own termination math would not be silently
corroborated by this verifier agreeing with it for the wrong reason.

Quaternion convention: (w, x, y, z), matching Isaac Lab's and
`RosInterface`'s own (`Quaternion(w=..., x=..., y=..., z=...)` from
`root_quat_w[..., 0..3]`).
"""

from __future__ import annotations

import math
from typing import NamedTuple

# ── Task constants, transcribed verbatim from panel_remount/task.py ──────
# (module-level `_PANEL_TARGET_POS`/`_PANEL_TARGET_QUAT` and the local
# `SUCCESS_*_TOLERANCE*` constants inside `_compute_step_return`). If the
# task's target/tolerances ever change, update here too -- these are
# intentionally NOT imported from `srb` (that would make this "verifier
# module" import torch/Isaac Lab, defeating the point of an independent,
# lightweight, offline-testable check).
PANEL_TARGET_POS = (3.5, 0.0, 0.5)  # task.py _PANEL_TARGET_POS, env-origin-relative (v2)
PANEL_TARGET_QUAT = (1.0, 0.0, 0.0, 0.0)  # task.py _PANEL_TARGET_QUAT (w, x, y, z)
SUCCESS_POS_TOLERANCE_M = 0.1  # task.py _compute_step_return SUCCESS_POS_TOLERANCE_M
SUCCESS_ROT_TOLERANCE_COS_HALF_ANGLE = 0.9  # task.py SUCCESS_ROT_TOLERANCE_COS_HALF_ANGLE

# Displacement threshold for the OBJECT_DISPLACED check: how far the panel
# must move from its episode-start ("rest") pose before this verifier calls
# it disturbed. Deliberately larger than physics/render jitter (order
# millimetres) and smaller than SUCCESS_POS_TOLERANCE_M, so "displaced" and
# "at target" are not the same event for a panel that never moved.
DISPLACEMENT_THRESHOLD_M = 0.03


class Quat(NamedTuple):
    w: float
    x: float
    y: float
    z: float


def _quat_conjugate(q: Quat) -> Quat:
    return Quat(q.w, -q.x, -q.y, -q.z)


def _quat_multiply(a: Quat, b: Quat) -> Quat:
    return Quat(
        w=a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
        x=a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
        y=a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
        z=a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
    )


def _euclidean_distance(p: tuple[float, float, float], q: tuple[float, float, float]) -> float:
    return math.sqrt(sum((pi - qi) ** 2 for pi, qi in zip(p, q, strict=True)))


class PanelAtTargetResult(NamedTuple):
    holds: bool
    distance_m: float
    rot_cos_half_angle: float
    confidence: float
    detail: str


def panel_at_target(
    panel_pos: tuple[float, float, float],
    panel_quat: tuple[float, float, float, float],
) -> PanelAtTargetResult:
    """Independently reproduce task.py's `termination_success` check.

    Args:
        panel_pos: Panel root position (x, y, z), env-origin-relative --
            same frame as the raw `srb/env{i} -> srb/env{i}/panel` `/tf`
            edge (SRB broadcasts `root_pos_w - env_origins`, see
            `RosInterface._broadcast_transforms`).
        panel_quat: Panel root orientation (w, x, y, z), same `/tf` edge.

    Returns:
        Whether the panel is within tolerance of the fixed target pose, the
        raw distance/rotation measurements, a confidence in [0, 1] (margin
        relative to the tolerance actually used -- 1.0 exactly at the
        target, 0.0 exactly at the tolerance boundary, clamped below that),
        and a human-readable detail string.

    Example:
        >>> r = panel_at_target((1.5, 0.0, 0.5), (1.0, 0.0, 0.0, 0.0))
        >>> r.holds
        True
        >>> round(r.confidence, 3)
        1.0
    """
    distance_m = _euclidean_distance(panel_pos, PANEL_TARGET_POS)
    q_panel = Quat(*panel_quat)
    q_target = Quat(*PANEL_TARGET_QUAT)
    q_rel = _quat_multiply(_quat_conjugate(q_panel), q_target)
    rot_cos_half_angle = abs(q_rel.w)

    pos_ok = distance_m < SUCCESS_POS_TOLERANCE_M
    rot_ok = rot_cos_half_angle > SUCCESS_ROT_TOLERANCE_COS_HALF_ANGLE
    holds = pos_ok and rot_ok

    # Confidence: how far inside (or outside) the tighter-binding tolerance
    # the current measurement sits, normalized to [0, 1]. Position and
    # rotation margins are on different scales (metres vs. cosine-of-half-
    # angle), so take whichever one is closer to failing as the binding
    # constraint -- an honest "how close to the edge" reading, not an
    # invented number.
    pos_margin = max(0.0, 1.0 - distance_m / SUCCESS_POS_TOLERANCE_M)
    rot_margin = max(
        0.0,
        (rot_cos_half_angle - SUCCESS_ROT_TOLERANCE_COS_HALF_ANGLE)
        / (1.0 - SUCCESS_ROT_TOLERANCE_COS_HALF_ANGLE),
    )
    confidence = min(pos_margin, rot_margin) if holds else 0.0

    detail = (
        f"dist_to_target={distance_m:.4f}m (tol={SUCCESS_POS_TOLERANCE_M}m), "
        f"rot_cos_half={rot_cos_half_angle:.4f} (tol={SUCCESS_ROT_TOLERANCE_COS_HALF_ANGLE})"
    )
    return PanelAtTargetResult(holds, distance_m, rot_cos_half_angle, confidence, detail)


class PanelDisplacedResult(NamedTuple):
    holds: bool
    displacement_m: float
    detail: str


def panel_displaced(
    panel_pos: tuple[float, float, float],
    rest_pos: tuple[float, float, float],
) -> PanelDisplacedResult:
    """Has the panel moved measurably from its episode-start ("rest") pose?

    Args:
        panel_pos: Current panel root position, env-origin-relative.
        rest_pos: Panel root position observed at/near episode start (the
            caller -- `node.py` -- tracks this across `/tf` messages and
            resets it on episode boundary; kept a pure argument here so
            this function stays independently testable).

    Example:
        >>> panel_displaced((1.1, 0.3, 0.3), (1.1, 0.3, 0.3)).holds
        False
        >>> panel_displaced((1.3, 0.2, 0.45), (1.1, 0.3, 0.3)).holds
        True
    """
    displacement_m = _euclidean_distance(panel_pos, rest_pos)
    holds = displacement_m > DISPLACEMENT_THRESHOLD_M
    detail = f"displacement={displacement_m:.4f}m (threshold={DISPLACEMENT_THRESHOLD_M}m)"
    return PanelDisplacedResult(holds, displacement_m, detail)
