# TODO

Goal: the Acta Astronautica paper. **`docs/heldout_design.md` is the plan**; its §10 order is the work order below.
Steps 1-4 reviewed by the user and merged 2026-09-23: research `main`, SRB `main`, openral `master` (not pushed).
Start the next task on a new branch (`feat/<name>`) in each repo it touches.

## Done

- F108-F110: the held-out site (one physics, five serviced units each with its own equipment, units as scene data),
  Mission A/B scenarios over every unit, telemetry + inventory at the boundary, authority by target, SPICE Earth
  link + ground protocol (300 s, flight-rule grants, HOLD, ALFUS labels), evaluator classes 1-5 + interaction
  measures, AMCL map as Nav2's global costmap, crab restored (drive limits), live acceptance `site_check_10`.

## Work order -- `docs/heldout_design.md` §10 (each step: offline check first, then one decisive live run)

5. [ ] **Baseline competence on the final scene** (paper §5.2-5.3 fairness; Table 2/3). Pre-freeze, not results.
   - [ ] PLEXIL Mission A over all five units live (Identify + per-unit button text built, plexiltest ok).
   - [ ] PLEXIL Mission B parameterized by cargo/destination (plan reads them from the brief's site ids).
   - [ ] EUROPA: one consolidated NDDL domain for both missions and every unit; `--power-field` goals per unit.
   - [ ] Covered pick/place recovery set for both baselines (retry/re-grasp a baseline author would write).
   - [ ] Live covered re-runs on the final scene: PLEXIL, EUROPA, Ours x Mission A (one PDU, BESS, ISRU) and
         Mission B (ORU to a PDU shelf, container to habitat). One run each unless a run fails for a reason
         the method should have covered -- then fix and rerun.
6. [ ] **Ours development on the held-out ladder** (paper §4 method, §6.3 trace figure). Generic changes only
   (§13.1), each in `research_findings.md`; development runs never count as results.
   - [ ] L2-A shutter (BESS HVAC, a PDU radiator) -> L2-B destination occupied -> L3 module failure (ORU, battery,
         filter) -> L4-near cannibalize (ground grant) -> L4-far (ISRU donor, Earth link).
7. [ ] **Freeze** (paper §5.3): run manifests, closed-capability certificates, freeze audit, git tags in all repos.
8. [ ] **Campaign** (paper §6): Experiment I (ladder x units x 3 methods, repeated for model variance, paired
       instances) -> §5.7 ablations (Ours without facts / verification / guard / context reconstruction, subset of
       cases) -> build `scan_label` (Data Matrix, wrist camera) -> Experiment II (timed extension effort,
       `engineering_worklog.jsonl`, all three methods).
9. [ ] Real LunarBot segment (§5.8): design deferred until 8 is stable; ask the user before planning it.

## Paper drafting (parallel; LaTeX, Acta Astronautica)

- [ ] Introduction, Related Work, Problem Setting, Method: writable now (no results language), verified citations.
- [ ] Experimental Methodology (§5): writable after 7 (freeze fixes the cases, metrics and exclusion rules).
- [ ] Results, trace figure, Discussion: after 8.
- [ ] Limitations must state: one engineer (no double-blind baseline authoring); "covers closed for landing
      ejecta" is our extrapolation; L2-B precedent is category-level only; look-alike module masses.

## Open decisions (user)

- `artifacts/runs/` holds ~100 development run dirs, 330 GB; cleanup deferred by the user (2026-09-23).
- Push the merged `main`/`master` of the three repos to their remotes: when?

## Design items not yet built (pick up when a run needs them)

- [ ] Claims/reconcile: `check_item_at`, `read_indicator`, a claim ledger.
- [ ] Dock error band from localization's own uncertainty (real bias 12-13 cm; `DOCK_ERROR_M` 0.06).
- [ ] Unify pick's and press's per-frame tracking class.
- [ ] `lower`'s stall read as contact without checking `stopped_above_expected_m` against a bound.
- [ ] An exception inside `_execute` leaves `failure_reason` blank; `OURS_RESET=1` reads TF before seeding AMCL.
- [ ] Single-frame VLM held/identity negatives can contradict visible geometry; unknown is correct, not "empty".
- [ ] Cache the views within one `pick` call (a pick costs 15-40 min wall; `find` alone ~10 min).
- [ ] The scene generator's `REACH` table is superseded by the reach model; delete it with `robot.reach_m` copies.
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
