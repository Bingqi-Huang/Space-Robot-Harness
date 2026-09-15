# 04 — SRB integration constraints for a rebuilt Mission A/B lunar-base scene

Research-only. Pinned revisions as checked out 2026-09-15 (SRB `main` 75263f9+, openral `master`,
IsaacLab v2.2.1 = `~/isaaclab`, confirmed via `isaac-sim/kit/python/.../__editable___isaaclab_0_45_9_finder.py`).
All geometry read from `assets/srb_assets/robot/mobile_manipulation/lunarbot/lunarbot.usdc` with pxr
(Blender's bundled Python, no sim launched) and cross-checked against the RM-75 URDF. Probe scripts:
`/tmp/phase_c_investigation/usd_probe*.py`, `eg2_fk.py`, `reach.py`, `terrain_probe.py`.

---

## 1. LunarBot physical envelope

### 1.1 Chassis / mounts (USD stage, Z-up, metres; `chassis_base_link` = ground contact plane)

| item | value | source |
|---|---|---|
| overall robot bbox (arm straight up, zero pose) | x −0.677…+0.647, y ±0.526, z 0…1.721 | usd_probe.py |
| chassis hull bbox | x ±0.661, y ±0.526, **z 0.365…0.952** (0.365 m ground clearance under hull) | usd_probe3.py |
| wheel centres / radius | (0.4925, ±0.42705), (−0.5225, ±0.42705); r = 0.1453 | `lunarbot.py:175-181`, USD wheel links at z=0.1453 |
| **arm base (`base_link`)** | **(−0.4475, 0, 0.727)** — on the chassis centre-line, at the **−X end**, 0.23 m in from the −X hull edge, 0.526 m from each side edge | usd_probe.py |
| shoulder (J2 axis, `Link2`) | z = 0.9675 | usd_probe.py; URDF base→J2 = 0.2405 (`rm_description/urdf/rm_75.urdf:88`) |
| RM-75 links | J2→J4 0.256, J4→J6 0.210, J6→flange 0.144 (flange reach 0.610 = datasheet working radius) | `rm_75.urdf:204,320,436`; `docs/lunar_bot_rm75_spec.md` |
| TCP | flange +0.140 m along Link7 +Z (`_TCP_OFFSET`) | `lunarbot.py:23,212` |
| front RGB-D (D435) | `rgbd_camera_frame` (0.4725, 0.092, 0.927), looks along chassis **+X**, pitched 15° down | USD + `lunarbot.py:243-246` |
| front camera optics | f=5 mm, h-aperture 12 mm → **HFOV ≈100°, VFOV ≈84°** (640×480), depth clip 0.05–25 m | `ground_manipulation/visual_ext.py:34-45`; resolution override `openral/scenes/deploy/srb_panel_remount.yaml:64` (default is 64×64, `extension/visual/cfg.py:27`) |
| wrist camera | on Link7, f=10, ap=16 → HFOV ≈77°, clip 0.001–1.5 m | `visual_ext.py:47-58`, `lunarbot.py:247-253` |
| Mid-360 lidar (`lidar_mid360_frame`) | (0.4726, −0.092, 0.8623), mounted inverted | USD, `lunarbot.py:234-241` |
| lidar model (RayCaster) | 40 ch × 360°, vertical −7…+52°, 1° h-res, 40 m | `srb/core/env/mobile/env.py:18-21,101-107` |

**Orientation gotcha:** camera + lidar are at chassis +X, arm is at chassis −X, and `cmd_vel` is
sign-flipped (`scale_linear=-1`, `lunarbot.py:183-191`, "chassis +X drives opposite to the visually
intended forward"). A scene layout must decide which end faces a workstation: the **arm end is the
chassis −X end, i.e. opposite the front camera/lidar mast.** The front camera therefore cannot see
what the arm is manipulating from a straight "back up to the bench" approach — only the wrist camera
can. Also: F23 (`docs/research_findings.md:461-488`) — the sim chassis/mast is a stale CAD revision
(real wheelbase 1065.6 mm symmetric; camera mast at Y=+92 mm).

### 1.2 Reachable TCP band (planar model through J1, joint limits J2 ±130°, J4 ±135°, J6 ±128°;
elbow/wrist kept >5 cm above ground; **ignores arm-link/chassis self-collision** — verify with MoveIt IK)

Distances are measured horizontally **beyond the chassis hull edge** (arm end edge is 0.23 m from J1;
side edge is 0.526 m from J1). From `reach.py`:

| approach | beyond arm-end (−X) edge | beyond side edge |
|---|---|---|
| top-down (±20°) | 0.05 m: z 0.32–1.13; 0.15 m: z 0.34–1.08; 0.25 m: z 0.42–0.98; **≥0.35 m unreachable** | **unreachable** |
| 45° down | 0.05: 0.36–1.29; 0.25: 0.39–1.23; 0.35: 0.48–1.16; 0.45: 0.63–1.01; ≥0.55 unreachable | 0.05: 0.48–1.16; 0.15: 0.63–1.02; ≥0.25 unreachable |
| horizontal (side grasp) | 0.15: 0.56–1.47; 0.35: 0.57–1.38; 0.45: 0.67–1.27; ≥0.55 unreachable | 0.05: 0.57–1.38; 0.15: 0.66–1.28; ≥0.25 unreachable |

Max horizontal TCP distance from J1 axis: 0.75 m.

**Hard consequences for scene design**
- **Nothing below z ≈ 0.32 m is graspable** in any orientation → no ground-lying manipulables. Every
  manipulable must sit on a rack/bench/shelf/mount whose grasp feature is at **z ≈ 0.40–1.10 m**
  (comfortable band for all three approaches ≈ 0.45–1.00 m).
- The target must be within **≈0.05–0.35 m beyond the arm-end edge** of the parked chassis (top-down
  ≤0.25 m; angled/horizontal up to 0.45 m). Side approaches give only ≈0.15 m of usable depth.
- So a workstation front face must allow the rover to park its **−X end** within ~0.1–0.3 m of the
  grasp feature: benches/racks need clear floor under/in front of them (hull ground clearance is
  0.365 m, but wheels at x=−0.5225 ±0.1453 stick out to x=−0.668).

### 1.3 Gripper (Inspire EG2-4C2 as modelled; no datasheet in this repo)

| item | value | source |
|---|---|---|
| actuated joints | 6 lock-step joints, stroke 0.82 rad each; 0 = closed | `lunarbot.py:25-45,96-101` |
| closed | fingers in contact (inner gap 0) | USD rest pose, eg2_fk.py |
| **open inner jaw gap** | **≈0.066 m** (fingertip centres 0.087 m apart, finger pads stay parallel) | `eg2_fk.py` (FK over joint1/4/5/6 axes from USD) |
| finger pad | ≈21 mm deep (x), 18 mm wide (y), distal link ≈34 mm tall (z 1.687–1.721) | usd_probe4.py |
| gripper length flange→fingertip | 0.143 m | usd_probe3.py |
| joint effort limit / stiffness | 0.9 N·m, 200 N·m/rad per joint | `lunarbot.py:142-149` |
| grip normal-force upper bound | ~(0.9+0.9) N·m / 0.042 m proximal lever ≈ 40 N per finger (saturated; approximate) | derived |

**Graspable feature width: ~10–60 mm** (≥ a few mm margin inside the 66 mm stroke; contact height
≤ ~30 mm of finger pad). Handles/grips 15–45 mm are the robust range. Anything wider needs a
dedicated handle/lug.

**Mass:** datasheet rated payload 5 kg (`docs/lunar_bot_rm75_spec.md`), incl. gripper (EG2 mass not in
repo). Sim torque limits don't bind (J2 60 N·m at 0.75 m under 1.62496 m/s² lunar g,
`srb/core/domain.py:38-39`, would allow ~49 kg). **The practical sim limit is holding stiffness:**
gravity is disabled on arm links and the relative-mode differential-IK action "provides zero
position-holding stiffness against persistent external disturbances" (`lunarbot.py:68-75`) → a
payload will sag under CARTESIAN_TWIST. Recommend manipulables **≤ ~1 kg** (lunar weight ≤1.6 N)
until a JOINT_POSITION hold under load is verified; ≤5 kg is the absolute datasheet cap. Friction
defaults: static/dynamic 1.0, `multiply` combine (`env_cfg.py` sim physics_material, L114-120).

### 1.4 Base / corridor

| item | value | source |
|---|---|---|
| Nav2 footprint radius | 0.82 m (farthest wheel centre 0.6749 + wheel r) | `openral/robots/lunar_bot/robot.yaml:131` (+ comment L120-131) |
| footprint polygon | x −0.6678…+0.6378, y ±0.57235 | `robot.yaml:148-152` |
| inflation radius | footprint_radius + clearance = 0.870 m | `docs/research_findings.md:1219-1221`; `openral_core/schemas.py` `nav2_param_overrides` (~L2147) |
| motion model | DiffDrive (commands are (v, ω) only, no strafing) | `robot.yaml:153-160` |
| true circumscribed radius (hull corners) | √(0.677²+0.526²) ≈ 0.857 m (+arm overhang if not stowed; arm stow pose reaches z 1.72) | USD bbox |

**Consequences:** in-place turns need a ≥1.72 m diameter clear circle (≥1.9 m with inflation margin);
straight corridors/doorways ≥1.2 m physically (1.05 m body + margin) but **≥1.8–2.0 m for Nav2 to
plan through** with inflation 0.87 m. F19 steering is fixed by steer-before-drive (F30) but large
in-place turns are still slow; prefer layouts with turnaround pads over tight bays.
Speed caps: 0.3 m/s linear, 0.5 rad/s angular (`robot.yaml:107-108`).

---

## 2. How SRB composes scenes

### 2.1 Scenery override path (the key finding — SRB-native, precedent exists)

- `BaseEnvCfg.scenery: Scenery | MobileRobot | AssetVariant | None = AssetVariant.PROCEDURAL`
  (`srb/core/env/common/base/env_cfg.py:76`). `_add_scenery` (L377-490): `None` → no scenery (L384-386);
  an `AssetVariant` → registry lookup (the MoonSurface/procedural path, L388-472); **a `Scenery`
  instance is used as-is** (L471-473), its prim path set to `{ENV_REGEX_NS}/scenery` (or
  `/World/scenery` if `stack`), converted to a static `AssetBaseCfg` with articulation/rigid-body
  disabled (L476-483) and put in `scene.scenery`.
- Hydra: `env.scenery=<name>` instantiates a registered scenery class by name
  (`srb/utils/hydra/sim.py:198-199`, `SceneryRegistry.get_by_name`, `srb/core/asset/scenery/scenery.py:115-119`).
- **Precedent:** `Lunalab(Subterrane)` and `Oberpfaffenhofen(Terrain)` are USD-file sceneries
  (`srb/assets/scenery/facility.py:21-60,178-190`): `AssetBaseCfg(spawn=UsdFileCfg(usd_path=...,
  collision_props=CollisionPropertiesCfg()))`; Lunalab additionally composes a procedural
  `MoonSurface` sub-terrain, boulders, and sets `scene.env_spacing` in a `setup_extras(env_cfg)` hook
  (called for every `Asset` in the cfg by `_setup_asset_extras`, `env_cfg.py:865-876`).
- **Path for the rebuild:** a new `srb/assets/scenery/<lunar_base>.py` → `class LunarBase(Terrain)`
  with a `UsdFileCfg` base map (authored terrain pad + base structures), registered automatically,
  selected per task (`scenery = assets.LunarBase()`) or via `env.scenery=lunar_base`. Robot spawn:
  `GroundEventCfg.randomize_robot_state` drops the robot at x,y ±0.5, z 0.4–0.6, random yaw, random
  velocity every reset (`srb/core/env/mobile/ground/env.py:28-48`) — must be overridden with a fixed
  dock pose for a base map.
- A flat-only alternative: `GroundPlane` scenery (`srb/assets/scenery/ground_plane.py`, `/World/ground_plane`);
  the RayCaster special-cases a `Plane` prim as an infinite plane (`isaaclab/.../ray_caster.py:173-176,198-202`).

### 2.2 Why the procedural MoonSurface cannot host fixed infrastructure (quantified)

`flat_area_size` is **not a flat disk.** In `simforge_foundry/geometry/terrain/moon_surface/nodes.py`
it is used twice: (a) crater/rock scatter points with horizontal radius `< flat_area_size` are deleted
(L2603-2610 `LENGTH < flat_area_size` → `Delete Geometry`); (b) vertex **z is multiplied** by
`FloatCurve(QUADRATIC_SPHERE gradient(position / flat_area_size))` (L2378-2382, 2448-2450, curve
points (0,1),(0.025,0.975),(0.5,0.1),(1,0) at L1482-1492) → z is exactly 0 only at the centre and
ramps smoothly back to full relief at r = flat_area_size. Measured on the cached spacing-32 terrain
(`~/.cache/simforge/model/moon_surface/2b2fbbe48fe9`, scale (32,32,3.2), F=4.22; `terrain_probe.py`):

| r from env origin | terrain z relative to centre |
|---|---|
| 0–0.5 m | ±0.001 |
| 0.5–1 m | ±0.01 |
| 1–1.5 m | ±0.05 |
| 1.5–2 m | −0.12…+0.15 |
| 2–2.5 m | −0.24…+0.28 |
| 2.5–3 m | −0.35…+0.41 |
| 3–4 m | −0.49…+0.71 |

So F18's "genuinely flat pad within ~half of flat_area_size" was wrong: at F18's own 2.1 m "safe
radius" relief is ±0.28 m. `panel_remount_v2` (spacing 160 → scale (160,160,16), F≈9.7) placed static
pedestals at z=0 at r≈3.5 m (r/F≈0.36); the spacing-160 mesh is not in the simforge cache any more,
but relief of order 0.1–0.3 m there is consistent with the floating pedestal the user saw.
**Conclusion: don't place static infrastructure on the procedural terrain at fixed z; author the base
terrain (with a genuinely flat pad) as part of the base USD, or measure heights per placement.**

### 2.3 Scene entities per task

- Entities are dataclass fields on the task's `SceneCfg` (`InteractiveSceneCfg`), `spawn=None` then
  filled in `__post_init__` (pattern in `panel_remount_v2/task.py`). Types available:
  `AssetBaseCfg` (static, no physics state), `RigidObjectCfg`, `ArticulationCfg`,
  `RigidObjectCollectionCfg` (many rigid objects as one batched asset; SRB precedent
  `srb/tasks/manipulation/{sample_collection/task_multi.py, peg_in_hole_assembly/task_multi.py,
  solar_panel_assembly/task.py}`).
- **The scene graph is fixed once built** (vectorized); variants must move/enable things, not add/remove.
- `num_envs` default 1 (`scene_cfg.py:10`), `replicate_physics=False`; `env_spacing` only matters for
  num_envs>1 (and it is what sizes procedural terrain via `spacing`). For a large static base with
  num_envs=1, spacing is irrelevant except that the procedural scenery path must be off. Multi-env
  with one shared base: `stack=True` puts scenery at `/World/scenery` with env_spacing 0 (`env_cfg.py:155-157, 476-480`).
- `sim.device` is **CPU** unless a `DeformableObjectCfg` is present (`env_cfg.py:857-863`); PhysX
  runs on CPU with CCD (`env_cfg.py` PhysxCfg `enable_ccd=True`). Every dynamic prop costs CPU physics.

### 2.4 Articulated props (hatch / drawer / rotary valve / connector)

- No passive articulated prop exists in SRB; SRB articulations are robots/tools
  (`srb/assets/object/tool/screwdriver.py:68-100` shows `ArticulationCfg` + `ImplicitActuatorCfg` +
  `ArticulationRootPropertiesCfg`).
- IsaacLab precedent for exactly this: the Sektion cabinet —
  `ArticulationCfg(spawn=UsdFileCfg(.../Props/Sektion_Cabinet/sektion_cabinet_instanceable.usd),
  init_state joint_pos={door_*,drawer_*}, actuators={ImplicitActuatorCfg(stiffness 10, damping 1–2.5)})`
  (`isaaclab_tasks/manager_based/manipulation/cabinet/cabinet_env_cfg.py:55-85`). Passive
  drawers/doors = low-stiffness/damping implicit actuators; detents/latches via stiffness to a target.
- Fix to the ground with `ArticulationRootPropertiesCfg(fix_root_link=True)` (creates a world
  FixedJoint, `isaaclab/sim/schemas/schemas_cfg.py:40-46`) or a fixed joint authored in the USD.
- Spawn-launch mitigation for any rigid body starting near colliders:
  `RigidBodyPropertiesCfg(max_depenetration_velocity=...)` (`schemas_cfg.py:92,427`; used in
  screwdriver.py) — caps the kind of 4.8 m/s ejection seen in heldout_state_mismatch.

---

## 3. What reaches ROS / verifier / perception for free

From `srb/interfaces/interface/ros.py` (`_broadcast_transforms`, L936-1077; joint states L195-206, 305-322):

- **TF** `srb/env{i}` → `srb/env{i}/<name>` for every `RigidObject` and `Articulation` root
  (L937-968), every object in a `RigidObjectCollection` (`srb/env{i}/<object_name>`, L1005-1039), and
  **every link of every articulation** `srb/env{i}/<asset>` → `srb/env{i}/<asset>/<body>` (L1040-1076).
  Cameras/RayCaster/IMU sensor frames too (L969-~1000).
- **`/srb/env{i}/<articulation>/joint_states`** (`JointState` pos/vel/effort) for **all** scene
  articulations (L195-206, 305-322) — so a hatch/valve/drawer joint angle reaches the verifier with no
  new SRB code.
- `/srb/env{i}/{reward, reward/<term>, terminated, truncated}` (L144-170, 275-281) — reward terms are
  auto-published per key of `info["reward_terms"]`, so task-computed effect predicates can be exposed
  as extra reward-term topics for free.
- **Not published:** `AssetBaseCfg` static props (no TF) and `scene.scenery`. Anything the verifier or
  a baseline Lookup must localise must be a rigid object/collection/articulation, or its pose must
  come from the scenario manifest.
- Cost: TF building is a Python loop with `.item()` per value per body per tick — bodies-heavy
  articulations add per-tick CPU (the F28 profile bucket `tf`).

---

## 4. Performance constraints

- F28 (`docs/research_findings.md:941-1021`): after fixes, full deploy graph runs ~12 Hz `/clock`
  (RTF ≈ 0.24 at 50 Hz agent rate). Remaining ~82 ms/tick: CPU PhysX 3 substeps ≈21 ms, render submit
  ≈12 ms, **≈30 ms GPU render wait for three 640×480 RTX cameras**, annotator readback ≈4.5 ms. Levers
  noted there: drop `cam_scene` in deploy, lower RTX preset/DLSS off, and the
  `PxShape::getMaterialFromInternalFaceIndex` terrain-contact warning spam (~30/substep).
  `sim.device=cuda` is **not** an option (no CCD on GPU PhysX).
- Implications: a heavier base (many lights, translucent/reflective materials, high-poly
  instanced meshes) increases the render-wait bucket directly; many dynamic props increase the CPU
  PhysX bucket; triangle-mesh terrain contacts are already the noisiest. Prefer static colliders with
  simple convex/box collision proxies, instancing, and few dynamic bodies.
- Camera→OpenRAL DDS large-message loss (~2 Hz received vs 12 Hz published) is still open (F28 last
  bullet) — any scene relying on perception inherits it until the Fast-DDS SHM/buffer fix lands.

### 4.1 Lidar sees only ONE mesh → Nav2 is blind to base structures unless they are in that mesh

- SRB attaches `lidar_robot` only if the robot has `frame_lidar` **and scenery is not None**
  (`srb/core/env/mobile/env.py:76`), with `mesh_prim_paths=[scenery prim path of env_0]` (L96-100).
- IsaacLab v2.2.1 `RayCaster` hard-requires exactly one path (`ray_caster.py:164-167`) and within it
  takes **the first `Mesh` child only** (`get_first_matching_child_prim`, L179-181), baked once into a
  warp BVH (L188-193; SRB only moves it to CUDA, `srb/core/sensor/ray_caster.py:21-32`). Faces are read
  as a flat index list (must be triangulated). No `MultiMeshRayCaster` in this IsaacLab version.
- Nav2 costmaps for this robot use **only** `LaserScan` from the lidar (`nav2_panda_mobile.yaml:283-298,
  367-379`; `pointcloud_to_laserscan` from `/openral/lidar/points`, `nav2.launch.py:249-266`) with
  `min_height 0.05 / max_height 0.6` in `chassis_base_link` and obstacle/raytrace range 2.5/3.0 m.
- **Consequences:** separate building/prop prims (AssetBaseCfg, rigid objects, articulations) are
  invisible to lidar and therefore to Nav2 — the rover will plan through walls and props. Options:
  (1) bake terrain + all static structure exteriors into **one triangulated lidar/collision mesh**
  inside the scenery USD (first Mesh child); (2) patch SRB's `RayCaster` subclass to merge several
  static meshes into one warp BVH (dynamic props still invisible); (3) add the front depth-camera
  pointcloud as a second costmap observation source (limited to the camera's 100° front FOV, and the
  camera end is opposite the arm end). Also: obstacles entirely above 0.6 m or thinner than the
  0.05 m floor band (overhangs, bench tops on thin legs) never enter the scan.

---

## 5. Placing static structures at correct terrain height

- Best: don't depend on procedural terrain — author the base's ground pad (flat, known z) in the
  scenery USD; place everything relative to it.
- Offline (no GPU): simforge caches generated terrain as USDZ at `~/.cache/simforge/model/<name>/<hash>/`
  with the generation `cfg.json` (`simforge/utils/cache.py:5`, `generator.py:47`); the mesh vertices can
  be read with pxr and sampled at (x,y) exactly as `terrain_probe.py` does (note spacing-160 terrain
  was not found in the cache today — it regenerates on demand and is seed-deterministic via
  `SimforgeAssetCfg.seed`, `simforge/integrations/isaaclab/spawner/simforge_asset/cfg.py:21-23`).
- In-sim: PhysX scene query `omni.physx.get_physx_scene_query_interface().raycast_closest(origin,
  dir, max_dist)` (used by `isaacsim.core.utils/collisions.py:57`), or IsaacLab's warp
  `raycast_mesh` (`isaaclab/utils/warp/ops.py:24`) against the scenery mesh — e.g. in a task's
  `__init__`/reset event to snap static props to ground before the first physics step.
- For rigid props, spawn a few mm above the measured surface and cap `max_depenetration_velocity`.
