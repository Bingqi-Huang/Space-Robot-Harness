# RTX Lidar integration for the Mid-360 — investigation and executable plan

Written 2026-09-14, immediately after the RayCaster-based Mid-360 landed
(`space_robotics_bench` `4baea49`). User decision: RTX Lidar support is a
tracked follow-up (`AGENT/execution_plan.md` item 2c), to start as soon as
the RayCaster version is stable. This project is **imitation learning, not
RL** — no `num_envs` parallelism requirement — which is the load-bearing
fact behind this plan: it removes the reason IsaacLab's own team gave for
*not* wrapping RTX Lidar (see below), so a path IsaacLab considers and
rejects for itself is still the right one for this project.

## 1. Why not stop at the RayCaster version

`isaaclab.sensors.ray_caster.RayCaster` (what `srb/core/env/mobile/env.py`
now uses) has two structural limits, both confirmed by reading
`ray_caster.py::_initialize_warp_meshes` this session, not assumed:

- **Exactly one static mesh**, baked into a Warp BVH once at sensor init.
  It never re-queries the live scene, so it is blind to every other prim
  (task objects, the panel/pedestal, anything that moves).
- For `num_envs > 1`, `mesh_prim_paths` is a single literal USD path (no
  `{ENV_REGEX_NS}` expansion inside `RayCaster` itself, unlike a sensor's
  own `prim_path`) — every env's rays sample the *same* one mesh. Correct
  only for `num_envs == 1`, which is exactly this project's deployment
  shape, so not a blocker here, but worth stating plainly.

RTX Lidar removes both: it ray-traces the actual live render scene every
frame (sees dynamic objects, real materials) and each sensor prim owns its
own render product, so multi-env correctness is a cost question, not a
correctness question.

## 2. Isaac Sim vs. Isaac Lab, and why IsaacLab doesn't wrap this

Isaac Sim is the engine (Omniverse/Kit, PhysX, RTX rendering, the full
sensor extension ecosystem including RTX Lidar). Isaac Lab is a research
framework built on top of it for batched robot learning (`num_envs`,
Gym-compatible envs, the `isaaclab.sensors.*` config classes) — SRB is
itself built on Isaac Lab throughout (`srb/core/env`, `srb/core/sensor`
import `isaaclab.*` directly). Per the IsaacLab GitHub discussion checked
this session (isaac-sim/IsaacLab #1201): the team *evaluated* wrapping RTX
Lidar and **dropped it because it doesn't parallelize** across thousands of
envs the way the Warp `RayCaster` does, and it is explicitly not on their
near-term roadmap. That reasoning does not apply to a single/few-env IL
deployment target — this plan integrates directly against Isaac Sim's own
`isaacsim.sensors.rtx` extension, bypassing IsaacLab's sensor abstraction
entirely, the same way OpenRAL already treats SRB as an external process
rather than a Python dependency.

## 3. What's actually installed here (verified live, this session)

- `isaacsim.sensors.rtx` **is present** in the pinned Isaac Sim 5.1 install
  (`~/Programs/isaac-sim/exts/isaacsim.sensors.rtx`), but is **not loaded**
  by IsaacLab's default headless experience — a bare
  `AppLauncher`-bootstrapped script gets `ModuleNotFoundError: No module
  named 'isaacsim.sensors'` until `enable_extension("isaacsim.sensors.rtx")`
  is called first (confirmed by reproducing the failure and the fix live).
  **First thing to check when implementing:** whether SRB's own experience
  files (`apps/srb*.kit`) already enable it — if not, add it there so
  `srb agent ros --interface ros env.robot=lunar_bot` gets it for free.
- The extension ships real lidar profiles as **JSON files**, still present
  on disk (`exts/isaacsim.sensors.rtx/data/lidar_configs/{HESAI,Ouster,
  SICK,SLAMTEC,Velodyne,ZVISION,NVIDIA}/*.json`) and still searched at
  runtime via the `app.sensors.nv.lidar.profileBaseFolder` carb setting
  (`exts/isaacsim.sensors.rtx/config/extension.toml`), which includes the
  bare `data/lidar_configs/` root itself as a search path — a JSON dropped
  directly there needs no extra search-path configuration.
- **No Livox profile exists in any of these vendor folders**, and per the
  IsaacSim GitHub discussions checked (#183, #685) this isn't a version gap
  to "catch up on" — no official Isaac Sim release, old JSON-scan
  architecture or new one, has ever shipped one. Community "Livox Mid360"
  JSON snippets found on forums are third-party, hand-authored against the
  pre-5.0 JSON-scan mechanism.

## 4. The two-tier config-resolution mechanism (read from source, not inferred)

`isaacsim/sensors/rtx/impl/commands.py::IsaacSensorCreateRtxSensor`:

1. `_add_reference()` — the **gated path**. Loops `SUPPORTED_LIDAR_CONFIGS`
   (`impl/supported_lidar_configs.py`, a hardcoded dict of ~20 official
   Nucleus USD asset paths, e.g. `/Isaac/Sensors/HESAI/XT32_SD10/
   HESAI_XT32_SD10.usd`) and only proceeds if the given `config` string
   matches that asset's filename stem (with/without the vendor prefix,
   spaces-for-underscores tolerated). **A custom "Livox_Mid360" name will
   never match here** — this is a fixed list of pre-built vendor USD
   assets, not something a JSON drop-in can extend.
2. `_call_replicator_api()` — falls through to
   `rep.functional.create.omni_lidar(config=..., ...)` if step 1 finds no
   match. **Not yet empirically confirmed whether this accepts an arbitrary
   config name** (this session's one test used a malformed config string —
   `"HESAI/Hesai_XT32_SD10"` instead of the whitelist's own
   `"HESAI_XT32_SD10"` — and the whole command chain returned `None`
   without a clear error; inconclusive, not a negative result). **First
   concrete task for whoever implements this:** smoke-test
   `LidarRtx(prim_path=..., config_file_name="HESAI_XT32_SD10")` (a
   provably-valid whitelisted name) to confirm the baseline path works at
   all in this install, then retry with an unlisted name to see whether it
   reaches the Replicator path and what happens.
3. If both fail, the deprecated `_create_camera_prim()` path (Camera-prim
   based, pre-5.0 mechanism, explicitly slated for removal) is the last
   resort — not worth relying on for new work.

**If the Replicator path also rejects unlisted names**, the fallback is to
author the `OmniLidar` prim directly with `pxr` — apply
`IsaacRtxLidarSensorAPI`/`OmniSensorGenericLidarCoreAPI` (schema names seen
in `LidarRtx.__init__`'s validation check) and set whatever attribute holds
the config name directly, the same way this session hand-authored the
RayCaster mount frame's `PhysicsRigidBodyAPI`/`PhysicsFixedJoint` schema
attributes in `lunarbot.usdc` by reading an existing prim's exact attribute
set first. The exact attribute name was not empirically pinned down this
session — do that first via `prim.GetProperties()` on a
whitelist-created reference sensor, exactly as this session's
`joint_and_mass_dump.txt`/`verify_usd.py` scripts did for the physics
joints.

## 5. The Mid-360's real scan pattern is a solved data problem, not new research

`Livox-SDK/livox_laser_simulation` (Livox's own open-source Gazebo plugin)
**officially supports the Mid-360**, including a real scan-pattern file at
`scan_mode/mid360.csv`: **24,000 time-stamped (time, azimuth, zenith)
tuples** per repeating cycle, generated from the actual non-repetitive
scan trajectory. This is the ground-truth source — no need to reverse the
Risley-prism physics or approximate with a rotary raster. **Check the
repo's license before pulling the CSV in**, but this is the correct source
to convert, not a placeholder.

The RTX Lidar JSON schema supports exactly this via `scanType: "solidState"`
(confirmed against a real, large example on disk —
`NVIDIA_ML30S`-class `ZVISION_ML30S.json` ships **51,200** points in a
single `emitterStates` entry, each with its own `azimuthDeg`/`elevationDeg`/
`fireTimeNs`/`channelId`/`rangeId`/`bank` value — an arbitrary point list,
not a rotating-line raster). Conversion is a straightforward data mapping:
`mid360.csv`'s (azimuth, zenith, time) columns → the JSON's
`azimuthDeg`/`elevationDeg`/`fireTimeNs` arrays (zenith→elevation needs a
90°-offset convention check against the JSON schema's own convention, seen
in the Hesai example: `elevationDeg` there runs +15°..-16° with 0° as
horizontal, i.e. elevation not zenith — convert accordingly).

Physical parameters to set from Livox's official Mid-360 datasheet
(fetch and confirm the actual PDF when implementing — do not trust this
plan's numbers as final): `nearRangeM` ≈0.1 (published blind-zone radius),
`farRangeM` — the commonly cited headline figure is 40 m @ 10% reflectivity
(matches the community JSON parameters already seen in the earlier RTX
Lidar research pass this session), `wavelengthNm` — Livox's mid-tier
lidars are commonly 905 nm class-1 devices, confirm against the datasheet
rather than assuming.

## 6. Runtime data access (confirmed by reading the actual class)

`isaacsim.sensors.rtx.LidarRtx` (`impl/lidar_rtx.py`, fully read this
session — not the deprecated `_create_point_cloud_graph_node`/
`add_point_cloud_data_to_frame` methods, all explicitly marked deprecated
as of Isaac Sim 5.0):

```python
lidar = LidarRtx(prim_path="/World/.../lidar_mid360", config_file_name="Livox_Mid360",
                  translation=..., orientation=...)
lidar.initialize()
lidar.attach_annotator("IsaacExtractRTXSensorPointCloudNoAccumulator")
# or "IsaacCreateRTXLidarScanBuffer" for a raw buffer instead of an
# already-accumulated point cloud; "IsaacComputeRTXLidarFlatScan" for a 2D
# flat-scan projection if that's ever useful for a cheap /scan-only path.
...
frame = lidar.get_current_frame()  # dict keyed by attached annotator name
```

No `num_envs`/tensor batching here — this is a plain per-instance Python
object with its own Replicator render product. For `num_envs > 1` each env
needs its own `LidarRtx` instance (real per-instance GPU render cost,
unlike `RayCaster`'s cheap batched Warp raycasting) — another reason this
approach fits a single/few-env IL target better than mass-parallel RL,
consistent with §1-2.

## 7. SRB/OpenRAL integration surface — what has to be built, not reused

- **No IsaacLab `SensorBase` wrapper exists for this** — `srb/core/sensor`
  cannot just re-export it the way it does `RayCaster`/`Imu`/`Camera`. A
  thin custom sensor class is needed in `srb/core/sensor/` (does not need
  to subclass IsaacLab's `SensorBase`; it only needs to expose whatever
  minimal interface `srb/core/env/mobile/env.py` and
  `srb/interfaces/interface/ros.py` need — construction from a `Frame`-like
  pose, a per-step data pull, a `.data` accessor shape close enough to
  `RayCasterData` that the rest of the code doesn't need to special-case
  it unnecessarily).
- **`srb/interfaces/interface/ros.py` needs a new branch.** Its RayCaster
  point-cloud publishing (`elif isinstance(sensor, RayCaster):` around
  line 802) won't match a custom wrapper class — add
  `elif isinstance(sensor, <NewLidarRtxWrapper>):` alongside it, reusing
  the same `PointCloud2` construction pattern already there.
- **Env wiring mirrors this session's `RayCasterCfg` pattern** in
  `srb/core/env/mobile/env.py` (`self._robot.frame_lidar`-gated
  construction in `__post_init__`, `self.scene.sensors.get("lidar_robot",
  None)` retrieval in `__init__`) — same shape, different sensor class
  underneath. Keep `frame_lidar` as the single source of truth for mount
  pose so both the RayCaster and RTX paths (if both are kept, e.g. RayCaster
  as a cheap/parallel-friendly fallback mode) read the same CAD-derived
  transform recorded in `docs/research_findings.md` F23.

## 8. Ordered execution plan

Each item independently verifiable before the next starts (per
`AGENT.md` rule 0.11).

1. Confirm/add `isaacsim.sensors.rtx` in SRB's own `.kit` experience files.
2. Smoke-test a **known-good whitelisted** RTX Lidar (`config_file_name=
   "HESAI_XT32_SD10"`) end-to-end in this install: prim creation, annotator
   attach, non-empty point cloud on one step. This isolates "does RTX Lidar
   work here at all" from "does our custom config work."
3. Verify `Livox-SDK/livox_laser_simulation`'s license permits pulling
   `scan_mode/mid360.csv` into this repo; write the CSV→JSON conversion
   script; sanity-check point count/range/elevation-vs-zenith convention.
4. Determine the actual whitelist-bypass mechanism (Replicator arbitrary
   name, or direct `pxr` prim authoring) per §4; get one custom-JSON Mid-360
   RTX Lidar prim producing real point-cloud data in isolation (no SRB env
   yet).
5. Build the thin SRB-side sensor wrapper class + `MobileEnvCfg` wiring
   (§7), gated the same way `frame_lidar` already gates the RayCaster path.
6. Add the `ros.py` publishing branch.
7. Live-verify through `srb agent rand --env panel_remount
   env.robot=lunar_bot --interface ros`: real RTX point cloud on the ROS
   topic, sees the pedestal/panel (the concrete capability RayCaster
   couldn't provide — this is the acceptance criterion for the whole item).
8. Decide whether to keep RayCaster as an alternate/cheap mode or retire it
   for `lunar_bot` once RTX Lidar is proven; do not remove it pre-emptively.

## 9. Open risks, stated plainly rather than papered over

- Whitelist-bypass mechanism unconfirmed (§4) — the single biggest
  technical unknown, resolve first (step 2-4 above), before investing in
  the CSV conversion or SRB-side wrapper.
- A single repeating `solidState` pattern (one CSV cycle replayed
  identically every sensor frame) is not the same as the real hardware's
  continuously-drifting non-repetitive coverage across frames — accept as
  a documented approximation unless per-frame pattern-swapping is later
  judged necessary (would need custom OmniGraph/Python scripting to cycle
  multiple `emitterStates` blocks over time; out of scope for a first pass).
- Per-env RTX render cost — fine for the deployment/IL target this project
  actually has, but would need re-evaluating if the project ever needs
  more than a handful of parallel envs with this sensor active.
- Datasheet numbers (range, wavelength) in §5 are carried from memory/
  earlier community references, not freshly verified against Livox's
  official Mid-360 PDF this session — verify before finalizing the JSON.
