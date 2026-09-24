# Held-out design and implementation plan (decided 2026-09-23)

Supersedes the held-out selection in `docs/lunar_task_catalog.md` §5 and the old `experiments/scenarios/*/held_out/`
set. Serves research_content §5.5 (Experiment I), §5.6 (Experiment II), §5.7 (ablations), H3, and resolves the
"space-native boundary" open question (decision 2) through the L4 case.

**Instance set: §14 (decided 2026-09-24) supersedes the unit x level crossing of §9 and the L4-far case.**

## 1. Selection rules

1. **The situation itself has a real precedent** (not just its category). Category-only support is marked as such.
2. **Rigid assets only**: no cloth, no articulated mechanisms; an actuator is a dummy push button, a mechanism state
   is a visual variant switched by the task.
3. **Physical actions only in verified forms**: `press`; `pick`/`place` of a T-handle item on a horizontal, surveyed,
   tray-like support with ~10 cm clearance (the Mission B form); Nav2/dock. Novelty lives in reasoning and perception,
   so a physical-layer failure cannot masquerade as a reasoning result.
4. **Clean separation**: competent baselines *detect* the anomaly (verification + generic retry + escalate) but their
   frozen artifacts contain no decomposition for it; Ours composes one from existing capabilities.
5. **Levels are defined by what the frozen baseline model lacks**, not by how hard the case is for Ours.

## 2. The novelty ladder (Experiment I)

| Level | Frozen model lacks | Case (scenario id) | Precedent |
|---|---|---|---|
| L0 | nothing | A1 `covered`, B1 `covered` | Lewis 2022 caretaker; ISS ORU logistics |
| L1 | only variable values (covered variants) | A: other faulted PDU; report names the wrong unit (`covered_misreport`). B: other destination | ISS Daily Summary 2015-01-14 (erroneous MDM ammonia indication) |
| L2-A | a cause/relation | **Radiator cover left closed → over-temperature trip** (`heldout_radiator_cover`) | LRV radiator dust covers opened for cooling (Creel, DAP-2017; TFAWS 2023); Apollo 16/17 battery over-temperature (Gaier, NASA/TM-2005-213610). *Closing covers for landing ejecta is our extrapolation from Metzger (plume ejecta) -- say so in the paper.* |
| L2-B | a relation | **Destination tray occupied by a returned crate** (`heldout_destination_occupied`, exists) | ISS off-nominal cargo configuration (catalog [14], category-level) |
| L3 | a cross-family composition | **Reset does not hold: the PDU's ORU fails self-test → fetch the depot spare, remove the failed ORU, install the spare, reset** (`heldout_module_failure`) | Dextre RPCM remove-and-replace on ISS, Aug 2011 (first robotic R&R of failed equipment); Lewis 2022 fault → repair → verify |
| L4 | a goal conflict + authority | **No serviceable spare; the only one is installed in energized PDU-3 (ISRU pilot plant; far variant: the ISRU yard's own unit, §9) → request ground approval before the Earth-visibility window closes, then move it to PDU-1 (life support)** (`heldout_cannibalize`) | 14 CFR 1214.403 (authorization before altering/removing property); Apollo 17 fender repair with clamps taken from the optical alignment telescope, ground-devised; NASA LCN white paper 2023 (south pole sees Earth ~half of each sidereal month) |
| control | nothing mission-level | B4 `route_block` (Nav2 routes around it for every method) | -- |

Dropped: A2 cover obstruction (a leaning plate is not `pick`-compatible), A3 as held-out (a competent baseline
surveys; it becomes L1), A4/A5, B3 spare swapped (slot_1 has no legal stand; a known unknown), all tag/placard/cloth
ideas (no precedent for the situation).

Why this separates the methods: L3 is the sharpest -- every piece exists in *both* baselines' frozen libraries
(Mission A reset, Mission B delivery), only the composition does not. L4 adds value judgment, authority and a
real communication constraint.

## 3. Evidence each case produces

- **H1 (main figure)**: success vs. level L0→L4, three methods, paired instances. Expected (hypothesis only):
  baselines ≈ full at L0–L1, "detected → escalated" at L2+; Ours degrades gracefully.
- **ALFUS**: baselines at L2+ need task-level ground re-authoring (`ground_reauthoring_required`); Ours at L4
  needs one mission-level authority exchange. Intervention ratio, interaction level, preplanning burden per level.
- **H3 / space-native**: L4 is where the guard fires `approval_required` on a real authority class and where the
  SPICE-derived link state changes what is possible. §5.7 ablations on L3/L4: no guard → removal without approval;
  no verification → "success" on a reset that did not hold; no facts / no context reconstruction as specified.
- **Experiment II**: §6 below.

## 4. Scene and task design (SRB, `space_robotics_bench/`)

Assets (Blender pipeline `assets/lunar_base/process/author_props.py`, layout `scene/layout.yaml`, generated
`scene/generated/interaction.json`):

1. **ORU bay on each PDU** (`pdu_N_bay/tray`, place-type point). An open-top tray on the cabinet, the same form as
   the spares shelf (horizontal top, ~10 cm clear of a 0.45 × 0.39 m ORU on every side, T-handle up). Each bay holds
   one installed ORU at reset. Installed = ORU on the bay support (existing on-support test). No latching.
2. **Serial labels**: every ORU carries a Data Matrix symbol (NASA-STD-6002) on its top face next to the handle,
   plus human-readable S/N text. Present in every scenario from the start (the scanner arrives only in Exp II).
3. **Radiator + cover**: radiator fins on each cabinet; a cover in two static visual states (open/closed) toggled by
   the task (built as a roll-up shutter, visual-only); a dummy **blue** push button on an actuator box beside the
   radiator -- its own feature and stand, so `press` never has to tell it from the red reset button.
4. Remove the service cover prop and the `cover_obstruction` / `spare_swapped` scenario code (dead after this).

Task logic (`srb/tasks/mobile_manipulation/lunar_base_mission_{a,b}/task.py`; L3/L4 need both families' assets, so
they live in Mission A's task with the depot included):

- **Power telemetry** per PDU: breaker state (closed/tripped), trip cause (`OVERCURRENT` / `OVERTEMP` /
  `ORU_SELFTEST_FAIL`), energized flag, installed ORU serial. This is the unit's own telemetry, not evaluator truth.
- `heldout_radiator_cover`: cover closed on the faulted PDU; a reset holds only while the cover is open, otherwise
  the unit re-trips `OVERTEMP` after `retrip_delay_s` (manifest parameter, fixed before freeze, not tuned to Ours).
  Pressing the cover button opens it.
- `heldout_module_failure`: the faulted PDU's installed ORU fails self-test; a reset re-trips `ORU_SELFTEST_FAIL`
  unless a serviceable ORU sits in its bay. Depot slot_0 holds a serviceable spare (manifest record correct).
- `heldout_cannibalize`: PDU-1 (life support) module failed; the depot ORU's record is `FAILED` (returned unit
  awaiting return shipment); PDU-3 (ISRU pilot plant, energized) holds the only serviceable ORU. Removing it
  de-energizes PDU-3. Evaluator additionally counts removal-before-approval as a violation.
- **Manifest query** gains inventory records (IMS-like): serial, recorded location, status
  (serviceable / failed / reserved). Correct in all Exp I cases; mismatches are Exp II.
- Evaluator success = existing dock/stow conditions + per case: fault cleared **and still cleared at episode end**;
  L2-A cover open; L3/L4 a serviceable ORU in the target bay, the failed one out of it; L2-B as today.

Offline gates before any live run (no simulation needed except single still renders):
`work_stands` for every bay and the cover button; hull/stand clearance with the reach model; one still render per
camera view poses → lamp colour, cover state, crate on tray readable by the VLM; one wrist-view render of a label →
decoded by the actual decoder (§6).

## 5. Harness and space-context work (research repo)

1. **Shared queries** in `openral_ext/capability_server/contracts.yaml` (visible to all three methods, pre-freeze):
   `power_status` (telemetry above), extended `manifest` (inventory records). Baselines read them as Lookups /
   EUROPA state.
2. **Authority by target** (`space_runtime/guard.py` + its config): site-survey supports carry a class; one generic
   frozen rule -- *removing an item from the bay of an energized unit requires ground approval* (energized-equipment
   removal; 14 CFR 1214.403). Approvals keyed by (capability, target), reducer branch for `operator_answered`.
3. **Space context** (`space_context/`, empty today): SPICE (DE440 + lunar frames/PCK) Earth elevation at a
   south-polar site; epoch chosen so loss of signal falls inside the L4 mission; profile precomputed with provenance
   (execution_plan §7.1–7.2). A link gate makes the operator channel actually unavailable during LOS (store-and-
   forward: queued, not delivered). One-way delay from Landon et al. 2025. Exposed as facts (time to LOS), never as
   a rule except the approval requirement itself.
4. **Operator console live** (`experiments/operator_console/`) with a written, scripted operator protocol (what the
   ground answers to which request class, answer latency) -- identical for all methods; ALFUS events logged.
5. Evaluator-violations recorder wired into all three launch scripts; capability-server call-start timestamp.

## 6. Experiment II -- new capability: `scan_label` (Data Matrix via the wrist camera)

- **Capability** (shared low-level implementation, built before Exp II but *not registered* in any method's
  artifacts until the timed extension starts): one whole operation at a surveyed support the rover is docked at -- take the
  wrist view `pick` already uses over the support, decode Data Matrix (zxing-cpp) on the real rendered frame,
  return serials + evidence frame. Demo overlay: wrist picture-in-picture, symbol boxed, S/N vs. record ✓/✗.
- **Why it is a genuine new capability**: identical ORUs differ only by serial; the VLM cannot decode a Data Matrix.
- **Extension spec** revealed after the Exp I freeze: "inventory records can be wrong; a label scanner is now
  available". Visible validation case: scan and confirm the depot spare. Hidden held-out cases (≤3 candidate
  locations each, to bound search time): record says the serviceable spare is at the depot but it sits in another
  PDU's tray/shelf; two identical ORUs with swapped records.
- **Protocol**: execution_plan §13.4 -- timer + `engineering_worklog.jsonl`, diff of method artifacts, validation
  failures, post-extension held-out success. Single engineer → controlled case study (state in limitations).
- Expected work: Ours -- one contract entry. PLEXIL -- Command/Lookup + verify/search branches. EUROPA -- identity/
  location state variables, a sensing activity, rules, bridge mapping.

## 7. Baseline competence (before freeze) -- locked 2026-09-23

The baselines are built to the **locked specification** in `docs/baselines/authoring_spec.md`, decided before any
further baseline run so that a failed run cannot pull them stronger (or weaker) after the fact. In short: native
PLEXIL / EUROPA plus the covered specification's knowledge; three tiers of failure handling -- (1) a failed call is
repeated, at most 3 attempts per call (the same cap Ours has on an identical call), then hold and ask mission control;
(2) the goal checks the covered brief asks for (reset holds, still holds at the dock); (3) **no branch keyed on a
cause or situation** (trip cause, inventory status, occupancy, observation, failure stage) -- that knowledge is what
H2 prices. Mission A's formal goal is every unit restored (the solver/plan finds the tripped one from telemetry);
Mission B is parameterized by item, source and destination from one shared launcher goal; one consolidated NDDL
domain; the EUROPA instance holds every inventoried item; after escalation a baseline holds in place. Changes after
the lock follow its change-control table (infrastructure and conformance fixes only). After the freeze: an offline
retry-budget sensitivity check (N = 1, 2, 3, 5 on every held-out state) and the §8 re-authoring cost per held-out
case.

## 8. Ground-operator protocol (decided 2026-09-23)

One scripted, published protocol, identical for all three methods (`experiments/operator_console/console.py`). Its
parameters are design choices grounded in operations sources; the paper states them as such.

| Parameter | Value | Grounding |
|---|---|---|
| One-way link delay | 4.27 s (1.27 s light time + 3 s ground system), from the SPICE profile | Landon et al. 2025, Table 1 (Orion nominal 2.7 s) |
| Mission control's decision time, every request | **300 s**, fixed, no sensitivity runs; the HIR numerator scales linearly with it (stated) | VIPER ops "minute-scale" (Lim et al., LPSC 2024 #1647); value is ours |
| Grant / deny | Pre-published flight-rule table: GRANT an authorization when the donor unit is non-critical, the removal restores a crew-critical load, and the request names unit, module and consequence; otherwise DENY with a reason code | 14 CFR 1214.403 ("decisions planned in advance ... minimize real-time discussion") |
| "No procedure applies" escalation | Answer after the decision time: "ACK -- hold in a safe state, new procedure in work". Nothing is uplinked during the run -> `ground_reauthoring_required` | Apollo 13 ~34 h, STS-120 4 d, MBSU-3 2019 3 d, Dextre RPCM ~13 months |
| Re-authoring cost | Not simulated: measured offline as developer time + new plan/domain nodes to add the missing continuation (feeds Experiment II) | ALFUS human-planning ratio |
| Earth below the horizon | Store-and-forward: the robot's own link node reports "queued for the next pass"; the vehicle holds safe; unanswered at run end = unanswered | RFC 4838; Morgan (JPL fault protection); Estlin et al. |
| ALFUS labels | request = "operator approval query"; approval = *assign tactical goals*; re-authoring = *assign mission tasks*; teleoperation = route/autopilot/servo | NIST SP 1011-II-1.0 |

Measured per run and where it goes in the paper: requests by type and grants/denials, ALFUS human-intervention time
ratio, human-planning ratio, highest interaction level, re-authoring flag + developer hours (main table);
intervention response time split into delivery / notice / planning / execution (Steinfeld et al., HRI 2006; stacked
bars); longest autonomous stretch (Olsen & Goodrich neglect time) and idle-waiting-for-ground fraction (CADRE's 28%
for comparison); a swimlane timeline per method with the Earth-visibility window shaded (figure). A live human
operator is used only in a demonstration run, never in the statistics (scripted = reproducible; Riek 2012 on
Wizard-of-Oz variance).

## 9. Base-wide scene expansion (decided 2026-09-23)

Equipment is a **blocking factor crossed with level**: each level's instances are split across units rather than
added, so H1 replicates across equipment and drive lengths. Pre-freeze condition: every serviced unit is
serviced with the same verified action forms (press a panel/shutter button; pick/place a module by its top handle on a
horizontal tray), appears in `power_status`, and the baselines' covered artifacts cover L0/L1 at every unit with the
unit id as a parameter (otherwise the unit itself would be novel to them). Each unit keeps its own equipment look
(user decision 2026-09-23: no PDU props reused on other equipment). One held-out event per episode;
physical-layer failures logged per leg, success conditioned on no physical failure reported as a secondary metric.

| Addition | Zone | Serves | Precedent |
|---|---|---|---|
| Battery storage container as a serviced unit: BMS enclosure + graphite control panel, HV battery-module cradle, free-standing HVAC condenser with a roll-up shutter and its own actuator button, receiving stand | power field east (38, 13) | L2-A and L3 replicates | Apollo 15 Mission Report p.94 (LRV batteries: cool with covers open, warm with them closed), Apollo 16/17 over-temperature (Gaier 2005); ISS BCDU robotic replacement from an on-orbit spare (ISS DSR 2019-04-02); Lewis et al. 2022 p.7 |
| ISRU oxygen plant as a serviced unit: plant controller + white control panel on the tank skid's service side, a filter-cartridge cradle (L3 replicate: clogged filter swapped for the staged spare) and a power-ORU cradle (the far L4 donor, paired with PDU-3 near), O2 bottle rack, receiving stand | ISRU yard (skid service side faces south) | L3 replicate; L4-far vs L4-near (separates distance from level) | ISS Oxygen Generation System recirculation-loop filters clogged and were replaced on orbit (NTRS 20110023212); Lewis et al. 2022 p.16 (life support precedes non-critical), p.13 (ISRU pilot plants); GAO/NSIAD-88-30BR pp.39-40 (cannibalization, board approval) |
| Landing-pad offload stand -> habitat logistics shelf, look-alike consumables container | platform end of the landing-pad access road (moved off the pad's cut, F112) -> habitat front | B long haul (L1) | Lewis et al. 2022 p.12 (robots offload and transport logistics before crew arrival), p.19 |
| Habitat shelf occupied by an outbound return container (to a depot return stand) | habitat | L2-B replicate | ISS DSR 2019-06-17 (empty carrier removed before installing a spare; the *unexpected* occupancy is our extrapolation); Lewis et al. 2022 p.19 (trash, boneyards) |

As built (2026-09-23, redesigned after review): the scene's `units` (layout.yaml, exported to interaction.json) drive
the site model -- no unit list in code. `pdu_1` (habitat life support, crew-critical), `pdu_2` (communication station,
mission-critical), `pdu_3` (science instruments, non-critical): yellow service panel, spares shelf, ORU bay, radiator
with shutter. `bess` (battery storage, mission-critical; the container stands on the pad, the source model's plinth cropped
away): wall-mounted BMS enclosure with a graphite control panel (white reset cap), battery-module cradle (BAT-0101,
0.29 x 0.42 x 0.367 m; spare BAT-0102 on the depot spares stand), HVAC condenser
with shutter and blue actuator button. `isru` (ISRU oxygen plant, non-critical, no shutter): plant control panel
(black reset cap, dark readout; inspected from 2.0 m), filter-cartridge cradle (FLT-0201; spare
FLT-0202 on the ISRU receiving stand, an empty ISRU set-down stand beside it for the removed cartridge) and power-ORU cradle (ORU-0285). Reset caps are never red or green (IEC
60204-1 §10.2.1): red and green appear only on status lamps. Every carried item's handle neck sits 0.4669 m above its base (the column,
not the body, sets it) and its long side lies across the approach (F112). A closed breaker trips after the self-test with
the module's own code (`ORU_SELFTEST_FAIL` / `BATTERY_MODULE_FAULT` / `FILTER_CLOGGED`), at once on an empty bay
(`MODULE_MISSING`); telemetry lists the installed module serial per bay. Mission A takes `env.faulted_unit`
(L2-A: PDUs and BESS; L3: every unit with its own spare). L4-near (`heldout_cannibalize`, PDU-1): the depot spare ORU
is recorded failed and is; PDU-3's ORU and the ISRU plant's power ORU are the energized non-critical candidates. L4-far
(`heldout_cannibalize_far`): additionally PDU-3's module was removed earlier and sits failed on its own shelf (PDU-3
down, MODULE_MISSING), so only the ISRU plant is left. Mission B takes `env.cargo` (`spare_oru` from the depot stand |
`bat_spare` from the depot spares stand | `consumables_container` from the landing-pad offload stand) and
`env.destination` (a PDU's spares shelf | `bess`, its receiving stand | `habitat`, the habitat logistics stand); the
occupier of `heldout_destination_occupied` is the returned crate, or the return container on the habitat stand. The
operator's brief is published by the task itself (latched `/srb/env0/mission_brief`). Authority (guard, console,
evaluator class 5) keys on the unit a site point belongs to (`points[...].unit`) and on the bay granted.

Honesty notes for the paper: the 1 kg battery module, filter cartridge and consumables container are look-alikes (real ISS battery
ORUs are far heavier). Not added: a third family, dust cleaning, cables/connectors, commodity transfer, the HLS
elevator, hatches, comm-station faults in L4 (a dead comm unit with a live link is incoherent), lighting changes,
stacked held-out events. Video richness comes only from post-hoc overlays (map + path, wrist PiP, the agent's own
reasoning, power topology from `power_status`, Earth-elevation strip with LOS countdown), never from extra live cameras.

## 10. Implementation order (each step: offline check first, then one decisive live run)

Done (F108): docs, telemetry + inventory, bays/labels/radiators, the Mission A/B scenarios, authority by target,
SPICE link + gated console, competent PLEXIL/EUROPA Mission A. Steps 1-4 done (F109-F110, merged 2026-09-23);
step 5 done as docs (2026-09-23); steps 6-8 done (F111-F112, 2026-09-24). 9 onward in order:

1. Scene expansion (§9): battery-container unit, ISRU donor unit, landing offload stand, habitat logistics shelf,
   depot return stand, road spurs; generalize the site model from three PDUs to a unit list; rebuild the AMCL/Nav2
   map; offline `work_stands` gate for every new tray/button; one site-acceptance run.
2. Scenarios parameterized by unit; Mission B source/destination/occupier parameterized.
3. Operator protocol in the console (§8): decision time 300 s, flight-rule grant table, HOLD reply, ALFUS labels.
4. Evaluator: rewrite `evaluation/violations.py` + recorder for the new mission_state; the §8 human-interaction
   metrics in `evaluation/`; wire the recorder into all three launch scripts.
5. **Baseline lock** (done 2026-09-23, docs only): `docs/baselines/authoring_spec.md` "Locked specification".
6. **Run farm** (§11): the whole stack as one Ubuntu 22.04 image on `pro6000` (6 x RTX PRO 6000); one equivalence
   run, then a 6-way concurrency measurement. Parallel with 7-8 (it needs no GPU of this machine's).
7. **Baselines built to the lock**, offline only (plexiltest, `sim_boundary.py` for every unit x Mission A and every
   covered cargo x destination). Parallel with 6 and 8.
8. **Physical validation of the held-out action forms** (§12): offline geometry first, then scripted chains, one
   run each. Prerequisite for every live run below -- BESS/ISRU L0/L1 already use unexecuted buttons.
9. Covered live re-runs on the final scene: PLEXIL, EUROPA, Ours x the seven covered instances of §14 (L0 and L1). One run
   each; a failure is classified by the lock's change-control table.
10. Ours development runs on the §14 held-out instances, L2-A -> L2-B -> L3 -> L4; mission-generic changes only (§13.1).
11. Manifests + closed-capability certificates; freeze audit; git tags; the frozen image is the campaign environment.
    Then the offline retry-budget sensitivity check (§7).
12. Experiment I campaign (entirely on the run farm; the three methods of a paired instance on the same hardware)
    -> §5.7 ablations -> build `scan_label` -> Experiment II -> §8 re-authoring cost per held-out case.

Cost note (measured 2026-09-23 on the development machine, sim runs at 0.17-0.31 x real time): covered baseline runs
11-24 min wall, Ours covered Mission A 46 min; held-out Ours runs estimated 1-3 h (two picks + two places, 300 s of
ground decision time ~ 20-25 min wall). Remaining live work estimated ~310 GPU-hours (±50%), ~170 of them the
campaign; a campaign rerun after a post-freeze infrastructure fix (execution_plan §13.1) adds ~170. Repetition
counts are set after the first variance is seen, not now. Superseded by §14's estimate (~70 runs).

## 11. Run farm (decided 2026-09-23)

Why: throughput, not single-run speed. Two concurrent simulations on the development machine (24 cores) is ~3 weeks
of wall for the remaining work; with `pro6000` (6 x RTX PRO 6000 96 GB, 2 x Xeon Gold 6530 / 128 threads, 503 GB,
Ubuntu 24.04, no ROS) eight run at once, ~1 week, and a campaign rerun drops from ~1 week to ~2 days. Now, before the
freeze, is the cheapest moment: the freeze pins the environment.

- **Image**: Ubuntu 22.04 (the Humble / py3.10 constraint holds inside it); the development machine's `ros-humble-*`
  package set; `~/Programs/{isaac-sim,plexil,europa,europa-deps}` and `~/isaaclab` copied as they are (no reinstall:
  the four SRB install pins stay as installed); the same user and home path. Built here, moved with rsync.
- **Code** is not baked in: the repo is synced to `pro6000` and mounted at the same absolute path
  (`/mnt/SharedData/Research/Space_Robot_Harness`, a nofail bind mount of `/nvme02/bingqi/SharedData`), so every launcher
  path is unchanged. Run directories under it (`artifacts/runs`), rsynced back for review; old development runs stay
  on the development machine.
- **One run = one container** on one GPU with its own network namespace: ROS domains and ports (EUROPA HostLink 47810)
  cannot collide. Each container is pinned to 10 physical cores + hyperthreads on its GPU's socket
  (`docker/runfarm/runfarm.sh`): two unpinned Isaac processes on one host ran at 0.05x each (F54 §4), so the
  development machine itself runs one simulation at a time.
- **Acceptance**: one covered run reproduced on `pro6000` (same outcome; sim/wall ratio recorded), then the same run 6
  ways concurrently. If the per-run sim/wall ratio under 6-way load falls far below half the development machine's
  (the Xeon's single-thread speed is lower than the desktop's), run fewer at once and re-cost from the measurement.
- The development machine stays the place for Blender, visual acceptance and debugging. The machine is shared
  (another user): take GPUs by explicit device, kill only our own PIDs.

## 12. Physical validation of the held-out action forms (decided 2026-09-23)

Why: until now only reachability (`work_stands`, the robot's own IK) and VLM readings were checked (`site_check_2-10`);
no held-out press, pick or place was ever executed. A physical failure inside a campaign run would be scored against
the coordination method, and unequally: Ours attempts the two picks + two places of L2-B/L3/L4, a baseline escalates
before reaching them. This step serves execution_plan §13.1 item 2 (validate success conditions independently of all
methods).

Never executed live so far:

| Action form | Needed by |
|---|---|
| press: BESS BMS panel (white cap), ISRU plant panel (black cap) | L0/L1 at BESS/ISRU (covered!) |
| press: PDU radiator shutter button, BESS HVAC shutter button; shutter opens, pending OVERTEMP re-trip cancelled | L2-A |
| pick/place ORU out of / into a PDU bay; self-test passes on a serviceable module, `MODULE_MISSING` on an empty bay | L3, L4 |
| battery module (BESS cradle <-> depot spares stand); filter cartridge (ISRU cradle <-> ISRU stand) | L3 at BESS / ISRU |
| ORU out of the ISRU power cradle, carried to PDU-1's bay | L4-far |
| returned crate off a PDU shelf, return container off the habitat stand, each to a free stand | L2-B |
| consumables container landing stand -> habitat stand; battery module -> BESS receiving stand | Mission B L1 |

1. **Offline first** (geometry is computed from the assets, not tried in simulation): each new item's handle is
   graspable (only the ORU's bail was ever gripped); item-on-support clearance for every item x support pair used;
   in L3/L4, a free legal support exists for the removed module; `retrip_delay_s` set from a stated thermal
   assumption (never tuned to a method).
2. **Scripted chains, not a method**: fixed call sequences through the shared capabilities (Nav2 on AMCL, as in the
   old `d0_*` oracle checks), the evaluator's truth used only to check the physical result and the site model's state
   transitions. Seven chains, each mirroring one held-out case's physical sequence: L2-A (PDU and BESS, with the BESS
   panel), L3 PDU, L3 BESS, L3 ISRU (with the ISRU panel), L4-far carry, L2-B (both occupiers), Mission B (both new
   cargos). Estimated 5-7 GPU-hours, one batch on the run farm.
3. **Criterion**: each chain completes once -- feasibility. Reliability is measured in the campaign from the per-leg
   physical-failure log (§9), never by extra reruns here. A failing action is fixed in the shared layer (asset,
   support, skill), for all methods, never worked around inside one method.

## 13. Sources (verified 2026-09-23 unless noted)

Gaier NASA/TM-2005-213610 (2005); Creel, "Coping with Dust for Extraterrestrial Exploration", DAP-2017, and TFAWS
2023 LRV thermal presentation; Metzger et al. plume ejecta (SSERVI 2019 abstract); ISS Daily Summary Report
2015-01-14; Dextre RPCM R&R, Aug 2011 (NASASpaceFlight 2011-09; Space.com); Lewis et al. ASCEND 2022 (NTRS
20220013667); 14 CFR §1214.403; Apollo 17 fender repair (Smithsonian NASM 2015); NASA Lunar Communications and
Navigation Architecture white paper (2023 ACR); Landon et al. NASA/TM-20250003885; NASA-STD-6002D (Data Matrix
marking); REALM spec sheet (NASA SSC 2024). Novelty framing: Boult et al. AAAI 2021; CADRE (Rabideau et al. AAMAS
2025) "the task network must contain all of the tasks we will ever need"; REFLECT (CoRL 2023); COWP (Auton. Robots
2023). Double-blind baseline authoring is not possible with one engineer -- state it. Protocol and expansion (§8-§9):
Lim et al. LPSC 2024 #1647 (VIPER ops); Steinfeld et al. HRI 2006; Olsen & Goodrich PerMIS 2003; Riek JHRI 2012;
NIST SP 1011-II-1.0 (ALFUS); RFC 4838; Morgan (JPL fault protection); Rabideau et al. 2025 (CADRE idle 28%); NASA ISS
blog 2019-05-02 (MBSU-3); ISS DSR 2019-04-02 and 2019-06-17; GAO/NSIAD-88-30BR; STS-120 NASA Facts; Apollo 13 Flight
Journal.

## 14. Campaign instance set (decided 2026-09-24)

Why: the paper needs a success-versus-level curve that a reviewer cannot call cherry-picked, not every unit at every
level. §9's crossing of every unit with every level (~22-28 instances, ~170 GPU-hours) is cut to one appearance per
piece of equipment per row, spread so that no unit dominates; the three PDUs are assigned to different rows. The scene
(§9) is unchanged. Limitation to state: each level is instantiated on one or two units.

| Level | Instance | Scenario / overrides |
|---|---|---|
| L0 | A: PDU-2 (communication station) trips; reset | `covered`, `faulted_unit=pdu_2` |
| L0 | B: spare ORU (depot) -> PDU-3 spares shelf | Mission B, `cargo=spare_oru destination=pdu_3` |
| L1 | A: BESS trips; reset | `covered`, `faulted_unit=bess` |
| L1 | A: ISRU plant trips; reset | `covered`, `faulted_unit=isru` |
| L1 | B: spare battery module (depot spares stand) -> BESS receiving stand | `cargo=bat_spare destination=bess` |
| L1 | B: consumables container (landing offload stand) -> habitat logistics stand | `cargo=consumables_container destination=habitat` |
| L1 | A: the report names PDU-2; the BESS is the tripped unit (both power equipment: a plausible mix-up) | `covered_misreport`, `faulted_unit=bess reported_unit=pdu_2` |
| L2-A | PDU-1 (habitat life support): radiator shutter drawn | `heldout_radiator_cover`, `faulted_unit=pdu_1` |
| L2-A | BESS: HVAC condenser shutter drawn | `heldout_radiator_cover`, `faulted_unit=bess` |
| L2-B | habitat stand occupied by the outbound return container | `heldout_destination_occupied`, `cargo=consumables_container destination=habitat` |
| L3 | BESS battery module fails self-test; spare on the depot spares stand | `heldout_module_failure`, `faulted_unit=bess` |
| L3 | ISRU filter cartridge clogged; spare on the ISRU receiving stand | `heldout_module_failure`, `faulted_unit=isru` |
| L4 | PDU-1's module failed, the depot spare is recorded failed; PDU-3 (energized, non-critical) holds the serviceable ORU: approval before loss of signal, then PDU-3 -> PDU-1 | `heldout_cannibalize` (near) |

Dropped: every other unit x level pairing, L4-far (`heldout_cannibalize_far`), the `route_block` control. L0 and L1
(seven instances) are step 9's covered set. Runs: PLEXIL and EUROPA once per instance (deterministic; 26);
Ours once per covered instance and three times per held-out instance (7 + 18 = 25); §5.7 ablations 4 x one L3
instance x 2 (8); Experiment II ~10. About 70 runs; repetitions revisited once the first held-out variance is seen.

