# 05 — Open-source articulated / manipulable engineering props (asset round 2)

Research-only, 2026-09-15. Goal: find open assets for what the design doc planned to hand-build
(PDU/electrical cabinets, breakers/levers/switches, valves, human-scale plugs/sockets, drawers,
lockers, cases with lids/latches, battery/ORU modules with handles, hatches, racks).
Contact sheets (all viewed):
- `artvip_sheet.jpg` — ArtVIP toolbox / industrial / lab / cabinet thumbnails
- `ph_sheet.jpg` — Poly Haven CC0 industrial props
- `skf3_sheet.jpg` — curated Sketchfab CC-BY candidates
- `fuel_sheet.jpg` — Gazebo Fuel engineering models
- `src_drc_sheet.jpg` — Blender renders of DRC valves + NASA SRC props (SRC textures not resolved in render → magenta; geometry only)

Envelope check reference (04): grasp feature 15–45 mm at z 0.45–1.00 m, moved part ≤1 kg (re-scale / re-mass allowed).

## 1. Verdict table (best per target category)

| Target | Best open asset(s) | Source / license | Format / joints (verified) | Scale / fit | Look |
|---|---|---|---|---|---|
| **Rugged equipment / spares case with lid + latches** | ArtVIP `household_items/toolbox/clamshell_tool_box_1` (orange Pelican-style), `clamshell_tool_box_2/7/8` | **ArtVIP, Apache-2.0** (HF `X-Humanoid/ArtVIP`, ungated) | **USD, Isaac-Sim-ready**: ArticulationRoot, 3 rigid bodies, 4 colliders, 2 revolute (lid, latch) + fixed; mpu 1.0, Z-up (pxr probe) | 0.60×0.45×0.25 m; handle width fits; re-mass | Photoreal, exactly the "lunar equipment case" look |
| same | Poly Haven `medical_box` (nodes: lid, latch, latch_rings, handle), `metal_toolbox` (lid, tray, handle, latches) | **CC0** | glTF, **separate part nodes** (no joints — author revolute/prismatic in USD) | ~0.40×0.29×0.35 m | Photoreal PBR |
| same | Gazebo Fuel `OpenRobotics/Large Crate Handles` (black hard case, side handles), `OpenRobotics/Electrical Box` (sealed rugged box) | CC-BY 4.0 / CC0 | SDF+DAE | ~0.6 m | mid-poly game |
| **Drawers / tool chest** | ArtVIP `toolbox/drawer_kit_10` (red 5-drawer chest), `drawer_kit_5/7` | Apache-2.0 | **USD, 6 rigid, 5 prismatic joints**, colliders | 0.38×0.26×0.34 m (bench-top → drawer handles land in grasp band on a bench) | Photoreal |
| same | Poly Haven `metal_tool_chest` (lid + hinges + handles as nodes; drawers not split), `tool_cart` (single mesh) | CC0 | glTF nodes | 0.69×0.41×0.65 m | Photoreal |
| **Locker / equipment cabinet with doors** | ArtVIP `lab_items/lab_cabinet/poison_cabinet` (8 revolute doors), `lab_cabinet001–005`, `small_furniture/cabinet/*` (damping-tuned doors/drawers) | Apache-2.0 | USD, ArticulationRoot, 9 bodies, 200 colliders | 1.24×0.78×3.0 m (too tall; lower modules usable) | Photoreal (lab white/grey) |
| same | Isaac `Sektion_Cabinet` (already in 01) | Omniverse | USD articulated | 0.67×0.76×0.79 m | household |
| **Electrical distribution box / PDU cabinet (door + breakers)** | Poly Haven **`power_box_01`** — open DB board with breaker rows; glTF nodes `power_box_01_door` + `power_box_01_box` → one revolute door; `utility_box_01/02` (outdoor 1.12 m cabinets, single mesh) | **CC0** | glTF; door separable; breakers baked in box mesh | 0.38×0.42×0.50 m (wall/bench mount at 0.5–1.0 m) | **Photoreal — best PDU look found** |
| same | Sketchfab `Electrical panel` (efimknife, open door + breaker rows), `Electric Distribution Box` (avadhootnb11, **CC-BY-SA**, animated door → separate node), `Weathered Electric Box`, `Industrial Electrical Box` (door open), `Breaker Panel Box LP` | CC-BY (one BY-SA) | FBX/glTF via Sketchfab download (**account/OAuth needed**); door is separate node where animated | 0.4–1.2 m | Good PBR |
| same | ArtVIP `industrial_machinery/machine/machine002…018` (industrial enclosures), `security_equipment/fire_alarm` | Apache-2.0 | USD; machine002 = 2.0×0.9×1.9 m with 1 revolute + 1 prismatic door | large | no thumbnails served; not visually checked |
| **Breaker lever / knife switch / toggle** | Sketchfab `Lever Power Switch` (fengyuan20000303, knife lever, 872 faces, **animated → lever separate**), `Lever_Switch_Electric_16MB` (animated), `Switchers` (bumstrum) | CC-BY | glTF nodes | re-scale lever handle to 25–35 mm | good |
| same | Poly Haven `portable_generator` — nodes `dial`, `switch`, `toggle` (rotary dial + toggle as separate parts) | CC0 | glTF nodes | small knobs (need up-scaled grip) | Photoreal |
| **Valves (rotary)** | Gazebo Fuel **DRC Practice valves**: Ball valve (+wall), Hand-wheel valve, **Handle-wheel valve** (0.2 m wheel w/ crank handle), Wheel valve, Wheel valve large, Valve wall | **CC0 on Fuel** (same models CC-BY 3.0 in `osrf/gazebo_models`) | **SDF with revolute joint + meshes** (pxr-free check of SDF) | ball-valve lever 93 mm, wheels 0.09–0.25 m; DRC-scale for humanoids ≈ fits RM-75 | colour-coded, clean |
| same | Fuel `hmoyen/Blow-Out Preventer Panel` — ROV panel with **5 revolute valves** + AprilTags | CC-BY 4.0 | SDF/STL/OBJ | subsea ROV panel ~1 m | functional |
| same | Sketchfab `Industrial Valve` (red wheel, 1.9k faces), `Main gas shut-off valve` (photoscan) | CC-BY | single mesh (wheel must be split) | — | good |
| **Human-scale plug / socket (connector)** | Fuel `hmoyen/M to F plug`, `F to M plug` + `Electrical Panel Bare Model` socket (**ROV wet-mate connectors with T-handles**, 0.2–0.5 kg, fixed `socket_joint`, "plug and socket plugin") | CC-BY 4.0 | SDF/DAE | handle bar grip ≈ right scale for a gripper | low-mid poly |
| same | **NASA Space Robotics Challenge (`osrf/srcsim`)** `worlds/cable.erb`: 16-link cable + plug (Ø50 mm outer / Ø34 mm body) into solar-array socket (Task 2) | Apache-2.0 | SDF/ERB parametric | Ø34 mm grip = in band | simple primitives |
| **Battery / ORU module with handles** | NASA SRC `solar_panel` (2.4 kg folding panel with 3 links), SRC `air_leak_detector` (1 kg handheld), `leak_patch_tool` (prismatic button); NASA ORU (02); Sketchfab `HV Battery Transport Container` (handles, CC-BY) | Apache-2.0 / PD / CC-BY | SDF (SRC), glTF | 0.44×0.51×0.12 m; tools 0.4 m long | SRC mid-poly textured; HV container good |
| **Comm dish (articulated maintenance target)** | NASA SRC **`satellite_dish`**: links base/pivot/dish/**wheel_yaw/wheel_pitch**, revolute `dish_yaw`, `dish_pitch` (−0.2…1.57 rad) — robot turns handwheels to align dish (SRC Task 1) | Apache-2.0 | SDF+OBJ (mm, scale 0.001) | 1.6×2.1×2.4 m | mid-poly, textured |
| **Solar array (static hero + socket)** | NASA SRC `solar_array` (3.2×2.0×2.1 m), `src_habitat` (HDU exterior + wheel valve), `space_table`, `mars_crate` | Apache-2.0 | SDF+OBJ | real m | mid-poly textured |
| **Hatch / access door** | Fuel `OpenRobotics/hatch` (SubT, frame + door link), Sketchfab `Naval Ship Door/Hatch` (CC-BY, frame + door), ArtVIP `small_furniture/door/*`, `industrial_machinery/subway/subwaydoor` | CC0 / CC-BY / Apache-2.0 | SDF / glTF / USD | human scale | ok–good |
| **Racks with slots (ORU bay)** | Sketchfab `Server rack` (Crysis007-94), `Server Racking System`, `Network Server Rack`, `Comms Room – Assets` (racks + consoles) | CC-BY | single meshes (slots must be modelled as fixtures) | 2 m racks | good |
| **Tools (graspable)** | Poly Haven `ratchet_wrench` (rigged), `pipe_wrench`, `adjustable_wrench`, `retro_multimeter`, `screwdriver`; NASA tools (02); SRC detector/patch tool; Isaac `power_drill_physics` (01) | CC0 / PD / Apache-2.0 | glTF/SDF/USD | 25–45 mm handles | Photoreal |
| **Power / utility dressing** | Poly Haven `portable_generator`, `utility_box_01/02`, `propane_tank`, `modular_electric_cables`, `modular_industrial_pipes_01`, `portable_searchlight`; Sketchfab `Diesel generator` (white), `Cable reels` | CC0 / CC-BY | glTF | real m | Photoreal |

## 2. Dataset-level findings

| Dataset | What's relevant | Format | License | Usable? |
|---|---|---|---|---|
| **ArtVIP** (ICLR 2026, HF `X-Humanoid/ArtVIP`, v1.2 2026-03) | 206 articulated objects + 48 "modular interaction" (magnetic/damped doors, triggers); categories incl. `toolbox` (clamshell cases, drawer kits), `industrial_machinery` (machines, security equipment, AGV, forklift/dolly, elevator, ticket gate, subway door), `lab_items` (lab/poison cabinets, bench, microscope), `small_furniture/cabinet/door`, `medical_equipment` (carts) | **USD authored for Isaac Sim 5.0** (joints, colliders, drives; verified 5 files with pxr) | **Apache-2.0**, ungated | **Yes — strongest find**; copy into repo allowed with NOTICE |
| **Poly Haven** | CC0 photoreal industrial props; several split into part nodes (power_box_01 door; tool chest lid; medical_box lid/latch; toolbox lid/tray; generator dial/switch/toggle) | glTF/FBX/Blend | CC0 | **Yes**; add joints ourselves |
| **Gazebo Fuel / osrf/gazebo_models** | DRC valves (joints), SubT hatch, ROV plug/socket + BOP valve panel, crates/boxes | SDF + DAE/OBJ/STL | CC0 / CC-BY 3.0 / CC-BY 4.0 per model | **Yes**; SDF→URDF→USD or rebuild joints in USD |
| **osrf/srcsim (NASA Space Robotics Challenge)** | satellite dish w/ handwheels (2 revolute), solar array + cable/plug, folding solar panel, leak detector, patch tool (prismatic button), habitat, crates, table, walkways, Mars rocks | SDF + OBJ | **Apache-2.0** | **Yes — space-mission-relevant maintenance props with joints** |
| Sketchfab CC-BY | best-looking electrical panels / lever switches / hard cases / racks / valves | FBX/glTF (download needs account) | CC-BY (keep ATTRIBUTION); avoid BY-NC/ND | Yes, per model; joints authored by us; animated models already have movable part as separate node |
| PartNet-Mobility (SAPIEN) | Safe, Switch, Suitcase, Box, StorageFurniture, Door, Faucet (rotary handles) — household scale | URDF + OBJ | SAPIEN terms: non-commercial research, no redistribution (terms page unreachable from host — verify); **download currently broken** (ManiSkill issue #1489, opened 2026-09-14: storage1.ucsd.edu refuses connections) | Fallback only; household look |
| GAPartNet | Handles/lids/drawers/knobs part annotations over PartNet-Mobility + AKB-48 | URDF | **CC BY-NC 4.0** | Fallback only |
| BEHAVIOR-1K / OmniGibson | `electric_switch`, `battery`, `fire_extinguisher`, cabinets… | encrypted USD | encrypted because sourced from ShapeNet/TurboSquid | **No** (can't export/modify) |
| ReplicaCAD / HSSD | household articulated furniture | GLB/URDF | CC-BY 4.0 / CC-BY-NC | Low relevance |
| AKB-48 | 2,037 scanned household articulated objects, 48 cats | URDF/OBJ | license not stated on pages found | Low relevance |
| Infinite-Mobility / Infinigen-Sim | procedural articulated generators (cabinets, drawers, doors, lamps, appliances) → URDF/USD/MJCF | Blender procedural | **BSD-3** | Could mass-generate cabinet/drawer variants; household style |
| Objaverse / Objaverse-XL | Sketchfab CC mirror, per-object license, no joints | GLB | per object | Same as Sketchfab |

## 3. What is still genuinely missing (after this round)

1. **A lunar/space-flavoured PDU with articulated breakers + swappable ORU slot as one asset.** Closest: Poly Haven `power_box_01` (CC0, photoreal, door split; breakers baked) or Sketchfab `Electric Distribution Box` (animated door). Plan: use these shells, add a door joint, and add a few separate breaker-lever / ORU-slot parts from the lever-switch and ArtVIP/ORU assets — assembly, not modelling from scratch.
2. **Slot-in ORU/battery bay (rack with receptacles).** Racks exist only as single meshes; the slot fixture (rails + seated frame) still has to be authored. The ORU module itself exists (NASA ORU, SRC solar panel, HV battery container).
3. **Industrial-scale plug/socket in a clean aerospace style.** Only the ROV wet-mate plugs (Fuel, CC-BY, low-poly) and the SRC parametric cable plug exist; they're functionally right but visually basic — retexture.
4. **VSAT-style vertical solar array mast** — still none open; SRC `solar_array` (Apache-2.0) is a ground array, usable as a stand-in.

## 4. Import path to Isaac Sim 5.1

- ArtVIP: native USD (built for Isaac Sim 5.0); reference directly; restyle materials; set mass on movable links.
- SDF (Fuel/SRC/DRC): convert SDF→URDF (`sdformat_urdf` / manual), then Isaac Sim URDF Importer (`isaacsim.asset.importer.urdf`) → USD; or import meshes and author joints in USD.
- glTF/FBX (Poly Haven, Sketchfab): Blender → USD (host has Blender 4.5) or `omni.kit.asset_converter`; keep separated nodes as links; author `PhysicsRevoluteJoint`/`PrismaticJoint` + ArticulationRoot + convex colliders; `metersPerUnit` check.
- PartNet-Mobility/GAPartNet: URDF Importer (only if non-commercial terms acceptable and download works).

## 5. Sources
- ArtVIP: https://huggingface.co/datasets/X-Humanoid/ArtVIP (license tag apache-2.0; README "compatible with Isaac-Sim 5.0"); https://arxiv.org/abs/2506.04941
- Poly Haven API: https://api.polyhaven.com (models `power_box_01`, `metal_tool_chest`, `medical_box`, `metal_toolbox`, `portable_generator`, `utility_box_01/02`, …), license CC0 (polyhaven.com/license)
- Gazebo Fuel: https://fuel.gazebosim.org (DRC Practice valves — CC0; hmoyen/M to F plug, F to M plug, Electrical Panel Bare Model, Blow-Out Preventer Panel — CC-BY 4.0; OpenRobotics/hatch, Electrical Box, Toolbox — CC0; Large Crate Handles — CC-BY 4.0)
- osrf/gazebo_models LICENSE: CC-BY 3.0 Unported; osrf/srcsim LICENSE: Apache-2.0 (https://github.com/osrf/srcsim)
- Sketchfab API model pages (license labels read from `/v3/models/<uid>`), uids in `uids.txt`
- PartNet-Mobility: https://sapien.ucsd.edu/browse ; download outage https://github.com/mani-skill/ManiSkill/issues/1489
- GAPartNet: https://pku-epic.github.io/GAPartNet/ (CC BY-NC 4.0)
- BEHAVIOR-1K encryption rationale: https://behavior.stanford.edu/getting_started/important_concepts.html ; categories https://behavior.stanford.edu/knowledgebase/categories/index.html
- ReplicaCAD: https://aihabitat.org/datasets/replica_cad/ (CC BY 4.0)
- Infinite-Mobility: https://github.com/InternRobotics/Infinite-Mobility (BSD-3 LICENSE, Princeton Infinigen base); Infinigen-Sim: https://arxiv.org/abs/2505.10755
- AKB-48: https://arxiv.org/abs/2202.08432
