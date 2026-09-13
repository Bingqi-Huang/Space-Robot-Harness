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
`feat/lunar-bot-arm-gripper` (current, **not yet committed** as of this
handoff — see Next). All still open; none merged yet.

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

## Next

1. Commit + push the current uncommitted work on `feat/lunar-bot-arm-gripper`
   (C++ angular-speed fix, `LunarBotSRBHAL` arm/gripper dispatch, lifecycle
   node transport, `robot.yaml` updates, new unit tests, the two new docs).
   Bump the research repo's submodule pointer + commit there too.
2. Then proceed to **Mission A** (plan §21 items 5–6): define a plain
   mission instruction (needs manipulation now that it's wired, per
   `execution_plan.md` §6.4), run generic OpenRAL against it, save traces,
   document real failure modes.
3. Still open, not blocking Mission A: the same missing-magnitude-check gap
   for `kJointTrajectory`/`kCartesianDelta`/`kGripperBinary` (per-joint)/
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
- `space_robotics_bench/` stays untouched — read/run only, ever (reading it
  to understand SRB's real action mechanics, as done for this slice, is
  fine and expected; editing/committing is not).
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
