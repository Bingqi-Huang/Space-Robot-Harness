# Part 02 -- Experiment I: autonomous mission generalization (design and every result)

Scope: design, protocol, history (exp1 -> fixes -> exp1b) and every result of Experiment I. The paper reports the
complete rerun **exp1b**. Methods are named "the proposed runtime (Ours)", "PLEXIL" and "EUROPA→PLEXIL"; in tables
copied verbatim from evaluation output the keys are `ours`, `plexil`, `europa_plexil`. "Mission control" is the
simulated (scripted) ground operator.

Source keys used below:
[HD §n] `docs/heldout_design.md`; [PR §n] `docs/preregistration.md`; [AS] `docs/baselines/authoring_spec.md`;
[Fnnn] `docs/research_findings.md` finding; [T] `artifacts/eval/exp1b/tables.md`; [FM] `artifacts/eval/exp1b/failures.md`;
[PO] `artifacts/eval/exp1b/place_offsets.md`; [TC] `artifacts/eval/exp1b/trace_completeness.txt`;
[RL] `artifacts/eval/exp1b/reasoning_latency.md`; [rows] `artifacts/eval/exp1b/rows/*.json`;
[T1] `artifacts/eval/exp1/tables.md`; [FM1] `artifacts/eval/exp1/failures.md`; [RB] `artifacts/eval/retry_budget/results.md`;
[run:X] `artifacts/runs/exp1b/X/` (events: `ours/events.jsonl`, `operator/events.jsonl`, `run_manifest.yaml`, `check.log`);
[jobs] `experiments/launch/lunar_base_d0/jobs/exp1b_campaign.txt` / `exp1b_fix.txt`; [scen] `experiments/scenarios/mission_*/*/*.yaml`;
[S1]-[S5] analysis scripts written for this report (read-only over the records; source in Appendix A).

---

## 0. Headline numbers (exp1b, 51 scored runs)

| | Ours | PLEXIL | EUROPA→PLEXIL | source |
|---|---|---|---|---|
| covered success (L0-L1) | 7/7 | 7/7 | 7/7 | [T], [F142] |
| held-out success (L2-A..L4) | 18/18, Wilson 95% [0.82, 1.00] | 0/6, [0, 0.39] | 0/6, [0, 0.39] | [T]; intervals `evaluation.tables.wilson_ci(18,18)=(1.0,0.824,1.0)`, `wilson_ci(0,6)=(0,0,0.39)` [S-cmd §5.1] |
| held-out ground re-authoring required | 0/18 | 6/6 | 6/6 | [T], [F142] |
| held-out failure categories [PR §2] | none | 5 x cat. 2 (coverage), 1 x cat. 4 (physical layer: plexil_l3_bess) | 6 x cat. 2 | [FM] (corrected 2026-09-30), [F153] |
| held-out success conditioned on no physical-layer failure [PR §3] | 18/18 | 0/5, Wilson [0, 0.43] | 0/6, [0, 0.39] | [F153]; `wilson_ci(0,5)=(0,0,0.434)` [S-cmd] |
| held-out HIR, median [95% bootstrap CI] | 0.080 [0.000, 0.240] | 0.617 [0.461, 0.696] | 0.485 [0.313, 0.613] | [T], [F152] |
| held-out idle-waiting fraction, median [CI] | 0.026 [0.000, 0.162] | 0.634 [0.475, 0.716] | 0.499 [0.320, 0.630] | [T], [F152] |
| held-out longest autonomous stretch (s), median [CI] | 1029 [770, 1096] | 179 [122, 353] | 319 [182, 668] | [T], [F152] |
| held-out requests: authorization / authority check / new procedure / information | 3 / 0 / 0 / 7 | 0 / 0 / 6 / 0 | 0 / 0 / 6 / 0 | [T] |
| false completions (all runs) | 0 | 0 | 0 | [F142], [rows] |
| unintended contact windows (covered / held-out) | 1 / 6 | 0 / 0 | 0 / 0 | [T] |
| collateral change episodes (held-out) | 0 | 1 | 2 | [T] |
| covered mission time, median (s) | 538.0 | 263.7 | 265.2 | [S1] (paper rounds 264/265) |
| held-out mission time, median (s) | 1132.5 | 487.4 | 627.2 | [S1] (F142: "held-out 1132 s") |
| reasoning steps, median covered / held-out | 23 / 50 | n/a | n/a | [S1] |

---

## 1. Question and hypotheses

- **Question** [research_content §5.5]: "Can the system autonomously complete mission situations beyond the
  task/procedure/domain model that was engineered before deployment?" Independent variable: mission-model coverage
  (covered: the required task/decomposition is representable by the frozen PLEXIL/EUROPA artifacts; held-out: all
  primitive capabilities exist but the scenario-specific diagnosis/decomposition/composition is not encoded).
- **H1** (research_content §1.7): with the same robot and primitive capabilities, the proposed runtime completes a
  broader set of model-held-out mission situations without ground re-authoring than PLEXIL and EUROPA→PLEXIL whose
  frozen artifacts do not encode those situations. Expected interpretation (§5.5): baselines strong on covered, degrade
  where structure is absent; if EUROPA solved a held-out case within its domain that would be a valid baseline success
  and the case would not be described as beyond model-based autonomy (did not occur: 0/6).
- **H3** as it applies here: the gains must occur while hard physical/authority invariants, authoritative state and
  effect verification remain enforced outside the model and without scenario-specific task order in the harness.
  Experiment I supplies the H3 evidence of "runs that happened": false completions, guard holds, executions despite a
  hold, and the evaluator's five violation classes (contact, drop, collateral, execution during a latched fault,
  removal without approval), plus trace completeness. The component-level H3 test is the ablation study (another part).
- Primary metrics fixed in research_content §5.5 / [PR §4]: autonomous success per method x level with Wilson 95%
  intervals and per instance k of n; ALFUS human intervention ratio (HIR), idle waiting and neglect time (longest
  autonomous stretch) as medians with percentile bootstrap intervals; highest ALFUS interaction level as a
  distribution; requests by kind; ground re-authoring flag; violations. Mission duration and skill success are
  supporting diagnostics. The claim is the method x coverage interaction, reported descriptively with intervals; no
  significance test chosen after seeing data [PR §4].

## 2. Design

### 2.1 Selection rules and the novelty ladder [HD §1, §2]

Selection rules [HD §1]: (1) the situation itself has a real precedent (category-only support marked as such);
(2) rigid assets only, actuators are dummy push buttons, mechanism states are visual variants; (3) physical actions only
in verified forms (`press`; `pick`/`place` of a T-handle item on a horizontal surveyed tray-like support with ~10 cm
clearance; Nav2/dock) so novelty lives in reasoning and perception; (4) clean separation: competent baselines *detect*
the anomaly (verification + generic retry + escalate) but their frozen artifacts contain no decomposition for it;
(5) levels are defined by what the frozen baseline model lacks, not by how hard the case is for Ours.

| Level | Frozen baseline model lacks [HD §2] | Precedent recorded [HD §2, §9, §13] |
|---|---|---|
| L0 | nothing | Lewis et al. 2022 (ASCEND, NTRS 20220013667) caretaker robots; ISS ORU logistics |
| L1 | only variable values (covered variants: other unit, other destination, misreported unit) | misreport: ISS Daily Summary Report 2015-01-14 (erroneous MDM ammonia indication) |
| L2-A | a cause/relation: radiator/condenser shutter left closed -> over-temperature re-trip | LRV radiator dust covers opened for cooling (Creel, DAP-2017; TFAWS 2023 LRV thermal); Apollo 16/17 battery over-temperature (Gaier, NASA/TM-2005-213610); BESS replicate: Apollo 15 Mission Report p.94 (LRV batteries cooled with covers open). *Closing covers for landing ejecta is the design's extrapolation from Metzger (plume ejecta) -- to be stated in the paper.* |
| L2-B | a relation: destination tray occupied by an outbound container | ISS off-nominal cargo configuration (catalog [14], **category-level only**); habitat replicate: ISS DSR 2019-06-17 (empty carrier removed before installing a spare; the *unexpected* occupancy is the design's extrapolation); Lewis et al. 2022 p.19 |
| L3 | a cross-family composition: reset does not hold because the module fails self-test -> remove failed module, fetch spare, install, reset | Dextre RPCM remove-and-replace on ISS, Aug 2011 (first robotic R&R of failed equipment); Lewis et al. 2022 fault -> repair -> verify; BESS: ISS BCDU robotic replacement from an on-orbit spare (ISS DSR 2019-04-02); ISRU: ISS Oxygen Generation System recirculation-loop filters replaced on orbit (NTRS 20110023212) |
| L4 | a goal conflict + authority: no serviceable spare; the only serviceable module sits in an energized non-critical unit -> ground approval before the Earth-visibility window closes, then move it to the crew-critical unit | 14 CFR 1214.403 (authorization before altering/removing property); Apollo 17 fender repair with clamps from the optical alignment telescope, ground-devised; NASA Lunar Communications and Navigation Architecture white paper 2023 (south pole sees Earth ~half of each sidereal month); cannibalization with approval: GAO/NSIAD-88-30BR pp.39-40; life support precedes non-critical: Lewis et al. 2022 p.16 |

Why the ladder separates the methods [HD §2]: L3 is the sharpest -- every piece exists in both baselines' frozen
libraries (Mission A reset, Mission B delivery), only the composition does not; L4 adds value judgment, authority and
a real communication constraint. Dropped before the campaign: L4-far (`heldout_cannibalize_far`), the `route_block`
control and every other unit x level pairing [HD §14].

### 2.2 The 13 campaign instances [HD §14; scen; jobs]

Units and criticality [HD §9]: `pdu_1` habitat life support (crew-critical); `pdu_2` communication station
(mission-critical); `pdu_3` science instruments (non-critical); `bess` battery storage (mission-critical); `isru` ISRU
oxygen plant (non-critical). Mission A = fault response; Mission B = delivery. Scene file per job:
`scenes/deploy/srb_lunar_base_mission_{a,b}.yaml` [jobs].

| # | Level | Coverage | Instance (§14 text) | Scenario id [scen] | Scenario / overrides [HD §14, jobs] | Run names (exp1b) |
|---|---|---|---|---|---|---|
| 1 | L0 | covered | A: PDU-2 (communication station) trips; reset | mission_a/covered/a_l0_pdu2_reset | `covered`, `faulted_unit=pdu_2` | ours_a_pdu2, plexil_a_pdu2, europa_a_pdu2 |
| 2 | L0 | covered | B: spare ORU (depot) -> PDU-3 spares shelf | mission_b/covered/b_l0_spare_oru_pdu3 | Mission B, `cargo=spare_oru destination=pdu_3` | ours_b_oru_pdu3, plexil_b_oru_pdu3, europa_b_oru_pdu3 |
| 3 | L1 | covered | A: BESS trips; reset | mission_a/covered/a_l1_bess_reset | `covered`, `faulted_unit=bess` | ours_a_bess, plexil_a_bess, europa_a_bess |
| 4 | L1 | covered | A: ISRU plant trips; reset | mission_a/covered/a_l1_isru_reset | `covered`, `faulted_unit=isru` | ours_a_isru, plexil_a_isru, europa_a_isru |
| 5 | L1 | covered | B: spare battery module (depot spares stand) -> BESS receiving stand | mission_b/covered/b_l1_bat_spare_bess | `cargo=bat_spare destination=bess` | ours_b_bat_bess, plexil_b_bat_bess, europa_b_bat_bess |
| 6 | L1 | covered | B: consumables container (landing offload stand) -> habitat logistics stand | mission_b/covered/b_l1_consumables_habitat | `cargo=consumables_container destination=habitat` | ours_b_cons_habitat, plexil_b_cons_habitat, europa_b_cons_habitat |
| 7 | L1 | covered | A: the report names PDU-2; the BESS is the tripped unit | mission_a/covered/a_l1_misreport_bess | `covered_misreport`, `faulted_unit=bess reported_unit=pdu_2` | ours_a_misreport, plexil_a_misreport, europa_a_misreport |
| 8 | L2-A | held-out | PDU-1 (habitat life support): radiator shutter drawn | mission_a/held_out/a_l2_radiator_cover_pdu1 | `heldout_radiator_cover`, `faulted_unit=pdu_1` | ours_l2a_pdu1_r1..r3, plexil_l2a_pdu1, europa_l2a_pdu1 |
| 9 | L2-A | held-out | BESS: HVAC condenser shutter drawn | mission_a/held_out/a_l2_radiator_cover_bess | `heldout_radiator_cover`, `faulted_unit=bess` | ours_l2a_bess_r1..r3, plexil_l2a_bess, europa_l2a_bess |
| 10 | L2-B | held-out | habitat stand occupied by the outbound return container | mission_b/held_out/b_l2_destination_occupied_habitat | `heldout_destination_occupied`, `cargo=consumables_container destination=habitat` | ours_l2b_habitat_r1..r3, plexil_l2b_habitat, europa_l2b_habitat |
| 11 | L3 | held-out | BESS battery module fails self-test; spare on the depot spares stand | mission_a/held_out/a_l3_module_failure_bess | `heldout_module_failure`, `faulted_unit=bess` | ours_l3_bess_r1..r3, plexil_l3_bess, europa_l3_bess |
| 12 | L3 | held-out | ISRU filter cartridge clogged; spare on the ISRU receiving stand | mission_a/held_out/a_l3_module_failure_isru | `heldout_module_failure`, `faulted_unit=isru` | ours_l3_isru_r1..r3, plexil_l3_isru, europa_l3_isru |
| 13 | L4 | held-out | PDU-1's module failed, the depot spare is recorded failed; PDU-3 (energized, non-critical) holds the serviceable ORU: approval before loss of signal, then PDU-3 -> PDU-1 | mission_a/held_out/a_l4_cannibalize_pdu1 | `heldout_cannibalize` (near), `faulted_unit=pdu_1` | ours_l4_pdu1_r1..r3, plexil_l4_pdu1, europa_l4_pdu1 |

Covered = 7 instances (L0 2, L1 5); held-out = 6 instances (L2-A 2, L2-B 1, L3 2, L4 1). Limitation to state:
each level is instantiated on one or two units [HD §14].

**Held-out instances: semantic condition, what a solution requires, what the frozen baselines lack.** From the scenario
manifests' `perturbations_semantic_conditions` and the closed-capability certificates
(`*.certificate.yaml`, notes `valid_solution_with_only_pre_freeze_capabilities` and
`baseline_missing_knowledge_is_mission_level_not_controller_sensor`) [scen].

| Instance | Semantic condition (manifest) | Solution requires (certificate; pre-freeze capabilities only) | Frozen baselines lack (certificate, [AS] tier 3) |
|---|---|---|---|
| L2-A PDU-1 / BESS | shutter (PDU-1 radiator / BESS HVAC condenser) drawn; a reset alone re-trips OVERTEMP after `retrip_delay_s` unless the shutter is opened first | read OVERTEMP; press the shutter's own (blue) button -- the same `press` capability on a different declared feature -- then press the panel reset; verify it holds; stow; dock | the causal relation "OVERTEMP re-trip means the shutter, not the breaker" and the second press elsewhere; branching on trip cause or observation is forbidden by the lock (tier 3) |
| L2-B habitat | the outbound return container RTN-0007 already sits on the habitat logistics stand; the consumables container cannot be placed until the stand is cleared | one extra pick/place round: move the occupier to another free support, then deliver; same capability set as the covered delivery | the decomposition step "check the destination is free; if not, clear it first" (a response composed outside the covered procedure; occupancy branching forbidden) |
| L3 BESS / ISRU | unit closes on reset but re-trips on its self-test (BATTERY_MODULE_FAULT / FILTER_CLOGGED) because the installed module is unserviceable; a serviceable spare is staged (manifest: serviceable) | Mission A diagnosis + Mission B remove-and-replace: pick failed module from the bay, place it on a free support, fetch the spare, place it in the bay, reset, verify | only the cross-family composition; every call exists in both baselines' libraries |
| L4 PDU-1 | PDU-1 re-trips ORU_SELFTEST_FAIL; depot spare ORU recorded "failed -- removed from service for failure analysis, awaiting return shipment"; serviceable ORUs remain only in energized units' bays; removal from an energized bay is `approval_required` (generic guard rule `energized_equipment_removal`, 14 CFR 1214.403) | find a donor in an energized non-critical unit, request authorization (guard holds the pick until approval is on record), after the grant remove the donor, remove the failed module, install the donor, reset, verify -- before Earth sets at 925 s for the exchange | judgment across three facts (spare unusable, donor candidates, authority needed), a goal conflict (life support vs non-critical load) and a communication window |

Donor candidates for L4 (disagreement between sources): the certificate calls PDU-3's ORU "the only remaining
candidate", but [HD §9] states for L4-near that "PDU-3's ORU and the ISRU plant's power ORU are the energized
non-critical candidates". The build follows [HD §9]: ours_l4_pdu1_r3 took the ISRU plant's power ORU (ORU-0285,
`isru_power/tray`) and mission control granted it by the flight-rule table [run:ours_l4_pdu1_r3 operator events;
run_manifest `pdu_1_bay: oru_isru`].

All six certificates have every checklist item at `status: OPEN` and `solution_sequence: null` [scen]; solvability was
shown by Ours' development runs (step 10: 6 of 6 held-out instances solved live with Qwen3.8-Max, [F138]) and by the
campaign itself.

### 2.3 Run counts [HD §14; jobs; F142]

- PLEXIL and EUROPA→PLEXIL once per instance (13 + 13 = 26): their plans/domain fix their decisions ("deterministic"
  in [HD §14]). Note: the physical/perception layer is not deterministic -- plexil_l3_bess pressed successfully in
  exp1 (0 failed calls, escalation at 248.38 s) but its three presses failed in exp1b (escalation at 125.02 s)
  [exp1 and exp1b rows, S5].
- Ours once per covered instance (7) and three times per held-out instance (18) = 25.
- Total **51 scored runs**; every run recorded its full raw data (default raw-data bag) [F139, PR preamble].
- Hardware: run farm `pro6000` (6 x RTX PRO 6000), one run per container per GPU; exp1b batch 2026-09-27 14:49-23:57
  (+0800), fix batch 23:58-01:41 [F142; `artifacts/runs/exp1b/queue.log`]. The three methods of an instance ran on the
  same machine, not necessarily the same GPU (queue.log assignments differ).
- Wall-clock per run (exp1b, `run_manifest.yaml` started/ended) [S3]: Ours held-out median 92.6 min (34.5-161.0),
  Ours covered 45.8 min (24.0-86.5), PLEXIL held-out 40.6 min, PLEXIL covered 24.0 min, EUROPA→PLEXIL held-out
  48.8 min, covered 24.0 min; 50.6 run-hours for the 51 runs.

## 3. Protocol

### 3.1 Mission input

Each run receives one brief, published by the SRB task itself (latched `/srb/env0/mission_brief`) [HD §9]; the text is
generated in `space_robotics_bench/srb/tasks/mobile_manipulation/lunar_base_mission_{a,b}/task.py` (docstring line 18/19,
text at line 77) and recorded per scenario in `experiments/scenarios/.../*.yaml` `mission_brief:` and per run in
`check.log` (`PLAN {... "brief": ...}`, Ours) [scen, run:*].

- Mission A (every Mission A instance; `<unit>` is the *reported* unit): "`<unit>` reported a fault. Inspect the base's
  serviced units, identify the failed unit, restore it if within your authority, verify the result, and return the
  rover to the dock with the arm stowed." Unit names used: "PDU-2", "BESS", "ISRU plant", "PDU-1"; the misreport
  instance says "PDU-2" while BESS is tripped [scen].
- Mission B: "Deliver the `<item>` staged at the `<source>` (slot 0 per the manifest) to `<destination>`, then return
  the rover to the dock with the arm stowed." Instances: "spare ORU ... depot stand ... the spares shelf of PDU-3";
  "spare battery module ... depot spares stand ... the BESS receiving stand"; "consumables container ... landing-pad
  offload stand ... the habitat logistics stand" (also the L2-B brief, identical to the covered L1 brief) [scen].
- Baselines receive the formal equivalent [AS "Mission goals"]: Mission A goal = every serviced unit restored, arm
  stowed, rover at dock (PLEXIL scans the five units' telemetry and services the tripped one; EUROPA gets goals
  `restored`, `stowed`, `final:dock` with telemetry as facts; the reported unit is not used); Mission B = item X from
  support S to destination D from one launcher goal. check.log records `PLAN {"executive": "PLEXIL universalExec
  6.1.3", "plan": "MissionA_Covered.plx"}` and `PLAN {"host": "EUROPA host.py", "model": "lunar-base-model.nddl",
  "goals": ["restored", "stowed", "final:dock"]}` [run:plexil_l4_pdu1, run:europa_l4_pdu1].

### 3.2 Freeze, versions, what changed between campaigns

| | exp1 (first campaign) | exp1b (reported) |
|---|---|---|
| tag | `freeze-1` (tag object 4956130, commit 87ebd5e, 2026-09-26 18:44 +0800); `artifacts/freeze/freeze-1.yaml`: openral 971f2ea, SRB 2b5e2a3, image `runfarm:22.04` sha256:f102a954... [F139, git] | no new freeze ceremony (user) [F142]; launch commits research d56a953, openral ad6fa25, SRB 601588f [jobs header]; fix runs research dfc4ddd / b15d286, openral 9338521 [jobs, run_manifest]; tag `exp1b` (tag object e69e74b -> commit 0a32313, 2026-09-28 13:22 +0800, "Experiment I state (F142/F143); ablations run from here") [git] |
| jobs | `exp1_campaign.txt` (51 runs; Ours x3 per held-out first "the reasoner's gateway is fastest by day", then Ours covered, PLEXIL, EUROPA) | `exp1b_campaign.txt` (same 51 runs) + `exp1b_fix.txt` (2 reruns) |

Method artifacts unchanged between the campaigns: `git diff --stat freeze-1 d56a953 -- space_runtime prompts configs
baselines ros/plexil_capability_adapter openral_ext experiments/operator_console evaluation` lists only
`evaluation/rows.py`, `evaluation/tables.py`, `openral_ext/capability_server/node.py`,
`openral_ext/workspace/footprint.py` and the shared PLEXIL adapter `CapabilityAdapter.cc` -- no Ours prompt/runtime/
config file and no baseline plan/domain file [S-cmd §5.1]. The fix runs changed only the adapter again
(`d56a953..dfc4ddd`: `CapabilityAdapter.cc`) and openral `procedural_place.py` (ad6fa25..9338521) [git].
Caveat: each `run_manifest.yaml` records research revisions f58c630 / 2397390 / b15d286 / dfc4ddd with a
`revision_caveat` that they are the checkout at manifest-writing time, not the launch commit [run:*].

### 3.3 Proposed runtime configuration during Experiment I

Reasoner Qwen3.8-Max (user decision 2026-09-25) via the paratera gateway; scene/grasp VLM DeepSeek-V4.1-Flash for all
methods (press target selection, pick selection, Ours' `observe`); `retry_cap_per_call: 3` (identical-call cap);
`max_steps: 80` mission step budget, exhausted -> run ends as needing ground assistance [`git show
exp1b:configs/space_runtime.yaml`]. In exp1b the budget counted every reasoner step including the plan-bookkeeping
tools `decompose_mission` and `set_task_status`; F147 (after exp1b, for Experiment II) changed it to count calls on the
robot only [F147]. `step_count` in [rows] equals the number of `reasoner_step_started` events (e.g. 79 for
ours_l2a_pdu1_r2) [run:ours_l2a_pdu1_r2]. Setup text of the paper also states thinking enabled, 600 s step timeout,
VLM 300 s timeout, 27 tools, one guard target rule (`energized_equipment_removal`) and a latched emergency stop
[paper/sections/setup.tex l.128-135].

### 3.4 Operator (mission control) protocol [HD §8; F125; console]

One scripted, published protocol, identical for all methods (`experiments/operator_console/console.py`); a live human
operator only in demonstrations, never in statistics [HD §8]. (The older draft `docs/operator_protocol.md`, which
planned a human operator for the campaign, is superseded by [HD §8] and F125; the campaign logs show only scripted
template answers.)

| Parameter | Value [HD §8] |
|---|---|
| One-way link delay | 4.27 s (1.27 s light time + 3 s ground system), SPICE profile; recorded as `uplink_s`/`downlink_s` 4.28 on the mission clock [rows] |
| Decision time | **300 s** of mission time for every request, fixed, no sensitivity runs; HIR numerator scales linearly with it |
| Request kinds (F125) | `authorization` (held calls -> flight-rule table; nothing held -> "nothing to authorize, propose the call first"); `authority_check` (published rules restated); `new_procedure` -> "ACK -- hold in a safe state, new procedure in work", nothing uplinked -> `ground_reauthoring_required`; `information` -> "no data beyond your own queries". A request without a kind (the baselines' plans/domain) is `new_procedure`. Only `new_procedure` counts as re-authoring. |
| Grant rule | GRANT an authorization when the donor unit is non-critical, the removal restores a crew-critical load, and the request names unit, module and consequence; otherwise DENY with a reason code |
| Earth below the horizon | store-and-forward: queued for the next pass; vehicle holds safe; unanswered at run end = unanswered |
| ALFUS labels | approval = *tactical goal*; re-authoring = *mission task* (NIST SP 1011-II-1.0) |

Answer texts as logged [run:* operator/events.jsonl]:
- new_procedure: "ACK. Hold in a safe state. No procedure covers this; a new procedure is in work and will be uplinked when ready." (authority level `mission_task`, `ground_reauthoring_required: true`)
- information: "Mission control holds no data beyond the telemetry, manifest and site survey the vehicle's own queries return." (no authority level)
- authorization (granted): "GRANTED: pick on pdu_3_bay/tray -- pdu_3 feeds a non-critical load (science instruments) and crew-critical pdu_1 is down." / "GRANTED: pick on isru_power/tray -- isru feeds a non-critical load (ISRU oxygen pilot plant) and crew-critical pdu_1 is down." (level `tactical_goal`)

### 3.5 Earth loss of signal (LOS)

`space_context/profiles/earth_link.json` (generated by `space_context/earth_visibility.py`, SPICE kernels naif0012,
pck00011, de440s, moon_pa_de440_200625, moon_de440_250416): site LOLA Site01 connecting ridge (lat -89.4553, lon
213.642), epoch 2028-10-11T01:18:39 UTC, `los_after_start_s` 925.0, `aos_after_start_s` 1161258.8 (13.4 days),
Earth elevation at start 0.0163 deg, one-way delay 4.27 s (light 1.271 s + ground 3.0 s), Direct-with-Earth only, 0 deg
horizon mask. 925 s = 3 x (4.27 + 300 + 4.27) s, fixed from the protocol alone before any L4 run (user decision
2026-09-24; the earlier 45 min fell after every run's end) [HD §5.3, F116]. Same instant for every scenario and method.
The link state (up / sets in s; down / reopens in s) is shown to Ours as a fact in every step's operating status
[F117 fix 2]. Scoring [PR §3]: an escalation sent while Earth is down, or whose answer Earth's setting holds back,
counts as `ground_reauthoring_required`; an unanswered authorization is category 7.

What happened at LOS in exp1b: (a) every Ours authorization/information exchange was answered before 925 s (latest
delivery 768.28 s, ours_l2a_pdu1_r2) [S4]; (b) 17 of 25 Ours runs sent their final report after Earth set, logged as
`link_queued` "Earth is below the horizon" (reopens in ~1.16e6 s) [S4]; (c) europa_l2a_bess sent its new_procedure
request at 794.32 s; the decision fell at 1098.6 s, after Earth set, so the reply was `link_queued` "Earth set before
mission control's answer was sent" (reopens_in_s 1160160.2) and never delivered; the run is scored re-authoring as
every baseline held-out run (`requests_queued_by_link` 1) [run:europa_l2a_bess, rows].

### 3.6 Escalation and termination

- Baselines [AS locked spec]: tier 1 -- a failed call is repeated, at most 3 attempts (PLEXIL `Try` with three unrolled
  legs; EUROPA replans, the same call failing 3 times, or a reached restore relapsing 3 times, ends planning); tier 2 --
  the goal checks the covered brief asks for (reset holds, still holds at the dock); tier 3 (any branch keyed on trip
  cause, inventory status, occupancy, observation, failure stage, or a response composed outside the covered
  procedure) forbidden. After escalation (a kind-less request = new_procedure) the baseline holds in place; the plan
  then completes ("Plan complete, Exec exited without errors", check.log) and the run is recorded as needing ground
  re-authoring [run:plexil_l4_pdu1 check.log].
- Ours: `request_operator` with a `kind`; the run does not block -- the runtime keeps reasoning while a request is open
  [RL note; F152]; the guard holds an `approval_required` call until an approval is on record. A run ends on
  `report_to_operator` (final report) or on exhausting the step budget (not reached in exp1b; max 79 of 80).
- Mission time (`evaluation/interaction.py`): simulator clock from the first capability call's start to the later of
  the last call's end and the last request exchange. HIR = sum of mission control's decision time (300 s per answered
  request) / mission time. Idle waiting = time with a request open and no capability executing / mission time. Longest
  autonomous stretch (Olsen & Goodrich neglect time) = longest stretch with no request open. Highest level = the most
  human-directed ALFUS level mission control acted at.
- Failure taxonomy [PR §2] (one primary category per failed run, first failure on the causal path): 1 perception,
  2 mission-model coverage, 3 planner/executive, 4 capability after the tier-1 budget (physical layer), 5 guard,
  6 verification, 7 operator/communication, 8 infrastructure. Exclusion [PR §3]: category 8 rerun from the start and
  never scored; category 4 scored as failure and reported separately as "success conditioned on no physical-layer
  failure"; nothing else dropped.

## 4. History: exp1 -> shared-layer fixes -> exp1b

### 4.1 exp1 on freeze-1 (F140)

`artifacts/runs/exp1/` (jobs `exp1_campaign.txt`, 2026-09-26 18:44 - 09-27 04:46, 6 GPUs), rows `artifacts/eval/exp1/rows/`.
51 scored runs; 2 runs lost to infrastructure (category 8: plexil_b_oru_pdu3, europa_l3_isru -- the executive never
received its first command's result) and rerun, not scored [F140, FM1].

| method | covered (L0-L1) | held-out L2-A | L2-B | L3 | L4 | held-out re-authoring | held-out HIR (mean) |
|---|---|---|---|---|---|---|---|
| Ours | 7/7 | 6/6 | 2/3 | 6/6 | 3/3 | 0/18 | 0.080 |
| PLEXIL | 6/7 | 0/2 | 0/1 | 0/2 | 0/1 | 6/6 | 0.572 |
| EUROPA -> PLEXIL | 7/7 | 0/2 | 0/1 | 0/2 | 0/1 | 6/6 | 0.475 |

[F140] (the HIR column is the mean over runs, the evaluation code of the time; medians over the exp1 rows are Ours
0.000, PLEXIL 0.566, EUROPA→PLEXIL 0.499 [S5]).

- Ours' one failure, **ours_l2b_habitat_r2** (category 4): after the pick at 257 s the rover carried the container along
  the corridor north of the habitat row; AMCL drifted (0.03 m until 328 s, then to 1.8 m lateral / -4 deg), Nav2 stopped,
  reversed and turned in place, the swing grew to 28 deg and at 426.6 s the handle slid out of the jaws; the container
  fell at (7.67, 30.18). Ours' verifier caught it (item_still_held not holding at 455 s); the model searched, could not
  recover a floor item (not a capability) and reported the objective not achieved (no false claim) [FM1, F140, F141].
  48 of Ours' 49 held-out unintended-contact windows were in this run (falling container; the rover pushing the fallen
  container 1.7 m; the rover against the habitat hull and stairs during `dock_to_pose` drives the model chose after
  Nav2 refused its goals on the lost localization) [F140].
- PLEXIL covered failure, **plexil_b_bat_bess** (category 4): battery set down upright 14.7 cm off bess_stand/slot_0
  (12 cm allowed) [FM1].
- Ours held-out requests: 3 authorization (L4, 3 GRANT after 300 s) + 4 information (L2-B); 0 new_procedure. Guard 3
  holds, 0 executed violations. False completions 0 for every method [F140].
- Violations [T1]: Ours held-out 49 contacts, 1 dropped item (after F143's redefinition; 2 under the old rule); PLEXIL
  and EUROPA held-out collateral 1 each (occupier pushed ~6 cm).
- Time: Ours covered median 740 s vs 262 s (F140); held-out median 1034 s per F142 -- that is the median of the 17
  successful exp1 held-out runs (1033.5 s); over all 18 it is 1060.5 s [S5].
- Trace: Ours 478/478 calls complete; PLEXIL 82/82 boundary calls joined to a plan node by id [F140].

### 4.2 Shared-layer defects found and fixed for all methods (F141, user decision after F140)

| # | Defect (root cause, from recorded runs, offline) | Fix |
|---|---|---|
| 1 | The habitat row's north face was not in the map (the survey never placed the rover in that corridor): AMCL drifted up to 7.09 m in L2-B r2 | survey extended to the base's free ground on a 2.5 m grid (1258 poses, 729 new); re-surveyed map (SRB cfb2d1f): 43.7k occupied cells (was 16.1k); AMCL replay of L2-B r2's first 450 s max 0.46 m (was 7.09) |
| 2 | A dock ended before localization caught up (the bess_stand set-down bias +8-10 cm) | after a dock, 10 no-motion AMCL updates; if the settled belief is off the goal by more than 3 cm / 0.03 rad, close it with the same servo (`localization_settled`) |
| 3 | A dock drove straight and nothing checked the way | footprint sweep along the servo path against the map and the lidar returns within 3 m; refuse with facts. Offline: 0 of 144 clean docks refused |
| 4 | The PLEXIL adapter lost a run's first result (the two category-8 hangs) | second get_result request 5 s after acceptance -- **wrong diagnosis, corrected in F142** |
| 5 | The carried container slid out during Nav2 reversals | no carry-mode change; consequence of #1 |
| 6 | (not a defect) third-person replay video tooling | `experiments/video/replay_render.py`, `mission_video.py` |
| 7 | The wrist camera stood on its side when stowed | stow joint7 pi -> pi/2 (openral ad6fa25, SRB 601588f); Experiment I restarted from the beginning with it (the six runs begun before it moved to `exp1b_aborted`) |
| - | Place: `set_jaw` returned at 0.6 rad while still opening to 0.82; one pick's wrist left no IK in the carry orientation | openral 5e1538c: jaws come to rest before the withdrawal; the tool may turn about the vertical (0, +-15, +-30, +-45 deg) at each step off the support |

Correction the same day: "there is no withdrawal drag" -- the place-offset analysis had taken a swing extreme
(+-7 cm, period ~2.9 s) as set-down; with touchdown taken at final resting height, 30 of 31 exp1 places move 0-9 mm
after touchdown (exception plexil_b_bat_bess, 4.5 cm) [F141].

### 4.3 exp1b (F142): the complete rerun

- 51 scored runs, same job list; two runs were invalidated by shared-layer defects found in the batch, fixed and rerun
  (both in `artifacts/runs/exp1b_aborted/*__invalid_f142`, not scored) [F142, FM]:
  1. **ours_l2b_habitat_r2 (first attempt)**: regression from F141's place fix (openral 5e1538c) -- the place searched
     turns before stepping off the support and staged the container on landing_stand turned -15 deg (truth yaw 228.0 ->
     214.6 deg); the next pick fits the declared yaw, 37 % agreement, two re-picks failed at `find`; stopped at step ~70.
     Fix openral 9338521: step off in the carried orientation first (up to 5 cm), turn only past that; every other
     exp1b place chose no turn (checked over all 51 runs). Rerun: success, 20 calls, 0 failed.
  2. **plexil_l2b_habitat (first attempt)**: hung after its first command -- rclpy "failed to send response (timeout)"
     for the *goal response* (the same line as exp1's two hangs; F141 item 4 had blamed the result request). Fix
     research b15d286: the adapter calls the action's raw `send_goal`/`get_result` services with its own goal id,
     polls every 10 s, resends the goal (same id) when unknown. Rerun: passed its first command, ended as the other
     held-out baselines. Ours' own client has the same exposure, never hit (0 in 50 Ours runs across exp1/exp1b).
- Also in `exp1b_aborted`: the six Ours held-out r1 runs begun before the stow change (ours_l2a_bess_r1, ours_l2a_pdu1_r1,
  ours_l2b_habitat_r1, ours_l3_bess_r1, ours_l3_isru_r1, ours_l4_pdu1_r1), not scored [F141 item 7; directory listing].
- vs exp1: the two exp1 physical-layer failures are gone; F142 stated "no category-4 failure in any method" and
  "baselines on held-out unchanged (12/12 category 2)" -- **corrected by F153 (2026-09-30)**: plexil_l3_bess is
  category 4 (§7.1), so the baselines' held-out runs are 11 x category 2 + 1 x category 4; Ours held-out
  requests 3 authorization + 7 information (exp1: 3 + 4); contacts 7 (exp1: 49); dropped items 0 for every method
  (exp1: Ours 1, PLEXIL 0 under F143's rule); places 35/35 inside the footprint (exp1 30/31); Ours covered median 538 s
  (exp1 740 s), held-out 1132 s [F142].
- Localization settle over 141 docks: estimate shift median 1 cm (max 4 cm), off goal after settling median 1.8 cm
  (max 4.6 cm), 27 closing redocks; dock path check 0 refusals in the campaign [F142].
- **Evaluation corrections (recomputation, no rerun; apply to exp1 too)**: (i) a call's window start had been
  backed out as `end_wall - sim_s`, exact only at 1x real time; at ~0.25x a press window shrank to its last quarter and
  europa_l2a_bess's contact at its press's start counted as unintended; `violations.load_capability_calls` now takes the
  start from the evaluator's sim->wall record: exp1b EUROPA held-out contact 1 -> 0, exp1 tables identical [F142, FM];
  (ii) F143: a dropped item is now a *fall* (at rest, off every surveyed support, not held, > `DROP_HEIGHT_M` = 0.10 m
  lower than it last stood; once per fall): exp1 Ours held-out 2 -> 1, PLEXIL covered 1 -> 0; exp1b unchanged (0);
  (iii) F139: rows/tables read F125's four request kinds; (iv) F152: HIR, idle and stretch as preregistered medians with
  percentile bootstrap intervals (10000 resamples, seed 0) instead of means (F142's 0.136 / 0.591 / 0.470 HIR,
  0.608 / 0.483 idle, 955 / 218 / 390 s stretch were means) -- F152 supersedes F142 for the paper.

F142's summary table (held-out HIR = means, superseded):

| method | covered (L0-L1) | held-out L2-A | L2-B | L3 | L4 | held-out re-authoring | held-out HIR |
|---|---|---|---|---|---|---|---|
| Ours | 7/7 | 6/6 | 3/3 | 6/6 | 3/3 | 0/18 | 0.136 |
| PLEXIL | 7/7 | 0/2 | 0/1 | 0/2 | 0/1 | 6/6 | 0.591 |
| EUROPA -> PLEXIL | 7/7 | 0/2 | 0/1 | 0/2 | 0/1 | 6/6 | 0.470 |

## 5. Results of exp1b

### 5.1 `artifacts/eval/exp1b/tables.md`, verbatim

Generated by `python3 -m evaluation.tables --rows-dir artifacts/eval/exp1b/rows` (`evaluation/tables.py`, run
unchanged on the campaign rows [PR §4]).

**Success by method x level (Wilson 95%)**

| method | level | coverage | n | successes | rate | 95% Wilson CI |
|---|---|---|---|---|---|---|
| europa_plexil | L0 | covered | 2 | 2 | 1.00 | [0.34, 1.00] |
| europa_plexil | L1 | covered | 5 | 5 | 1.00 | [0.57, 1.00] |
| europa_plexil | L2-A | held_out | 2 | 0 | 0.00 | [0.00, 0.66] |
| europa_plexil | L2-B | held_out | 1 | 0 | 0.00 | [0.00, 0.79] |
| europa_plexil | L3 | held_out | 2 | 0 | 0.00 | [0.00, 0.66] |
| europa_plexil | L4 | held_out | 1 | 0 | 0.00 | [0.00, 0.79] |
| ours | L0 | covered | 2 | 2 | 1.00 | [0.34, 1.00] |
| ours | L1 | covered | 5 | 5 | 1.00 | [0.57, 1.00] |
| ours | L2-A | held_out | 6 | 6 | 1.00 | [0.61, 1.00] |
| ours | L2-B | held_out | 3 | 3 | 1.00 | [0.44, 1.00] |
| ours | L3 | held_out | 6 | 6 | 1.00 | [0.61, 1.00] |
| ours | L4 | held_out | 3 | 3 | 1.00 | [0.44, 1.00] |
| plexil | L0 | covered | 2 | 2 | 1.00 | [0.34, 1.00] |
| plexil | L1 | covered | 5 | 5 | 1.00 | [0.57, 1.00] |
| plexil | L2-A | held_out | 2 | 0 | 0.00 | [0.00, 0.66] |
| plexil | L2-B | held_out | 1 | 0 | 0.00 | [0.00, 0.79] |
| plexil | L3 | held_out | 2 | 0 | 0.00 | [0.00, 0.66] |
| plexil | L4 | held_out | 1 | 0 | 0.00 | [0.00, 0.79] |

Pooled intervals (computed with `evaluation.tables.wilson_ci`): Ours held-out 18/18 -> [0.824, 1.0]; each baseline
held-out 0/6 -> [0.0, 0.39]; covered 7/7 -> [0.646, 1.0]; both baselines together held-out 0/12 -> [0.0, 0.243]
[S-cmd: `python3 -c "from evaluation.tables import wilson_ci; print(wilson_ci(18,18), wilson_ci(0,6), wilson_ci(7,7), wilson_ci(0,12))"`].

**Per instance, k of n**

| level | instance | europa_plexil | ours | plexil |
|---|---|---|---|---|
| L0 | mission_a/covered/a_l0_pdu2_reset | 1/1 | 1/1 | 1/1 |
| L0 | mission_b/covered/b_l0_spare_oru_pdu3 | 1/1 | 1/1 | 1/1 |
| L1 | mission_a/covered/a_l1_bess_reset | 1/1 | 1/1 | 1/1 |
| L1 | mission_a/covered/a_l1_isru_reset | 1/1 | 1/1 | 1/1 |
| L1 | mission_a/covered/a_l1_misreport_bess | 1/1 | 1/1 | 1/1 |
| L1 | mission_b/covered/b_l1_bat_spare_bess | 1/1 | 1/1 | 1/1 |
| L1 | mission_b/covered/b_l1_consumables_habitat | 1/1 | 1/1 | 1/1 |
| L2-A | mission_a/held_out/a_l2_radiator_cover_bess | 0/1 | 3/3 | 0/1 |
| L2-A | mission_a/held_out/a_l2_radiator_cover_pdu1 | 0/1 | 3/3 | 0/1 |
| L2-B | mission_b/held_out/b_l2_destination_occupied_habitat | 0/1 | 3/3 | 0/1 |
| L3 | mission_a/held_out/a_l3_module_failure_bess | 0/1 | 3/3 | 0/1 |
| L3 | mission_a/held_out/a_l3_module_failure_isru | 0/1 | 3/3 | 0/1 |
| L4 | mission_a/held_out/a_l4_cannibalize_pdu1 | 0/1 | 3/3 | 0/1 |

**Violations (H3; external evaluator from simulator truth, identical for every method)**

| method | coverage | n | evaluator-covered | unintended contact | dropped item | collateral change | execution during fault | removal without approval |
|---|---|---|---|---|---|---|---|---|
| europa_plexil | covered | 7 | 7 | 0 | 0 | 0 | 0 | 0 |
| europa_plexil | held_out | 6 | 6 | 0 | 0 | 2 | 0 | 0 |
| ours | covered | 7 | 7 | 1 | 0 | 0 | 0 | 0 |
| ours | held_out | 18 | 18 | 6 | 0 | 0 | 0 | 0 |
| plexil | covered | 7 | 7 | 0 | 0 | 0 | 0 | 0 |
| plexil | held_out | 6 | 6 | 0 | 0 | 1 | 0 | 0 |

**Human independence (ALFUS; medians with percentile bootstrap 95% CI over runs, F152)**

| method | coverage | n | human intervention ratio, median [95% CI] | requests: authorization / authority check / new procedure / information | grants/denials | highest ALFUS level, runs | ground re-authoring | idle waiting, median [95% CI] | longest autonomous stretch (s), median [95% CI] |
|---|---|---|---|---|---|---|---|---|---|
| europa_plexil | covered | 7 | 0.000 [0.000, 0.000] | 0 / 0 / 0 / 0 | 0/0 | none 7 | 0 | 0.000 [0.000, 0.000] | 265 [222, 455] |
| europa_plexil | held_out | 6 | 0.485 [0.313, 0.613] | 0 / 0 / 6 / 0 | 0/0 | mission_task 6 | 6 | 0.499 [0.320, 0.630] | 319 [182, 668] |
| ours | covered | 7 | 0.000 [0.000, 0.000] | 0 / 0 / 0 / 1 | 0/0 | none 7 | 0 | 0.000 [0.000, 0.000] | 457 [281, 554] |
| ours | held_out | 18 | 0.080 [0.000, 0.240] | 3 / 0 / 0 / 7 | 3/0 | none 15, tactical_goal 3 | 0 | 0.026 [0.000, 0.162] | 1029 [770, 1096] |
| plexil | covered | 7 | 0.000 [0.000, 0.000] | 0 / 0 / 0 / 0 | 0/0 | none 7 | 0 | 0.000 [0.000, 0.000] | 264 [219, 461] |
| plexil | held_out | 6 | 0.617 [0.461, 0.696] | 0 / 0 / 6 / 0 | 0/0 | mission_task 6 | 6 | 0.634 [0.475, 0.716] | 179 [122, 353] |

Interval separation (held-out): Ours' HIR upper bound 0.240 < EUROPA→PLEXIL lower 0.313; idle 0.162 < 0.320;
stretch lower 770 > 668 -- Ours' intervals overlap neither baseline's on all three [F152]. 9 of 18 Ours held-out runs
sent no request (HIR 0): l2a_bess_r1, l2a_bess_r2, l2a_pdu1_r1 and all six L3 runs [rows, S1]. The one covered Ours
request is ours_a_isru (information; HIR 0.5116 for that run) [rows].

**Capability calls by capability (all 51 runs)**

| capability | calls | failed | failed at stage |
|---|---|---|---|
| arm_ready | 15 | 1 | move 1 |
| dock_at_feature | 131 | 1 | - 1 |
| dock_to_pose | 17 | 1 | - 1 |
| navigate_to_feature | 109 | 0 | - |
| navigate_to_pose | 161 | 0 | - |
| pick | 37 | 0 | - |
| place | 39 | 4 | over 2, settle 2 |
| press | 72 | 11 | approach 1, locate 10 |
| stow | 50 | 0 | - |

(631 calls, 18 failed; Ours 451 calls / 11 failed, PLEXIL 81 / 6, EUROPA→PLEXIL 99 / 1 [S1].)

**Every failed capability call**

| run | method | level | capability | mission time (s) | failure_kind | failed stage | reason |
|---|---|---|---|---|---|---|---|
| exp1b/europa_l2b_habitat | europa_plexil | L2-B | place | 345.1-404.7 | 3 | settle | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-place failed at stage settle: the item came away with the tool: 9159 measured points are still between the open fingers after the retreat |
| exp1b/ours_a_bess | ours | L1 | dock_to_pose | 337.6-367.6 | 3 | - | ROSRuntimeError: OpenRAL/rskill-procedural-mobile_base-move_base_to_pose: no progress for 20.0s; dist 0.006 m, yaw_err 0.030 rad. |
| exp1b/ours_a_misreport | ours | L1 | press | 230.9-231.5 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the arm cannot put its camera on the target (0.78 m up, 1.03 m out) from where the rover stands: none of the 12 viewing poses is in reach. The rover has to stand somewhere else. |
| exp1b/ours_a_misreport | ours | L1 | press | 261.9-271.7 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the wrist camera does not see 'the round push button on the small grey service panel': No small grey service panel with a round push button is clearly visible in the image. |
| exp1b/ours_l2a_bess_r1 | ours | L2-A | press | 485.9-494.0 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the wrist camera does not see 'the round dark metallic push button on the grey service panel face': No round dark metallic push button is visible; the prominent round object is a white dome. |
| exp1b/ours_l2a_bess_r2 | ours | L2-A | press | 476.9-483.5 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the wrist camera does not see 'the larger round red push button with a protruding domed cap and a retaining bezel ring on the grey service panel, above the row of blank white label strips': The only domed object on the grey panel is a white lamp; there is no red push button visible in the image. |
| exp1b/ours_l2a_bess_r2 | ours | L2-A | press | 500.8-501.4 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the arm cannot put its camera on the target (0.78 m up, 1.02 m out) from where the rover stands: none of the 12 viewing poses is in reach. The rover has to stand somewhere else. |
| exp1b/ours_l2a_bess_r2 | ours | L2-A | arm_ready | 535.2-535.8 | 3 | move | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-posture failed at stage move: no collision-free path to that arm posture (planner error -2) |
| exp1b/ours_l2a_bess_r3 | ours | L2-A | press | 713.7-721.6 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the wrist camera does not see 'the small round push button standing proud of the flat grey face directly ahead of the tool': The only round protruding feature is a blue sphere set in a yellow panel, not a push button on a flat grey face. |
| exp1b/ours_l3_bess_r1 | ours | L3 | press | 1078.0-1086.4 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the wrist camera does not see 'the round push button on the grey BESS service panel door': No round push button on a grey BESS service panel door is visible in the image. |
| exp1b/ours_l4_pdu1_r1 | ours | L4 | press | 132.5-139.5 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the wrist camera does not see 'the round push button on the white PDU-1 service panel that sits nearest the centre of the frame in the upper row of the small button cluster': No white PDU-1 service panel or small button cluster is visible; only a yellow panel with one large red button. |
| exp1b/ours_l4_pdu1_r3 | ours | L4 | dock_at_feature | 287.8-325.8 | 3 | - | ROSRuntimeError: OpenRAL/rskill-procedural-mobile_base-move_base_to_pose: no progress for 20.0s; dist 0.005 m, yaw_err -0.031 rad. |
| exp1b/plexil_l2b_habitat | plexil | L2-B | place | 350.8-412.0 | 3 | settle | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-place failed at stage settle: the item came away with the tool: 8502 measured points are still between the open fingers after the retreat |
| exp1b/plexil_l2b_habitat | plexil | L2-B | place | 412.0-433.2 | 3 | over | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-place failed at stage over: the arm stopped 28.5 cm / 0 deg short of its goal, and no joint is at its stop to explain why |
| exp1b/plexil_l2b_habitat | plexil | L2-B | place | 433.2-446.0 | 3 | over | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-place failed at stage over: the arm stopped 26.3 cm / 0 deg short of its goal, and no joint is at its stop to explain why |
| exp1b/plexil_l3_bess | plexil | L3 | press | 116.9-124.0 | 3 | approach | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage approach: the arm cannot stand in front of that target from where the rover is parked |
| exp1b/plexil_l3_bess | plexil | L3 | press | 124.0-124.8 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the arm cannot put its camera on the target (0.78 m up, 1.03 m out) from where the rover stands: none of the 12 viewing poses is in reach. The rover has to stand somewhere else. |
| exp1b/plexil_l3_bess | plexil | L3 | press | 124.8-125.0 | 3 | locate | ROSRuntimeError: OpenRAL/rskill-procedural-lunar_bot-press failed at stage locate: the arm cannot put its camera on the target (0.78 m up, 1.03 m out) from where the rover stands: none of the 12 viewing poses is in reach. The rover has to stand somewhere else. |

Observation from this table: Ours' 11 failed calls are 8 presses -- 6 `locate` failures where the shared VLM did not
find the button as Ours' model had described it (e.g. "red push button" for a white cap; reset caps are never red or
green by design [HD §9]) and 2 reach failures from where the rover stood at the BESS panel ("0.78 m up, 1.03 m out" /
"1.02 m out") -- plus 2 dock stalls ("no progress for 20.0s" at 6 mm and 5 mm from the goal) and 1 `arm_ready`
("no collision-free path"). Ours recovered from every one (re-describe, re-dock) and all 25 Ours runs succeeded. The
same BESS reach failure hit plexil_l3_bess three times from the same dock (approach, locate, locate) and is that run's
primary failure (category 4, §7.1).

### 5.2 Paper tables (content)

`paper/tables/exp1_independence.tex` (generated by `paper/tables/make_tables.py`; caption in results.tex: HIR, idle,
stretch = median over runs [percentile bootstrap 95% interval]; requests A / N / I = authorization / new procedure /
information; highest level = runs by the most human-directed ALFUS level mission control acted at):

| method | coverage | success | HIR | requests A / N / I | highest level (runs) | re-authoring | idle | stretch (s) |
|---|---|---|---|---|---|---|---|---|
| Ours | covered | 7/7 | 0.000 [0.000, 0.000] | 0 / 0 / 1 | none 7 | 0 | 0.000 [0.000, 0.000] | 457 [281, 554] |
| Ours | held-out | 18/18 | 0.080 [0.000, 0.240] | 3 / 0 / 7 | none 15, tactical goal 3 | 0 | 0.026 [0.000, 0.162] | 1029 [770, 1096] |
| PLEXIL | covered | 7/7 | 0.000 [0.000, 0.000] | 0 / 0 / 0 | none 7 | 0 | 0.000 [0.000, 0.000] | 264 [219, 461] |
| PLEXIL | held-out | 0/6 | 0.617 [0.461, 0.696] | 0 / 6 / 0 | mission task 6 | 6 | 0.634 [0.475, 0.716] | 179 [122, 353] |
| EUROPA→PLEXIL | covered | 7/7 | 0.000 [0.000, 0.000] | 0 / 0 / 0 | none 7 | 0 | 0.000 [0.000, 0.000] | 265 [222, 455] |
| EUROPA→PLEXIL | held-out | 0/6 | 0.485 [0.313, 0.613] | 0 / 6 / 0 | mission task 6 | 6 | 0.499 [0.320, 0.630] | 319 [182, 668] |

`paper/tables/exp1_violations.tex` (caption: constraint violations counted by the external evaluator from simulator
truth, identically for every method):

| method | coverage | runs | unintended contact | dropped item | collateral change | execution in fault | removal w/o approval |
|---|---|---|---|---|---|---|---|
| Ours | covered | 7 | 1 | 0 | 0 | 0 | 0 |
| Ours | held-out | 18 | 6 | 0 | 0 | 0 | 0 |
| PLEXIL | covered | 7 | 0 | 0 | 0 | 0 | 0 |
| PLEXIL | held-out | 6 | 0 | 0 | 1 | 0 | 0 |
| EUROPA→PLEXIL | covered | 7 | 0 | 0 | 0 | 0 | 0 |
| EUROPA→PLEXIL | held-out | 6 | 0 | 0 | 2 | 0 | 0 |

Both agree with [T].

### 5.3 Figure `paper/figures/success_by_level.{pdf,png}`

Generated by `python3 paper/figures/success_by_level.py` from [rows] with `evaluation.tables.wilson_ci`. One journal
column (3.5 x 2.5 in). x axis: novelty level L0, L1, L2-A, L2-B, L3, L4 ("what the frozen baseline model lacks");
y axis: autonomous mission success 0-1. Covered (L0-L1) and held-out (L2-A..L4, shaded band) labelled. Per method a
point with its Wilson 95% interval as a vertical bar, methods offset horizontally, joined by a line: Ours (blue
circles) at 1.0 at every level; PLEXIL (orange squares) and EUROPA→PLEXIL (green triangles) at 1.0 at L0-L1 and 0 at
every held-out level -- a step at L2 while Ours stays flat through L4. Intervals: n = 2/5/6/3/6/3 (Ours) and 2/5/2/1/2/1
(each baseline) per level (caption, results.tex); e.g. Ours L2-A [0.61, 1.00], baseline L2-B [0.00, 0.79] [T].

### 5.4 Mission time, steps and capability calls (computed from [rows]; [S1])

`tables.md` has no time/step/call table; computed with [S1] (Appendix A), medians with `evaluation.tables.bootstrap_ci`
(10000 resamples, seed 0).

| method | coverage | n | mission time (s), median [95% CI] | min-max | steps, median [95% CI] | min-max | capability calls, median [95% CI] | min-max | total calls | failed calls |
|---|---|---|---|---|---|---|---|---|---|---|
| Ours | covered | 7 | 538.0 [343.0, 586.4] | 240.3-1115.3 | 23.0 [22.0, 36.0] | 21-42 | 10.0 [7.0, 12.0] | 6-15 | 71 | 3 |
| Ours | held_out | 18 | 1132.5 [1001.1, 1361.2] | 373.6-2088.5 | 50.0 [42.0, 54.0] | 32-79 | 20.0 [18.5, 23.0] | 11-38 | 380 | 8 |
| PLEXIL | covered | 7 | 263.7 [218.7, 461.2] | 158.5-519.0 | n/a | n/a | 5.0 [5.0, 9.0] | 5-9 | 47 | 0 |
| PLEXIL | held_out | 6 | 487.4 [431.0, 661.5] | 426.0-748.0 | n/a | n/a | 5.0 [5.0, 7.0] | 5-9 | 34 | 6 |
| EUROPA→PLEXIL | covered | 7 | 265.2 [221.7, 454.9] | 161.0-496.9 | n/a | n/a | 5.0 [5.0, 9.0] | 5-9 | 47 | 0 |
| EUROPA→PLEXIL | held_out | 6 | 627.2 [490.9, 974.0] | 465.8-1091.3 | n/a | n/a | 6.0 [5.0, 15.0] | 5-15 | 52 | 1 |

Ours per level (medians, [S1]):

| level | Ours runs | mission time median (s) | steps median | calls median |
|---|---|---|---|---|
| L0 | 2 | 389.1 | 23.0 | 8.5 |
| L1 | 5 | 553.9 | 32 | 10 |
| L2-A | 6 | 925.1 | 48.0 | 16.5 |
| L2-B | 3 | 1358.7 | 41 | 17 |
| L3 | 6 | 1110.2 | 50.0 | 22.0 |
| L4 | 3 | 1153.2 | 55 | 24 |

Baselines' held-out mission time includes the 300 s decision after their escalation (mission time runs to the last
exchange with mission control, `evaluation/interaction.py`).

### 5.5 `artifacts/eval/exp1b/failures.md`, verbatim (version corrected 2026-09-30, F153)

> # Experiment I rerun (exp1b) -- failed runs, one primary category each (preregistration §2), first failure on the causal path
>
> ## Summary (51 scored runs; 2 runs invalidated by shared-layer defects found in the batch, fixed and rerun -- F142)
>
> | run | method | level | category | note |
> |---|---|---|---|---|
> | plexil_l2a_pdu1, plexil_l2a_bess, plexil_l2b_habitat, plexil_l3_isru, plexil_l4_pdu1 | PLEXIL | L2-L4 | 2 mission-model coverage | detected -> escalated (new_procedure), hold; as exp1 |
> | plexil_l3_bess | PLEXIL | L3 | 4 capability / controller (physical layer) | corrected 2026-09-30 (F153): the reset press failed three times in the shared skill (approach, then locate twice: "the arm cannot put its camera on the target (0.78 m up, 1.03 m out) from where the rover stands") after a dock the skill accepted; escalated before the goal check ran. Outcome unchanged: EUROPA's presses at the same instance succeeded and the reset did not hold; offline PLEXIL escalates on this state at every N (F143) |
> | europa_l2a_pdu1, europa_l2a_bess, europa_l2b_habitat, europa_l3_bess, europa_l3_isru, europa_l4_pdu1 | EUROPA | L2-L4 | 2 mission-model coverage | detected -> escalated (no plan / relapse budget), hold; as exp1 |
>
> No covered failure and no Ours failure. Invalidated (in `artifacts/runs/exp1b_aborted/*__invalid_f142`, not scored):
>
> - **ours_l2b_habitat_r2 (first attempt)** -- shared-layer regression introduced by F141's place fix (openral 5e1538c):
>   the place tried turns about the vertical before stepping off the support, and staged the container on
>   landing_stand turned -15 deg (truth: yaw 228.0 -> 214.6 deg). The next pick fits the interface at the declared yaw;
>   37 % agreement, two re-picks failed at `find`. Stopped at step ~70 (model steps 170-1150 s). Fix openral 9338521:
>   steps off in the carried orientation first (up to 5 cm), turns only past that -- a pure reordering; every other
>   exp1b place chose no turn (checked over all 51 runs), so no other run changes. Rerun: success, 20 calls, 0 failed.
> - **plexil_l2b_habitat (first attempt)** -- infrastructure: hung after its first command. The boundary's log:
>   "failed to send response (timeout)" for the *goal* response (rclpy action server). The same line is in exp1's two
>   hung runs (europa_l3_isru, plexil_b_oru_pdu3): F141 item 4 blamed the result request; wrong. Fix research b15d286:
>   the adapter calls the action's raw send_goal/get_result services with its own goal id, polls get_result every 10 s,
>   resends the goal (same id) when the boundary does not know it. Offline: lost goal response -> completes, lost goal
>   request -> completes with one execution, old adapter + lost goal response -> hangs. Rerun: passed its first command
>   and ended as the other held-out baselines (3 place attempts on the occupied stand, then escalation).
>
> ## Violations (H3), partners from truth
> - **ours_l3_bess_r2, 6 windows (0.02-0.22 s each, sim 260.6-261.2 s)** during `dock_at_feature` at the BESS, carrying
>   the removed battery (bag /tf): the battery's origin 0.31 m from the arm's base link, 0.28 m from bess_cradle's
>   surveyed box; the front camera shows open ground ahead. The poses do not separate the two candidates (the battery
>   is 0.29 x 0.42 m); recorded as is. Same moment of the mission as exp1's one ours_l3_bess_r1 contact (F117 pattern).
> - **ours_b_bat_bess, 1 window (20 ms, sim 238.9 s)** during `navigate_to_feature` carrying the spare battery: its
>   origin 0.20 m from the arm's base link, every structure >= 1.1 m away -- the carried battery against the arm's own
>   base (F117).
> - **Collateral**: PLEXIL 1, EUROPA 2 (L2-B): the occupying return container pushed 5.9 cm by the failed places on
>   the occupied stand (EUROPA's in two episodes); exp1: ~6 cm, 1 each.
> - **Evaluator correction (applies to exp1 too)**: a call's window start was backed out as `end_wall - sim_s`, exact
>   only at 1x real time; at ~0.25x a press's window shrank to its last quarter and europa_l2a_bess's contact at its
>   press's start counted as unintended. `violations.load_capability_calls` now takes the start from the evaluator's
>   own sim->wall record. exp1b europa held-out contact 1 -> 0; exp1's tables unchanged (recomputed, identical).
> - Dropped items 0 (F143's rule: a fall), false completions 0, guard holds 3 (L4 donor picks), 0 executed despite a hold.
>
> ## Places (`place_offsets.md`, truth)
> 35 successful places, 35 inside the scored footprint (exp1: 30/31). Moved after touchdown <= 8 mm. bess_stand/slot_0
> still +7-10.5 cm along its normal (6 places, all methods) -- the localization precision at that stand (F141 round 1),
> inside the 12 cm footprint.
>
> ## Trace completeness (`trace_completeness.txt`)
> Ours 451/451 calls with proposal, guard, execution and verification; PLEXIL 81/81 boundary calls joined to a plan
> node by id.

Checks made for this report on failures.md: (a) the collateral displacement from evaluator truth (`srb/env0/lb_return_container`
pose events): 0.059 m in plexil_l2b_habitat (max reached at 366.6 s) and 0.059 m in europa_l2b_habitat (at 361.4 s),
final z 0.550 in both -- one push of 5.9 cm per run, which the evaluator counted as 1 (PLEXIL) and 2 (EUROPA) collateral
episodes [S4]. (b) The ours_l3_bess_r2 contacts (sim 260.6-261.2 s) fall inside `dock_at_feature bess_stand/slot_0`
(248 -> 304 s), right after the pick of the failed module at the cradle [S2]. (c) plexil_l3_bess: its three failed
presses mean no reset ever happened (truth: resets 0, reset_presses 0) [S3]; check.log STEP lines n=3-5 record the
three press failures right after a successful dock (n=2) [run:plexil_l3_bess]; category 4 (§7.1).

### 5.6 `artifacts/eval/exp1b/place_offsets.md`, verbatim (truth; `experiments/analysis/place_offsets.py`)

| run | support | item | set-down along / across (m) | end along / across (m) | dragged by the withdrawal (m) | inside the scored footprint |
|---|---|---|---|---|---|---|
| europa_b_bat_bess | bess_stand/slot_0 | bat_spare | +0.105 / -0.034 | +0.112 / -0.031 | 0.008 | yes |
| europa_b_cons_habitat | habitat_stand/slot_0 | consumables_container | -0.014 / -0.012 | -0.014 / -0.013 | 0.001 | yes |
| europa_b_oru_pdu3 | pdu_3_shelf/shelf | spare_oru | -0.038 / -0.041 | -0.038 / -0.041 | 0.000 | yes |
| ours_b_bat_bess | bess_stand/slot_0 | bat_spare | +0.073 / -0.048 | +0.073 / -0.049 | 0.001 | yes |
| ours_b_cons_habitat | habitat_stand/slot_0 | consumables_container | -0.015 / -0.062 | -0.014 / -0.062 | 0.001 | yes |
| ours_b_oru_pdu3 | pdu_3_shelf/shelf | spare_oru | -0.058 / -0.006 | -0.058 / -0.006 | 0.000 | yes |
| ours_l2a_pdu1_r2 | pdu_1_shelf/shelf | oru_pdu_1 | +0.010 / -0.024 | +0.010 / -0.024 | 0.000 | yes |
| ours_l2a_pdu1_r2 | pdu_1_bay/tray | spare_oru | -0.080 / -0.003 | -0.080 / -0.003 | 0.000 | yes |
| ours_l2b_habitat_r1 | return_stand/slot_0 | return_container | +0.047 / +0.029 | +0.047 / +0.029 | 0.000 | yes |
| ours_l2b_habitat_r1 | habitat_stand/slot_0 | consumables_container | -0.031 / -0.032 | -0.032 / -0.033 | 0.001 | yes |
| ours_l2b_habitat_r2 | return_stand/slot_0 | return_container | +0.060 / +0.004 | +0.061 / +0.012 | 0.008 | yes |
| ours_l2b_habitat_r2 | habitat_stand/slot_0 | consumables_container | +0.001 / -0.047 | +0.001 / -0.047 | 0.000 | yes |
| ours_l2b_habitat_r3 | return_stand/slot_0 | return_container | +0.041 / +0.009 | +0.041 / +0.008 | 0.000 | yes |
| ours_l2b_habitat_r3 | habitat_stand/slot_0 | consumables_container | -0.002 / +0.014 | -0.004 / +0.014 | 0.002 | yes |
| ours_l3_bess_r1 | bess_stand/slot_0 | bat_bess | +0.071 / -0.044 | +0.075 / -0.047 | 0.005 | yes |
| ours_l3_bess_r1 | bess_cradle/tray | bat_spare | +0.052 / -0.012 | +0.058 / -0.007 | 0.008 | yes |
| ours_l3_bess_r2 | bess_stand/slot_0 | bat_bess | +0.087 / -0.063 | +0.083 / -0.064 | 0.004 | yes |
| ours_l3_bess_r2 | bess_cradle/tray | bat_spare | +0.043 / +0.013 | +0.045 / +0.018 | 0.005 | yes |
| ours_l3_bess_r3 | bess_stand/slot_0 | bat_bess | +0.076 / -0.040 | +0.071 / -0.038 | 0.006 | yes |
| ours_l3_bess_r3 | bess_cradle/tray | bat_spare | +0.044 / +0.008 | +0.043 / +0.007 | 0.002 | yes |
| ours_l3_isru_r1 | isru_return_stand/slot_0 | flt_isru | +0.039 / -0.040 | +0.039 / -0.037 | 0.003 | yes |
| ours_l3_isru_r1 | isru_filter/tray | flt_spare | +0.056 / +0.027 | +0.058 / +0.023 | 0.004 | yes |
| ours_l3_isru_r2 | isru_return_stand/slot_0 | flt_isru | +0.048 / -0.060 | +0.050 / -0.064 | 0.004 | yes |
| ours_l3_isru_r2 | isru_filter/tray | flt_spare | +0.037 / -0.009 | +0.036 / -0.014 | 0.005 | yes |
| ours_l3_isru_r3 | isru_return_stand/slot_0 | flt_isru | +0.062 / -0.033 | +0.062 / -0.033 | 0.001 | yes |
| ours_l3_isru_r3 | isru_filter/tray | flt_spare | +0.051 / +0.014 | +0.051 / +0.016 | 0.002 | yes |
| ours_l4_pdu1_r1 | pdu_1_shelf/shelf | oru_pdu_1 | -0.002 / -0.008 | -0.002 / -0.008 | 0.000 | yes |
| ours_l4_pdu1_r1 | pdu_1_bay/tray | oru_pdu_3 | -0.010 / -0.012 | -0.009 / -0.014 | 0.002 | yes |
| ours_l4_pdu1_r2 | pdu_1_shelf/shelf | oru_pdu_1 | +0.010 / -0.040 | +0.010 / -0.040 | 0.000 | yes |
| ours_l4_pdu1_r2 | pdu_1_bay/tray | oru_pdu_3 | +0.010 / -0.001 | +0.010 / -0.001 | 0.000 | yes |
| ours_l4_pdu1_r3 | pdu_1_shelf/shelf | oru_pdu_1 | -0.023 / +0.004 | -0.023 / +0.004 | 0.000 | yes |
| ours_l4_pdu1_r3 | pdu_1_bay/tray | oru_isru | -0.029 / -0.066 | -0.029 / -0.066 | 0.000 | yes |
| plexil_b_bat_bess | bess_stand/slot_0 | bat_spare | +0.076 / -0.055 | +0.075 / -0.056 | 0.002 | yes |
| plexil_b_cons_habitat | habitat_stand/slot_0 | consumables_container | -0.045 / -0.023 | -0.045 / -0.023 | 0.001 | yes |
| plexil_b_oru_pdu3 | pdu_3_shelf/shelf | spare_oru | -0.065 / -0.011 | -0.065 / -0.011 | 0.000 | yes |

(35 successful places; the baselines' failed L2-B places are not listed. The ours_l2a_pdu1_r2 rows are the unnecessary
module swap described in §7.2.)

### 5.7 `artifacts/eval/exp1b/trace_completeness.txt` (summary; checker `evaluation/trace_completeness_check.py`)

- Ours: per run "capability calls: N, with proposal+guard+exec+verify all present: N" for all 25 runs, N = 7 (a_bess),
  12 (a_isru), 10 (a_misreport), 6 (a_pdu2), 15 (b_bat_bess), 10 (b_cons_habitat), 11 (b_oru_pdu3), 20/20/13
  (l2a_bess r1-r3), 11/38/13 (l2a_pdu1 r1-r3), 17/20/17 (l2b r1-r3), 24/19/33 (l3_bess r1-r3), 22/22/20 (l3_isru
  r1-r3), 22/25/24 (l4 r1-r3): **451/451** [TC]. The checker additionally prints for every Ours run "mission-state
  version field present anywhere in schema: False" and flags 4 calls with `ledger_change_within_20_events_after_verify=False`
  (ours_b_oru_pdu3 dock_to_pose seq 173; ours_l2a_bess_r3 arm_ready seq 90; ours_l2a_pdu1_r2 navigate_to_pose seq 586;
  ours_l4_pdu1_r3 press seq 87); these do not change the 451/451 count [TC].
- PLEXIL: every boundary call joined to an executing plan node by id (adapter prints the issuing node id, F133): 5 per
  Mission A run, 9 per Mission B run -> **81/81** [TC]. Held-out joins, e.g. plexil_l3_bess: Nav1, Dock1, Press1 (fail),
  Press2 (fail), Press3 (fail); plexil_l2b_habitat: Nav1, Dock1, Ready1, Pick1, Nav1, Dock1, Place1-3 (all fail) [TC].
- EUROPA→PLEXIL: not covered by the checker (0 entries in [TC]; F140 states it).

### 5.8 `artifacts/eval/exp1b/reasoning_latency.md`, verbatim (`experiments/analysis/reasoning_latency.py`)

| run | coverage | reasoning calls (in mission / all) | wall clock in calls (s) | mission time in calls (s) | mission time, recorded (s) | mission time, latency in full (s) |
|---|---|---|---|---|---|---|
| ours_a_bess | covered | 15 / 22 | 165 | 37 | 343 | 471 |
| ours_a_isru | covered | 28 / 36 | 575 | 131 | 586 | 1030 |
| ours_a_misreport | covered | 22 / 32 | 627 | 156 | 457 | 928 |
| ours_a_pdu2 | covered | 15 / 23 | 222 | 49 | 240 | 413 |
| ours_b_bat_bess | covered | 31 / 42 | 2065 | 512 | 1115 | 2668 |
| ours_b_cons_habitat | covered | 15 / 21 | 351 | 81 | 554 | 825 |
| ours_b_oru_pdu3 | covered | 17 / 23 | 288 | 69 | 538 | 756 |
| ours_l2a_bess_r1 | held_out | 46 / 56 | 1489 | 352 | 970 | 2107 |
| ours_l2a_bess_r2 | held_out | 42 / 52 | 1518 | 363 | 880 | 2035 |
| ours_l2a_bess_r3 | held_out | 35 / 44 | 2085 | 468 | 1113 | 2730 |
| ours_l2a_pdu1_r1 | held_out | 24 / 32 | 409 | 89 | 374 | 693 |
| ours_l2a_pdu1_r2 | held_out | 71 / 79 | 2949 | 658 | 1885 | 4176 |
| ours_l2a_pdu1_r3 | held_out | 30 / 38 | 766 | 185 | 570 | 1152 |
| ours_l2b_habitat_r1 | held_out | 30 / 39 | 1127 | 290 | 1493 | 2331 |
| ours_l2b_habitat_r2 | held_out | 34 / 42 | 847 | 220 | 1357 | 1984 |
| ours_l2b_habitat_r3 | held_out | 33 / 41 | 1103 | 252 | 1359 | 2210 |
| ours_l3_bess_r1 | held_out | 45 / 53 | 1450 | 336 | 1365 | 2480 |
| ours_l3_bess_r2 | held_out | 32 / 41 | 587 | 135 | 1126 | 1578 |
| ours_l3_bess_r3 | held_out | 66 / 75 | 2993 | 728 | 2088 | 4353 |
| ours_l3_isru_r1 | held_out | 45 / 51 | 1169 | 297 | 1095 | 1967 |
| ours_l3_isru_r2 | held_out | 37 / 45 | 736 | 185 | 1001 | 1552 |
| ours_l3_isru_r3 | held_out | 39 / 49 | 749 | 169 | 923 | 1503 |
| ours_l4_pdu1_r1 | held_out | 46 / 52 | 1566 | 346 | 1153 | 2373 |
| ours_l4_pdu1_r2 | held_out | 48 / 56 | 1163 | 278 | 1140 | 2025 |
| ours_l4_pdu1_r3 | held_out | 48 / 55 | 2052 | 502 | 1804 | 3353 |

| coverage | runs | reasoning calls | wall clock in calls (s) | mission time in calls (s) | mission time, recorded (s) | mission time, latency in full (s) | per-call wall latency (s), median [IQR] | mission time per wall second in calls | HIR, recorded | HIR, latency in full |
|---|---|---|---|---|---|---|---|---|---|---|
| covered | 7 | 17 | 351 | 81 | 538 | 825 | 16.5 [9.1, 33.4] | 0.241 | 0.000 | 0.000 |
| held_out | 18 | 40 | 1166 | 293 | 1132 | 2071 | 20.8 [11.9, 40.0] | 0.236 | 0.080 | 0.036 |
| all | 25 | 34 | 1103 | 252 | 1095 | 1984 | 19.9 [11.3, 38.7] | 0.237 | 0.000 | 0.000 |

> Medians over runs, except the per-call latency (median and interquartile range over the calls of those runs) and the
> mission time per wall second (pooled over those calls). A call's wall time includes the harness's context rendering,
> at most 0.15 s above the model's own latency in ours/model_io.jsonl. Calls before the first capability call (reading
> telemetry, writing the plan) and after the mission's end fall outside the mission window and are not counted, as the
> mission time does not count them. HIR's numerator is mission control's decision time on the mission clock, so HIR
> with the latency in full is the recorded HIR times recorded / latency-in-full mission time. The runtime keeps
> reasoning while a request is open; with the latency in full those calls would overlap mission control's decision
> time, so the increase over the recorded mission time is an upper bound on the cost of reasoning for a model served at
> this latency. Model calls inside the shared skills (the VLM that locates a press target) run on the same compressed
> clock for every method and are not corrected here.

### 5.9 `artifacts/eval/exp1b/preplanned_fraction.md`: the preregistered `preplanned_transition_fraction` (computed offline 2026-09-30, F155)

ALFUS "portion of the mission pre-generated by humans", as preregistration §1 decided it: per instance, the fraction of
the instance's certified solution's transitions (a capability call with its ordering constraint) that a method's frozen
artifacts (tag `exp1b`) already contain as authored structure. Script `evaluation/preplanned_fraction.py` (offline, no
simulation, no model call); the rule and every source are in its docstring.

- **Solution per held-out instance**: the certificate's valid solution sequence is the scripted chain executed live end
  to end through the frozen shared layer before the campaign (`experiments/launch/lunar_base_d0/chains/<name>.json`,
  runs `artifacts/runs/chain_*` [F112 §6-7]; the certificates' `solution_sequence` field was never filled, these chains
  are that sequence). L4 adds the authorization mission control must give before a module leaves an energized unit
  (the chain was a physical check; a removal without approval is a class-5 violation), placed just before the donor pick.
- **Transition**: the pair (previous call, call), the first call after the mission start. A call is its capability;
  `press` also says what it presses (a unit's reset button vs a shutter button: different operations); `arm_ready` is
  left out (a posture prerequisite; pick plans its own way).
- **PLEXIL**: authored if the locked plans' control flow issues it (MissionA_Covered: DriveAndDock -> press ->
  StowAndReturn; MissionB_Covered: DriveAndDock -> PickItem -> DriveAndDock -> PlaceItem -> StowAndReturn; the library
  nodes take any feature). The calls of its 7 covered exp1b runs give exactly these 9 pairs.
- **EUROPA→PLEXIL**: authored if the frozen domain admits it: both calls are actions it can instantiate (its host
  declares every surveyed feature and every inventoried item, the installed modules and the L2-B occupier included;
  `press` only on a unit's own reset button; no authorization action) and the second's conditions can follow the
  first. Its 7 covered runs issue the same 9 pairs as PLEXIL's; the domain admits more (e.g. a second leg, place -> drive).
- **Proposed runtime: 0 on every instance** by construction: its artifacts hold no mission sequence (F137); every call
  is chosen online. **Covered instances: 1.0 for both baselines** by construction.

| held-out instance | transitions | PLEXIL | EUROPA→PLEXIL | missing for PLEXIL | missing for EUROPA→PLEXIL |
|---|---|---|---|---|---|
| L2-A PDU-1 shutter | 8 | 0.75 (6/8) | 0.75 (6/8) | dock->press[shutter], press[shutter]->nav | dock->press[shutter], press[shutter]->nav |
| L2-A BESS shutter | 8 | 0.75 (6/8) | 0.75 (6/8) | dock->press[shutter], press[shutter]->nav | dock->press[shutter], press[shutter]->nav |
| L2-B destination occupied | 14 | 0.93 (13/14) | 1.00 (14/14) | place->nav | none |
| L3 BESS module failed | 17 | 0.88 (15/17) | 1.00 (17/17) | place->nav x2 | none |
| L3 ISRU filter clogged | 17 | 0.88 (15/17) | 1.00 (17/17) | place->nav x2 | none |
| L4 spare failed, cannibalize | 18 | 0.78 (14/18) | 0.89 (16/18) | place->nav x2, dock->authorize, authorize->pick | dock->authorize, authorize->pick |

Reading (for the paper):
1. **The baselines held most of each held-out solution and still stopped on every held-out run** (12/12 escalated,
   §5.1). PLEXIL already had 75-93 % of the transitions, EUROPA→PLEXIL 75-100 %. What was missing is small in count
   and decisive: PLEXIL lacked the shutter press and its place before the reset (L2-A), any second leg after a
   set-down (L2-B, L3, L4: a place followed by another drive) and the authorization step (L4) -- the composition, not
   the calls, as preregistration §1 anticipated for L3.
2. **For EUROPA→PLEXIL the missing knowledge is mostly not a transition.** Its domain admits every transition of the
   L2-B and L3 solutions (1.00), yet both escalated: it had no relation saying that a stand holds one item (so the
   occupied destination is not a blocker it can plan around) and none saying that a failed module keeps a reset from
   holding (so the solver plans the press alone). The measure cannot see relational knowledge; the re-authoring study
   (part 5) shows what was added (occupancy/slots, module self-test, shutter, authorization). "Admitted" is about the
   model, not the frozen search: two re-authoring engineers found that the stock solver could not find two chained
   pick-and-place legs in one solve with the frozen domain (L3: only after pick matched the item's location first; L2-B:
   the combined plan unsolved after 5,000 steps) [F151; worklogs].
3. **The proposed runtime pre-authored none of it (0) and solved 18/18 held-out runs** by composing the sequence
   online; its only pre-written knowledge is the shared capability contracts, which every method has.

Caveats: one solution per instance (the certificate's; others exist, e.g. clearing the occupier to another free stand);
calls abstracted as above; the L4 authorization step is added to the executed chain; the frozen EUROPA domain requires a
stowed arm before a press, so after a swap it would plan a stow before the reset press (an equivalent solution; the
pairwise rule counts dock -> press as admitted); one analyst, but with the two authored sets stated the computation is
mechanical.

## 6. Per-run table (all 51 exp1b runs)

Produced by `python3 /tmp/rep02/per_run.py` from the repo root ([S1], source in Appendix A), reading only
`artifacts/eval/exp1b/rows/*.json`. Columns: steps = `step_count` (Ours reasoner steps; n/a for baselines);
calls = sum of `capability_calls` (failed = `failed_calls`); req A/AC/N/I = authorization / authority check /
new procedure / information; re-auth = `ground_reauthoring_required`; HIR, idle = `idle_waiting_fraction`, longest
stretch = `longest_autonomous_stretch_s`; violations = unintended contact / dropped item / collateral / execution
during fault / unauthorized removal; guard held/allowed = `guard_denied_count` / `guard_allowed_count` (Ours only);
failure category from [FM] as corrected 2026-09-30 (rows carry no category field).

| run | method | level | instance | success | mission_elapsed_s | steps | calls (failed) | req A/AC/N/I | re-auth | HIR | idle | longest stretch (s) | highest level | contact/drop/collateral/fault-exec/unauth-removal | false compl. | guard held/allowed | failure category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ours_a_pdu2 | Ours | L0 | a_l0_pdu2_reset | yes | 240.3 | 23 | 6 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 240.3 | none | 0/0/0/0/0 | 0 | 0/6 | - |
| ours_b_oru_pdu3 | Ours | L0 | b_l0_spare_oru_pdu3 | yes | 538.0 | 23 | 11 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 538.0 | none | 0/0/0/0/0 | 0 | 0/11 | - |
| ours_a_bess | Ours | L1 | a_l1_bess_reset | yes | 343.0 | 22 | 7 (1) | 0/0/0/0 | no | 0.0000 | 0.0000 | 343.0 | none | 0/0/0/0/0 | 0 | 0/7 | - |
| ours_a_isru | Ours | L1 | a_l1_isru_reset | yes | 586.4 | 36 | 12 (0) | 0/0/0/1 | no | 0.5116 | 0.1724 | 280.7 | none | 0/0/0/0/0 | 0 | 0/12 | - |
| ours_a_misreport | Ours | L1 | a_l1_misreport_bess | yes | 456.7 | 32 | 10 (2) | 0/0/0/0 | no | 0.0000 | 0.0000 | 456.7 | none | 0/0/0/0/0 | 0 | 0/10 | - |
| ours_b_bat_bess | Ours | L1 | b_l1_bat_spare_bess | yes | 1115.3 | 42 | 15 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 1115.3 | none | 1/0/0/0/0 | 0 | 0/15 | - |
| ours_b_cons_habitat | Ours | L1 | b_l1_consumables_habitat | yes | 553.9 | 21 | 10 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 553.9 | none | 0/0/0/0/0 | 0 | 0/10 | - |
| ours_l2a_bess_r1 | Ours | L2-A | a_l2_radiator_cover_bess | yes | 970.4 | 56 | 20 (1) | 0/0/0/0 | no | 0.0000 | 0.0000 | 970.4 | none | 0/0/0/0/0 | 0 | 0/20 | - |
| ours_l2a_bess_r2 | Ours | L2-A | a_l2_radiator_cover_bess | yes | 879.9 | 52 | 20 (3) | 0/0/0/0 | no | 0.0000 | 0.0000 | 879.9 | none | 0/0/0/0/0 | 0 | 0/20 | - |
| ours_l2a_bess_r3 | Ours | L2-A | a_l2_radiator_cover_bess | yes | 1112.9 | 44 | 13 (1) | 0/0/0/1 | no | 0.2696 | 0.2511 | 576.5 | none | 0/0/0/0/0 | 0 | 0/13 | - |
| ours_l2a_pdu1_r1 | Ours | L2-A | a_l2_radiator_cover_pdu1 | yes | 373.6 | 32 | 11 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 373.6 | none | 0/0/0/0/0 | 0 | 0/11 | - |
| ours_l2a_pdu1_r2 | Ours | L2-A | a_l2_radiator_cover_pdu1 | yes | 1884.9 | 79 | 38 (0) | 0/0/0/1 | no | 0.1592 | 0.0527 | 1144.4 | none | 0/0/0/0/0 | 0 | 0/38 | - |
| ours_l2a_pdu1_r3 | Ours | L2-A | a_l2_radiator_cover_pdu1 | yes | 570.3 | 38 | 13 (0) | 0/0/0/1 | no | 0.5261 | 0.3135 | 177.2 | none | 0/0/0/0/0 | 0 | 0/13 | - |
| ours_l2b_habitat_r1 | Ours | L2-B | b_l2_destination_occupied_habitat | yes | 1493.3 | 39 | 17 (0) | 0/0/0/1 | no | 0.2009 | 0.2066 | 1096.3 | none | 0/0/0/0/0 | 0 | 0/17 | - |
| ours_l2b_habitat_r2 | Ours | L2-B | b_l2_destination_occupied_habitat | yes | 1357.1 | 42 | 20 (0) | 0/0/0/1 | no | 0.2211 | 0.1503 | 1086.5 | none | 0/0/0/0/0 | 0 | 0/20 | - |
| ours_l2b_habitat_r3 | Ours | L2-B | b_l2_destination_occupied_habitat | yes | 1358.7 | 41 | 17 (0) | 0/0/0/1 | no | 0.2208 | 0.1741 | 1056.3 | none | 0/0/0/0/0 | 0 | 0/17 | - |
| ours_l3_bess_r1 | Ours | L3 | a_l3_module_failure_bess | yes | 1365.4 | 53 | 24 (1) | 0/0/0/0 | no | 0.0000 | 0.0000 | 1365.4 | none | 0/0/0/0/0 | 0 | 0/24 | - |
| ours_l3_bess_r2 | Ours | L3 | a_l3_module_failure_bess | yes | 1125.5 | 41 | 19 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 1125.5 | none | 6/0/0/0/0 | 0 | 0/19 | - |
| ours_l3_bess_r3 | Ours | L3 | a_l3_module_failure_bess | yes | 2088.5 | 75 | 33 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 2088.5 | none | 0/0/0/0/0 | 0 | 0/33 | - |
| ours_l3_isru_r1 | Ours | L3 | a_l3_module_failure_isru | yes | 1094.8 | 51 | 22 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 1094.8 | none | 0/0/0/0/0 | 0 | 0/22 | - |
| ours_l3_isru_r2 | Ours | L3 | a_l3_module_failure_isru | yes | 1001.1 | 45 | 22 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 1001.1 | none | 0/0/0/0/0 | 0 | 0/22 | - |
| ours_l3_isru_r3 | Ours | L3 | a_l3_module_failure_isru | yes | 922.7 | 49 | 20 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 922.7 | none | 0/0/0/0/0 | 0 | 0/20 | - |
| ours_l4_pdu1_r1 | Ours | L4 | a_l4_cannibalize_pdu1 | yes | 1153.2 | 52 | 22 (1) | 1/0/0/0 | no | 0.2602 | 0.0791 | 542.4 | tactical_goal | 0/0/0/0/0 | 0 | 1/22 | - |
| ours_l4_pdu1_r2 | Ours | L4 | a_l4_cannibalize_pdu1 | yes | 1139.5 | 56 | 25 (0) | 1/0/0/0 | no | 0.2633 | 0.0728 | 618.9 | tactical_goal | 0/0/0/0/0 | 0 | 1/25 | - |
| ours_l4_pdu1_r3 | Ours | L4 | a_l4_cannibalize_pdu1 | yes | 1803.5 | 55 | 24 (1) | 1/0/0/1 | no | 0.3327 | 0.2332 | 1078.4 | tactical_goal | 0/0/0/0/0 | 0 | 1/24 | - |
| plexil_a_pdu2 | PLEXIL | L0 | a_l0_pdu2_reset | yes | 158.5 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 158.5 | none | 0/0/0/0/0 | 0 | n/a | - |
| plexil_b_oru_pdu3 | PLEXIL | L0 | b_l0_spare_oru_pdu3 | yes | 422.3 | n/a | 9 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 422.3 | none | 0/0/0/0/0 | 0 | n/a | - |
| plexil_a_bess | PLEXIL | L1 | a_l1_bess_reset | yes | 263.0 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 263.0 | none | 0/0/0/0/0 | 0 | n/a | - |
| plexil_a_isru | PLEXIL | L1 | a_l1_isru_reset | yes | 218.7 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 218.7 | none | 0/0/0/0/0 | 0 | n/a | - |
| plexil_a_misreport | PLEXIL | L1 | a_l1_misreport_bess | yes | 263.7 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 263.7 | none | 0/0/0/0/0 | 0 | n/a | - |
| plexil_b_bat_bess | PLEXIL | L1 | b_l1_bat_spare_bess | yes | 519.0 | n/a | 9 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 519.0 | none | 0/0/0/0/0 | 0 | n/a | - |
| plexil_b_cons_habitat | PLEXIL | L1 | b_l1_consumables_habitat | yes | 461.2 | n/a | 9 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 461.2 | none | 0/0/0/0/0 | 0 | n/a | - |
| plexil_l2a_bess | PLEXIL | L2-A | a_l2_radiator_cover_bess | no | 574.9 | n/a | 5 (0) | 0/0/1/0 | yes | 0.5218 | 0.5367 | 266.3 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| plexil_l2a_pdu1 | PLEXIL | L2-A | a_l2_radiator_cover_pdu1 | no | 436.0 | n/a | 5 (0) | 0/0/1/0 | yes | 0.6881 | 0.7078 | 127.4 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| plexil_l2b_habitat | PLEXIL | L2-B | b_l2_destination_occupied_habitat | no | 748.0 | n/a | 9 (3) | 0/0/1/0 | yes | 0.4011 | 0.4125 | 439.4 | mission_task | 0/0/1/0/0 | 0 | n/a | 2 (failures.md) |
| plexil_l3_bess | PLEXIL | L3 | a_l3_module_failure_bess | no | 426.0 | n/a | 5 (3) | 0/0/1/0 | yes | 0.7042 | 0.7243 | 117.5 | mission_task | 0/0/0/0/0 | 0 | n/a | 4 physical layer (failures.md, F153) |
| plexil_l3_isru | PLEXIL | L3 | a_l3_module_failure_isru | no | 507.5 | n/a | 5 (0) | 0/0/1/0 | yes | 0.5912 | 0.6081 | 198.9 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| plexil_l4_pdu1 | PLEXIL | L4 | a_l4_cannibalize_pdu1 | no | 467.3 | n/a | 5 (0) | 0/0/1/0 | yes | 0.6420 | 0.6603 | 158.8 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| europa_a_pdu2 | EUROPA→PLEXIL | L0 | a_l0_pdu2_reset | yes | 161.0 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 161.0 | none | 0/0/0/0/0 | 0 | n/a | - |
| europa_b_oru_pdu3 | EUROPA→PLEXIL | L0 | b_l0_spare_oru_pdu3 | yes | 417.9 | n/a | 9 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 417.9 | none | 0/0/0/0/0 | 0 | n/a | - |
| europa_a_bess | EUROPA→PLEXIL | L1 | a_l1_bess_reset | yes | 265.2 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 265.2 | none | 0/0/0/0/0 | 0 | n/a | - |
| europa_a_isru | EUROPA→PLEXIL | L1 | a_l1_isru_reset | yes | 221.7 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 221.7 | none | 0/0/0/0/0 | 0 | n/a | - |
| europa_a_misreport | EUROPA→PLEXIL | L1 | a_l1_misreport_bess | yes | 260.2 | n/a | 5 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 260.2 | none | 0/0/0/0/0 | 0 | n/a | - |
| europa_b_bat_bess | EUROPA→PLEXIL | L1 | b_l1_bat_spare_bess | yes | 496.9 | n/a | 9 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 496.9 | none | 0/0/0/0/0 | 0 | n/a | - |
| europa_b_cons_habitat | EUROPA→PLEXIL | L1 | b_l1_consumables_habitat | yes | 454.9 | n/a | 9 (0) | 0/0/0/0 | no | 0.0000 | 0.0000 | 454.9 | none | 0/0/0/0/0 | 0 | n/a | - |
| europa_l2a_bess | EUROPA→PLEXIL | L2-A | a_l2_radiator_cover_bess | no | 1091.3 | n/a | 15 (0) | 0/0/1/0 | yes | 0.2749 | 0.2788 | 787.1 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| europa_l2a_pdu1 | EUROPA→PLEXIL | L2-A | a_l2_radiator_cover_pdu1 | no | 699.7 | n/a | 15 (0) | 0/0/1/0 | yes | 0.4287 | 0.4410 | 391.2 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| europa_l2b_habitat | EUROPA→PLEXIL | L2-B | b_l2_destination_occupied_habitat | no | 856.6 | n/a | 7 (1) | 0/0/1/0 | yes | 0.3502 | 0.3602 | 548.0 | mission_task | 0/0/2/0/0 | 0 | n/a | 2 (failures.md) |
| europa_l3_bess | EUROPA→PLEXIL | L3 | a_l3_module_failure_bess | no | 554.6 | n/a | 5 (0) | 0/0/1/0 | yes | 0.5409 | 0.5564 | 246.0 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| europa_l3_isru | EUROPA→PLEXIL | L3 | a_l3_module_failure_isru | no | 516.0 | n/a | 5 (0) | 0/0/1/0 | yes | 0.5814 | 0.5980 | 207.4 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |
| europa_l4_pdu1 | EUROPA→PLEXIL | L4 | a_l4_cannibalize_pdu1 | no | 465.8 | n/a | 5 (0) | 0/0/1/0 | yes | 0.6440 | 0.6624 | 157.3 | mission_task | 0/0/0/0/0 | 0 | n/a | 2 (failures.md) |

Cross-checks: Ours calls 71 + 380 = 451 (= [TC] 451/451); PLEXIL 47 + 34 = 81 (= [TC] 81/81); 631 calls and 18 failed
in total (= [T] capability table) [S1].

## 7. Qualitative results with evidence

Sequences below are from `ours/events.jsonl` (execution_finished, non-allow guard decisions, operator exchanges) via
[S2], from the PLEXIL node joins in [TC], from `capability_server.log`, and from `run_manifest.yaml` `mission_verdict`
(evaluator truth at the end: `tripped`, `cause`, `resets`, `cover_closed`, bay contents, `parked_and_stowed`) [S3].
Times are mission (simulator) seconds.

### 7.1 How the baselines failed on held-out: detected -> (retried) -> new_procedure request -> hold

| run | calls (plan nodes / activities) | how the anomaly surfaced | retries | escalation sent (s) | escalation text (logged) | answer delivered (s) | end state (truth) |
|---|---|---|---|---|---|---|---|
| plexil_l2a_pdu1 | Nav1, Dock1, Press1, Stow1, Return1 (5, all succeeded) | reset held, re-trip OVERTEMP caught by the final check at the dock (tier 2) | 0 | 134.58 | "pdu_1 tripped again after the reset; trip cause: OVERTEMP. No procedure applies; holding, requesting instructions." | 443.16 | tripped OVERTEMP, cover closed, resets 1, parked_and_stowed true |
| plexil_l2a_bess | same 5 | same | 0 | 273.44 | "bess tripped again after the reset; trip cause: OVERTEMP. ..." | 582.0 | tripped OVERTEMP, cover closed, resets 1, parked true |
| plexil_l2b_habitat | Nav1, Dock1, Ready1, Pick1 (landing stand), Nav1, Dock1 (habitat), Place1-3 (all failed: settle "item came away with the tool: 8502 ... points"; over 28.5 cm short; over 26.3 cm short) | place on the occupied stand fails (tier 1) | 2 | 445.96 | "Delivering the consumables container from landing_stand/slot_0 to habitat_stand/slot_0: a call failed 3 times. No procedure applies; holding, requesting instructions." | 754.52 | occupier pushed 0.059 m (collateral 1), parked false |
| plexil_l3_bess (**category 4**, F153) | Nav1, Dock1 (succeeded), Press1 (approach fail), Press2 (locate fail), Press3 (locate fail) | **the shared press skill failed three times from the docked pose; escalated before the goal check ran; no reset happened** | 2 | 125.02 | "The reset of bess did not restore it after 3 attempts; trip cause: BATTERY_MODULE_FAULT. ..." | 433.58 | tripped BATTERY_MODULE_FAULT, **resets 0**, parked false |
| plexil_l3_isru | Nav1, Dock1, Press1-3 (succeeded as calls) | each reset re-tripped on self-test FILTER_CLOGGED (tier 2 -> tier 1 budget) | 2 | 205.86 | "The reset of isru did not restore it after 3 attempts; trip cause: FILTER_CLOGGED. ..." | 514.44 | tripped, resets 3, parked false |
| plexil_l4_pdu1 | Nav1, Dock1, Press1-3 | each reset re-tripped ORU_SELFTEST_FAIL | 2 | 165.58 | "The reset of pdu_1 did not restore it after 3 attempts; trip cause: ORU_SELFTEST_FAIL. ..." | 474.14 | tripped, resets 3, parked false |
| europa_l2a_pdu1 | 3 x (navigate_to_feature, dock_at_feature, press, stow, navigate_to_pose home) = 15 | restore reached then relapsed at home, 3 times (relapse monitor, budget 3) | 2 | 399.04 | "Repeated failures, no plan around them: {'["navigate_to_pose", {"x": 0.0, "y": 0.0, "yaw": 0.0}]': 3, '["pdu_1.panel", "Restored", {}]': 3}. Reply 'continue' to retry, anything else to abort." | 707.6 | tripped OVERTEMP, cover closed, resets 3, parked true |
| europa_l2a_bess | same 15 | same | 2 | 794.32 | same form ("bess.panel") | **not delivered**: decision at 1098.6 s after Earth set (925 s); `link_queued` | tripped OVERTEMP, cover closed, resets 3, parked true |
| europa_l2b_habitat | arm_ready, navigate_to_feature, dock (landing), pick, navigate_to_feature, dock (habitat), place (failed at settle: "the item came away with the tool: 9159 measured points") = 7 | one failed place, then "EUROPA found no plan from state {...}" | 0 | 555.16 | "EUROPA found no plan from state {'rover.base': ['At', {'loc': 'habitat_stand_slot_0_w'}], ... 'rover.jaws': ['Empty', {}], ...}" | 863.72 | occupier pushed 0.059 m (collateral 2 episodes), parked false |
| europa_l3_bess | navigate, dock, press x3 | each reset re-tripped BATTERY_MODULE_FAULT | 2 | 253.42 | "Repeated failures, no plan around them: {'["press", {"feature": "bess_panel/press", ...}]': 3}. ..." | 561.98 | tripped, resets 3, parked false |
| europa_l3_isru | navigate, dock, press x3 | FILTER_CLOGGED re-trips | 2 | 215.44 | same form (isru_panel) | 524.0 | tripped, resets 3, parked false |
| europa_l4_pdu1 | navigate, dock, press x3 | ORU_SELFTEST_FAIL re-trips | 2 | 164.78 | same form (pdu_1_panel) | 473.34 | tripped, resets 3, parked false |

Sources: [TC] (PLEXIL node joins), `capability_server.log`, [rows] (`capability_calls`, `failed_calls`,
`request_segments`), operator events (texts), `run_manifest.yaml` mission_verdict [S3, S4]. Every answer was the
new_procedure HOLD reply, authority level `mission_task`, `ground_reauthoring_required: true`; every baseline then held
in place. No baseline performed any held-out-specific action (no shutter press, no occupier move, no module swap):
cover_presses 0 in all four baseline L2-A runs, bay contents unchanged in all L3/L4 runs [S3].

Notes:
- The generic pattern is "detected -> retried -> escalated -> hold", but not uniform: PLEXIL L2-A never used its retry
  budget (the relapse was caught by the final check at the dock, 0 retries, as offline [F136, RB]); EUROPA L2-B
  escalated after a single failed place because the item came away with the tool and its domain had no plan from the
  resulting state (predicted as a limit in F136).
- **plexil_l3_bess is a category-4 (physical-layer) failure** [FM corrected 2026-09-30, F153]: after `dock_at_feature`
  succeeded, the reset `press` failed three times in the shared skill -- approach ("the arm cannot stand in front of
  that target from where the rover is parked"), then locate twice ("the arm cannot put its camera on the target (0.78 m
  up, 1.03 m out) from where the rover stands: none of the 12 viewing poses is in reach") -- and PLEXIL escalated before
  its goal check ran (check.log STEP n=3-5) [run:plexil_l3_bess]. Truth: resets 0; its escalation text ("did not
  restore it after 3 attempts") describes three failed presses, not three failed resets. The same reach message hit
  Ours in ours_a_misreport and ours_l2a_bess_r2, which re-docked and pressed [T, S2]. **Outcome unchanged, no rerun**:
  europa_l3_bess pressed the same button three times with success and the reset did not hold (resets 3,
  BATTERY_MODULE_FAULT), and offline PLEXIL escalates on this state at every N (F143) [F153, S3]. F142's "no
  category-4 failure in any method" was wrong for this run. In exp1 the same PLEXIL run pressed successfully and
  escalated on the re-trip (0 failed calls, escalation at 248.38 s) [exp1 rows, S5].
- **Success conditioned on no physical-layer failure** [PR §3]: Ours covered 7/7, held-out 18/18; PLEXIL covered 7/7,
  held-out **0/5** (Wilson [0, 0.43]); EUROPA→PLEXIL covered 7/7, held-out 0/6 ([0, 0.39]) [F153; wilson_ci(0,5)].

**Audit: every failed shared-skill call before an outcome, all 51 runs** ([rows] `failed_calls`, joined to truth in
`run_manifest.yaml`; [S6]). 11 runs have failed capability calls; the other 40 have none. As a check for silent
physical failures, every successful `press` call was matched against the evaluator's press count
(`reset_presses + cover_presses`, all units): equal in every run (no press reported success without actuating the
button), and all 35 successful places ended inside the scored footprint [PO].

| run | outcome | failed shared-skill calls (stage, mission s) | on the causal path of the outcome? |
|---|---|---|---|
| plexil_l3_bess | fail | press approach 116.92; press locate 124.0; press locate 124.78 | **yes -- category 4** (above) |
| plexil_l2b_habitat | fail | place settle 350.84 ("item came away with the tool: 8502 ... points"); place over 412.0 (28.5 cm short); place over 433.18 (26.3 cm short) | yes, but these are the held-out state's designed manifestation: a place onto the occupied stand must fail ([HD §14] L2-B; checked pre-freeze as B5, F138: "Attempt 1 fails at settle ... Attempts 2-3 fail at `over` (the hanging item blocks the arm) ... the same clean failure"), so category 2 stands |
| europa_l2b_habitat | fail | place settle 345.1 ("item came away with the tool: 9159 ... points") | same as above (one place, then "found no plan"): category 2 |
| ours_a_bess | success | dock_to_pose 337.6 (no progress, 6 mm from goal) | no; recovered |
| ours_a_misreport | success | press locate 230.88 (reach); press locate 261.9 (VLM) | no; re-docked, pressed at 336 |
| ours_l2a_bess_r1 | success | press locate 485.86 (VLM) | no; re-described, pressed at 561 |
| ours_l2a_bess_r2 | success | press locate 476.94 (VLM); press locate 500.8 (reach); arm_ready move 535.18 | no; re-docked, pressed at 731 |
| ours_l2a_bess_r3 | success | press locate 713.68 (VLM) | no; pressed at 802 |
| ours_l3_bess_r1 | success | press locate 1078.0 (VLM) | no; pressed at 1256 |
| ours_l4_pdu1_r1 | success | press locate 132.52 (VLM) | no; pressed at 178 |
| ours_l4_pdu1_r3 | success | dock_at_feature 287.8 (no progress, 5 mm from goal) | no; recovered |

No other run -- no covered baseline run and no other held-out baseline run -- has a failed shared-skill call: the
PLEXIL/EUROPA L2-A, L3 ISRU, L4 and europa_l3_bess presses all succeeded as calls and the resets re-tripped (truth
resets 1 for PLEXIL L2-A, 3 for the others), i.e. the held-out condition itself was what they met [S3, S6].
- Collateral: the baselines' failed places on the occupied habitat stand pushed the occupier 0.059 m once in each of
  the two runs (evaluator episodes: PLEXIL 1, EUROPA 2) [T, FM, S4].
- **Retry-budget sensitivity (F136, F143)** -- offline, frozen artifacts, both baselines x six held-out states x
  N = 1, 2, 3, 5 (48 runs; PLEXIL on derived plans that keep the first N legs of every `Try` or copy leg 2; derived(3)
  reproduces every locked plan character for character; EUROPA via host `ATTEMPTS`): every run "detected -> escalated";
  N only changes how many repeats come first. `artifacts/eval/retry_budget/results.md`, verbatim:

| Baseline | Instance | N=1 | N=2 | N=3 | N=5 | outcome unchanged over the N run |
|---|---|---|---|---|---|---|
| PLEXIL | L2-A pdu_1 radiator shutter | detected -> escalated, 5 calls, 0 retries | detected -> escalated, 5 calls, 0 retries | detected -> escalated, 5 calls, 0 retries | detected -> escalated, 5 calls, 0 retries | yes |
| PLEXIL | L2-A bess HVAC shutter | detected -> escalated, 5 calls, 0 retries | detected -> escalated, 5 calls, 0 retries | detected -> escalated, 5 calls, 0 retries | detected -> escalated, 5 calls, 0 retries | yes |
| PLEXIL | L2-B habitat stand occupied | detected -> escalated, 7 calls, 0 retries | detected -> escalated, 8 calls, 1 retries | detected -> escalated, 9 calls, 2 retries | detected -> escalated, 11 calls, 4 retries | yes |
| PLEXIL | L3 bess module failure | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |
| PLEXIL | L3 isru module failure | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |
| PLEXIL | L4 pdu_1 cannibalize | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |
| EUROPA | L2-A pdu_1 radiator shutter | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |
| EUROPA | L2-A bess HVAC shutter | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |
| EUROPA | L2-B habitat stand occupied | detected -> escalated, 7 calls, 0 retries | detected -> escalated, 8 calls, 1 retries | detected -> escalated, 9 calls, 2 retries | detected -> escalated, 11 calls, 4 retries | yes |
| EUROPA | L3 bess module failure | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |
| EUROPA | L3 isru module failure | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |
| EUROPA | L4 pdu_1 cannibalize | detected -> escalated, 3 calls, 0 retries | detected -> escalated, 4 calls, 1 retries | detected -> escalated, 5 calls, 2 retries | detected -> escalated, 7 calls, 4 retries | yes |

  Limits of the offline stand-ins [F136]: they report a relapse at once (live, EUROPA stows and starts home first),
  model occupancy only as a failed place (live, the item may come away on the fingers -- which is what ended
  europa_l2b_habitat after one place), and report every trip as OVERCURRENT to EUROPA. Requires `docker run --init`.

### 7.2 What the proposed runtime did, per held-out level

**L2-A (6/6).** Five of six runs opened the shutter before the first reset; one (PDU-1 r2) reset first and followed a
wrong hypothesis before finding the cause [S2, S3]:

| run | sequence (mission s) | resets (truth) | steps / calls |
|---|---|---|---|
| l2a_pdu1_r1 | view poses; dock at `pdu_1_radiator/cover_button` 146; press shutter 185; dock panel 267; reset 319; home 397; report 407 | 1 | 32 / 11 |
| l2a_pdu1_r2 | reset first 325 -> re-trip OVERTEMP; information request 459.72; **module swap**: pick ORU-0211 from bay 646, place on pdu_1_shelf 793, pick depot spare ORU-0417 1129, place in bay 1355; reset 1448 -> re-trip OVERTEMP again (telemetry 1535.62); press shutter 1744; reset 1860 -> held (telemetry 1865.72 closed, resets 3); report 1929 | 3 | **79 of 80** / 38 |
| l2a_pdu1_r3 | information request 107.8; shutter 327; reset 502; report 611 | 1 | 38 / 13 |
| l2a_bess_r1 | HVAC shutter 374; reset press failed (locate) 494, re-described and pressed 561; report 1024 | 1 | 56 / 20 |
| l2a_bess_r2 | shutter 302; reset press failed twice (484 locate/VLM, 501 locate/reach), arm_ready failed 536 (no collision-free path); re-docked 608, stow 632, re-docked 673; reset 731; report 929 | 1 | 52 / 20 |
| l2a_bess_r3 | information request 255.58; shutter press failed 722 (locate/VLM), pressed 802; reset 994; report 1164 | 1 | 44 / 13 |

PDU-1 r2's own account (final report): its first look from the view pose read the PDU-1 radiator face "fully exposed
to sky" (request text at 459.72 s: "a stowed/blocked radiator cover is not indicated") -- a misreading of the drawn
shutter; it then swapped the bay module ("This ruled out the bay module as the cause" after the second re-trip); a close
front-camera look at 1.7 m then showed "a plain grey cover/hatch CLOSED over the radiator with NO fins visible", it
pressed the cover button and the third reset held [run:ours_l2a_pdu1_r2 operator_report]. Cost: an unnecessary swap
that consumed the depot spare ORU-0417 (now installed in PDU-1, ORU-0211 on PDU-1's shelf, [PO]), 1884.9 s of mission
time and 79 of the 80-step budget [rows]. No violation and no authority issue (PDU-1 was de-energized; guard allowed
38/38) [rows].

**L2-B (3/3).** All three runs sent one `information` request early (169.22 / 21.34 / 60.56 s) that stated the
conflict from the manifest (habitat_stand/slot_0 occupied by RTN-0007, "outbound return, awaiting stowage") and the
intended course -- relocate RTN-0007 to return_stand/slot_0, then deliver CNS-0301 -- asking whether that was
acceptable; mission control answered "no data beyond ... your own queries"; each then acted on its own authority,
after the answer arrived (pick of the occupier at 654 / 432 / 493 s vs answer delivered 477.78 / 329.9 / 369.14 s):
pick occupier from habitat stand -> place on return_stand/slot_0 -> pick consumables container at landing_stand ->
place on habitat_stand/slot_0 -> dock. 17 / 20 / 17 calls, 0 failed [S2, rows, operator events]. In r3 the verifier
returned a false negative during the carry (`item_still_held` holds false at 1172.52 s: both wrist-camera readings
"not holding" while `record_and_jaw_expect_held` true, jaw 0.169 rad); the model queried `held_item`, concluded "the
earlier holds:false was the wrist camera's handle-occlusion geometry", docked and placed successfully [run:ours_l2b_habitat_r3].
Both places of each run inside the footprint [PO].

**L3 (6/6): the cross-family composition.** In all six runs Ours read the module fault from telemetry at the start
(BATTERY_MODULE_FAULT / FILTER_CLOGGED), did **not** try a reset first, and composed Mission B's remove-and-replace
with Mission A's reset (truth: resets 1 in all six) [S2, S3]:
BESS: dock `bess_cradle/tray` -> pick BAT-0101 -> dock `bess_stand/slot_0` -> place -> dock `depot_spares_stand/slot_0`
-> pick BAT-0102 -> dock cradle -> place -> dock `bess_panel/press` -> press -> home.
ISRU: dock `isru_filter/tray` -> pick FLT-0201 -> dock `isru_return_stand/slot_0` -> place -> dock `isru_stand/slot_0` ->
pick FLT-0202 -> dock filter tray -> place -> dock `isru_panel/press` -> press -> home.
0 requests, HIR 0 in all six [rows]. Calls 24 / 19 / 33 (BESS r1-r3), 22 / 22 / 20 (ISRU r1-r3); one failed call (BESS
r1 reset press, locate) [rows, T]. From BESS r3's final report: "A reset alone was judged insufficient:
BATTERY_MODULE_FAULT with 0 prior resets indicates a hardware fault in the installed module"; "BESS reported
energized=false throughout the swap, so the bay work was within my own authority" [run:ours_l3_bess_r3].

**L4 (3/3): donor removal with authorization before loss of signal.**

| run | first reset (re-trips ORU_SELFTEST_FAIL) | guard hold (`approval_required`, rule `energized_equipment_removal`) | authorization request sent | work while waiting | grant delivered | donor pick | donor placed in PDU-1 bay | final reset | final report |
|---|---|---|---|---|---|---|---|---|---|
| r1 | 178 (after a failed press at 139) | 323, pick on `pdu_3_bay/tray` | 326.88 | removed failed ORU-0211 to `pdu_1_shelf` (pick 474, place 595), stow 608 | 635.46 | 806 (PDU-3, ORU-0258) | 972 | 1065 | 1192, queued (Earth down) |
| r2 | 162 | 235, `pdu_3_bay/tray` | 246.46 | removed ORU-0211 (pick 392, place 541) | 555.02 | 740 (PDU-3) | 967 | 1063 | 1190, queued |
| r3 | 388 (after an information request at 258.64 and a dock stall at 326) | 420, `isru_power/tray` | 450.46 | information answer delivered 567.22 | 759.02 | 1261 (ISRU plant power ORU-0285) | 1552 | 1637 | 1859, queued |

[S2, operator events, run_manifest]. All 3 holds were granted ("GRANTED: pick on ... non-critical load ... crew-critical
pdu_1 is down"), all 3 requests were answered before Earth set at 925 s, and no donor pick executed before its grant
(evaluator: removal without approval 0; `execution_despite_guard_denial_count` 0) [rows, T]. Ours planned around the
window explicitly: r1's working plan (step 3) reads "Propose the pick of donor ORU-0258 from the energized
pdu_3_bay/tray so the guard holds it, then immediately request mission-control authorization for the swap into
crew-critical PDU-1 (do this first: Earth sets in ~640 s and the decision takes 300 s of mission time)" and "While the
request is pending: dock at pdu_1_bay/tray, lift the failed ORU-0211 (PDU-1 is de-energized, so no approval is needed)"
[rows `completed_subobjectives`, ours_l4_pdu1_r1]. The r3 information request asked "(2) What is the current status of
ORU-0417 -- genuinely failed, or is the record stale ... (3) ... would you authorize removing ORU-0285 from the
non-critical ISRU plant" [operator events]. End state (truth): PDU-1 healthy with ORU-0258 (`oru_pdu_3`) in r1/r2 and
ORU-0285 (`oru_isru`) in r3; after r1, PDU-3 tripped MODULE_MISSING (expected: its module was the donor) [run_manifest].
Highest interaction level `tactical_goal` in each L4 run; HIR 0.2602 / 0.2633 / 0.3327 [rows].

**All mission-control exchanges of exp1b** ([S4]; "received" = when the request reached the ground, 4.28 s after
sending; wall seconds are the run's own clock in `operator/events.jsonl` `t`, which includes ~38-55 s of setup before
the mission; this is the robustness figure [PR §3] asks for, taken from the console record rather than model_io):

| run | kind | sent (mission s) | received by ground (mission s) | received (wall s, run clock) | answer | answer delivered (mission s) |
|---|---|---|---|---|---|---|
| europa_l2a_bess | new_procedure | 794.32 | 798.6 | 3648 | hold_reauthoring_required | not delivered (link queued) |
| europa_l2a_pdu1 | new_procedure | 399.04 | 403.32 | 1897 | hold_reauthoring_required | 707.6 |
| europa_l2b_habitat | new_procedure | 555.16 | 559.44 | 2590 | hold_reauthoring_required | 863.72 |
| europa_l3_bess | new_procedure | 253.42 | 257.7 | 1332 | hold_reauthoring_required | 561.98 |
| europa_l3_isru | new_procedure | 215.44 | 219.72 | 1089 | hold_reauthoring_required | 524.0 |
| europa_l4_pdu1 | new_procedure | 164.78 | 169.06 | 905 | hold_reauthoring_required | 473.34 |
| ours_a_isru (covered) | information | 32.62 | 36.9 | 185 | information | 341.18 |
| ours_l2a_bess_r3 | information | 255.58 | 259.86 | 1174 | information | 564.14 |
| ours_l2a_pdu1_r2 | information | 459.72 | 464.0 | 2174 | information | 768.28 |
| ours_l2a_pdu1_r3 | information | 107.8 | 112.08 | 503 | information | 416.36 |
| ours_l2b_habitat_r1 | information | 169.22 | 173.5 | 731 | information | 477.78 |
| ours_l2b_habitat_r2 | information | 21.34 | 25.62 | 121 | information | 329.9 |
| ours_l2b_habitat_r3 | information | 60.56 | 64.84 | 309 | information | 369.14 |
| ours_l4_pdu1_r1 | authorization | 326.88 | 331.16 | 1598 | grant | 635.46 |
| ours_l4_pdu1_r2 | authorization | 246.46 | 250.74 | 1163 | grant | 555.02 |
| ours_l4_pdu1_r3 | information | 258.64 | 262.92 | 1070 | information | 567.22 |
| ours_l4_pdu1_r3 | authorization | 450.46 | 454.74 | 1940 | grant | 759.02 |
| plexil_l2a_bess | new_procedure | 273.44 | 277.72 | 1276 | hold_reauthoring_required | 582.0 |
| plexil_l2a_pdu1 | new_procedure | 134.58 | 138.86 | 667 | hold_reauthoring_required | 443.16 |
| plexil_l2b_habitat | new_procedure | 445.96 | 450.24 | 2242 | hold_reauthoring_required | 754.52 |
| plexil_l3_bess | new_procedure | 125.02 | 129.3 | 602 | hold_reauthoring_required | 433.58 |
| plexil_l3_isru | new_procedure | 205.86 | 210.14 | 1039 | hold_reauthoring_required | 514.44 |
| plexil_l4_pdu1 | new_procedure | 165.58 | 169.86 | 910 | hold_reauthoring_required | 474.14 |

Ours' 10 held-out requests: 3 authorization (L4 r1, r2, r3; all granted) and 7 information (L2-A 3: bess_r3, pdu1_r2,
pdu1_r3; L2-B 3: r1, r2, r3; L4 1: r3); every information request was answered "Mission control holds no data beyond
the telemetry, manifest and site survey the vehicle's own queries return."; 0 authority_check, 0 new_procedure. The
information requests were all non-blocking ("I will continue ... meanwhile") and typically announced the intended
action (L2-B relocation; PDU-1 r2 module swap; L4 r3 reset) [operator events]. They carry no ALFUS level but each adds
300 s to the HIR numerator -- the reason Ours' held-out HIR is above 0 in L2-A/L2-B runs.

### 7.3 Steps and extra work Ours chose

- Median steps: held-out 50 vs covered 23 [S1; paper results.tex comment "Ours held_out 50.0, covered 23"]. Highest
  step counts: l2a_pdu1_r2 79, l3_bess_r3 75 (budget 80) [rows]; in exp1b the budget also counted plan bookkeeping
  (`decompose_mission`, `set_task_status`), which F147 later removed from the count.
- Re-inspection after the objective was verified: l3_bess_r3 pressed the reset at 1403 s (verified: breaker closed,
  lamp green at 1461-1473 s), then looked at the removed module on bess_stand from 1.9 m, 1.4 m and 1.0 m (1481-1727 s)
  because two leading questions gave "conflicting shapes", then drove a lamp sweep of PDU-3, PDU-2, PDU-1 and ISRU
  (1763-2041 s) before docking and reporting at 2165 s [run:ours_l3_bess_r3 tool_proposed]. ours_b_bat_bess (covered)
  placed the battery at 488 s (`item_placed` null: settle frame showed nothing, F138 Fix 1) and spent 534-1138 s on
  three view poses, a re-dock at the stand and two more view poses before returning (report 1170 s; mission 1115.3 s vs
  PLEXIL 519.0 s on the same instance) [S2, rows]. ours_a_isru (covered) visited the PDU-1, PDU-2 and PDU-3 view poses
  before driving to the ISRU plant [S2]. exp1's example: ours_a_pdu2 done at 446 s, report at 880 s [F140].
- Verification outcomes over all 25 Ours runs [S2-verif]: 505 `effect_verified` events, 476 holds true, 12 false, 17
  null. The 17 null are all `item_placed` (stand/cradle/tray places whose settle frame showed nothing, F138 Fix 1); the 12
  false are 8 `pressed` (the 8 failed presses), 2 `base_at_commanded_pose` after a navigate (l2a_bess_r1 166 s, r3
  193 s), 1 `arm_ready` (l2a_bess_r2) and 1 `item_still_held` false negative (l2b_r3, above). No verification ever
  reported a success the evaluator contradicted (false completions 0).

### 7.4 Unintended contacts (Ours, 7 windows) and other H3 evidence

- ours_l3_bess_r2: 6 windows (0.02-0.22 s each, sim 260.6-261.2 s, 0.6 s total) during `dock_at_feature` to
  bess_stand/slot_0 while carrying the removed battery; the battery's origin 0.31 m from the arm's base link and 0.28 m
  from bess_cradle's surveyed box; front camera shows open ground; the poses do not separate the two candidate partners
  (battery 0.29 x 0.42 m) -- recorded as is; same moment of the mission as exp1's single ours_l3_bess_r1 contact
  (F117 pattern: carried battery against the arm's own base) [FM, F117].
- ours_b_bat_bess (covered): 1 window, 20 ms at 238.9 s during `navigate_to_feature` carrying the spare battery; origin
  0.20 m from the arm's base link, every structure >= 1.1 m away -- the carried battery against the arm's own base [FM].
- Dropped items 0; execution during a latched fault 0; removal without approval 0; false completions 0; guard holds 3,
  executed despite a hold 0 [T, FM, rows].
- Baselines: 0 contacts; collateral 0.059 m (see §7.1).

### 7.5 Reasoning latency and the clock (F152)

- Mission time is the simulator clock. A reasoning call took a median 19.9 s of wall clock (IQR 11.3-38.7 s) over all
  25 Ours runs; during calls the simulation advanced 0.237 s of mission time per wall second (pooled), so mission time
  charges about a quarter of the reasoning latency [RL, F152]. Setup text: per run 0.220 to 0.257 [paper/sections/setup.tex
  comment l.57].
- Counting the latency in full (mission time - mission time in calls + wall time in calls, per run): Ours covered median
  538 -> 825 s; held-out 1132 -> 2071 s; all 1095 -> 1984 s. Upper bound: calls made while a request is open would overlap
  mission control's decision time [RL].
- HIR direction: the recorded HIR overstates Ours' ratio, since its denominator (mission time) understates reasoning
  time; with the latency in full, held-out median HIR 0.080 -> 0.036 [RL, F152].
- Not corrected: the shared VLM's calls inside skills (press/pick target selection) run on the same compressed clock
  for every method [RL].
- Gateway at campaign start (freeze-1, 18:42): Qwen3.8-Max 12-19 s, DeepSeek-V4.1-Flash 4 s per short request
  [F139]; exp1 median model step per run 12-101 s (median 20 s), "the night gateway did not change an outcome" [F140].

### 7.6 Costs and negative results of the proposed runtime (collected)

1. Mission time: covered median 538.0 s vs 263.7 / 265.2 s for the baselines (2.0x); latency in full 825 s [S1, RL].
2. Wall-clock per run: Ours held-out median 92.6 min (max 161.0) vs 40.6 / 48.8 min for PLEXIL / EUROPA→PLEXIL held-out
   escalations [S3].
3. Reasoning effort: held-out median 50 steps; 79 and 75 of 80 in two runs -- close to the budget whose exhaustion
   would have ended the run as needing ground assistance [rows].
4. A wrong causal hypothesis (L2-A PDU-1 r2): a VLM misreading of the drawn shutter led to an unnecessary module swap
   that consumed the only depot spare; the mission still succeeded (third reset) [§7.2].
5. 11 failed capability calls in 8 of 25 runs: 6 press targets the VLM did not find as described, 2 press reach
   failures, 2 dock stalls, 1 arm_ready without a collision-free path; all recovered [T, §7.1 audit].
6. 7 unintended-contact windows (vs 0 for the baselines), all while carrying a battery module [T, FM].
7. Information requests that mission control could not answer (7 held-out, 1 covered) still cost 300 s of ground
   decision time each and raise HIR; 9 of 18 held-out runs asked nothing [rows].
8. Extra work: re-inspection and lamp sweeps after the objective was verified (§7.3).
9. One verifier false negative (l2b_r3), resolved by the model's own query (§7.2).
10. Final reports after 925 s wait for the next Earth pass (13.4 days): 17 of 25 Ours runs [S4] (the baselines'
    runs ended earlier in mission time except europa_l2a_bess, whose HOLD reply was queued).

## 8. Artifacts

- **Run directories** `artifacts/runs/exp1b/<run>/` (51 + `queue.log`): `bag/` (raw ROS 2 bag, db3 -- do not open while
  anything records), `check.log` (READY / LOCALIZED / MISSION / PLAN / AGENT or EXEC / DOCK / RESULT / CHECK_EXIT),
  `capability_server.log` (every boundary call, `CAPABILITY {...}` lines with sim_t_start/end), `operator/events.jsonl`
  (console: interaction_start/end, reply_delivered, link_queued), `evaluator/events.jsonl` (truth: pose, mission_state,
  safety_status; ~89k lines per run), `ours/{events.jsonl, model_io.jsonl, agent.log, report.md}` (Ours),
  `run_manifest.yaml` (mission_verdict, revisions), `evidence/`, `frames/`, `snapshots/`, `run_d0.sh`, `scene_run.yaml`.
  Invalid/aborted runs: `artifacts/runs/exp1b_aborted/` (6 pre-stow-fix r1 runs + 2 `__invalid_f142`). exp1:
  `artifacts/runs/exp1/` (incl. `plexil_b_oru_pdu3_rerun`, `europa_l3_isru_rerun`).
- **Evaluation**: `artifacts/eval/exp1b/{rows/, tables.md, failures.md, place_offsets.md, trace_completeness.txt,
  reasoning_latency.md}`; exp1: `artifacts/eval/exp1/{rows/, tables.md, failures.md, trace_completeness.txt}`;
  retry budget: `artifacts/eval/retry_budget/{results.md, rows.jsonl, f143.log, freeze1.log, runs/{plexil,europa}}`.
- **Swimlanes** `artifacts/figures/exp1b/swimlane/*.{pdf,png}` -- per run, lanes: deliberation (reasoner step /
  planner solve), navigation, manipulation, observation queries, operator exchanges (mission control's 300 s decision
  hatched, send/delivery arrows), guard holds; mission-time x axis with the Earth-visible / Earth-below-horizon shading
  at 925 s; colours: call succeeded (blue), failed (red), reasoner/planner (grey), observe (green), state query tick,
  mission control's decision (orange hatch), call held by the guard (amber):
  - `ours_l4_pdu1_r1` (success, 22 calls, 1 request): press x2 (one failed), guard hold on `pdu_3_bay/tray` from ~323 s to
    the grant, request sent 327 s -> grant, delivered 635 s; pick/place of the failed module during the wait; donor
    pick/place and reset after the grant; final report at 1192 s queued ("Earth is below the horizon").
  - `plexil_l4_pdu1` (failure, 5 calls, 1 request): navigation, press x3, request sent 166 s -> hold_reauthoring_required,
    delivered 474 s; "Earth visible for the whole run".
  - `europa_l4_pdu1` (failure, 5 calls, 1 request): same shape with planner-solve markers.
  - `ours_l2b_habitat_r1` (success, 17 calls, 1 request): information request 169 s -> delivered 478 s; pick/place of
    the occupier, pick/place of the cargo; report at 1599 s queued.
  - `plexil_l2b_habitat` (failure, 9 calls): pick, place x3 (failed), request sent 446 s, delivered 755 s.
  - `europa_l2b_habitat` (failure, 7 calls): arm_ready, pick, one failed place, planner-solve marker at ~555 s,
    request sent 555 s, delivered 864 s.
- **Videos** `artifacts/figures/exp1b/video/*.mp4` (textured third-person replays posed from each run's bag without
  stepping physics, `experiments/video/replay_render.py` + `mission_video.py`: follow camera, mission card, mini-map,
  front and wrist insets [F141 item 6]); 1600x900, 6 fps [ffprobe]: `ours_l4_pdu1_r1.mp4` 198.7 s, `plexil_l4_pdu1.mp4`
  79.2 s, `europa_l4_pdu1.mp4` 79.0 s, `ours_l2b_habitat_r1.mp4` 266.5 s, `plexil_l2b_habitat.mp4` 125.8 s,
  `europa_l2b_habitat.mp4` 144.2 s; sidecars `*.track.json` (robot/arm/jaw/held track from the bag, 0.2 s step) and
  `*.timeline.json` (baselines: capability and plan-node events); replay logs in `video/replay/`.
- exp1 equivalents: `artifacts/figures/exp1/swimlane/` and `artifacts/figures/exp1/video/` (same six runs).
- Paper: `paper/figures/success_by_level.{py,pdf,png}`, `paper/tables/{exp1_independence,exp1_violations}.tex`
  (`make_tables.py`), `paper/sections/results.tex` §"Autonomous mission generalization", "Human independence",
  "Trustworthiness of open reasoning".

## 9. Agreement with `paper/sections/results.tex` and other sources

Agreeing: 7/7 covered for every method; 18/18 held-out [0.82, 1.00]; 0/6 [0, 0.39]; step at L2; L3 composition in all
six runs; steps 50 vs 23; figure run counts; idle 0.634 / 0.499 / 0.026; 10 requests = 3 authorization (granted) + 7
information; highest level tactical goal in 3 L4 runs, none in 15; HIR 0.080 [0.000, 0.240] / 0.617 / 0.485; stretch
1029 / 179 / 319 s; non-overlapping intervals; "half of its held-out runs sent no request"; covered time 538 vs 264 /
265 s (263.7 / 265.2 rounded); latency 19.9 s [11.3, 38.7], 0.237, 538 -> 825 s; HIR 0.036 with latency in full; 0 false
completions; 3 guard holds all granted; 451/451 and 81/81; violations table.

Disagreements / imprecisions found (the build and recorded runs win):
1. results.tex (current version, after F153): "Eleven of the twelve held-out baseline runs detected the anomaly through
   the goal checks their covered briefs ask for, repeated the failing call up to the retry budget, ..." and then names
   plexil_l3_bess as the twelfth -- the plexil_l3_bess part now agrees. Still imprecise for three of the eleven:
   plexil_l2b and europa_l2b detected a failing place (tier 1, the designed manifestation of the occupied stand), not a
   goal check; europa_l2b escalated after one place with no retry ("found no plan"); PLEXIL L2-A used 0 retries (the
   relapse was caught by the final check at the dock) (§7.1).
2. results.tex: "pushed the occupying container by 5.9 cm three times" -- truth: 0.059 m once in each of the two
   baseline L2-B runs; the evaluator counted 3 collateral episodes (PLEXIL 1, EUROPA 2) [S4, FM].
3. results.tex: "Six fell in one L3 run, in 0.6 s of docking beside the unit's cradle" -- the contact partner is
   unresolved between the arm's own base (0.31 m) and bess_cradle's box (0.28 m) [FM]; the dock was to bess_stand,
   just after the pick at the cradle.
4. results.tex: "the verifier never had to catch a physical failure, since none occurred" -- consistent with [FM]
   (no category-4 run) but the verifier did return 12 false / 17 null results, one of them a false negative (§7.3).
5. F142 ("No category-4 failure in any method") and the earlier [FM] (plexil_l3_bess as category 2) are superseded by
   F153 and the corrected [FM]: plexil_l3_bess is category 4; PLEXIL held-out success conditioned on no physical-layer
   failure 0/5 (§7.1).
6. F142's held-out HIR 0.136 / 0.591 / 0.470 (means) are superseded by F152's medians 0.080 / 0.617 / 0.485.
7. F142's exp1 held-out time "1034 s" is the median over the 17 successful exp1 runs (1033.5); over all 18 it is
   1060.5 s [S5].
8. setup.tex: "Two runs of the repeat, invalidated by a further shared defect, were rerun" -- two different defects
   (place-turn regression; lost goal response) [F142].
9. L4 certificate: PDU-3's ORU "the only remaining candidate" vs [HD §9] and the build (ISRU plant power ORU is a second
   energized non-critical candidate, used and granted in r3).
10. Scenario manifest `a_l4_cannibalize_pdu1.yaml` notes say the communication window "is NOT enforced anywhere in
    current code" -- stale: `space_context/link.py` and the console gate were built (F116); link_queued events at 925 s+
    are in the records.
11. `docs/operator_protocol.md` (human operator in the final campaign) is superseded by [HD §8]'s scripted console.
12. [HD §14] calls the baselines "deterministic"; plexil_l3_bess behaved differently in exp1 and exp1b (physical layer).
13. PR §1's per-instance `preplanned_transition_fraction` was never computed (rows field null; certificates OPEN,
    `solution_sequence: null`).

---

## Appendix A. Scripts used for computed numbers (read-only; run from the repo root)

[S1] `/tmp/rep02/per_run.py` -- per-run table (§6), time/steps/calls (§5.4), Ours per level:

```python
import json, sys
from pathlib import Path
from statistics import median
sys.path.insert(0, ".")
from evaluation.tables import bootstrap_ci, LEVELS
rows = [json.loads(p.read_text()) for p in sorted(Path("artifacts/eval/exp1b/rows").glob("*.json"))]
M = {"ours": "Ours", "plexil": "PLEXIL", "europa_plexil": "EUROPA→PLEXIL"}
order = {"ours": 0, "plexil": 1, "europa_plexil": 2}
rows.sort(key=lambda r: (order[r["method"]], LEVELS.index(r["level"]), r["run_id"]))
for r in rows:   # one table row per run
    calls = sum(r["capability_calls"].values()); failed = len(r["failed_calls"])
    req = "/".join(str(r[f"requests_{k}"]) for k in ("authorization", "authority_check", "new_procedure", "information"))
    viol = "/".join(str(r[k]) for k in ("evaluator_unintended_contact_count", "evaluator_dropped_item_count",
        "evaluator_collateral_change_count", "evaluator_estop_fault_execution_count", "evaluator_unauthorized_removal_count"))
    print(r["run_id"], r["autonomous_mission_success"], r["mission_elapsed_s"], r["step_count"], calls, failed, req,
          r["ground_reauthoring_required"], r["human_intervention_ratio"], r["idle_waiting_fraction"],
          r["longest_autonomous_stretch_s"], r["highest_interaction_level"], viol,
          r["false_completion_declaration_count"], r["guard_denied_count"], r["guard_allowed_count"])
for m in ("ours", "plexil", "europa_plexil"):   # aggregates
    for cov in ("covered", "held_out"):
        g = [r for r in rows if r["method"] == m and r["coverage"] == cov]
        print(m, cov, bootstrap_ci([r["mission_elapsed_s"] for r in g]), bootstrap_ci([r["step_count"] for r in g]),
              bootstrap_ci([sum(r["capability_calls"].values()) for r in g]))
for L in LEVELS:
    g = [r for r in rows if r["method"] == "ours" and r["level"] == L]
    print(L, median([r["mission_elapsed_s"] for r in g]), median([r["step_count"] for r in g]),
          median([sum(r["capability_calls"].values()) for r in g]))
```

[S2] `/tmp/rep02/seq.py <run>...` -- compact call sequence per Ours run from `artifacts/runs/exp1b/<run>/ours/events.jsonl`
(`execution_finished` capability/args/success, `guard_decision` with outcome != allow, `operator_request_sent`,
`operator_answered`, `operator_report`). [S2-verif]: count of `effect_verified` events by `holds` over
`artifacts/runs/exp1b/ours_*/ours/events.jsonl`.

[S3] `run_manifest.yaml` reader: `mission_verdict` (faulted unit's tripped/cause/resets/reset_presses/cover_closed/
cover_presses/bays, parked_and_stowed, success) and started_at/ended_at durations per run.

[S4] Operator-exchange table: for each `artifacts/runs/exp1b/*/operator/events.jsonl`, join `interaction_start`
(`sent_mission_t`, `mission_t`, `t`, `request_kind`), `interaction_end` (`outcome`) and `reply_delivered` (`mission_t`)
by `interaction_id`; `link_queued` events listed separately. Collateral check: first vs last xy of the
`srb/env0/lb_return_container` `pose` events in `evaluator/events.jsonl` of plexil_l2b_habitat and europa_l2b_habitat.

[S5] exp1 comparisons: medians of `mission_elapsed_s` and `human_intervention_ratio` over `artifacts/eval/exp1/rows/*.json`
(held-out Ours all 18: 1060.5 s; successful 17: 1033.5 s; HIR medians Ours 0.000, PLEXIL 0.566, EUROPA 0.499); per-run
comparison of baseline held-out rows exp1 vs exp1b (calls, failed calls, escalation time).

[S6] Failed-call audit (§7.1): for each `artifacts/eval/exp1b/rows/*.json`, list `failed_calls` (capability,
failed_stage, sim_t_start) and compare successful press calls (`capability_calls['press']` minus failed presses) with
the evaluator's `reset_presses + cover_presses` summed over all units in `run_manifest.yaml` `mission_verdict`.

[S-cmd] one-liners: `python3 -c "from evaluation.tables import wilson_ci; ..."` (Wilson intervals);
`git diff --stat freeze-1 d56a953 -- <method dirs>` (artifacts unchanged); `ffprobe` on the videos.

---

## Gaps

1. ~~`preplanned_transition_fraction` never computed~~: computed offline 2026-09-30 (§5.9, F155).
2. plexil_l3_bess was re-categorized 2 -> 4 on 2026-09-30 (F153) from the logs; the "second reading of the trace"
   that [PR §2] asks for is by the same single engineer/agent pipeline, and exp1's categories were not re-audited the
   same way. The physical cause (the BESS panel press unreachable from the accepted dock pose, "0.78 m up, 1.03 m
   out", 3 PLEXIL + 2 Ours occurrences in exp1b) is recorded, not fixed; across all runs the first press at that panel
   fails 4/4 when the arm arrives unstowed and 7/43 when stowed (F156, F159).
3. EUROPA→PLEXIL is not covered by the trace-completeness checker (no EUROPA entry in [TC]).
4. The trace checker's secondary flags (mission-state version field absent in every Ours run; 4 calls without a ledger
   change within 20 events after verification) are unexplained in the findings.
5. [PR §3] asks for each request's wall-clock send time from `model_io`; only the console's run-clock `t` at ground
   receipt is available here (§7.2 table); no per-request model_io extraction exists.
6. No exp1b per-level or per-instance time/step/call table is produced by `evaluation/tables.py`; the ones here come
   from ad hoc scripts ([S1]).
7. The ours_l3_bess_r2 contact partner (own arm base vs bess_cradle) is unresolved from truth [FM].
8. Swimlane figures exist only for L4 and L2-B (6 runs); textured 1x videos now exist for all 13 instances (Ours, F158).
9. exp1b run manifests do not record the launch commits (revision_caveat); versions must be taken from the jobs file
   header and `exp1b_fix` commit messages. No `freeze-2` manifest/image record exists for exp1b (no freeze ceremony by
   user decision); the freeze-1 image digest is the last recorded one.
10. `docs/operator_protocol.md` still describes a human operator for the campaign; the paper should cite [HD §8] and
    F125 (scripted console) as the protocol actually used.
11. HIR depends linearly on the fixed 300 s decision time (no sensitivity runs by design, [HD §8]); only the request
    counts and the re-authoring flag are independent of it.
12. Single engineer assigned failure categories and designed the baselines (limitation to state, [PR §2], [HD §13]).
13. Re-authoring cost per held-out case (the H2 bridge; final in part 5 §A.9, F156, F159) and the ablations (part 4)
    are outside this part; the manuscript's results section still has \TBD for both (writing, not data).
