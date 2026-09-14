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
      cameras/depth/IMU/lidar; re-roots TF; publishes `/odom` +
      `tcp_frame`. Still standalone, not wired into `deploy_e2e.launch.py`.
- [x] 2b. SRB backend for `openral deploy sim` — F26/F27/F28/F29. Tick rate
      0.36→~12 Hz. Kernel-path BODY_TWIST moves the robot through the full
      graph. Open, not urgent: camera topics ~2 Hz vs SRB's 12 Hz.
- [x] 2c. RTX Lidar — **parked by user decision** (F24, upstream Isaac Sim
      bug). RayCaster is permanent; don't reopen without new evidence.
- [x] **3. Five procedural rSkills** — `move_joints`/`stow`/
      `move_ee_to_pose`/`grasp`/`release` (F30), all live-verified.
      `move_ee_to_pose` has a known residual precision gap near tight
      tolerances (lead for item 6, F30).
- [x] **4. F19 fix** — steer-before-drive in SRB `FourWheelSteerAction`
      (F30); point-turn precision still imperfect (wheel scrub). Also
      found+fixed: `WheeledManipulatorActionGroup.map_cmd_to_action` took
      `(vx,vy)` instead of `(vx,wz)` — `angular.z` was silently dropped.
- [x] 5. Navigation — built + live-verified, merged into
      `feat/lunar-bot-capability-set`. User resolved the ADR-0040/0099
      question (F32): route through the kernel, don't bypass, don't weaken
      Nav2's own avoidance — matches this design (kernel adds only the
      existing velocity-magnitude cap). `twist_to_action_relay_node.py`
      closes the gap `MobileBaseBridge`'s docstring names.
      `pointcloud_to_laserscan` installed by user; its launch wiring had a
      real dead-code bug (function written, never called) — found + fixed.
      **Live-verified decisively (F33)**: `/cmd_vel` → correct
      `BODY_TWIST` chunk on `candidate_action` → kernel-approved
      `safe_action` → robot's real SRB pose moved ~0.6 m, unlatched
      throughout. `/scan` verified flowing 7-11 Hz. Two more real bugs
      (missing `footprint_polygon`, per-package pluginlib names) found +
      fixed live-dispatching an actual NavigateToPose (F36). **Open (F37,
      deferred)**: bt_navigator never reaches ACTIVE unless
      `sensor_bridge_node` is already publishing `/odom` when Nav2's
      lifecycle bringup starts (root-caused, not a mystery) — real fix is
      the already-tracked "wire sensor_bridge into deploy_e2e.launch.py"
      follow-up; the kernel-checked-motion claim itself doesn't depend on
      this.
- [x] 6. MoveIt for RM-75 — built + merged into
      `feat/lunar-bot-capability-set`. Vendored `ros2_rm_robot`'s RM75
      URDF/MoveIt2 config per explicit user decision overriding CLAUDE.md
      §1.9 for this fork (F31, license was undeclared/inconsistent
      upstream). New `rm75` embodiment tag; `rskill-moveit-*` retagged;
      trajectory→JOINT_POSITION bridge was already generic.
      **Fully live-verified end to end (F36, resolves F33)**: root cause
      was a units mismatch (gripper backfill echoed raw SRB units into a
      `[0,1]`-normalised envelope), not a bad waypoint — fixed, re-run
      reaches `success: true`, arm converges to ~0.03 rad of target.
      `move_group.launch.py` still standalone, not in `deploy_e2e.launch.py`.
- [x] 7. Mission verifier node (this repo, `openral_ext/mission_verifier/`)
      — built + live-verified (F33), merged into `main`. Reads real SRB
      ground-truth TF (`srb/env0 -> srb/env0/panel`) + `/srb/env0/
      terminated`, cross-checks against the task's own self-report rather
      than trusting it, publishes `VerifierEvent` JSON on
      `/space_harness/verifier_events` at ~10 Hz, zero errors observed.
- [x] 8. §19 run-manifest writer (`openral_ext/run_manifest/`), merged.
      Wraps `openral deploy sim` (doesn't reimplement its orchestration).
      Writes what's real today (revisions, mission_config,
      capability_registry, real OTel traces, metrics, rosbag opt-in);
      honestly omits (recorded reason, not fake data) what has no source
      yet (`space_context_ref`/`network_profile_ref`/`model_config` —
      B3/baselines not started). 6/6 offline checks vs. real fixtures,
      independently re-run by the coordinator before merge.
- [x] 9. Kernel magnitude checks (F35), merged. All 4 remaining modes
      closed same way as F12/F16. 245/245 kernel tests pass (independently
      re-run). Found, deferred: a dormant OOB-stride risk in 3 pre-existing
      modes (only triggers for horizon>1, nothing sends that today).
- **Coordination**: Mid-360 landed on SRB `feat/mid360-lidar` — open/unmerged,
  fair game to build on.
- [~] B3: reasoner-in-the-loop, real LLM (DeepSeek-V4.1-Flash, user
      -supplied gateway, F38). **Reasoning exit condition MET**: 60+
      ticks correctly decomposed "drive to pedestal, then open gripper"
      into 2 subtasks, picked a real skill with sound rationale, never
      double-dispatched. 2 real bugs found+fixed (gateway 400s on
      `tool_choice="required"` → new `OPENRAL_REASONER_TOOL_CHOICE` env;
      SOCKS proxy crashed the client → unset at launch). **Physical
      completion pending**: chosen skill's sidecar hit a real first-use
      cold start (multi-GB VLA download) — not a defect, won't recur.

**F20** (JOINT_* wire row always full-width) found+fixed live during item-3
prep. Record: `docs/lunar_bot_joint_position_control.md`.

---

## Rules

- Branch or worktree per task; delete after **merge** (AGENT.md §1). The
  whole Phase B stack merged 2026-09-14: openral `master` @ `ec95fe8`,
  SRB `main` @ `6d8a388` (`docs/upstream_pins.md`). Not pushed to origin
  yet. New work starts a fresh branch off `master`/`main`, not the old
  stack names.
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
- **FIXED (F34)**: calling only `/openral/estop_reset` now clears the HAL
  and the skill runner too (both watch `/openral/safety_status` for
  `latched: false`) — `/openral/estop_cleared` still works as a second
  path but is no longer the only way to reach them.
- A `ros2 topic list` presence check is **not** a reliable readiness signal
  right after a teardown/relaunch (repeatedly false-positived this
  session, F30) — use a real functional check (an actual TF lookup, an
  actual dispatch) instead.
