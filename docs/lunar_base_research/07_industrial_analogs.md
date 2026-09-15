# 07 — Earth industrial / energy / telecom assets that retexture into a lunar base

Second asset round, 2026-09-15. Research only. Does not repeat 01 (NVIDIA/SimReady) or 02
(NASA/space-specific). Visual judgments from contact sheets actually viewed in this dir:
`r2_energy.jpg`, `r2_other.jpg`, `r2_space.jpg`, `r2_polyhaven.jpg`. Raw search dumps:
`skf2_energy.txt`, `skf2_other.txt`, `skf2_other_filtered.txt`, `skf3.txt`, `fuel.txt`,
`blenderkit.txt`, `acg.json`.

Retexture assumption: almost every Earth asset is weathered/rusted or colored; the plan is to keep
geometry and re-material with ambientCG CC0 materials (white paint, brushed metal, gold MLI foil,
solar cell) in Blender. Geometry quality, scale and part separability are what matter here.

## 0. License verdicts by source

| Source | License | Research sim + published figures/video | Public-repo redistribution | Notes |
|---|---|---|---|---|
| Poly Haven | CC0 | Yes | Yes | glTF/FBX/Blend direct via api.polyhaven.com, no account; real scale |
| ambientCG | CC0 | Yes | Yes | PBR materials |
| Sketchfab CC-BY / CC-BY-SA | CC-BY 4.0 / BY-SA | Yes (attribution file) | Yes w/ attribution (SA: derivatives BY-SA) | download needs a Sketchfab account/API token; glTF auto-conversion + original. **Avoid models tagged meshy/Tripo/Rodin/"createdwithai"** (AI-generated meshes, messy topology, e.g. `BESS_rexnew`, `Industrial Switchgear`) |
| Gazebo Fuel (OpenRobotics) | mostly CC0 / CC-BY 4.0; some CC-BY-NC-ND (MovAi, ctrazziwp) → avoid | Yes | Yes for CC0/BY | quality mostly SubT/hospital low-fi |
| BlenderKit CC0 subset | CC0 | Yes | Yes | ≈ Poly Haven mirror; paid/"not free" items need subscription |
| Objaverse 1.0 | per-object CC (721k BY, 3.5k CC0, NC/SA variants) | per object | per object | same Sketchfab pool; useful later for bulk license-filtered pulls, not new content |
| Blender Studio "Charge" asset library | CC-BY (credits kept) | Yes | Yes w/ attribution | battery-factory industrial props, tools, metals; download needs Blender Studio membership |
| Fab.com (incl. free listings) | Fab Standard License | Yes (any engine allowed) | **No standalone redistribution**; NoAI-tagged listings forbid gen-AI data use | local cache only; fab.com blocks automated fetch (Cloudflare) — verify each listing manually |
| Unity Asset Store (free packs) | Unity Asset Store EULA | Yes, other engines allowed | No standalone redistribution | local cache only |
| Clearpath `cpr_gazebo` (inspection/agriculture worlds) | BSD-3 repo | Yes | Yes | solar panel mesh texture named `SolarPanelsPolycrystalline…_COL_3K` looks like a Poliigon texture → texture provenance unclear, use mesh only |
| Poly Pizza, Quaternius, Kenney | CC0/CC-BY | — | — | **stylized/low-poly, rejected on look** |

## 1. Best candidates per category

Scale = real-world size (Poly Haven dimensions metadata in m; Sketchfab needs rescale check).
"Parts" = separable nodes for articulation (verify in glTF after download).

### 1.1 Solar arrays / trackers / masts
| Model | URL | License | Faces | Look / fit |
|---|---|---|---|---|
| **Photovoltaic Panels** (mfb64) | sketchfab.com/3d-models/cc9b7d59031e44ddb873056effece590 | CC-BY | 31k | clean framed module, front+back, junction boxes — tile into array blankets |
| **光伏发电板架集合 PV panel racks collection** (mrdt.club) | …/5f71fce4fa394726bba185ae54e53498 | CC-BY | 1.42M | many racking types incl. pole-mounted single-axis trackers — best tracker/mast geometry; decimate |
| Monocrystalline Sun Panels Set | …/05397c7f453b4b9b856c9d56f7369aa7 | CC-BY | 3k | simple but credible panels (fallback) |
| **telecom tower** (lattice) | …/103135f81b8e42b9986d9b217a749ca6 | CC-BY | 14k | lattice mast body → compose VSAT-style vertical array (mast + PV blanket) |
| Clearpath cpr_gazebo solar panels | github.com/clearpathrobotics/cpr_gazebo | BSD-3 (texture unclear) | low | plain framed panels |
| ambientCG `SolarPanel002/003` | ambientcg.com | CC0 | — | solar-cell material |
| Rejected | plasticarm "Solar Farm Array" (sci-fi flower), low-poly panel arrays |

### 1.2 Battery storage / switchgear / distribution cabinets (PDU candidates)
| Model | URL | License | Faces | Look / fit |
|---|---|---|---|---|
| **utility_box_01 / utility_box_02** | polyhaven.com/a/utility_box_01, _02 | CC0 | 4.4k / 6.3k | outdoor distribution cabinet 0.52/0.92 × 0.43 × 1.12 m, door handles, vents — **best PDU body** (retexture white); doors part of mesh → split in Blender |
| **power_box_01** | polyhaven.com/a/power_box_01 | CC0 | 21k | breaker panel 0.38×0.42×0.50 m, **rigged door**, breaker rows — PDU interior / breaker-row detail |
| **Distribution_Box** (ESobolev) | …/18b306c360d24cac9f5cbbfe96cfed41 | CC-BY | 5k (641 likes) | realistic box with open door and knife switches |
| **Integrated Box Energy Storage System** (mrdt.club) | …/4b2d126ea84f4634899d885befe96394 | CC-BY | 318k | clean white battery racks/cabinets + heat-exchanger units — best BESS / battery-module look, already near aerospace white |
| **10kV ring main unit** (mrdt.club) | …/630e2c585c2142a095b9ddd51de8ef88 | CC-BY | 116k | white multi-door switch cabinets on a railed platform — power-field switchgear |
| Electrical Distribution Cabinet (fdgasd7) | …/5dd2ce8a5baf4efca7179ed821084a21 | CC-BY | 51k | clean white panel face with switches/lamps |
| Electrical Breaker Panel Box LP | …/4b12b4e00fc14f95beb55d7016eaf28d | CC-BY | 4.7k | open breaker panel + conduit |
| Distribution box (Ianchiu0103) | …/227521ac5d5e465192bb9534e7989396 | CC-BY | 62k | wired breaker interior |
| Electric telecom box (matousekfoto, 3D scan) | …/25a8fe8fe1c24bdbb2f88ffbf66568e0 | CC-BY | 194k | photoreal concrete-base cabinet, monolithic scan → visual only |
| Diesel generator (epilogueronin) | …/7a0b72c7d01944a8aafab59d44eb120e | CC-BY | 10k | clean white enclosed generator w/ panel — power/converter unit |
| Solar Inverter Subsystem / SMA Sunny Boy (avredu) | …/aa2ec0ed329342b6a059e3eeab806e22 | CC-BY | 28k | inverter + isolator switches (rotary handle = graspable switch) |
| Avoid | `battery energy storage system (BESS)` rexnewgeek4 and `Industrial Switchgear` MADMOVIESINC — AI-generated tags |

### 1.3 Charging stations / docks
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| New energy vehicle charging station (mrdt.club) | …/1930fe67b1d84a3a9dbcf4cb50c58a8f | CC-BY | 202k | kiosks + charger posts + cabinets; plug/holster geometry |
| EV Charging Station A (khekwei) | …/aa2af6b5d2f54ac395cfc7e132f25282 | CC-BY | 27k | canopy + charger post |
| Sci-fi electrical charger (JonParrish) | …/f09b75dca41b40f6b1c3c64eca138094 | CC-BY | 12k | high-quality sci-fi charger column (glow strips → tone down) |
| Low Poly Charging Station (vadzaecc) | …/60c2ed77623149d7b45e1d58b7360cb1 | CC-BY | 5.6k | round dock pad + solar panel — concept close to rover dock, look semi-stylized |
| Fuel `HospitalRobotCharger` | fuel.gazebosim.org OpenRobotics | CC-BY | low | wall robot charger |

### 1.4 Telecom masts / dish antennas
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| **Satellite Dish** (Garecra) | …/2da4f72575944b92a681f1ba8f74b8d6 | CC-BY | 1.16M (236 likes) | segmented hex-panel reflector on lattice pedestal — **best surface comm dish**, decimate |
| parabolic antenna (MKisu) | …/48a3827de3dc44e1a8d95040a0b4525a | CC-BY | 9k | clean simple dish on post |
| BTS Antennas (Parabolic & Sectoral) | …/5e7feb9be34f4a128b213b9d6d6069a7 | CC-BY | 14k | microwave dish + sector antenna — relay terminal on a mast |
| 5G Telecommunications Mast | …/c9ea1b7b2e9043deb8c082e392deb4bc | CC-BY | 15k | slim mast + base cabinet |
| telecom tower (lattice) | see 1.1 | | | |
| (NASA Tall Dish, Radome already in 02) |

### 1.5 Cable reels / conduits / trays
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| **modular_electric_cables** | polyhaven.com/a/modular_electric_cables | CC0 | 42k | conduit runs, junction boxes, connectors kit — harness runs PDU↔arrays |
| Cable reels (thesidekick, photogrammetry) | …/53d00d26d6e14cd5bca1d7cedd4eb3b4 | CC-BY | 331k | realistic reels + coiled cable, grass base to strip |
| Fuel `Cable_Spool` | OpenRobotics | CC-BY | low | simple spool (movable obstruction) |
| UTILITY TUNNEL CABLE TRAYS & PIPING | …/5140c7e8b536400c97a3f546dd58f1fd | CC-BY | 1.04M | Revit-style trays/pipes (clean, heavy) |

### 1.6 Pipes / valves / tanks
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| **modular_pipes** | polyhaven.com/a/modular_pipes | CC0 | 47k | pipe kit **with handwheel valves** (valve wheel = articulable, graspable) |
| modular_industrial_pipes_01 | polyhaven.com/a/modular_industrial_pipes_01 | CC0 | 12k | flanges, red handwheel valve |
| Large Industrial Storage Tanks (duanesmind) | …/bd3ac97071104b64bc388a155b64f79e | CC-BY | 10k (952 likes) | spherical tanks + stairs — ISRU/propellant farm after white retexture |
| Gas Bottles Set | …/d671d93577b546b3bc8eda586ee75b31 | CC-BY | 5k | cylinders (O2/N2 bottle look) |
| propane_tank / small_lpg_tank | polyhaven.com | CC0 | — | small pressure bottles |

### 1.7 Modular container buildings / habitat analogs
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| **Halley VI Antarctic Research Station Dorm Pod** (lages.miguel) | …/88dbccb1cb6e487585a6505d64cb36e8 | CC-BY | 68k | module on hydraulic ski-legs with stairs — **strong habitat/logistics module analog** (repaint blue→white) |
| Classic Shipping Container (Webster) | …/772f4be391a245f699c54e6cf157c58d | CC-BY | 17k | ISO container, doors modeled open → logistics module / depot shed |
| Container Pack (drcrazzie) | …/0d416a9bcfc14978aa50e80281dfe9a5 | CC-BY | 448k | many rusty containers (retexture) |
| Rejected | popo57 "lunar base" (CC-BY but blocky/untextured), Habitat Lander Pod (Mars branding, game look), glass container office |

### 1.8 Shelving / racks / pallets
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| steel_frame_shelves_01/02/03 | polyhaven.com | CC0 | 8k | 2.35×0.72×2.31 m steel shelving (retexture boards→metal) |
| Modular Shelving Unit (Metal) (Webster) | …/6a1f71934d434585aa598b004f056ca9 | CC-BY | 6.6k | clean metal shelving |
| Server Racking System / Server rack (Crysis007-94) | …/6fe2cacf836b4aed96c650b286db5486, …/5320622f6c0741b7aed399bfa2965dc4 | CC-BY | 300k / 30k | avionics/electronics racks (open-frame one reads as spares rack) |
| Fuel `Pallet_Rack`, `Pallet_Rack_Section`, `Euro pallet` | OpenRobotics | CC-BY / CC0 | low | depot racking |

### 1.9 Ladders / stairs / platforms
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| **Scaffold Stairs Steel construction** (dchant) | …/d2230c5644234b3781cd7b2a6cec9638 | CC-BY | 79k (494 likes) | clean steel stair tower/platform — lander/habitat access |
| modular_fire_escape, ladder_sectioned_01 | polyhaven.com | CC0 | 11k / — | stair + ladder kit |
| Fuel ladders 60°/75° with 0–2 handrails | OpenRobotics (DRC/SubT) | CC0 | low | simple industrial ladders |

### 1.10 Floodlight towers / lighting
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| Light Tower (krambulini) | …/9addea6a4129438b83a1fc3ed4a784ec | CC-BY | 15k (424 likes) | trailer floodlight tower — work-site lighting |
| Ladder, Railing and Flood Light Set Up (dumokanart) | …/c75451c06c09431b908790bce04d329d | CC-BY | 11k (716 likes) | tripod floods, mast ladder, railing |
| portable_searchlight, security_light | polyhaven.com | CC0 | — | small lamps |

### 1.11 Fences / barriers
modular_chainlink_fence (Poly Haven CC0), Industrial Yellow Safety Barrier/Pole (…/cda46c9b520c48708dbecb5a72bfdf9a, CC-BY, 51k), Fuel Jersey barriers (CC0).

### 1.12 Workbenches / carts / cases / tools
| Model | URL | License | Faces | Fit |
|---|---|---|---|---|
| tool_cart, industrial_storage_cart, metal_tool_chest, metal_toolbox, hand_truck, industrial_pastic_container | polyhaven.com | CC0 | 10–29k | carts/chests with drawers & lids (split for articulation) |
| **Industrial AGV Trolley** (nguyenngockhanh.nnk) | …/016a066401a3489dafa98669d3a4b3f1 | CC-BY | 74k | clean white AGV with cage cart — reads as lunar cargo cart |
| Mechanic Tool Cart | …/b6845c7028ff4c73a0b62e78ef2b3500 | CC-BY | 13k | 3-tier cart |
| **Case – Pelican 472 style** | …/d4b448ffbf464d84a14c80307d8fea1c | CC-BY | 60k | hard equipment case with handles — graspable spares/sample case (retexture white) |
| **HYTORC LION Gun – electric torque wrench** | …/bcc47ca2a2204e13881cba04c19f840b | CC-BY | 1.09M | photoreal pistol-grip power tool — graspable tool (decimate) |
| Workbench (jjchalupnik) | …/9634d6a81a494925a909512c8048f446 | CC-BY | 8k | bench (wood → retexture) |

### 1.13 Materials (ambientCG CC0)
`Foil002` (gold foil → MLI), `Foil001/003` (aluminium), `SolarPanel002/003`, `MetalPlates015A/B`, `MetalPlates017A` (sci-fi panels), `PaintedMetal012` (white), `DiamondPlate*` (walkways), `SheetMetal001/002` (perforated), `CorrugatedSteel*`, `Styrofoam004` (insulation).

## 2. Remaining gaps after this round

1. **Vertical solar array mast (VSAT-like)**: no single model; compose lattice tower + PV racks/modules.
2. **PDU with real joints** (hinged door, removable ORU bays, breaker lever): geometry exists
   (utility_box + power_box + inverter isolator switch) but must be split into links and jointed.
3. **Human-scale connector/plug at 15–45 mm grip**: EV charger plug geometry (mrdt charging station)
   is the closest; needs extraction/rescale.
4. **Aerospace finish**: nearly everything needs re-materialing (weathered/colored Earth look).
5. **Cargo lander**: still from SRB (Resilience/Peregrine/Vikram) — nothing better found here.
6. Sketchfab downloads require an account token; Blender Studio Charge library requires membership.
