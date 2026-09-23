# Held-out design and implementation plan (decided 2026-09-23)

Supersedes the held-out selection in `docs/lunar_task_catalog.md` §5 and the old `experiments/scenarios/*/held_out/`
set. Serves research_content §5.5 (Experiment I), §5.6 (Experiment II), §5.7 (ablations), H3, and resolves the
"space-native boundary" open question (decision 2) through the L4 case.

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

## 7. Baseline competence (before freeze)

PLEXIL and EUROPA covered artifacts gain what the covered brief implies: read `power_status` to find the tripped
unit (so L1 misreport is covered), press, re-check after a dwell, generic retry-once-then-escalate, pick/place
recovery set; consolidate the duplicated NDDL. Authored from the covered specification only.

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
| Landing-pad offload stand -> habitat logistics shelf, look-alike consumables container | ship pad edge -> habitat front | B long haul (L1) | Lewis et al. 2022 p.12 (robots offload and transport logistics before crew arrival), p.19 |
| Habitat shelf occupied by an outbound return container (to a depot return stand) | habitat | L2-B replicate | ISS DSR 2019-06-17 (empty carrier removed before installing a spare; the *unexpected* occupancy is our extrapolation); Lewis et al. 2022 p.19 (trash, boneyards) |

As built (2026-09-23, redesigned after review): the scene's `units` (layout.yaml, exported to interaction.json) drive
the site model -- no unit list in code. `pdu_1` (habitat life support, crew-critical), `pdu_2` (communication station,
mission-critical), `pdu_3` (science instruments, non-critical): yellow service panel, spares shelf, ORU bay, radiator
with shutter. `bess` (battery storage, mission-critical; the container stands on the pad, the source model's plinth cropped
away): wall-mounted BMS enclosure with a graphite control panel (white reset cap), battery-module cradle (BAT-0101,
0.29 x 0.42 x 0.367 m so its handle sits at the ORU's height; spare BAT-0102 on the depot spares stand), HVAC condenser
with shutter and blue actuator button. `isru` (ISRU oxygen plant, non-critical, no shutter): plant control panel
(black reset cap, dark readout; inspected from 2.0 m), filter-cartridge cradle (FLT-0201; spare
FLT-0202 on the ISRU receiving stand) and power-ORU cradle (ORU-0285). Reset caps are never red or green (IEC
60204-1 §10.2.1): red and green appear only on status lamps. A closed breaker trips after the self-test with
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
SPICE link + gated console, competent PLEXIL/EUROPA Mission A. Remaining:

1. Scene expansion (§9): battery-container unit, ISRU donor unit, landing offload stand, habitat logistics shelf,
   depot return stand, road spurs; generalize the site model from three PDUs to a unit list; rebuild the AMCL/Nav2
   map; offline `work_stands` gate for every new tray/button; one site-acceptance run.
2. Scenarios parameterized by unit; Mission B source/destination/occupier parameterized.
3. Operator protocol in the console (§8): decision time 300 s, flight-rule grant table, HOLD reply, ALFUS labels.
4. Evaluator: rewrite `evaluation/violations.py` + recorder for the new mission_state; the §8 human-interaction
   metrics in `evaluation/`; wire the recorder into all three launch scripts.
5. Baselines cover every unit (L0/L1 parameterized), pick/place recovery set, consolidated NDDL, Mission B brief
   checks; re-run covered live for all three methods on the final scene.
6. Ours development runs L2-A -> L2-B -> L3 -> L4 (near, then far); mission-generic changes only (§13.1).
7. Manifests + closed-capability certificates; freeze audit; git tags.
8. Experiment I campaign -> §5.7 ablations -> build `scan_label` -> Experiment II.

Cost note (estimate, not measured): L2-A presses only; L2-B, L3, L4 are two picks + two places (~2-3 h wall per
run at 15-40 min per pick); L4-far and the B long haul add driving. Repetition counts are set after the first
variance is seen, not now.

## 11. Sources (verified 2026-09-23 unless noted)

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
