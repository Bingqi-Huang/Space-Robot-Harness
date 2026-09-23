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
| L4 | a goal conflict + authority | **No serviceable spare; the only one is installed in energized PDU-3 (science payload) → request ground approval before the Earth-visibility window closes, then move it to PDU-1 (life support)** (`heldout_cannibalize`) | 14 CFR 1214.403 (authorization before altering/removing property); Apollo 17 fender repair with clamps taken from the optical alignment telescope, ground-devised; NASA LCN white paper 2023 (south pole sees Earth ~half of each sidereal month) |
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
   the task like `set_status_lamp`; a dummy **blue** "RADIATOR COVER" push button on the service panel, far enough
   from the red reset button that `press`'s shape fit + pointer cannot confuse them (spacing fixed offline).
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
  awaiting return shipment); PDU-3 (science payload, energized) holds the only serviceable ORU. Removing it
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

## 8. Implementation order (each step: offline check first, then one decisive live run)

1. Docs (this commit).
2. SRB: telemetry + inventory records in the task, manifest/`power_status` queries in the capability server.
3. SRB assets: ORU bays + installed ORUs with labels, radiator + cover + cover button; offline gates of §4.
4. SRB task scenarios `covered_misreport`, `heldout_radiator_cover`, `heldout_module_failure`,
   `heldout_cannibalize`; remove dead scenarios/prop.
5. Harness: authority by target, SPICE space context + link gate, operator console + protocol, recorder wiring.
6. Baseline competence (§7).
7. Ours development runs, one per case, L2-A → L2-B → L3 → L4; failures answered only with mission-generic
   changes (execution_plan §13.1), each recorded in `docs/research_findings.md`.
8. Rewrite scenario manifests + closed-capability certificates; freeze audit; git tags.
9. Experiment I campaign → §5.7 ablations → build `scan_label` → Experiment II.

Cost note (estimate, not measured): L2-A presses only; L2-B, L3, L4 are two picks + two places (≈2–3 h wall per
run at 15–40 min per pick). Repetition counts are set after the first variance is seen, not now.

## 9. Sources (verified 2026-09-23 unless noted)

Gaier NASA/TM-2005-213610 (2005); Creel, "Coping with Dust for Extraterrestrial Exploration", DAP-2017, and TFAWS
2023 LRV thermal presentation; Metzger et al. plume ejecta (SSERVI 2019 abstract); ISS Daily Summary Report
2015-01-14; Dextre RPCM R&R, Aug 2011 (NASASpaceFlight 2011-09; Space.com); Lewis et al. ASCEND 2022 (NTRS
20220013667); 14 CFR §1214.403; Apollo 17 fender repair (Smithsonian NASM 2015); NASA Lunar Communications and
Navigation Architecture white paper (2023 ACR); Landon et al. NASA/TM-20250003885; NASA-STD-6002D (Data Matrix
marking); REALM spec sheet (NASA SSC 2024). Novelty framing: Boult et al. AAAI 2021; CADRE (Rabideau et al. AAMAS
2025) "the task network must contain all of the tasks we will ever need"; REFLECT (CoRL 2023); COWP (Auton. Robots
2023). Double-blind baseline authoring is not possible with one engineer -- state it.
