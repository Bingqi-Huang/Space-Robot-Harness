# NVIDIA-official assets for the lunar-base rebuild (Isaac Sim 5.1) — survey

Method: full S3 key listing of `omniverse-content-production` (5.1 tree + bucket-root content), then
downloaded representative USDs and opened them with Isaac Sim's own `pxr` 0.24.5
(`omni.usd.libs`, no Kit/GPU) to count `PhysicsRigidBodyAPI` / `CollisionAPI` / `MassAPI` /
`ArticulationRootAPI` / joints and bounding boxes. Raw listings in this dir: `props.tsv` (2 507 keys),
`envs.tsv` (34 437), `nvidia.tsv` (226 290), `simready.tsv` (37 336), `isaaclab.tsv` (4 196);
`simready_asset_info.json` = NVIDIA's own per-asset metadata (1 029 SimReady props, extents, classes);
`simready_manipulables.md` = the 280 SimReady items with every dimension 5–62 cm.
Probe scripts: `usdprobe.sh` + `probe.py` / `probe2.py`.

## 0. Headline

- **Nothing space/lunar exists in NVIDIA content.** Grep across ~300 k keys for lunar/moon/mars/space/
  rover/antenna/satellite/solar/lander/habitat/dome returns only `Samples/Astronaut/Astronaut.usd`
  (28.6 MB, visual-only human figure, no physics). No lunar terrain, no rovers, no solar arrays, no
  antennas, no habitat modules. Those must come from NASA / other sources (other forks' scope).
- NVIDIA content is valuable for the **"base interior / logistics / maintenance hardware" layer**:
  physics-ready storage cases, totes, drums, jerricans, pails, bins (SimReady), an **articulated
  cabinet with drawers + doors**, physics tools (drill, clamps), assembly **plug/socket pairs**
  (AutoMate, 100 variants), Factory nuts/bolts/gears, and a large visual-only equipment/furniture set
  (workbenches, tool carts, cabinets, fire cabinets, worklights, compressors, heaters, ramps, a
  6×15×8 m power station).
- **License verdict:** props/SimReady/DigitalTwin/IsaacLab assets are Omniverse "Content": you may use,
  **modify, and create derivatives**, and distribute them **incorporated into your work** (scenes,
  videos, figures, a released benchmark scene) but **not as stand-alone assets**. Anything under
  `/Isaac/Environments/` is "Limited Use Content": **use only, no modification** — avoid basing the
  scene on those. Practical rule: don't commit raw NVIDIA USDs to a public repo; fetch by URL/script
  at setup time, commit only our composed scene + provenance list.

## 1. Where it lives / how to get it

| Source | Content | How to download | Size |
|---|---|---|---|
| S3 `…/Assets/Isaac/5.1/Isaac/Props/` | classic Isaac props (YCB, KLT bin, Sektion cabinet, Factory, dolly, pallets, mounts) | per-file HTTPS GET (works via host proxy) | ~4.5 GB total |
| S3 `…/Assets/Isaac/5.1/Isaac/IsaacLab/` | AutoMate plug/socket ×100, Factory peg/hole/nut/bolt/gear, Arena objects (power drill, kitchen w/ drawers), Mimic task props | per-file | ~7 GB (mostly checkpoints/datasets) |
| S3 `…/Assets/simready_content/common_assets/props/` | **SimReady**: 1 029 props, each with `PhysicsVariant = None / RigidBody` (collision = convexDecomposition, mass from physics-material density) | per-file; metadata `asset_info.json` | 84 GB incl. textures (only fetch what's used) |
| S3 `…/Assets/Isaac/5.1/NVIDIA/Assets/DigitalTwin/Assets/Warehouse/` | ~7 300 files, visual-only (no physics APIs found) warehouse equipment/furniture/safety/storage | per-file | 25 GB |
| S3 `…/Assets/Isaac/5.1/NVIDIA/Assets/ArchVis/Industrial/` | warehouse building shell, racks, crates, fencing, ramps (visual) | per-file | 2 GB |
| Official packs (docs 5.1 download page) | `isaac-sim-assets-materials_and_props-5.1.0.zip` 3.7 GB, `…-environments-5.1.0.zip` 14.5 GB, `…-robots_and_sensors-5.1.0.zip`, `…-complete-5.1.0.00{1,2,3}.zip` (part 1 = 53.7 GB) at `https://downloads.isaacsim.nvidia.com/` | aria2/curl, MD5s on the page | — |
| S3 bucket root `Samples/Astronaut/` | astronaut figure (visual) | per-file | 28.6 MB |

No separate "SimReady Warehouse pack zip" for 5.x was found on S3; the SimReady set above is the
canonical copy. Host has 3.0 TB free on `/mnt/SharedData`; proxy already configured.

## 2. Physics-readiness probe results (actually opened)

| Asset (path under `Assets/…`) | Size (m) | Rigid | Collision | Mass | Articulation / joints | Verdict |
|---|---|---|---|---|---|---|
| `Isaac/5.1/Isaac/Props/Sektion_Cabinet/sektion_cabinet_instanceable.usd` | 0.67×0.76×0.79 | 9 bodies | in instanced collision layer (`sektion_cabinet_collisions.usd`) | yes | **1 art. root, 9 joints: prismatic (2 drawers), revolute (2 doors), fixed**; `Physics` variant `Default / Isaac_Lab_Settings` | **Ready articulated** — drawer/door open/close tasks (same asset as Isaac Lab cabinet task) |
| `Isaac/5.1/Isaac/Props/Dolly/dolly_physics.usd` | ~0.5×0.5×0.3 (bbox polluted by ground) | 9 | convexHull/cube | 30 kg body | **art. root, 8 revolute (casters)** | Ready; pushable cart |
| `Isaac/5.1/Isaac/Props/KLT_Bin/small_KLT.usd` | 0.20×0.30×0.15 | 1 | cube | 0.56 kg | — | **Ready**, graspable tote |
| `Isaac/5.1/Isaac/Props/YCB/Axis_Aligned_Physics/006_mustard_bottle.usd` (+003/004/005) | 0.10×0.19×0.06 | 1 | convexDecomp | 0.60 kg | — | Ready (household, low lunar relevance) |
| `Isaac/5.1/Isaac/IsaacLab/Arena/assets/object_library/power_drill_physics/power_drill_physics.usd` | 0.18×0.19×0.06 | 1 | convexDecomp | 0.90 kg | — | **Ready tool** (drill as "service tool") |
| `Isaac/5.1/Isaac/IsaacLab/AutoMate/<id>/plug.usd`, `socket.usd` (100 ids) | plug ≈0.007×0.007×0.075, socket ≈0.072×0.072×0.022 | via `Physics` variant `PhysX` | via variant | via variant | — | Ready but **mm-scale** — too small for RM-75+EG2 at mission level; good as "connector" geometry if scaled |
| `Isaac/5.1/Isaac/IsaacLab/Factory/factory_bolt_m16.usd` (+nut_m16, gear_*, peg/hole 8 mm) | 0.02–0.04 | 1 | **SDF** | 0.05 kg | art. root + fixed joint | Ready, precision-assembly scale (too fine for 610 mm arm w/ CARTESIAN_TWIST) |
| `Isaac/5.1/Isaac/Props/Pallet/o3dyn_pallet.usd` | ~1.2×0.8×0.59 | 1 | convexDecomp | 60 kg | — | Ready (static-ish logistics furniture) |
| `simready_content/common_assets/props/case_e01/case_e01.usd` | 0.48×0.28×0.21 | 1 (RigidBody variant) | 6 convexDecomp | mass 0 → from material density (metal 2700 / plastic 800 kg/m³) | — | **Ready**; mass will be unrealistic for hollow shells → **override `MassAPI` per object** |
| `simready_content/.../cabinet_b01/cabinet_b01.usd` | 0.34×1.07×2.01 | 1 | 3 convexDecomp | density | **no joints** | Rigid only (doors don't open) |
| `simready_content/.../plasticjerrican_a02/…usd` | 0.22×0.24×0.29 | 1 | convexDecomp | density | — | Ready |
| `simready_content/.../steeldrum_a04/…usd` | 0.37×0.38×0.48 | 1 | convexDecomp+hull | density | — | Ready (too heavy to lift; pushable/obstacle) |
| `NVIDIA/Assets/DigitalTwin/.../Storage/Cases/Case_E/Case_E01_…PR_V_NVD_01.usd` | 0.48×0.28×0.21 | 0 | 0 | 0 | — | Visual-only twin of the SimReady case |
| `.../Equipment/Carts/ToolboxCart_A/ToolBoxCart_A01_01.usd` | 0.81×0.45×0.86 | 0 | 0 | 0 | none | Visual-only (drawers not articulated) |
| `.../Safety/Fire_Protection/FireCabinet_A/FireCabinet_A01_01.usd` | 1.22×0.40×1.46 | 0 | 0 | 0 | none | Visual-only |
| `.../Furnishing/Cabinets/SteelCompartmentWithFeet_A/…A01_PR_NVD_01.usd` | 0.32×0.50×1.85 | 0 | 0 | 0 | none | Visual-only |
| `.../Equipment/Power/PowerStation_B/PowerStation_B01_01.usd` | 5.97×14.87×8.07 | 0 | 0 | 0 | none | Visual-only big "power station" backdrop (needs added static collider) |
| `.../Facilities/Worklight/Worklight_C/Worklight_C01_01.usd` | 0.91×0.79×2.19 | 0 | 0 | 0 | none | Visual-only floodlight mast |
| `Props/NVIDIA/Carter/ChargingDock/charging_station_final/CHARGING_STATION_ASM_base.usd` | 0.28×0.52×0.48 | 0 | 0 | 0 | none | Visual robot charging dock (base "charging station" prop; add collider) |
| `Samples/Astronaut/Astronaut.usd` | ≈1.75 m figure (cm units) | 0 | 0 | 0 | none | Visual dressing only |

All SimReady/DigitalTwin USDs are Z-up, `metersPerUnit = 0.01` (cm) — scene composition must respect
units. SimReady uses `_base` / `_inst` instancing; DigitalTwin files are mostly self-contained.

## 3. Candidates by lunar-base role (what to actually use)

### 3a. Graspable by RM-75 (610 mm reach, 5 kg) + 2-finger gripper — physics-ready

| Role in mission | Candidate | Path | Size | Notes |
|---|---|---|---|---|
| Spare-part / ORU case (Mission B "deliver component") | SimReady `case_e01`, `case_d01`, `case_a01` | `simready_content/common_assets/props/case_e01/case_e01.usd` etc. | 0.48×0.28×0.21 / 0.41×0.32×0.34 / 0.55×0.36×0.23 | Handles present on mesh; override mass to 2–4 kg; `case_e01` is the most graspable |
| Small tote / sample bin | Isaac `small_KLT.usd`; SimReady `bin_a04..a06`, `container_c09..c16` (0.41×0.30×0.13–0.33), `tote_d0x` | see §1 / `simready_manipulables.md` | 0.20–0.41 m | KLT has explicit mass 0.56 kg — best out-of-box |
| Fluid/consumable canister | SimReady `plasticjerrican_a01..a04`, `utilityjug_a01..a03`, `metalfstylecan_a01`, `screwtoppail_a01` | `…/plasticjerrican_a02/plasticjerrican_a02.usd` | 0.19–0.28 m wide | Good "coolant / regolith sample canister" stand-ins after retexture |
| Hand tool | `power_drill_physics.usd`; YCB `051_large_clamp`, `052_extra_large_clamp`, `037_scissors` (Axis_Aligned has visual; only 003–006 have Physics copies) | `IsaacLab/Arena/assets/object_library/power_drill_physics/` | 0.18 m | Drill is physics-ready; clamps need colliders added |
| Movable obstruction (held-out "blocked access") | SimReady `steeldrum_a04` (0.37×0.38×0.48), `fiberdrum_a06/a07`, `squarepail_a02`, `case_c01` | `simready_content/…` | 0.3–0.6 m | Plausible "debris/stowed container blocking a panel"; set mass ≤5 kg if it must be liftable, heavier if only pushable |

### 3b. Articulated (makes inspection/maintenance physically real)

| Candidate | Joints | Use |
|---|---|---|
| `Isaac/Props/Sektion_Cabinet/sektion_cabinet_instanceable.usd` | 2 prismatic drawers, 2 revolute doors | **"Equipment locker / spares cabinet"**: open drawer → retrieve part (Mission B), door-closed-vs-open as observable state; restyle materials to metallic/white aerospace look. Only physics-ready articulated storage found in NVIDIA content. |
| `Isaac/Props/Dolly/dolly_physics.usd` | 8 revolute casters | Pushable logistics cart (Mission B transport alternative / capability substitution) |
| IsaacLab Arena `kitchen_scene_teleop_v3` (drawers) | drawers in kitchen set | Not lunar-plausible; skip except as articulation reference |
| AutoMate plug/socket (100 pairs) | none (rigid pair, tight tolerance) | Connector geometry idea only; mm-scale |

No NVIDIA asset provides **valves, breaker panels, hatches, latches, or cable connectors at human scale
with joints** — these must be authored (simple revolute/prismatic joints on custom meshes) or sourced
elsewhere.

### 3c. Static base infrastructure / dressing (visual; add colliders)

| Role | Candidate (DigitalTwin Warehouse unless noted) | Size |
|---|---|---|
| Workbench / service table | `Furnishing/Workbenches/MetalWorktable_A/*` (24 variants, ~0.8 MB each), `LabWorkbench_A`, `PedestalWorkbench_A` | ~1.2–1.8 m |
| Tool cart / instrument cart | `Equipment/Carts/ToolboxCart_A/*`, `InstrumentCart_A`, `WeldedSteelCart_A` | ~0.8 m |
| Storage shelving / racks | `Shelving/Industrial/*`, `Shelving/Racks/*`; ArchVis `Shelves/Rack*Empty_A*`; SimReady `shelf` class (250) | 1–3 m |
| Lockers / cabinets | `Furnishing/Cabinets/ClosedIndSteel_A/*`, `Ventilated_A`, `SteelCompartmentWithFeet_A` | 1.7–2 m |
| Fire / safety equipment | `Safety/Fire_Protection/*` (extinguishers, fire cabinets), `Safety/Barriers/*` (722 files), `Safety/Cones/*` | — |
| Lighting masts | `Facilities/Worklight/Worklight_A/B/C` | ~2.2 m |
| Power / utility machinery | `Equipment/Power/PowerStation_B` (6×15×8 m), `Equipment/Compressors/AirVertical_A`, `AirHorizontal_A`, `Equipment/Heaters/*` | large |
| Tanks | `Storage/IBC_Tanks/*` (SimReady `ibctank_*` physics), `stainlesssteelibctank_a01` (1.27×1.11×1.30) | ~1.2 m — plausible "propellant/ISRU tank" after retexture |
| Ramps / walkways | `Equipment/Ramps/AluminiumWalkRamp_A`, `DockBoard_*`, `WorkRamp_A`; SimReady `inclined plane` (22, physics) | — |
| Fencing / railing | ArchVis `Railing/MetalFencing_A1..A3`, SimReady `metalfencing_a*` (physics) | 1.07 m tall |
| Pallets | SimReady `aluminumpallet_a01/a02` (physics), Isaac `Pallet/pallet.usd` | 1.2×1.0×0.14 |
| Robot charging dock | `Isaac/Props/NVIDIA/Carter/ChargingDock/…/CHARGING_STATION_ASM_base.usd` | 0.28×0.52×0.48 |
| Crew figure | `Samples/Astronaut/Astronaut.usd` | 1.75 m |

Warehouse building shells (`ArchVis/Industrial/Buildings/Warehouse01.usd` 133 MB; `Modular_Warehouse`,
`Simple_Warehouse` under `/Isaac/Environments/`) are terrestrial architecture — wrong look for a lunar
base, and the `/Isaac/Environments/` ones can't be modified under the license supplement.

### 3d. Environment-level

No lunar terrain, sky, or sun-lighting sample. Only `Environments/Terrains/{flat_plane, rough_plane
(171 MB), slope, stairs}.usd` (Limited Use) and dome lights (Earth skies). Lunar terrain must come from
SRB/simforge, OmniLRS or NASA DEMs.

## 4. License detail (quoted from the files actually shipped)

- `Isaac/Environments/environment-supplement-LICENSE.txt` (v. 2021-11-18): assets under
  `/Isaac/Environments` are "Limited Use Content" — "license to install and use copies … for your use
  only, **without modifications**"; the Agreement's normal Content grant "does not apply".
- NVIDIA Omniverse License Agreement §2.1 (local copy `isaac-sim/LICENSE.txt`, points to
  docs.omniverse.nvidia.com/…/NVIDIA_Omniverse_License_Agreement.html): Content may be installed and
  used; "**Modify and create derivative works of … the Content**"; "**Distribute Content (unmodified or
  as modified by you) as incorporated into your products or services** for the purpose of enhancing your
  work … but **not deploy or distribute the Content on a stand-alone basis**"; "Distribute user generated
  content that you develop using Omniverse, such as video, audio, stills, models, 3D assets and screen
  captures". §6.4 forbids distributing any portion of Omniverse in publicly accessible repositories
  except as expressly allowed.
- §2.3: individual licenses may be used commercially; academic/research use is clearly within scope.

**Verdict for this project:** using Props / IsaacLab / SimReady / DigitalTwin / ArchVis assets in the
lunar-base scene, retexturing/rescaling them, adding physics/joints, and publishing videos/figures and a
composed benchmark scene is permitted. Do not vendor the raw asset files into the public repo as a
standalone asset library (fetch script + provenance manifest instead). Avoid `/Isaac/Environments/*`
as a base because modification is not allowed.

## 5. Practical caveats for integration

1. SimReady mass comes from physics-material density over convex-decomposed volume → hollow cases/drums
   come out far too heavy/light; set `MassAPI.mass` explicitly for every manipulable (≤ 5 kg for RM-75).
2. Units are cm (`metersPerUnit=0.01`), Z-up; SRB spawners must scale 0.01 or reference with correct
   stage metadata.
3. DigitalTwin/ArchVis visual assets have **no colliders** — add `CollisionAPI` (convexHull/decomp or
   simple boxes) for anything the robot or lidar (RayCaster needs a mesh) must interact with.
4. Several DigitalTwin files are 10–40 MB (high-poly carts/desks); prefer the ≤5 MB variants for a
   scene that must run RayCaster lidar + cameras on one GPU.
5. Sektion cabinet is the only physics-articulated storage; other human-scale articulated
   infrastructure (valves, breakers, hatches, latches, connectors) must be authored.
