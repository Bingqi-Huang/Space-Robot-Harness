# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

A0–A4 done. See `docs/research_findings.md` before designing any mechanism.

---

## Phase B: Generic OpenRAL on SRB — in progress

Per execution_plan.md §18 Phase B. Embodiment: **LunarBot** (user directive).

### Slices 1–3 — LunarBot mobile-manipulator HAL, all ✅ (2026-09-13)

Full records: `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_procedural_kind.md`,
`docs/phase_b_lunar_bot_arm_gripper.md`. All verified live through the real
candidate_action→kernel→safe_action→HAL→SRB path. One-line-each findings
(full write-ups in `docs/research_findings.md`):

- **F11** — added a genuine `kind: "procedural"` rSkill (Baseline A needs
  it too); `ProceduralBodyTwistRskill` verified through the real
  `ExecuteRskill` action server.
- **F15** — RESOLVED as a false alarm: kernel heartbeats
  `/openral/safety_status` fine at 1 Hz; the "zero messages" reading was a
  shell-piping artifact. Do not spend more effort on this.
- **F12** — FIXED: `max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s`
  were declared but enforced by nothing; fixed in `kBodyTwist`, scope
  BODY_TWIST only (`docs/f12_body_twist_envelope_fix.md`).
- **F16** — FIXED: CARTESIAN_TWIST's `max_ee_angular_speed_rad_s` had the
  same gap as F12; fixed the same way, verified live.
- **F17** — the kernel's `/openral/estop_reset` doesn't clear other nodes
  latched on `/openral/estop` — also publish `/openral/estop_cleared`. See
  "Watch out" below.

Built: `LunarBotSRBHAL` dispatches BODY_TWIST/CARTESIAN_TWIST/GRIPPER_BINARY
(now also JOINT_POSITION, see below); arm's raw-unit conversion is
empirically calibrated (pose-dependent for a 7-DoF arm, unlike the base);
gripper's SRB wire convention is inverted (`True`=close). `kJointTrajectory`/
`kCartesianDelta`/`kGripperBinary`(per-joint)/`kGripperPosition`/
`kCompositeMode` still delegate to an unlaunched Python stub — same F12/F16
gap, untouched, still open.

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

**Before that: a scripted pick-and-place feasibility check was run against
`panel_remount`** (before writing the instruction text) to confirm the
mission is achievable at all with current actuation, not "necessarily
fails" as the user rightly worried it might. Found: **F19** — the base's
`cmd_vel` drifts incoherently on a large in-place turn (likely the 4WIS
±120° steering limit saturating), not yet resolved. Also, per the user's
explicit direction, **JOINT_POSITION control was added for the arm** (see
below) — CARTESIAN_TWIST alone wasn't going to support the precision
manipulation Mission A needs.

### JOINT_POSITION arm control ✅ (2026-09-13)

openral branch `feat/arm-joint-position-control`; SRB branch
`feat/switchable-arm-control` (`90f9d5e`). Full record:
`docs/lunar_bot_joint_position_control.md`.

Two independent SRB action terms both claiming the arm's 7 joints would
silently fight every step (Isaac Lab's `ActionManager` applies every
declared term unconditionally — no "pick one" mechanism). Built
`SwitchableArmAction`: one action term, both IK and joint-position
sub-controllers computed every step, a per-env mode flag picks which
result is actually applied — "real robotic arms work this way, the
mode-switch logic lives inside the arm's own controller" (the user's own
framing). **F20 — found + fixed live**: the safety kernel forces every
JOINT_* chunk to be the full 21-wide vector regardless of
`action.joint_names`; a first HAL implementation wrongly assumed a 7-wide
row when `joint_names` was set, silently dropping every JOINT_POSITION
dispatch (caught immediately by live E2E testing, not code review — the
unit tests written first encoded the same wrong assumption and passed).
Verified live through the real safety chain: JOINT_POSITION moves the arm,
CARTESIAN_TWIST still works, mode-switching (twice) is clean with no jump.
**Gap, flagged not silent**: arm joints declare no `position_limits` (no
real RM-75 spec available), so the kernel's JOINT_POSITION per-joint check
— which does exist and run, unlike CARTESIAN_TWIST/BODY_TWIST before this
project's earlier fixes — resolves to ±inf for these 7 joints today.

---

## Rules

- Branch or worktree per task; delete after **merge** (AGENT.md §1) —
  openral: `feat/lunar-bot-hal` → `fix/body-twist-speed-envelope` →
  `feat/lunar-bot-arm-gripper` → `feat/arm-joint-position-control`; SRB:
  `feat/panel-remount-mission-a` → `feat/switchable-arm-control` — all
  stay open, Phase B is still landing on them.
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
