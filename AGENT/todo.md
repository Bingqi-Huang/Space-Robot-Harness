# TODO

Goal: the Acta Astronautica paper. Held-out set decided 2026-09-23 -- **`docs/heldout_design.md` is the plan**; its
§8 order is the work order below. Branch `feat/heldout-ladder` (research repo + `space_robotics_bench`), cut from
`feat/experiment-campaign` at `fb47fd8`. All three methods already complete Mission A/B covered live (F92-F107).

## Work order (heldout_design §8) -- each step: offline check first, then one decisive live run

1. [x] Docs: `docs/heldout_design.md`; pointers in research_content §5.5/§5.6, execution_plan §6.4/§21, catalog §5
       (superseded) + OIG IG-18-001 misattribution corrected.
2. [ ] SRB telemetry + inventory: per-PDU breaker state / trip cause / energized / installed ORU serial in the
       mission tasks; `power_status` query and inventory records in `manifest` (capability server contracts).
3. [ ] SRB assets (`assets/lunar_base/process/author_props.py`, `scene/layout.yaml`):
   - [ ] ORU bay on each PDU, tray form like the spares shelf, installed ORU with T-handle up; `work_stands` must
         list a legal stand for every bay (compute offline before anything else).
   - [ ] Data Matrix + S/N label on every ORU top face (NASA-STD-6002); wrist-view still render decoded by zxing-cpp.
   - [ ] Radiator fins + cover (open/closed visual variants, no joint) + blue dummy cover button on the panel;
         spacing vs. the red reset button fixed offline so `press` cannot confuse them.
   - [ ] Remove the service cover prop.
4. [ ] SRB scenarios: `covered_misreport`, `heldout_radiator_cover`, `heldout_module_failure`,
       `heldout_cannibalize` (+ existing `heldout_destination_occupied`); evaluator conditions per heldout_design §4;
       delete `heldout_cover_obstruction` / `heldout_status_mismatch` / `heldout_spare_swapped` code.
5. [ ] Harness:
   - [ ] Authority by target: support classes in the site survey; one generic guard rule (removal from the bay of an
         energized unit → `approval_required`); approvals keyed (capability, target); `operator_answered` reducer.
   - [ ] `space_context/`: SPICE Earth elevation at a south-polar site, epoch so LOS falls inside the L4 run,
         precomputed profile with provenance; link gate (operator channel down during LOS, store-and-forward);
         one-way delay per Landon et al. 2025.
   - [ ] Operator console live + written scripted operator protocol (same for all methods), ALFUS events.
   - [ ] Evaluator-violations recorder in all three launch scripts; call-start timestamp in capability-server log.
6. [ ] Baseline competence (heldout_design §7): PLEXIL + EUROPA covered artifacts read `power_status`, press,
       re-check after a dwell, retry once then escalate; pick/place recovery set; consolidate the duplicated NDDL
       (`mission-a-model.nddl`/`mission-b-model.nddl`). Author from the covered spec only.
7. [ ] Ours development runs, one per case: L2-A → L2-B → L3 → L4. Mission-generic changes only (§13.1); record
       each in `docs/research_findings.md`.
8. [ ] Rewrite `experiments/scenarios/` manifests + certificates for the new set; freeze audit; git tags.
9. [ ] Experiment I campaign → §5.7 ablations → build `scan_label` (not registered in any method) → Experiment II
       (timed, `engineering_worklog.jsonl`).

## Paper drafting (parallel)

- [ ] Introduction / Related Work / Method as LaTeX for Acta Astronautica, verified citations, no results language.
- [ ] Limitations must state: one engineer (no double-blind baseline authoring); "covers closed for landing
      ejecta" is our extrapolation; L2-B precedent is category-level only.

## Open decisions (user)

- `_debug_archive/` under `artifacts/runs/` (117 GB): delete?
- Merge `feat/experiment-campaign` (+ this branch) to `main`: when?

## Design items not yet built (pick up when a run needs them)

- [ ] Claims/reconcile: `check_item_at`, `read_indicator`, a claim ledger.
- [ ] Dock error band from localization's own uncertainty (real bias 12-13 cm; `DOCK_ERROR_M` 0.06).
- [ ] Unify pick's and press's per-frame tracking class.
- [ ] `lower`'s stall read as contact without checking `stopped_above_expected_m` against a bound.
- [ ] An exception inside `_execute` leaves `failure_reason` blank; `OURS_RESET=1` reads TF before seeding AMCL.
- [ ] Single-frame VLM held/identity negatives can contradict visible geometry; unknown is correct, not "empty".
- [ ] Cache the views within one `pick` call (a pick costs 15-40 min wall; `find` alone ~10 min).
- [ ] The scene generator's `REACH` table is superseded by the reach model; delete it with `robot.reach_m` copies.
- [ ] `depot_stand/slot_1` has no legal stand at any reach distance -- nothing may be staged there for a pick.
- [ ] Servo gains were tuned against the soft arm (F95/F96/F98): re-check only if a run shows a stall or dip.

## Numbers still owed a measured source

`bring_in`'s sag margin (`held_drop_m`); the posture-window margin; the fit's agreement floor of one half; the
posture pull's 0.05/s; `retrip_delay_s` (L2-A, set from a stated thermal assumption before freeze).

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15-77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).
- Killing a check script mid-navigate leaves Nav2's goal running: cancel `/navigate_to_pose/_action/cancel_goal`
  (all-zero goal_id) before any restore.

## Rules

- Branch or worktree per task (`.worktree/<name>`); delete after merge. Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; <=150 lines each; update at every milestone.
- No pytest beyond upstream suites; offline checks before one decisive live run. No base-rate reruns of covered
  missions just to get a number (rejected 2026-09-23).
- No defensive coding, corner-case guards, hash checks or ad-hoc patches (AGENT.md §4).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Held-out situations need a real precedent for the situation itself; rigid assets; verified action forms only.
- Model-facing tools are operations, not stages; no mechanical parameters in contracts (execution_plan §8.2).
- One simulation per GPU. Never navigate on truth. Kill only your own processes by explicit PID.
- Replies to the user: Simplified Chinese, plain words, concise; design choices are the user's to make.
