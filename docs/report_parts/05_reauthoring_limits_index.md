# Part 05 -- Re-authoring study, validity and limitations, artifact and manuscript index

Snapshot: written 2026-09-30, sources read up to 10:28 CST (02:28 UTC), research `main` at 53ba795. The re-authoring
live validation is running while this is written; section A.9 is the only table expected to change.

Conventions in this part:
- Methods: "the proposed runtime (Ours)", "PLEXIL", "EUROPA→PLEXIL". Source files that write `europa_plexil`,
  `EUROPA -> PLEXIL` or `europa` mean EUROPA→PLEXIL.
- Every number is followed by its source in brackets. **[derived]** marks a number this part computed from a named raw
  source (worklog timestamps, `queue.log`, `git diff`), not copied from a finding.
- Clocks: the worklogs (`experiments/reauthoring/worklog/*.jsonl`) stamp **UTC**. The run-farm `queue.log` files stamp
  **local time, CST = UTC+8**. Mission time in `check.log` is the simulator clock.
- "Fn" means `docs/research_findings.md` finding n.

---

## A. The re-authoring study

### A.1 Purpose

- In Experiment I (exp1b) every held-out run of PLEXIL and EUROPA→PLEXIL ended "detected -> escalated -> hold". The
  frozen plan or domain had no continuation, and mission control answered "a new procedure is in work"
  [docs/reauthoring/spec.md; F142]. That is 6 of 6 held-out runs per baseline, each with one `new_procedure` request and
  primary failure category 2 "mission-model coverage" (12/12) [F142; artifacts/eval/exp1b/tables.md;
  artifacts/eval/exp1b/failures.md].
- The study prices that new procedure: "the engineering time and the new plan / domain elements a ground engineer needs
  to make the frozen baseline complete one held-out case autonomously" [docs/reauthoring/spec.md].
- Ours needed no re-authoring in 18 of 18 held-out runs (0/18 re-authoring, 0 `new_procedure` requests). Its cost here
  is zero [F142; docs/reauthoring/spec.md].
- Where the study comes from:
  - heldout_design §8 "Re-authoring cost" [docs/heldout_design.md §8].
  - authoring_spec "After the freeze". There it answers "an engineer could have written that branch", and it feeds H2
    [docs/baselines/authoring_spec.md "After the freeze"; F111].
- The retry-budget sensitivity is the companion evidence. Offline, with N = 1/2/3/5 attempts per call on every held-out
  state (48 runs), every run ended "detected -> escalated". So the baselines' held-out failures do not come from too
  small a retry budget [F136; F143; artifacts/eval/retry_budget/results.md].

### A.2 Design

| element | as specified | source |
|---|---|---|
| unit of study | one engineer per (baseline, held-out case): 2 baselines x 4 cases (L2-A, L2-B, L3, L4) = 8 sessions | docs/reauthoring/spec.md; F149 |
| engineer | a fresh Claude session ("opus") per pair, each independent of the others. The branch commits carry `Co-Authored-By: Claude Opus 5.5`, and setup.tex names "Claude Opus 5.5". Not a human engineer | F149; `git log exp1b..reauth/*`; paper/sections/setup.tex §setup-reauthoring |
| starting state | the Experiment I freeze, tag `exp1b`. Branch `reauth/<baseline>-<case>` in `.worktree/reauth-<baseline>-<case>`, built by `experiments/reauthoring/make_worktree.sh` (submodules as worktrees; venv, install, kernels and key linked; ros/ built; SRB pinned by `pin_srb.sh`) | docs/reauthoring/spec.md; experiments/reauthoring/make_worktree.sh |
| what the engineer is given | the case brief `docs/reauthoring/cases/<case>.md`: the diagnosis (cause, the facts that matter, the goal), **not the procedure**. Also given: the frozen baseline and its docs (`docs/baselines/{plexil,europa}.md`), `docs/baselines/authoring_spec.md`, `openral_ext/capability_server/contracts.yaml`, the site survey / equipment catalogue / manifest (`interaction.json`), `experiments/launch/lunar_base_d0/`, and the baseline's own Exp I run(s) of that case under `artifacts/runs/exp1b/<baseline>_<case run>/` | docs/reauthoring/spec.md "What you are given" |
| not to be opened | any Ours record or run (`artifacts/runs/**/ours_*`, `prompts/`, `space_runtime/`), other cases' briefs, other engineers' branches or runs, `experiments/ablation/`, `docs/research_findings.md` | docs/reauthoring/spec.md |
| what may change | PLEXIL: `baselines/plexil/` (plans, library nodes, interface config, offline tests) and, where a new call or result must be carried, `ros/plexil_capability_adapter` ("carries calls and state, no mission logic"). EUROPA→PLEXIL: `baselines/europa/` (NDDL domain, initial state, host, bridge, config) | docs/reauthoring/spec.md |
| lock relaxation | **tier 3 of the baseline lock lifted for that case only**: a branch (PLEXIL) or relation (EUROPA) may key on the case's cause or situation and compose existing capabilities. Tier 1 (3 attempts per call) is unchanged. The covered procedure must keep working ("do not remove or weaken it"). Every encoded fact must trace to the covered specification, the contracts, the survey / catalogue / manifest or the brief | docs/reauthoring/spec.md; docs/baselines/authoring_spec.md (tiers) |
| not the engineer's | skills, the capability boundary, SRB, the evaluator, the operator console, the spec, the validator. A defect there is shared infrastructure: stop the timer, note it, report it | docs/reauthoring/spec.md |
| timer | `evaluation/engineering_worklog.py` start/stop/note. Active time = reading, editing, building, offline checks, and waiting on one's own validation runs. The timer stops for any pause, e.g. waiting for a GPU someone else holds or for the model provider. Every failed validation run and every modelling/logic error is written as a note | docs/reauthoring/spec.md "Timer and record"; evaluation/engineering_worklog.py |
| cap | **3 h active**. At the cap: stop, `note "cap reached"`, commit; the case is reported as "not reached in 3 h" | docs/reauthoring/spec.md |
| validation | live runs of the modified baseline on **every instance of the case** (the baseline's own Exp I job lines). Each run goes through the per-GPU lock shared with the ablation live runs, `experiments/reauthoring/gpu_run.sh <gpu> <session> <jobs> artifacts/runs/reauth/<baseline>_<case>/v<k> <checkout>`, on the engineer's own GPU. A Mission A/B baseline run takes "~15-40 min" | docs/reauthoring/spec.md; experiments/reauthoring/gpu_run.sh |
| pass rule | `experiments/reauthoring/validate.py <run dir>...` prints PASS when every instance succeeded by the external evaluator, nothing was dropped (evaluator class 2), and no module was taken from an energized unit without approval (class 5) | experiments/reauthoring/validate.py; docs/reauthoring/spec.md |
| stop | **the timer stops at the first PASS**. The engineer commits changes and worklog on its branch; never merges, never pushes | docs/reauthoring/spec.md |
| engineer's summary | active time and time waiting on its own runs; files changed (+/-); the semantic constructs added (PLEXIL nodes/branches/lookups/commands; NDDL classes, predicates, actions, compatibilities, host changes); validation runs and outcomes; modelling errors; any shared defect hit | docs/reauthoring/spec.md "Your summary" |
| plan deviation | heldout_design §8 planned the cost as "Not simulated: measured offline as developer time + new plan/domain nodes". authoring_spec "After the freeze" says "(evidence for the paper, no live runs)". The study as run adds live validation on every instance, so its pass criterion is the external evaluator | docs/heldout_design.md §8; docs/baselines/authoring_spec.md; docs/reauthoring/spec.md |

### A.3 The case briefs (what each engineer was told)

| case (scenario id) | what the robot reported in Exp I | diagnosis given | goal | instances to validate (PLEXIL / EUROPA→PLEXIL job names) |
|---|---|---|---|---|
| **L2-A** shutter left drawn (`heldout_radiator_cover`) | the faulted unit was reset, read closed, and tripped again with trip cause **OVERTEMP**; after the retry budget the baseline asked mission control and held | the unit's heat-rejection shutter (a PDU's radiator shutter; the BESS HVAC condenser shutter) was left drawn. With it closed, a closed breaker overheats and trips OVERTEMP "about 30 s after a reset". It opens with a push button, a surveyed press point: `pdu_{1,2,3}_radiator/cover_button`, `bess_hvac/cover_button` (the unit's `cover` in the survey; the ISRU plant has none). Once it is open a reset holds. OVERTEMP is visible in `power_status` (breaker, trip_cause) | mission unchanged: every serviced unit restored (breaker closed and staying closed), arm stowed, rover docked | 2: `plexil_l2a_pdu1`, `plexil_l2a_bess` / `europa_l2a_pdu1`, `europa_l2a_bess` (`env.faulted_unit=pdu_1` / `bess`) |
| **L2-B** delivery stand occupied (`heldout_destination_occupied`) | delivering CNS-0301 from `landing_stand/slot_0` to `habitat_stand/slot_0`, the place failed three times (the set-down pushed against something); asked and held | `habitat_stand/slot_0` already holds the outbound return container RTN-0007 (manifest: outbound return, awaiting stowage; pick point `return_container/pick`). The stand takes one item. The occupier must first go to another free support (`return_stand/slot_0` is where outbound returns go), then the delivery is made. The robot can see the occupier (camera, or the failing place) and read the manifest | CNS-0301 on `habitat_stand/slot_0`; RTN-0007 resting on some other support (not dropped, not held); arm stowed; rover docked | 1: `plexil_l2b_habitat` / `europa_l2b_habitat` (`env.cargo=consumables_container env.destination=habitat`) |
| **L3** module failure (`heldout_module_failure`) | the reset did not restore the unit after 3 attempts; trip cause **BATTERY_MODULE_FAULT** (BESS) / **FILTER_CLOGGED** (ISRU); asked and held | the installed module fails its self-test, so no reset holds until it is replaced. BESS: BAT-0101 in `bess_cradle/tray`, spare BAT-0102 on `depot_spares_stand/slot_0`. ISRU: FLT-0201 in `isru_filter/tray`, spare FLT-0202 on `isru_stand/slot_0`. The tripped unit is de-energized, so removal is within the vehicle's authority. The failed module comes out and goes onto a free support (`return_stand/slot_0`, `isru_return_stand/slot_0`); the spare goes in; then a reset holds. Modules are picked and placed like any catalogued item; bay trays are place points of role `equipment_bay` | the faulted unit restored, arm stowed, rover docked | 2: `plexil_l3_bess`, `plexil_l3_isru` / `europa_l3_bess`, `europa_l3_isru` |
| **L4** no spare, energized donor (`heldout_cannibalize`) | the reset of PDU-1 (habitat life support, crew-critical) did not restore it after 3 attempts; trip cause **ORU_SELFTEST_FAIL**; asked and held | PDU-1's ORU-0211 (`pdu_1_bay/tray`) failed. The only spare, ORU-0417 on `depot_stand/slot_0`, is recorded failed and fails its self-test. Serviceable ORUs remain only in energized units: PDU-3's ORU-0258 (`pdu_3_bay/tray`, non-critical, near) and the ISRU plant's ORU-0285 (`isru_power/tray`, non-critical, far). Removal from an energized unit needs mission control's authorization first (14 CFR 1214.403). The protocol: a request with `kind: "authorization"` and `pending_approvals: [{capability, target, reason}]` is decided by the flight-rule table 300 s after arrival (plus 4.27 s one-way delay each way). It grants a removal from a non-critical unit that restores a crew-critical load (`grants` in the reply) and denies otherwise. A request without a kind is an escalation. Earth sets 925 s of mission time after the start; later requests are only queued. ORU-0211 must leave the bay before the donor goes in | PDU-1 restored, arm stowed, rover docked; no module taken from an energized unit without an approval on record | 1: `plexil_l4_pdu1` / `europa_l4_pdu1` (`env.faulted_unit=pdu_1`) |

All job lines share `D0_CAPABILITY_SERVER=1`, `D0_SCENE=scenes/deploy/srb_lunar_base_mission_{a,b}.yaml` and
`D0_CHECK=d0_{plexil,europa}_mission_{a,b}_check.py` [docs/reauthoring/cases/{l2a,l2b,l3,l4}.md]. There are 12 instance
runs per validation round over the 8 pairs (PLEXIL 6, EUROPA→PLEXIL 6) [derived from the briefs].

### A.4 Sessions and timeline

| event | time | source |
|---|---|---|
| a network drop killed the first round of engineer sessions "a few minutes in (timers started, nothing written)"; their worklogs were deleted and the sessions restarted (preregistration §3: infrastructure is repeated) | 2026-09-29, before 09:39 UTC | F149 |
| the eight sessions start their timers in parallel | 2026-09-29 09:39:35-09:40:17 UTC | worklogs `session_start` [derived] |
| model gateway refuses the account (HTTP 403 "team not allowed to access model"; user: out of credit). Every live run needs it (Ours' reasoner; every method's press/pick locate VLM), so live validation waits | 2026-09-29 | F149 |
| each engineer finishes authoring and its offline checks, then stops the timer "waiting for model provider (shared outage)". PLEXIL: 09:44:47-09:52:58 UTC. EUROPA→PLEXIL: 09:51:26-10:46:21 UTC | 2026-09-29 | worklogs; F151 |
| sessions resume (same agents) for live validation | 2026-09-30 01:13:29-01:13:47 UTC (09:13 CST) | worklogs; AGENT/todo.md |
| GPU assignment seen in the queues: PLEXIL L2-A gpu0, L2-B gpu1, L3 gpu2, L4 gpu3; EUROPA→PLEXIL L2-A gpu4, L2-B gpu5, L4 gpu3 (after PLEXIL L4). todo planned "EUROPA L3 on 1, L4 on 3" | 2026-09-30 | artifacts/runs/reauth/*/v1/queue.log; AGENT/todo.md |
| EUROPA→PLEXIL L3 and L4 stop "waiting for GPU". L4's note: "GPU 3 busy: rf-plexil_l4_pdu1". EUROPA L4 resumes at 02:24:32 UTC; its v1 starts 10:24:20 CST | 2026-09-30 | worklogs; queue.log |

### A.5 Offline results (F151, verbatim)

F151 states: "All eight engineers (docs/reauthoring/spec.md, F149) finished authoring and their own offline checks; none
has run live (gateway refused, F149), each timer stopped 'waiting for model provider'." The table gives active time
(`engineering_worklog.py total`); notes (validation failures + modelling errors + outage/hygiene notes); and the diff of
the baseline's own files (`baselines/`, `ros/`) on `reauth/<b>-<case>` [F151]:

| case | PLEXIL: active, notes, diff | EUROPA→PLEXIL: active, notes, diff |
|---|---|---|
| L2-A shutter | 312 s, 1, 3 files +60/-1 | 685 s, 3, 3 files +70/-16 |
| L2-B occupied stand | 527 s, 4, 7 files +96/-6 | 3977 s, 6, 6 files +67/-16 |
| L3 module failure | 488 s, 4, 5 files +122/-2 | 3786 s, 9, 6 files +178/-34 |
| L4 donor + authorization | 785 s, 4, 6 files +278/-6 | 3524 s, 6, 3 files +300/-58 |

(Only the column header's method name was changed, to "EUROPA→PLEXIL".)

F151's headline reads "PLEXIL covers each held-out case in 5-13 min, EUROPA -> PLEXIL in 11-66 min with 3-9
modelling notes" [F151]. The "3-9" counts every note, outage and hygiene notes included, not only modelling errors
(A.5.2).

**A.5.1 Re-check against the raw worklogs and branches [derived].** Closed-session sums reproduce every active time
(312.2, 526.6, 488.1, 784.6, 685.1, 3976.7, 3786.0, 3523.9 s). `git diff --stat exp1b..reauth/<b>-<case> -- baselines ros`
reproduces every file count and +/- of the table. For EUROPA→PLEXIL L3, a later 14.5 s session ("waiting for GPU",
2026-09-30) brings the closed total to 3800.5 s; for L4, a 43.3 s session brings it to 3567.2 s [derived, worklogs].

**A.5.2 What the notes are** (this part's classification of each worklog note written before live validation) [derived, worklogs]:

| pair | notes (F151) | modelling / logic errors | offline-check or runner errors | outage / ready | search hygiene | other |
|---|---|---|---|---|---|---|
| PLEXIL L2-A | 1 | 0 | 0 | 1 (authoring done; offline_check 59/59 PASS; blocked by HTTP 403) | 0 | -- |
| PLEXIL L2-B | 4 | 1 (adapter `ManifestAt`: a range-for over a temporary json's member dangled, always ""; caught offline by the stand-in boundary probe) | 0 | 2 | 1 (a grep spanned `experiments/` beyond `launch/lunar_base_d0`; "it printed no lines, no held-out material seen") | -- |
| PLEXIL L3 | 4 | 0 ("no modelling error found offline") | 0 | 2 (offline 95/95 PASS first time; outage) | 1 (held-out lines printed, A.8) | 1 design note (set-down support, A.7) |
| PLEXIL L4 | 4 | 0 in the plan | 2 (offline-check iteration 1: plexiltest steps the exec once per script event, a delay step added; iteration 2: the L4 cases' initial state lacked the ItemDescription lookups. Both were errors of the test script "not the plan"; iteration 3: 55/55) | 1 | 0 | 1 (adapter `RequestAuthorization` checked against the real console.py) |
| EUROPA→PLEXIL L2-A | 3 | 1 (`open_shutter` copied press's posture transition Stowed->Ready; the solver put a stow first; fixed: no posture slaves) | 0 | 2 (offline chain done; ready) | 0 | -- |
| EUROPA→PLEXIL L2-B | 6 | 3 (capacity model blows up the default search: 5000 steps unsolved vs 118; failed alternatives; the domain-only derivation is correct but not found: A.7) | 0 | 2 | 1 (A.8) | the frozen planner's horizon defect (A.7) |
| EUROPA→PLEXIL L3 | 9 | 4 notes (horizon-filter escape of `seat`'s `met_by Fail`; guards removing pick's Free effect from the supporter table; pick's slot effect ordered before its support bound; press/nav conditions merging with initial facts) | 1 note: a correction to error 3 that also records the runner error (parallel offline chains on the default docker bridge cross-talked over DDS, ROS domain 92; rerun with `--network none`) | 2 | 1 (A.8) | 1 baseline data gap (no "filter cartridge" row in `baselines/item_descriptions.json`; host KeyError; row added) |
| EUROPA→PLEXIL L4 | 6 | 4 errors in 2 notes (threat decisions before open conditions; press's Stowed precondition trapping the search; action-name ordering of supporters, set-aside renamed `deposit_module`; failed install translated to generic Holding) | 1 note: 7 parallel offline chains cross-talked over DDS, ROS domain 92 ("invalid runs, rerun with --network none"). The same note records that sim_boundary `site_map` lacked unit/role and the host read-back missed bays/failed args (both fixed before any live run) | 2 | 1 (A.8) | -- |

### A.6 What each engineer wrote

F151, verbatim: "PLEXIL: a branch keyed on the case's cause (trip cause OVERTEMP -> shutter button; module fault ->
remove / set down / fetch spare / install; ORU_SELFTEST_FAIL at PDU-1 -> authorization request + donor transfer; a
manifest record on the destination -> clear it to the return stand) composed of the existing library nodes, plus new
Lookups/Commands in the adapter where the case needed a signal (`ManifestAt`, `RequestAuthorization`). [...] EUROPA: new
classes, timelines and actions (shutter, bay contents and access, slots/supports, self-test), host translation of the new
facts, and changes to covered rules the solver needed (press no longer requires the arm stowed; navigation without a
from-pose condition; slot tokens ordered last)." [F151]

Per branch. The constructs are from each engineer's commit message and worklog. Node and declaration counts come from
`git diff exp1b..reauth/<b>-<case>` [derived]:

| branch (head) | files changed (baseline's own) | constructs added | labelled PLEXIL nodes added / NDDL declarations added [derived] | offline checks |
|---|---|---|---|---|
| `reauth/plexil-l2a` (1c6149d authoring; 3dea952 PASS) | `MissionA_Covered.ple` +39, `.plx` +1/-1, `offline_check.py` +20 (3 files +60/-1) | `ShutterOf` (unit -> `<cover>/cover_button` from the survey; ISRU none); `OpenShutter`: if the tripped unit's `trip_cause` reads OVERTEMP, DriveAndDock to the shutter button and press under a 3-attempt Try; `ShutterNotOpened` escalation + hold. The covered procedure is unchanged after it. Existing Lookup `PowerUnit(Unit, "trip_cause")` | 9 nodes (ShutterOf, OpenShutter, Open, ToShutter, PressShutter, Shutter1-3, ShutterNotOpened) | offline_check 59/59 PASS (OVERTEMP at pdu_1 and bess; each shutter call failing 2x/3x) [commit 1c6149d; worklog] |
| `reauth/plexil-l2b` (e078203) | `item_descriptions.json` +5, `MissionB_Covered.ple`/`.plx`, new `lib/StowArm.ple`/`.plx`, `offline_check.py`, `CapabilityAdapter.cc` +17 (7 files +96/-6) | new adapter Lookup `ManifestAt(place, field)`. When the manifest records something at the destination, `ClearDestination` runs first: DriveAndDock, PickItem, DriveAndDock, PlaceItem to `return_stand/slot_0`, then the new library node `StowArm`. The covered delivery then runs unchanged. The occupier's pick description comes from a new "return container" row in the shared item table | 16 nodes (incl. the StowArm library, 5) | offline_check 52/52 (51 existing + destination occupied). Real adapter vs `sim_boundary.py` with RTN-0007 on `habitat_stand/slot_0`: clears then delivers, ok true. Authored scene: covered sequence unchanged [commit; worklog] |
| `reauth/plexil-l3` (478dbb2) | `MissionA_Covered.ple` +61, `.plx`, new `lib/StowArm.ple` +21/`.plx`, `offline_check.py` +39 (5 files +122/-2) | for BATTERY_MODULE_FAULT (BESS) / FILTER_CLOGGED (ISRU): take the failed module out of its bay; set it down on a free support (`bess_stand/slot_0`, `isru_return_stand/slot_0`); fetch the spare (`depot_spares_stand/slot_0`, `isru_stand/slot_0`); install it; then the covered reset and return. New library node StowArm | 18 nodes (incl. StowArm, 5) | plexilc + offline_check 95/95 PASS first time (51 covered unchanged, 2 module-failure nominal, 42 fail-2x/3x at every call site of the path) [commit; worklog] |
| `reauth/plexil-l4` (e9914ad) | `MissionA_Covered.ple` +54, `.plx`, new `lib/ReplaceFromDonor.ple` +106/`.plx`, `offline_check.py` +73, `CapabilityAdapter.cc` +48 (6 files +278/-6) | when PDU-1's reset does not hold and trip cause is ORU_SELFTEST_FAIL, new library node `ReplaceFromDonor` runs. It asks for authorization (kind "authorization", held call `pick` on `pdu_3_bay/tray`) while, in a Concurrence, it takes the failed ORU-0211 out to PDU-1's free spares shelf and drives to PDU-3. Once granted it picks ORU-0258, installs it in PDU-1's bay and resets PDU-1 (3 press+check attempts); then the covered return and final check. Denied or out of attempts: escalate and hold. Adapter: `Command Boolean RequestAuthorization(question, capability, target, reason)` | 42 nodes | 55/55 (51 covered + 4 L4) after 2 test-script iterations. Adapter vs real console.py: `pdu_3_bay/tray` granted -> true, `pdu_2_bay/tray` denied -> false, a request without kind still `new_procedure` [commit; worklog] |
| `reauth/europa-l2a` (66c3a5b) | NDDL +27, `host.py` +37, `sim_boundary.py` +22 (3 files +70/-16) | `Panel.Overheated` (tripped OVERTEMP: a reset alone does not hold); class `Shutter` (unit + surveyed cover_button); action `open_shutter` (docked at the button: Overheated -> Faulted, which press then restores). Host: trip cause read when a trip is seen (OVERTEMP -> Overheated); shutter objects from the survey's `units[u].cover`; `open_shutter` dispatched as the press capability. `sim_boundary --drawn UNIT` | 1 predicate, 1 class, 1 action (+ its compatibility) | offline chain: pdu_1 and bess derive nav/dock cover_button -> open_shutter(press) -> nav/dock panel -> press -> stow -> dock, done. Covered pdu_2 and Mission B ORU->PDU-1 shelf unchanged [commit; worklog] |
| `reauth/europa-l2b` (a699c58) | `host_config.json` +2/-1, NDDL +35, `host.py` +23, `planner/europa_plan.cc` +5, `sim_boundary.py` +12, `item_descriptions.json` +5 (6 files +67/-16) | `Support` (a place point) with a `Slot` timeline. An item's stay on a support and its set-down occupy the slot (`ItemLoc::On` rule, place), so nothing is set down on an occupied support. Host: place points as Support. An outbound return the record lists as awaiting stowage gets the goal "on the return stand" **ahead of the mission's goals (one goal per solve)**. Planner horizon opens at -1. "return container" row. `sim_boundary --outbound` | classes Slot, Support (+ ItemLoc forward declaration); predicates Occupied, On; actions pick, place re-declared | offline chain (docker `--network none`): L2-B done in 4 plans (stow RTN-0007 habitat -> return stand; CNS-0301 landing -> habitat; stow; dock), 15 dispatches. With pick:1 and place:2 failing: replans, done. Covered regressions done: consumables -> habitat and ORU -> PDU-1 shelf (9 dispatches each), Mission A pdu_2 (5) [commit; worklog] |
| `reauth/europa-l3` (580bd5e) | `PlannerConfig.xml` +3, `host_config.json` +2/-2, NDDL +107, `host.py` +61, `sim_boundary.py` +32, `item_descriptions.json` +5 (6 files +178/-34) | place-point occupancy (Slot Free/Holds; Support with return_stand); item kind and serviceability; a unit self-test timeline (Pass / Fail{bay, kind, module}); the unit's own non-dispatched `seat` action. The self-test passes once the failed module stands on a return stand and a serviceable module of the bay's kind is in the bay; press needs Pass. pick binds its support from the item's location first; press needs no prior posture; Nav2 moves have no from-stance condition; Slot threats ordered last. Host: trip cause -> failed module; per-solve self-test facts from installed_modules; slot facts; return stands and module faults in host_config. `sim_boundary --failed-module`. "filter cartridge" row | classes Slot, Support, SelfTest; predicates Free, Holds, Pass, Fail; actions seat, pick, place | offline chain (run-farm image, `--network none`): L3 bess and isru done, "one 16-activity plan (arm_ready; pick failed module from bay; place on isru_return_stand/slot_0; pick spare; place in bay; press) then stow, return". Covered pdu_2, Mission B ORU -> pdu_1 shelf and battery -> bess_stand unchanged (9 calls); covered bess/isru OVERCURRENT still nav/dock/press [commit; worklog] |
| `reauth/europa-l4` (547ebd2) | NDDL +167, `host.py` +128, `sim_boundary.py` +63 (3 files +300/-58) | Item kind/serviceable; `Place` (free); `Bay` (unit, takes, Access Reserved/Cleared, Contents Holds/Empty); `Panel.Blocked`; `Unit.noncritical`; `Jaws.HoldingModule`. Actions `remove_module`, `take_donor_module`, `install_module`, `deposit_module` (pick/place capabilities in those roles) and `request_authorization`. pick/place take a Place; press no longer requires Stowed. Host: new objects and facts from site_map / manifest / power_status; Blocked from the bays' installed modules; the authorization request (kind authorization, the held pick) **"with the granted donor's restore goal dropped"**; a held bay module on failure kept as HoldingModule. sim_boundary: modules move with pick/place, `--failed` / `--record-failed`, authorization answered by `console.decide` | classes Place, Access, Contents, Bay; predicates HoldingModule, Blocked, Reserved, Cleared, Holds, Empty; actions pick, place, remove_module, take_donor_module, install_module, deposit_module, request_authorization | L4 (`--failed ORU-0211 --record-failed ORU-0417`): 17-activity plan in 887 steps / 2.3 s (arm_ready, request_authorization(pdu_3 bay; stand-in GRANTED), remove ORU-0211 from pdu_1 bay, deposit on pdu_1_shelf, take ORU-0258 from pdu_3 bay, install in pdu_1 bay, press -> stow -> dock). With `--fail pick:2 / place:1 / place:2 / navigate:3:far` each replans and completes. Covered regressions unchanged [commit; worklog] |

Size comparison. PLEXIL's baseline-file diffs are +60 to +278 lines in 3-7 files. EUROPA→PLEXIL's are +67 to +300 lines
with -16 to -58 deletions: it rewrites covered rules [F151]. Line counts are not comparable across PLEXIL, NDDL,
Python and C++ (execution_plan §14.4; research_content §5.6 metric 2) [AGENT/execution_plan.md §14.4].

### A.7 Deviations and defects found by the study

| item | what | how it was handled / counted | source |
|---|---|---|---|
| **L2-B host-side goal (EUROPA→PLEXIL)** | the domain-only derivation (capacity + "an outbound return awaiting stowage rests on the return stand") is correct: "the stowage alone solves in 189 steps, the delivery alone in ~175". But EUROPA's default chronological search does not find the interleaved plan (5000 and 60000 steps; also "crashes in EUROPA's token discard when rules relate two slaves"). So the host turns the record's "awaiting stowage" into a goal ahead of the mission's (one goal per solve) | "Deviations kept and counted as cost" | F151; worklog europa_plexil_l2b (error 3); commit a699c58 |
| **EUROPA planner horizon defect (frozen baseline)** | "the horizon opened at 0, so open conditions of an activity that could start at once were skipped (it picked the container where the rover stood)". The worklog words it as: the HorizonFilter (PartiallyContained) never checks conditions of an activity that can start at t=0; plan 2 picked the consumables container at the return stand. Fixed on the branch: horizon opens at -1 (`planner/europa_plan.cc` +5). EUROPA L3 met the same filter class (its error 1: `Unit.seat`'s `met_by Fail` could end at t=0 and "fell outside the horizon filter"; fixed in the domain with `seat leq(1,start)`) | "Exp I's covered runs did not depend on it (7/7); recorded, the frozen baseline unchanged" | F151; worklogs europa_plexil_l2b, europa_plexil_l3 |
| **EUROPA→PLEXIL L4 donor goal** | the host drops "the granted donor's restore goal" (Mission A's formal goal is every unit restored; PDU-3 goes down once its ORU is taken) | not discussed in F151; host-side goal handling like L2-B's | commit 547ebd2 |
| **Covered rules changed (EUROPA→PLEXIL)** | "press no longer requires the arm stowed; navigation without a from-pose condition; slot tokens ordered last" (L3, L4, L2-A posture) | the spec requires the covered procedure to keep working. Each engineer ran covered regressions offline (all unchanged, A.6); no live covered rerun | F151; worklogs; docs/reauthoring/spec.md |
| **L4 hard-coded "only spare recorded failed" (PLEXIL)** | "The L4 plan hard-codes 'the only spare is recorded failed' from the brief: with a serviceable spare it would still take PDU-3's module -- a pre-written branch holds for the situation it was written for" | recorded as a property of re-authoring | F151 |
| **Shared `baselines/item_descriptions.json` edited** | rows added on the engineers' own branches: "return container" (`reauth/plexil-l2b` +5, `reauth/europa-l2b` +5) and "filter cartridge" (`reauth/europa-l3` +5; worklog: "baseline data gap ... host KeyError for the ISRU spare") | branches are never merged (spec), so no conflict. PLEXIL L3 instead wrote the filter's look "from its catalogue preview flt_0201/0202" | F151; `git diff --stat`; worklogs |
| **PLEXIL L3 set-down support differs from the brief** | brief: return stands `return_stand/slot_0`, `isru_return_stand/slot_0`. The engineer found the manifest records RTN-0007 on `return_stand/slot_0` and sets the failed BESS module on the free BESS receiving stand `bess_stand/slot_0` (ISRU: `isru_return_stand/slot_0`) | a design note from the manifest, allowed by the spec | worklog plexil_l3; commit 478dbb2 |
| **sim_boundary / host read-back fixes (EUROPA→PLEXIL L4)** | `sim_boundary` `site_map` lacked unit/role (added); host read-back missed bays/failed args in the post-activity telemetry read | fixed before any live run; inside the baseline's own files | worklog europa_plexil_l4 |
| **Offline DDS cross-talk (EUROPA→PLEXIL L3, L4)** | parallel offline EUROPA chains on the default docker bridge (ROS domain 92) crossed ("Mission B runs saw the Mission A run's PDU-2 press") | invalid offline runs rerun with `--network none`. L4's note warns that another domain-92 chain running "(~10:50-11:00 UTC) could have seen mine too" | worklogs europa_plexil_l3, europa_plexil_l4 |
| **Frozen domain limit** | "the frozen domain + default solver cannot plan two transfers in one solve (tested: 2 chained deliveries time out) until pick's conditions are reordered" | finding of the L3 engineer | worklog europa_plexil_l3 (error 4) |

### A.8 Held-out material seen by accident

The spec forbids other cases' briefs, Ours material, `experiments/ablation/` and `docs/research_findings.md`. After the
first incidents, "the remaining engineers were told to keep searches inside their baseline's files" [F149].

| pair | what was printed or read | recorded where | effect stated |
|---|---|---|---|
| PLEXIL L2-A | F149: repo-wide greps by "two PLEXIL engineers" printed lines of `experiments/launch/lunar_base_d0/chains/l2a_*.json`, `chains/l3_isru.json` and `experiments/scenarios/mission_a/held_out/a_l3_module_failure_isru*.yaml`, "not opened, recorded in their worklogs". F151 attributes this to "PLEXIL L2-A and L3 (F149)" | **disagreement: `plexil_l2a.jsonl` (working tree, branch and 62abbdf versions) has no hygiene note.** Only PLEXIL L3's worklog records its part. The L2-A record may have been in the deleted first-round worklogs or only in the session's report | F149; F151; worklog plexil_l2a |
| PLEXIL L3 | "a repo-wide grep for the filter cartridge's catalogue text printed lines of held-out material (`chains/l3_isru.json`, `experiments/scenarios/mission_a/held_out/a_l3_module_failure_isru*.yaml`); files not opened or used" | worklog plexil_l3 | "stands from the brief + manifest" |
| PLEXIL L2-B | a grep over `*.py` under `evaluation/` and `experiments/` "spanned experiments/ beyond launch/lunar_base_d0" | worklog plexil_l2b | "printed no lines, no held-out material seen" |
| EUROPA→PLEXIL L2-B | one repo-wide grep (`'awaiting stowage\|outbound return'`) printed 3 lines: SRB `lunar_base_mission_b/task.py` comments (occupier: outbound return container at the habitat; status text) and `experiments/scenarios/mission_b/held_out/b_l2_destination_occupied_habitat{,.certificate}.yaml` ("occupier on the habitat stand, must be cleared to some other support") | worklog europa_plexil_l2b | "No content beyond the brief; files not opened" [worklog]; "said nothing beyond the brief" [F151] |
| EUROPA→PLEXIL L3 | a grep printed **2 lines of `docs/research_findings.md`** (a forbidden file; "Mission B offline method, no held-out content"). Read `baselines/scripts/retry_budget_sensitivity.py`'s docstring, "which summarises the offline stand-in states of L2-A/L2-B/L3/L4". Read SRB `lunar_base/site.py` `power_telemetry()` / `inventory_record()` for the telemetry format | worklog europa_plexil_l3 | F151 names the retry-budget docstring and site.py but **not** the research_findings.md lines |
| EUROPA→PLEXIL L4 | `baselines/scripts/retry_budget_sensitivity.py` ("saw only its own L4 line: pdu_1, reset never, ORU_SELFTEST_FAIL, same as the brief"); SRB `srb/tasks/mobile_manipulation/lunar_base/site.py` lines 115-145 (generic `inventory_record`: status 'serviceable'); `artifacts/runs/site_check_13/check.log` POWER line (covered site check: power_status field names) | worklog europa_plexil_l4 | "No other held-out material printed" |
| EUROPA→PLEXIL L2-A, PLEXIL L4 | no hygiene note | worklogs | -- |

setup.tex leaves as an open question whether the manuscript states this exposure [paper/sections/setup.tex comment in
§setup-reauthoring].

### A.9 Live validation: PENDING (running 2026-09-30)

Only PLEXIL L2-A has a final worklog stop at a PASS. The other rows show the state at 10:28 CST. Their "provisional"
cells are the `check.log` RESULT success flag of runs whose queue has finished. **That flag is not the validate.py
verdict; fill each row only from the engineer's worklog stop entry, `validate.py` output and branch diff.**

| baseline | case | instances | validation runs | PASS/FAIL | final active time (s) | of it waiting on own runs | diff, baseline's own files (whole branch) | state at snapshot / source |
|---|---|---|---|---|---|---|---|---|
| PLEXIL | L2-A | 2 (`plexil_l2a_pdu1`, `plexil_l2a_bess`) | 1 (v1) | **PASS on the first live validation**: "both instances success, 1 cover press + 1 reset each, no escalation; no GPU wait (queue started at once)" [worklog plexil_l2a]. Evaluator RESULT success true, parked_and_stowed true; mission time 1161.9 s (pdu1), 1615.9 s (bess) [check.log] | **3247** [commit 3dea952 "Active time 3247 s"; worklog: 312.2 s authoring + 2934.9 s live session] | ~2916 s [derived: v1 queue started 09:13:48 CST = 01:13:48 UTC; timer stopped 02:02:24.5 UTC]. The engineer's own work was therefore ~331 s [derived] | 3 files +60/-1 (5 files +68/-1 incl. `experiments/reauthoring/jobs/plexil_l2a_v1.txt` +2 and the worklog +6) [`git diff --stat exp1b..reauth/plexil-l2a`] | done. Runs `artifacts/runs/reauth/plexil_l2a/v1/`: pdu1 09:13:48-09:34:45, bess 09:34:45-10:03:17 CST [queue.log] |
| PLEXIL | L2-B | 1 (`plexil_l2b_habitat`) | v1 running | PENDING | PENDING (527 offline) | PENDING | PENDING (7 files +96/-6 offline) | v1 started 09:13:53 CST on gpu1, not finished [queue.log] |
| PLEXIL | L3 | 2 (`plexil_l3_bess`, `plexil_l3_isru`) | v1 running | PENDING | PENDING (488 offline) | PENDING | PENDING (5 files +122/-2 offline) | `plexil_l3_bess` started 09:14:07 CST on gpu2, not finished [queue.log] |
| PLEXIL | L4 | 1 (`plexil_l4_pdu1`) | v1 finished | PENDING. Provisional: RESULT success true, parked_and_stowed true, mission time 4126.9 s [check.log] | PENDING (785 offline) | PENDING | PENDING (6 files +278/-6 offline) | v1 09:13:58-10:24:20 CST, CHECK_EXIT 0, queue done [queue.log]; worklog session still open |
| EUROPA→PLEXIL | L2-A | 2 (`europa_l2a_pdu1`, `europa_l2a_bess`) | v1 finished | PENDING. Provisional: both RESULT success true, parked_and_stowed true; mission time 1233.3 s (pdu1), 1738.7 s (bess) [check.log] | PENDING (685 offline) | PENDING | PENDING (3 files +70/-16 offline) | pdu1 09:13:48-09:35:58, bess 09:35:58-10:06:32 CST, both CHECK_EXIT 0, queue done [queue.log]; worklog session still open |
| EUROPA→PLEXIL | L2-B | 1 (`europa_l2b_habitat`) | v1 finished | PENDING. Provisional: RESULT success true, parked_and_stowed true, mission time 4048.0 s [check.log] | PENDING (3977 offline) | PENDING | PENDING (6 files +67/-16 offline) | v1 09:14:18-10:23:21 CST, CHECK_EXIT 0, queue done [queue.log]; "queued on GPU 5 ... started at once, no GPU wait" [worklog] |
| EUROPA→PLEXIL | L3 | 2 (`europa_l3_bess`, `europa_l3_isru`) | none yet | PENDING | PENDING (3786 offline + 14.5 closed) | PENDING | PENDING (6 files +178/-34 offline) | timer stopped "waiting for GPU" at 01:14:01 UTC; no run dir yet [worklog; artifacts/runs/reauth/] |
| EUROPA→PLEXIL | L4 | 1 (`europa_l4_pdu1`) | v1 running | PENDING | PENDING (3524 offline + 43.3 closed) | PENDING | PENDING (3 files +300/-58 offline) | resumed 02:24:32 UTC; v1 started 10:24:20 CST on gpu3 [worklog; queue.log] |

Cap check: EUROPA→PLEXIL L2-B has 3977 s offline, and its v1 queue ran 09:14:18-10:23:21 CST [F151; queue.log]. So its
final active time will be well above an hour. The 3 h cap is 10800 s [docs/reauthoring/spec.md].

What the results section needs once the table is complete (results.tex `\TBD` at `sec:results-reauthoring`): "per
baseline and held-out case: active engineering time, plan nodes or domain elements added, validation runs; the proposed
runtime needed none (0 of 18 held-out runs re-authored)" [paper/sections/results.tex]. The node and declaration counts
of A.6 and the notes of A.5.2 are ready for that. The spec also asks each engineer for "the time waiting on your own
runs", which is the same split as Experiment II's "waiting on own validation run" and "other work" [F146;
paper/tables/exp2_engineering.tex].

---

## B. Validity, deviations and limitations

### B.1 Deviations from the preregistration (docs/preregistration.md, approved 2026-09-24)

| preregistered | as done | status | source |
|---|---|---|---|
| §1 `preplanned_transition_fraction`: "Decided: per instance, from its closed-capability certificate [...]. Reported once per instance x method" | not computed. `rows.py` writes `preplanned_transition_fraction=None`; evaluation/README.md: "Does not fill in `preplanned_transition_fraction` -- still a pending user decision" | **open**. The README contradicts the preregistration, which records the definition as decided. setup.tex: "the re-authoring flag and the re-authoring study stand in for it" | docs/preregistration.md §1; evaluation/README.md; evaluation/rows.py; paper/sections/setup.tex comment |
| §4 "HIR, waiting time, neglect time: medians with bootstrap intervals; interaction level as an ordinal distribution" | `evaluation/tables.py` reported means until F152. F142's HIR 0.136 / 0.591 / 0.470, idle 0.608 / 0.483 and stretch 955 / 218 / 390 s are means. Now medians with percentile bootstrap 95% intervals (10000 resamples, seed 0). Held-out HIR: Ours 0.080 [0.000, 0.240], PLEXIL 0.617 [0.461, 0.696], EUROPA→PLEXIL 0.485 [0.313, 0.613]; idle PLEXIL 0.634, EUROPA→PLEXIL 0.499; stretch 1029 / 179 / 319 s | **fixed**; F152 supersedes the F142 means for the paper | F152; artifacts/eval/exp1b/tables.md |
| §3 "each request's wall-clock send time is reported beside its mission time (from the model_io record) as a robustness figure; no rerun" | F152 reports a reasoning-latency analysis instead: per-call wall latency median 19.9 s (IQR 11.3-38.7); sim runs at 0.237 of real time during calls. With latency counted in full, Ours' covered median mission time 538 -> 825 s and held-out 1132 -> 2071 s (an upper bound); held-out HIR 0.080 -> 0.036. The VLM's calls are not corrected | **reported in a different form**: `reasoning_latency.md` has per-run and per-coverage tables, no per-request wall-clock send time | F152; artifacts/eval/exp1b/reasoning_latency.md |
| §3 / execution_plan §13.1 "A post-freeze fix that changes shared code reruns the affected campaign from the start" | Exp I: after F141 the whole campaign was rerun (exp1b) [F141; F142]. Within exp1b, two runs invalidated by shared defects were fixed and rerun alone [F142]. Exp II: fixes F145/F147 reran only the runs they decided [F145; F147]. User rule 2026-09-29: fixes are "folded into that experiment's results (F141/F142, F145, F147) -- not reported as a separate round" | **deviation, by user decision** | docs/preregistration.md §3; AGENT/execution_plan.md §13.1; AGENT/todo.md Rules |
| §4 "Ours' model variance: every held-out instance three times; revisited once, after the first held-out variance is seen, and then fixed" | three runs per held-out instance (18) in both exp1 and exp1b; no revisit is recorded in F139-F152 | kept at 3 | docs/heldout_design.md §14; F140; F142 |
| §2 failure taxonomy "by one engineer [...] checked by a second reading" | `failures.md` gives one primary category per failed run (exp1b: only the 12 baseline held-out runs, category 2) | as planned; "one engineer" to be stated in limitations | docs/preregistration.md §2; artifacts/eval/exp1b/failures.md |
| heldout_design §14 run plan "§5.7 ablations 4 x one L3 instance x 2 (8)" | replaced by method B: injected accidents, offline counterfactual replay (684 chains, 828 model calls), live only where offline shows a difference (J1 x4, J3 x2) | user decision (F130 blocked; F144/F148 decided) | docs/heldout_design.md §14; F130; F148; F149; F150 |
| heldout_design §8 "intervention response time split into delivery / notice / planning / execution [...] (stacked bars)" | segments are computed per request in `evaluation/interaction.py` (line 72) | no table or figure found in artifacts/eval/exp1b/ or paper/ | docs/heldout_design.md §8; evaluation/interaction.py |

### B.2 Deviations of the build from AGENT/research_content.md (§3-§5)

| research_content | as built | source |
|---|---|---|
| §3.4.2 / §4.3 semantic observation as a design requirement of the method | semantic observation is one query of the **shared** capability set. `observe` (VLM on one frame), `locate_in_view` (engineering) and `held_item` are answered by the shared VLM, which also selects targets inside pick/press for all three methods. The reasoner reads text only | paper/sections/problem.tex comment; openral_ext/capability_server/contracts.yaml; paper/sections/method.tex |
| §3.4.3 / §4.9 onboard / surface-edge / Earth reasoning tiers with reconciliation | **one remote reasoner** (Qwen3.8-Max on the paratera gateway, `configs/space_runtime.yaml`); no onboard or edge tier. Reconstruction after a restart is supported (`facts.py` reasoner_history, `agent.py` resume) but no endpoint change occurred in the experiments; it is tested offline by ablation J3 | configs/space_runtime.yaml; paper/sections/method.tex and problem.tex comments; F148; F150 |
| §4.8 space-operational context: communication, compute, energy, thermal, illumination, health | Ours' context holds the Direct-with-Earth link state (SPICE), mission control's decision time and the units' telemetry (load, criticality, energized, breaker, trip cause, resets, installed modules). The `space_context` query also returns body, gravity (+ range) and a **static** `light_intensity` constant from SRB's Domain. There are **no compute, energy, thermal or time-varying illumination facts**. method.tex's comment omits gravity and the static light constant | paper/sections/method.tex comment; openral_ext/capability_server/node.py `space_context()`; space_robotics_bench/srb/interfaces/interface/ros.py (space_context publisher); contracts.yaml `power_status`, `space_context` |
| §3.4.4 / §4.7 thin guard with hard resource/health limits, FDIR prohibitions, staleness, authority | `invariants: []`; `fdir_prohibits: {estop: [all_effects]}`; one `target_authority` rule, `energized_equipment_removal` (pick; target role `equipment_bay`; when the unit is energized -> `approval_required`; 14 CFR 1214.403). Every capability contract has `authority_class: routine` (20 of 20). No event made a capability unavailable | configs/space_runtime.yaml; contracts.yaml [derived count]; paper/sections/method.tex comment |
| §4.10 verifier evidence sources include "deterministic simulator truth" | the verifier **never reads simulator truth**, the skill's success flag, the agent's claims or the call order. Truth is the external evaluator's only | space_runtime/verification.py docstring; configs/space_runtime.yaml verification comment |
| §5.7 ablations on natural runs of a subset of Exp I cases | injected accidents J1-J4 plus natural probes N/NF, offline stage 2, live stage 3 only where offline shows a difference. F130: natural runs "would most likely give null results" | F130; F148; paper/sections/setup.tex comment |
| §5.8 real LunarBot demonstration | **dropped by the user 2026-09-30**; "stated as future work in the paper" | AGENT/todo.md; commit 53ba795 |
| §5.6 / execution_plan §13.4 engineers: counterbalanced multiple developers preferred, else one developer as a case study | Exp II: one fresh Claude session per method, order Ours -> PLEXIL -> EUROPA→PLEXIL, each from the previous merged state. The baselines reuse Ours' contract and PLEXIL's Lookups ("the conservative direction"); "a Claude engineer compresses coding time and the paper must say so"; a human-engineer round ("plan B") not now. Re-authoring: 8 parallel Claude sessions from exp1b | F144; F146; AGENT/handoff.md; paper/sections/setup.tex |
| §5.5 metric 3 human planning / preplanning burden | `preplanned_transition_fraction` not computed (B.1) | evaluation/README.md |
| §3.4: five requirements | problem.tex states six (R1-R6): FDIR and trace are split out, semantic observation and distributed intelligence are dropped as requirements | paper/sections/problem.tex comment |
| §1.4 / §2.5 coding-agent harness motivation | method.tex derives the design from space-operations disciplines and makes no coding-agent analogy (user framing: trustworthy AI) | paper/sections/method.tex comment; F148 |

### B.3 Threats to validity

| threat | facts | mitigation / how stated | source |
|---|---|---|---|
| small n | 51 scored runs. Held-out runs per level: Ours 6/3/6/3, each baseline 2/1/2/1. Ours held-out 18/18, Wilson [0.82, 1.00]; baselines 0/6, [0, 0.39]. Each level is instantiated on one or two units | descriptive, with Wilson and bootstrap intervals; no significance test chosen after the data | artifacts/eval/exp1b/tables.md; paper/sections/results.tex; docs/heldout_design.md §14; docs/preregistration.md §4 |
| one simulated site | one base on a LOLA DEM near the south pole; Isaac Sim 5.1 + SRB; rigid assets; push-button actuators; carried modules are 1 kg look-alikes ("real ISS battery ORUs are far heavier"); flat 0 deg horizon and instantaneous set of Earth's centre are idealizations | stated as honesty notes | docs/heldout_design.md §1, §9; F116; paper/sections/setup.tex |
| held-out instances designed by the authors | each case has a documented precedent. L2-B's precedent is category-level ("the unexpected occupancy is our extrapolation"). L2-A: "Closing covers for landing ejecta is our extrapolation from Metzger". "Double-blind baseline authoring is not possible with one engineer -- state it" | precedent table; levels defined by what the frozen baseline lacks (§1 rule 5) | docs/heldout_design.md §1, §2, §9, §13 |
| Ours developed on the held-out instances | step 10 ran Ours on the six held-out instances as development runs (never scored): 14 Ours held-out development runs, 6 of 6 solved in development. Failures were answered only with generic changes under three tests (names no situation/place/serial; holds for every task; traceable), checked by the freeze audit. The reasoner was chosen among four candidates on those runs and offline replays. The user rejected a dev/test split by device | freeze audit (every hunk traces to a finding; no held-out word in model-facing text); development runs not scored | F117; F118; F119-F123; F132; F137; F138; F139; AGENT/todo.md Rules; execution_plan §13.1 "Held-out situations before the freeze". The dev/test decision is recorded in the session memory, not in a repository document |
| simulator clock vs wall clock | mission time is the simulator clock; the sim ran at 0.237 of real time during reasoning calls, so mission time charges deliberation at about a quarter. Covered median mission time 538 -> 825 s with latency in full, held-out 1132 -> 2071 s; HIR 0.080 -> 0.036. The shared VLM's calls run on the same compressed clock for every method (not corrected). Run-farm speed ~0.2 sim/wall with six at once | disclosed in results and setup | F152; artifacts/eval/exp1b/reasoning_latency.md; AGENT/handoff.md |
| CPU PhysX | physics stays CPU PhysX (GPU PhysX crashes in SRB, F54 §5; user decision); physics ~30 of 102 ms per tick | stated | F111 §3; AGENT/handoff.md |
| mission control's 300 s decision time | a design value ("value is ours"), fixed before the campaign, no sensitivity runs; HIR scales linearly with it | stated | docs/heldout_design.md §8; paper/sections/setup.tex |
| engineers are Claude sessions | Exp II and re-authoring engineers are Claude Opus 5.5 sessions, not humans; Exp II order Ours -> PLEXIL -> EUROPA→PLEXIL; "compresses coding time". Exp II engineers' own work: 4.7 / 10.8 / 20.8 min of 54.5 / 46.3 / 53.4 min active | case-study evidence, not a human-factors claim | F144; F146; AGENT/handoff.md; research_content §5.6 |
| accidental exposure of held-out material (re-authoring) | A.8 | recorded in worklogs; remaining engineers restricted | F149; F151 |
| ablation stage 2 | "stage 2 asks one step after the accident, on the full method's recorded prefix" | stated | F148 |
| failure taxonomy | one engineer assigns categories | stated in limitations | docs/preregistration.md §2 |
| trace completeness | the checker covers Ours (451/451) and PLEXIL (81/81 joined by node id), not EUROPA→PLEXIL | stated | F142 |
| model stochasticity | decoding is the gateway's default (no request sets a sampling parameter); Ours three runs per held-out instance; night gateway latency 170-330 s per step at night (F118), "the night gateway did not change an outcome" (F140) | stated | F137; F118; F140 |
| baseline strength | baselines built to a lock decided before further runs (not strengthened or weakened after a failure). The EUROPA host solves one goal at a time ("makes EUROPA greedier, i.e. weaker"). The re-authoring study found a horizon defect in the frozen EUROPA planner that Exp I's covered runs did not depend on (7/7) | lock + change control; defect recorded, frozen baseline unchanged | F111; docs/baselines/authoring_spec.md; paper/sections/setup.tex; F151 |
| Ours is slower and less systematic | covered median mission time 538 s vs 264 / 265 s; in Exp II H1 Ours needed 12-17 scans vs PLEXIL 6, EUROPA→PLEXIL 3; 74 and 78 of 80 steps before F147 | reported | F142; F146; paper/sections/results.tex |

**Known limits recorded in AGENT/todo.md "Known limits":**
- Localization ~5 cm at bess_stand (map precision); 0.3-1.3 m transients round the habitat row's east end (F141). The
  scan's likelihood peak there is 5-6 cm from the truth with 5 cm map cells [F141].
- A carried item swings ±7 cm while lowered (period ~2.9 s); the touchdown phase decides the set-down point (F141).
- The scan's plates are read only from a view the arm can take at a docked stand. The battery module's plates never
  read (domed lid); the scan then reports that something stands there (F147).

Other recorded, not fixed:
- A place that must turn still leaves an item the next pick cannot fit (pick fits the declared yaw only) [F142; F138].
- Dock "no progress" at 6 mm / 1.7 deg (two runs); AMCL bias 5-13 cm vs truth; the arm pushing the rover during a
  stalled place (14 deg) [F138].
- Ours' own action client has the same goal-response exposure as the fixed PLEXIL adapter; it was never hit (0 in 50
  Ours runs) [F142].

### B.4 Infrastructure incidents and how they were handled

Rule: category 8 (simulator crash, DDS, farm, model-provider outage) is fixed, repeated from the start and never scored
[docs/preregistration.md §2-§3].

| incident | when / where | handling | source |
|---|---|---|---|
| executive never received its first command's result (2 of 27 baseline runs: `plexil_b_oru_pdu3`, `europa_l3_isru`) | exp1 (freeze-1) | category 8, rerun, not scored. Found by a stale-log check (capability log unchanged 30 min) | F140 |
| same class in exp1b `plexil_l2b_habitat`. Root cause: the **goal response** was dropped ("failed to send response (timeout)"); F141's result-request diagnosis was wrong | exp1b | adapter fix b15d286 (raw `send_goal`/`get_result` services, own goal id, result poll every 10 s); run invalidated and rerun | F142; artifacts/eval/exp1b/failures.md |
| run-farm container network: the host proxy listens on its own 127.0.0.1 with fake-IP DNS; no route to the API | 2026-09-23 | public DNS in the container (commit af9a879). Offline-script containers use `--dns 223.5.5.5 --dns 119.29.29.29` ("without it the gateway times out") | F111 §3; AGENT/handoff.md |
| **SRB pinning**: an exp1b checkout simulated the main checkout's SRB (absolute paths in openral deploy configs; `srb` imported from Isaac's installed package). Main's SRB has Exp II's extra ORU (`lb_oru_returned`), so every restore died with a KeyError; six J1/J3 runs hung after INITIAL | 2026-09-29 | stopped, no data kept. `experiments/reauthoring/pin_srb.sh <checkout>` points configs and PYTHONPATH at the checkout's SRB; applied to `.worktree/ablation` and every re-authoring checkout (in `make_worktree.sh`); relaunched runs restored | F149 |
| **model gateway refused the account** (HTTP 403 "team not allowed to access model"; out of credit) for Qwen3.8-Max and DeepSeek-V4.1-Flash. The relaunched ablation runs' reasoner failed every step to the budget | 2026-09-29 | category 8; all stopped; ablation stage 3 and all re-authoring validation waited; engineers' timers stopped "waiting for model provider (shared outage)"; resumed 2026-09-30 01:13 UTC | F149; F151; worklogs |
| network drop killed the first round of re-authoring sessions a few minutes in | 2026-09-29 | worklogs deleted, sessions restarted from the start (preregistration §3) | F149 |
| night-time gateway latency: 3-5 min per step; 25 reasoner calls timed out (180 s) in one development run | 2026-09-25 (step 10, development) | development runs, not scored; reasoner timeout 600 s in the frozen config | F118; configs/space_runtime.yaml |
| DDS cross-talk between parallel offline EUROPA chains on the default docker bridge (ROS domain 92) | 2026-09-29 (re-authoring offline checks) | invalid offline runs rerun with `--network none` | worklogs europa_plexil_l3, europa_plexil_l4 |
| EUROPA offline chain host hung before its first query (14th sequential chain) | F136 | `docker run --init` (24/24 ran through); one EUROPA L2-B N=5 chain died at its first dispatch and was rerun alone | F136; F139 |
| duplicate run booted after a finished run dir was moved while its farm worker was alive | Exp II (F147) | stopped after ~1 min, deleted (no data); rule: move a run only after "queue done" | F147 |
| ECONNRESET | -- | **no record found** in docs/research_findings.md, AGENT/, the worklogs, git log or the reauth/ablation run logs | -- |

### B.5 User decisions that shape the paper

| decision | date / source |
|---|---|
| Framing: trustworthy AI. "the harness is what makes the model's autonomy safe; an FM embedded in the space-robot workflow that keeps the established engineering disciplines. Not 'an LLM calling tools'" | 2026-09-29 [F148; AGENT/handoff.md] |
| Fixes found during a campaign: applied for all methods, recorded in findings, folded into that experiment's results, "not reported as a separate round"; only the runs they decided are rerun, from a snapshot where possible; never rerun what already passed | 2026-09-29 [AGENT/todo.md Rules; F142; F145; F147] |
| No freeze ceremony (no `freeze_audit`/`freeze_tag` rerun after fixes) | [AGENT/todo.md Rules; AGENT/handoff.md; F142 "no freeze ceremony (user)"] |
| Baselines locked: "not strengthened, not patched beyond the lock's change control" | 2026-09-23 lock [AGENT/todo.md Rules; F111; docs/baselines/authoring_spec.md] |
| Truth only for evaluation: "Contacts from truth + layout; never decide or navigate on truth"; "Simulator truth is for evaluation / post-hoc diagnosis only, never a decision" | [AGENT/todo.md Rules; AGENT/handoff.md] |
| Ours: generic changes only, three tests (names no situation/place/serial; holds for every task; traceable), recorded in findings | [AGENT/todo.md Rules] |
| Dev/test split by device rejected; held-out development relies on generic changes + freeze audit | user (session memory; not in a repository document) |
| Hardware LunarBot demonstration (research_content §5.8) dropped; future work | 2026-09-30 [AGENT/todo.md; commit 53ba795] |
| Physics stays CPU PhysX | [F111; AGENT/handoff.md] |
| Reasoner Qwen3.8-Max; VLMs stay DeepSeek-V4.1-Flash; models on the paratera gateway | 2026-09-25 [F123]; 2026-09-23 [F111] |
| Earth-set at 925 s of mission time (three request-answer cycles), before any L4 run | 2026-09-24 [F116] |
| Requests carry a kind; only `new_procedure` counts as re-authoring | 2026-09-26 [F125] |
| Fix every shared-layer defect after exp1, then rerun Experiment I (exp1b) | 2026-09-27 [F141] |
| PLEXIL retry budget measured on derived plans; a drop is a fall (class 2 redefinition) | 2026-09-28 [F143] |
| Exp II before the ablations; ablation method B; extension engineer = Claude, order Ours -> PLEXIL -> EUROPA→PLEXIL; human-engineer round "plan B" not now | 2026-09-28 [F144; F146; AGENT/todo.md] |
| Exp II shared scan-view fix; both F147 fixes, only the decided run rerun | 2026-09-28 [F145]; 2026-09-29 [F147] |
| Ablation recommendations accepted, including J3 live as an exception (2 runs); the re-authoring study now | 2026-09-29 [F149] |
| Preregistration approved; campaign instance set (13 instances) | 2026-09-24 [docs/preregistration.md; docs/heldout_design.md §14] |
| Mission control decision time 300 s, no sensitivity runs; no live operator in scored runs | 2026-09-23 [docs/heldout_design.md §8] |
| Clean-up deferred: keep `artifacts/runs/step10_final`, `.worktree/prefreeze`, branch `feat/prefreeze-infra`; pushes wait for the user | 2026-09-26 [AGENT/todo.md] |

---

## C. Artifact and manuscript index

### C.1 Paper-ready figures and tables (`paper/`)

| path | what it shows | generated by / from |
|---|---|---|
| `paper/figures/success_by_level.{pdf,png}` | autonomous mission success of the three methods at each novelty level of Exp I (L0-L4), Wilson 95% intervals; one journal column (3.5 x 2.5 in); markers + direct labels; colours `#2a78d6` Ours, `#eb6834` PLEXIL, `#1baf7a` EUROPA→PLEXIL. Caption in results.tex: runs per level Ours 2, 5, 6, 3, 6, 3; each baseline 2, 5, 2, 1, 2, 1 | `python3 paper/figures/success_by_level.py` from `artifacts/eval/exp1b/rows` [F149; the script] |
| `paper/tables/exp1_independence.tex` | human independence (ALFUS) per method x coverage: success, HIR, requests A/N/I, highest level (runs), re-authoring, idle, stretch; medians [bootstrap 95%]. Held-out: Ours 18/18, HIR 0.080 [0.000, 0.240], requests 3/0/7, none 15 + tactical goal 3, re-authoring 0, idle 0.026 [0.000, 0.162], stretch 1029 [770, 1096]; PLEXIL 0/6, 0.617 [0.461, 0.696], 0/6/0, mission task 6, 6, 0.634 [0.475, 0.716], 179 [122, 353]; EUROPA→PLEXIL 0/6, 0.485 [0.313, 0.613], 0/6/0, mission task 6, 6, 0.499 [0.320, 0.630], 319 [182, 668] | `python3 paper/tables/make_tables.py` from `artifacts/eval/exp1b/tables.md` |
| `paper/tables/exp1_violations.tex` | evaluator violation classes per method x coverage. Unintended contact Ours covered 1, held-out 6; collateral change PLEXIL held-out 1, EUROPA→PLEXIL held-out 2; every other cell 0 | same |
| `paper/tables/exp2_engineering.tex` | Exp II: active 54.5 / 46.3 / 53.4 min; waiting on validation 49.8 / 35.4 / 32.5; other work 4.7 / 10.8 / 20.8; 1 validation run each; mission artifacts +49/-3, +89/-5, +144/-27; supporting files +0/-0, +122/-3, +53/-0; held-out before 0/2 each; after 6/6, 2/2, 2/2 (Ours, PLEXIL, EUROPA→PLEXIL) | `make_tables.py` from `artifacts/eval/exp2/tables.md` |
| (none yet) | re-authoring table, ablation table, architecture figure, site figure | -- |

### C.2 Figures and videos in `artifacts/figures/`

| path | what it shows | status | source |
|---|---|---|---|
| `artifacts/figures/exp1b/swimlane/{ours_l4_pdu1_r1, plexil_l4_pdu1, europa_l4_pdu1, ours_l2b_habitat_r1, plexil_l2b_habitat, europa_l2b_habitat}.{pdf,png}` | one swimlane per run, x = mission time; lanes deliberation / navigation / manipulation / observation queries / operator exchanges / guard holds; the Earth window shaded from the run's own profile. Labels merge neighbours of the same kind and move colliding ones below the bar (fix F149) | **campaign (exp1b), paper-usable**; re-rendered after the label fix and looked at | F135; F142; F149 |
| `artifacts/figures/exp1b/video/{same six}.mp4` (+ `.track.json`; baselines also `.timeline.json`; `replay/`) | textured third-person follow video posed from the run's bag (no physics step), mission card left, mini-map bottom-right, front + wrist insets. 1600x900, 6 fps. Durations: ours_l4_pdu1_r1 198.7 s, ours_l2b_habitat_r1 266.5 s, plexil_l4_pdu1 79.2 s, plexil_l2b_habitat 125.8 s, europa_l4_pdu1 79.0 s, europa_l2b_habitat 144.2 s | campaign (exp1b); supplementary video material | F141 item 6; F142; ffprobe [derived] |
| `artifacts/figures/exp1/swimlane/*`, `artifacts/figures/exp1/video/*` (same six runs) | as above, for the freeze-1 campaign (exp1) | **superseded by exp1b** | F140; F141 |
| `artifacts/figures/swimlane/{ours_qwen_l4_pdu1, plexil_a_bess, europa_a_bess}.{pdf,png}` | first swimlanes: Ours L4 (Qwen3.8-Max development run) and baselines covered A-BESS (step 9) | development runs, not campaign. Caveat: the step-9 runs used the pre-F116 profile (Earth-set 2700 s) | F135 |
| `artifacts/figures/video/ours_qwen_l4_pdu1.mp4` | first mission video (1113 frames at 6 fps, 186 s for 1157 s of mission time) | development run (step10_models) | F135 |

### C.3 Evaluation outputs in `artifacts/eval/`

| path | content | source |
|---|---|---|
| `artifacts/eval/exp1b/tables.md` | **Exp I as reported**: success per method x level with Wilson CI; per-instance k/n; violations; interaction (medians + bootstrap, per F152); physical failures per capability; every failed call (run, capability, mission time, stage, reason) | F142; F152 |
| `artifacts/eval/exp1b/failures.md` | failed runs, one primary category (preregistration §2), and the two invalidated-and-rerun runs | F142 |
| `artifacts/eval/exp1b/place_offsets.md` | every place's set-down / end offsets, drag, inside-footprint | F141; F142 |
| `artifacts/eval/exp1b/reasoning_latency.md` | per-run and per-coverage reasoning calls, wall vs mission time, mission time with latency in full, HIR recorded vs latency in full | F152 |
| `artifacts/eval/exp1b/trace_completeness.txt` | Ours 451/451, PLEXIL 81/81 joined | F142 |
| `artifacts/eval/exp1b/rows/` | evaluator rows (input to tables and the figure) | F142 |
| `artifacts/eval/exp1/{tables.md, failures.md, trace_completeness.txt, rows/}` | freeze-1 campaign, **superseded** (Ours 17/18 held-out; PLEXIL covered 6/7) | F140 |
| `artifacts/eval/exp2/tables.md` | Exp II: §1 engineering, §2 held-out extension cases, §3 every run | F146; F147 |
| `artifacts/eval/exp2/delta_{ours,plexil,europa_plexil}.md` | per-method artifact delta (e.g. Ours "+49 -3 lines across 7 artifact file(s)") | F146 |
| `artifacts/eval/retry_budget/{results.md, rows.jsonl, runs/, f143.log, freeze1.log}` | offline retry-budget sensitivity, both baselines x six held-out instances x N = 1/2/3/5 (48 runs): all "detected -> escalated" | F136; F139; F143 |
| `artifacts/eval/ablation/stage1.md` | stage 1 (the variants on the exp1b runs as they happened, no model) | F148 |
| `artifacts/eval/ablation/score/{stage2.md, sheet.md, notes.md, reading_rubric.md, labels.json, rows.jsonl}` | stage 2 scores (by rule + blind reader), the reader's sheet, 25 borderline notes, rubric | F149; F150 |
| `artifacts/eval/ablation/{points/, results/, live/, live_j3/, smoke_*}` | decision points, 684 chains' model results, live job files for J1 x4 and J3 x2 | F148; F149 |
| `artifacts/eval/freeze_audit/2026-09-26.md` | freeze audit (34 hunks in 9 files; held-out word search; baseline changes since the lock) | F137; F139 |
| `artifacts/eval/step9_10/`, `artifacts/eval/step10_qwen/rows/` | development runs (step 9 covered, step 10 held-out), R2 recompute | F132 (development, not findings) |
| `artifacts/freeze/freeze-1.yaml`, `freeze-1.dry_run.yaml` | freeze record: three repos' HEADs, run-farm image, venv packages, model configs | F137; F139 |
| `artifacts/reasoner_replay/{l2b_occupied, l4_transfer, model_regression, authority_wording, f124}` | offline model replays used to choose the reasoner | F119-F124; F131 |
| `experiments/reauthoring/worklog/*.jsonl`, `artifacts/runs/reauth/<b>_<case>/v<k>/` | re-authoring timers/notes and validation runs (live, in progress) | F149; F151 |

### C.4 Existing manuscript drafts (`paper/sections/`)

No `main.tex` and no `.bib` exist in `paper/`. Each section file defines `\providecommand{\TBD}` [find paper; the files].

| file | content | labels defined | `\TBD` / placeholders left | refs to labels defined elsewhere |
|---|---|---|---|---|
| `problem.tex` (§ "Problem setting and requirements") | the lunar-base setting and a representative Mission A brief; the delay (3-14 s) and Earth-visibility constraints; the comparison fixes everything but the mission-level system; covered vs held-out (five conditions); H1-H3; six requirements R1-R6 (no solution in the runtime; authoritative record; independent verification; authority/invariants outside the model; onboard FDIR + escalation over a delayed link; reconstructable trace). Comments record the disagreement with research_content §3.4 | `sec:requirements`, `req:no-solution`, `req:facts`, `req:verification`, `req:authority`, `req:fdir`, `req:trace` | none; needs `\usepackage{enumitem}` | `sec:method`, `sec:setup-missions` |
| `method.tex` (§ "The proposed runtime") | the step loop as maps: record E_t, reducer φ, renderer ρ, model proposal a_t from closed tool set A, guard g ∈ {allow, deny, approval required, unavailable}, boundary evidence y_t, verifier v. What each map guarantees (R2-R6); the closed whole-operation palette; guard target rule (14 CFR 1214.403); three-valued verification; typed anomalies and four request kinds; record = trace; the prediction that removing a mechanism matters only where nothing else observes the consequence. Comments list the build-vs-research_content disagreements (B.2) | `sec:method`, `fig:architecture` | `fig:architecture` is an `\fbox` placeholder with a `\TBD` caption | `sec:requirements`, `sec:setup-ablation` |
| `setup.tex` (§ "Experimental setup") | subsections: site and robot (89.455°S 213.64°E; Isaac Sim 5.1 + SRB; five units; LunarBot RM-75/EG2/Mid-360/RGB-D; ROS 2 Humble, AMCL, Nav2, MoveIt, OpenRAL skills; DwE link, Earth-set 925 s, 13.4 d, 4.27 s; sim 0.237 of real time during reasoning); missions and the novelty ladder (Table `tab:instances`, 13 instances with precedents); compared methods (Qwen3.8-Max, thinking, 600 s; DeepSeek-V4.1-Flash, 300 s; 80-step budget; 27 tools; one guard target rule + e-stop; PLEXIL 6.1.3; EUROPA→PLEXIL integration and patch; the lock; retry-budget sensitivity 48 runs); mission control (kinds, flight-rule table, 300 s, queued = re-authoring, ALFUS levels); Exp I (51 scored runs); Exp II (scan_label, Claude Opus 5.5 engineers, order, G3, H1/H2 and precedents, fixes); re-authoring (C.4 below); ablations (variants, accidents J1-J4, N/NF, stages); metrics and statistics | `sec:setup`, `sec:setup-site`, `fig:site`, `sec:setup-missions`, `tab:instances`, `sec:setup-baselines`, `sec:setup-operator`, `sec:setup-exp1`, `sec:setup-exp2`, `sec:setup-reauthoring`, `sec:setup-ablation`, `sec:setup-metrics` | `fig:site` `\fbox` placeholder with a `\TBD` caption. Open questions in comments: "level of detail on the model choice"; "whether to report exp1 in an appendix"; whether to state the re-authoring engineers' accidental exposure. The ablation live runs are "pending the model gateway" (comment) | `sec:requirements`, `sec:method`, `sec:results-alfus` |
| `results.tex` (§ "Results") | Exp I (7/7 covered each; Ours 18/18 held-out [0.82, 1.00], baselines 0/6 [0, 0.39]; retry budget; L3 as the sharpest case; median steps 50 vs 23); human independence (Table `tab:independence`; idle 0.634 / 0.499 / 0.026; HIR 0.080 / 0.617 / 0.485; stretch 1029 / 179 / 319 s; 9 of 18 no request; 538 vs 264 / 265 s; latency 19.9 s, 0.237, 538 -> 825 s); trustworthiness (0 false completions in 51; 3 guard holds; Table `tab:violations`; 7 contacts; trace 451/451, 81/81); Exp II (Table `tab:extension`; 12-17 scans vs 6 and 3) | `sec:results`, `sec:results-exp1`, `fig:success-level`, `sec:results-alfus`, `tab:independence`, `sec:results-trust`, `tab:violations`, `sec:results-exp2`, `tab:extension`, `sec:results-reauthoring`, `sec:results-ablation` | `\TBD` at `sec:results-reauthoring` ("per baseline and held-out case: active engineering time, plan nodes or domain elements added, validation runs; the proposed runtime needed none (0 of 18 held-out runs re-authored)"); `\TBD` at `sec:results-ablation` ("offline counterfactual decisions per accident and variant (F148 rubric) and the live consequences") | `sec:setup-baselines`, `sec:setup-operator`, `sec:requirements`; **`sec:limitations` is referenced but defined nowhere** (dangling) |
| `CITATIONS_TODO.md` | the 36 citation keys used in problem/method/setup with the full reference and a status; figures needed (`fig:architecture`, `fig:site`); preamble requirements (`enumitem`, `amsmath`, `xcolor`, `booktabs`) | -- | -- | -- |

Sections not yet drafted: abstract, introduction, related work, discussion, limitations (`sec:limitations`),
conclusion [ls paper/sections].

setup.tex's re-authoring paragraph (`sec:setup-reauthoring`) already states the design as run. It covers eight pairs
with a fresh Claude Opus 5.5 session each, the diagnosis without the procedure, and tier three lifted for that case
only. It also covers the retained retry budget and covered procedure, no access to Ours' records, the 3 h cap with the
timer stopping at the first pass, and live validation on every instance (evaluator success, nothing dropped, no
unapproved removal). It closes with Ours' zero cost [paper/sections/setup.tex].

**Citation keys needing verification** (status "verify" in CITATIONS_TODO.md; "do not fill a verify entry from
memory"), 24 of 36:

barker2021lola (authors, article number); bedraxweiss2004europa (venue); berger2021rfid (document type); castano2022ops
(full author list, pages); cfr1214403 (section title, exact wording); dextre2011rpcm (NASA or CSA primary source);
gaier2005apollo (whether the battery over-temperature account is in the TM); gao1988cannibalization (title);
landon2025delay (table number for the 3 s low end); lewis2022uncrewed (ASCEND paper number); lim2024viper (authors,
title); nasa1971apollo15 (report number); nasa2015issdsr, nasa2019issdsr0402, nasa2019issdsr0617 (URLs); nasa2019mbsu3
(URL, title); nasa2020std6002 (revision date); nasa2023lcn (document number, exact wording); nasa2024hpsc (which
document); ogs2011filters (title, authors, venue); openral (citation form, version); orsula2024srb (authors, year,
paper/arXiv); rabideau2025cadre (author list, pages); themis2007pfr196 (date; "the key's year is a guess").
[paper/sections/CITATIONS_TODO.md]

"Sure" (12): acton1996spice, cerf2007dtn, coleman2014moveit, ecss2008operability (clause numbers from
authoring_spec), estlin2006plexil, huang2007alfus, macenski2020nav2, macenski2022ros2, olsen2003metrics,
park2021de440, riek2012woz, wilson1927probable [paper/sections/CITATIONS_TODO.md]. results.tex cites nothing yet.

### C.5 Git tags and branches that pin each experiment's system

| ref | research repo | openral | SRB | pins | source |
|---|---|---|---|---|---|
| tag `freeze-1` | 87ebd5e (2026-09-26 18:44 +0800, "freeze: step 11 -- PLEXIL adapter rebuilt, audit clean, Experiment I jobs (51 runs)") | 971f2ea | 2b5e2a3 | the first Exp I campaign (exp1, F140), superseded by exp1b; history | F139; `git tag`; `git -C openral/SRB log` |
| tag `exp1b` | 0a32313 (2026-09-28 13:00 +0800, handoff/todo after F143) | 9338521 | 601588f | **Experiment I as reported** (F142); the base of the ablations (`feat/ablation`) and of every `reauth/*` branch. The exp1b runs' own manifests record research 2397390 (21 runs), f58c630 (19), b15d286 (9), dfc4ddd (2), openral ad6fa25 (49) / 9338521 (2), SRB 601588f (51) [derived, `artifacts/runs/exp1b/*/run_manifest.yaml`]. Between f58c630 and the tag, method-relevant files change only in the PLEXIL adapter fix (b15d286); the openral place fix (9338521) is the 2 reruns' revision; evaluator and retry-budget scripts also change [derived, `git diff --stat f58c630 exp1b`] | F142; F144 ("tagged exp1b in all three repos") |
| tag `exp2-base` | c4ef808 (2026-09-28 14:41) | 9338521 | 3b16c05 | Exp II shared supply (scan_label unregistered, second ORU, Mission B knobs, G3) | F144 |
| tag `exp2-ours` | 9003d09 (2026-09-28 15:41) | -- | -- | Ours' Exp II extension | F146; handoff |
| tag `exp2-base-plexil` | 64e2ed6 (merge of exp2/ours, 15:42) | -- | -- | PLEXIL's extension base | handoff |
| tag `exp2-plexil` | d3a59a4 (16:37) | -- | -- | PLEXIL's extension | F146 |
| tag `exp2-base-europa` | 93b4879 (merge of exp2/plexil, 16:40) | -- | -- | EUROPA→PLEXIL's extension base | handoff |
| tag `exp2-europa_plexil` | 5b893a7 (17:35) | -- | -- | EUROPA→PLEXIL's extension; contained in `main` | F146; `git merge-base` |
| Exp II final system | no tag; the F145 (scan view) and F147 (on-support fact, step budget) fixes are on `main`. The F147 rerun ran at research e1506c6 (2026-09-29 09:11) | -- | -- | Exp II after the folded-in fixes | F145; F147; AGENT/handoff.md ("Exp II's final system adds F144-F147") |
| branch `feat/ablation` | 7525f2b (3 commits over exp1b: 627750d switches + stage 1, ccb0aa7 stage 2 + scorer + env-gated Earth-set, 7525f2b stage 3 jobs) in `.worktree/ablation` | -- | -- | §5.7 ablations; not merged ("switches default off; render_check 1099/1099") | F148; AGENT/todo.md |
| branches `reauth/plexil-{l2a,l2b,l3,l4}` | 3dea952, e078203, 478dbb2, e9914ad | worktrees of main's (pinned SRB) | -- | re-authoring, PLEXIL | A.6; `git branch` |
| branches `reauth/europa-{l2a,l2b,l3,l4}` | 66c3a5b, a699c58, 580bd5e, 547ebd2 | -- | -- | re-authoring, EUROPA→PLEXIL | A.6 |
| branch `feat/prefreeze-infra` | 548c19b (also on origin) | -- | -- | kept by the user | AGENT/todo.md; AGENT/handoff.md |
| `main` | 53ba795 (2026-09-30 10:18) | master 9338521 | main 3b16c05 | current; nothing pushed since ("research main ahead of origin") | AGENT/handoff.md; `git log` |

---

## Gaps

1. **Live validation incomplete** (A.9). Only PLEXIL L2-A has a final PASS in its worklog (3247 s). PLEXIL L4,
   EUROPA→PLEXIL L2-A and L2-B have finished v1 queues with provisional RESULT success but no validate.py verdict or
   final active time. PLEXIL L2-B and L3 are still running; EUROPA→PLEXIL L4 started 10:24 CST; EUROPA→PLEXIL L3 waits
   for a GPU. Final active times, validation-run counts, waiting times and post-validation diffs must be filled from the
   worklogs, validate.py and `git diff --stat exp1b..reauth/<b>-<case>` when each stops.
2. The engineers' returned summaries (spec "Your summary") are not in the repository. The waiting-time split is only
   derivable (A.9, PLEXIL L2-A ~2916 s [derived]).
3. **Disagreement**: F149/F151 attribute a held-out grep exposure (`chains/l2a_*.json`) to PLEXIL L2-A, but
   `plexil_l2a.jsonl` has no such note. F151 also omits EUROPA→PLEXIL L3's 2 printed lines of the forbidden
   `docs/research_findings.md`.
4. F151's headline "3-9 modelling notes" counts all notes; by A.5.2's classification, modelling/logic errors are 0-1
   for PLEXIL and 1-4 for EUROPA→PLEXIL. A findings-level statement of error counts does not exist yet.
5. EUROPA→PLEXIL L4's host drops "the granted donor's restore goal" (commit 547ebd2). F151 does not discuss it as a
   deviation, although it is analogous to L2-B's host-side goal.
6. `preplanned_transition_fraction` is not computed. evaluation/README.md calls it "a pending user decision" while the
   preregistration records it as decided.
7. The preregistered per-request wall-clock send time (preregistration §3) is not tabulated. F152's latency analysis
   covers the concern in another form.
8. The intervention response-time split (delivery / notice / planning / execution; heldout_design §8) is computed per
   request in `evaluation/interaction.py` but has no table or figure.
9. No record of an **ECONNRESET** incident was found anywhere in the repository sources read.
10. The user's rejection of a dev/test split is recorded only in the session memory, not in a repository document.
11. Manuscript: `sec:limitations` is referenced in results.tex but not defined. No main.tex, no .bib. Abstract,
    introduction, related work, discussion, limitations and conclusion are not drafted. `fig:architecture` and
    `fig:site` are placeholders. 24 of 36 citation keys need verification. The ablation and re-authoring results
    subsections are `\TBD`.
12. No paper-ready figure or table exists yet for the re-authoring study or the ablations. The exp1b swimlanes/videos
    exist only for L4 and L2-B.
13. No tag pins the final Experiment II system (after F145/F147); it lives on `main` (F147 rerun at e1506c6).
14. The EUROPA planner horizon defect (F151) was fixed only on `reauth/europa-l2b`. The frozen baseline is unchanged,
    and whether any Exp I held-out EUROPA→PLEXIL run was affected is asserted only for the covered runs ("7/7").
