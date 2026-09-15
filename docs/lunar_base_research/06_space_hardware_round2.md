# 06 — Round-2 search: open-licensed realistic lunar/space surface hardware

Research-only, 2026-09-15. Extends `02_internet_assets.md` (don't re-read that for NASA 3D
Resources / Poly Haven / Astromaterials3D / license-blocker basics). Raw data and scripts in
`r2/`; contact sheets (thumbnails actually viewed) are `06_sheet_*.jpg` next to this file.

## 0. What was searched (and how)

| Source | Method | Volume | Yield |
|---|---|---|---|
| Sketchfab (live) | API search, `downloadable=true`, licenses `cc0`/`by`/`by-sa`, sorted by likes, 122 terms (lunar/lander/habitat/VSAT/fission/antenna/CLPS names/VIPER/CADRE/LTV/ISRU/radiator/electrical cabinet/battery/charging/docking/truss/tank/light tower/…), up to 5 pages each | ~6,000 unique models (`r2/skf_r2*.json`) | Most useful source this round |
| Objaverse 1.0 | all 160 metadata shards (551 MB) grepped on name+tags, license ∈ {by, by-sa, cc0} | 2,677 hits → 1,190 space-relevant (`r2/objaverse_space.json`) | Same Sketchfab items (≤2023 snapshot) — **but gives login-free GLB mirrors** (§3) |
| Gazebo Fuel | model + world search API | ~20 queries | Gazebo Garden **Moon Base dome** (CC-BY 4.0) |
| Printables | GraphQL `searchPrints2`, 37 terms + per-model license/file query | ~1,100 prints (`r2/printables.json`) | Untextured print meshes; several CC0/CC-BY landers |
| BlenderKit | search API, 25 terms | 1,014 assets (`r2/blenderkit.json`) | 68 CC0, 315 free Royalty-Free |
| Smithsonian 3D | 3d-api file search | 14 terms | Only Apollo 11 CM, hatch, Shuttle (already known) |
| GitHub | repo search (rate-limited) + clones | lunar habitat/base/lander/Isaac/gazebo | LunCoSim = procedural USDA primitives, no art; nothing else |
| NASA Eyes glTF | direct asset paths | — | HTTP 403, no license → not a source |
| ESA Argonaut CAD | esa.int page | — | HTTP 403 to automated fetch; license still unverified (manual check) |
| Poly Pizza | search pages | — | JS-rendered + low-poly style → fails realism bar, skipped |
| Blender Studio open movies | — | — | Not pursued: 2012-era sci-fi props, no lunar hardware |

## 1. Best usable model per category

License legend: **PD** NASA public domain · **CC0** · **BY** CC-BY 4.0 (attribution) · **BY-SA** (derivatives must stay BY-SA) · **RF** BlenderKit Royalty-Free (use in project OK, no standalone redistribution) · ✗ = not open.
"GLB mirror" = downloadable from `huggingface.co/datasets/allenai/objaverse/resolve/main/<path>` without a Sketchfab login (Sketchfab itself needs an account/API token to download).

### Habitats / airlocks
| Pick | Source / license | Geometry | Verdict |
|---|---|---|---|
| **"Mars One" Mission – Base** (admone) `83ced347…` | Sketchfab, **BY**; GLB mirror `glbs/000-121/…` (20.6 MB) | 232k faces, **30 separate objects**, 30 PBR texture sets; arbitrary units (~986 wide) → rescale | **Best free habitat set found.** White inflatable modules on lander bases + airlock/stairs; reads as a credible NASA/ESA-style surface outpost. Use as habitat hero (terrain in model to strip). |
| **Gazebo Garden "Moon base dome"** (OpenRobotics) | Gazebo Fuel, **BY 4.0** (256 MB) | 36 separate DAE parts: `DomeOuter`, `OuterWall`, `OuterWallGate`, `DomeEntryWay`, **`Door`**, `BaseRamp`, `OutsideRamp`, `StrutBase`, `Tube`, interior garden | Geodesic greenhouse dome + gated airlock entry (`06_gazebo_moonbase_dome.png`). Door is its own mesh → articulable. More "concept art" than Artemis, but clean PBR. |
| NASA Habitat Demonstration Unit | NASA PD (round 1) | 2 GLBs | Still the most NASA-authentic module. |
| **International Docking System (IDSS)** (arcturusvfx) `678890a8…` | Sketchfab **BY**, GLB mirror `glbs/000-142/…`; also BlenderKit **CC0** "IDSS docking adapter" | 29k faces, **15 parts incl. `Hatch`, petals, latches**, 1.52×0.79 m real scale | Real hatch/docking interface → airlock hatch or mating port on habitats. |
| Complete Mars Base Station (arthuralvesdejesus) `28197d98…` | Sketchfab **BY** | 18.2M faces, 100 materials | Parts donor only (too heavy); includes modules, solar arrays, domes. |
| Root Module – Biomass Production System (kuroderuta) `0bd845b7…` | Sketchfab **BY** | 93k faces, ISS-style rack unit | Good "service rack unit" with visible fault cues (lights, drawers). |

Confirmed absent (any open license): Artemis Foundation Surface Habitat, Sierra Space LIFE, Bigelow B330 surface variant, ESA Moon Village modules. Sketchfab/Meshy "Artemis habitat" results are AI-generated or cartoon.

### Vertical solar arrays / power towers / fission power / radiators
| Pick | Source / license | Notes |
|---|---|---|
| **ISS Roll-Out Solar Arrays (iROSA) 1:100** | Printables id 958363, **CC0**, 1.2 MB STL | Real iROSA blanket+boom geometry, untextured → scale up, add solar-cell material; closest open analogue of a VSAT blanket. |
| HW: Detalisation – Solar Module (M8ZA) `b2b6dbc3…` | Sketchfab **BY**, GLB mirror `glbs/000-041/…` | Mast-mounted solar/power module (6 parts); good lattice-mast component. |
| TRUSS_ASSET `f3085c33…` (GLB mirror `glbs/000-064/…`), Modular Truss `adf2c63d…` | Sketchfab **BY** | Square/round truss segments to build a VSAT-style mast. |
| Dynetics HLS lander (Printables 180064) | **BY**, 16 STL parts | Has two tall **vertical solar panel masts** — shape reference/donor. |
| Sci-Fi Solar Panel (edwincgstudio) `0f444052…` | Sketchfab **BY** | Mounted twin-panel unit, plausible near-future look. |
| BlenderKit "Sci-Fi Solar Power Installation" (24 m) / "Sci-Fi Solar Panels Module" | **RF** free | Not visually verified (BlenderKit thumbnails not fetched); candidate if RF is acceptable. |

Confirmed absent: any VSAT (Astrobotic/Honeybee/Lockheed/Blue Origin/Leidos) model, **fission surface power / Kilopower** (only sci-fi reactors and a CGTrader listing = ✗ ML clause), **thermal radiators** (only household radiators).

### Communications
| Pick | Source / license | Notes |
|---|---|---|
| **Industrial Antenna** (RickPG001) `001970c2…` | Sketchfab **BY** | 122k faces, realistic large dish on pedestal, PBR — best ground-station dish. |
| **Satellite Comms** (duanesmind) `4be56951…` | Sketchfab **BY**, GLB mirror `glbs/000-083/…` | 8.7k faces, **3 parts Base/Arm/Dish** → pan/tilt joints; dish on elevated platform. |
| NASA Tall Dish | NASA PD (round 1) | 3 separable parts. |
| OpenRobotics "antenna" (SubT tripod relay) | Gazebo Fuel **BY 4.0** | Small tripod relay/radio terminal — good portable comm node / relay terminal. |
| Satellite Dish (Garecra) `2da4f725…` | Sketchfab **BY** | 1.16M faces, segmented hex dish — sci-fi-leaning. |

### Landers (CLPS / HLS / historic)
| Target | Best open option | License | Verdict |
|---|---|---|---|
| Nova-C | OmniLRS `IM2_Athena` USD (round 1) | BSD-3 | Use. (Printables NOVA-C 1:32 is "Standard Digital File" ✗; Sketchfab Nova-C IM-1 is a paid store item ✗) |
| Vikram | SRB `vikram.usdz`; **Printables ISRO Vikram Lander** (1822686, detailed) | BY-SA | Use SRB; Printables mesh is very detailed if a second variant is wanted. |
| Peregrine / Resilience | SRB usdz (round 1) | — | Use. |
| SLIM | Printables 530596, 33 STL parts | **BY-SA** | Detailed, untextured. |
| Beresheet | Printables 224901 | **BY** | Simple. |
| Dynetics HLS | Printables 180064 | **BY** | Good silhouette, vertical arrays. |
| Starship HLS (background) | SpaceX Starship S25 & Booster 9 (clarence365) `f76be07d…`, 885k faces | **BY** | Hero backdrop only (50 m). |
| Apollo LM (detailed) | CMFDesign `d5eea68f…` (451k faces, GLB mirror `glbs/000-043/…`); tushevs `464e8b88…` (1M faces, textured, mirror `glbs/000-010/…`) | **BY** | Far better than NASA's low-poly LM. |
| Blue Ghost, Griffin, Argonaut, Blue Moon MK1 | — | — | **Absent open**: Blue Ghost only CC-BY-NC-ND (Printables 1214417); Nova-C/Griffin/Blue Moon on CGTrader/Sketchfab store ✗; Argonaut ESA CAD license unverified (403). |

### Rovers (VIPER / CADRE / LTV / crew / utility)
| Target | Best open option | License | Verdict |
|---|---|---|---|
| Crew pressurized rover | **[MMSEV] Space Exploration Vehicle** (MarcoRomero) `d2f3b528…`, 413k faces, 4K PBR, real scale 3.1×4.0×4.5 m, GLB mirror `glbs/000-052/…` | **BY** | Better textured than NASA's SEV (PD). |
| Unpressurized rover / LTV stand-in | **Mondfahrzeug (Lunar Rover)** — Deutsches Museum laser-scan/photogrammetry LRV `acb3f864…`, 464k faces | **BY-SA** | Museum-grade Apollo LRV. (Printables NASA LTV = Standard Digital File ✗; Printables NASA Lunar Electric Rover 1766804 = **CC0**, 188 MB, detailed but untextured) |
| Utility/science rover | **ESA ExoMars Rover** (marian42) `4148a592…`, 107k faces, **77 named parts (axles, steering, wheels, bogies)**, 2.3 m, GLB mirror `glbs/000-133/…` | **BY and CC0** (author dual-licenses in description) | Best articulated rover; plausible as a parked/broken science rover. |
| Yutu | tashtego `d9564c9a…` | BY | Low-poly but accurate. |
| VIPER | Printables 1826557 1:100 | CC0 | Crude block — **effectively absent**. |
| CADRE | — | — | **Absent**. |

### ISRU / excavation / processing
- NASA **RASSOR** (PD, round 1) remains the only realistic lunar excavator.
- **Chemical tank** (Sketchfab `63c001e7…`, BY, 8.7k faces, GLB mirror `glbs/000-056/…`): twin process vessels on skid → ISRU oxygen-extraction plant stand-in (retexture clean metal).
- SRB `beneficiation_unit` (round 1).
- **Absent**: any realistic ISRU plant / regolith processing module / 3D-printing construction rig. Excavators found are terrestrial (CAT/Hitachi scans).

### Cargo / logistics containers / pallets
| Pick | Source / license | Notes |
|---|---|---|
| **Sci-Fi crate / ammunition box (1) & (2)** (ul1tka) `69fe3211…`, `342efe4d…` | Sketchfab **BY**, GLB mirrors `glbs/000-148/…`, `glbs/000-006/…` | 1.6k / 648 faces, clean white aerospace look with handles/latches; units arbitrary → rescale to ≤0.5 m manipulable cases. Best-looking graspable containers found. |
| BlenderKit "Sci-Fi Crate", "Sci-Fi Box" | **CC0** | Simple, retexturable. |
| BlenderKit "Scifi Storage Case" (0.27×0.59×0.19 m), "High Voltage Battery Transport Container" (0.56 m), "Simple-Space-box" (0.43 m) | **RF** free | Real-scale, manipulable-sized. |
| NASA ORU, Crew Lock Bag, SLI carrier | PD (round 1) | Still best logistics set. |

### Charging / docking stations
- **Sci-fi electrical charger** (Sketchfab `f09b75dc…`, BY, 12k faces, GLB mirror `glbs/000-032/…`): cable-plug charging pedestal — sci-fi styling, usable as rover charger after retexture.
- **IDSS docking system** (above) as a mechanical docking/mating interface.
- **Absent**: realistic rover charging dock (NVIDIA Carter dock, round 1, is closest).

### Electrical / maintenance infrastructure (PDU, breakers, batteries)
| Pick | Source / license | Notes |
|---|---|---|
| **Electric Distribution Box** `b5e233fb…` | Sketchfab **BY-SA**, 5.7k faces | Open door exposing breaker rows — ideal PDU/breaker-panel reference; door likely separable (verify in file). |
| Electrical Breaker Panel Box – LP `4b12b4e0…`; Switchboard `cbfb7619…` | Sketchfab **BY** | Breaker box on post; hazard-marked cabinet door. |
| Electrical Control Panel sci-fi `c0dfab99…` (round 1) | **BY** | Wall power box with door. |
| BlenderKit "Electrical control panel", "White Electric box" (scan) | **CC0** | Retexturable cabinets. |
| **Simple Sci-fi power battery** `4663e0ac…` | Sketchfab **BY**, GLB mirror `glbs/000-103/…`, 18 parts | Swappable battery/ORU module look with handles. |
| Server rack (sci-fi) `5320622f…`; Comms Room assets `566a5b11…` | **BY** | Comm cabinet interiors, seismograph, radio racks. |
| **Light Tower** `9addea6a…` | **BY**, GLB mirror `glbs/000-055/…`, real scale 1.2×2.0×1.8 m | Mobile floodlight mast — plausible work-site lighting. |
| Tool Chest `7bdb028e…`, Drawer Tool Cart `da8955e5…` | **BY** | Terrestrial red finish → retexture; drawers modelled. |

### EVA tools / sample containers / science instruments
- EVA tools: NASA PD tools + Poly Haven CC0 (round 1) — nothing better found; BlenderKit **CC0** "Metal Toolbox".
- Sample containers: ALSRC (BY, round 1) + Astromaterials3D Apollo samples (CC0, dozens more confirmed).
- **Surface science instruments (seismometer, retroreflector, ALSEP, weather station)**: **absent** in usable form (only terrestrial seismograph in Comms Room assets, low-poly weather stations).

## 2. Visual realism verdicts (from contact sheets)

- Credible / NASA-plausible: Mars One base, MMSEV, Deutsches Museum LRV, ExoMars, Apollo LM (both), Industrial Antenna, Satellite Comms, IDSS, Sci-Fi crates (white), Electric Distribution Box, Root Module, Light Tower, Vikram (Printables).
- Sci-fi-leaning but acceptable after retexture: Gazebo moon dome, sci-fi charger, sci-fi battery, Garecra dish, chemical tank, edwincgstudio solar panel.
- Rejected (cartoon/game/terrestrial mismatch): Habitat Lander Pod, LPRV Rover, "Mars Base" (MOJackal), Micro Habitation Pod, sci-fi space stations, Moonwards, Kenney/Poly Pizza, KSP/Fallout/Warhammer items, low-poly solar panels (MRowa BY-SA), Starship MK1/Block2 WIP, terrestrial excavators.

## 3. Practical download notes

- **Objaverse GLB mirror** avoids Sketchfab login: `https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/<shard>/<uid>.glb` (paths listed above; full map in `r2/object-paths.json.gz`). Verified by downloading 13 picks into `r2/glb/` and reading glTF node/extent data (`r2/glb/glbinfo.py`). Newer items (Industrial Antenna, Deutsches Museum LRV, Vikram, Electric Distribution Box, Starship S25) are not in Objaverse 1.0 → need a Sketchfab account/API token.
- **Scale is unreliable**: Mars One base (~986 units), sci-fi crates (~200–440), Apollo LM CMFDesign (~154), sci-fi charger (~281) are unit-less; MMSEV, ExoMars, IDSS, Light Tower are ~real metres. Normalize every asset.
- Gazebo Fuel download: `https://fuel.gazebosim.org/1.0/OpenRobotics/models/Moon%20base%20dome/tip/moon%20base%20dome.zip` pattern (DAE + PBR JPG).
- Printables downloads need a (free) login; files are STL/3MF only (no materials).
- CC-BY: keep `ATTRIBUTION.md` (author + URL + license). **BY-SA** items (LRV scan, Electric Distribution Box, SLIM, Vikram print): modified USDs must be released BY-SA — acceptable for a public research repo, but keep them in a separate folder.
- Still blocked: TurboSquid/CGTrader free (ML clause), Sketchfab NC/ND/store, Printables "Standard Digital File" and NC/ND, Fab/Megascans standalone.

## 4. Remaining true gaps (searched everywhere above)

VSAT vertical solar array, fission surface power unit, thermal radiator panels, Artemis-era habitat (FSH/LIFE), Blue Ghost / Griffin / Argonaut / Blue Moon landers (open-licensed), VIPER (usable), CADRE, LTV (open-licensed), ISRU plant, realistic rover charging dock, surface science instruments. For these the realistic path is **composition** (iROSA blanket + truss mast = VSAT-like; tanks + electrical cabinets + radiator panels from simple geometry) rather than a download.
