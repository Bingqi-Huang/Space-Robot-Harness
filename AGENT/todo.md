# TODO

Goal: the Acta Astronautica paper. Held-out set decided 2026-09-23 -- **`docs/heldout_design.md` is the plan**; its
§8 order is the work order below. Branch `feat/heldout-ladder` (research repo + `space_robotics_bench`), cut from
`feat/experiment-campaign` at `fb47fd8`. All three methods already complete Mission A/B covered live (F92-F107).

## Work order -- `docs/heldout_design.md` §10 (each step: offline check first, then one decisive live run)

Done (F108, commits `ca492cf`, `3edd2d6`; SRB `6d72441`): docs; telemetry + inventory at the boundary; bays, labels,
radiators; Mission A/B scenarios; Ours' authority by target; SPICE Earth link + gated console; competent PLEXIL/EUROPA
Mission A (offline-verified). Ground protocol (§8, decision time 300 s) and base-wide expansion (§9) decided 2026-09-23.

1. [ ] Scene expansion (§9): battery-container unit (38,13), ISRU pilot-plant unit (ISRU yard), landing offload
       stand, habitat logistics shelf, depot return stand, road spurs; site model from 3 PDUs to a unit list; AMCL/Nav2
       map re-survey; offline `work_stands` for every new tray/button; one site-acceptance run (`d0_site_check.py`).
2. [ ] Scenarios parameterized by unit (A) and by source/destination/occupier (B).
3. [ ] Console protocol (§8): `--decision-time-s 300`, flight-rule grant table, HOLD reply, ALFUS labels.
4. [ ] Evaluator: rewrite `evaluation/violations.py` + `experiments/evaluator_recorder/` for the new mission_state
       (`units`, `objects`; approved cannibalization is not collateral); §8 interaction metrics in `evaluation/`;
       recorder wired into all three launch scripts; capability-server call-start timestamp.
5. [ ] Baselines cover every unit (L0/L1 parameterized), pick/place recovery set, consolidated NDDL; re-run covered
       live for PLEXIL, EUROPA and Ours on the final scene.
6. [ ] Ours development runs L2-A -> L2-B -> L3 -> L4-near -> L4-far; mission-generic changes only (§13.1), each in
       `docs/research_findings.md`.
7. [ ] Manifests + closed-capability certificates; freeze audit; git tags.
8. [ ] Experiment I campaign -> §5.7 ablations -> build `scan_label` (wrist-view label decode check there) ->
       Experiment II (timed, `engineering_worklog.jsonl`).

## Paper drafting (parallel)

- [ ] Introduction / Related Work / Method as LaTeX for Acta Astronautica, verified citations, no results language.
- [ ] Limitations must state: one engineer (no double-blind baseline authoring); "covers closed for landing
      ejecta" is our extrapolation; L2-B precedent is category-level only.

## Open decisions (user)

- `artifacts/runs/` holds ~100 development run dirs, 330 GB; cleanup deferred by the user (2026-09-23).
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
