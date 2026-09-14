# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

A0–A4 done. See `docs/research_findings.md` before designing any mechanism.

---

## Phase B: Generic OpenRAL on SRB — in progress

Per execution_plan.md §18 Phase B. Embodiment: **LunarBot** (user directive).

### Slices 1–3 — LunarBot mobile-manipulator HAL, all ✅ (2026-09-13)

Full records: `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_procedural_kind.md`,
`docs/phase_b_lunar_bot_arm_gripper.md`. All verified live through the real
candidate_action→kernel→safe_action→HAL→SRB path.

**F11** (procedural rSkill kind), **F15** (false alarm), **F12**+**F16**
(FIXED: BODY_TWIST/CARTESIAN_TWIST speed envelopes unenforced), **F17**
(estop_reset doesn't clear other latched nodes). Write-ups: `docs/research_findings.md`.

### `panel_remount` v1 task — ✅ (2026-09-13)

`space_robotics_bench/srb/tasks/mobile_manipulation/panel_remount/`. A solar
panel knocked off its pedestal; robot must locate, pick, place back within
tolerance; genuine binary success termination. **F18** found+fixed (moon
terrain only flat within ~4 m of origin). v1 simplification: one
pedestal+panel pair, not §6.4's "multiple candidate components" — v2 (§6.4)
still pending. Full record: `docs/mission_a_panel_remount.md`. Mission A
instruction text written but **not to be used yet** — Mission A does not
start until Phase B2 is fully done.

### Phase B2 — LunarBot capability set (execution_plan §8.3) — IN PROGRESS

Design + reuse survey: `docs/lunar_bot_capability_set_plan.md`. Branch
`openral/feat/lunar-bot-capability-set`; SRB `feat/four-wheel-steer-alignment`.
Build order (each verified live):

- [x] 1. RM-75 limits in `robot.yaml` (`f7b5ccd`, F22).
- [x] 2. Sensor bridge — `LunarBotSensorBridgeNode`, F25. Relays SRB
      cameras/depth/IMU/lidar; re-roots TF to `chassis_base_link`;
      publishes `/odom` + (new, F30) `tcp_frame`. Still runs standalone,
      not wired into `deploy_e2e.launch.py` (robot-agnostic launch needs a
      generic companion-node mechanism — follow-up).
- [x] 2b. SRB backend for `openral deploy sim` — F26/F27/F28.
      `openral_sim.backends.srb`, `process_group_wrapper.py`,
      `scenes/deploy/srb_panel_remount.yaml`. Tick rate 0.36→~12 Hz (F28).
      Exit condition reached (F29): kernel-path BODY_TWIST moves the robot
      through the full `deploy sim` graph. Open, not urgent: camera topics
      reach OpenRAL at ~2 Hz vs SRB's 12 Hz (Fast-DDS large-message loss —
      fix = XML profile + `sysctl net.core.rmem_max`, not attempted).
- [x] 2c. RTX Lidar — **parked by user decision** (F24, confirmed upstream
      Isaac Sim bug). RayCaster is permanent. Do not re-open without new
      upstream evidence.
- [x] **3. Five procedural rSkills** — `move_joints`, `stow`,
      `move_ee_to_pose`, `grasp`, `release` (F30). All live-verified via
      real `ExecuteRskill` dispatch against the running graph. `stow` /
      `grasp` (on empty gripper, correctly fails) / `release` converge
      cleanly. `move_ee_to_pose` works end-to-end (TF servo, dispatch,
      success/failure signaling) but has a known residual precision/
      oscillation gap near tight tolerances — see F30, a lead for item 6
      (MoveIt), not re-opened by default tuning alone.
- [x] **4. F19 fix** — steer-before-drive in SRB `FourWheelSteerAction`
      (F30). Steering now ramps correctly toward the right per-wheel
      target; net point-turn precision still imperfect (real wheel scrub,
      not fully isolated from tuning this session). **Found +fixed along
      the way**: a separate, pre-existing bug in
      `WheeledManipulatorActionGroup.map_cmd_to_action` (`twist[:2]` took
      `(vx,vy)` instead of `(vx,wz)` — every `angular.z` command was
      silently dropped). Both are their own commits.
- [ ] 5. Navigation — Nav2 via `openral_nav2_bringup`, lidar profile from
      the Mid-360 (`pointcloud_to_laserscan` apt install needed);
      `/cmd_vel → candidate_action` relay so the kernel bounds Nav2.
- [ ] 6. MoveIt for RM-75 — required (license check on `ros2_rm_robot`
      first). Also the natural fix path for move_ee_to_pose's precision
      gap (F30).
- [ ] 7. Mission verifier node (this repo) on simulator truth.
- [ ] 8. §19 run-manifest writer wrapping `openral deploy sim` (this repo).
- [ ] 9. Remaining kernel magnitude checks (`kJointTrajectory` first).
- **Coordination**: Mid-360 landed on SRB `feat/mid360-lidar` — open/unmerged,
  fair game to build on.
- [ ] B3: reasoner-in-the-loop two-step run with full trace = Phase B exit.
      Items 3+4 give the reasoner real manipulation + a working (if
      imprecise) base turn to compose; B3 itself not yet attempted.

**F20** (JOINT_* wire row always full-width) found+fixed live during item-3
prep. Record: `docs/lunar_bot_joint_position_control.md`.

---

## Rules

- Branch or worktree per task; delete after **merge** (AGENT.md §1) — every
  branch below stays open, Phase B is still landing on them:
  openral: `feat/lunar-bot-hal` → `fix/body-twist-speed-envelope` →
  `feat/lunar-bot-arm-gripper` → `feat/arm-joint-position-control` →
  `feat/lunar-bot-capability-set`; SRB: `feat/panel-remount-mission-a` →
  `feat/switchable-arm-control` → `feat/mid360-lidar` /
  `fix/ros-bridge-array-fast-path` → `feat/four-wheel-steer-alignment`.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3). Pure-Python logic
  smoke checks (no ROS/simulator) before a live test are fine and cheap —
  do them first, then one decisive live pass, not exhaustive repeated runs.
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code until Phase B observes real
  failures calling for it** (plan §21.6–7).
- On this shared host, kill only exact PIDs you launched yourself, never a
  pattern (F10). Re-`pgrep` the exact current PID immediately before
  signaling it — don't reuse one echoed by an earlier command (F30: a
  stale PID left a duplicate `sensor_bridge_node` running, causing ~76 s of
  spurious TF failures).
- `ros2 lifecycle`/`node list` don't work on this host — use direct
  `lifecycle_msgs/srv/ChangeState`/`GetState` service calls (F14).
- Any shell running `ros2 action send_goal`/`topic echo` on an
  `openral_msgs`-typed interface needs **both**
  `/opt/ros/humble/setup.bash` **and** `install/setup.bash` sourced, every
  time — a fresh Bash call starts with neither.
- Resetting `/openral/estop_reset` does NOT clear other nodes latched on
  `/openral/estop` — also publish `std_msgs/Empty` on
  `/openral/estop_cleared` (F17).
- A `ros2 topic list` presence check is **not** a reliable readiness signal
  right after a teardown/relaunch (repeatedly false-positived this
  session, F30) — use a real functional check (an actual TF lookup, an
  actual dispatch) instead.
