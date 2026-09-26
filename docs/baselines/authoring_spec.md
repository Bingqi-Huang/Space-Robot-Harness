# Baseline authoring spec (PLEXIL and EUROPA->PLEXIL)

Shared by both external baselines (execution_plan §1.5, §11.1, §13.1; research_content §3.2-3.3, §5.2-5.3). Each
baseline's own doc (docs/baselines/plexil.md, docs/baselines/europa.md) states what it built; this file states the
rule both must follow, the **locked specification** both are built to (decided with the user 2026-09-23), and the
table format both use to show they followed it.

## Baseline authoring rule (fairness; mandatory)

Plan artifacts (PLEXIL plans/library nodes, EUROPA domain models/compatibilities, the EUROPA host's result
translation) may encode only what traces to:

- (a) the model-covered mission specification -- the site survey, the equipment catalogue, the manifest/inventory
  record and the covered mission briefs (Mission A: a unit reported a fault, identify, restore, verify, return;
  Mission B: deliver a named item from a named support to a named destination, return), at every serviced unit and
  every covered cargo/destination (`docs/heldout_design.md` §9: L0/L1 parameterized by unit);
- (b) a generic capability contract (`openral_ext/capability_server/contracts.yaml`) -- what a capability's inputs
  and outputs mean, for every caller, not a mission-specific shortcut through it;
- (c) the generic fields of a capability result (success, the robot-observable evidence every result carries: base
  pose, arm posture, jaw angle) -- read to know where the robot and the item are after a call, never branched on by
  failure kind or stage (locked spec, tier 1).

Do **not** encode held-out situations or anything specific to them: `heldout_radiator_cover`,
`heldout_destination_occupied`, `heldout_module_failure`, `heldout_cannibalize`, `heldout_cannibalize_far`,
`route_block`, and the retired `spare_swapped` / `cover_obstruction` / `status_mismatch` (drawn shutters, occupied
trays, failed modules, donor units, blocked routes). Do not open held-out solution material, held-out scenario code
paths or `experiments/scenarios/**/held_out`.

A baseline is allowed to be a *pre-engineered procedure* for the covered case -- that is the point of comparison
against Ours (which is not told the physical steps) -- but every fact the procedure relies on must be traceable by
the table below, not asserted from familiarity with the task family.

## Locked specification (2026-09-23)

Lock commit: `1b6a40f` (merge feat/baseline-lock-build, 2026-09-24); `evaluation/freeze_audit.py` checks the traceability
tables' files against it.

**Principle.** A baseline is the native PLEXIL / EUROPA mechanism plus the knowledge the covered specification
contains. The shared adapters (`ros/plexil_capability_adapter`, the HostLink bridge) only carry calls and state; they
hold no mission intelligence. Neither baseline is strengthened beyond this, and neither is weakened below it.

### The line: three tiers of failure handling

| Tier | Trigger | Baselines | Why it does not blur H1/H2 |
|---|---|---|---|
| 1 Call failure | a capability call returns failure | PLEXIL: repeat the identical call, at most **3 attempts** per call (`Try`); EUROPA: replan from the updated facts, the same call failing 3 times ends planning; then hold in place and ask mission control | no held-out case is solvable by repeating a call (`heldout_design.md` §1 rule 4) |
| 2 Goal verification | the covered brief says "verify the result": the breaker reads closed after the reset and still at the dock | a failed check re-runs the action that should achieve it under tier 1's budget, then escalates | makes a held-out run end "detected -> escalated", not a false success -- fair to the baselines |
| 3 Cause / situation | a branch keyed on why or in what situation something failed: trip cause, inventory status, tray occupancy, VLM observation, failure stage; or a response composed of capabilities outside the covered procedure | **forbidden** | this is exactly the knowledge whose post-freeze cost H2 measures; encoding it turns held-out into covered |

Grounding (verified 2026-09-23): ECSS-E-ST-70-11C §5.7.5.3i/5.7.5.4c (command retries as the first isolation step,
the number of repetitions a telecommand-changeable parameter -- no standard value), §5.7.5.2g (what a level cannot
handle goes to the next higher instance, ultimately ground), Table 5-1 (PLEXIL ~ E3 event-based on-board procedures,
EUROPA ~ E4 goal-oriented re-planning); RAX DS1 validation report p.2 (outside critical sequences a fault "usually
requires the intervention of the ground operations team"; EXEC discards the plan and enters standby); Wang, Russino,
Basich, Chien, ICAPS 2022 (MEXEC: re-schedule the failed task, then replan, then ground -- "similar to current Mars
Rover operations"); Estlin et al. NASA/TM-2006-213483 pp.26-27 (the PLEXIL rover plan models only the contingencies
of its scenario "for simplicity"); Morris et al. IWPSS 2013 (EUROPA->PLEXIL: "creating new operators and models ...
goes beyond current planner technology"); Ding et al. COWP 2023 (the closed-world baseline replans after every
action, with no situation handlers). No public source fixes a retry count.

- **Retry budget = 3 attempts per call**: the same cap Ours' reasoning loop has on an identical call
  (`configs/space_runtime.yaml` `reasoner.retry_cap_per_call: 3`, OpenRAL `ReasonerCore.retry_cap_per_kind`), so all
  three methods get the same per-call budget. EUROPA's `ATTEMPTS` is already 3; PLEXIL's `Try` legs go from 2 to 3.
- **No stage-specific branches.** Every `pick` call re-perceives from scratch, so a repeat already is "re-observe and
  retry"; a stage branch would only choose among the same responses. A stage failure that needs handling is fixed
  inside the shared skill, for all three methods.
- **After escalation the baseline holds where it is** (the protocol's HOLD reply); the run is recorded as needing
  ground re-authoring.

### Mission goals (formal equivalent of the brief, research_content §5.3 rule 8)

- **Mission A** (every scenario, covered or held-out, looks the same to a baseline): every serviced unit restored,
  arm stowed, rover at the dock. PLEXIL scans the five units' telemetry (`PowerUnit` Lookup) and services the tripped
  one; EUROPA receives the goal "every unit `Restored`" and the units' telemetry as facts, and the solver derives which
  unit to press. The reported unit is not used (the brief asks to identify the failed unit; L1 `covered_misreport`).
- **Mission B**: item X from support S to destination D, arm stowed, rover at dock; X in {spare ORU, spare battery
  module, consumables container}, D in {PDU-1..3 spares shelf, BESS receiving stand, habitat logistics stand}. Both
  baselines read (X, S, D) from the same launcher-supplied goal (EUROPA's `--goal` already is); PLEXIL's plan is
  parameterized by it (site features and item descriptions looked up in the plan's own tables).
- Item descriptions for `pick` (`target`, `part`) are written from the equipment catalogue and the item's look, one
  table shared by both baselines; not copied from Ours' runs of a new item.

### Changes to the current artifacts (audit 2026-09-23)

| Artifact | Change | Reason |
|---|---|---|
| PLEXIL `MissionA_Covered` (identify by telemetry, press, verify, re-press, final check at dock, escalate) | keep; budget 3 | tier 1-2, native `Try` / `if` |
| PLEXIL library `DriveAndDock` / `StowAndReturn` / `PickItem` / `PlaceItem` | every capability call under the same 3-attempt `Try` (today: nav/dock/return 2, stow/pick/place 1) | one uniform tier-1 budget |
| PLEXIL `MissionB_Covered` (hard-coded depot -> PDU-1 shelf, ORU only) | parameterize by (X, S, D) | otherwise L1 "other destination" would be falsely held-out |
| Adapter Lookups `LastFailureKind`, `LastFailureStage`, `jaw` | **delete** | used only by stage branching (tier 3); removing them keeps it out |
| EUROPA host `--power-field` (Python derives the restore goals from telemetry) | delete; goal = every unit `Restored`, telemetry injected as facts | mission logic belongs in goals/domain, not host code |
| EUROPA restore relapse monitor (a reached goal lost counts as a failure) | keep, budget 3 | native execution monitoring (T-REX: observations dominate expectations) |
| EUROPA `facts_from_result` | keep | §11.2 step 6 result translation; a dropped item stays unrepresentable (stated limitation) |
| EUROPA one goal per solve (solver segfault on chained goals), fresh plan DB per replan | keep, state in limitations | a workaround that makes EUROPA greedier, i.e. weaker, not stronger |
| `mission-a-model.nddl` + `mission-b-model.nddl` | **one consolidated domain** (press + pick/place + items + units) for both missions | otherwise EUROPA lacks pick/place in Mission A and L3 would fail for an unfair reason |
| EUROPA mission instance | every site item from the inventory record as an `Item` on its support | Ours sees the same manifest; L3's failure must be missing causal knowledge only |
| "Mission B brief checks" (`heldout_design.md` §10 step 5) | not done | would strengthen the baselines beyond the brief |

### Change control after the lock

A failed covered run is classified before anything changes:

| Cause | Allowed |
|---|---|
| Shared infrastructure (capability server, adapter transport, Nav2, simulator, launcher) | fix; applies to every method; recorded in `research_findings.md` |
| Authoring defect: an artifact does not implement this spec (wrong feature id, a domain that cannot solve a covered instance the spec covers) | fix only up to conformance with this spec |
| Physical-layer failure after the tier-1 budget | no baseline change; rerun this validation once unchanged; if it recurs it is a shared-capability defect, fixed for all methods |
| "One more branch would pass" | forbidden; any deviation from this spec goes to the user first |

### After the freeze (evidence for the paper, no live runs)

- **Retry-budget sensitivity**: run the frozen baselines offline (`plexiltest`, `sim_boundary.py`) on every held-out
  scenario's state with N = 1, 2, 3, 5 and record that the outcome ("detected -> escalated") does not change.
- **Re-authoring cost** (`heldout_design.md` §8, feeds H2): per held-out case, the developer time and new plan / domain
  nodes needed to cover it -- the answer to "an engineer could have written that branch".
- Limitations to state: the baselines are authored to the covered specification; a wider failure-mode analysis
  (e.g. an OVERTEMP response) would cover L2-A at a cost the re-authoring measure reports.

## Traceability table format

Each baseline doc carries one table per plan (or per library, when a library is shared across missions), one row
per fact the plan encodes that is not simply "call this capability with these arguments" (that much is rule (b) by
construction). Columns:

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| node/leg name | the value or choice | file:line or run id | (a)/(b)/(c) |

- **Plan element** -- the node, argument or branch in the plan (e.g. `ToDepot: navigate_to_feature`, `PlaceItem:
  release_constraint`).
- **Fact encoded** -- what the plan assumes or hard-codes there (a feature name, a catalogue item, a retry count).
- **Source** -- where that fact comes from: the site survey / catalogue / manifest (`interaction.json`, `site_map`),
  the covered brief, a contracts.yaml entry, or this spec (tier 1-2).
- **Rule** -- which of (a)/(b)/(c) above justifies it.

A row citing a held-out run or scenario name is a defect in the plan, not the table: fix the plan, not the row.
