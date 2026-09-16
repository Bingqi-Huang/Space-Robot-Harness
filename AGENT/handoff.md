# Handoff

State as of 2026-09-16. **Phase A + B complete. Phase C (C1–C6) complete.** Task list: `todo.md`.
Findings: `docs/research_findings.md` (F1–F49). Next: §21.4 of `execution_plan.md`, not more oracle work.

## Read this first — where the last session went wrong

The scripted oracle (`assets/lunar_base/scene/srb_mission_{a,b}_run.py`) is a required instrument
(`execution_plan` §13.1) and **its job is done**: six Mission A/B cases reach verifier success and three
real verifier defects were found doing it. What it does *not* do is §13.2's other half — prove a solution
exists **using only the shared capability set** — because it bypasses OpenRAL entirely and commands SRB
actions with its own IK (F45 says this in its own last paragraph).

The last session spent a day improving the oracle's grasp/transport realism anyway (nine deck-transfer
runs, still not working, F49). Two facts were already in the record and went unused:

- the five procedural manipulation rSkills are **built and live-verified** (F30);
- **MoveIt for the RM-75 works** through the kernel (F36: chunk 8, success, arm within 0.03 rad).

Do not continue the oracle. The physical work belongs on the capability path.

## The actual open risk to Experiment I

All three methods share one capability stack (§5.3). Its measured precision may not meet the missions'
geometry, and nobody has checked:

| capability | measured | mission needs |
|---|---|---|
| Nav2 `NavigateToPose` | ~0.8 m along-track overshoot (F47, open) | work poses with 0.198 m clearance |
| `move_ee_to_pose` (procedural) | 1.3–2.5 cm then drifts back — SRB `arm_ik` re-syncs every step, no holding stiffness (F30) | cm-level and held |
| `moveit-eef-pose` | one verified dispatch (F36), never on the lunar base | collision-aware approach |
| `grasp` / `release` | gripper mechanism fixed + holds 1 kg (F49), only ever driven from the oracle | grasp the spares' T-handle |

If the shared stack cannot execute Mission A/B, all three methods fail for the same physical reason and
the experiment measures nothing. **Settle this before anything else.**

## Next steps, in `execution_plan` §21 order

1. **Mission B transport, one bounded attempt**: real pinch grasp (works) + carry the payload clamped in
   the jaws — the user's own preferred option — no rover deck. Re-run the three cases, record videos.
   If it does not work in one pass, fall back to SRB `83f5636` (hook grasp, 3/3 verified) and move on.
2. **§21.4 — the shared capability boundary**: drive Mission A `covered` through the real graph
   (`openral deploy sim --config scenes/deploy/srb_lunar_base.yaml`, env `lunar_base_mission_a_visual`,
   `env.scenario=covered`) using Nav2 + MoveIt/procedural rSkills through the kernel. This is both the
   capability-precision answer above and §13.2's closed-capability certificate.
3. Then §21.5/21.6 (PLEXIL, then EUROPA→PLEXIL), §21.7 (manifests/freeze/validator), §21.8 (thin
   `space_runtime` for Mission A). Phase D space context only for variables the final scenarios exercise.

## Where things stand (facts, not plans)

- Branches: SRB `main` + dev `feat/lunar-base-scene` (head `a3ac8aa`) on **git@github.com:DsslRobot/srb_assets.git**
  (`origin`, LFS; `fork` = old fork, `upstream` = AndrejOrsula). openral `master` (head `3ef3220`, pushed).
  Research repo `main`, no remote.
- LunarBot conventions (F43): REP-103 base twist; teleop W/S drive, A/D and C/V yaw; kernel bound
  0.6 m/s / 0.5 rad/s, Nav2 caps 0.57 / 0.47; Mid-360 inverted (F42). PhysX warnings hidden
  (`SRB_PHYSX_WARNINGS=1` shows them). Don't change the robot model for cosmetic reasons (user rule).
- **Gripper (F49)**: `PhysxMimicJointAPI` couples `eg2_joint2..6` to `eg2_joint1`, so both pads clamp
  together like the real EG2-4C2; effort 4.0 N·m in both the SRB actuator and `robot.yaml`. Authored by
  `assets/lunar_base/process/add_gripper_mimic.py`. Holds 1 kg.
- **Payloads** carry a T-handle lifting eye (12 mm neck, 55 mm free height, 90×45×14 mm head) — form
  closure, not friction. Regenerate with `process/process.py --only <name>` then `scene/build_scene.py`.
- **Deck transport does not work** and the code for it is committed as WIP in `lunar_oracle.py`
  (`place_on_deck` / `lift_from_deck` / `swing_around_shoulder`). Last fully verified Mission B oracle:
  SRB `83f5636`.
- MoveIt now launches inside the deploy graph (`RobotDescription.motion_planning`, openral `3ef3220`);
  the gripper-effort and SIGTERM fixes are in the same commit. **None of it exercised live yet.**

## Lunar base scene (C2–C3, `space_robotics_bench/assets/lunar_base/`)

- After a layout edit: `python3 scene/build_terrain.py && python3 scene/build_scene.py` (~30 s; printed
  problems + clearances must be empty). Variants: `build_scene.py --variant route_block`.
- `/lunar_base/lidar` (terrain + one box per static structure) is all the lidar sees (F41): obstacles
  Nav2 must see belong in the static layout, not runtime spawns.
- Interaction layer: `scene/interaction.py` → `usd/scene/lunar_base/interaction.json`. REACH 0.45 m past
  the −X hull edge for every side-on frame (F45).
- Checks: `scene/srb_settle_check.py <out>` (~6 min, PASS), `srb_drive_check.py`, `srb_teleop_check.py`,
  `render_review.py`.

## Missions (C4–C5)

- Tasks: `lunar_base_mission_a` (covered | heldout_cover_obstruction | heldout_status_mismatch) and
  `lunar_base_mission_b` (covered | heldout_destination_occupied | heldout_spare_swapped);
  `mission_state()` is verifier truth; `terminate_on_success=False` for demos.
- Oracle: `~/Programs/isaac-sim/python.sh assets/lunar_base/scene/srb_mission_{a,b}_run.py <out>
  --scenario <s> [--no-video] [--arm-only ...]`. Videos in `assets/lunar_base/review/mission_{a,b}/`
  (mp4 gitignored). Shared primitives `scene/lunar_oracle.py`, model IK `scene/rm75_ik.py`.
- Manipulation facts: shoulder-back READY (0,−1,0,−1.4,0,1.2,0); carry with the base 8 cm above the
  highest support; arm links occupy z 0.93–1.35, deck top 0.612 — a payload swung between them hits one
  or the other, which is what killed the deck transfer.

## OpenRAL graph on the lunar base (F47–F49)

- `openral deploy sim --config scenes/deploy/srb_lunar_base.yaml` (or `_route_block`,
  `srb_panel_remount.yaml`): SRB + sensor bridge + kernel + HAL + SLAM + Nav2 + MoveIt (+ reasoner, which
  needs the F38 LLM env — `experiments/launch/reasoner_env.sh`).
- Nav2 smoke (launch detached): `[NAV2_SCENE=... NAV2_GOALS="x,y;x,y"]
  experiments/launch/lunar_base_nav2/run_nav2_smoke.sh <logdir>`.
- Open: ~0.8 m along-track overshoot (MPPI approach vs ~0.9 s base velocity time constant).

## Environment reference (reusable, don't rediscover)

- Every ROS shell: `source /opt/ros/humble/setup.bash`, `source openral/install/setup.bash`,
  `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`. No `set -u` around ROS setup scripts.
- Long Isaac jobs: `setsid nohup ... &` — background tasks otherwise get killed as "low memory" with
  >200 GB free (F46). ≤2 rendering Isaac instances (3 → Vulkan DEVICE_LOST).
- Kill exact PIDs only; `pkill -f` inside a tool call can kill the calling shell. After deploy runs check
  `ps -eo pid,args | grep -E "openral/install/lib|opt/ros/humble/lib|kit/python"`.
- `srb agent rand/zero` never stop on their own (SIGINT after a bounded wait). `srb agent rand --help`
  doesn't list tasks registered after Isaac init.
- `ros2 lifecycle`/`node list` don't enumerate here — call `lifecycle_msgs` services directly.
- Readiness is a functional check, not `ros2 topic list`.
- Isaac ships Lula (`isaacsim.robot_motion.lula`: RRT, RmpFlow, kinematics, trajectory generation); the
  `lula` C++ API takes obstacles directly, no USD prims. cuRobo is not installed. Recorded for later —
  the planner for the capability path is MoveIt, which is already integrated.

## Lessons (keep)

- `reset_root_state_uniform` pose_range is a delta (F40); spawning inside a collider launches silently.
- "Works" needs multi-angle renders or a follow-camera video, not a clean log.
- Side close-ups (`Oracle.snapshot`) settle grasp geometry questions faster than logs.
- **Before adding fidelity, check what the plan actually requires of the artifact you are improving.**
  Nine deck-transfer runs bought nothing the paper needs (F49).
