# Handoff

State as of 2026-09-16. **Phase A + B complete. Phase C (C1–C6) complete** apart from Nav2 approach tuning.
Task list: `todo.md`. Findings: `docs/research_findings.md` (F1–F48). Next: Phase D/E (execution_plan §21).

## Where things stand

- Branches (user rule: only trunk + the working dev branch): SRB `main` + dev branch `feat/lunar-base-scene`
  (all Phase C work) on **git@github.com:DsslRobot/srb_assets.git** (`origin`, LFS; old fork = remote `fork`,
  `upstream` = AndrejOrsula). openral `master` only (pushed). Research repo `main` (no remote). `.gitmodules`
  points SRB at srb_assets (branch = dev branch).
- LunarBot conventions (F43): REP-103 base twist; teleop base mode W/S drive, A/D and C/V yaw; kernel bound
  0.6 m/s / 0.5 rad/s, Nav2 caps 0.57 / 0.47; Mid-360 inverted (F42). PhysX plugin warnings hidden
  (`SRB_PHYSX_WARNINGS=1` shows them). Don't change the robot model for cosmetic reasons (user rule).

## Lunar base scene (C2–C3, `space_robotics_bench/assets/lunar_base/`)

- Pipeline after a layout edit: `python3 scene/build_terrain.py && python3 scene/build_scene.py` (~30 s once the
  terrain exists; problems + clearances printed, must be empty). Variants: `build_scene.py --variant route_block`
  (layout.yaml `variants:`; writes `lunar_base_<v>.usda`, shares textures/interaction). Asset reprocessing:
  `python3 process/process.py --only <name>`; authored props: `blender -b --factory-startup -P
  process/author_props.py -- <out>` then copy the prop into `authored/`.
- `/lunar_base/lidar` (terrain + one box per static structure) is the only thing the lidar sees (F41): obstacles
  Nav2 must see go into the static layout, not runtime spawns.
- Interaction layer: `scene/interaction.py` → `usd/scene/lunar_base/interaction.json` (frames, spawns, work/view
  poses). REACH 0.45 m past the −X hull edge for every side-on frame (F45); spares carry bail handles (F46).
- Checks: `scene/srb_settle_check.py <out>` (~6 min, PASS after F46 changes), `srb_drive_check.py`,
  `srb_teleop_check.py`, `render_review.py`.

## Missions (C4–C5)

- Tasks: `lunar_base_mission_a` (covered | heldout_cover_obstruction | heldout_status_mismatch) and
  `lunar_base_mission_b` (covered | heldout_destination_occupied | heldout_spare_swapped); `mission_state()` is
  verifier truth; `terminate_on_success=False` for demos.
- Scripted oracle (not the harness): `~/Programs/isaac-sim/python.sh assets/lunar_base/scene/srb_mission_{a,b}_run.py
  <out> --scenario <s> [--no-video] [--arm-only ...]`. All six cases verifier success; follow-camera videos in
  `assets/lunar_base/review/mission_{a,b}/` (mp4 gitignored). Shared primitives `scene/lunar_oracle.py` (base,
  RM-75 model IK `scene/rm75_ik.py` with residual correction, hook grasp, carry rate limits, camera, snapshots).
- Manipulation facts: arm shoulder-back branch READY (0,−1,0,−1.4,0,1.2,0); EG2 pinch/cage slips on 1 kg — hook
  the bail bar (base reverses 0.22 m under it); carry with base 8 cm above the highest support.

## OpenRAL graph on the lunar base (F47–F48)

- `openral deploy sim --config scenes/deploy/srb_lunar_base.yaml` (or `_route_block`, `srb_panel_remount.yaml`):
  SRB + sensor bridge (`simulator.bridges`) + kernel + HAL + SLAM + Nav2 (+ reasoner, which needs the F38 LLM env).
- Nav2 smoke (launch detached): `[NAV2_SCENE=... NAV2_GOALS="x,y;x,y"] experiments/launch/lunar_base_nav2/
  run_nav2_smoke.sh <logdir>` — goals, stop traces, odometry track.
- Nav2 fixes in openral: bridge gating, list-valued param overrides, manifest base_frame, use_sim_time in every
  server, lifecycle driver instead of lifecycle_manager autostart, per-robot goal checker. Open: ~0.8 m
  along-track overshoot from 0.57 m/s (MPPI approach vs ~0.9 s base velocity time constant).

## Environment reference (reusable, don't rediscover)

- Every ROS shell: `source /opt/ros/humble/setup.bash`, `source openral/install/setup.bash`,
  `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`. No `set -u` around ROS setup scripts.
- Long Isaac jobs: launch with `setsid nohup ... &` — this tool's background tasks get killed as "low memory"
  with >200 GB free (F46). ≤2 rendering Isaac instances at once (3 → Vulkan DEVICE_LOST + hung process).
- Process hygiene: kill exact PIDs; `pkill -f <pattern>` inside a tool call can kill the calling shell itself.
  After deploy runs, check `ps -eo pid,args | grep -E "openral/install/lib|opt/ros/humble/lib|kit/python"` —
  Nav2 python helpers survive the launch group kill. Verify zero Isaac instances before and after launches.
- `srb agent rand/zero` never stop on their own (SIGINT after a bounded wait). `srb agent rand --help` doesn't
  list tasks registered after Isaac init. `srb` resolves the main checkout (editable install).
- `ros2 lifecycle`/`node list` don't enumerate by name here — call `lifecycle_msgs` services directly; a node
  that does not answer `get_state` is usually blocked inside a lifecycle callback (F47), not a DDS fault.
- Readiness is a functional check, not `ros2 topic list`.

## Lessons (keep)

- `reset_root_state_uniform` pose_range is a delta (F40); spawning inside a collider launches silently.
- "Works" needs multi-angle renders or a follow-camera video the user can look at, not a clean log.
- Side close-ups (`Oracle.snapshot`) settle grasp geometry questions faster than logs.
