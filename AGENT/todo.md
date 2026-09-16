# TODO

## Phase A: Upstream Verification — ✅ COMPLETE (2026-09-13)

## Phase B: Generic OpenRAL on SRB — ✅ COMPLETE (2026-09-14)

LunarBot HAL + capability set (F11–F38). B3's physical completion is subsumed by D0.

## Phase C: Long-horizon mission construction — ✅ COMPLETE (2026-09-16)

Lunar base scene (C1–C3), Mission A/B tasks with covered + held-out cases and verifier truth
(C4–C5, F45–F46), Nav2 on the base (F47–F48), EG2 clamps (F49). The scripted oracle discharged
§13.1 (verifier validated independently of any method); its job is done — do not improve it.

---

## Phase D0: the shared capability stack on Mission A/B — IN PROGRESS (F50)

`execution_plan` §21.4 + §13.2. Blocks everything after it.

- [x] Graph defects found live and fixed (F50 §2): lxml, `_visual` task construction, Nav2 Spin vs
      kernel envelope, costmap size/type/voxel column, stale-node teardown, MoveIt self-model +
      passive joints, replay pacing, arm twist holding stiffness, gripper settle.
- [x] Physics measured (F50 §1): braking τ≈1 s; slip 15–38 % straight, in-place turn 42–54 % at
      4× torque; sim 0.13–0.18× real time → all skill timeouts on the sim clock.
- [x] Omnidirectional base: SRB (vx, vy, wz) + Nav2 Omni; `move_base_to_pose` docking rSkill.
- [x] **MoveIt on the lunar base: 1.11 cm** (a8).
- [x] **`move_ee_to_pose` holds: 0.8 cm, drift <0.7 cm; press clears PDU-2's fault** (a8).
- [x] `grasp` close / `release` criteria (empty jaws settle at the pads' contact).
- [ ] **Localization realism** — the blocker (F50 §4, user decisions in handoff):
  - [ ] Bridge `odom_source: wheel` (done) + slip-aware twist covariance from the LS residual.
  - [ ] Prebuilt map: occupancy grid rendered from the scene's static geometry → `nav2_map_server`
        (`map_path`) + `nav2_amcl`. (Alt: slam_toolbox survey + localization mode with
        `slam_toolbox_lunar_bot.yaml`.)
  - [ ] Scene/launch: SLAM off, AMCL on, bridge `odom_source: wheel` for the D0 scenes.
  - [ ] `d0_common.py`: errors vs `/openral/pose_truth`; dock in `map`; Nav2 goals in `map`.
  - [ ] Measure: wheel-odom drift over the 18 m leg; AMCL error at PDU-2 and the depot.
- [ ] Mission A `covered` to the dock with realistic localization (stow via READY, 0.1 rad / 30 s).
- [ ] **Mission B `covered`**: pinch the T-handle neck, carry clamped (never hooked/hanging),
      place on PDU-1's shelf, dock. `grasp` has never held a payload through an rSkill.
- [ ] F50 closing numbers: the four capabilities' precision under realistic localization.
- [ ] Silence the bridge's per-tick camera TF lookups when the scene has no cameras (log noise).

Carried: Nav2's own along-track overshoot (F47) no longer matters — the dock skill closes the
last metre — but record it once localization is realistic.

---

## After D0 (execution_plan §21, in order)

- [ ] §21.4 common capability-server boundary callable identically by Ours and PLEXIL.
- [ ] §21.5 PLEXIL Release 6 + LunarBot adapter; one covered Mission A instance end to end.
- [ ] §21.6 EUROPA → PLEXIL bridge; replanning inside the encoded domain on the same case.
- [ ] §21.7 scenario manifests, evaluator-only annotations, freeze manifest, closed-capability validator.
- [ ] §21.8 thin `space_runtime` for Mission A (facts/evidence, context, guard, playbook audit).
- [ ] Phase D space context only for variables the final scenarios exercise.
- [ ] Phase E: semantic query / relative perception; **terminal precision = manipulation rSkill with
      visual servoing** (user decision), not base localization.

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream suites (AGENT.md §3); pure-Python offline checks before one decisive live run.
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **Do not restrict LunarBot's manoeuvres to avoid slip**; fix estimation. **Carry payloads clamped.**
- **No third-party research code that needs adapting** unless the in-house route is shown insufficient.
- Kill only processes of your own run (descendant tree of the deploy PID); never `pkill -f` a pattern.
  Check `ps -eo pid,args | grep -E "kit/python|openral/install/lib|/opt/ros/humble/lib/"` before launching.
- Every ROS shell: `source /opt/ros/humble/setup.bash && source openral/install/setup.bash`,
  `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`. Rebuild colcon packages with
  `--merge-install --symlink-install` and `-DPYTHON_EXECUTABLE=/usr/bin/python3` (venv lacks catkin_pkg).
- Long Isaac jobs: `setsid nohup ... &`. ≤2 rendering Isaac instances.
- `srb agent rand/zero` never stop on their own; `ros2 lifecycle`/`node list` don't enumerate here.
- Measure motion in sim time, never wall time.
