"""Offline logic smoke check for the mission verifier -- no ROS, no sim,
no pytest (AGENT.md: minimize pytest). Same style as the procedural
rSkills' own offline smoke check from execution_plan.md §8.3 item 3.

Run: python3 openral_ext/mission_verifier/smoke_test_logic.py
"""

from openral_ext.mission_verifier.panel_remount_logic import (
    DISPLACEMENT_THRESHOLD_M,
    PANEL_TARGET_POS,
    PANEL_TARGET_QUAT,
    panel_at_target,
    panel_displaced,
)


def check(label, fn):
    try:
        fn()
        print(f"PASS {label}")
    except AssertionError as e:
        print(f"FAIL {label}: {e}")
        raise


# ── panel_at_target: exactly at target -> holds, confidence 1.0 ──────────
def test_at_target_exact():
    r = panel_at_target(PANEL_TARGET_POS, PANEL_TARGET_QUAT)
    assert r.holds
    assert abs(r.confidence - 1.0) < 1e-9, r.confidence
    assert r.distance_m == 0.0


# ── panel_at_target: within position tolerance, identity orientation ─────
def test_at_target_within_tolerance():
    near = (
        PANEL_TARGET_POS[0] + 0.03,
        PANEL_TARGET_POS[1],
        PANEL_TARGET_POS[2],
    )
    r = panel_at_target(near, PANEL_TARGET_QUAT)
    assert r.holds, r.detail
    assert 0.0 < r.confidence < 1.0, r.confidence


# ── panel_at_target: outside position tolerance -> fails, confidence 0 ───
def test_at_target_too_far():
    far = (PANEL_TARGET_POS[0] + 0.5, PANEL_TARGET_POS[1], PANEL_TARGET_POS[2])
    r = panel_at_target(far, PANEL_TARGET_QUAT)
    assert not r.holds
    assert r.confidence == 0.0


# ── panel_at_target: right position, wrong orientation (90deg off) -> fails ──
def test_at_target_wrong_orientation():
    # 90 deg about z: (w, x, y, z) = (cos(45deg), 0, 0, sin(45deg))
    quat_90z = (0.70710678, 0.0, 0.0, 0.70710678)
    r = panel_at_target(PANEL_TARGET_POS, quat_90z)
    assert not r.holds, r.detail
    assert r.rot_cos_half_angle < 0.9, r.rot_cos_half_angle


# ── panel_at_target: sign-ambiguous quaternion (q and -q) still matches ──
def test_at_target_quat_sign_ambiguity():
    negated = tuple(-c for c in PANEL_TARGET_QUAT)
    r = panel_at_target(PANEL_TARGET_POS, negated)
    assert r.holds, r.detail


# ── panel_displaced: no movement -> False ─────────────────────────────────
def test_displaced_no_movement():
    rest = (1.1, 0.3, 0.3)
    r = panel_displaced(rest, rest)
    assert not r.holds
    assert r.displacement_m == 0.0


# ── panel_displaced: movement just under threshold -> False ──────────────
def test_displaced_under_threshold():
    rest = (1.1, 0.3, 0.3)
    moved = (1.1 + (DISPLACEMENT_THRESHOLD_M * 0.5), 0.3, 0.3)
    r = panel_displaced(moved, rest)
    assert not r.holds, r.detail


# ── panel_displaced: movement past threshold -> True ──────────────────────
def test_displaced_past_threshold():
    rest = (1.1, 0.3, 0.3)
    moved = (1.1 + (DISPLACEMENT_THRESHOLD_M * 3), 0.3, 0.35)
    r = panel_displaced(moved, rest)
    assert r.holds, r.detail


check("at_target_exact", test_at_target_exact)
check("at_target_within_tolerance", test_at_target_within_tolerance)
check("at_target_too_far", test_at_target_too_far)
check("at_target_wrong_orientation", test_at_target_wrong_orientation)
check("at_target_quat_sign_ambiguity", test_at_target_quat_sign_ambiguity)
check("displaced_no_movement", test_displaced_no_movement)
check("displaced_under_threshold", test_displaced_under_threshold)
check("displaced_past_threshold", test_displaced_past_threshold)
print("ALL SMOKE CHECKS PASSED")
