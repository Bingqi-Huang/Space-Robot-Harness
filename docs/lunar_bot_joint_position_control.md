# LunarBot arm gains JOINT_POSITION control (in addition to CARTESIAN_TWIST)

Built 2026-09-13, per the user's direction while reviewing Mission A's
feasibility: "机械臂应该再加上关节的位置控制，这也是必要的基础设施" (the arm
should also get joint-position control — this is necessary infrastructure
too). Spans both forks: `space_robotics_bench` (branch
`feat/switchable-arm-control`, `90f9d5e`) and `openral` (branch
`feat/arm-joint-position-control`).

## Why this came up: a feasibility check, not a plan

Before writing Mission A's natural-language instruction, a scripted
closed-loop pick-and-place attempt was run against `panel_remount` using
only the actuation that existed at the time (BODY_TWIST, CARTESIAN_TWIST,
GRIPPER_BINARY). It surfaced two real, previously-unconfirmed problems with
the base's `cmd_vel`, and more importantly, made the user (and this
project) reconsider whether an EE-velocity-only arm was ever going to
support the precision manipulation Mission A needs. Rather than push a
fragile velocity-control feasibility script further, the user's call was to
build the missing control mode properly first.

## The real architectural problem this solves

LunarBot's arm was driven only through `arm_ik`
(`DifferentialInverseKinematicsActionCfg`) in
`WheeledManipulatorActionGroup`. Simply adding a second, independent
`JointPositionActionCfg` term claiming the same 7 joints would **not**
have worked: Isaac Lab's `ActionManager` applies every declared action
term's `apply_actions()` unconditionally, every physics step — there is no
framework-level "pick one" mechanism. Two terms on the same joints would
silently fight over whose `set_joint_position_target()` call survives each
step, with whichever term happens to run later in the manager's internal
term order winning outright — completely undoing the other, every step,
forever. Confirmed by reading Isaac Lab's `ActionTerm`/`ActionManager`
source, not assumed.

**Fix: one action term, two internal sub-controllers, a mode flag** — this
was the user's own framing too: "真实机械臂都是这样的，随时切换控制策略。这都
是写在机械臂内部的控制器的" (real robotic arms work this way — switching
control strategy on demand, with that logic living inside the arm's own
controller). `SwitchableArmAction`
(`srb/core/action/term/manipulation/switchable_arm.py`) owns the arm's 7
joints as a single slot. Both the differential-IK controller and a direct
joint-position path are computed *every step*; a per-env mode flag (the
first element of the raw action vector) selects which result actually
reaches `set_joint_position_target()`. Switching modes never causes a
jump: the IK sub-controller's target is always recomputed from the
end-effector's *current measured* pose (the same property
`DifferentialInverseKinematicsAction` already has), so resuming IK mode
after a stretch of joint-position mode picks up from wherever the arm
actually is.

## What changed

### SRB (`space_robotics_bench`)

- New `srb/core/action/term/manipulation/switchable_arm.py` —
  `SwitchableArmAction` / `SwitchableArmActionCfg`. Raw action layout
  (`action_dim = 1 + 6 + 7 = 14`): `[0]` mode flag (>0.5 = joint-position
  mode), `[1:7]` IK sub-command (vx,vy,vz,wx,wy,wz, scaled by
  `ik_scale`), `[7:]` joint-position sub-command (7 absolute radian
  targets, scaled by `joint_pos_scale`).
- `WheeledManipulatorActionGroup`'s `arm_ik` field
  (`DifferentialInverseKinematicsActionCfg`) replaced with `arm`
  (`SwitchableArmActionCfg`). Teleop's `map_cmd_to_action` updated to
  always drive the arm in IK mode (mode flag `0.0`) with the 7
  joint-position sub-slots as an ignored placeholder — teleop's existing
  base/arm exclusivity toggle is unaffected.
- `lunarbot.py`'s action group instantiates `SwitchableArmActionCfg` with
  `ik_scale=0.1` (same value `arm_ik` used) and `joint_pos_scale=1.0`
  (direct radians passthrough — no calibration needed for this sub-mode,
  unlike the IK sub-mode).
- New wire topic: `.../robot/robot/switchable_arm`
  (`std_msgs/Float32MultiArray`, 14 floats) — the topic name comes from
  the action term's registered key, which turned out to derive from the
  **class name**, not the `ActionGroup`'s field name (a real, if minor,
  discovery while verifying this live — explains why the old topic was
  `.../differential_inverse_kinematics`, not `.../arm_ik`).

### OpenRAL

- `LunarBotSRBHAL` (`python/hal/src/openral_hal/lunar_bot_srb.py`) —
  `send_action` gains a `JOINT_POSITION` branch (`_send_joint_position`),
  alongside the existing `CARTESIAN_TWIST` one; both now publish to the
  single combined `arm_topic` (renamed from `arm_ik_topic`) with a `mode`
  flag distinguishing them. JOINT_POSITION is a direct radians passthrough
  (no HAL-side unit conversion, unlike CARTESIAN_TWIST's calibrated
  raw-unit conversion).
- **A real bug found and fixed during first live E2E test, not just in
  code review**: the C++ safety kernel's structural check
  (`validator.cpp`'s `is_joint_mode` branch) requires every JOINT_* chunk's
  `n_dof` to equal the envelope's *full* joint count (21 for LunarBot), not
  just the 7 arm joints being commanded — a pre-existing kernel
  requirement, unrelated to this work. The first implementation wrongly
  assumed that when `action.joint_names` names the 7 arm joints
  (ADR-0102), the wire row is *also* just 7-wide — it is not; the row is
  *always* 21-wide (steering/wheel/gripper slots zero-padded by the
  caller), and `joint_names` only marks which of those 21 slots the
  emitter meant. Live E2E testing caught this immediately (the arm didn't
  move at all — the HAL was throwing and dropping every JOINT_POSITION
  chunk); fixed by always resolving the 7 arm values from a full-width
  row via precomputed indices (`self._arm_joint_indices`, resolved from
  the manifest, not hardcoded).
- `robots/lunar_bot/robot.yaml` — `supported_control_modes` gains
  `joint_position`. Arm joints still declare no `position_limits` (no real
  RM-75 joint-range spec was available to source one from — not invented),
  so the safety kernel's JOINT_POSITION per-joint bound check (which does
  exist and does run for this mode, unlike CARTESIAN_TWIST/BODY_TWIST
  before this project's earlier fixes) resolves to ±inf for these 7
  joints today — a real, explicitly flagged gap, not a silent one.
- 5 new unit tests (13 total in the file) covering both JOINT_POSITION
  paths (`action.joint_names` set vs. absent, both correctly resolving
  against a full-width row) and both rejection cases (wrong joint names,
  wrong row width).

## Verified live, through the real safety-checked path

`candidate_action → C++ kernel → safe_action → openral_hal_lunar_bot →
SRB`, against `panel_remount env.robot=lunar_bot`:

- **JOINT_POSITION**: commanding `[0.4, -0.5, 0.1, 1.0, 0.1, 0.5, 0.1]`
  (a full 21-wide zero-padded chunk, `joint_names` naming the 7 arm
  joints) moved all 7 joints measurably toward those targets, no
  rejection.
- **CARTESIAN_TWIST regression**: still works unchanged after switching
  modes.
- **Mode switching, twice**: JOINT_POSITION → CARTESIAN_TWIST →
  JOINT_POSITION (commanding the stow pose `[0, -0.6, 0, 1.2, 0, 0.6, 0]`)
  — each switch took effect cleanly, arm converged toward the newly
  commanded mode's target both times, no jump, no fighting between modes.

(Isolated, pre-fix SRB-only verification, for reference: publishing
directly to `.../switchable_arm` with mode=1.0 moved `joint1` from ~-0.06
toward a commanded 0.5 target while the other 6 joints held their targets;
switching back to mode=0.0 with a small IK twist resumed smoothly with no
discontinuity in the end-effector pose.)

## What this does NOT cover

- No position limits for the 7 arm joints (see above) — a real, open gap.
- Multi-pedestal Mission A variant, bolt/screwdriver mechanics, and the
  base `cmd_vel` in-place-rotation problem found during the feasibility
  check are all still open, tracked separately.
- Mission A's plain-language instruction text and the generic-OpenRAL run
  (`execution_plan.md` §21 items 5–6) have not restarted yet — this was
  necessary infrastructure first, per the user's explicit "先把基础设施准
  备好" (get the infrastructure ready first, no rush).
