# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

A0–A4 done. See `docs/research_findings.md` before designing any mechanism.

---

## Phase B: Generic OpenRAL on SRB — in progress

Per execution_plan.md §18 Phase B. Embodiment: **LunarBot** (user directive).

### Slice 1 — LunarBot BODY_TWIST through the real safety chain ✅

`docs/phase_b_lunar_bot_hal.md`. New HAL (`LunarBotSRBHAL` +
`openral_hal_lunar_bot`) bridges candidate_action → C++ safety kernel →
safe_action → SRB's `cmd_vel`. Verified live.

### Slice 2 — `kind: "procedural"` rSkill + F11 resolved ✅ (2026-09-13)

openral branch `feat/lunar-bot-hal` (`f47e966`, pushed, **not yet merged**).
Full record: `docs/phase_b_procedural_kind.md`.

Added a genuine, permanent `RSkillKind` — deterministic/non-learned
actuators, needed anyway for Baseline A (§5.2). `ProceduralBodyTwistRskill`
verified live through the **real** `ExecuteRskill` action server (not
`ROSPublishingHAL` called directly): `ros2 action send_goal` → resolver →
skill → candidate_action → kernel → safe_action → HAL → SRB → robot moved.

**F15 — RESOLVED as a false alarm.** A 3s dispatch aborted at ~2.7s on a
safety-status staleness watchdog; first read wrongly concluded the kernel
never heartbeats `/openral/safety_status`. It does, at a clean 1.000 Hz —
the "zero messages" reading was a shell-piping artifact
(`timeout ... | tail` loses output when SIGTERM lands mid-print). **Do not
spend more effort on this.** Full record: `docs/research_findings.md` F15.

**F12 — FIXED 2026-09-13** per user decision ("按照他们的规范来把这个补上").
`max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` were declared but
enforced by nothing. Fixed in `validator.cpp`'s `kBodyTwist` case (real
magnitude check, mirroring `kCartesianTwist`); re-verified live — 6.0 m/s
(20× the declared bound) now rejected. Full record:
`docs/f12_body_twist_envelope_fix.md`, `docs/research_findings.md` F12.
**Scope: BODY_TWIST only** — `kJointTrajectory`/`kCartesianDelta`/
`kGripperBinary`/`kGripperPosition`/`kCompositeMode` still delegate to the
unlaunched Python stub, same gap, untouched.

### Slice 3 — Arm + gripper unified into one mobile-manipulator HAL ✅ (2026-09-13)

openral branch `feat/lunar-bot-arm-gripper` (off `fix/body-twist-speed-
envelope`). Full record: `docs/phase_b_lunar_bot_arm_gripper.md`.

SRB side (arm/gripper action wiring) is done, per the user — read-only
confirmed the actual mechanism (Isaac Lab source, not just the topic type):
the arm's `differential_inverse_kinematics` is a scaled per-step position
delta, NOT a native rate, and the gripper's `binary_joint_position` Bool is
**inverted** (`True` = close). Both confirmed live before writing HAL code.

**F16 — found + fixed before trusting the new arm wiring**: CARTESIAN_TWIST's
angular-speed bound (`max_ee_angular_speed_rad_s`, already declared on
`panda_mobile`) had the exact same "declared, not enforced" shape as F12 —
fixed the same way (kernel now checks it in `kCartesianTwist`), verified
live through the **full** candidate_action→kernel→safe_action→HAL→SRB path
(not just the isolated kernel).

Built: `LunarBotSRBHAL.send_action` now dispatches BODY_TWIST /
CARTESIAN_TWIST / GRIPPER_BINARY; `openral_hal_lunar_bot`'s transport gained
arm_ik + hand publishers; `robot.yaml` declares `max_ee_speed_m_s: 0.2` /
`max_ee_angular_speed_rad_s: 0.3` (conservative, empirically-calibrated —
see the doc for the measured raw↔physical-unit table, which is genuinely
pose-dependent for a 7-DoF arm, unlike the base). 9 new unit tests (real
manifest + injected publish_fn) + full live E2E: in-bound arm motion, both
linear and angular over-limit rejection, gripper open/close (full chain,
correct direction), BODY_TWIST regression — all confirmed.

**F17 — found**: resetting the kernel's `/openral/estop_reset` does NOT
clear other nodes latched on `/openral/estop` — needs a separate
`/openral/estop_cleared` broadcast too (normally the dashboard's job, a
deliberate human-in-the-loop step). See "Watch out" below.

### Then, per plan §21 items 5–6 — blocked on a new SRB task (in progress)

Investigated 2026-09-13: no existing SRB task fits Mission A + LunarBot.
`_ground_manipulation` is a bare scaffold; every task with real objects
(`solar_panel_assembly`, `screwdriving`, `peg_in_hole_assembly`, etc.) is
`ManipulationEnv`-only (fixed-base arm, type-incompatible with LunarBot's
`WheeledManipulator`); the one mobile-manipulator task
(`mobile_debris_capture`) is `OrbitalManipulationEnv` (orbital, not ground).

**`panel_remount` task written and verified live ✅ (2026-09-13)**, in
`space_robotics_bench/srb/tasks/mobile_manipulation/panel_remount/`
(submodule commit — see `docs/upstream_pins.md`). A solar panel knocked off
its pedestal mount; robot must locate it, pick it up, place it back within
tolerance — mirrors `solar_panel_assembly`'s structure on
`GroundManipulationEnv` instead of the fixed-base `ManipulationEnv`. Has a
genuine binary success termination (position + orientation tolerance, a
real `torch.jit.script` bool check) — no existing SRB task has one at all.
Full record: `docs/mission_a_panel_remount.md`.

**F18 — found + fixed**: SRB's procedural moon terrain is only reliably
flat within ~4 m of the env origin (`flat_area_size` in `env_cfg.py`); the
first placement (2.4–3.0 m out) spawned the panel embedded in uneven
terrain, and PhysX's depenetration ejection sent it falling forever
(`z=-2637` and counting). Fixed by keeping pedestal/panel within ~1.5 m of
origin; panel now settles to a stable rest pose, confirmed live. Documented
in the task file and `docs/research_findings.md` so it's not rediscovered.

**Deliberate v1 simplification**: one pedestal+panel pair, not §6.4's
"multiple candidate components" (would need genuine fault-identification
across several instances) — a natural, cheap follow-up once this is proven.

- [x] Write the new task/scene inside `space_robotics_bench/`.
- [ ] Define Mission A's plain-language instruction text (no space
      constraints yet — that's Phase D).
- [ ] Run generic OpenRAL against it; save traces; document real failure
      modes — this is what should motivate `space_runtime`'s first schemas,
      not intuition.

---

## Rules

- Branch or worktree per task; delete after **merge** (AGENT.md §1) —
  `feat/lunar-bot-hal` → `fix/body-twist-speed-envelope` →
  `feat/lunar-bot-arm-gripper` all stay open; Phase B is still landing on them.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3).
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code until Phase B observes real
  failures calling for it** (plan §21.6–7).
- `space_robotics_bench/` is now a real git submodule (`docs/upstream_pins.md`,
  2026-09-13) — the agent that developed it independently no longer manages
  it, so it is fair game to edit/commit like `openral/`, same branch-per-task
  + commit discipline. On this shared host, kill only exact PIDs you launched
  yourself, never a pattern (`docs/research_findings.md` F10).
- `ros2 lifecycle`/`node list` don't work on this host — use direct
  `lifecycle_msgs/srv/ChangeState`/`GetState` service calls (F14).
- Any shell running `ros2 action send_goal`/`topic echo` on an
  `openral_msgs`-typed interface needs **both**
  `/opt/ros/humble/setup.bash` **and** `install/setup.bash` sourced, every
  time — a fresh Bash call starts with neither.
- Resetting the kernel's `/openral/estop_reset` does NOT clear other nodes
  latched on `/openral/estop` — also publish `std_msgs/Empty` on
  `/openral/estop_cleared` (F17), or every HAL downstream of the first
  violation stays silently inert for the rest of the session.
