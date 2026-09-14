# `openral deploy sim` SRB backend — investigation and executable plan

Written 2026-09-14, read-only survey of the pinned OpenRAL revision
(`docs/upstream_pins.md`). User decision: an SRB scene backend **is** to be
built so `openral deploy sim --config scenes/deploy/srb_<scene>.yaml
--initial-task "<mission>"` becomes the single, standard way every baseline
is launched — instead of a bespoke launch file in this repository (which
`docs/lunar_bot_capability_set_plan.md` §3.8 had proposed; that section is
superseded by this document).

## 1. How the existing `isaacsim` backend works (what can migrate)

`python/sim/src/openral_sim/backends/isaac_sim.py` + `tools/isaac_sidecar.py`:

| Concern | Mechanism | Reusable for SRB? |
|---|---|---|
| Interpreter isolation | Isaac Lab runs in its own py3.11 venv; OpenRAL (3.10 here) talks to it out of process. `OPENRAL_ISAAC_SIDECAR_PYTHON` names the interpreter; `provision_isaac_sim` checks/creates the venv before `ros2 launch`. | **Yes, same problem.** SRB is `requires-python ==3.11.*`, run via `~/Programs/isaac-sim/python.sh` (`/home/bingqi/.local/bin/srb`). SRB is not pip-provisionable by OpenRAL (Isaac Sim + SRB's own install) → `provision_srb()` only *checks* (`srb` on PATH, `ISAAC_SIM_PATH`, conda not active) and prints the recipe, like `_sidecar_python`'s error path. |
| Process lifecycle | `SidecarClient`: ping an existing process, else `Popen` the launcher with a resolved argv, poll until it answers or `boot_timeout_s`; reap a stale one; kill only what we spawned. | **Yes, as a pattern**, but the readiness probe becomes ROS (topics appear), not a ZMQ ping. |
| Identity check | `expected_identity={"task","layout"}` compared against the ping reply so a stale sidecar for another scene is rejected. | Replaced: the launch owns the SRB process it spawns; adopting a pre-existing SRB is opt-in only. |
| Data plane | ZMQ REQ/REP + msgpack: `reset` / `step(action)` / `render` / `close`; the sidecar returns `images`, `state`, `joint_positions`, `depth_points`, `scan`, `base_pose`, `sim_time_ns`; the HAL side is `SimAttachedHAL` (steps the env per action, packs the flat action vector, `idle_step`s when idle) + `SimSensorBridge` / `MobileBaseBridge` re-publish the obs as ROS topics. | **No — replace with SRB's native ROS interface.** See §2. |
| Clock | Sidecar reports `sim_time_ns`; the HAL publishes `/clock`; `_scene_backend_has_sim_clock` → `clock_origin=simulation` → `use_sim_time` graph-wide. | SRB's `RosInterface` already publishes `/clock`. Keep `use_sim_time`, disable the HAL's own `/clock` publisher. |
| Scene YAML | `scenes/deploy/isaac_*.yaml`: `scene.backend: isaacsim`, `backend_options: {layout, headless, host, boot_timeout_s, timeout_ms}`. | Same shape; new keys. |
| HAL registry | `_ROBOT_HAL_REGISTRY` in `deploy_sim.py` maps `robot_id` → `openral_hal_<x>` lifecycle node + flags (`manifest_driven`, `supports_sim_env_yaml`, `bare_twin_sim`). **`lunar_bot` has no entry**, so `deploy sim` cannot bring it up today at all. | Add an entry with a new flag (§3). |

## 2. Why the data plane should not be the ZMQ step protocol

SRB already exposes everything the deploy graph needs, over ROS, under
`srb agent ros --interface ros` (`srb/interfaces/interface/ros.py`, verified
live in `docs/srb_integration_notes.md`):

- per-action-term command topics (`cmd_vel`, `switchable_arm`,
  `binary_joint_position`) — the surface `openral_hal_lunar_bot` already
  drives through the safety kernel, verified for all four control modes;
- `joint_states`, IMU, `/tf` (robot, every object, every sensor), cameras
  (`image_rgb`, `image_depth`, `camera_info`, `pointcloud`), RayCaster
  point clouds (the Mid-360 the other agent is adding will appear here with
  no OpenRAL-side work), `terminated`/`truncated`/reward terms;
- `/clock`, and `env{i}/reset` + `envs/reset` services.

Re-marshalling all of that through a ZMQ `step()` would (a) discard the
verified topic HAL for a second, parallel integration (`SimAttachedHAL`
with a LunarBot action packer), (b) push 640×480 RGB-D frames and point
clouds through msgpack every step, (c) couple SRB's stepping to the HAL's
tick (SRB's `ros_agent` loop steps continuously on its own), and (d) miss
SRB-side sensors added by others. The Isaac sidecar exists because Isaac
Lab had no ROS surface; SRB has one. So the SRB backend is **ROS-attached**:
the simulator is an external ROS process that `openral deploy sim` owns.

What is genuinely lost vs. `SimAttachedHAL`: per-episode `reset(seed=…)`.
SRB's reset service takes no seed; the seed is fixed at launch
(`env.seed=<n>` Hydra override). One run = one SRB process = one seed,
which is exactly what §19's `run_manifest.yaml` records anyway.

## 3. Executable plan (openral fork, branch `feat/srb-deploy-backend`)

Each step names the file, the change, and how it is verified. Order is
dependency order; 1–4 are the backend, 5–6 make LunarBot use it.

1. **Schema: `DeployScene.simulator`** (`python/core/src/openral_core/schemas.py`).
   New Pydantic model `ExternalSimulatorSpec`: `argv: list[str]`,
   `cwd: str | None`, `env_set: dict[str,str]`, `env_unset: list[str]`,
   `ready_topics: list[str]` (all must have ≥1 publisher),
   `boot_timeout_s: float`, `publishes_clock: bool`, `attach_existing: bool`
   (default `False`: always spawn and own). Generic — "a ROS-native
   simulator this scene needs on the bus", the sim-path analogue of
   `DeployScene.drivers` (which is real-path only). Fixture test:
   `scenes/deploy/srb_panel_remount.yaml` loads (§1.11 real fixtures).
   Schema addition is backward-compatible (optional field) → no
   `schema_version` bump; record the decision per CLAUDE.md §1.6.
2. **Scene backend module** `python/sim/src/openral_sim/backends/srb.py`,
   registered in `_register_backends()` as scene id `srb`, `fixed_robot=None`,
   `provision=provision_srb`. `provision_srb()` checks `srb` on PATH,
   `ISAAC_SIM_PATH`, that no conda env is active, and raises `ROSConfigError`
   with the exact recipe otherwise (mirrors `_sidecar_python`'s message
   discipline). The factory returns a `SimRollout` whose `reset`/`step`
   raise a typed `ROSConfigError("srb is ROS-attached; use openral deploy
   sim")` — no fake stepping (CLAUDE.md §1.11). Unit test on the error path
   + provision probe.
3. **Launch: spawn and gate the simulator**
   (`packages/openral_rskill_ros/launch/deploy_e2e.launch.py` +
   `python/cli/src/openral_cli/deploy_sim.py`). When the scene declares
   `simulator`: `deploy_sim` resolves `argv`/env (conda stripped,
   `PYTHONPATH` unset, `ISAAC_SIM_PATH` set — the F9 recipe from
   `docs/srb_integration_notes.md`), forwards them as launch args; the launch
   adds an `ExecuteProcess` first, then a readiness gate node (new small
   script `wait_for_topics`, reusing the pattern of `tools/lifecycle_autostart.py`)
   that blocks the HAL's `configure` until `ready_topics` have publishers or
   `boot_timeout_s` elapses (fail loudly, like `_boot_failure_error`). On
   shutdown the process is terminated with its exact PID (never a pattern —
   F10). `clock_origin`: `publishes_clock: true` → `use_sim_time` on, and a
   new HAL param `publish_clock:=false` so the lifecycle node's `/clock`
   publisher (`lifecycle.py` ~L635) is skipped. Verified by launching
   with `--dry-run` (argv rendering) and live (SRB comes up, gate opens,
   graph reaches ACTIVE, `ros2 topic hz /clock` from SRB only).
4. **HAL registry entry** (`deploy_sim.py` `_ROBOT_HAL_REGISTRY`):
   `"lunar_bot": _HalSpec(package="openral_hal_lunar_bot",
   executable="lifecycle_node.py", manifest_driven=True,
   external_sim=True)`. New flag `external_sim` = do **not** inject
   `sim_env_yaml` (no scene-attach), build `hal.sim` from the manifest.
   `robots/lunar_bot/robot.yaml`: `hal.sim:
   "openral_hal.lunar_bot_srb:LunarBotSRBHAL"` (same topic HAL; the
   manifest comment about `hal.real` is rewritten: the HAL is
   transport-shaped, `sim` vs `real` is which process is on the other end).
   Verified: `openral deploy sim --config … --dry-run` renders the graph;
   live, `/joint_states` carries SRB's 21 joints.
5. **Scene YAML** `scenes/deploy/srb_panel_remount.yaml`:
   `robot_id: lunar_bot`; `scene: {id: srb, backend: isaacsim,
   observation_height: 480, observation_width: 640, cameras: [front, wrist],
   backend_options: {env_id: "srb/panel_remount_visual", hydra_overrides:
   ["env.robot=lunar_bot", "env.seed=0", "env.camera_resolution=[640,480]",
   "env.camera_data_types=[rgb,depth]"]}}`; `simulator: {argv: ["srb",
   "agent", "ros", "--env", "panel_remount_visual", "--headless",
   "--interface", "ros", "env.robot=lunar_bot", …], env_unset:
   [CONDA_PREFIX, …, PYTHONPATH], env_set: {ISAAC_SIM_PATH: …},
   ready_topics: ["/srb/env0/robot/joint_states", "/clock",
   "/srb/env0/cam_front/image_rgb"], boot_timeout_s: 600, publishes_clock:
   true}`; `seed: 0`. The Hydra dotlist overrides for camera resolution /
   data types are **to be verified** on the SRB side (they are
   `VisualExtCfg` fields inherited by `VisualTaskCfg`, and SRB reads
   `sys.argv` dotlist overrides in `srb/utils/hydra/sim.py` ~L486); if they
   do not take, the fallback is a `panel_remount_visual` cfg change on
   `feat/panel-remount-visual-config` in the SRB fork.
6. **Sensor bridge attaches here** (capability-set item 2,
   `docs/lunar_bot_capability_set_plan.md` §3.2): the bridge node is added
   to `openral_hal_lunar_bot` and the launch starts it after the HAL. With
   `sensors:` declared in the manifest, the existing derivation in
   `deploy_e2e.launch.py` (~L1339: `camera_names` from RGB sensors) wires
   world state, the detector and the scene VLM with no further change.
   Verified: world state lists both cameras; a detection of the panel lifts
   to a 3-D pose within ~0.2 m of `/tf` truth.

Exit condition for the backend: `openral deploy sim --config
scenes/deploy/srb_panel_remount.yaml --initial-task "drive forward one
metre, then open the gripper"` brings up SRB + kernel + HAL + bridge +
world state + perception + runner + reasoner from one command, the
reasoner dispatches `rskill-procedural-body_twist`, the base moves, and the
gripper opens — with no manual process juggling. (The manipulation skills
and Nav2 come after, per §8.3.)

## 4. What this changes in the capability-set order

`docs/lunar_bot_capability_set_plan.md` §3.8 (a launch file in this repo)
is dropped. The run-manifest writer (§19) stays in this repo but wraps
`openral deploy sim` (records both submodule commits, the scene YAML, the
mission text, seed, model config, trace/rosbag locations). Revised order
in `execution_plan.md` §8.3: RM-75 limits (done) → sensor bridge → **SRB
deploy backend** → procedural manipulation skills → F19 → Nav2 (Mid-360)
→ MoveIt → verifier → run-manifest writer → remaining kernel checks →
B3.

## 5. Mid-360 lidar — interface contract with the SRB-side agent

The physical LunarBot carries a Livox Mid-360 (user, 2026-09-14). Another
agent adds it to `lunarbot.py` in the SRB fork; this project does **not**
touch `lunarbot.py` concurrently. What the OpenRAL side will consume, and
therefore asks the SRB side to fix and record:

- sensor key in `scene._sensors` (proposed: `lidar`) → SRB publishes
  `/srb/env0/lidar/pointcloud` (`sensor_msgs/PointCloud2`, frame
  `srb/env0/lidar`) automatically via `RosInterface` for any `RayCaster`;
- mount: parent prim + offset on `chassis_base_link` (record the numbers;
  the sensor bridge re-roots `srb/env0/lidar` → `chassis_base_link →
  lidar_link`);
- pattern: Mid-360 is a non-repetitive 3-D scanner, 360° × 59° FOV
  (−7° … +52°), 40 m range at 10 % reflectivity, ~200 k points/s, 10 Hz —
  whichever `RayCasterCfg` pattern approximates it, record it and the
  chosen ray count / update period so the paper can state the fidelity.

OpenRAL side (capability-set item 5, Nav2): `has_lidar: true` selects the
`lidar` costmap profile, which needs a 2-D `/scan` for `slam_toolbox` and
the collision monitor. `pointcloud_to_laserscan` is **not** installed on
this host (checked); plan is `apt install ros-humble-pointcloud-to-laserscan`
and a slice of the Mid-360 cloud → `/scan`, while Nav2's local costmap
additionally consumes the full `PointCloud2` through the `voxel_layer`. In
simulation `map → odom` is truth from the bridge, so `slam_toolbox` is
optional; it is kept in the graph only if it proves reliable on moon
terrain, otherwise the profile runs without SLAM and the paper says so.

## 6. Open items to verify in the coding round (not assumptions)

- Hydra dotlist overrides for `camera_resolution` / `camera_data_types` via
  `srb agent … env.camera_resolution=[640,480]`.
- `srb agent ros` reset service `env0/reset` behaviour mid-run (does it
  re-randomize the panel pose with the fixed seed — needed for repeated
  trials without relaunching Isaac Sim, which costs ~1–2 min per boot).
- `SRB`'s articulation root pose (`srb/env0/robot`) equals the
  `chassis_base_link` pose.
- `use_sim_time` + SRB `/clock` rate vs. the world-state staleness limits
  (`staleness_limit_s` 0.5 s wall vs. sim time).
