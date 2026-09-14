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

### Then, per plan §21 items 5–6 — new SRB task built, item 6 in progress

No existing SRB task fit Mission A + LunarBot (bare `_ground_manipulation`
scaffold, or fixed-base-only `ManipulationEnv` tasks, or the one
mobile-manipulator task being orbital) — full investigation in
`docs/mission_a_panel_remount.md`.

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
flat within ~4 m of the env origin (`flat_area_size` in `env_cfg.py`);
outside it PhysX's depenetration ejection flings a spawned object forever.
Fixed by keeping pedestal/panel within ~1.5 m of origin; confirmed live.

**Deliberate v1 simplification**: one pedestal+panel pair, not §6.4's
"multiple candidate components" (would need genuine fault-identification
across several instances) — a natural, cheap follow-up once this is proven.

- [x] Write the new task/scene inside `space_robotics_bench/`.
- [x] Define Mission A's plain-language instruction text — written in
      `docs/mission_a_panel_remount.md`. **Not to be used yet** — user
      directive 2026-09-14: Mission A does not start until its
      prerequisites exist (execution_plan rule 0.11).
- [ ] Run generic OpenRAL against Mission A — **deferred behind Phase B2**
      (F21: no manipulation rSkill, no sensors wired, reasoner never in
      the loop for this robot). Plan revised 2026-09-14: execution_plan
      §6.2/§6.4/§8.1/§8.3/§9.1/§18/§21.

### Phase B2 — LunarBot capability set (execution_plan §8.3) — IN PROGRESS

Design + reuse survey: `docs/lunar_bot_capability_set_plan.md`. Branch
`openral/feat/lunar-bot-capability-set`. Build order (each verified live):

- [x] 1. RM-75 limits in `robot.yaml` (`f7b5ccd`, F22) — kernel rejects
      out-of-range JOINT_POSITION live.
- [ ] 2. Sensor bridge: SRB cameras/depth/IMU/truth pose → `/openral/cameras/*`,
      `/odom`, `map→odom→chassis_base_link` TF; `sensors:` in manifest;
      `panel_remount_visual` needs ≥640×480 + depth on `cam_front`.
- [ ] 3. Procedural rSkills `move_joints` / `move_ee_to_pose` / `grasp` /
      `release` / `stow` (tag `lunar_bot`); scripted remount closes the loop.
- [ ] 4. F19 fix in SRB `FourWheelSteer` (drive ∝ cos(steer error)).
- [ ] 5. Nav2 via `openral_nav2_bringup`; costmap source = RGB-D →
      `octomap_server` `/map` unless the real robot has a lidar (**ask**);
      `/cmd_vel → candidate_action` relay so the kernel bounds Nav2.
- [ ] 6. MoveIt for RM-75 (license check on RealMan `ros2_rm_robot` first).
- [ ] 7. Mission verifier node (this repo) on simulator truth.
- [ ] 8. Launch orchestration + §19 run-manifest writer (this repo).
- [ ] 9. Remaining kernel magnitude checks (`kJointTrajectory` first).
- [ ] B3: reasoner-in-the-loop two-step run with full trace = Phase B exit.

A scripted pick-and-place feasibility check against `panel_remount` (run
before trusting the instruction text) found **F19** (base `cmd_vel` drifts
on large in-place turns — revised root cause: no steer-before-drive
sequencing, fix planned in B2 item 4) and led to **JOINT_POSITION arm
control ✅ (2026-09-13)**: `SwitchableArmAction` in SRB
(`feat/switchable-arm-control` `90f9d5e`) — one action term, IK and
joint-position sub-controllers both computed every step, a mode flag picks
which is applied — plus the HAL branch (`feat/arm-joint-position-control`
`a785b88`). **F20** found + fixed live (JOINT_* wire rows are always the
full 21-wide vector). Full record: `docs/lunar_bot_joint_position_control.md`.
The "no arm position limits" gap noted there is now closed (F22).

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
