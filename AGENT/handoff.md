# Handoff

State as of 2026-09-13. Phase A complete. Phase B slices 1–2 verified live;
F15 closed as a false alarm; **F12 investigated, then FIXED** per the user's
explicit decision to implement it as part of this project's scientific
contribution. Task list: `todo.md`. Records: `docs/phase_b_lunar_bot_hal.md`,
`docs/phase_b_procedural_kind.md`, `docs/f12_body_twist_envelope_fix.md`.
Findings: `docs/research_findings.md`.

## F12: fixed, not just confirmed

`max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` were enforced by
**nothing** — each side of the kernel/supervisor split named the other as
responsible, and `kernel_params_from_envelope()` didn't even forward the
value. Live-confirmed pre-fix: `lunar_bot` at 6.0 m/s (20× the declared 0.3
m/s bound) moved the full distance, zero rejection.

**Fixed on branch `fix/body-twist-speed-envelope`** (off `f47e966`), scope
**BODY_TWIST only**:

- Python (`envelope_loader.py`): two new `EnvelopeIntersection` fields,
  `None`→`inf` resolution, tighten-only validation, and — the actual bug —
  `kernel_params_from_envelope()` now forwards both into the ROS params dict.
- C++ (`envelope.hpp`/`envelope.cpp`/`lifecycle_kernel.cpp`): mirrored struct
  fields, parameter declaration, parameter loading.
- C++ (`validator.cpp`): `kBodyTwist` split out of the shared
  "delegate to Python" case into its own real linear+angular magnitude
  check, mirroring `kCartesianTwist`'s existing structure exactly.
- Tests: 3 new gtest cases in `test_validator.cpp`
  (`BodyTwistLinearSpeedCapEnforced`, `BodyTwistAngularSpeedCapEnforced`,
  `BodyTwistDimMismatchRejected`); full `ctest` suite (4 binaries) passes,
  including the pre-existing `BodyTwistPassesWithSixDofWidthAndJointEnvelope`
  unmodified.
- **Re-verified live** against a real running `safety_kernel_node` (envelope
  params generated the sanctioned way, node driven through lifecycle
  services): the exact 6.0 m/s scenario is now rejected
  (`safety_status.latched=True, drop_reason=KIND_FORCE,
  detail="base_linear_speed"`, nothing on `/openral/safe_action`); 1.0 rad/s
  angular-only violation also rejected; 0.2 m/s / 0.2 rad/s in-bound command
  still passes through unchanged.

**Not in scope, still open**: `kJointTrajectory`/`kCartesianDelta`/
`kGripperBinary`/`kGripperPosition`/`kCompositeMode` still delegate to the
Python supervisor stub — same original gap, untouched, deliberately, to keep
this a single-purpose reviewable change. Full record:
`docs/f12_body_twist_envelope_fix.md`.

## Next

Commit + push this fix (branch `fix/body-twist-speed-envelope`), bump the
research repo's submodule pointer. Then, per the user's earlier instruction,
proceed to **Mission A** (plan §21 items 5–6): define a plain mission
instruction, run generic OpenRAL against it, save traces, document real
failure modes. Arm/gripper HAL wiring (CARTESIAN_TWIST/GRIPPER_BINARY) is
still open too, whenever it's next needed.

## Environment reference (reusable, don't rediscover)

- SRB / kernel / HAL / runner launch: `docs/srb_integration_notes.md` §2,
  `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_procedural_kind.md`.
- Standalone kernel bring-up (no SRB/HAL needed to test the kernel itself):
  `docs/f12_body_twist_envelope_fix.md`'s "Live" section — generate params
  via `compute_intersection()`+`kernel_params_from_envelope()`, launch
  `install/lib/openral_safety_kernel/safety_kernel_node --ros-args
  --params-file <path>`, drive lifecycle via direct `ChangeState`/`GetState`
  service calls, publish `ActionChunk` directly on `candidate_action`.
- `RskillRunnerNode` is constructed directly in Python — mirror `compose.py`:
  construct with `skill_resolver=None`, then swap `node._skill_resolver =
  make_default_skill_resolver(node, search_paths=["rskills"])` before
  `configure()`.
- Any shell calling `ros2 action send_goal`/`topic echo`/`topic hz` on an
  `openral_msgs` interface needs both `/opt/ros/humble/setup.bash` and
  `install/setup.bash` sourced.
- When checking a topic's publish rate, redirect `ros2 topic hz` to a file
  instead of piping through `tail`/`grep` — piping after a `timeout` kill
  loses the buffered output and reads as "zero messages" even when the
  topic is publishing fine.
- Colcon rebuild of the safety kernel: conda stripped from env (`env -u
  CONDA_PREFIX ...` + miniconda stripped from `PATH`), `--merge-install`
  (this workspace's `install/` layout), both `PYTHON_EXECUTABLE` and
  `Python3_EXECUTABLE` pointed at `.venv/bin/python`.

## Watch out

- **Never `pkill -f` on this host** — exact PIDs only, every time, including
  the reparented kit-python child.
- A bare `time.sleep()` before reading a ROS subscription callback's result
  is a race — the callback never fires without `rclpy.spin_once`/
  `spin_until_future_complete`, so a stale TRANSIENT_LOCAL message (e.g. the
  kernel's own activation-time `safety_status`) can be misread as the
  response to whatever you just did. Spin through the wait, don't sleep
  through it.
- `space_robotics_bench/` stays untouched — read/run only, ever.
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
