# Baseline authoring spec (PLEXIL and EUROPA->PLEXIL)

Shared by both external baselines (execution_plan §1.5, §11.1, §13.1; research_content §3.2-3.3, §5.2-5.3). Each
baseline's own doc (docs/baselines/plexil.md, docs/baselines/europa.md) states what it built; this file states the
one rule both must follow and the table format both use to show they followed it.

## Baseline authoring rule (fairness; mandatory)

Plan artifacts (PLEXIL plans/library nodes, EUROPA domain models/compatibilities) may encode only what traces to:

- (a) the model-covered mission instance -- the specific site, objects and mission brief Ours is run on (Mission A
  `covered`, Mission B `covered`; site_knowledge, the manifest, the mission brief text);
- (b) a generic capability contract (`openral_ext/capability_server/contracts.yaml`) -- what a capability's inputs
  and outputs mean, for every caller, not a mission-specific shortcut through it;
- (c) failure kinds and reported stages that capabilities actually returned in covered development runs (this
  repo's `artifacts/runs/**`, or a covered run of the baseline's own plan) -- never a failure kind/stage invented
  because it seems plausible.

Do **not** encode held-out situations or anything specific to them: `destination_occupied`, `spare_swapped`,
`cover_obstruction`, `status_mismatch`, `route_block` (occupied shelves, swapped slots, covers over buttons,
misread lamps, blocked routes). Do not open held-out solution material or `experiments/scenarios/**/held_out`.

A baseline is allowed to be a *pre-engineered procedure* for the covered case -- that is the point of comparison
against Ours (which is not told the physical steps) -- but every fact the procedure relies on must be traceable by
the table below, not asserted from familiarity with the task family.

## Traceability table format

Each baseline doc carries one table per plan (or per library, when a library is shared across missions), one row
per fact the plan encodes that is not simply "call this capability with these arguments" (that much is rule (b) by
construction). Columns:

| Plan element | Fact encoded | Source | Rule |
|---|---|---|---|
| node/leg name | the value or choice | file:line or run id | (a)/(b)/(c) |

- **Plan element** -- the node, argument or branch in the plan (e.g. `ToDepot: navigate_to_feature`, `PlaceItem:
  release_constraint`).
- **Fact encoded** -- what the plan assumes or hard-codes there (a feature name, a catalogue item, a retry count, a
  failure-kind/stage branch).
- **Source** -- where that fact comes from: a site_knowledge/manifest event (run id + `events.jsonl` line or
  field), a contracts.yaml entry, a covered dev run's `execution_finished`/capability-server log line, or another
  covered baseline run (e.g. `MissionA_Covered` p1).
- **Rule** -- which of (a)/(b)/(c) above justifies it.

A row citing a held-out run or scenario name is a defect in the plan, not the table: fix the plan, not the row.
