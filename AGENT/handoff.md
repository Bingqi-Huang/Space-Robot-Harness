# Handoff

State as of 2026-09-13. Phase A complete. Phase B slices 1–3 done and
verified live: LunarBot is now a genuine mobile manipulator — base
(BODY_TWIST), arm (CARTESIAN_TWIST), and gripper (GRIPPER_BINARY) all drive
through the real safety chain from one unified HAL. F12, F16 (a second
instance of F12's bug class, for CARTESIAN_TWIST's angular bound) both
fixed; F15 closed as a false alarm; F17 (multi-node estop reset) documented.
Task list: `todo.md`. Records: `docs/phase_b_lunar_bot_hal.md`,
`docs/phase_b_procedural_kind.md`, `docs/f12_body_twist_envelope_fix.md`,
`docs/phase_b_lunar_bot_arm_gripper.md`. Findings: `docs/research_findings.md`.

## Where things stand

Branch chain: `feat/py310-humble` → `feat/lunar-bot-hal` (`f47e966`) →
`fix/body-twist-speed-envelope` (`fabe588`, pushed) →
`feat/lunar-bot-arm-gripper` (`af8fba2`, pushed). All still open; none
merged yet.

**`space_robotics_bench/` is now a real git submodule** (`docs/upstream_pins.md`),
pinned at `9caeb46`, same discipline as `openral/` — the agent that
developed it independently no longer manages it, so this project now
edits/commits there directly.

`LunarBotSRBHAL.send_action` now dispatches BODY_TWIST / CARTESIAN_TWIST /
GRIPPER_BINARY. The arm's SRB action (`differential_inverse_kinematics`) is
NOT a native velocity controller — it's a scaled per-step position delta
recomputed from the current measured pose every step (confirmed by reading
Isaac Lab's own source, not guessed from the `Twist` message type); holding
a constant raw value produces continuous motion proportional to its
magnitude (functionally a velocity from outside), so the HAL converts using
empirically-measured (pose-dependent, deliberately conservative)
constants — see `docs/phase_b_lunar_bot_arm_gripper.md` for the full table.
The gripper's `binary_joint_position` Bool is **inverted**: `True` = close,
`False` = open (confirmed live). Both facts came from reading
`space_robotics_bench/` read-only (never modified) plus the vendored Isaac
Lab source at `~/isaaclab/`.

While wiring the arm, found F16: `max_ee_angular_speed_rad_s` (CARTESIAN_
TWIST's angular bound) had the exact same "declared, not enforced" gap F12
found for BODY_TWIST — fixed the same way, verified live end-to-end.

## Next — Mission A needs a new SRB task; none exist for LunarBot today

Investigated (2026-09-13) what SRB task could serve as Mission A (plan §6.4:
infrastructure inspection/maintenance, plain instruction not action
sequence). **Finding: nothing usable exists yet.**

- `_ground_manipulation` (what Phase B's HAL tests reused) is a bare
  scaffold — no objects, no fault, no success condition.
- Every task with real objects/rewards (`solar_panel_assembly`,
  `screwdriving`, `peg_in_hole_assembly`, `sample_collection`, `excavation`)
  is built on `ManipulationEnv` (`robot: Manipulator`) — fixed-base arms
  only, type-incompatible with LunarBot's `WheeledManipulator`.
- The one mobile-manipulator task, `mobile_debris_capture`, is built on
  `OrbitalManipulationEnv` — a free-flying orbital arm, not a ground rover.
- None of SRB's existing tasks have a real binary success/termination
  condition anyway (`termination = torch.zeros(...)`, always) — this
  project's own verification layer (plan §4.4) was always going to have to
  supply that regardless of which scene gets picked.

Decided: write Mission A's task directly inside `space_robotics_bench/`
(`srb/tasks/mobile_manipulation/`), following the `solar_panel_assembly`
pattern but rebased onto `GroundManipulationEnv` for `lunar_bot`. Reuse
existing assets — `solar_panel.usdz`, `industrial_pedestal_*.usdz`,
`bolt_hex_m8`/`nut_hex_m8` (has a "tight" variant — a loosened-bolt fault is
right there), `screwdriver_hex_m3/m5.usdz` — all already in
`assets/srb_assets/object/`. Task registration (`register_srb_tasks` →
`gymnasium.register`) isn't restricted to files inside SRB's own tree, but
since we now own this fork, there's no reason to register externally —
put it where `solar_panel_assembly` etc. already are.

**Not yet started**: the actual task/scene file, and defining the plain-
English mission instruction text itself (plan §21 item 5) once the scene
exists. Then run generic/unmodified OpenRAL against it and save traces
(item 6) — that's what should motivate `space_runtime`'s first schemas
(item 7), not intuition.

Still open, not blocking: the same missing-magnitude-check gap for
`kJointTrajectory`/`kCartesianDelta`/`kGripperBinary` (per-joint)/
`kGripperPosition`/`kCompositeMode` (F12/F16's sibling gap, untouched).

## Environment reference (reusable, don't rediscover)

- SRB / kernel / HAL / runner launch: `docs/srb_integration_notes.md` §2,
  `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_lunar_bot_arm_gripper.md`.
- Standalone kernel bring-up (no SRB/HAL needed to test the kernel itself):
  `docs/f12_body_twist_envelope_fix.md`'s "Live" section.
- To read SRB's actual action-term mechanics (not just the topic/message
  type, which can mislead — see the arm/gripper facts above), the vendored
  Isaac Lab source lives at `~/isaaclab/source/isaaclab/isaaclab/envs/mdp/
  actions/` and `~/isaaclab/source/isaaclab/isaaclab/controllers/` on this
  host — read it, don't guess from `srb/core/action/`'s thin wrapper alone.
- **F17 — multi-node estop reset**: the kernel's `/openral/estop_reset`
  service only clears the kernel's own latch. Every other node that latched
  on `/openral/estop` (e.g. a HAL lifecycle node) stays latched and
  silently drops commands until `/openral/estop_cleared` (`std_msgs/Empty`)
  is also published — normally the operator dashboard's job. Any test
  script driving the kernel directly must publish it too after every reset.
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
  is a race — spin through the wait (`rclpy.spin_once` in a loop), don't
  sleep through it, or a stale TRANSIENT_LOCAL message gets misread as a
  fresh response.
- `space_robotics_bench/` is now a real git submodule, formally pinned like
  `openral/` (2026-09-13) — the agent that developed it independently no
  longer manages it, so editing/committing there is fine now, same branch +
  commit discipline as `openral/`. (This reverses the earlier "read/run
  only" rule from Phase B slices 1–3 — that was about not colliding with
  concurrent work, not a permanent restriction.)
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
