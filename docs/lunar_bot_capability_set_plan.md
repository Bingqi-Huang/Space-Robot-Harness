# LunarBot capability set — design notes (execution_plan.md §8.3, Phase B2)

Written 2026-09-14 after a read-only survey of the pinned OpenRAL and SRB
revisions (`docs/upstream_pins.md`). This is the planning record for the
work that must exist before Mission A can be run through the reasoner:
what upstream already provides, what is missing for `lunar_bot`, and the
design decision for each item. Nothing here is implemented yet except
item 1 (RM-75 limits, `openral` `f7b5ccd`). Everything below is to be
verified live when built — "upstream has it" was already shown twice this
project to differ from "it works for this robot" (F19, F20).

## 0. Why this document exists

`research_content.md` §5.1 requires all four operating models (procedure-
driven, generic OpenRAL, prompt-only space-aware, proposed runtime) to
share the same perception, navigation, manipulation controller, FDIR
primitives and safety. §6.4 requires a "capability set shared across all
baselines" table in the paper. For `lunar_bot` that set does not exist
upstream: the reasoner has never been in the loop for this robot, no
sensor reaches world state, and no rSkill can move the arm. The
capability set is therefore paper infrastructure, not a detour.

## 1. What upstream OpenRAL already provides (reuse, don't rewrite)

| Piece | Where | Relevance |
|---|---|---|
| World-state aggregator node | `packages/world_state/openral_world_state_ros/lifecycle_node.py` | Subscribes `/joint_states`, `/openral/cameras/<name>/image` per manifest RGB sensor (BEST_EFFORT), `/openral/perception/objects`, `/openral/world_voxels`, and a depth-cloud fallback `/openral/cameras/front_depth/points`; lifts 2-D detections to 3-D via TF `spec.frame_id ← base_frame` and `map ← base_frame`. Needs a `map` frame and per-sensor optical frames in TF. |
| Image detector node | `openral_perception_ros/ros_image_detector_node.py` | Subscribes one RGB topic, publishes `/openral/perception/objects`; open-vocabulary `omdet-turbo-locator` / `locateanything`, or RT-DETR COCO. Attributes detections to `sensor_id` (default `front_depth`). Serves `/openral/perception/locate_in_view`. |
| Scene VLM node | `openral_perception_ros/scene_vlm_node.py` | `qwen35-4b-nf4` sidecar; the reasoner's `scene_query` tool. |
| ROS-image sensor reader | `openral_runner/backends/ros2_image.py` (`SensorReaderBackend.ROS2_IMAGE`) | The sanctioned way to consume an image that a *driver* publishes on a ROS topic (ZED, RealSense) — exactly the SRB case. Bound via `sensors[].deploy_binding` in the manifest / deploy scene. |
| Mobile-base bridge | `openral_hal/mobile_base_bridge.py` | Publishes `/odom` + `odom→base_link` TF from `hal.base_pose`, and `/cmd_vel`→BODY_TWIST. **Not usable as-is**: it attaches only when the manifest declares `base_joints` (LunarBot has none — 4WIS/4WID, not a holonomic planar base), and its `/cmd_vel` path *bypasses* the safety supervisor by design. |
| Nav2 bringup | `packages/openral_nav2_bringup` | `nav2.launch.py` with two costmap profiles: `lidar` (`/scan`) and `visual` (`/map` OccupancyGrid via `static_layer`). Frames `map`/`odom`/`base_link`, `/odom` topic; bond timeout already raised to 30 s (issue #256). Reasoner starts it as a background service when a goal needs navigation. |
| Nav2 rSkill | `rskills/rskill-nav2-navigate-to-pose` | `kind: ros_action`, tag `mobile_base` (LunarBot carries it), result-only mode; goal schema supports `map` and `base_link` frames. |
| OctoMap bridge | `packages/openral_octomap_bridge` | OctoMap → kernel `OccupancyVoxels` for capsule-vs-world collision. Separate concern from Nav2's 2-D costmap but consumes the same depth cloud. |
| Procedural rSkill kind | `openral_rskill.procedural_body_twist` (this project, F11) | The pattern every new LunarBot skill follows: `kind: procedural`, `entrypoint`, `default_goal_json`, `goal_params_schema`, `chunk_size: 1`. |
| MoveIt rSkills | `rskills/rskill-moveit-{joints,eef-pose,look-at}` | Tagged franka/ur; need a MoveIt `move_group` for RM-75 and a trajectory consumer. |
| Host packages installed (Humble) | — | `navigation2`, `nav2_bringup`, `slam_toolbox`, `octomap_server`, `octomap_msgs`, `moveit_ros_move_group`, `moveit_msgs`, `robot_state_publisher` all present — no apt work needed for Nav2/OctoMap/MoveIt. |

## 2. What SRB publishes for `lunar_bot` under `--interface ros`

From `srb/interfaces/interface/ros.py` (verified by reading; the
non-visual subset was verified live in `docs/srb_integration_notes.md`):

- `/srb/env0/robot/joint_states` (21 joints) — already consumed by the HAL.
- `/srb/env0/imu_robot` (`sensor_msgs/Imu`, frame `srb/env0/imu_robot`).
- `/tf`: `srb/env0 → srb/env0/<asset>` for every rigid object and
  articulation (`robot`, `panel`, …) and every sensor
  (`srb/env0/cam_front`, `srb/env0/cam_wrist`, …). Camera frames use
  `quat_w_ros`, i.e. **already the ROS optical convention**. Object poses
  on `/tf` are the simulator truth the verifier (not the reasoner) will
  read.
- With the `*_visual` task variant (`GroundManipulationEnvVisualExtCfg`):
  `cam_scene` (third-person, 2 m behind/above the base), `cam_front`
  (on `rgbd_camera_frame/camera_front`, pitched 15° down, 25 m clip),
  `cam_wrist` (on `Link7`, 1.5 m clip). Each publishes
  `/srb/env0/<cam>/camera_info`, `/srb/env0/<cam>/image_rgb`,
  `/srb/env0/<cam>/image_depth` (when depth is enabled) and
  `/srb/env0/<cam>/pointcloud` (frame `srb/env0/<cam>`). **Defaults are
  64×64 and RGB-only** (`VisualExtCfg.camera_resolution=(64,64)`,
  `camera_data_types`) — the Mission A visual task must set a usable
  resolution (≥ 640×480 for the detector) and `("rgb", "depth")` on
  `cam_front` at least.
- `/srb/env0/terminated`, `/srb/env0/truncated`, `/srb/env0/reward` and
  per-term reward topics (`reward_success`, `penalty_undesired_robot_contacts`, …).

Not published: `/odom`, any `map`/`base_link` frame, any `LaserScan`.

## 3. Design decisions, item by item (§8.3 numbering)

### 3.1 RM-75 limits — done (`f7b5ccd`), verified against the kernel alone.

### 3.2 Sensor bridge (SRB → OpenRAL conventions)

A new node in `packages/openral_hal_lunar_bot` (`sensor_bridge_node`, a
lifecycle node beside the HAL, or folded into `LunarBotHALLifecycleNode`
— decide at build time by which keeps the HAL node's executor free), doing:

1. **TF re-rooting.** Subscribe SRB's `/tf`; for each SRB frame of
   interest compute `T(robot ← frame)` from `T(env ← robot)` and
   `T(env ← frame)` and re-publish as `chassis_base_link → <manifest
   frame>` (`front_camera_optical_frame`, `wrist_camera_optical_frame`,
   `imu_link`). Publish `odom → chassis_base_link` from `T(env ← robot)`
   and a static identity `map → odom`. Stated plainly in the paper: in
   simulation, localization is ground truth; the frames exist so that Nav2,
   the world-state lift and the verifier all resolve through TF exactly as
   they would on the real robot (where `map → odom` comes from a
   localizer). Frame names are read from `robot.yaml` (`base_frame`,
   `odom_frame`, `sensors[].frame_id`), never hardcoded (CLAUDE.md §2).
   *To verify live:* that SRB's `srb/env0/robot` root pose is the
   `chassis_base_link` pose (articulation root prim vs. base frame).
2. **`/odom`** (`nav_msgs/Odometry`, RELIABLE): pose from the same
   transform; twist from finite differences of consecutive poses (or the
   IMU angular rate) expressed in the base frame per REP-105.
3. **Images.** Relay `/srb/env0/cam_front/image_rgb` →
   `/openral/cameras/front/image`, `/srb/env0/cam_wrist/image_rgb` →
   `/openral/cameras/wrist/image`, rewriting `header.frame_id` to the
   manifest frame, BEST_EFFORT. Preferred implementation: declare the
   sensors in `robot.yaml` with a `deploy_binding` of backend `ros2_image`
   pointing at the SRB topics, so upstream's own reader publishes them —
   no new relay code if the binding supports frame rewriting; otherwise a
   thin relay in the bridge node. Same for `camera_info`.
4. **Depth.** Relay `/srb/env0/cam_front/pointcloud` →
   `/openral/cameras/front_depth/points` (frame rewritten) — this feeds
   both the world-state object lift and OctoMap/Nav2. Also relay
   `image_depth` → `/openral/cameras/front_depth/image` for the detector's
   `sensor_id=front_depth` attribution.
5. **IMU** → `/imu` (frame `imu_link`).
6. **`/joint_states`** — already published by `ManifestHALLifecycleNode`
   from the HAL's state; keep.

`robot.yaml` additions: `sensors:` block with `front` (rgb), `front_depth`
(depth), `wrist` (rgb), each with `frame_id`, `rate_hz`, real intrinsics
taken from SRB's `CameraInfo` at the chosen resolution (not guessed —
`PinholeCameraCfg(focal_length=5.0, horizontal_aperture=12.0)` gives
`fx = width·5/12`); `odom_frame: odom`.

Verification: world state lists 21 joints, two live camera frames, and
after pointing the detector at `front` with query "solar panel", one
lifted object whose `map`-frame position is within ~0.2 m of the panel's
`/tf` truth.

### 3.3 Procedural manipulation rSkills (`kind: procedural`, tag `lunar_bot`)

Five skills, each a closed loop on world state / TF, each emitting one
chunk per tick through `ROSPublishingHAL` → kernel, each finishing on a
measured condition and reporting failure honestly:

| Skill | Control mode | Goal params | Done when | Fails when |
|---|---|---|---|---|
| `move_joints` | JOINT_POSITION (full 21-wide row, F20) | 7 targets (rad), tolerance, timeout | all \|q−q\*\| < tol | timeout; kernel rejection (outside RM-75 range) |
| `move_ee_to_pose` | CARTESIAN_TWIST | target pose in `chassis_base_link` or `map`, tolerances, max speed | pos+rot error < tol (TF `Link7`/TCP vs target) | timeout; no progress for N s; kernel rejection |
| `grasp` | GRIPPER_BINARY then hold | — | gripper joints stop moving and are not at the fully-closed stroke (something is between the jaws) | jaws reach fully-closed (nothing grasped) |
| `release` | GRIPPER_BINARY | — | jaws at open stroke | timeout |
| `stow` | JOINT_POSITION | fixed stow pose from `lunarbot.py` init state | as `move_joints` | as `move_joints` |

Design rules: no skill encodes mission semantics (no "pick up the panel");
`move_ee_to_pose` takes a pose, and *which* pose is the reasoner's job
(from `locate_object` / world state). The TCP frame: `Link7` +
`_TCP_OFFSET` (`lunarbot.py`), exposed by the sensor bridge as
`tcp_frame` on TF so the skill and the verifier use one definition.
These five are also exactly the primitives Baseline A's behavior tree is
composed from (§11.1) — build them once.

Verification: a scripted sequence (`move_ee_to_pose` above panel →
descend → `grasp` → lift → `move_ee_to_pose` above pedestal mount →
descend → `release` → `stow`) remounts the panel in `panel_remount` v1 and
`/srb/env0/terminated` goes `true`. This is the first time the whole
manipulation chain closes; expect calibration issues in CARTESIAN_TWIST
(the raw-unit conversion is pose-dependent, `docs/phase_b_lunar_bot_arm_gripper.md`).

### 3.4 F19 — root-cause hypothesis from reading `four_wheel_steer.py`

The kinematics are right (`v_wheel = v + ω × r`, steer = `atan2`, wrap to
(−90°, 90°] with drive-sign flip). What is missing is **steer-before-
drive sequencing**: `apply_actions` writes the steer *position* target and
the drive *velocity* target in the same step. The steering joints are
position-controlled (stiffness 280, velocity limit 1.9635 rad/s ≈ 112°/s),
so a commanded in-place rotation asks every wheel to swing ~90° — taking
~0.8 s — while the drive wheels are already spinning at full target speed
at the *old* steer angle. During that transient the four wheels push in
inconsistent directions: the observed "drifts/rotates incoherently".
The (−90°, 90°] wrap makes it worse whenever the commanded ratio `v/ω`
crosses a wheel's singular direction — the steer target flips by 180° and
the drive sign flips, another large transient.

Fix to implement (SRB fork, `feat/four-wheel-steer-alignment` or on the
capability-set branch): scale each wheel's drive velocity by
`max(0, cos(steer_target − steer_measured))` (zero drive while a wheel is
more than 90° off, full drive when aligned) — the standard 4WIS practice;
optionally rate-limit the steer target. Verify with an in-place +90° turn:
yaw reaches 90° ± a few degrees with < 5 cm translation. This must land
before Nav2, whose controllers assume `cmd_vel` is tracked faithfully.

### 3.5 Navigation

- **Costmap source.** LunarBot declares `has_lidar: false`; the simulated
  model has a front RGB-D only. Two options — **open question for the
  user**: (a) if the real LunarBot carries a lidar, add a matching
  `RayCaster` sensor to `lunarbot.py` and use Nav2's `lidar` profile via
  `/scan`; (b) otherwise use the `visual` profile with `/map` produced by
  `octomap_server` from `/openral/cameras/front_depth/points`
  (`octomap_server` publishes `projected_map` — remap to `/map`; TF
  `map ← front_camera_optical_frame` resolves through the bridge). Option
  (b) needs no new simulated sensor and matches the real robot's RGB-D.
  Default is (b) unless told the real robot has a lidar.
- **`/cmd_vel` through the kernel.** Upstream's Nav2 manifest and
  `MobileBaseBridge` both let Nav2 write the base directly, bypassing the
  supervisor. For this paper (§10.1: never bypass safety) a
  `cmd_vel → candidate_action` relay node publishes each Nav2 twist as a
  BODY_TWIST chunk (`rskill_id = nav2`), so the kernel's
  `max_base_*_speed` bounds apply and violations latch exactly as for any
  skill. The HAL's own `cmd_vel_topic` stays SRB's `/srb/env0/action/cmd_vel`;
  Nav2's `/cmd_vel` is consumed only by the relay.
- **Terrain.** Beyond the ~4 m flat pad (F18) the moon terrain is
  uneven; `panel_remount` v2's approach route must be verified traversable
  in `agent zero` before it becomes a Nav2 test.
- Verification: `rskill-nav2-navigate-to-pose` dispatched from the rskill
  runner with a `map`-frame goal 3–4 m away; robot arrives within Nav2's
  goal tolerance, no kernel latch, no contact with the pedestal.

### 3.6 MoveIt for RM-75 (after 3.3)

RealMan publishes `ros2_rm_robot` (rm_description / rm_75 MoveIt config);
its content and license must be checked before anything is copied
(CLAUDE.md §1.9 — Apache-2.0/MIT/BSD only). The pieces: URDF/SRDF for
RM-75 with the gripper as an attached body; `move_group` planning against
the OctoMap; a `FollowJointTrajectory` action server implemented in this
project that streams the trajectory as JOINT_POSITION chunks through the
kernel to the HAL (so MoveIt never touches the robot directly); the three
`rskill-moveit-*` manifests get `lunar_bot` in `embodiment_tags`. Value for
the paper: the "manipulation planning" capability of §6.4 and a
collision-aware alternative to the procedural IK skills — i.e. a genuine
capability-substitution case for §5.4.1. Deferred until 3.3 works so the
first mission runs do not wait on it.

### 3.7 Mission verifier node (this repo)

Reads simulator truth (`/tf` object poses, `/srb/env0/terminated`, reward
terms) and emits typed verifier events with evidence references
(execution_plan §4.4). For `panel_remount` v1 the conditions are exactly
the task's own success check (panel within 0.1 m / ~51° of the mount pose)
plus "panel is/is not grasped" (TCP–panel distance + gripper state).
Deterministic, no learned component.

### 3.8 Launch orchestration + run artifacts (this repo, `experiments/`)

`openral deploy sim` cannot target SRB (`SceneBackend` has no `srb`
variant — adding one is real `openral_sim` engineering and is *not*
planned). Instead one ROS 2 launch file in this repo brings up, in order:
safety kernel (params generated from `robot.yaml` via
`kernel_params_from_envelope`) → LunarBot HAL → sensor bridge →
world state → detector / scene VLM → rskill runner → prompt router →
reasoner; SRB itself is launched separately (`srb agent ros --env
panel_remount_visual env.robot=lunar_bot --headless`) because it needs
the conda-free, `PYTHONPATH`-free environment (`docs/srb_integration_notes.md`).
A `run_manifest.yaml` writer records both submodule commits, seeds, model
config, mission text, and the OTel/rosbag locations (§19). Every
baseline uses this same launch with a different reasoner/runtime config.

### 3.9 Remaining kernel magnitude checks

`kJointTrajectory`, `kCartesianDelta`, `kGripperBinary` (per-joint),
`kGripperPosition`, `kCompositeMode` still delegate to an unlaunched
Python stub. The LunarBot HAL cannot be asked to emit the first two
today, but MoveIt (3.6) will emit joint trajectories, so at least
`kJointTrajectory` must be closed the way F12/F16 were before 3.6 lands.

## 4. Open questions for the user

1. Does the physical LunarBot carry a lidar? (Decides 3.5's costmap source.)
2. MoveIt (3.6): keep it in scope after the procedural skills, or drop it
   if the procedural IK skills prove sufficient for Mission A v2? The
   paper's §6.4 lists "manipulation planning *or* a learned policy", so
   it is optional in principle; I recommend keeping it as the
   capability-substitution case.
3. `openral deploy sim` support for SRB is deliberately *not* planned
   (launch lives in this repo). Confirm.

## 5. Suggested branch layout for the coding rounds

- `openral`: `feat/lunar-bot-capability-set` (created; carries 3.1) —
  sensor bridge, procedural skills, cmd_vel relay, kernel checks, manifest.
- `space_robotics_bench`: `feat/four-wheel-steer-alignment` (F19 fix) and
  `feat/panel-remount-visual-config` (camera resolution/depth), stacked on
  `feat/switchable-arm-control`.
- research repo: `experiments/launch/`, `experiments/manifests/`,
  `verifiers/`.
