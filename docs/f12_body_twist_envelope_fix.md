# F12 fix — BODY_TWIST magnitude bounds now enforced in the C++ safety kernel

Fixed 2026-09-13 on openral branch `fix/body-twist-speed-envelope` (off
`f47e966`). Per the user's explicit decision: implement this properly,
following OpenRAL's own engineering standards (CLAUDE.md §3 — safety-kernel
changes need review discipline, tests, and a hazard-log-equivalent record),
as part of this project's scientific contribution — not a silent local patch.

## The gap this closes

`docs/research_findings.md` F12 (confirmed, then live-tested): every robot's
`robot.yaml` declares `safety.max_base_linear_speed_m_s` /
`max_base_angular_speed_rad_s`, but nothing enforced them. The C++ kernel's
`validate()` explicitly delegated BODY_TWIST (and five other per-mode control
modes) to the Python `openral_safety/supervisor_node.py`, whose own docstring
said the opposite — it was a Day-1 stub waiting for the C++ kernel. Neither
side did it. `kernel_params_from_envelope()` did not even forward the values
into the kernel's ROS parameters, so there was nowhere for the value to land.
Live-confirmed pre-fix: `lunar_bot` commanded at 6.0 m/s (20× its declared 0.3
m/s bound) moved the full distance with zero rejection.

**Scope of this fix: BODY_TWIST only.** The same gap for
`kJointTrajectory`/`kCartesianDelta`/`kGripperBinary`/`kGripperPosition`/
`kCompositeMode` is untouched and still open — those modes' per-axis bounds
still have no enforcement anywhere. Fixing BODY_TWIST was in scope because
it's the control mode `lunar_bot`'s base actually uses today (Phase B slice
1); the others weren't touched to keep this a reviewable, single-purpose
change rather than a large multi-mode rewrite.

## What changed

### Python (`packages/openral_safety/openral_safety/envelope_loader.py`)

- `EnvelopeIntersection` dataclass gained `max_base_linear_speed_m_s: float`
  and `max_base_angular_speed_rad_s: float`, with the same `None` →
  `math.inf` sentinel convention the C++ side's `kPosInfinity` already used
  for every other optional bound (`_resolve_optional_bound()` helper).
- `_validate_envelope_tightens()` extended to check these two fields too
  (a skill-level envelope may only tighten a robot's ceiling, never loosen
  it — same rule as every other bound).
- `compute_intersection()`'s `_pick_min_optional()` closure resolves the
  robot/skill intersection for both fields.
- `kernel_params_from_envelope()` now actually emits both as ROS parameters
  (previously it silently dropped `max_base_linear_speed_m_s` and never
  had `max_base_angular_speed_rad_s` at all — half of why nothing could
  enforce them even if the kernel wanted to).
- Validated with a standalone script: `lunar_bot` (bounds declared) resolves
  to `0.3`/`0.5` correctly; `ur5e` (bounds not declared, fixed-base arm)
  resolves to `inf` without error, and both appear in the params dict either
  way.

### C++ (`cpp/openral_safety_kernel/`)

- `include/openral_safety_kernel/envelope.hpp` — `EnvelopeIntersection`
  struct gained the same two fields, defaulting to `kPosInfinity` (mirrors
  `max_ee_speed_m_s` exactly) — an unconfigured robot's behavior is provably
  unchanged.
- `src/lifecycle_kernel.cpp` — declares the two new ROS parameters at
  construction (CLAUDE.md §1.4: declare at construction, don't depend on
  launch-file presence), default `kPosInfinity`.
- `src/envelope.cpp` — `load_envelope_from_ros_parameters()` reads both
  parameters into the struct.
- `src/validator.cpp` — `kBodyTwist` split out of the shared "delegate to
  Python" case (previously grouped with `kJointTrajectory`/`kCartesianDelta`/
  `kGripperBinary`/`kGripperPosition`/`kCompositeMode`) into its own case,
  mirroring the existing `kCartesianTwist` case's structure exactly: each
  step's 6-vector `(vx, vy, vz, wx, wy, wz)` yields
  `linear_speed = sqrt(vx²+vy²+vz²)` checked against
  `max_base_linear_speed_m_s`, and `angular_speed = sqrt(wx²+wy²+wz²)`
  checked against `max_base_angular_speed_rad_s`. A violation returns a
  `Violation{kind: kForce, field: "base_linear_speed"|"base_angular_speed"}`
  — same shape every other magnitude violation uses, so the kernel's
  existing latch/estop/`FailureTrigger`/`SafetyStatus` publishing path needs
  no changes.
- `test/test_validator.cpp` — three new gtest cases:
  `BodyTwistLinearSpeedCapEnforced` (the exact 6.0 vs 0.3 m/s live-test
  scenario), `BodyTwistAngularSpeedCapEnforced` (1.0 vs 0.5 rad/s, linear
  in-bound), `BodyTwistDimMismatchRejected` (row width < 6 still rejected as
  a structural error, unrelated to the new magnitude check). The pre-existing
  `BodyTwistPassesWithSixDofWidthAndJointEnvelope` (0.1 m/s against an
  envelope that never sets the new fields, so they default to
  `kPosInfinity`) was left unmodified and still passes — proof the new
  fields are opt-in-by-declaration, not a behavior change for any robot that
  doesn't set them.

## Verification

- `colcon build --merge-install --packages-select opentelemetry_cpp_vendor
  openral_safety_kernel` (conda stripped from env, `PYTHON_EXECUTABLE` +
  `Python3_EXECUTABLE` both pointed at the workspace venv) — clean build.
- `ctest` in `build/openral_safety_kernel`: all 4 binaries pass
  (`test_validator`, `test_collision`, `test_no_alloc`,
  `test_lifecycle_kernel`) — the new tests plus the full pre-existing suite,
  no regressions.
- **Live, against a real running `safety_kernel_node`** (no SRB/HAL in this
  pass — isolates the kernel's actual parameter-load → validate() wiring,
  already the thing ctest's pure-function tests can't reach on their own).
  Envelope parameters generated the sanctioned way
  (`compute_intersection()` + `kernel_params_from_envelope()` against the
  real `robots/lunar_bot/robot.yaml`, dumped to a ROS params YAML, loaded via
  `--ros-args --params-file`), node driven through
  `configure()`/`activate()` via direct `lifecycle_msgs` service calls (`ros2
  lifecycle` doesn't enumerate nodes on this host — F14):
  - Linear 6.0 m/s (vs. declared 0.3 m/s bound): **rejected** —
    `safety_status.latched=True, drop_reason=KIND_FORCE,
    detail="base_linear_speed"`; zero messages on `/openral/safe_action`.
  - Angular 1.0 rad/s (vs. declared 0.5 rad/s bound), linear in-bound:
    **rejected** — same shape, `detail="base_angular_speed"`.
  - Linear 0.2 m/s + angular 0.2 rad/s (both in-bound): **passed through** —
    one message on `/openral/safe_action`, `flat` unchanged from what was
    published, `safety_status.latched` stays `False`.
  - Between each rejection and the next test: `/openral/estop_reset` service
    call (kernel's `estop_reset_cooldown_s` default is 0.5s) — confirms the
    kernel's existing latch/reset contract is unaffected by this change.

## What this does NOT cover

- `kJointTrajectory`/`kCartesianDelta`/`kGripperBinary`/`kGripperPosition`/
  `kCompositeMode` still delegate to the Python supervisor stub — same gap,
  untouched. A future fix following this exact pattern (new envelope fields
  already exist for some of these, e.g. `max_ee_speed_m_s` for Cartesian
  modes already works via `kCartesianTwist`; gripper/joint-trajectory bounds
  would need their own manifest fields first).
- No change to the Python `supervisor_node.py` stub itself — it's now
  redundant for BODY_TWIST specifically, but left as-is since removing it
  is a separate decision (it may still matter for a deployment that runs the
  Python supervisor without this C++ kernel).
- No change to workspace/collision/force checks — unaffected, already real
  per F12's original investigation.
