# TODO

Goal: the Acta Astronautica paper. Held-out set decided 2026-09-23 -- **`docs/heldout_design.md` is the plan**; its
§8 order is the work order below. Branch `feat/heldout-ladder` (research repo + `space_robotics_bench`), cut from
`feat/experiment-campaign` at `fb47fd8`. All three methods already complete Mission A/B covered live (F92-F107).

## Work order (heldout_design §8) -- each step: offline check first, then one decisive live run

1. [x] Docs: `docs/heldout_design.md`; pointers in research_content §5.5/§5.6, execution_plan §6.4/§21, catalog §5
       (superseded) + OIG IG-18-001 misattribution corrected.
2. [x] SRB telemetry + inventory (2026-09-23): shared site model `srb/tasks/mobile_manipulation/lunar_base/site.py`
       (breaker/thermal/ORU physics, same in every scenario; scenarios set initial conditions only); SRB publishes
       `env0/power_telemetry` + latched `env0/inventory_record`; boundary queries `power_status`, `manifest.inventory`
       (items by serial, catalogue keyed by item name). Verified live (site_check_2).
3. [x] SRB assets: ORU bay per PDU (shelf tray form, role `equipment_bay`), installed ORUs ORU-0211/0233/0258 + spare
       ORU-0417 + crate CRT-0112 with Data Matrix labels, radiator + roll-up shutter (visual-only, `set_radiator_cover`)
       + blue cover button; service cover and its scenarios removed. `work_stands` live: bays 1.10-1.115 m, cover
       buttons 1.06-1.075 m (shelf reference 1.08-1.11). VLM read the open shutter right but took the light closed
       shutter's slat seams for fins -> shutter made charcoal, seams removed; site_check_3 reads both states right.
   - [ ] Label decode from a real wrist view (moved to the `scan_label` build, Exp II).
4. [x] SRB scenarios `covered`, `covered_misreport`, `heldout_radiator_cover`, `heldout_module_failure`,
       `heldout_cannibalize` (A), `covered`, `heldout_destination_occupied` (B). Only radiator_cover booted so far.
5. [ ] Harness:
   - [x] Authority by target: `guard.target_authority` rule `energized_equipment_removal` (pick from an
         `equipment_bay` of an energized unit -> approval_required), telemetry read fresh before the check,
         approvals keyed (capability, target), pending approvals carried on `request_operator`, console `GRANT:`.
         `pick.support` now required; `item` is the catalogue name for every method (PLEXIL Mission B plan
         recompiled, EUROPA host maps its object ids at the boundary). Not yet exercised live.
   - [x] `space_context/earth_visibility.py` (SPICE, DE440, Site01 89.455S 213.64E) -> `profiles/earth_link.json`:
         epoch 2028-10-11T00:49Z, Earth sets 2700 s into every run, back 13.5 d later, one-way delay 4.27 s;
         `space_context/link.py`; boundary `space_context.earth_link`; console gated by it (store-and-forward, a
         request while Earth is down gets a link "queued" status, not an answer). Kernels in `space_context/kernels/`.
   - [ ] **Operator protocol (user decision)**: what mission control grants, its decision time (`--decision-time-s`),
         ALFUS authority level of an approval. Needed before L4 runs.
   - [ ] Rewrite `evaluation/violations.py` + `experiments/evaluator_recorder/` for the new mission_state
         (`units`, `objects` for all five items; approved cannibalization is not collateral, unapproved is) and wire
         the recorder into all three launch scripts; capability-server call-start timestamp.
6. [~] Baseline competence (heldout_design §7; F108): PLEXIL Mission A (telemetry identify, verify, retry once,
       final check, escalate; adapter `PowerUnit` Lookup) and EUROPA `--power-field` (telemetry-grounded panels,
       restore goals held, relapse -> operator after 3) done + offline-verified. Still open: pick/place recovery set
       (both), consolidate the duplicated NDDL, Mission B "verify the destination before placing" if the brief
       implies it (decide when re-running B covered).
   - [ ] Re-run Mission A/B covered live for all three methods on the rebuilt scene (campaign prerequisite).
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

- `artifacts/runs/_debug_archive/` never existed (the old handoff was wrong). `artifacts/runs/` holds ~100 development
  run dirs, 330 GB (`ma5` alone 93 GB); some are cited as evidence in `docs/research_findings.md` -- which to delete?
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
