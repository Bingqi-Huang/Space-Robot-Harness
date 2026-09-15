# Lunar base scene — redesign for Mission A/B (Phase C restart)

**Status:** design, 2026-09-15; C1 (asset processing) done; C2 blockout built (SRB
`feat/lunar-base-scene`, `assets/lunar_base/scene/layout.yaml` is now the source of truth for
positions — it deviates from §4 where noted there: PDUs face south, landing pad moved NW so the
Starship shadow misses the base, core platform graded to one level), awaiting user approval. Supersedes
`docs/panel_remount_v2_mission_logic_plan.md` and the `panel_remount_v2` scene, which the
user rejected outright (too simple, SRB-assets-only, a solar panel sitting on a pedestal top,
a pedestal floating above terrain, the panel out of arm reach, the panel still tumbling off).
Research behind every claim here: `docs/lunar_base_research/` (00 requirements, 01 NVIDIA
assets, 02 NASA/internet assets, 03 lunar simulators, 04 SRB integration + LunarBot envelope,
05–07 second asset round).

> **Scope correction (user, 2026-09-15) — overrides the articulation detail in §5, §6.4, §8.4.**
> The paper proves the mission-level harness, not dexterous manipulation. Use good-looking
> downloaded assets with minimal edits; do not hand-model or articulate PDU doors, ORU bays,
> breaker levers or connectors. Maintenance/inspection = the robot navigates, observes (VLM),
> and touches marked waypoints on the asset or presses a dummy button; completion is read from
> simulator truth (EE reached waypoint / button state / object at destination). Logistics keeps
> simple pick-and-place of ≤1 kg items. Add a mechanism only when a covered/held-out case needs
> an observable state change. Concretely: Z2 PDU = Sketchfab "Electrical Distribution Cabinet"
> (Z2-03) as-is; Z2 solar = "PV racks & trackers" (Z2-12) crops; no Blender-authored gap assets
> unless nothing downloaded fits.
>
> **Assets live in the SRB fork** (user convention): `space_robotics_bench/assets/lunar_base/`
> — `manifest.yaml` (81 sources, licenses), `fetch_assets.py`, `processing.yaml` +
> `process/` Blender pipeline, `usd/` (git LFS). Batch 1 = 20 processed assets; review gallery
> https://claude.ai/artifact/EjraQQQRg3251eNQpUnF9U.

## 1. Design principles

1. **Experiment first.** The scene exists to carry Experiment I (covered vs held-out, Mission
   A + B, three methods on one capability stack) and Experiment II (extension cases).
   Every zone and asset below is traceable to a case in §5 (research_content §3.3, §5.4–5.6;
   execution_plan §6.4–6.5, §13).
2. **Credible near-term lunar surface base.** NASA/Artemis-style engineering look, real
   scale, south-pole low-sun lighting, regolith, craters, rocks, horizon. Good enough for
   the paper's scenario figure and mission-trace figure (research_content §6.6).
3. **Physically honest.** Structures sit on graded pads or snapped to measured terrain
   height; mounts, receptacles and latches look like real engineering interfaces; every
   manipulable is inside LunarBot's measured envelope (§3); dynamic spawns are
   collision-free and settle-checked.
4. **Mission-agnostic harness, fixed scene topology.** Covered/held-out variants move,
   enable, or change the state of existing objects; they never add/remove scene entities
   (IsaacLab vectorized scene graph, 04 §2.3). No decision logic in the scene.
5. **Verification before claims** (§8): offline geometry checks, per-tick settle traces,
   scripted manipulation feasibility, multi-angle renders reviewed by the user.

## 2. Hard constraints found in research (these shape the layout)

| Constraint | Value | Source |
|---|---|---|
| Graspable height band | TCP reachable z ≈0.32–1.13 m; **design grasp features at 0.45–1.00 m**; nothing graspable on the ground | 04 §1.2 |
| Standoff | arm is on chassis **−X end**; grasp feature **0.05–0.35 m beyond the −X hull edge** (top-down ≤0.25 m); side approach only ≈0.15 m | 04 §1.2 |
| Camera vs arm | front RGB-D + lidar on **+X end**, arm on −X end → inspect facing a target, turn around to manipulate; only the wrist camera sees the grasp | 04 §1.1 |
| Gripper | open jaw ≈66 mm; **grasp features 15–45 mm** (10–60 absolute) | 04 §1.3 |
| Mass | datasheet 5 kg cap; **manipulated items ≤1 kg** until a loaded hold is verified (arm has no holding stiffness under CARTESIAN_TWIST) | 04 §1.3 |
| Base / Nav2 | footprint r 0.82 m, inflation 0.87 m, diff-drive, 0.3 m/s → **aisles ≥2.0 m, turnaround pads ≥2.0 m dia** in front of every workstation | 04 §1.4 |
| Lidar | RayCaster ray-casts **only the first Mesh child of the scenery prim**; Nav2 sees nothing else | 04 §4.1 |
| Terrain | SRB procedural MoonSurface is **not flat** inside `flat_area_size` (±0.05 m at 1.5 m, ±0.28 m at 2.1 m, up to +0.7 m at 3–4 m for spacing 32); F18's "flat pad" was wrong | 04 §2.2 |
| TF/ROS for free | rigid objects, collections, articulations (+ every link) and articulation joint_states are published; static `AssetBaseCfg` and scenery are not | 04 §3 |
| Performance | deploy graph ≈12 Hz (RTF ≈0.24), 30 ms GPU render wait + 21 ms CPU PhysX already; PhysX on CPU (CCD) | 04 §4, F28 |
| Licenses | NASA PD (strip meatball/worm insignia for AI imagery), CC0 (Poly Haven, Astromaterials3D), CC-BY with attribution; NVIDIA Omniverse content modifiable but not redistributable standalone, `/Isaac/Environments/*` not modifiable; TurboSquid/CGTrader free assets blocked (ML clause) | 01 §4, 02 §0 |

Consequence for traverse time: a 25 m drive at 0.3 m/s is ~85 s sim ≈ 6 min wall at RTF
0.24. The base core must be compact (§4) or the campaign becomes unrunnable.

## 3. Site concept — "Shackleton Connecting Ridge Outpost"

A small crew-tended/robot-maintained Artemis-era surface outpost: habitat, power field,
comm station, landing pad with cargo depot, ISRU/excavation yard, rover dock, graded roads.
LunarBot is the resident maintenance/logistics robot.

- **Terrain:** real LOLA 5 m/px DEM of a south-pole site (PGDA, public domain; Connecting
  Ridge preferred) for macro relief, horizon and lighting geometry, upsampled with
  OmniLRS-style procedural craters/rocks (BSD-3 numpy generator) to cm-scale detail.
  Baked once into our own USD terrain. **Graded pads** (exactly planar, known z) under
  every structure and work site, blended with berms into the relief; roads graded too.
  Off-pad dressing snapped by bilinear DEM lookup (OmniLRS `StaticAssetsManager` pattern).
- **Integration:** new SRB scenery `LunarBase(Terrain)` (template: `Lunalab`/`Oberpfaffenhofen`,
  `srb/assets/scenery/facility.py`), selected by the Mission A/B tasks. Robot reset event
  overridden to a fixed dock pose. `num_envs=1`.
- **Lidar/Nav2:** the scenery USD's **first Mesh child is a single triangulated "world
  collision/lidar mesh"** = terrain + simplified exterior hulls of every static structure,
  so Nav2 sees buildings with no upstream RayCaster patch. Dynamic/articulated props stay
  separate (invisible to lidar — acceptable: they sit inside workstations off the road
  network; route obstructions that must block Nav2 are placed as static-mesh variants or
  detected via depth camera, decided in blockout).
- **Lighting:** low sun (elevation a few degrees) with long shadows, star skydome (SRB
  `stars`/`milky_way`), Earth low on the horizon. Sun/Earth vectors from SPICE only if a
  final scenario uses illumination (Phase D rule); otherwise a documented fixed epoch.

## 4. Layout (core ≈50 × 50 m, env origin = rover dock)

```text
                      N (+Y)
                 [Z3 Comm station]
                  Tall Dish + radome
                  comm cabinet (connector)
                        |
   [Z5 ISRU yard] ---- [Z1 Habitat & airlock staging] ---- [Z2 Power field]
   beneficiation unit   HDU habitat + logistics module      3 VSAT-style masts
   RASSOR (parked)      staging bench + ORU cradle          4 PDU cabinets on a
   regolith hopper      tool tray, spares locker (art.)     service aisle
        \                       |                             /
         \------------- [Z0 Rover dock / charging pad] ------/
                        start + "safe state" end pose
                                |
                 [Z4 Landing pad & cargo depot]
                  commercial lander (SRB Resilience/Peregrine)
                  NASA SLI carrier, cargo racks w/ ORU + tote slots
                  parked SEV rover (background / obstacle)
```

- Distances dock→zone 12–22 m; a road **loop** (Z5–Z1–Z2–Z4) so every zone has two routes
  (needed for route-obstruction and substitution cases).
- Every workstation face: grasp features at 0.45–1.00 m, a ≥2 m clear parking/turnaround
  pad in front, park line such that the −X hull edge ends 0.10–0.25 m from the feature.
- Background dressing outside the core (visual only, off lidar mesh where irrelevant):
  crater rims, boulder fields (Astromaterials3D/Poly Haven rocks), distant ridge from DEM.

## 5. Zones → assets → experiment cases

### Z2 Power field — Mission A primary site
- **VSAT-style solar array masts ×3** — authored in Blender (no credible free model exists,
  02 §5 gaps): lattice mast 6–8 m, rectangular array blanket, harness to PDUs. Static, hero.
- **PDU cabinet ×4 (identical class, per-instance state)** — authored, articulated:
  front **hinged door** (revolute, 30 mm bar handle at z≈0.85 m, low-stiffness detent),
  **2 ORU bays** each holding a swappable **ORU module** (rigid ≤1 kg, 25 mm T-handle at
  z≈0.65–0.8 m, seated pose = fixture frame), **breaker lever** (revolute, 2 detents, 30 mm
  knob at z≈0.75 m), **status beacon** (emissive colour driven by true state), **radiator
  dust cover** (hinged flap). All faults are *visible* (semantic observation, §3.4.2).
- Cases: covered A1 known fault (one PDU: door ajar + module unseated → reseat, close,
  verify via joint state + seat pose); covered A2 manipulation retry (module misses seat);
  **held-out A-obstruction** (tool case / fallen cable spool blocks the bay → relocate first);
  **held-out A-inconsistent** (beacon says nominal but a module is visibly unseated, or the
  beacon fault is on PDU-2 while the physical fault is on PDU-3 → closer wrist-camera look).
- Space-context hook (only if Phase D selects it): array output / battery state → power fact.

### Z3 Comm station — Mission A secondary site
- **NASA Tall Dish** (3 separable parts → pan/tilt joints; PD), **Radome** (PD),
  **comm cabinet** (authored: door + cable **plug/socket** with 35 mm plug body at z≈0.8 m).
- Cases: covered A3 connector reseat; held-out A-substitution candidate (Z3 road blocked by a
  non-movable parked rover → reach via loop road). Space-context hook: link availability.

### Z4 Landing pad & cargo depot — Mission B source
- **SRB commercial lander** (Resilience or Peregrine usdz; real CLPS-class hardware, already
  in `srb_assets`), **NASA Super Lightweight Interchangeable carrier** (PD),
  **cargo racks** (authored or SimReady shelf restyled + colliders) holding spare **ORU
  modules**, **NASA ORU box / Crew Lock Bag** (PD, handles re-fitted to 15–45 mm), SimReady
  `case_e01` / KLT totes (mass overridden ≤1 kg), **spares locker** = Isaac `Sektion_Cabinet`
  (2 drawers + 2 doors, articulated, restyled white/metal).
- Cases: covered B1 fetch spare ORU from rack → deliver to Z1 cradle / install in Z2 bay;
  **held-out B-hidden** (required spare not on the rack, only inside a closed locker drawer →
  open drawer, retrieve); **held-out B-occupied** (destination cradle occupied by a
  failed module → clear it to the returns tote first).

### Z1 Habitat & airlock staging — Mission B destination
- **NASA Habitat Demonstration Unit** (2 parts, PD; insignia repainted), logistics module,
  **staging bench** (authored/DigitalTwin worktable + colliders) with **ORU cradle** (seat
  fixture), **tool tray** (NASA Wrench, Ratchet, Pistol Grip Tool — PD; Poly Haven wrenches,
  CC0 — mass/handles checked), returns tote.
- Cases: delivery/placement effects (seat pose in cradle), tool fetch for Experiment II
  "new capability" extension (e.g. a pistol-grip-tool capability supplied identically to all
  methods).

### Z5 ISRU / excavation yard — obstruction & substitution source, visual richness
- **SRB beneficiation unit** (33 MB, convex-decomposed), **NASA RASSOR** parked (PD),
  regolith hopper/tanks (SimReady IBC tank restyled), cable spools, SimReady drums/jerricans
  as movable debris candidates (mass set per role: liftable ≤1 kg vs push-only heavy).

### Z0 Rover dock
- Charging dock (authored; NVIDIA Carter dock is visual-only reference), dock pad markings.
  "Leave the robot in an operationally safe condition" (research_content §3.1) becomes a
  verifiable end pose.

## 6. Asset pipeline

1. `experiments/scene_assets/fetch_assets.py` — downloads every third-party asset from its
   source URL into a git-ignored cache; `provenance.yaml` per asset (URL, license, author,
   date, modifications). Commit only our authored assets + NASA PD / CC0 / CC-BY
   (with `ATTRIBUTION.md`); NVIDIA content fetched, never vendored.
2. Conversion: GLB/OBJ/FBX → Blender 4.5 (host) or Isaac `omni.kit.asset_converter` → USD;
   rescale to metres (NVIDIA SimReady/DigitalTwin are cm), Z-up, strip NASA insignia,
   decimate hero meshes, instancing for repeats.
3. Physics authoring: static structures → simple convex/box collision proxies + contribution
   to the single lidar mesh; manipulables → convex decomposition, explicit `MassAPI` (≤1 kg),
   `max_depenetration_velocity` capped; articulated props → `ArticulationCfg` with fixed root,
   low-stiffness implicit actuators for doors/levers (IsaacLab cabinet precedent).
4. Authored-in-Blender set (gaps, our own CC0): VSAT-style mast, PDU cabinet (+door, bays,
   breaker, beacon, dust cover), ORU module, cargo rack, ORU cradle, comm cabinet + plug,
   rover dock. Materials from simforge (MLI gold, brushed metal, solar cell, scratched paint).
5. Performance budget (measured, not assumed): ≤~15 dynamic rigid bodies, ≤~8 articulations,
   instanced statics, no translucent materials; tick profile with `SRB_ROS_PROFILE=1` before/after.

## 7. Scenario control & verification truth

- One Mission A task, one Mission B task, each with a `scenario` config block (not a single
  enum): which PDU/cabinet is faulty, fault type (door/module/breaker/connector/beacon
  mismatch), obstruction object + pose (on/off), blocked road segment, spare location
  (rack/locker), destination occupancy. Scenario manifests (execution_plan §12) instantiate it.
- Evaluator/verifier truth from free ROS signals: articulation joint_states (door, breaker,
  drawer, dish), rigid-object TF (module/plug/tool poses vs fixture frames), robot dock pose.
  Fixture frames published as part of the scenario manifest (static structures have no TF).

## 8. Verification protocol (replaces "clean log + a few frames")

1. **Offline geometry** (pxr, no GPU): every static asset's bbox bottom vs terrain/pad z
   (gap ≤ 1 cm); spawn-pose pairwise overlap check for all dynamic/articulated bodies;
   every grasp feature vs the §2 reach/standoff/width table.
2. **Settle traces:** every dynamic body, every scenario variant, ≥3 resets: per-tick pose +
   velocity until sleep; fail on any velocity spike above a stated bound.
3. **Multi-angle renders:** scripted camera orbit per zone (≥8 views incl. ground-contact
   close-ups and robot-eye views from the park pose), GUI walkthrough; **user sign-off gate**
   at asset gallery (C1) and blockout (C2) before physics work continues.
4. **Manipulation feasibility:** scripted procedural rSkills (Phase B stack) actually grasp
   every manipulable and operate every articulation in every covered case, plus MoveIt IK
   check of each grasp pose.
5. **Nav2 check:** costmap shows every static structure; each road segment plannable;
   route-block variants force the loop.

## 9. Implementation phases (each ends with an evidence record + user checkpoint)

| Phase | Output | Gate |
|---|---|---|
| C1 Asset gallery | fetched/converted/authored assets, provenance, turntable renders | user approves look |
| C2 Terrain + blockout | DEM terrain, pads, roads, zone blockout with hero assets, lidar mesh, renders + GUI walkthrough | user approves layout/look |
| C3 Interaction layer (was "articulated infrastructure"; scope correction) | service panels (button + status lamp + cover ledge), spares shelves, staging stand, dynamic spares + cover, interaction frames, work/view poses — **done 2026-09-15, F44** | §8.1–8.2 pass |
| C4 Mission A task | scenario block, verifier truth, scripted runs of all three cases with follow-camera videos — **done 2026-09-16, F45** (§8.5 Nav2 still open, F37) | §8.4–8.5 pass |
| C5 Mission B task | same for B — **done 2026-09-16, F46** (hook grasp on bail handles; §8.5 Nav2 still open) | §8.4–8.5 pass |
| C6 Wrap-up | findings, docs, retire `panel_remount_v2` | full §8 on all variants |

## 10. User decisions (2026-09-15)

1. Terrain: **real LOLA south-pole DEM (Connecting Ridge) + procedural cm-scale detail**, graded pads.
2. Core size: **compact ≈50 × 50 m**.
3. Nav2 visibility: **bake terrain + static structure exteriors into the single lidar mesh**; no RayCaster patch.
4. Gap assets (VSAT-style mast, PDU, racks, cradle, comm cabinet, dock): **authored by us in Blender** (CC0, articulated).
