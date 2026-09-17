# Handoff

State as of 2026-09-17 evening. **Ours (`space_runtime/`) completes Mission A `covered` with vision-only contact (oa2,
verifier success, 33 steps, 30 min).** Now: Mission B `covered` with Ours (runs ob1–ob5), then the held-out
situations, then the 1x video. Findings: `docs/research_findings.md` F1–F54 — **read F53, F54**. Tasks: `todo.md`.

## User decisions (keep)

- `execution_plan` §21: **Ours before the baselines**; tasks from `docs/lunar_task_catalog.md`; Ours may meet held-out
  situations before the freeze (generic changes only); freeze = git commits/tags, **no hash checks anywhere**.
- Contact = **visual servoing on targets described in words** (fiducials dropped). Both cameras RealSense D435i, 15 Hz.
  View with `orientation: grip` (wrist image level).
- VLM = **Kimi-K3** (boundary `observe`/`locate_in_view`/`approach_target`, 3 concurrent asks, median).
  Reasoner = DeepSeek-V4.1-Flash, **thinking ON**. Task success matters most (handle grasp must work).
- **Step-wise development**: never rerun a mission from scratch after a failure. Restore the sim to before the failed
  step, fix, rerun only that step; continue on success, stop and fix on failure.
- One simulation at a time.

## Ours: how to run

- New Mission B dev run (from `openral/`), graph held after the check:
  `D0_HOLD=1 OURS_STOP_ON_FAILURE=1 D0_TRACE_OBJECT=spare_oru D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml
  D0_CHECK=ours_mission_check.py D0_CAPABILITY_SERVER=1 OURS_MISSION=b setsid nohup
  ../experiments/launch/lunar_base_d0/run_d0.sh <log> > <log>/runner.out 2>&1 < /dev/null &`
- Every agent step: `<log>/snapshots/before_step_<n>.pt` (SRB `envs/snapshot`: articulations, rigid objects, held
  actions) + `.json` (the rover's AMCL estimate then). On first failed capability/effect: `STOPPED` in check.log,
  agent killed, graph stays up (`<log>/held`).
- After the fix: `[D0_RESTART_BOUNDARY=1] OURS_MISSION=b OURS_STOP_ON_FAILURE=1 OURS_RESUME_FROM=<log>
  OURS_RESUME_BEFORE_STEP=<n> setsid nohup experiments/launch/lunar_base_d0/attach_d0.sh <graph log> <new log> &`
  → restores the snapshot, re-seeds AMCL (`/initialpose` from the saved estimate), truncates the record before step n,
  resumes the agent (`RESTORED` line logs truth-vs-estimate error). Next failure: resume from `<new log>`.
- Take a held graph down: `experiments/launch/lunar_base_d0/teardown_d0.sh <graph log>`.
- Record: `<log>/ours/{events.jsonl,report.md,agent.log}`; boundary log `capability_server.log`, frames `evidence/`.
- Continuity probe: `OURS_RESTART_AT_STEP=N [OURS_RESTART_MODEL=GLM-5.2]` (rs1 passed).
- Vision contact check: `D0_CHECK=vision_check.py D0_CAPABILITY_SERVER=1` (vc4 press, vc10 grasp).
- Gateway key from `AGENT/VLM_provider.md` (run_d0.sh / attach_d0.sh export it and unset the host proxy).
- Video: `D0_VIDEO=<mp4>` + `SRB_VIDEO_SPEEDUP=1` → `<mp4>.times`; then `python3 experiments/video/overlay.py`.
- Speed: sim ≈ 0.375× wall with cameras (after lidar 10 Hz + publish-on-new-frame); physics ~24 ms/tick remains.
  `D0_PROFILE=1` prints per-bucket step cost. GPU PhysX (`D0_GPU_PHYSICS=1`) crashes in SRB — do not use.

## Mission B with Ours so far

- ob1–ob4: lost query response; grasp missed (TCP semantics); ORU knocked; wrist camera could not frame the handle.
- ob5/ob6 (step-wise): arm creep after every servo (fixed in openral), too-tight plan verification band, opaque MoveIt
  failures (now explained with IK reachability + direction hint), agent re-docking with the arm raised pushed the ORU
  (docking contract warns), AMCL re-seed lost after restore (fixed), no camera-aiming capability → `look_at_feature`.
- Current: graph `artifacts/runs/ob6` held; latest record `ob6_s15d` stopped at step 19: `approach_target` crashed on a
  Kimi-K3 gateway timeout (now an unanswered ask, reason reported). Resume: `OURS_RESUME_FROM=<...>/ob6_s15d
  OURS_RESUME_BEFORE_STEP=19 D0_RESTART_BOUNDARY=1 attach_d0.sh <...>/ob6 <new log>`.
- Timing (ob6_s15d): reasoner thinking ~55 %, arm motion ~25 %, VLM ~20 % of wall time; reasoner 40–255 s per step.
- Analysis: 12 failures = 4 stack defects, 5 interface gaps, 3 reasoner judgement errors (all where the interface made
  it do 3-D kinematics in coordinates).

## Boundary (openral_ext/capability_server)

- `contracts.yaml` effects: navigate_to_pose, dock_to_pose, move_joints, arm_ready, stow, plan_ee_pose,
  move_ee_to_pose, navigate_to_feature, dock_at_feature, plan_ee_to_feature, move_ee_to_feature, approach_target,
  move_tool, grasp, release; queries: site_map, observe, locate_in_view, manifest, arm_state, base_pose, tcp_pose, jaw,
  locate_feature. Evidence robot-observable only; no simulator truth.
- `openral_ext/planning_scene`: surveyed site structures only (movable objects removed with truth).
- PLEXIL baseline: `docs/baselines/plexil.md`; `ros/plexil_capability_adapter`; Mission A plan passes (p1).

## What D0 established (F51–F52)

- `/odom` wheel-inertial; AMCL on a lidar-surveyed map; SLAM off; Nav2 goals in `map`; truth only measures.
- Scripted Mission A (a5) / B (b7) `covered` succeed; held-out `route_block` passes (Nav2 detour).

## How to run scripted D0 checks (don't rediscover)

- From `openral/`: `D0_SCENE=scenes/deploy/srb_lunar_base_mission_{a,b}[_fast].yaml D0_CHECK=<check>.py
  setsid nohup ../experiments/launch/lunar_base_d0/run_d0.sh <logdir> > <logdir>/runner.out 2>&1 < /dev/null &`
- Options: `D0_VIDEO`, `D0_SCENARIO=<heldout_…>`, `D0_SCENERY=lunar_base_route_block`, `D0_TRACE_OBJECT`,
  `D0_CAPABILITY_SERVER=1`, `D0_STEPS=1,2,…`, `D0_PLANNING_SCENE=0`, `D0_HOLD=1`.
- Teardown by run tag (`D0_RUN_TAG`); `LEFT 0 tagged processes` in `deploy.pid`. The agent carries the tag too.

## Things that bit (keep)

- `openral deploy sim` reaps openral processes at start/exit → `OPENRAL_SKIP_ORPHAN_REAP=1` in run_d0.sh.
- bash reads scripts incrementally: runs exec a frozen copy of `run_d0.sh`. Checks load at start.
- `pgrep -f`/`pkill -f` loops once killed the calling shell: kill explicit PIDs only.
- Stale agents ignore SIGTERM (blocked in rclpy) → kill -9; check ROS domain clean before a run.
- Parallel sims → 0.05×. Run one.
- Camera TF was frozen at spawn in SRB → bridge chains cameras through Link7 / rgbd_camera_frame.
- SRB `cmd_vel` callback used to open the gripper; binary commands latched. Read the jaw, not handle distance.
- `terminate_on_success` teleports the rover at success; deploy scenes set it false.
- Verifier `oru_on: ""` can mean knocked off, not grasped — check jaw and handle height.

## Where things are

- Research repo: `feat/ours-space-runtime` (not merged).
- openral: `feat/wrist-depth-relay` 53b5ab0 (camera mounts, wrist depth relay).
- SRB: `feat/camera-budget-video-times` 0d4a416 (15 Hz cameras, work lights, lidar 10 Hz, publish-on-new, video
  `.times`, `envs/snapshot`).
- Videos (not in git): `artifacts/videos/mission_{a,b}_covered.mp4` (scripted D0, 4×).
