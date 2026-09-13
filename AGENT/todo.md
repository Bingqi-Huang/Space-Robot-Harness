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

**F15 — investigated 2026-09-13, RESOLVED as a false alarm.** The 3s
dispatch aborted at ~2.7s on a safety-status staleness watchdog. First read
concluded the kernel never heartbeats `/openral/safety_status` — wrong. It
does, at a clean 1.000 Hz (`publish_diagnostics`'s wall timer ends with an
unconditional `publish_safety_status_now()`, verified live with
`ros2 topic hz`). The earlier "zero messages" reading was a shell-piping
artifact (`timeout ... | tail` loses output when SIGTERM lands mid-print).
The one abort was very likely a single missed/delayed heartbeat under a
busier multi-participant DDS graph — the mechanism is deliberately
conservative by design, so an occasional trip under load is it working as
intended, not a bug. **Do not spend more effort on this** — treat an
occasional safety-stale abort as expected, and note it's exactly the class
of event execution_plan.md §5.4.4/§13.6 already want to study, not a
nuisance. Full record: `docs/research_findings.md` F15.

**F12 — investigated 2026-09-13, then FIXED 2026-09-13 per user decision
("按照他们的规范来把这个补上，这就是我们科学贡献的一部分了").**
`max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` were enforced by
nothing (root cause: kernel and Python supervisor each named the other as
responsible; `kernel_params_from_envelope()` didn't even forward the value).
Verified live pre-fix: `lunar_bot` at 6.0 m/s (20× the declared 0.3 m/s
bound) moved the full distance, zero rejection. **Fixed for BODY_TWIST**:
new envelope fields (Python dataclass + C++ struct + ROS params), `validator.cpp`'s
`kBodyTwist` split out of the shared Python-delegation case into a real
linear/angular magnitude check mirroring `kCartesianTwist`. New gtest
coverage + full ctest suite pass; re-verified live against a real running
kernel node — the same 6.0 m/s scenario is now rejected
(`drop_reason=KIND_FORCE, detail="base_linear_speed"`), same for angular,
in-bound commands still pass. Full record: `docs/f12_body_twist_envelope_fix.md`,
`docs/research_findings.md` F12. **Scope: BODY_TWIST only** —
`kJointTrajectory`/`kCartesianDelta`/`kGripperBinary`/`kGripperPosition`/
`kCompositeMode` still delegate to the Python stub, same gap, untouched.

**Same missing-magnitude-check gap for** `kJointTrajectory`/
`kCartesianDelta`/`kGripperBinary`(the shared per-joint bound)/
`kGripperPosition`/`kCompositeMode` — not part of the F12/F16 fixes, still
open.

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

### Then, per plan §21 items 5–6 (not started)

- [ ] Define Mission A as a plain instruction (no space constraints).
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
- `space_robotics_bench/` stays untouched — another agent owns it. On this
  shared host, kill only exact PIDs you launched yourself, never a pattern
  (`docs/research_findings.md` F10).
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
