# TODO

Goal: the Acta Astronautica paper. **`docs/heldout_design.md` is the plan**; its §10 order is the work order below.
Steps 1-4 merged and pushed 2026-09-23 (research `main`, SRB `main`, openral `master`). Step 5 (baseline lock) is
docs on `feat/baseline-lock`. Start each next task on a new branch (`feat/<name>`) in every repo it touches.

## Done

- F108-F110: the held-out site (five serviced units, own equipment each, units as scene data), Mission A/B scenarios
  over every unit, telemetry + inventory at the boundary, authority by target, SPICE Earth link + ground protocol,
  evaluator classes 1-5 + interaction measures, AMCL map as Nav2's global costmap, crab restored, `site_check_10`.
- 2026-09-23 decisions (docs): baseline lock (`docs/baselines/authoring_spec.md` "Locked specification"); run farm
  (`heldout_design.md` §11); physical validation of the held-out action forms (§12).

## Work order -- `docs/heldout_design.md` §10

6. [ ] **Run farm on `pro6000`** (§11; parallel with 7-8). Done 2026-09-23: image `runfarm:22.04` (Dockerfile,
       `docker/runfarm/`) built on both machines (uid 1000 here, 1007 there); home installs + caches rsynced; repo at
       the same path (`/mnt/SharedData` = nofail bind mount of `/nvme02/bingqi/SharedData`); nvidia-container-toolkit,
       docker group; `runfarm.sh` pins each container to 10 cores + HT on its GPU's socket. Physics stays CPU PhysX
       (user, 2026-09-23).
   - [ ] Equivalence + profile: PLEXIL Mission A covered on the final scene with `D0_PROFILE=1`, in a container on
         pro6000 GPU 0 (outcome, sim/wall ratio, per-tick buckets); then the same 6 ways concurrently; re-cost.
7. [ ] **Baselines built to the lock**, offline only (parallel with 6 and 8):
   - [ ] every call under a 3-attempt `Try` (PLEXIL library); EUROPA `ATTEMPTS` 3 (already).
   - [ ] delete adapter Lookups `LastFailureKind`, `LastFailureStage`, `jaw`.
   - [ ] PLEXIL Mission B parameterized by (item, source, destination) from the shared launcher goal; item-description
         table from the catalogue (ORU, battery module, consumables container).
   - [ ] EUROPA: one consolidated NDDL domain; delete `--power-field`, goal "every unit Restored" + telemetry facts;
         every inventoried item in the instance; relapse monitor kept at budget 3.
   - [ ] offline: plexiltest / `sim_boundary.py` for every unit (Mission A) and every covered cargo x destination (B);
         traceability tables in `docs/baselines/{plexil,europa}.md` updated.
8. [ ] **Physical validation** (§12; prerequisite for every live run below):
   - [ ] offline: each new item's handle graspable; item x support clearances; a free legal support for the removed
         module in L3/L4; `retrip_delay_s` from a stated thermal assumption.
   - [ ] seven scripted chains, one run each (L2-A PDU+BESS with BESS panel; L3 PDU; L3 BESS; L3 ISRU with ISRU panel;
         L4-far carry; L2-B both occupiers; Mission B both new cargos). Failures fixed in the shared layer only.
9. [ ] Covered live re-runs on the final scene: PLEXIL, EUROPA, Ours x Mission A (one PDU, BESS, ISRU) and Mission B
       (ORU to a PDU shelf, container to habitat). One run each; failures classified by the lock's change-control table.
10. [ ] **Ours development on the held-out ladder** (paper §4, §6.3 trace figure). Generic changes only (§13.1), each
        in `research_findings.md`; development runs never count. L2-A -> L2-B -> L3 -> L4-near -> L4-far.
        Watch: a reset reported done before the L2-A re-trip (false success), and requesting approval before LOS in L4.
11. [ ] **Freeze** (paper §5.3): manifests, closed-capability certificates, freeze audit, git tags in all repos; the
        frozen image is the campaign environment. Then offline retry-budget sensitivity (N = 1, 2, 3, 5, every held-out
        state).
12. [ ] **Campaign** (paper §6), entirely on the run farm, a paired instance's three methods on the same hardware:
        Experiment I (ladder x units x 3 methods, repeated for model variance) -> §5.7 ablations -> build `scan_label`
        -> Experiment II -> §8 re-authoring cost per held-out case.
13. [ ] Real LunarBot segment (§5.8): design deferred until 12 is stable; ask the user before planning it.

## Paper drafting (parallel; LaTeX, Acta Astronautica)

- [ ] Introduction, Related Work, Problem Setting, Method: writable now (no results language), verified citations.
- [ ] Experimental Methodology (§5): writable after 11 (freeze fixes the cases, metrics and exclusion rules).
      Baseline paragraph: ECSS E3 (PLEXIL) / E4 (EUROPA) with pre-planned responses for covered failure modes, rest to
      ground (ECSS-E-ST-70-11C §5.7.5.2g); sources listed in `authoring_spec.md`.
- [ ] Results, trace figure, Discussion: after 12.
- [ ] Limitations must state: one engineer (no double-blind baseline authoring); "covers closed for landing ejecta"
      is our extrapolation; L2-B precedent is category-level only; look-alike module masses; baselines authored to the
      covered specification -- a wider failure-mode analysis would cover L2-A at the measured re-authoring cost;
      EUROPA solves one goal at a time (solver segfault on chained goals) with a fresh database per replan; a dropped
      item is unrepresentable in the EUROPA domain; physical-layer failures reported per leg.

## Open decisions (user)

- `artifacts/runs/` holds ~100 development run dirs, 330 GB; cleanup deferred by the user (2026-09-23).
- Merge of `feat/baseline-lock` + `feat/run-farm` into `main` (both pushed 2026-09-23) awaits approval.

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
posture pull's 0.05/s; `retrip_delay_s` (L2-A, from a stated thermal assumption before freeze).

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
- Baselines: native mechanism + covered knowledge only; never strengthened after a failed run (lock change control).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Held-out situations need a real precedent for the situation itself; rigid assets; verified action forms only.
- Model-facing tools are operations, not stages; no mechanical parameters in contracts (execution_plan §8.2).
- One simulation per GPU. Never navigate on truth. Kill only your own processes by explicit PID (pro6000 is shared).
- Replies to the user: Simplified Chinese, plain words, concise; design choices are the user's to make.
