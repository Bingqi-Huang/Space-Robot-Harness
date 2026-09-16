# Handoff

State as of 2026-09-16 (evening). **Phase A + B + C done. Phase D0 in progress: Mission A's arm half
works through the real graph; localization is the blocker.** Findings: `docs/research_findings.md`
F1–F50 — **read F50 first**. Tasks: `todo.md`.

## What D0 is and where it stands

D0 = `execution_plan` §21.4/§13.2: prove the **shared capability stack** (the one PLEXIL, EUROPA→PLEXIL
and Ours will all use) can execute Mission A/B through `openral deploy sim` — every motion an
`ExecuteRskill` dispatch through runner → kernel → HAL → SRB, no oracle. If the stack can't, every
method fails for the same physical reason and Experiment I measures nothing.

Mission A `covered`, run a8 (F50 §3): Nav2 ✅ → dock ✅ → close jaws ✅ → READY ✅ → **MoveIt 1.11 cm**
✅ → servo 0.82 cm, hold drift <0.7 cm ✅ → **press: verifier cleared PDU-2's fault** ✅ → retract ✅ →
stow ❌ (0.086 rad short in 15 s; script fixed, not re-run). Return-to-dock not reached.
**Mission B has not run on the new stack** (grasp has never carried a payload via an rSkill).

## The blocker: localization (F50 §4) — user decisions

- `/odom` is **SRB ground truth**. Dock succeeds only because of that. slam_toolbox's map drifts
  **1.0–2.3 m** over an 18 m drive; Nav2 reaches its goal in `map` (0.1–0.4 m) and is physically off.
- User decided: **(i) wheel-inertial odometry, (ii) localization against a prebuilt map. No
  third-party LIO integration** (kinematic-icp/FAST-LIO2) unless (ii) is insufficient. Prefer our own
  implementation over importing packages that need adapting (`robot_localization` isn't installed).
- **Terminal centimetres are the arm's job** (a manipulation rSkill with visual servoing, Phase E);
  the base needs ≲0.10–0.15 m at the work site.
- **Never restrict LunarBot's manoeuvres to reduce slip.** In-place turning and crabbing are design
  features; correct slip in the estimator. (Slip measured: 15–38 % straight, in-place turn realises
  42–54 % at 4× torque.)

## Next steps, in order

1. **Localization** (task #6 in todo):
   a. Bridge `odom_source: wheel` exists (4WIS least squares + IMU yaw rate; truth on
      `/openral/pose_truth`). Add slip-aware twist covariance from the least-squares residual.
   b. Prebuilt map: render a 2D occupancy grid from the scene's static geometry (the
      `/lunar_base/lidar` mesh, F41) → `map.yaml`/PGM → `nav2_map_server` via the deploy `map_path`
      (launch seeds it when SLAM is off) + `nav2_amcl` (installed; `amcl:` block already in the Nav2
      base file). Alternative: slam_toolbox survey with `slam_toolbox_lunar_bot.yaml` (35 m range,
      installed, not selected via `slam_params_file`) → serialize → localization mode.
   c. `d0_common.py`: measure errors against `/openral/pose_truth`, dock in `map`, send Nav2 goals in
      `map` directly (no odom→map transform). Measure wheel-odom drift and AMCL error at PDU-2 and the
      depot — replace the estimates in F50 with numbers.
2. Re-run Mission A to the dock (stow fix) with realistic localization.
3. **Mission B `covered`**: pinch the T-handle neck, carry clamped (never hooked/hanging — user rule),
   place on PDU-1's shelf. Script exists: `d0_mission_b_check.py`.
4. Then §21.4's second half: the common capability-server boundary callable identically by Ours and
   PLEXIL → §21.5 PLEXIL → §21.6 EUROPA→PLEXIL → §21.7 freeze/validator → §21.8 thin `space_runtime`.

## How to run (don't rediscover)

- One live check: `D0_SCENE=scenes/deploy/srb_lunar_base_mission_a_fast.yaml D0_CHECK=d0_mission_a_check.py
  setsid nohup experiments/launch/lunar_base_d0/run_d0.sh <logdir> &` (from `openral/`, path `../experiments/...`).
  Knobs: `D0_STEPS=1,2`, `D0_CONTINUE_ON_FAIL=1`, `D0_DOMAIN=78`. Output: `STEP` JSON lines in
  `<logdir>/check.log` (incl. `sim_s`, `sim_rate`, `pos_err_m`, `map_pos_err_m`, `tcp_err_m`, tracks).
- A run: ~4 min Nav2 + ~3 min dock + ~1 min arm, wall. **Sim runs at 0.13–0.18× real time** with or
  without cameras. All rSkill timeouts and the runner budget are on the sim clock now.
- Second graph in parallel on GPU 1: add `--kit_args "--/renderer/activeGpu=1 --/physics/cudaDevice=1"`
  to the scene's `simulator.argv` and `D0_DOMAIN=78`. Never with `CUDA_VISIBLE_DEVICES=1`.
- Simulator-only measurements (no ROS): `space_robotics_bench/assets/lunar_base/scene/srb_{brake,traction,
  turn,arm_twist}_check.py <outdir>` with `~/Programs/isaac-sim/python.sh`.
- Offline MoveIt check (no sim): `ros2 launch rm_75_config move_group.launch.py` on its own domain +
  `experiments/launch/lunar_base_d0/moveit_selfmodel_check.py`.

## Things that bit this session (keep)

- **Teardown must walk the process tree.** `openral deploy sim` setsid()s its `ros2 launch` child and SRB
  sits in its own session; group/session kills miss them. Stale `runtime_node`/`move_group` then share
  the domain and every goal goes to a dead server ("no goal response"). `run_d0.sh` collects all
  descendants before killing and logs `LEFT 0 of the tree still alive`; the check opens with a
  functional dispatch probe. Before any launch: `ps -eo pid,args | grep -E "kit/python|openral/install/lib|/opt/ros/humble/lib/"`.
- PIDs wrap on this host (4.19M → small numbers): don't infer age from PID.
- Isaac/ROS gotchas fixed this session (F50 §2): `lxml` for MoveIt in the graph; `mission_brief` property
  broke `_visual` tasks; Nav2 Spin at 1.0 rad/s E-stopped the kernel; 20 m global costmap too small;
  `RewrittenYaml` rewrites every same-named key (use dotted-path overrides, keep int types); voxel column
  must start below the DEM floor; MoveIt model must know all 21 joints or it logs 600 ERRORs/s.
- Measuring velocity from wall-clock timestamps in a 0.15× sim reads as "the robot barely moves".
  Always use sim time (`sim_s`) or `/odom` twist.
- One variable at a time; think before running (memory `feedback-think-then-one-decisive-test`).

## Where things are

- openral `master` 0646bd6 (not pushed): clock injection + paced replay + gripper criterion (1d5b739);
  omni base, `move_base_to_pose` rSkill, LunarBot Nav2/slam files, rm_75_config self-model, bridge
  wheel odom + truth topic, Mission A/B scenes + `_fast` (0646bd6).
- SRB `feat/lunar-base-scene` 633a4ed (not pushed): arm twist integrator that holds, (vx, vy, wz) base
  (action layout +1 slot), `env0/mission_state` topic, EG2 closed target 0.10 rad, measurement scripts.
  `main` unchanged. Remotes: SRB `origin` DsslRobot/srb_assets (LFS); openral pushed only to 3ef3220.
- Research repo `main`: `experiments/launch/lunar_base_d0/` (runner, `d0_common.py`, Mission A/B checks,
  offline MoveIt check), F50.
- Robot conventions (F43): REP-103 base twist, kernel 0.6 m/s / 0.5 rad/s (bounds the linear SPEED
  vector, so crabbing is covered), Nav2 caps 0.57 / 0.47, accel 0.3 / decel 0.25 m/s².
- Lunar base scene / assets / oracle: unchanged from C2–C6 (`assets/lunar_base/`); oracle's job is done
  (F49) — do not improve it. Its action indices were shifted for the new base slot.
