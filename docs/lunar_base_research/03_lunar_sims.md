# 03 — Reusable lunar simulators, terrain and scene pipelines (for rebuilding Mission A/B)

Scope: what existing projects/assets/pipelines we can reuse to rebuild the Mission A/B lunar
base inside SRB (Isaac Sim 5.1 / IsaacLab 2.2.1 pinned). Research only; nothing installed.
Surveyed 2026-09-15.

---

## 1. OmniLRS (github.com/OmniLRS/OmniLRS)

| Item | Finding |
|---|---|
| License | **BSD-3-Clause** (code). Assets: Git LFS inside the repo (same license unless noted); lunar south-pole DEMs pulled separately from AWS S3 (NASA LRO/LOLA-derived, public domain). |
| Isaac Sim | v2.5.0 (2025-11-13) "Migration to Isaac Sim 5.0"; v3.0.0 (2026-06-29) pixi env pins `isaacsim==5.0.0`. Last commit 2026-09-08 — actively maintained. Not on 5.1, not IsaacLab-based (own Omniverse app loop, `run.py` + Hydra cfg). |
| Environments (`cfg/environment/`) | `lunalab` (Univ. Luxembourg analog lab digital twin, incl. deformable), `lunaryard_{20,40,80}m` (procedural outdoor yard, 0.02 m DEM resolution, craters from spline profiles + power-law distributions, optional rocks via Thomas-cluster sampling), `lunaryard_40m_workshop(_full)` (yard + static assets: lunalab rock, **Vikram lander**, huge background landscape mesh), `largescale` / `largescale_200km` (geometry clipmaps over real LOLA south-pole DEMs, km scale, Warp mesh updates). |
| Lighting | Stellar-engine ephemeris (SPICE kernels `de421.bsp`, `moon_pa_de421`, …) → Sun/Earth positioned from lat/lon + UTC date; sun intensity/angle/temperature configurable. Directly matches research_content §4.8 "illumination from SPICE". |
| Shipped assets | Textures: `LunarRegolith8k` (8k diffuse/normal/rough/AO), basalt, gravel, BlackIron/BlackPaint. USD: rock collections (`apollo_rocks`, `lunar_rocks`, `small_rocks`, `lunalab_rocks`), landers (`Vikram`, `ispace_ultra`, `IM2_Athena`), robots (Husky, EX1, Pragyaan), `landscape_cropped` background (~1.1 GB). **No habitats, no infrastructure modules, no manipulable service components** — it is a rover/terrain simulator. |
| Extras in v3.0.0 | Yamcs mission-control TM/TC, multi-physics telemetry framework (power, radio, thermal, OBC), monitoring/lander cameras, **fault injection**. Conceptually relevant to our FDIR/space-context story but tied to OmniLRS's own app loop. |
| Static asset placement on terrain | `src/environments/static_assets_manager.py`: `position[2] = get_height_func((x, y)) + position[2]` — every static asset is **snapped to the DEM height** at its XY, with an explicit offset. `large_scale_lunar.get_height_and_normal()` also returns the surface normal for orienting assets. This is exactly the discipline the rejected scene lacked. |

**Port effort into SRB `GroundManipulationEnv`:**
- Cheap/safe: reuse **assets** (8k regolith textures, rock USDs, lander USDs) and the **DEM + crater generator** (`src/terrain_management/terrain_generation.py`, pure numpy/cv2) offline: generate a heightmap `.npy`, mesh it once to USD, register as an SRB `Terrain` subclass (see §2 mechanism). Height lookup is then a bilinear sample of the same `.npy` → deterministic snapping of every static asset.
- Medium: SPICE sun positioning — copy the stellar-engine math (SpiceyPy) into a small SRB event term that sets `scene.sunlight` orientation/intensity from mission epoch.
- Not worth it: running OmniLRS's app/ROS stack alongside SRB, clipmap large-scale terrain (km scale is irrelevant for a ~40–80 m base), Yamcs.
- Version risk: assets are plain USD/textures → 5.1-compatible; OmniLRS code targets 5.0 APIs (ArticulationControl) — don't import its runtime, only its generators/assets.

## 2. SRB capabilities not used by the rejected scene

### 2.1 Asset library (`space_robotics_bench/assets/srb_assets/`, CC0 except listed attributions)
- **Scenery (`srb/assets/scenery/`)**: `MoonSurface` / `MarsSurface` (simforge procedural), `GroundPlane`, **`Lunalab`** (`lunalab.usdc`, 4.8 MB — Univ. Luxembourg lab digital twin, custom USD + procedural terrain inset + boulder Poisson-disk scatter + particle regolith), **`Oberpfaffenhofen`** (`oberpfaffenhofen_test_site.usdc`, 20 MB, DLR Moon-Mars test site, CC BY-SA 4.0 — real scanned terrain).
- **Landers (static set dressing, `robot/lander/`)**: `apollo.usdz` (7.8 MB), `peregrine.usdz` (12 MB), `resilience.usdz` (31 MB), `vikram.usdz` (13 MB).
- **Rovers (`robot/rover/`)**: `construction_rover`, `leo_rover`, `mars_rover`, `osr`, `perseverance`, `pragyan` — usable as parked/broken secondary vehicles.
- **Manipulators**: Canadarm3 large, VISPA (Airbus), Franka, Kinova variants, SO-100.
- **Objects**: `beneficiation_unit.usdz` (33 MB — ISRU processing unit, convex-decomposed rigid), `cargo_bay.usdz` (payload), `solar_panel.usdz`, `industrial_pedestal_{25,50,100}cm`, `sample_tube` (Mars 2020), bolt/nut M8 (+tight variants), peg-in-hole profiles, screwdriver hex M3/M5, 6 scoop variants, 22 **Apollo samples** (NASA CC0 photoscans), 7 **Poly Haven moon rocks** (CC0), 4 Lunalab boulders.
- **Skydomes**: `stars`, `milky_way` (NASA SVS), `low_lunar_orbit`, `spaceport_moon_lab` (Poly Haven HDRI), EXR high/low res.
- Upstream SRB `main` is v0.0.6 (2025-10-28) and is already merged into our fork — no newer scenery exists upstream.

### 2.2 simforge_foundry procedural generators (installed in Isaac Sim's Python)
Geometry: `MoonSurface`, `MarsSurface` (terrain); `Rock`, `Asteroid`; `SolarPanel` (procedural panel geometry, distinct from the static usdz); `Cubesat`; `Scoop`; `BagRandom` (deformable regolith bag); `PegInHole` (`Module`, `Hole`, `Peg`). Materials: moon/mars surface & rock, asteroid, brushed chrome, scratched/smooth metal, smooth gold (MLI-like), scratched plastic, solar cell/solar panel, woven fabric, random. **No structures/habitats/buildings** in simforge.

### 2.3 Scenery override mechanism (confirmed in source)
- `env_cfg.scenery: Scenery | MobileRobot | AssetVariant | None`, default `AssetVariant.PROCEDURAL`. Registry: any subclass of `Terrain` or `Subterrane` (`srb/core/asset/scenery/`) auto-registers by class name; selection honours `DOMAINS` (e.g. `Domain.MOON`).
- A task can set `scenery` to a concrete instance (custom USD) or `None` (no terrain) — `_add_scenery` in `srb/core/env/common/base/env_cfg.py` wraps it as a static `AssetBaseCfg` (`disable_rigid_body=True`).
- `Asset.setup_extras(env_cfg)` hook lets a scenery add sub-assets, scatter events, override `env_spacing`, sunlight, skydome, viewer — **`Lunalab` is the working template for a custom "lunar base" scenery class** (USD shell + terrain inset + boulder scatter + lighting overrides).
- Procedural `MoonSurface` receives `scale=(spacing, spacing, 0.1*spacing)`, `density`, `flat_area_size = 0.8*_dyn_res**1.2`.

### 2.4 Why the rejected pedestal floated (inferred from the node graph — not measured)
Tracing `flat_area_size` (input socket 3) through `simforge_foundry/geometry/terrain/moon_surface/nodes.py`: it feeds (a) a `LESS_THAN` compare → `DeleteGeometry` (crater/rock instances removed inside the area) and (b) a `ShaderNodeTexGradient` → `FloatCurve` → `CombineXYZ.z` → `SetPosition` — i.e. a **radial height falloff curve**, not a hard z=0 disk. Height is only fully suppressed near the centre and blends back toward full relief with distance, so objects at 72–79 % of the nominal half-size (3.5–3.8 m of ~4.85 m) can sit well off z=0. Combined with pedestals authored as static `AssetBaseCfg` at literal `z=0` and no height lookup, a floating/sunken pedestal is expected. F18's "genuinely flat pad" description was an over-simplification. (Terrain `z` scale also grows with `env_spacing`: `0.1*spacing` = 16 m vertical scale at spacing 160.)

## 3. Other projects

| Project | Engine / version | License | Assets | USD-exportable? | Reuse verdict |
|---|---|---|---|---|---|
| **NASA DUST** (Digital Lunar Exploration Sites Unreal Simulation Tool, JSC NExSyS) | Unreal Engine 5 | Presentations call it "NASA developed open-source", but **no public download found** (NTRS papers/slides only). | DLES south-pole datasets (LOLA ~5 m/px), real-time south-pole lighting, waypoint tools; companion **LUTE** exports terrain patches as Wavefront OBJ. | Terrain → OBJ via LUTE only (if obtainable). | Not actionable now; the underlying LOLA DEMs are public (also used by OmniLRS large-scale). |
| **space-ros/demos** + **space-ros/simulation** | Gazebo Harmonic, ROS 2 Jazzy | demos Apache-2.0; `simulation` repo **no license file** | `lunar_terrain` (DEM worlds), `moon_mons_mouton` (Mons Mouton DAE mesh, LFS), Curiosity, Canadarm2, lunar_pole_exploration_rover | DAE/OBJ meshes → Isaac asset converter | Mons Mouton mesh is a nice real-site terrain, but license unclear → don't ship in paper assets without clarifying. |
| **AndrejOrsula/space_robotics_gz_envs** | Gazebo, Blender-procedural SDF export | Apache-2.0 / MIT | Same srb_assets procedural moon/mars worlds (+ "array" worlds) | Source pipelines already in SRB/simforge | Nothing beyond what SRB already has. |
| **LunarSim** (PUTvision) | Unity, ROS 2 Humble | **No license** in repo; last push 2023-12 | Unity lunar terrain, rover | Unity → FBX export possible but license blocks reuse | Skip. |
| **OmniLRS** | Isaac Sim 5.0 | BSD-3 | see §1 | Native USD | **Best external source** for terrain generation, regolith textures, rocks, landers, SPICE lighting. |
| Lunar construction framework (arXiv 2505.22091) | Not stated in abstract; ROS 2 + deformable terrain, excavator/dump-truck | No code/asset link found | construction machines | Unknown | Skip. |
| Isaac Sim / IsaacLab official | 5.x | NVIDIA Omniverse license | No lunar/space scenes found in official sample content (warehouses, hospitals, offices, SimReady props) | Native USD | Industrial props (crates, carts, racks, containers, tool cases) are the only source of *manipulable diverse infrastructure* — covered by another fork's survey. |

No 2025–2026 lunar-base benchmark with an Isaac Sim scene containing habitats/infrastructure was found; published lunar sims focus on terrain + rovers. **The base structures (habitat modules, power/comms infrastructure, service racks) will have to come from generic asset sources (NASA 3D Resources, SimReady/industrial props, CC0/CC-BY model sites) and be composed by us.**

## 4. Placing static infrastructure on non-flat terrain — patterns seen

1. **Heightmap lookup + offset (OmniLRS)**: terrain is a known DEM array; each static asset's `z = DEM(x, y) + offset`, optionally oriented to the surface normal. Deterministic, no physics query, trivially reproducible per seed.
2. **Flattened pads**: OmniLRS `generateRandomTerrain(is_yard=True)` zeroes the low-frequency noise border ring; lunalab zeroes borders to meet catwalks. Real lunar-base concept art and NASA base-camp studies also assume graded pads for habitats/landers — so a flattened pad under each structure is both physically plausible and simulation-friendly.
3. **Physics settle for dynamic props (SRB Lunalab)**: boulders scattered with `reset_xforms_uniform_poisson_disk_2d` and a small negative z range (partially embedded) — fine for rocks, wrong for structures.
4. **Scanned site mesh (Oberpfaffenhofen in SRB)**: terrain already final; objects must still be height-snapped (raycast or pre-baked lookup).

**Recommended for us:** own the terrain as a DEM we generate (OmniLRS-style numpy generator or SRB-procedural baked once), carve explicit **graded pads** (hard-flat, z=0 ± 0) under every structure/work site with a smooth berm blend outside, and snap anything off-pad via bilinear DEM lookup at config time — never literal `z=0` on procedural relief. Validate with a per-asset contact/gap check (bounding-box bottom vs. DEM height) plus multi-angle renders.

---

## Sources
- OmniLRS repo, CHANGELOG, cfg, source (cloned 2026-09-15, HEAD `5429512`, 2026-09-08): https://github.com/OmniLRS/OmniLRS ; Installation wiki: https://github.com/OmniLRS/OmniLRS/wiki/Installation ; paper: https://arxiv.org/pdf/2309.08997
- NASA DUST: https://ntrs.nasa.gov/citations/20220014707 , https://ntrs.nasa.gov/api/citations/20230001371/downloads/DUST_Presentation.pdf , https://ieeexplore.ieee.org/document/10115607/
- space-ros demos/simulation: https://github.com/space-ros/demos , https://github.com/space-ros/simulation
- space_robotics_gz_envs: https://github.com/AndrejOrsula/space_robotics_gz_envs
- LunarSim: https://github.com/PUTvision/LunarSim , https://doi.org/10.3390/app132212401
- Lunar construction framework: https://arxiv.org/abs/2505.22091
- SRB source + attributions: local `space_robotics_bench/` (`srb/assets/`, `srb/core/asset/scenery/`, `srb/core/env/common/base/env_cfg.py`, `docs/src/misc/attributions.md`); simforge_foundry installed package.
