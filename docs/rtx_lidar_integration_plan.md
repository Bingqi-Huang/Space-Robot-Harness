# RTX Lidar integration for the Mid-360 — investigation and executable plan

Written 2026-09-14, immediately after the RayCaster-based Mid-360 landed
(`space_robotics_bench` `4baea49`). User decision: this is **permanent,
repeatedly-reused infrastructure**, not a demo — treated accordingly below.
Everything resolvable through research (not requiring a running
implementation to discover) has been resolved and is stated as fact with a
source, not hedged. Items that can only be settled by actually building the
thing are marked as such explicitly in §9 and nowhere else.

## Status (2026-09-14, implementation attempted the same day)

`srb/core/sensor/rtx_lidar.py` implements and **live-verifies** §3-§7 of
this plan: loading the real Mid-360 scan pattern
(`srb/core/sensor/data/livox_mid360_scan_pattern.npz`, from Livox's own
`livox_laser_simulation`), slicing it into the same sequential
24,000-point wrapping windows the real hardware/plugin uses, building the
`omni:sensor:Core:*` emitter-array kwargs, and authoring a custom
`OmniLidar` prim through the fully-ungated `rep.functional.create.omni_lidar`
path — confirmed live: correct schema applied, all attribute values
(including the full 24,000-element arrays) round-trip exactly as
authored.

**Blocked, not by this code: pulling live point-cloud data through the
sensor.** This is a confirmed upstream Isaac Sim bug, not an SRB or
implementation defect — reproduced identically with both the custom
Mid-360 sensor above AND an official whitelisted reference sensor
(`HESAI_XT32_SD10`, created the fully-supported way), across six different
render-advance mechanisms in headless mode (bare `simulation_app.update()`,
`SimulationContext.step()`, the async `next_render_simulation_async`
matching Isaac Sim's own official test suite, and the purpose-built
synchronous `rep.orchestrator.step()`) and the two documented headless
workarounds from Isaac Sim's own Known Issues page
(`rt_subframes>=2`, `--/exts/isaacsim.core.throttling/enable_async=false`).
In every case, `/Render/PostProcess/SDGPipeline/PostProcessDispatcher`
never advances past reference time 0/0.

**Precisely localized via a non-headless re-run against the machine's real
display** (confirmed live, GUI screenshot inspected): general RTX
rendering is completely healthy — the main Perspective viewport renders
the scene correctly (lit, shaded, shadowed), and the Stage tree shows the
whitelisted sensor's full prim hierarchy (visual mesh + the `OmniLidar`
prim itself) present and correct. But the sensor's own dedicated
render-product preview pane stays solid black throughout, with the GPU
pinned at ~60%/270W (genuine sustained work, not an idle deadlock) and
zero progress for several minutes. So this is specifically the RTX Lidar
synthetic-data-generation render-product/dispatcher path that never
produces a frame — in both headless and windowed/GUI mode alike — not a
headless-only, GPU-driver, or general-renderer issue.

Matches [isaac-sim/IsaacSim#110](https://github.com/isaac-sim/IsaacSim/issues/110)
("Cannot retrieve RTX lidar data using headless Python script", still open)
and an [NVIDIA forum
thread](https://forums.developer.nvidia.com/t/unable-to-reliably-produce-lidar-data-in-a-headless-simulation/337835)
reporting the identical symptom, where an NVIDIA moderator stated (2025-09-24)
the issue "has been fixed in Isaac Sim 5.1.0". **That lead was chased and
closed out, not left as a guess**: downloaded NVIDIA's official
`isaac-sim-standalone-5.1.0-linux-x86_64.zip` "GA" package directly and
compared it byte-for-byte-equivalent (VERSION string, extension versions
like `omni.replicator.core-1.12.27+107.3.3`) against our pinned
`5.1.0-rc.19` install — **identical**. NVIDIA shipped the RC build
unchanged as the GA release; there is no smaller, same-series upgrade that
could contain this fix (deleted the redundant download afterward, no
disk left behind). The only newer Isaac Sim releases are 6.0.0/6.0.1/6.1.0
(checked the full release list) — a two-major-version jump requiring an
IsaacLab upgrade from the pinned 2.2.1 and a full SRB re-verification;
disproportionate to this one sensor and not undertaken without an
explicit user decision to fund that migration.

**Consequence for `srb/core/env/mobile/env.py`**: not wired in as the
active `lidar_robot` sensor. RayCaster remains the active implementation
(unchanged, still working, per `docs/research_findings.md` F23). Wiring
`rtx_lidar.py`'s sensor into the env lifecycle and `ros.py`'s publishing
loop (§9) is real remaining work, but doing it now would mean shipping and
testing an env-integration layer against a data source confirmed broken
at the source — not a productive use of effort until the Isaac Sim build
is updated. Also tried and ruled out: the official standalone example's
`enable_motion_bvh` flag (`--/renderer/raytracingMotion/*` carb settings)
— produced genuinely different resource behavior (a CPU burst to ~1690%
across many threads, unlike any prior attempt) but still zero data after
a 4-minute run. Full account, including every avenue tried, in
`docs/research_findings.md` F24 — treat that as the up-to-date
authoritative record. **Next step, concretely: re-run this same live
verification (a self-contained repro is in this session's scratchpad, not
committed — recreate from `srb/core/sensor/rtx_lidar.py` + the six
-mechanism list above, plus `enable_motion_bvh`) after moving to Isaac Sim
6.x (the only available newer release) or after NVIDIA ships an actual
point-fix to the 5.1 line.**

This project is **imitation learning, not RL** — no `num_envs` parallelism
requirement — which is the load-bearing fact behind this plan: it removes
the reason IsaacLab's own team gave for *not* wrapping RTX Lidar (see §2),
so a path IsaacLab considers and rejects for itself is still the right one
for this project.

## 1. Why not stop at the RayCaster version

`isaaclab.sensors.ray_caster.RayCaster` (what `srb/core/env/mobile/env.py`
now uses) has two structural limits, confirmed by reading
`ray_caster.py::_initialize_warp_meshes`:

- **Exactly one static mesh**, baked into a Warp BVH once at sensor init.
  It never re-queries the live scene, so it is blind to every other prim
  (task objects, the panel/pedestal, anything that moves).
- For `num_envs > 1`, `mesh_prim_paths` is a single literal USD path (no
  `{ENV_REGEX_NS}` expansion inside `RayCaster` itself, unlike a sensor's
  own `prim_path`) — every env's rays sample the *same* one mesh. Correct
  only for `num_envs == 1`, this project's deployment shape.

RTX Lidar removes both: it ray-traces the actual live render scene every
frame (sees dynamic objects, real materials) and each sensor prim owns its
own render product, so multi-env correctness becomes a cost question, not
a correctness question.

## 2. Isaac Sim vs. Isaac Lab, and why IsaacLab doesn't wrap this

Isaac Sim is the engine (Omniverse/Kit, PhysX, RTX rendering, the full
sensor extension ecosystem including RTX Lidar). Isaac Lab is a research
framework built on top of it for batched robot learning (`num_envs`,
Gym-compatible envs, the `isaaclab.sensors.*` config classes) — SRB is
itself built on Isaac Lab throughout. Per the IsaacLab GitHub discussion
(isaac-sim/IsaacLab #1201): the team *evaluated* wrapping RTX Lidar and
**dropped it because it doesn't parallelize** across thousands of envs the
way the Warp `RayCaster` does, and it is explicitly not on their near-term
roadmap. That reasoning does not apply to a single/few-env IL deployment
target — this plan integrates directly against Isaac Sim's own
`isaacsim.sensors.rtx` extension, bypassing IsaacLab's sensor abstraction
entirely, the same way OpenRAL already treats SRB as an external process
rather than a Python dependency.

## 3. The real mechanism — resolved, not a JSON file at all

This supersedes an earlier, wrong hypothesis from the first research pass
(that a dropped-in JSON profile, found via the `profileBaseFolder` search
path, is what the runtime reads). Reading the actual creation code and the
generated USD schema directly settles it:

**A custom lidar is authored as literal USD attribute values on an
`OmniLidar` prim — there is no live JSON-loading path in this version.**
The schema (`OmniSensorGenericLidarCoreAPI`) has an
`omni:sensor:Core:emitterStatesFile` string attribute whose own doc string
says plainly: *"File containing the emitter states of the sensor; **Not
supported, yet.**"* (verified in
`omni.usd.schema.omni_sensors-0.0.0+69cbf6ad/usd_plugins/generatedSchema.usda`).
The `data/lidar_configs/*.json` files on disk and the
`app.sensors.nv.lidar.profileBaseFolder` search path are the **pre-5.0**
mechanism (Camera-prim based, explicitly deprecated); the vendor JSONs
still present on disk read as the authoring source NVIDIA used to bake the
official `/Isaac/Sensors/<vendor>/...usd` assets once, offline — not
something the running sensor re-parses. Ignore both for new work.

The real, unrestricted creation path:

```python
import omni.replicator.core as rep
prim = rep.functional.create.omni_lidar(
    position=(x, y, z), rotation=(roll, pitch, yaw),  # degrees, XYZ order
    **{
        "omni:sensor:Core:scanType": "SOLID_STATE",
        "omni:sensor:Core:nearRangeM": 0.1,
        "omni:sensor:Core:farRangeM": 40.0,
        "omni:sensor:Core:waveLengthNm": 905.0,
        "omni:sensor:Core:emitterState:s001:azimuthDeg": [...],     # len N
        "omni:sensor:Core:emitterState:s001:elevationDeg": [...],   # len N
        "omni:sensor:Core:emitterState:s001:fireTimeNs": [...],     # len N, uint
        "omni:sensor:Core:emitterState:s001:channelId": [...],      # len N, uint
        # ... see §5 for the full attribute reference
    },
)
```

Source, read directly (not inferred):
`omni.replicator.core-1.12.27+107.3.3/omni/replicator/core/scripts/
functional/create_batch.py::omni_lidar` applies schema
`"OmniSensorGenericLidarCoreAPI"` plus, for any kwarg matching
`omni:sensor:Core:emitterState:<instance>:*`, the matching multi-apply
instance of `"OmniSensorGenericLidarCoreEmitterStateAPI:<instance>"` — then
calls a generic `_create_prim_generic(prim_type_name="OmniLidar", ...,
**kwargs)`. **There is no whitelist check anywhere in this call path** —
`SUPPORTED_LIDAR_CONFIGS` (§4) is checked only inside the *other*,
higher-level convenience command (`IsaacSensorCreateRtxLidar`'s
`_add_reference()`), which is for referencing NVIDIA's pre-built vendor
USD assets by name — not something a custom sensor needs to go through at
all. **This retires the "whitelist bypass" as an open question — there is
no whitelist on this path to bypass.**

`LidarRtx.__init__` (`isaacsim.sensors.rtx`, our chosen Python wrapper,
§6) internally calls `omni.kit.commands.execute("IsaacSensorCreateRtxLidar",
..., config=config_file_name, **kwargs)`, i.e. it goes through the
*gated* command, not the raw Replicator function directly. Two viable
implementation shapes, in order of preference:

1. **Author the prim with `rep.functional.create.omni_lidar(**kwargs)`
   directly** (the ungated path above), then wrap the resulting prim path
   with `LidarRtx(prim_path=<already-existing path>, ...)` — `LidarRtx.
   __init__`'s `is_prim_path_valid(prim_path)` branch (see `lidar_rtx.py`
   line 110) skips the gated command entirely when the prim already
   exists, and only validates that it `HasAPI("OmniSensorGenericLidarCoreAPI")`
   — which it will, since we just applied that schema ourselves. This gets
   the ungated authoring *and* `LidarRtx`'s annotator/frame-data
   convenience for free.
2. Fallback: author the prim with plain `pxr` (`Usd.Stage.DefinePrim`
   + `Usd.Prim.ApplyAPI` + attribute `Set()` calls), the same low-level
   technique already used this session for the RayCaster mount frame in
   `lunarbot.usdc`. Equivalent, more verbose, only needed if `rep.
   functional.create.omni_lidar` turns out to have some issue in practice
   (execution-time risk, see §9).

## 4. `SUPPORTED_LIDAR_CONFIGS` — what it actually gates (for completeness)

`isaacsim/sensors/rtx/impl/commands.py::IsaacSensorCreateRtxSensor.
_add_reference()` loops `SUPPORTED_LIDAR_CONFIGS`
(`impl/supported_lidar_configs.py`, ~20 hardcoded official Nucleus USD
asset paths, e.g. `/Isaac/Sensors/HESAI/XT32_SD10/HESAI_XT32_SD10.usd`) and
only proceeds if the given `config` string matches that asset's filename
stem (with/without the vendor prefix, spaces-for-underscores tolerated).
This is purely a name→pre-built-asset lookup for NVIDIA's own reference
sensors and is irrelevant once §3's direct-authoring path is used — not a
gate to defeat, just a different, unrelated convenience for a different
use case (dropping a known commercial sensor into a scene by name).

## 5. Full attribute reference (from the generated USD schema, verified on disk)

Source: `~/Programs/isaac-sim/extscache/omni.usd.schema.omni_sensors-
0.0.0+69cbf6ad/usd_plugins/generatedSchema.usda`, classes
`OmniSensorGenericLidarCoreAPI` and
`OmniSensorGenericLidarCoreEmitterStateAPI` (multi-apply, default instance
name `s001`).

**Top-level sensor attributes** (`omni:sensor:Core:` prefix), with the
Mid-360 value to set (§6 has the citation for each):

| Attribute | Schema default | Set to (Mid-360) |
|---|---|---|
| `scanType` | `"ROTARY"` | `"SOLID_STATE"` |
| `nearRangeM` | 0.3 | **0.1** |
| `farRangeM` | 200 | **40.0** (see §9 on the 70m@80%-reflectivity figure) |
| `waveLengthNm` | 903 | **905.0** |
| `numberOfEmitters` | 128 | length of the emitter arrays (§7) |
| `reportRateBaseHz` | 36000 | **200000** (point rate) |
| `scanRateBaseHz` | 10 | **10** (frame rate) |
| `rangeAccuracyM` | 0.02 | **0.02** (≤2cm @10m) |
| `pulseTimeNs` | 6 | leave default unless datasheet states otherwise |
| `intensityProcessing` | `"NORMALIZATION"` | leave default |
| `maxReturns` | 2 | 1 (Mid-360 is single/first-return; confirm if dual-return firmware matters later) |
| `azimuthErrorStd` / `elevationErrorStd` | 0.005 / 0 | derive from the &lt;0.15° angular precision figure if per-axis noise modeling is wanted; optional polish, not required for a first pass |

**Per-emitter arrays** (`omni:sensor:Core:emitterState:s001:` prefix, all
must have equal length = `numberOfEmitters`): `azimuthDeg` (float),
`elevationDeg` (float), `fireTimeNs` (uint, delta from tick start),
`channelId` (uint) — required; `bank`, `rangeId`, `distanceCorrectionM`,
`focalDistM`, `focalSlope`, `horOffsetM`, `vertOffsetM`, `reportRateDiv`,
`roi` — optional, can be left empty (schema default `[]`).

**Read-only fact worth using**: array VALUES can be updated at runtime via
plain `attr.Set(new_values)` — only the array LENGTH is documented as
runtime-immutable ("Changing the number of elements at runtime is not
supported"). This is what makes §7's window-cycling approach for true
non-repetitive fidelity implementable, not just aspirational.

## 6. Livox Mid-360 official datasheet (verified 2026-09-14, primary source)

Source: https://www.livoxtech.com/mid-360/specs (official Livox spec page).

- FOV: 360° horizontal, **-7° to +52° vertical** (exact, not just the ~59°
  total figure).
- Detection range: **40 m @ 10% reflectivity, 70 m @ 80% reflectivity.**
- Blind zone / minimum range: **0.1 m.**
- Wavelength: **905 nm**, Class 1 eye-safe (IEC 60825-1:2014).
- Point rate: **200,000 points/s** (first return).
- Frame rate: 10 Hz (typical usage).
- Range precision: ≤2 cm @10 m, ≤3 cm @0.2 m. Angular precision: &lt;0.15°.
  False alarm rate: &lt;0.01%.
- Physical (useful for the mount, not the sensor model): 65×65×60 mm,
  265 g, IP67, 9-27 V DC, 6.5 W avg / 14 W peak, built-in IMU (ICM40609),
  100BASE-TX Ethernet, -20°C to 55°C operating range.

## 7. The Mid-360's real scan pattern — exact source, format, and replay mechanism

`Livox-SDK/livox_laser_simulation` (Livox's own open-source Gazebo plugin)
**officially supports the Mid-360**. Verified directly against the raw
repo files this session (not a secondary summary):

- **License: MIT** (Copyright (c) 2021 livox) — permissive, no copyleft
  concern for pulling the data file into this repo.
- `scan_mode/mid360.csv`: header `Time/s,Azimuth/deg,Zenith/deg`,
  **800,000 data rows** (not 24,000 — that number is a *different*,
  related parameter, see below). `Time` is an integer sample index
  1..800,000, +1 per row (not literal seconds) — at the datasheet's
  200,000 pts/s rate, 800,000 samples = exactly one 4.0 s pattern cycle.
  `Azimuth` spans 0.0004°–360.0°. **`Zenith` is angle-from-vertical
  (0°=straight up), not elevation** — convert via
  `elevation_deg = 90 - zenith_deg`: the data's zenith range
  37.836°–97.212° maps to elevation +52.164° to -7.212°, matching the
  official -7°/+52° FOV almost exactly (the small margin beyond nominal
  spec is expected/normal for real captured hardware data, not a bug in
  the conversion).
- **How the plugin actually replays it** (read directly from
  `src/livox_points_plugin.cpp`): the full 800,000-row table loads once
  into memory. Each simulation tick, it does **not** replay a static
  pattern — it takes a sliding window of `samples` consecutive rows
  starting at a running `currStartIndex`, then advances
  `currStartIndex += samples` for the next tick, wrapping via `%
  maxPointSize` (800,000). Consecutive frames therefore use genuinely
  different, forward-advancing slices of the full trajectory, only
  repeating after a full cycle. The Mid-360 xacro's own default is
  `samples=24000` (**this** is where the "24,000" figure from the first,
  less careful research pass actually came from — it is the per-tick
  window size, not the CSV's row count), `downsample=1`. One full
  non-repetitive cycle therefore spans `ceil(800000/24000) ≈ 34` ticks
  before repeating.
- **Implication, stated as a real engineering choice, not deferred**: a
  *single static* `emitterState` block (one fixed 24,000-point window)
  reproduces only one still frame of the pattern, not the real
  frame-to-frame-varying coverage. Given §5's confirmation that emitter
  array *values* (not lengths) can be updated at runtime, the faithful
  approach is: **pre-slice the 800,000-row table into the same
  sequential, wrapping 24,000-point windows the real plugin uses, and
  advance to the next window's `azimuthDeg`/`elevationDeg`/`fireTimeNs`
  values on the sensor prim once per RTX Lidar tick** (same modulo-wrap
  scheme, `currStartIndex += 24000, % 800000`). This is a plan decision,
  not an open question — do this, not the static single-window
  approximation, unless execution reveals a concrete reason not to
  (e.g. attribute-update overhead measured to be too costly at the
  target tick rate — an execution-time question, correctly left for §9).

## 8. Runtime data access

`isaacsim.sensors.rtx.LidarRtx` (`impl/lidar_rtx.py`, fully read — use only
the current, non-deprecated API):

```python
lidar = LidarRtx(prim_path="/World/.../lidar_mid360")  # prim already
                                                        # authored per §3
lidar.initialize()
lidar.attach_annotator("IsaacExtractRTXSensorPointCloudNoAccumulator")
# or "IsaacCreateRTXLidarScanBuffer" for a raw buffer instead of an
# already-accumulated point cloud; "IsaacComputeRTXLidarFlatScan" for a 2D
# flat-scan projection if a cheap /scan-only path is ever wanted.
...
frame = lidar.get_current_frame()  # dict keyed by attached annotator name
```

No `num_envs`/tensor batching — a plain per-instance Python object with its
own Replicator render product. For `num_envs > 1` each env needs its own
`LidarRtx` instance (real per-instance GPU render cost, unlike
`RayCaster`'s cheap batched Warp raycasting) — another reason this fits a
single/few-env IL target better than mass-parallel RL.

**A native ROS2 path also exists and was found, but is not the
recommended integration**: `isaacsim.ros2.bridge`'s
`OgnROS2RtxLidarHelper` OmniGraph node can publish an RTX lidar straight
to ROS2 without any Python polling — checked directly
(`isaacsim/ros2/bridge/impl/og_shortcuts/og_rtx_sensors.py`,
`ogn/python/nodes/OgnROS2RtxLidarHelper.py`), and it validates the same
`OmniLidar` + `OmniSensorGenericLidarCoreAPI` prim shape this plan
produces. Using it would mean running a second, OmniGraph-based ROS
publishing path alongside SRB's existing single unified `rclpy`-based
`RosInterface` (`srb/interfaces/interface/ros.py`), which already owns
topic naming, QoS, and lifecycle for every other sensor — architecturally
inconsistent. **Recommendation: pull data via `LidarRtx.get_current_frame()`
in Python and publish through the existing manual `PointCloud2`
construction pattern already in `ros.py`, not the OmniGraph node**, purely
for consistency with how every other SRB sensor is wired. Keep the
OmniGraph path in mind as a fallback only if the Python polling path proves
to have unacceptable overhead (execution-time question).

## 9. SRB/OpenRAL integration surface — what has to be built, not reused

- **No IsaacLab `SensorBase` wrapper exists for this** — `srb/core/sensor`
  cannot just re-export it the way it does `RayCaster`/`Imu`/`Camera`. A
  thin custom sensor class is needed in `srb/core/sensor/` (does not need
  to subclass IsaacLab's `SensorBase`; only needs a `.data` shape close
  enough to `isaaclab.sensors.ray_caster.RayCasterData` — confirmed fields
  `pos_w: (N,3)`, `quat_w: (N,4)` [w,x,y,z], `ray_hits_w: (N,B,3)` — that
  the rest of the code doesn't need to special-case unnecessarily).
- **`srb/interfaces/interface/ros.py` needs a new branch.** Its RayCaster
  point-cloud publishing (`elif isinstance(sensor, RayCaster):`, currently
  around line 802) won't match a custom wrapper class — add
  `elif isinstance(sensor, <NewLidarRtxWrapper>):` alongside it, reusing
  the same `PointCloud2` construction pattern already there.
- **Env wiring mirrors this session's `RayCasterCfg` pattern** in
  `srb/core/env/mobile/env.py` (`self._robot.frame_lidar`-gated
  construction in `__post_init__`, `self.scene.sensors.get("lidar_robot",
  None)` retrieval in `__init__`) — same shape, different sensor class
  underneath. Keep `frame_lidar` as the single source of truth for mount
  pose so both the RayCaster and RTX paths (if both are kept, e.g.
  RayCaster as a cheap/parallel-friendly fallback mode) read the same
  CAD-derived transform recorded in `docs/research_findings.md` F23.
- **A real, confirmed rendering-pipeline gap in `srb/__main__.py`.** RTX
  Lidar needs the RTX render pipeline running at all — Isaac Sim's own
  `enable_cameras`/rendering-experience path. SRB currently gates that
  purely on the task-id suffix: `kwargs["enable_cameras"] = video_enable
  or env_id.endswith("_visual")` (line 112; the same `endswith("_visual")`
  pattern is repeated at lines 1154/1157/1159 for a different subcommand).
  `panel_remount` (no `_visual` suffix) with `env.robot=lunar_bot` today
  loads the plain `srb.headless.kit` experience, **not**
  `srb.headless.rendering.kit` — confirmed by diffing the two `.kit` files
  directly: the rendering variant is the one that pulls in
  `omni.replicator.core` and sets `isaaclab.cameras_enabled = true` plus
  the RTX raytracing cache settings. Without it, an RTX Lidar prim would
  either fail to produce data or silently render nothing. **This must be
  fixed as part of this item, not discovered by a confused failed test
  later**: the `enable_cameras` condition needs an additional clause —
  something like `or (getattr(env_cfg._robot, "frame_lidar", None) and
  <robot's lidar backend is RTX, not RayCaster>)` — evaluated wherever the
  robot/task selection is already known at CLI-parse time. Exact
  implementation shape (a config flag on the sensor wrapper vs. a
  robot-level attribute) is a design choice for step-5 of §10, but the
  *fact* that today's gating logic is insufficient is settled now, not
  left for implementation to rediscover.
- **SRB's `.kit` experience files need `isaacsim.sensors.rtx` added** to
  the `[dependencies]` of `apps/srb.headless.rendering.kit` (and
  the non-headless `srb.rendering.kit`, `srb.rendering.xr.kit` variants for
  parity) — confirmed absent by grepping every `apps/*.kit` file for the
  extension name; none currently declare it. `isaacsim.ros2.bridge` is
  presumably already present for the existing camera/ROS path — no need to
  re-verify, only the RTX sensor extension itself is new.

## 10. Ordered execution plan

Each item independently verifiable before the next starts (per
`AGENT.md` rule 0.11). The mechanism uncertainty from the first research
pass is gone (§3-§5); what remains genuinely needs a running Isaac Sim to
confirm (marked ⚑, and only there).

1. Add `isaacsim.sensors.rtx` to `apps/srb.headless.rendering.kit` (+
   `srb.rendering.kit`/`srb.rendering.xr.kit` for parity).
2. Fix the `enable_cameras`/rendering-experience gating in
   `srb/__main__.py` (§9) so `lunar_bot`'s RTX lidar path gets rendering
   even for non-`_visual` task ids.
3. ⚑ Smoke-test `rep.functional.create.omni_lidar(**kwargs)` directly (no
   SRB env yet) with a handful of manually-specified emitter points and
   confirm `LidarRtx(prim_path=<that path>).attach_annotator(...)` returns
   non-empty point data against a trivial test scene. This isolates
   "does the ungated direct-authoring path (§3) actually work end-to-end
   in this install" from every downstream step.
4. Write the `mid360.csv` → windowed-emitter-arrays conversion script per
   §7 (download the CSV — MIT-licensed, safe to vendor a copy into
   `assets/` with attribution — slice into sequential 24,000-point windows
   with the zenith→elevation conversion, verify window count ≈34 and that
   concatenating all windows reconstructs the original azimuth/zenith
   ranges).
5. ⚑ Wire per-tick window advancement (start with the simplest viable
   mechanism — updating the `s001` instance's arrays from Python each
   step via `attr.Set()` — and only reach for OmniGraph/multi-instance
   cycling if that proves to have a real performance problem). Confirm
   visually/numerically that the point cloud pattern actually changes
   window-to-window rather than repeating.
6. Build the thin SRB-side sensor wrapper class + `MobileEnvCfg` wiring
   (§9), gated the same way `frame_lidar` already gates the RayCaster path.
7. Add the `ros.py` publishing branch (§9).
8. Live-verify through `srb agent rand --env panel_remount
   env.robot=lunar_bot --interface ros`: real RTX point cloud on the ROS
   topic, sees the pedestal/panel (the concrete capability RayCaster
   couldn't provide — the acceptance criterion for the whole item).
9. Decide whether to keep RayCaster as an alternate/cheap mode or retire it
   for `lunar_bot` once RTX Lidar is proven; do not remove it pre-emptively.

## 11. What's left that genuinely needs execution to discover (not before)

Everything else in this document is settled. Only these are real open
questions, deliberately left for implementation:

- Whether `rep.functional.create.omni_lidar`'s ungated path (§3) has any
  practical rough edges not visible from reading the source (step 3 of
  §10 is exactly the test that answers this).
- Per-tick Python `attr.Set()` overhead for a 24,000-element array update,
  at whatever tick rate the deployment actually runs — may or may not
  need a cheaper update strategy (batching, a native OmniGraph node,
  reducing the window size) than the naive per-step Python call.
- Whether the 40 m (10% reflectivity) or a reflectivity-dependent range
  model is worth implementing later versus the single conservative 40 m
  `farRangeM` figure used in §5 — a fidelity refinement, not a blocker.
- Final call on retiring vs. keeping the RayCaster path for `lunar_bot`
  (§10 step 9) — depends on how RTX Lidar performs in practice.
