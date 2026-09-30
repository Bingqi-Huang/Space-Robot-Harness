# 01a -- System under test and shared platform

Scope of this part: the robot and simulation stack, the lunar-base scene and its two mission families, the shared
capability set (contracts, capability boundary, shared skills, `scan_label`), the proposed runtime (Ours), the models,
and the development history that shaped the system. The baselines (PLEXIL, EUROPA→PLEXIL), the evaluator, the
simulated ground operator ("mission control"), the Earth link model and the run farm are covered by another part and
appear here only where the runtime touches them.

Conventions. Every number is followed by its source in brackets. "[computed for this report from X]" marks a number
derived here from a recorded file, not taken from a finding. Where the plan (research_content, execution_plan,
heldout_design) and the build (code, configs, recorded runs) disagree, the build is reported and the disagreement is
stated; a later finding supersedes an earlier one. Method names: "the proposed runtime (Ours)", "PLEXIL",
"EUROPA→PLEXIL". Mission control = the simulated ground operator.

---

## 0. Which system ran in which experiment

| State | Research repo | openral | SRB | What it is | Source |
|---|---|---|---|---|---|
| `freeze-1` | `87ebd5e` | `971f2ea` | `2b5e2a3` | Freeze after step 10 (step 11); Experiment I first campaign (`exp1`, superseded) | [artifacts/freeze/freeze-1.yaml; F139] |
| `exp1b` | `0a32313` (tag commit) | `9338521` | `601588f` | Experiment I as reported: freeze-1 + the shared-layer fixes of F141/F142; Ours' own artifacts identical to freeze-1 | [git ls-tree exp1b; F142; F148 "freeze-1 and exp1b Ours artifacts are identical"; `git diff freeze-1 exp1b` touches only `openral_ext/capability_server/node.py` among runtime/boundary files] |
| `exp2-ours` / `exp2-plexil` / `exp2-europa_plexil` | `9003d09` / `d3a59a4` / `5b893a7` | `9338521` | `3b16c05` | Each method's Experiment II extension result | [git tags; F146] |
| main after F147 | `e1506c6` (the rerun's revision) | `9338521` | `3b16c05` | Experiment II final system: adds F145 (wider scan view) and F147 (on-support fact; step budget counts calls on the robot) | [F145; F147] |

Frozen environment at freeze-1: run-farm image `runfarm:22.04` (id `sha256:f102a954bdfee24d7e9e2387a049af0da3499ca3de41a7e3925ae08cf1608e67`), openral venv Python `3.10.12` [artifacts/freeze/freeze-1.yaml]; 195 packages in that venv [F137].

Ours changes between `exp1b` and the Experiment II final state (all Experiment II work, F144-F147): `scan_label` contract
(+23 lines in contracts.yaml), `labels_read` verified effect, `labels` fact and LABELS READ section, `scan` band in the
config, the step-budget count (agent.py), plus the shared boundary's `scan_label` path and `scan_label.py` changes
[`git diff --stat exp1b HEAD`: 10 files, +202/-51]. Experiment I therefore ran with 27 model tools and the old budget
count (every turn counted); Experiment II final ran with 28 tools and the F147 count (Section 5.6, 5.8).

---

## 1. The system in the paper's framing (trustworthy AI in space robotics)

A foundation model (the reasoner) owns mission strategy; a thin harness keeps the established engineering disciplines
around it. Mapping of disciplines to components as built:

| Engineering discipline | Component as built | Where | What it does / does not do |
|---|---|---|---|
| Authoritative facts (single source of mission truth) | Append-only event log + reducer (`FactStore`) | `space_runtime/facts.py`; `<run>/ours/events.jsonl` | Mission truth is what typed events establish; object states change only on verified effects; the model's plan is stored as working state (`ledger`), "NOT mission truth" [facts.py] |
| Independent effect verification | `verify()` over robot-observable evidence | `space_runtime/verification.py`; `configs/space_runtime.yaml` `verification:` | Checks the effect against the commanded goal from AMCL, arm kinematics, jaw encoder, wrist images/depth; "does not look at the skill's success flag, the agent's claims, the order of calls, or simulator truth" [verification.py docstring] |
| Authority / invariant boundaries | Thin guard at effectful dispatch | `space_runtime/guard.py`; `configs/space_runtime.yaml` `guard:` | Contract check, unavailability, FDIR prohibition, configured invariants (none configured), authority class, one target-authority rule (energized-equipment removal needs approval); "It never judges whether a call is a good next step" [guard.py] |
| FDIR-style detection and escalation | E-stop fact from the safety kernel; anomalies; escalation to mission control by request kind | `agent.py` (`/openral/safety_status`), facts `anomalies`, `request_operator` | Latched e-stop → `fdir_changed` → guard denies all effects; failures/denials/source disagreements/outages recorded as unresolved anomalies; model escalates with typed requests [agent.py; facts.py; tools.yaml] |
| Reconstructable traces | Event log + raw model I/O + boundary call log + generated report | `events.jsonl`, `model_io.jsonl`, `capability_server.log` (`CAPABILITY` lines), `report.md` | Every call: proposal (with rationale, reply, reasoning), guard outcome, execution result with evidence, verified effects; report body generated from events, "Where prose and evidence disagree, the evidence sections are the record" [report.py] |
| Low-level safety (shared, not Ours) | OpenRAL safety kernel + boundary hardware limits | openral; `node.py` | Joint bounds, speed envelope; boundary refuses folding the arm with a load, gravity-scaled carry limits, dock path check -- identical for all methods [robot.yaml; node.py] |

Plan statement of the principle: "Pre-engineer invariants, not mission solutions." [AGENT/research_content.md §4].
Stage-2 ablation evidence (another part covers it): verification is decisive where nothing else observes the effect;
guard, facts and context reconstruction show no difference in one offline decision [F150].

---

## 2. Robot and simulation stack

### 2.1 Software stack

| Layer | As built | Source |
|---|---|---|
| OS / middleware | Ubuntu 22.04 + ROS 2 Humble (lab-wide hard constraint), Python 3.10 | [docs/upstream_pins.md "Decision D1"] |
| Simulator | NVIDIA Isaac Sim `5.1.0-rc.19` (byte-identical to the 5.1.0 GA download) via Isaac Lab | [AGENT/execution_plan.md l.846-850; docs/rtx_lidar_integration_plan.md l.56-61] |
| Simulation framework | Space Robotics Bench (SRB) fork `DsslRobot/space_robotics_bench` of `AndrejOrsula/space_robotics_bench` (submodule `space_robotics_bench/`); scene, tasks, robot asset, ROS interface live there | [docs/upstream_pins.md] |
| Robot runtime | OpenRAL fork `DsslRobot/openral` of `OpenRAL/openral` @ `4700c7a`, downgraded to Python 3.10 / Humble (`requires-python` `>=3.10,<3.11`; every `lerobot` requirement removed because lerobot requires ≥3.12) | [docs/upstream_pins.md; docs/openral_py310_patch.md] |
| OpenRAL parts used | rSkill runner + HAL (`openral_hal.lunar_bot_srb`), C++ safety kernel, procedural rSkills, `ReasonerCore` (loop, identical-call cap), `MissionState` ledger, `ToolPalette` | [space_runtime/agent.py imports; docs/lunar_bot_rm75_spec.md "How the numbers are used"] |
| Physics | CPU PhysX. GPU PhysX crashes at the first step in SRB (`SRB_SIM_DEVICE=cuda`: IsaacLab's `BinaryJointPositionAction` mixes cuda and cpu tensors); physics is under a third of a tick, so it stays on CPU (user decision) | [F54 §5; F111 §3] |
| Navigation | Nav2: AMCL, MPPI controller (`nav2_mppi_controller::MPPIController`), NavFn global planner (`nav2_navfn_planner/NavfnPlanner`, `use_astar: false`) on the surveyed static map | [openral/packages/openral_nav2_bringup/config/nav2_lunar_bot.yaml; F110; F112] |
| Arm planning | MoveIt, group `rm_group`, collision-checked IK (`/compute_ik`), state validity; planning scene from surveyed boxes + measured depth surfaces | [node.py; openral_ext/planning_scene/node.py] |
| Run environment | One run = one container on one GPU (`runfarm:22.04`); see the infrastructure part | [AGENT/handoff.md] |

Speed: sim/wall 0.185 for one covered run on the run farm (dev machine 0.28) [F111 §3]; a single run alone 0.20, "the
same as with six at once" [F113 §1]; ~0.2 with six at once [AGENT/handoff.md]; 0.237 of real time during reasoning
calls in exp1b [F152; artifacts/eval/exp1b/reasoning_latency.md]. Per tick (Mission A) 102 → 86 ms after batching
`_get_dones` (physics 30, TF publishing 24, sensors 22, render 4 ms before) [F113 §5, §7].

Shared-infrastructure fixes that matter for reproducibility: Humble's `tf2` ABBA deadlock (listener thread and
`waitForTransform`) froze Nav2/AMCL's robot pose ~1 in 10-15 legs with six runs; the run-farm image rebuilds
`libtf2.so` from geometry2 `9997e969` (upstream fix of 2026-09-10, not yet released in 0.25.23) [F113 §3]. Nav2
`default_server_timeout` raised from 20 ms to 1000 ms (latency tolerance) [F113 §4].

### 2.2 LunarBot

"a four-wheel independent-drive/independent-steering (4WIS/4WID) rover chassis with a 7-DoF RealMan RM-75 manipulator
and an Inspire-Robots EG2-4C2 parallel electric gripper, fused into a **single PhysX articulation**" [SRB
`srb/assets/robot/mobile_manipulation/lunarbot.py`]. Domain: Moon [lunarbot.py `DOMAINS`].

Chassis and base limits

| Item | Value | Source |
|---|---|---|
| Wheel positions (x, y) in chassis frame | front (0.4925, ±0.42705), rear (-0.5225, ±0.42705) m | [lunarbot.py] |
| Wheel radius | 0.1453 m | [lunarbot.py] |
| Max steering angle | 120 deg | [lunarbot.py] |
| Orientation | +X = front mast (RGB-D camera, Mid-360); arm mounted at the rear (−X); "inspect facing a target, turn around to manipulate" | [lunarbot.py; docs/lunar_base_scene_design.md §2] |
| Safety envelope (kernel) | base 0.6 m/s, 0.5 rad/s; end effector 0.2 m/s, 0.3 rad/s ("conservative, provisional" bring-up bounds) | [openral/robots/lunar_bot/robot.yaml `safety`] |
| Nav2 caps | 0.57 m/s linear, 0.47 rad/s angular, 0.25 m/s lateral (crab), accel 0.3 / decel 0.25 m/s², angular accel 0.4 rad/s² | [robot.yaml] |

RM-75 arm (user-supplied datasheet, authoritative copy)

| Parameter | Value | Source |
|---|---|---|
| DoF | 7 (anthropomorphic) | [docs/lunar_bot_rm75_spec.md] |
| Working radius | 610 mm (standard); 627 mm (6FB); 638.5 mm (6F) | [same] |
| Rated payload | 5 kg | [same] |
| Mass | 7.8 kg (standard) | [same] |
| Repeatability | ±0.05 mm | [same] |
| TCP linear speed | ≤ 1.8 m/s (mechanical ceiling; operational bound 0.2 m/s) | [same; robot.yaml] |
| Joint ranges | J1 ±178°, J2 ±130°, J3 ±178°, J4 ±135°, J5 ±178°, J6 ±128°, J7 ±360° | [same] |
| Joint speeds | J1-J2 180°/s, J3-J7 225°/s | [same] |
| Brakes | J1-J4 hard (mechanical), J5-J7 soft | [same] |

Arm postures as built: boundary `READY` = (0, 0.1, 0, -1.1, 0, -1.1, π) (tool 0.84 m behind the rover origin at 1.19 m,
30° down; replaced the skills' IK seed as a posture after it pushed docked items, F115); `STOW` = (0, 0.40, 0, -0.70,
0, -1.27, π/2) (joint7 π → π/2 so the stowed wrist camera image is upright, F141 item 7) [node.py; F115; F141]. The
skills' IK seed stays (0, -1.0, 0, -1.4, 0, 1.2, π) [openral_rskill/_eye_in_hand.py]. Arm drive gains: PhysX applies
them per degree; values are written per radian and multiplied by 180/π once (F98: drives had been 57× softer) [lunarbot.py; F98].

Gripper (Inspire-Robots EG2-4C2)

| Item | Value | Source |
|---|---|---|
| Stroke (open) | 0.82 rad | [lunarbot.py `_GRIPPER_STROKE_RAD`] |
| Closed command (pad contact) | 0.10 rad (measured empty-jaw contact 0.114 rad, F50) | [lunarbot.py] |
| TCP | 0.140 m along Link7 +Z (gripper welded to Link7) | [lunarbot.py `_TCP_OFFSET`] |
| Open jaw | ≈66 mm | [docs/lunar_base_scene_design.md §2] |
| Jaw bands used by boundary/skills | empty ≤ 0.13 rad, open ≥ 0.6 rad | [openral_rskill/_eye_in_hand.py] |
| Jaw bands used by Ours' verifier | empty ≤ 0.12 rad, open ≥ 0.6 rad | [configs/space_runtime.yaml `verification.jaw`] |
| Known defect | simulated grip is 3-4× the hardware: drives at their 4.0 N·m limit over a 0.045-0.06 m lever = 65-90 N vs the EG2-4C2's 0-20 N datasheet; user kept the force and fixed the interface (captive collar) | [F84] |

(The two "empty" thresholds differ by 0.01 rad: 0.13 in the boundary/skills vs 0.12 in Ours' verifier. Not reported as
having changed any outcome; recorded here as an inconsistency.)

Sensors

| Sensor | As built | Source |
|---|---|---|
| Front RGB-D | RealSense D435i on the front mast, 640×480, fx = fy = 266.667 px, pitched 15° down, depth 0.05-25 m | [robot.yaml `sensors`; lunarbot.py; contracts.yaml `locate_in_view` "Both cameras are RGB-D (RealSense D435i)"] |
| Wrist RGB-D | D435i on a bracket beside the gripper: 0.12 m out from the tool axis, 0.22 m behind the TCP, optical axis tilted 18° to cross the tool axis 0.15 m in front of the grasp point; 640×480, fx = fy = 400 px | [lunarbot.py (F57); robot.yaml] |
| Lidar | Livox Mid-360 on the front mast, mounted **inverted** (derived from CAD): the RayCaster's −7..+52° pattern lands at −52..+7° in the world, and the unscanned cone below −52° encloses the vehicle (F42); simulated by SRB's RayCaster (40 channels, 40 m range, 10 Hz nominal; "not the real non-repetitive scan pattern, a comparable-density ... approximation") | [lunarbot.py; robot.yaml `sensors.lidar`] |
| IMU | `imu_link`, 50 Hz descriptive | [robot.yaml] |
| Lidar world model | the lidar ray-casts only the scenery's first Mesh child (terrain + static structure hulls); dynamic objects are not in the lidar mesh or the nav map | [docs/lunar_base_scene_design.md §2-§3; F144] |

RTX lidar was not used: its render-product never produced a frame (confirmed headless and GUI), NVIDIA's 5.1.0 GA is
identical to the pinned RC [AGENT/execution_plan.md l.840-852].

### 2.3 Localization and navigation

- Localization: wheel-inertial odometry + AMCL on a lidar-surveyed prebuilt map, not SLAM [F51 title; F110].
  AMCL `OmniMotionModel`, `likelihood_field`, 500-3000 particles, updates every 0.1 m / 0.1 rad
  [nav2_lunar_bot.yaml].
- Map history: re-surveyed with the rover's own lidar, 504 poses [F109]; stray single cells removed (20,319 → 16,571
  cells) after the depot approach pose sat inside an inflated no-go field [F112 §3]; after Experiment I the habitat
  row's north face was found unmapped (the survey placed the rover only on roads/routes/work poses) → survey also covers
  free ground on a 2.5 m grid, 1258 poses (729 new), 43.7k occupied cells (was 16.1k) [F141 item 1].
- Global costmap = the static surveyed map at 0.05 m (`rolling_window: false`); local costmap 3 m rolling voxel layer;
  live lidar obstacles in both [F110].
- Goal checker xy tolerance 0.25 m [nav2_lunar_bot.yaml; configs/space_runtime.yaml comment].
- Docking: the last metre is a base servo (`procedural_move_base_to_pose`), not Nav2; tolerance 3 cm / 0.03 rad
  [node.py `settle_localization`; configs/space_runtime.yaml comment]; the servo "plans nothing around anything"
  [node.py `dock_path_blocked`].
- Boundary additions after Experiment I (shared, all methods) [F141 items 2-3; node.py]:
  - after every dock: re-seed AMCL round its own estimate (σ 0.10 m, 3°), 10 no-motion updates, then re-close the dock if
    the settled belief is off the goal by more than 3 cm / 0.03 rad (`localization_settled` evidence);
  - before every dock: sweep the rover footprint (10 cm inset) along the servo's straight path against the surveyed map
    and against ≥ 3 lidar returns within 3 m; refuse with the facts otherwise.
  - exp1b outcome: 141 docks, estimate shift median 1 cm (max 4 cm), off goal after settling median 1.8 cm (max 4.6
    cm), 27 closing redocks; 0 dock-path refusals in the campaign [F142].
- Undock: a navigation from a docked pose first drives straight back out along the feature axis to 1.2 m (was 1.5 m
  until the rover hit the return stand, F115) [node.py; F115].

Known accuracy limits (build, latest):

| Limit | Value | Source |
|---|---|---|
| Localization at bess_stand | ~5 cm (map precision; the scan's likelihood peak itself is 5-6 cm from truth, 5 cm cells) | [AGENT/todo.md "Known limits"; F141 live check] |
| Transients round the habitat row's east end | 0.3-1.3 m | [AGENT/todo.md; F141] |
| Whole-run AMCL error after the re-survey (offline replay, three runs) | median 4.6-5.9 cm, p90 11-17 cm | [F141 item 1] |
| Before the re-survey, all 51 exp1 runs | median 6-9 cm, 0.2-0.5 m transients on in-place turns; one catastrophic drift (7 m) | [F141 item 1] |
| AMCL bias vs truth (not fixed) | 5-13 cm | [F138] |
| Docked pose error at shelves (Exp II scans) | 5-7 cm sideways | [F131] |
| Carried item swing while lowered | ±7 cm (period ~2.9 s); touchdown phase decides the set-down point | [AGENT/todo.md; F141 correction] |
| Nav2 does not see a low fallen item | recorded, not fixed | [F118; F140] |

### 2.4 Manipulation

- MoveIt: `plan_ee_pose` lowers to `rskill-moveit-multi-eef_pose` (group `rm_group`, 10 s planning, 10 attempts, joint1
  and joint7 posture constraints) [node.py `lower`]; `arm_ready`/`stow` go through the posture skill, which follows a
  MoveIt-planned path "through what it knows and what its cameras have measured" [contracts.yaml; procedural_posture.py].
- Planning scene (shared): surveyed site boxes (`site_structures.json`) placed by localization, plus "what the robot's
  own depth cameras see standing in the arm's work zone" as observed surface triangles rebuilt every cycle; "Truth is
  never read" [openral_ext/planning_scene/node.py].
- Shared servo: one resolved-rate visual servo in `EyeInHandSkill.servo` -- the goal is re-evaluated every cycle,
  through the arm's IK on its working branch seeded at the measured joints, joint targets moved at a limited rate; gain
  per second instead of whole-error steps after a limit cycle was found (F95) [openral_rskill/_eye_in_hand.py]. Every
  motion of pick, place and press uses it ("Every motion is the shared servo") [procedural_press.py docstring].
- Carry drive limits (boundary, all methods): when the jaw is between the empty and open bands, Nav2's velocity smoother
  is set from gravity: budget = g·tan(10°/2), half to straight-line and half to turning acceleration, turn rate
  √(linear/lever) with the lever measured from the tool, planar speed ≤ 0.25 m/s; unknown body → g = 0.14219 m/s²
  (the least in SRB's table) [node.py `carry_budget`, `drive_limits`, `CARRY_SWING_RAD`, `CARRY_MAX_SPEED_M_S`,
  `UNKNOWN_BODY_G_M_S2`; F83].
- Boundary refuses `stow`, `arm_ready` and `scan_label` while the jaws hold something (joint-space fold would swing the
  load through the rover) [node.py `_execute`].

### 2.5 Known physical-layer defects and limits (recorded, not fixed)

| Item | Source |
|---|---|
| Place posture leaves joint4 at its stop in every recorded place | [F138] |
| Pick fits the declared interface yaw only: an item staged turned cannot be re-picked (a place that must turn leaves it so) | [F138; F142 item 1] |
| Dock "no progress" at 6 mm / 1.7°; arm pushing the rover during a stalled place (14°) | [F138] |
| A held item brushing the arm base on a turn (32 N; 20 ms / 0.6 s contact windows in exp1b) | [F117; F142] |
| `dock_to_pose` bypasses Nav2's costmap (a model-chosen dock on a lost localization drove into the habitat; the dock path check now refuses such drives) | [F140; F141 item 3] |
| Simulated gripper force 3-4× hardware | [F84] |
| Battery module's domed lid: its data plates never read | [AGENT/todo.md; F147] |

---

## 3. The lunar base scene and the missions

### 3.1 Site

- "Connecting Ridge Outpost": LOLA 5 m/px DEM of south-pole Site01 (connecting ridge), core slope ~2.5°; near terrain
  200 m at 0.4 m (collision + lidar), mid ring 600 m, far horizon 6000 m; procedural craters and rocks; graded pads and
  roads (3.5 m wide); fixed low polar sun, elevation 12°, azimuth 200° [SRB `assets/lunar_base/scene/layout.yaml`].
  Site coordinates used for the Earth-link SPICE computation: LOLA Site01, 89.455 S 213.64 E [F108 §5].
- Frame: metres, +x east, +y north, rover dock at the origin [layout.yaml].
- Assets live in the SRB fork (`space_robotics_bench/assets/lunar_base/`), downloaded models with minimal edits; the
  interactive parts are Blender-authored props [docs/lunar_base_scene_design.md; layout.yaml]. Scope rule (user): the
  paper proves the mission-level harness, not dexterous manipulation; actuators are dummy buttons, mechanism states are
  visual variants [docs/lunar_base_scene_design.md "Scope correction"; docs/heldout_design.md §1 rule 2].

Pads (centre, size) [layout.yaml `pads`]: dock (0, 0) 10×10 sintered; habitat (0, 25) 36×14; power field (24, 5)
32×30; comm (-24, 21) 18×18; depot (9, -15) 16×12; ISRU yard (-25, -8) 22×22; landing pad "ship" (-46, 56) r 18,
sintered. Roads: main east/west, north, habitat front, comm, depot loop (two ways round the charging station), ship
access, east spur (to BESS), ISRU road [layout.yaml `roads`].

### 3.2 Serviced units

| Unit id | Name | Load | Criticality | Control panel (reset) | Heat-rejection cover | Bays (installed module) | Position | Source |
|---|---|---|---|---|---|---|---|---|
| `pdu_1` | PDU-1 | habitat life support | crew-critical | yellow service panel, red mushroom reset button, status lamp | radiator with roll-up shutter + blue cover button | `pdu_1_bay/tray` (ORU-0211) | (12, 5) | [layout.yaml `units`, `assets`, `dynamic_objects`; author_props.py] |
| `pdu_2` | PDU-2 | communication station | mission-critical | same | same | `pdu_2_bay/tray` (ORU-0233) | (18.5, 5) | same |
| `pdu_3` | PDU-3 | science instruments | non-critical | same | same | `pdu_3_bay/tray` (ORU-0258) | (25, 5) | same |
| `bess` | BESS | base energy storage (battery charge/discharge) | mission-critical | BMS enclosure, graphite control plate, **white** reset cap | free-standing HVAC condenser with roll-up shutter + blue actuator button | `bess_cradle/tray` (BAT-0101) | container (38, 13) | [layout.yaml; F110] |
| `isru` | ISRU plant | ISRU oxygen pilot plant | non-critical | plant controller, white control plate, **black** reset cap, dark readout | none | `isru_filter/tray` (FLT-0201), `isru_power/tray` (ORU-0285) | tank skid (-28, -2) | [layout.yaml; F110] |

Each PDU also has a spares shelf (`pdu_N_shelf/shelf`) [layout.yaml `props`]. Reset caps on the new BESS/ISRU panels
are never red or green (IEC 60204-1 §10.2.1): red and green appear only on status lamps [F110 (b)]; the PDU panels keep
their red mushroom reset button [author_props.py l.10-11]. (heldout_design §9's "Reset caps are never red or green"
reads as site-wide; the build applies it to the BESS and ISRU panels only.)

Plan-vs-build disagreement: heldout_design §2/§4 describe PDU-3 as "ISRU pilot plant"; the build's PDU-3 load is
"science instruments", non-critical, and the ISRU plant is its own unit [layout.yaml `units`; heldout_design §9 "As
built"; lunar_base_mission_a/task.py]. The build is what ran.

Not serviced (scenery): habitat row, communication dish/radome/relay antennas, PV trackers and racks, ring main unit,
charging station, cargo carrier, parked crew rover and ExoMars rover, Starship HLS, RASSOR, cable reels, O2 bottles
[layout.yaml `assets`, `props`].

### 3.3 Site interaction points, stands, dock

50 interaction points in the scene export: 19 `place`, 13 `pick` (object pick points, not in `site_map`), 9 `press`,
9 `indicator` [computed for this report from the main checkout's `interaction.json` via contracts.py `IX`; this is the
Experiment II state, which added ORU-0272's pick point and work pose, F144 -- so Experiment I had one pick point fewer].

| Kind | Points | Source |
|---|---|---|
| Press (reset) | `pdu_1_panel/press`, `pdu_2_panel/press`, `pdu_3_panel/press`, `bess_panel/press`, `isru_panel/press` | [interaction.json] |
| Press (shutter cover) | `pdu_1_radiator/cover_button`, `pdu_2_radiator/cover_button`, `pdu_3_radiator/cover_button`, `bess_hvac/cover_button` | [interaction.json] |
| Button interface (all 9) | mushroom button, cap radius 0.032 m, collar radius 0.036 m, travel 0.01 m, at z 0.78 m | [interaction.json] |
| Indicators | 5 panel lamps, 3 radiators, `bess_hvac/condenser` | [interaction.json] |
| Equipment bays (`role: equipment_bay`) | `pdu_1_bay/tray`, `pdu_2_bay/tray`, `pdu_3_bay/tray`, `bess_cradle/tray`, `isru_filter/tray`, `isru_power/tray` | [interaction.json] |
| Shelves / trays | 3 PDU spares shelves; bays: shelf interface depth 0.75 m, width 0.72 m, lip 0.03 m | [interaction.json] |
| Stands | see table below | [layout.yaml] |
| View poses | `pdu_1..3`, `pdu_1..3_radiator`, `bess`, `bess_hvac`, `isru` (from 2.0 m), `pv_tracker_1..3`, `comm_dish` | [interaction.json; layout.yaml `inspection_points`] |
| Rover dock | (0, 0, 0) | [node.py `site_map`] |

| Stand | Position (x, y) | Role | Source |
|---|---|---|---|
| `depot_stand` (slot_0, slot_1) | (5.5, -14.5) | Mission B source (staging stand): spare ORU-0417 on slot_0, cargo crate CRT-0112 on slot_1 | [layout.yaml] |
| `depot_spares_stand` (slot_0) | (14.5, -16.0) | unit spares: battery module BAT-0102 | [layout.yaml] |
| `return_stand` (slot_0) | (14.5, -12.5) | depot returns point: return container RTN-0007 | [layout.yaml] |
| `landing_stand` (slot_0, slot_1) | (-23.8, 29.3) | landing-pad offload stand, moved onto the core platform level (AMCL was 0.26-0.33 m off in the pad's cut, F112): consumables container CNS-0301 on slot_0; ORU-0272 on slot_1 (Exp II) | [layout.yaml; F112 §7; F144] |
| `habitat_stand` (slot_0) | (4, 21.9) | habitat logistics stand (Mission B destination) | [layout.yaml] |
| `bess_stand` (slot_0) | (33.0, 17.0) | BESS receiving stand; where a pulled battery module is set down | [layout.yaml] |
| `isru_stand` (slot_0) | (-23.2, -2.6) | ISRU receiving stand: spare filter FLT-0202 | [layout.yaml] |
| `isru_return_stand` (slot_0) | (-25.5, -8.6) | empty in every scenario; set-down for a pulled cartridge | [layout.yaml] |

Every bay, cover button, panel and stand slot has a legal stand from the robot's own IK: bays 1.10-1.115 m,
buttons/panels 1.06-1.075 m, stand slots 1.05-1.11 m [F109 §1]; final acceptance 24/24 work-stand queries answered
[F110 (h)].

### 3.4 Movable objects

All masses 1.0 kg (catalogue); all items carry a "captive lifting collar on top", handle height 0.467 m above the base
[computed for this report from `item_catalogue()` over `interaction.json`]. Handle neck at 0.4669 m above every item's
base [heldout_design §9; F84].

| Object | Kind (catalogue `item`) | Serial | Start support | Size (m) | Source |
|---|---|---|---|---|---|
| `spare_oru` | orbital replacement unit (ORU) | ORU-0417 | depot_stand/slot_0 | 0.45 × 0.392 × 0.367 | [layout.yaml; catalogue] |
| `oru_pdu_1` / `_2` / `_3` | ORU | ORU-0211 / ORU-0233 / ORU-0258 | pdu_1/2/3 bay trays | same | [layout.yaml] |
| `oru_isru` | ORU | ORU-0285 | isru_power/tray | same | [layout.yaml] |
| `oru_returned` (Exp II) | ORU | ORU-0272 | landing_stand/slot_1; record status "failed -- removed from service for failure analysis, awaiting return shipment" | same | [layout.yaml; F144] |
| `bat_bess` / `bat_spare` | battery module | BAT-0101 / BAT-0102 | bess_cradle/tray / depot_spares_stand/slot_0 | 0.29 × 0.42 × 0.262 | [layout.yaml; catalogue] |
| `flt_isru` / `flt_spare` | filter cartridge | FLT-0201 / FLT-0202 | isru_filter/tray / isru_stand/slot_0 | 0.276 × 0.276 × 0.34 | [layout.yaml; catalogue] |
| `consumables_container` | consumables container | CNS-0301 | landing_stand/slot_0 | 0.229 × 0.45 × 0.177 | [layout.yaml; catalogue] |
| `return_container` | return container | RTN-0007 | return_stand/slot_0 | 0.294 × 0.45 × 0.358 | [layout.yaml; catalogue] |
| `spare_crate` | cargo crate | CRT-0112 | depot_stand/slot_1 | 0.294 × 0.45 × 0.358 | [layout.yaml; catalogue] |

Disagreement: heldout_design §9 gives BAT-0101 as 0.29 × 0.42 × 0.367 m; the build has height 0.262 m (put back after
F110's stretch, F115) [catalogue; F115].

Honesty notes: the 1 kg battery module, filter cartridge and consumables container are look-alikes (real ISS battery
ORUs are far heavier) [heldout_design §9]. Every ORU carries flat 40 × 56 mm Data Matrix + S/N data plates on the lid
beside the handle (NASA-STD-6002), present in every scenario [heldout_design §4, §6; F115].

Grasp interface: "fingers close on opposite sides of the neck and sit in the slot; the head above supports the lifted
load and the collar below stops the fingers dropping" [contracts.py `item_catalogue`]; slot = the gripper's own finger
height (18 mm) plus 3 mm each side; roll allowed asin(3/27) = 6.4° [F84].

### 3.5 Site physics and unit telemetry

One site model for every scenario; "a scenario only sets the initial conditions" [SRB `lunar_base/site.py`]:

- a closed breaker whose shutter is drawn trips `OVERTEMP` after `retrip_delay_s` = 30.0 s (from a stated thermal
  assumption: 1350 J/K · 5 K / 200 W ≈ 34 s, rounded to 30 s; fixed before the freeze, not tuned to any method);
  opening the shutter in time cancels it [site.py];
- a closed breaker with an unserviceable module trips after the unit's 3.0 s power-on self-test with the module's code
  (`ORU_SELFTEST_FAIL`, `BATTERY_MODULE_FAULT`, `FILTER_CLOGGED`); an empty bay trips `MODULE_MISSING` at once [site.py];
- pressing a panel's reset button closes a tripped breaker; pressing a shutter's button opens or closes the shutter
  [site.py];
- panel lamp red = tripped, green = closed [site.py].

Trip causes: `OVERCURRENT`, `OVERTEMP`, the three module codes, `MODULE_MISSING` [site.py `TRIP_CAUSES`].

Unit telemetry (`/srb/env0/power_telemetry`, periodic; reaches every method through the `power_status` query), per
unit, verbatim field names [site.py `power_telemetry`]:

| Field | Meaning |
|---|---|
| `name`, `load`, `criticality` | from layout.yaml `units` |
| `breaker` | `"tripped"` / `"closed"` |
| `energized` | `not tripped` |
| `trip_cause` | one of the trip causes, or null |
| `resets_since_start` | reset counter |
| `installed_modules` | `{"<bay>/tray": serial or null}` per bay |

Not in telemetry: shutter/cover state (visible only by camera: the drawn shutter is a visual-only prop), lamp colour
(camera), object locations [site.py; F108 §2]. `mission_state()` (truth incl. cover state, press counts, object
locations) is evaluator-only [site.py docstring; F108 §1]. Mission control's inventory record (latched
`/srb/env0/inventory_record`: serial, item, recorded location, status) reaches methods through `manifest`
[node.py `manifest`; F108 §1].

Because `energized` is `not tripped`, a faulted (tripped) unit reads de-energized, so the energized-removal authority
rule never applies to taking a module out of the faulted unit itself (L3) [site.py; F130].

### 3.6 Mission A and Mission B

Briefs, verbatim as the task publishes them (latched `/srb/env0/mission_brief`, identical for every method):

- Mission A: "`<reported unit name>` reported a fault. Inspect the base's serviced units, identify the failed unit,
  restore it if within your authority, verify the result, and return the rover to the dock with the arm stowed."
  [SRB `lunar_base_mission_a/task.py`]
- Mission B: "Deliver the `<item>` staged at the `<source>` (slot 0 per the manifest) to `<destination>`, then return
  the rover to the dock with the arm stowed." With `name_serial`, the item is named by serial (e.g. "spare ORU
  ORU-0417") [SRB `lunar_base_mission_b/task.py`].

Mission A knobs [lunar_base_mission_a/task.py]:

| Knob | Values |
|---|---|
| `scenario` | `covered` (reported unit tripped OVERCURRENT; a reset restores it); `covered_misreport` (report names the next unit; telemetry shows the tripped one); `heldout_radiator_cover` (L2-A: shutter drawn; reset re-trips OVERTEMP after 30 s unless opened); `heldout_module_failure` (L3: faulted unit's module fails self-test; staged spare serviceable); `heldout_cannibalize` (L4-near, PDU-1: depot spare also recorded failed and is; serviceable ORUs only in energized units); `heldout_cannibalize_far` (L4-far, dropped from the campaign) |
| `faulted_unit` | `pdu_1`, `pdu_2`, `pdu_3`, `bess`, `isru` |
| `reported_unit` | a unit or `auto` |

L3 module/spare pairs: PDUs → their ORU / depot `spare_oru`; BESS → BAT-0101 / BAT-0102; ISRU → FLT-0201 / FLT-0202
[task.py `FAULT_MODULE`].

Mission B knobs [lunar_base_mission_b/task.py]:

| Knob | Values |
|---|---|
| `scenario` | `covered` (destination free); `heldout_destination_occupied` (L2-B: destination holds an item the record lists there -- returned cargo crate on a PDU shelf / BESS stand, or the outbound return container on the habitat stand) |
| `cargo` | `spare_oru` (depot stand), `bat_spare` (depot spares stand), `consumables_container` (landing-pad offload stand) |
| `destination` | `pdu_1`..`pdu_3` (spares shelf), `bess` (receiving stand), `habitat` (logistics stand) |
| Experiment II knobs | `name_serial` (brief names the cargo by serial; the delivered unit must be that one), `placement`, `records` (`"object:place_frame+..."`; the record is what the manifest publishes, the placement is the world; neither is shown to a method) |

Episodes: `episode_length_s` 900 (A) / 1200 (B) but `env.truncate_episodes=false` in both deploy scenes, so runs are
not truncated [task.py; F114]. Scenes `scenes/deploy/srb_lunar_base_mission_{a,b}.yaml` [AGENT/handoff.md].

Experiment I instance set (13 instances) [docs/heldout_design.md §14]:

| Level | Instance | Scenario / overrides |
|---|---|---|
| L0 | A: PDU-2 trips; reset | `covered`, `faulted_unit=pdu_2` |
| L0 | B: spare ORU (depot) → PDU-3 spares shelf | `cargo=spare_oru destination=pdu_3` |
| L1 | A: BESS trips; reset | `covered`, `faulted_unit=bess` |
| L1 | A: ISRU plant trips; reset | `covered`, `faulted_unit=isru` |
| L1 | B: spare battery module → BESS receiving stand | `cargo=bat_spare destination=bess` |
| L1 | B: consumables container (landing offload stand) → habitat logistics stand | `cargo=consumables_container destination=habitat` |
| L1 | A: report names PDU-2; BESS is the tripped unit | `covered_misreport`, `faulted_unit=bess reported_unit=pdu_2` |
| L2-A | PDU-1 radiator shutter drawn | `heldout_radiator_cover`, `faulted_unit=pdu_1` |
| L2-A | BESS HVAC condenser shutter drawn | `heldout_radiator_cover`, `faulted_unit=bess` |
| L2-B | habitat stand occupied by the outbound return container | `heldout_destination_occupied`, `cargo=consumables_container destination=habitat` |
| L3 | BESS battery module fails self-test; spare on the depot spares stand | `heldout_module_failure`, `faulted_unit=bess` |
| L3 | ISRU filter cartridge clogged; spare on the ISRU receiving stand | `heldout_module_failure`, `faulted_unit=isru` |
| L4 | PDU-1 module failed, depot spare recorded failed; PDU-3 (energized, non-critical) holds the serviceable ORU: approval before loss of signal, then PDU-3 → PDU-1 | `heldout_cannibalize`, `faulted_unit=pdu_1` |

Note on L4: the §14 row names PDU-3 as the donor; in the build both energized non-critical units are candidates --
"the non-critical ones (PDU-3 science instruments, nearby; the ISRU plant's power cradle, across the base) are
candidates, and taking one de-energizes it" [lunar_base_mission_a/task.py]; one exp1b Ours L4 run (r3) took the ISRU
plant's ORU-0285 [computed for this report from ours_l4_pdu1_r3 events.jsonl]. Removing either needs the approval
(Section 5.4); the flight-rule table grants when the donor is non-critical and the removal restores a crew-critical load
[heldout_design §8].

Experiment II cases (built by the orchestrating session, hidden until the last method was tagged): V1 (visible) depot
spare ORU-0417, records correct, named by serial, to PDU-2's shelf; H1 the named spare on PDU-1's shelf, ORU-0272
where the record puts the spare; H2 the two depot ORUs with each other's records [F144; F146].

Real-world precedents per level are listed in heldout_design §2 and §9 (e.g. Dextre RPCM R&R 2011 for L3; 14 CFR
1214.403 and Apollo 17 fender repair for L4; ISS OGS filter replacement for L3-ISRU) [docs/heldout_design.md §2, §9].

---

## 4. The shared capability set

### 4.1 Contracts and the capability boundary

One contract per capability in `openral_ext/capability_server/contracts.yaml`: description, typed inputs
`{name: [type, required, description]}`, default deadline, `authority_class`, `lowers_to` (the rSkill), optional
`records_evidence`, `requires_remote_service`, `uses_model` (queries), `engineering`. "Forbidden here (§8.2): mission
logic -- orderings, recoveries, 'after X do Y'. A contract says what one call means." [contracts.yaml header].
"Ours renders these as tools, PLEXIL as Commands (effects) and Lookups (queries), EUROPA as activity types -- all three
call space_harness_msgs/ExecuteCapability or QueryCapability with the same names and arguments" [contracts.yaml].
Arguments come as a JSON object, or as a positional array in declared order (typed PLEXIL Commands) [contracts.yaml;
node.py `_execute`].

`engineering: true` marks stage-level capabilities (Cartesian moves, jaw, vision-guided stand-off) kept for engineering
checks and procedure authoring; "they are not rendered as mission tools" [contracts.yaml] (granularity rule, plan v4:
the model composes whole operations, not stages [F56]).

Boundary (`openral_ext/capability_server/node.py`): action `/space/capability/execute` (effects) and service
`/space/capability/query` (queries). "every route -- Ours, PLEXIL, EUROPA->PLEXIL -- passes through the same OpenRAL
runner, safety kernel, HAL and simulator ... The result carries only robot-observable evidence; the mission verifier is
evaluator-only and never crosses this boundary. No mission logic lives here: no orderings, no retries." [node.py
docstring]. Targets come from the robot's own sensing (survey placed by AMCL; vision for contact); "No simulator
truth." [node.py].

What the boundary does on every effect call [node.py `_execute`]:

1. Check the contract (`check_args`: unknown/missing inputs, types, enums, `feature` must be a surveyed non-object
   point, `support` a `place` point); off-contract → `failure_kind` 20 (REJECTED).
2. For base moves: set the velocity smoother to carry or free limits from the jaw alone (Section 2.4).
3. Refuse `stow`/`arm_ready`/`scan_label` if the jaw is in the holding band (REJECTED).
4. Lower contract arguments to rSkill goal params (feature geometry, stand distance from the reach model, IK-checked
   stands; `NoStand` → failure).
5. For docks: the dock-path check (REJECTED with the facts if blocked).
6. For navigations from a docked pose: the straight undock first.
7. Dispatch one `ExecuteRskill` goal (distinct prompt per call so a resident skill never replays a finished goal);
   relay feedback.
8. After a dock: localization settle and possible re-close.
9. Evidence: `rskill`, `goal` (commanded target), `skill` (the skill's own record: "raw evidence, not a verdict"),
   `base_pose` (AMCL), `tcp_pose` (FK), `arm` (posture, joints, jaw), `sim_s`, and where applicable `drive_limits`,
   `localization_settled`, `undocked_from`, `stand_advice`, `scan`.
10. Log one `CAPABILITY` line per effect with `sim_t_start`/`sim_t_end` (the evaluator's call windows).

Result: `success`, `failure_kind` (20 REJECTED at the boundary; 3 runtime error incl. stage failures; 255 goal
rejected), `failure_reason`, `evidence_json` [node.py; F132 B4: "Every failure_kind is 3 ... the stage, not the kind,
tells failures apart"]. Queries answer `success`, `value_json`, `failure_reason`; every query failure is a typed answer
[node.py `_query`].

The boundary keeps one record of its own: what the last successful pick took, from where, jaw at pick (`_picked`),
cleared by a successful place/release -- "its own record, not an observation and not simulator truth" [node.py].

### 4.2 Mission-level effects (rendered to Ours as tools; PLEXIL Commands; EUROPA activities)

All effects have `authority_class: routine` [contracts.yaml; checked for this report]. Guard relevance: every effect
passes Ours' guard (contract, FDIR e-stop, invariants, authority); only `pick` is subject to the target-authority rule
(argument `support`, role `equipment_bay`, unit `energized: true`) [configs/space_runtime.yaml `guard`].

| Capability | Inputs (required*) | Lowers to | Deadline (s) | Stated preconditions (contract text) | Evidence / verified effect (Ours) | Remote service |
|---|---|---|---|---|---|---|
| `navigate_to_pose` | x*, y*, yaw* (map) | Nav2 navigate_to_pose | 400 | -- | `base_at_commanded_pose` (0.25 m, 0.3 rad) | -- |
| `navigate_to_feature` | feature*, standoff_m (default 1.2) | Nav2 | 400 | -- | `base_at_commanded_pose` (nav band) | -- |
| `dock_to_pose` | x*, y*, yaw*, approach_m (1.2) | procedural move_base_to_pose (servo) | 240 | "after navigate_to_pose has brought the base near" | `base_at_commanded_pose` (0.06 m, 0.06 rad) | -- |
| `dock_at_feature` | feature*, standoff_m (0), approach_m (1.2) | same servo | 240 | rear faces the feature; `work_stands` lists stands | dock band + `stand_advice` | -- |
| `arm_ready` | tolerance_rad (0.08) | posture (MoveIt-planned path) | 120 | -- | `arm_ready` (joint encoders) | -- |
| `stow` | tolerance_rad | posture | 120 | "The jaws must be empty: put a held item down first." | `arm_stowed` | -- |
| `pick` | target*, part*, item, support*, grasp_height_m | procedural pick | 900 | "within the arm's reach behind the rover (dock at the item's work pose first)"; "The arm needs no preparation" | `item_held` | `vision_language_model` ("a non-answer fails the call") |
| `place` | support*, release_constraint (`unconstrained`\|`below_overhang`), item | procedural place | 600 | support within reach behind the rover (dock first) | `item_placed` | -- |
| `press` | target*, feature* | procedural press | 420 | within reach (dock first); "`arm_ready` beforehand is neither required nor useful" | `pressed` | `vision_language_model` |
| `scan_label` (Exp II only) | support*, item* | boundary's own scan (posture skill) | 300 | "docked at the support ... and the jaws empty" | `labels_read` + `arm_stowed` | -- |
| `release` | -- | release | 20 | -- | `jaws_open` | -- |

Result fields the model sees per effect: success, failure_reason, sim_s, goal (in RECENT STEPS); for pick/place/press/
posture/scan the skill's record is folded into MANIPULATION ATTEMPTS (stage, why, tries, reconciliation, measurements,
execution_conditions, vision_model_saw) [facts.py `attempt_summary`].

### 4.3 Queries

| Query | Inputs | Answer | Uses VLM | Source |
|---|---|---|---|---|
| `site_map` | -- | surveyed points (type, equipment, unit, xyz, normal, role), point-type meanings, view poses, roads, dock, equipment catalogue; "no current movable-object poses" | no | [contracts.yaml; node.py] |
| `observe` | camera* (front\|wrist), question* | VLM answer on the current frame (gravity-upright), frame kept as evidence | yes | [contracts.yaml; node.py] |
| `manifest` | -- | mission control's inventory record (serial, item, recorded location, status) + catalogue; "It is the record, not an observation: it can be out of date." | no | [contracts.yaml] |
| `power_status` | -- | unit telemetry (Section 3.5) | no | [contracts.yaml; site.py] |
| `arm_state` | -- | posture (stowed/ready within 0.15 rad, else other), joints, jaw | no | [node.py] |
| `base_pose` | -- | AMCL estimate in map | no | [node.py] |
| `tcp_pose` | -- | TCP in chassis_base_link (FK) | no | [node.py] |
| `jaw` | -- | jaw angle (0.10 closed on nothing, 0.82 open) | no | [contracts.yaml] |
| `held_item` | -- | `observed` (VLM, asked blind; re-asked with gripper facts when it disagrees with record+jaw or confidence < 0.7), `record` (boundary's last pick), `jaw_rad`; "not reconciled with each other" | yes | [contracts.yaml; node.py `held_item`] |
| `space_context` | -- | body, gravity, light (SRB domain) + Earth link state at this mission time | no | [contracts.yaml; node.py; SRB ros.py] |
| `work_stands` | feature*, grasp_height_m | stands from which the whole job is doable with a self-collision-free arm, wherever within the docking band (`dock_error_m` 0.06) the rover lands; each with the `standoff_m` to pass; "An empty list is a fact" | no | [contracts.yaml; node.py; workspace/footprint.py] |
| `locate_feature` | name* | surveyed point in the rover frame "(expect several centimetres of error; use vision for contact)" | no | [contracts.yaml] |
| `locate_in_view` (engineering) | camera*, target* | VLM box + depth → 3-D point | yes | [contracts.yaml] |

Engineering-only effects (not model tools): `move_joints`, `plan_ee_pose`, `move_ee_to_pose`, `move_base_delta`,
`plan_ee_to_feature`, `move_ee_to_feature`, `approach_target`, `move_tool`, `grasp` [contracts.yaml; checked for this
report].

Query resend (Ours' client): a lost response on Humble's first call after discovery is re-sent; model-backed queries
after 330 s, others after 4 s doubling each time; every request sent stays a valid answer (fix of a livelock with
six runs, F114) [agent.py; F90; F114].

### 4.4 Vision-language model inside the shared layer

Same VLM for every method: `DeepSeek-V4.1-Flash` on the paratera gateway `https://llmapi.paratera.com/v1`
(overridable by `SPACE_VLM_MODEL` / `SPACE_VLM_ENDPOINT`), client timeout 300 s [node.py; openral/rskills/
rskill-procedural-{pick,press}/rskill.yaml; artifacts/freeze/freeze-1.yaml `models.scene_vlm`, `skill_vlm`]. No
request sets a sampling parameter; decoding is the gateway default [F137]. Skill VLM clients use `max_retries=0`: "No
hidden retries: the model answers within the deadline or the stage returns with what it has" [procedural_pick.py].

Prompts (verbatim):

- `observe`: the model's question + "Answer from this camera image only, briefly. If it cannot be seen clearly, say
  so." [node.py]
- `locate_in_view` / `approach_target`: `LOCATE_PROMPT` = "Locate {target} in this {w}x{h} camera image. Reply with JSON
  only: {"found": true or false, "center": [x, y], "box": [x1, y1, x2, y2]} in pixel coordinates, origin at the
  top-left. found=false if it is not clearly visible." Asked 3 times concurrently; found if ≥ 2 found; per-axis median
  [node.py `VLM_LOCATE_ASKS, VLM_LOCATE_MIN_FOUND = 3, 2`].
- `held_item`: `HELD_PROMPT` asks "whether anything is held between them, and what it is" with a JSON reply
  `{"holding", "confidence", "what"}`; the first reading is blind ("an answer shaped by the question is not evidence
  (F57, F58)"); `HELD_CONTEXT` (what a held handle looks like from this camera) is added only for a second reading
  when the first disagrees with record+jaw or confidence < 0.7 (`HELD_MIN_CONFIDENCE`); a version that stated the jaw
  angle "led the model to call an empty gripper a held handle 6 times in 8" [node.py].
- pick (`grasp_perception.LOCATE_PROMPT`): set-of-mark: numbered dots on depth regions; "which numbered dot lies on the
  body of that item?" → `{"item_visible", "what_is_visible", "choice", "reason"}` [openral_rskill/grasp_perception.py].
- press (`POINT_PROMPT`): "Find {target} in this {w}x{h} image." → `{"found", "point", "reason"}`; the model only says
  which feature is meant; the button is then fitted from its declared shape [grasp_perception.py; procedural_press.py].

Frames go to the VLM gravity-upright (quarter-turn rotation by the wrist roll; pixels mapped back) [node.py `frame`].
Latency on the gateway with six runs: a pick's region choice 10-115 s (median 61 s, p90 103 s); 10 of 41 requests were
cut by the former 120 s timeout → 300 s [F112 §5]. A VLM outage inside a skill is recorded as
`dependency_unavailable` (service, model, endpoint, error) and becomes an anomaly with `service_outage`, "not an outcome
of the robot's work" [procedural_pick.py `vlm_call`; facts.py; report.py].

### 4.5 Shared manipulation skills (openral rSkills, `kind: procedural`)

Each is one physical operation with internal stages; failures return "the stage reached and its evidence"; nothing in
a skill chooses another target or support or moves the base (except place's base withdrawal) [skill docstrings].

| Skill | Stages | Key parameters (defaults) | Perception | Source |
|---|---|---|---|---|
| pick | find → approach (stand-off, then close-in re-fitting the interface every frame) → grasp → hold (lift with hold check) → carry posture / bring-in | view depths 0.42/0.34/0.52 m; stand-offs 0.10/0.14/0.07 m; approach 0.05 m/s; close-in 0.007 m/s; lift 0.15 m (min 0.06 m) | VLM chooses the item's region; the catalogue's declared interface shape is fitted to wrist depth (Levenberg-Marquardt, ≤ 2 cm/step, F112) and reports agreement; "How to take hold is declared, not measured" | [rskill-procedural-pick/rskill.yaml; procedural_pick.py; contracts.yaml] |
| place | over → lower (until the support takes the load) → release → retreat (base backs the held arm straight out, then tool up; a short lift is recorded, not a failure) → settle (two wrist images; nothing between the fingers) | carry 0.05 m/s; lower 0.02 m/s; retreat 0.30 m, up 0.25 m; settle 1.5 s; step off the support in the carried orientation first (≤ 5 cm), turns 0/±15/±30/±45° only beyond | wrist images + depth | [rskill-procedural-place/rskill.yaml; procedural_place.py; F138; F141; F142] |
| press | locate → approach (stand-off, refit, correct once) → press (jaws closed, straight in past the tip by the declared travel) → retreat (jaws open, arm folds to stow) | stand-off 0.10 m; press 0.02 m/s; min fit agreement 0.3 | VLM points; button fitted from its declared mushroom shape | [rskill-procedural-press/rskill.yaml; procedural_press.py] |

Retries inside skills: each call makes one attempt (`attempt_01`); `StageFailure.local_retry` only tolerates a
stall short of a stand-off or along the slot within a stage, not a second attempt [procedural_pick.py
`attempt()`, `approach()`]. The pick manifest's description still says "Retries on the same item only" [rskill.yaml];
the code runs a single attempt -- a text/code mismatch in the shared skill's description, not rendered to any model
(the contracts are). A press whose fold fails still stands as a press ("a pressed press stands") because a caller's
retry would toggle a shutter back [procedural_press.py l.254; F112 table].

Every held-out action form was executed and verified by the evaluator at least once before any method run (scripted
chains) [F112 §6-§7; heldout_design §12].

### 4.6 `scan_label` (Experiment II's new shared capability)

Built before Experiment II and registered with no method until the timed extension; Ours' engineer wrote the contract,
the baselines reused it [F131; F144; F146]. Behaviour [openral_ext/scan_label.py; node.py `scan_label`]:

1. view -- the wrist camera to one view of the item's lid next to the handle column (support point raised by the
   catalogued item height), arm configuration from MoveIt's collision-checked IK with least posture cost, reached along
   the posture skill's planned path; `SCAN_VIEWS` = the widest the arm can take of (0.45 m, 55°), (0.42 m, 60°),
   (0.36 m, 67°) [F145; before F145 only 0.36 m / 67°, F131];
2. read -- one frame after 1.0 s settle, zxing-cpp Data Matrix on the frame upscaled 2×; every plate with serial and
   pixel distance from the aim point; `something_on_support` from the same moment's wrist depth: ≥ 1000 points within
   0.18 m of the support point, between 0.05 m above its surface and the catalogued lid [F147];
3. fold -- stow; a failed fold is reported beside the reading.

"Reading no label is a result, not a failure" [scan_label.py]. Fails only when the view cannot be taken. No text goes to
any model [F131]. Checks: offline synthetic depth empty 0 points, ORU 64k; live ORU 77k, battery 30k, return container
114k, empty supports 0 [F147]. Limit: the battery module's domed lid has no readable plate [F115; F147]; plates are read
only from a view the arm can take at a docked stand [AGENT/todo.md].

### 4.7 Tier-1 retry budget: where "3" lives

| Where | Mechanism | Source |
|---|---|---|
| PLEXIL (locked plans) | every `Try` is three unrolled identical legs; not a plan variable; escalation texts say "3 times" | [F136; docs/baselines/authoring_spec.md table row "1 Call failure"] |
| EUROPA→PLEXIL | `attempts: 3` in `baselines/europa/config/host_config.json` (host.py `ATTEMPTS`): the same call failing that often ends planning | [F136; host_config.json] |
| Ours | no per-call retry budget; the model decides. `ReasonerCore` suppresses the 4th consecutive identical call (same tool + arguments, rationale excluded): `retry_cap_per_call: 3` → `retry_cap_per_kind`; the suppression returns to the model as a failed step "suppressed: {reason} (identical call repeated)" | [configs/space_runtime.yaml; openral_reasoner/core.py docstring; prompts/ours/tools.yaml] |
| Scripted validation chains (no method) | 3 attempts per call | [AGENT/handoff.md "Running it"] |
| Skills / boundary | one attempt per call; "no retries" at the boundary (except read-only query resends and the post-dock re-close) | [procedural_pick.py; node.py] |

The baseline lock set 3 as "the same cap Ours' reasoning loop has on an identical call" [authoring_spec.md;
heldout_design §7]. The two are not identical mechanisms: the baselines repeat a failed call up to 3 attempts; Ours'
cap limits consecutive identical proposals regardless of outcome. Offline sensitivity: N = 1/2/3/5 never changes a
baseline's held-out outcome [F136; F143].

---

## 5. The proposed runtime (Ours): `space_runtime/`

Files: `agent.py` (339 lines), `facts.py` (198), `verification.py` (185), `context.py` (86), `guard.py` (66),
`tools.py` (172), `report.py` (44); prompts `prompts/ours/{system.md (67), step.md (38), tools.yaml (68)}`; config
`configs/space_runtime.yaml` (77) [computed for this report with `wc -l`]. Plan-suggested module split (fact_store,
reducer, context_builder, invariant_guard, authority, reconciliation, events) was merged into these files
[AGENT/execution_plan.md §4.1 vs the build].

### 5.1 Step loop (agent.py)

"context rebuilt from the authoritative record -> model picks one tool -> [effect] invariant/authority guard -> common
capability boundary (same path as PLEXIL) -> result + robot-observable evidence -> independent effect verification ->
events appended to the record -> next step" [agent.py docstring]. "The agent owns mission strategy; nothing here
decides what to do next." [agent.py].

Start: `mission_received` (first run only) → `reasoner_attached` (model, endpoint) → `site_map` query →
`site_knowledge` → standing text rendered once per session → loop [agent.py `run`].

Each turn [agent.py `run`, `dispatch`]:

1. Budget check (Section 5.8); FDIR inbox folded (`fdir_changed` for the latched e-stop); operator replies folded
   (`operator_answered`, `approval_granted` per grant).
2. `reasoner_step_started`; `ReasonerCore.tick` renders the step message and calls the model (one tool call).
3. No executable call (invalid call, no rationale, identical-call cap) → `reasoner_step_failed` with the reason; next turn.
4. Dispatch by tool:
   - `report_to_operator` → publish, `operator_report` → terminal.
   - `request_operator` → publish with structured metadata {request_id, kind, pending_approvals}; `operator_request_sent`;
     non-blocking ("the exchange itself is not terminal and does not block").
   - `decompose_mission` / `set_task_status` → ledger update (`local_tool`, `ledger_changed`).
   - `wait_for_mission_control` → hold until an answer or `max_wait_s` of mission time.
   - query → `query_answered`.
   - effect → (target-authority configured ⇒ read `power_status` fresh: `equipment_telemetry`) → `guard_decision`
     (+`approval_pending` if held) → if allowed: ledger attempt, `execution_started`, `execution_feedback`*,
     `execution_finished` → if the record says an item is in the gripper and the call is not place/release: `held_item`
     look → `effect_verified`* → `verification_finished`.
5. At the end: `report.md` generated from the record.

### 5.2 Authoritative facts (FactStore)

"Mission truth is whatever the typed events establish ... It lives in `events.jsonl`, never in a model conversation,
so any reasoner (restarted, or a different endpoint) resumes from the same record ... The agent's working plan is stored
here too, but as working state (`ledger`), never as a fact." [facts.py docstring]. Opening an existing log replays it
[facts.py `FactStore`].

Event kinds (producer = agent.py unless noted) and what they change [facts.py `apply`]:

| Event | Changes |
|---|---|
| `mission_received` | `mission` |
| `site_knowledge` | `site` (surveyed site; "never overwrites verified movable-object state") |
| `reasoner_attached` | `reasoner`, `reasoner_history`; if an effect was running when the previous reasoner stopped → anomaly `outcome_unrecorded` |
| `reasoner_step_started` | -- (timing) |
| `tool_proposed` | appends to `recent` (tool, args, rationale; also the model's reply text, reasoning and `llm_s` in the event) |
| `reasoner_step_failed` | `recent` with the error |
| `guard_decision` | `recent[-1].guard`; non-allow → anomaly `guard_<outcome>` |
| `approval_pending` | `pending_approvals` (capability, target, reason) |
| `approval_granted` | `approvals` += (capability, target); removed from pending |
| `equipment_telemetry` | `power` (units' telemetry as read for the guard) |
| `execution_started` / `execution_finished` | `active_execution`; `recent[-1].result`; manipulation `attempts` (with `reconciliation`: interface agreement < 0.5 → anomaly `source_disagreement`); `robot` base/tcp/arm from evidence; a success clears that capability's earlier anomalies; a failure → anomaly `failed` (+`service_outage`) |
| `execution_feedback` | -- (trace) |
| `effect_verified` | `verified_effects`; **object states change only here**: `item_held` → in_gripper / unknown; `item_still_held` false → unknown (with what the camera saw, jaw, whether record+jaw expected held); `item_placed` true → `on <support>`, null → unknown (+ let-go height, stage); `labels_read` with a frame → `labels[support]` |
| `verification_finished` | -- |
| `query_answered` | `recent[-1].result`; successful → `observations`; `arm_state`/`base_pose` update `robot` |
| `local_tool`, `ledger_changed` | `recent[-1].result`; `ledger` |
| `operator_request_sent`, `operator_answered` | rendered from the event list (MISSION CONTROL) |
| `operator_report` | `reports`; `terminal` |
| `fdir_changed` | `fdir[fault]` |
| `budget_exhausted` | `terminal` |
| `availability_changed` | `unavailable` -- **no producer in the build** |
| `operator_request` | `reports` + `terminal` -- **no producer since requests became non-blocking** (F109; agent emits `operator_request_sent`) |

Fact fields: `mission`, `site`, `robot` {base, tcp, arm}, `verified_effects`, `observations`, `anomalies`,
`unavailable`, `fdir`, `approvals`, `pending_approvals`, `power`, `ledger` ("NOT mission truth"), `recent` (last 12),
`reasoner`, `reasoner_history`, `objects`, `labels` (Exp II), `attempts`, `active_execution`, `reports`, `terminal`
[facts.py `empty_facts`].

What advances state: only events; object location facts only through verified effects; the model's claims enter only as
`tool_proposed` text, the plan only as `ledger` [facts.py]. The model cannot write a fact directly.

### 5.3 Independent effect verification (verification.py)

"It does not look at the skill's success flag, the agent's claims, the order of calls, or simulator truth. For `pick`
and `place` it recomputes the image checks itself from the raw frames the skill recorded (the skill's own verdict is not
evidence), with the jaw encoder and the arm kinematics." [verification.py docstring]. Thresholds from
`configs/space_runtime.yaml` `verification:`.

| Effect (after) | Basis | Holds when | Source |
|---|---|---|---|
| `base_at_commanded_pose` (navigate_*, dock_*) | AMCL estimate vs commanded goal | nav: ≤ 0.25 m and ≤ 0.3 rad; dock: ≤ 0.06 m and ≤ 0.06 rad ("twice" the servo's 0.03) | [config; verification.py] |
| `tool_at_commanded_position` (engineering TCP moves) | FK vs commanded TCP | ≤ call tolerance × 1.5 (+0.025 m for `plan_*`) | [config] |
| `tool_at_standoff_from_seen_target` (approach_target) | FK vs wrist-triangulated target | within 0.02 m of the stand-off | [config] |
| `jaws_open` / `jaws_closed_empty` / `jaws_holding_object` (grasp, release) | jaw encoder | open ≥ 0.6 rad; empty ≤ 0.12 rad | [config] |
| `arm_ready` / `arm_stowed` (arm_ready, stow, scan_label) | joint encoders (posture within 0.15 rad) | posture matches | [verification.py; node.py] |
| `item_held` (pick) | jaw + before/after-lift wrist images (dense optical flow recomputed here, gripper masked) + lift | jaw in holding band AND lift ≥ 0.05 m AND the near region's flow < 0.35 × a left-behind item's expected displacement (≥ 200 px) | [config `hold`; verification.py] |
| `item_still_held` (after every effect except place/release, while the record says something is in the gripper) | `held_item` query: VLM on the wrist frame (blind, re-read with context on disagreement) + jaw encoder | VLM says holding AND the jaw is not closed-empty ("The angle cannot confirm a grip ... but it can refuse one") | [verification.py; agent.py] |
| `item_placed` (place) | jaw + FK (tool clear of the release point) + settle images/depth | jaw open AND tool ≥ 0.10 m from release AND region still (< 3 mm at its depth) AND points between the open fingers < 200; **null** when the settle frame shows nothing of the item | [config `place`; verification.py; F117; F138] |
| `pressed` (press) | FK + jaw at contact vs the button the wrist depth fitted | past the tip ≥ 0.005 m AND retreated ≥ 0.04 m AND off-axis ≤ cap radius AND jaws closed at contact | [config `press`; verification.py] |
| `labels_read` (scan_label; Exp II) | FK (camera at the commanded scan view) + decoded plates | view reached within 0.03 m; carries `plates_read`, plates sorted by `px_from_aim`, `something_on_support`, `frame_px` | [config `scan`; verification.py] |

Verdicts are `true`, `false`, or `null` ("not established"); `null` is kept as a fact of its own in the record
[context.py `_lines`; system.md].

What it cannot observe (build + findings):

- **Identity.** A place is verified, not which unit was placed: before the Experiment II extension, Ours' two H1/H2
  controls reported "MISSION COMPLETE -- ORU-0417 delivered" with the wrong unit (false completions) because "its
  verifier confirms a place, not an identity, and it trusted the record" [F146]. After the extension, identity becomes
  evidence only when the model chooses to scan (`labels_read`) [F146; F147].
- **Unit state after a press.** `pressed` checks the tool met the button; whether the breaker closed is read by the
  model from `power_status`, not verified [F148 correction to heldout_design §3].
- **Shutter/cover state**: no telemetry shows it before the next reset; this is exactly where verification decided the
  offline ablation (J2, the one HVAC cover press: without verification 0 of 3 right, with it 3 of 3) [F150].
- **Localization error.** Base effects are checked against the robot's own AMCL estimate; a drifting localization
  verifies as "at the goal" (exp1 L2-B r2: AMCL 7 m off) [F141 item 1; config comment "never from simulator truth"].
- **Items not in the settle view.** `item_placed` → null; in exp1b 17 places were left not established (truth: all
  delivered), 2 navigations off the band with flag success, 2 docks in the band with flag failure; 54 carried-item looks,
  53 held, 1 false alarm [F148 stage 1].
- **VLM reading of a held item** can be wrong; the jaw encoder can only veto (closed-empty) [verification.py comments
  citing g5m; F58].

### 5.4 The guard (guard.py + `configs/space_runtime.yaml` `guard:`)

"Checks only explicit execution boundaries ... It never judges whether a call is a good next step." [guard.py].
Applies to effects only (queries and local tools are not guarded) [agent.py `dispatch`]. Check order [guard.py `check`]:

1. registered effect capability, else `deny`;
2. arguments match the contract (`check_args`), else `deny` ("arguments off-contract");
3. capability in `facts.unavailable` → `unavailable` (unreachable in the build: nothing emits `availability_changed`);
4. active fault whose prohibition covers the call → `deny`: configured `fdir_prohibits: estop: [all_effects]`, fed by the
   OpenRAL safety kernel's latched `/openral/safety_status`;
5. configured hard invariants → `deny`: **`invariants: []` -- empty** ("Only documented hard operating limits belong
   here (space-context limits enter with the scenarios that exercise them)"; none were configured);
6. target-authority rules → the rule's outcome unless an approval of (capability, target) is on record:

```yaml
- name: energized_equipment_removal
  why: taking a module out of an energized unit's bay alters operating infrastructure and cuts its load; it needs
       ground authorization first (14 CFR 1214.403: authorization before altering or removing station property)
  applies_to: [pick]
  target_arg: support
  target_role: equipment_bay
  when_unit: {energized: true}
  outcome: approval_required
```

7. authority class → `routine: allow`, `approval_required: approval_required` (allowed if a capability-wide approval is
   on record), `prohibited: deny`. All contracts are `routine` [configs/space_runtime.yaml; contracts.yaml].

Outcomes: `allow`, `deny`, `approval_required`, `unavailable`, each with a structured reason that goes back to the model
(RECENT STEPS `guard`, UNRESOLVED ANOMALIES `guard_<outcome>`, MISSION CONTROL `held_for_approval`) [guard.py;
context.py]. The rule reads the unit's state fresh: before every effect the harness queries `power_status`
(`equipment_telemetry`) [agent.py]. A held call is carried to mission control by the next `request_operator`
(structured `pending_approvals`; mission control grants or denies exactly those (capability, target) pairs, never from
the text) [agent.py; F108 §4; F125].

Observed: Exp I (exp1b) 3 holds, all L4 donor picks, 0 calls executed despite a hold [F142]. The held targets were
`pdu_3_bay/tray` (r1 at 322.96 s, r2 at 235.44 s of mission time) and `isru_power/tray` (r3 at 419.88 s: the ISRU
plant's power ORU, the other energized non-critical candidate); each grant was followed by exactly one pick on the
granted target [computed for this report from artifacts/runs/exp1b/ours_l4_pdu1_r{1,2,3}/ours/events.jsonl].
Across the 25 exp1b Ours runs: 451 `allow`, 3 `approval_required`, 0 `deny`, 0 `unavailable`; 0 `fdir_changed`
events (no e-stop latched); 0 `budget_exhausted`; 1 `reasoner_step_failed` (a `dock_at_feature` call with an empty
rationale) [computed for this report from artifacts/runs/exp1b/ours_*/ours/events.jsonl].

Note (code vs text): the standing text says "An approval covers one call on one target"; the code keeps an approval in
`facts.approvals` and never consumes it, so a repeated identical call on the same target would also be allowed
[prompts/ours/system.md; guard.py; facts.py]. In the three exp1b L4 runs each grant was used by exactly one pick
(above), so it did not matter there; Experiment II and development runs were not checked.

Plan checks not implemented: freshness of safety-critical inputs; hard resource/health limits (no resource model);
capability degradation producers [AGENT/execution_plan.md §4.3 vs guard.py].

Space-context facts are exposed as context, not rules: "These are facts, not limits: the boundary keeps its own
hardware-protecting limits whatever you conclude from them" [contracts.yaml `space_context`]; the only authority rule
is the approval requirement [heldout_design §5.3].

### 5.5 Dynamic context reconstruction (context.py)

Two messages per model call, rebuilt from the record; "Nothing here chooses or suggests the next action." [context.py].
"There is no conversation memory beyond that message and this standing text." [system.md].

System message (standing text, filled once per reasoner session, `system_text`) [prompts/ours/system.md]:
identity and mission ownership; eight operating rules; the authority model (exceptions read off the contracts and the
guard config -- rendered as the single energized-removal line); the link and mission control (Direct-with-Earth only,
one-way delay 4.27 s, store-and-forward, decision time 300 s, the four request kinds); how to read each record section
and the evidence basis of every verified effect; the surveyed site (frame, point types, every point with unit, view
poses, dock) and the equipment catalogue ("documented prior knowledge; not current observations").

Step message (`step_text`, every step), sections in order [prompts/ours/step.md; context.py]:

| Section | Content | Window |
|---|---|---|
| MISSION | the brief | -- |
| STEP | {step, of_budget}; reasoner sessions if continued by another reasoner | -- |
| ROBOT STATE | latest base (AMCL), TCP, arm | latest |
| VERIFIED EFFECTS | verification records | last 12 |
| OBSERVATIONS | the model's query answers (excluding site_map) | last 8 |
| MOVABLE ITEMS | every manipulated item: state + the verified effect that set it | all |
| LABELS READ (Exp II) | latest frame per scanned support | all |
| MANIPULATION ATTEMPTS | stage, why, tries, reconciliation, measurements, execution conditions, what the VLM saw | last 10 |
| UNRESOLVED ANOMALIES | failed / guard_* / source_disagreement / outcome_unrecorded (+service_outage) | all unresolved |
| MISSION CONTROL | mission time, link up/down with Earth-set or reopening in s; requests (`asked`, kind) and answers (`answered`, outcome); approvals on record; calls held | last 8 exchanges |
| OPERATING STATUS | unavailable capabilities; active faults | -- |
| YOUR WORKING PLAN | tasks {task_id, status, text, last_verdict} -- "yours to revise; not a record of what happened" | all |
| RECENT STEPS | last tool calls with non-allow guard outcome and result | last 12 |

Records are JSON lines; empty fields dropped except `holds` [context.py]. Unit telemetry is not a standing section: the
guard's own `power_status` reads fill `facts.power` but are not rendered; the model sees telemetry when it queries
`power_status` (OBSERVATIONS) [context.py `step_text`; agent.py].

Rendered example (exp1b `ours_l4_pdu1_r1`, step 20): `{"step":20,"of_budget":80}`; MISSION CONTROL
`{"mission_time_s":323,"link":"up","earth_sets_in_s":602.0}` and `{"held_for_approval":[{"capability":"pick","target":"pdu_3_bay/tray"}]}`
[artifacts/runs/exp1b/ours_l4_pdu1_r1/ours/model_io.jsonl].

Size: system 24.1k characters, step 32.9k at step 16 of a development run, 27 tools [F124]; in exp1b
`ours_l4_pdu1_r1` the system message is 24,925 characters, the step message median 33,600 characters, prompt tokens
median 23,790.5 and max 28,564 over 52 calls [computed for this report from that run's model_io.jsonl]. Rebuilt
message 42-74 k characters two thirds through exp1b runs, against 57-162 k characters (~23-66 k tokens) for an
accumulated conversation [F148 stage 1].

Reconstruction after a restart: `--resume` reopens the record; a new `reasoner_attached` adds to `reasoner_history`
(rendered in STEP as `continued_by_another_reasoner`); an effect running at the stop becomes `outcome_unrecorded`
[agent.py; facts.py; context.py]. Experiment I had no restart; the only evidence is the offline J3 ablation [F148].
Development probe: `OURS_RESTART_AT_STEP=N` kills the agent (SIGKILL) and restarts it on the same record, optionally on
another model (`OURS_RESTART_MODEL`) [experiments/launch/lunar_base_d0/ours_mission_check.py].

### 5.6 Tools exposed to the model (tools.py, tools.yaml)

Palette = every non-engineering contract + five harness-local tools [tools.py `tool_schemas`; agent.py palette]:

- Effects (Exp I: 10; Exp II final: 11 with `scan_label`): navigate_to_pose, dock_to_pose, arm_ready, stow,
  navigate_to_feature, dock_at_feature, pick, place, press, release (+ scan_label) [contracts.yaml; `git show
  exp1b:contracts.yaml` checked for this report].
- Queries (12): site_map, observe, manifest, power_status, arm_state, base_pose, tcp_pose, jaw, held_item,
  space_context, work_stands, locate_feature.
- Local (5): `decompose_mission` (write the ordered task list; empty target replaces open tasks, closed ones stay;
  target = active task splits it), `set_task_status` (done | abandoned, with note), `report_to_operator` (final report,
  ends the run), `request_operator` (kind + text), `wait_for_mission_control` (max_wait_s of mission time)
  [prompts/ours/tools.yaml].
- Total 27 in Exp I, 28 in Exp II final [F124 "27 tools"; count above].

Every tool takes a `rationale` ("one sentence: why this call now"); a rationale under 3 words is rejected as "an
unjustified call is not an answer" (F92: a `dock_to_pose {0,0,0}` came with the rationale "placeholder") [tools.py
`decode`]. A reply without a tool call is re-asked once with "Respond with exactly one tool call now." [tools.py;
tools.yaml]. Only the first tool call of a response is used [tools.py `select_tool`]. `decompose_mission` uses plain
task strings because OpenRAL's `DecomposeMissionTool` required each subtask to name one tabletop object [tools.py
docstring].

`request_operator` kinds (F125): `authorization` (held calls → flight-rule table; none held → nothing to authorize),
`authority_check` (published rules restated), `new_procedure` (hold in a safe state; the only kind counted as
re-authoring), `information` ("no data beyond your own queries") [tools.yaml; system.md; F125]. A baseline request has
no kind and is treated as `new_procedure` [F125].

### 5.7 Prompts (prompts/ours/system.md, step.md)

Every text the reasoner reads is in `prompts/ours/`; Python only selects facts and fills templates ("no sentence is
composed in code") [F124; docs/prompt_text_design.md]. Opening: "Mission control gives you a mission objective, not a
procedure. You own the mission strategy: you interpret the objective, decide what to observe, break the work into tasks,
choose and order capabilities, recover when something fails, and decide when the mission is complete or when you need
mission control." [system.md].

The eight operating rules, summarized (verbatim quotes for the trust-defining ones) [system.md]:

1. One tool per step; an effect runs to completion; result, evidence and independent verification appear in the next
   record.
2. **"Distinguish what is established from what is assumed. Mission reports and plans can be wrong; a capability's
   success flag means the skill finished, not that the world is as you intended. Rely on verified effects and
   observations, and query or observe when the information you need is missing or stale."**
3. Keep and revise a working plan; "Close a task only when the evidence supports it."
4. On failure/denial/refusal "read the reason and change something ... Do not repeat an identical call against
   unchanged evidence."
5. **"Hard boundaries (the invariant/authority guard, the safety kernel) are not obstacles to work around. If a
   boundary blocks the only way forward, tell mission control with request_operator."**
6. Frames (`map`, `chassis_base_link`); site features by SITE names.
7. **"End the run with report_to_operator when the mission is complete or cannot be completed. The report states what
   you observed, what you did, which effects were verified, and anything unresolved; it must not claim an effect that
   the evidence does not show."**
8. One-sentence rationale.

Authority text (rendered in exp1b): "Every capability call is yours to decide and make on your own. The exceptions need
mission control's approval first: - pick on a equipment_bay whose unit reports {"energized":true}: approval required
-- ... An approval covers one call on one target: propose the call, the guard holds it, and a request_operator sent
while it is held carries it to mission control." [exp1b ours_l4_pdu1_r1 model_io.jsonl, system message]. Written as
"acting is the default" after Qwen asked permission for what no rule restricts (L2-B) and sent L4 requests in prose
[F123].

Held-out hygiene: the freeze audit found no scenario name, held-out object or held-out unit id in model-facing text; the
generic hits are `energized` (the one authority rule), `isru` (power_status contract's unit list), `slot_0` / `spare
ORU` (contract examples), false hits `covers`/`filter` [F137]; the observe contract's example "whether a place is
occupied" was removed before step 10 because it matched L2-B [F116].

### 5.8 Step budget and termination

`max_steps: 80` [configs/space_runtime.yaml]. The run ends on `report_to_operator` or `budget_exhausted` ("exhausted ->
run ends as needing ground assistance") [config; agent.py].

- Experiment I (exp1b): every turn counted -- `tool_proposed` (all tools, incl. plan tools) and `reasoner_step_failed`
  [`git diff exp1b HEAD -- space_runtime/agent.py`]. Longest held-out development run 45 steps of 80 [F117]; exp1b
  reasoning calls per run up to 79 (`ours_l2a_pdu1_r2`) [artifacts/eval/exp1b/reasoning_latency.md].
- F147 (Experiment II, all later runs): the budget counts calls on the robot -- effects, queries, messages to mission
  control -- and failed steps, not `decompose_mission` / `set_task_status` ("the model's own advisory record", which
  had spent up to a fifth of the budget); STEP shows the used count. Offline replay: Exp II H1 runs 74/75/78 → 56/53/56,
  H2 27-35 → 20-23 [F147; agent.py].
- A gateway outage fails every step (ROSPlanningError → `reasoner_step_failed`), which counts toward the budget: the
  refused-account runs "failed every step to the budget" [agent.py; F149].

### 5.9 Traces and the report

Per run under `<run>/ours/`: `events.jsonl` (the authoritative record; every event carries `seq`, `kind`, `wall_t`,
`sim_t`), `model_io.jsonl`, `agent.log`, `report.md`; beside them the boundary's `capability_server.log` (one
`CAPABILITY` JSON line per effect with args, success, failure, `sim_t_start`/`sim_t_end`, evidence), evidence images
under `evidence/`, `snapshots/` [agent.py; tools.py; node.py; run directory listing of exp1b/ours_l4_pdu1_r1].

`model_io.jsonl` per model call: step, wall_t, model, latency_s, the exact request messages (system + step), the
response (content, reasoning, finish_reason, every tool call offered), token usage -- "this is what was actually sent,
immune to that code changing" [tools.py `_log_model_io`]. `tool_proposed` also stores the model's reply text and
reasoning ("the record is the transcript") [agent.py `proposed`].

`report.md` is generated from the events: the agent's own report quoted, then operator exchanges, executed
capabilities, verified effects, movable items, attempts, observations, non-allow guard decisions, steps without an
executable call, unresolved anomalies, service outages ("not the robot's doing"), the final plan [report.py].

Trace completeness (another part scores it): exp1b Ours 451/451 calls carry proposal, guard, execution and verification
[F142].

Example event counts (exp1b `ours_l4_pdu1_r1`): 396 events; 52 `tool_proposed`, 22 effect executions, 25
`effect_verified`, 23 `guard_decision` (1 `approval_required`: pick on `pdu_3_bay/tray`), 1 request / 1 answer / 1 grant
[computed for this report from that run's events.jsonl].

### 5.10 Resume from snapshots (development only)

The launcher saves the simulator's full state before every agent step (`snapshots/before_step_<n>.pt`, with the rover's
own localization estimate in a `.json` beside it); `OURS_RESUME_FROM=<run dir> OURS_RESUME_BEFORE_STEP=<n>` truncates
the record before step n, restores the scene and continues the agent with `--resume` [ours_mission_check.py;
AGENT/handoff.md]. "Development only, never scored" [AGENT/handoff.md]. A restore cannot keep an item in the jaws (the
holding contact is not in the saved state; the item falls out) [ours_mission_check.py citing F60]. Used e.g. for L2-B
`resume43d` in step 10 [F138].

### 5.11 Ablation switch (brief; another part covers the ablation)

`OURS_ABLATION` ∈ {no_facts, no_verification, no_guard, no_context} on branch `feat/ablation` (`.worktree/ablation`,
not merged into main at the time of writing); unset = the full method "byte for byte"; variant texts in
`prompts/ours_ablation/<variant>/` [.worktree/ablation/space_runtime/ablation.py; F148]. Render check: every recorded
step of the 25 exp1b Ours runs re-renders identically, 1099/1099 [F148].

### 5.12 Runtime-side known defects and plan-vs-build gaps

| Item | Source |
|---|---|
| `availability_changed` and `operator_request` handled by the reducer but never emitted; `unavailable` guard outcome unreachable | [facts.py; agent.py] |
| `invariants: []` -- no hard invariant configured | [configs/space_runtime.yaml] |
| Approvals are not consumed after use (text says one call) | [guard.py; system.md] |
| Jaw empty threshold 0.12 (verifier) vs 0.13 (boundary/skills) | [config; _eye_in_hand.py] |
| Ours' action client (`agent.py execute`) has the same exposure to a lost goal response as the PLEXIL adapter had; never hit (0 in 50 Ours runs across exp1/exp1b); not changed | [F142 item 2] |
| `agent.py` is outside the freeze audit's `METHOD_ARTIFACTS["ours"]` list (listed as "outside the artifact list" and audited there) | [artifacts/eval/freeze_audit/2026-09-26.md §(a), "Changed ... outside the artifact list"] |
| Plan items not built: service registry / endpoint router, freshness checks, resource/illumination/compute context modules (space_context has only `earth_visibility.py` + `link.py`), OpenTelemetry trace correlation | [AGENT/execution_plan.md §4.1-§4.6 vs `space_context/`, `space_runtime/`] |
| Ours' H1 (Exp II) search less systematic than PLEXIL's sweep; 74 and 78 of 80 steps before F147 | [F146; AGENT/handoff.md] |
| rows.py's ledger rule cannot see a false completion whose report is the plan's still-active last task (evaluation side) | [F146; AGENT/handoff.md] |

---

## 6. Models

### 6.1 Configuration as run

| Role | Model | Endpoint | Settings | Used by | Source |
|---|---|---|---|---|---|
| Reasoner (Ours only) | `Qwen3.8-Max` | paratera gateway `https://llmapi.paratera.com/v1`, key from env `SPACE_REASONER_API_KEY` | timeout 600 s; `thinking: true` (no extra body sent; `false` would send `thinking: {type: disabled}`); `tool_choice="auto"`; no sampling parameters (gateway default decoding) | Ours | [configs/space_runtime.yaml; tools.py; F137; artifacts/freeze/freeze-1.yaml] |
| Scene VLM | `DeepSeek-V4.1-Flash` | same gateway (key env `SPACE_LLM_API_KEY`) | timeout 300 s | capability server `observe`, `held_item`, `locate_in_view` / `approach_target` -- all methods | [node.py; freeze-1.yaml `scene_vlm`] |
| Skill VLM | `DeepSeek-V4.1-Flash` | same gateway | `VLM_TIMEOUT_S` 300 s, `max_retries=0` | pick (region choice), press (point) -- all methods | [rskill.yaml; procedural_pick.py; procedural_press.py; freeze-1.yaml `skill_vlm`] |

Engineers in Experiment II and the re-authoring study are Claude sessions (another part) [F146; F149].

### 6.2 Reasoner history

| From | Reasoner | Endpoint | Why | Source |
|---|---|---|---|---|
| 2026-09-17 (first agent commit) | DeepSeek-V4.1-Flash | paratera | initial | [git log configs/space_runtime.yaml: 17d2bea] |
| 2026-09-17 20:07 | DeepSeek-V4-Pro | paratera | offline replay of 5 Mission B decision points × 2: V4-Pro 7/10, Kimi-K3 3/10, Qwen3.8-Max 3/10, local qwen3.8 27B 3/10, GLM-5.3 2/10 (timeouts), V4.1-Flash 1/10 text; median 162 s per step | [8b1fa10; F55 §4] |
| 2026-09-18 16:38 | `deepseek-flash` | DeepSeek's own endpoint `https://api.deepseek.com` | "1.2 s a step instead of 162 s" | [git f2281a9 subject] |
| 2026-09-23 | DeepSeek-V4.1-Flash | paratera | DeepSeek's own API became unaffordable (user decision); reasoner step 2.1-3.2 s from a container | [a727fe4; F111 §4] |
| 2026-09-25 | **Qwen3.8-Max** | paratera | step 10 held-out: DeepSeek-V4.1-Flash failed L2-B and L4 on reasoning; model comparison F119-F122; user decision | [d163305; F123] |

Thinking mode: offline A/B over 42 decisions of run oa1: off 3.9 s median vs 13.3 s on, tool choice not systematically
different; kept on ("capability over latency", user decision) [F54 §6; configs/space_runtime.yaml comment citing F53].
(The config comment cites F53; the A/B is written up in F54 §6 -- a numbering slip in the comment.)

Scene VLM history: GLM-5.3-Flash chosen at F55 (Kimi-K3 95-150 s per answer); gateway stalls of image requests (F58);
DeepSeek-V4.1-Flash on paratera from 2026-09-23 for scene VLM and pick/press [F55 §4; F111 §4; node.py comment "GLM-5.3-Flash and
Kimi-K3 15/15, Qwen3.8-Flash 14/15; research repo F54"]. Readings re-checked on the new model (BESS lamp red, HVAC
shutter drawn, ISRU lamp green; 25/25 work stands) [F112 §5].

### 6.3 Why Qwen3.8-Max (F119-F123)

L2-B offline (3 calls per model per point, two decision points of the live DeepSeek failure; rubric fixed before) [F119]:

| Model | FAIL (place on occupier) | plan: stage, move occupier, deliver | escalate | s per call |
|---|---|---|---|---|
| DeepSeek-V4.1-Flash (live) | 3/6 | 0 | 0 | 41-283 |
| Kimi-K3 | 0 | 4/6 | 0 | 124-343 |
| Qwen3.8-Max | 0 | 1/6 | 3/6 | 71-231 |
| GLM-5.3-Flash | 2/6 | 1/6 | 3/6 | 185-431 |

L4 offline (three decision points, 3 calls each) [F120]:

| Model | calls naming the transfer (of 9) | donor pick proposed / authorization request |
|---|---|---|
| DeepSeek-V4.1-Flash (live) | 0 | 0 |
| Qwen3.8-Max | 8 | 1 pick + 1 authorization request + 1 plan starting with the held pick |
| GLM-5.3-Flash | 4 | 0 |
| Kimi-K3 | 2 | 1 pick |

Regression on ten decision points DeepSeek had got right (3 calls each): DeepSeek 25/30 PASS, 5 NEUTRAL, 0 FAIL (median
13 s); Qwen3.8-Max 26/30, 4, 0 (19 s); Kimi-K3 27/30, 3, 0 (23 s) [F121].

Live, same harness, only the reasoner swapped: Kimi-K3 solved L2-B (39 steps), failed L4 (grant decided 9 s after
Earth-set); Qwen3.8-Max solved L4 (51 steps; guard hold, authorization, grant, donor install) and on L2-B held on
mission control's answer (asked with no call held) [F122]. User decision: Qwen3.8-Max; VLMs unchanged; "A method change:
every development run before it is not comparable" [F123]. Re-check on the reorganized texts (F124): regression 30/30
without a FAIL (PASS 25, NEUTRAL 5); L4 names the transfer in 7 of 9 calls, 3 authorization requests; L2-B 0 FAIL of 6
[F131 last paragraph].

### 6.4 Per-call reasoning latency (exp1b; F152)

From `artifacts/eval/exp1b/reasoning_latency.md` (medians over runs, except per-call latency: median and IQR over calls):

| Coverage | Runs | Reasoning calls | Wall clock in calls (s) | Mission time in calls (s) | Mission time recorded (s) | Mission time, latency in full (s) | Per-call wall latency (s) | Mission time per wall second in calls | HIR recorded | HIR latency in full |
|---|---|---|---|---|---|---|---|---|---|---|
| covered | 7 | 17 | 351 | 81 | 538 | 825 | 16.5 [9.1, 33.4] | 0.241 | 0.000 | 0.000 |
| held_out | 18 | 40 | 1166 | 293 | 1132 | 2071 | 20.8 [11.9, 40.0] | 0.236 | 0.080 | 0.036 |
| all | 25 | 34 | 1103 | 252 | 1095 | 1984 | 19.9 [11.3, 38.7] | 0.237 | 0.000 | 0.000 |

"A call's wall time includes the harness's context rendering, at most 0.15 s above the model's own latency"; calls
before the first capability call and after the mission's end are outside the mission window; the latency-in-full
mission time is an upper bound (calls overlap mission control's decision time); VLM calls inside the shared skills run
on the same compressed clock for every method and are not corrected [reasoning_latency.md notes; F152]. Per-run range:
calls in mission 15-71, wall clock in calls 165-2993 s [reasoning_latency.md]. Other latency records: median model
step per run 12-101 s (median 20 s) in exp1 [F140]; gateway at the freeze start Qwen3.8-Max 12-19 s, DeepSeek-V4.1-Flash
4 s per short request; night 170-330 s per step [F139; F118].

---

## 7. Development history that shaped the system

### 7.1 Rule for changes to Ours, and the freeze audit

- Ours may take only generic changes that pass three tests: the change names no situation, place or serial; it holds
  for every task; it is traceable (recorded in findings) [AGENT/todo.md "Rules"; F147 applies them]. Plan source:
  "Failures are answered only with mission-generic changes" (execution_plan §13.1) [docs/freeze_audit.md].
- Baselines are locked (docs/baselines/authoring_spec.md) and changed only under the lock's change control; shared-layer
  fixes found in a campaign are applied for all methods, recorded, and only the runs they decided are rerun; no freeze
  ceremony after freeze-1 [AGENT/todo.md; AGENT/handoff.md; F141/F142; F145; F147].
- Freeze audit (`evaluation/freeze_audit.py`, report `artifacts/eval/freeze_audit/2026-09-26.md`): diffs Ours'
  artifacts against step 10's starting point `8361741`, attaches to each hunk the findings (F116 on) sharing a code word
  and the git-blame commits, greps model-facing text for §14's held-out words, checks the baselines against the lock
  `1b6a40f` [F137]. Result at F137: 34 hunks in 9 files, 23 sharing a code word with a finding (F117, F123, F124),
  `tools.py`'s hunks = F124's reorganization, "None of the changes names a device, cause, object or order"; one held-out
  run name in a verification.py comment was removed before the freeze (cb7f9d0) [F137; F139]. The report file was
  regenerated at the freeze commit `87ebd5e` (F137 had cited HEAD 548c19b) [freeze audit report header; F139].
- `evaluation/freeze_tag.py` recorded the three repos' HEADs, the image, the venv packages, each method's artifacts and
  the model configuration → `artifacts/freeze/freeze-1.yaml` [F137; F139].
- `docs/freeze_audit.md`'s "History" still says "no freeze has been run" -- stale relative to F139 [docs/freeze_audit.md].

### 7.2 Key changes (F108-F147)

| Finding | Date | Change | Kind |
|---|---|---|---|
| F108 | 09-23 | One site model, scenarios as initial conditions; unit telemetry + inventory record through the boundary; ORU bays; Data Matrix labels; drawn shutter recoloured after the VLM read it as fins; **guard rule class `target_authority`** (energized-equipment removal, 14 CFR 1214.403); SPICE Earth link | scene / Ours |
| F109 | 09-23 | BESS + ISRU units, offload/habitat/return stands, map re-survey; **`request_operator` asynchronous** + `wait_for_mission_control` | scene / Ours |
| F110 | 09-23 | Own equipment per unit; reset caps white/black; global costmap = static surveyed map; smoother free limits read from launch (crab restored) | scene / shared |
| F111 | 09-23 | Baseline lock (tier-1 = 3 attempts); run farm; models to paratera DeepSeek-V4.1-Flash | baselines / infra / models |
| F112 | 09-24 | Baselines built to lock; held-out action forms executed (pick fit LM-damped, seeded at the declared work point; place settle; press folds after); map stray cells; VLM timeout 300 s | shared |
| F113 | 09-24 | tf2 ABBA deadlock fixed in the image; Nav2 server timeout 1000 ms; campaign cut to 13 instances | infra |
| F114 | 09-24 | Livelock/timeout sweep: Ours' query resend doubles; `answer()` waits; episodes not truncated | Ours / shared |
| F115 | 09-24 | Covered live reruns 18/21 (shared-layer failures); new READY posture; place fails "the item came away with the tool" (in-jaws count); undock 1.5 → 1.2 m | shared |
| F116 | 09-24 | Earth-set moved to 925 s of mission time; queued escalation counts as re-authoring; observe's example "whether a place is occupied" removed | protocol / Ours text |
| F117 | 09-25 | **Verifier: `item_placed` requires < 200 points between the open fingers**; **time + link state in every step** | Ours (generic) |
| F118 | 09-25 | **Decision time and approval mechanics stated in context** | Ours (generic) |
| F119-F122 | 09-25 | Model comparison (Section 6.3) | models |
| F123 | 09-25 | **Reasoner → Qwen3.8-Max (600 s); authority line rewritten** ("acting is the default"); texts to move into files | Ours |
| F124 | 09-26 | **Every text the reasoner reads in `prompts/ours/`**; record as JSON lines; explanations in the standing text; `playbook.md` gone | Ours (organization) |
| F125 | 09-26 | **Request kinds** (authorization / authority_check / new_procedure / information); mission control answers by kind and held calls, never by text; request event field `request_kind` | Ours / protocol |
| F130 | 09-25 | Ablations would likely show no natural difference (→ method B, F148) | analysis |
| F131 | 09-25 | `scan_label` built, unregistered; view 0.36 m / 67° | shared |
| F137 | 09-26 | Freeze audit tooling | process |
| F138 | 09-26 | **Verifier: `item_placed` = null when the settle frame shows nothing of the item** (5344ec6); shared place: base-driven withdrawal, short lift recorded not failed; step 10: 6/6 held-out solved live (development) | Ours / shared |
| F139 | 09-26 | Freeze `freeze-1`; Experiment I campaign (51 runs) | process |
| F141 | 09-27 | After exp1: map covers free ground; post-dock localization settle; dock path check; adapter first-result fix (misdiagnosed, corrected F142); place jaw-at-rest + turn search; stow joint7 π/2 | shared |
| F142 | 09-28 | exp1b rerun; place step-off before turning (openral 9338521); PLEXIL adapter raw send_goal/get_result with own goal id | shared / baseline infra |
| F144 | 09-28 | Exp II setup: `scan_label` reaches the boundary (unregistered), ORU-0272, Mission B knobs, G3 validation suite | shared |
| F145 | 09-28 | Scan view = widest of three the arm can take | shared |
| F146 | 09-28/29 | Ours' extension: contract + `labels_read` effect + LABELS READ section + 2 descriptions (7 files +49/-3), active 54.5 min, 4.7 min not waiting on the simulation | Ours (Exp II) |
| F147 | 09-29 | `something_on_support` (shared); **Ours' step budget counts calls on the robot** | shared / Ours (generic) |

Earlier findings the runtime cites in code: F53/F54 (thinking kept on), F57/F58 (blind held-item reading; query outage is
not evidence), F60 (restore cannot keep a held item), F90 (dropped first response), F92 (rationale required) [agent.py;
node.py; tools.py; ours_mission_check.py comments].

Step-10 development outcomes that motivated the generic changes: DeepSeek-V4.1-Flash solved 4 of 6 held-out instances;
L2-B failed with a false completion caught by F117's fix; L4 failed on the model's strategy [F117; F118]; with
Qwen3.8-Max 6 of 6 solved live (development runs, never scored) [F138].

---

## Gaps (what could not be found or verified)

1. Isaac Lab version: not recorded in the files read (Isaac Sim `5.1.0-rc.19` is).
2. The front camera's D435i identity rests on the contract text and a node.py comment; robot.yaml lists the wrist camera
   RGB only (no `wrist_depth` entry) although the boundary subscribes to `/openral/cameras/wrist_depth/image`.
3. The thinking-mode A/B is cited as F53 in the config comment but is written up in F54 §6; the numbers are taken from
   F54 §6.
4. The OpenRAL safety kernel's exact checks at runtime (deadman, joint bounds, speed envelope) were taken from robot.yaml
   and the RM-75 spec; the kernel source was not read. No exp1b Ours run latched an e-stop (0 `fdir_changed`); the
   Experiment II and development runs were not checked, so the e-stop → deny path has no live exercise on record here.
5. Whether the non-consumed approval ever allowed a second call on the same target was checked only in the three exp1b
   L4 runs (it did not); other runs were not checked.
6. The exact ReasonerCore semantics beyond its docstring (`retry_cap_hold`, heartbeat suppression) were not traced in
   code; the report relies on the docstring.
7. The pick skill's `bring_in` / carry posture details and the hold-check thresholds inside the skill (as opposed to the
   verifier's) were not read in full.
8. Evaluator success conditions, the operator console's flight-rule table, the Earth-link generation and the run-farm
   details are left to the other parts; this part only cites them where the runtime reads them.
9. The execution_plan's §9.5/§10 text on the context builder and FDIR was not read in full; comparisons use §4.1-§4.6
   and research_content §4.
10. No numbers were verified by re-running anything (by instruction); all numbers are from findings, configs, code or
    finished run files as cited.
