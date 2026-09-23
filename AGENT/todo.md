# TODO

Goal: the Acta Astronautica paper. **`docs/heldout_design.md` is the plan**; its §10 order is the work order below.
Development runs on `pro6000` (see handoff). Larger tasks on `feat/<name>` + `.worktree/<name>`; small fixes straight
on main (AGENT.md §1). Local commits since 2026-09-23 are NOT pushed yet (research main, openral master, SRB main).

## Done

- F108-F111: held-out site, scenarios, protocol, evaluator, baseline lock, run farm, models on paratera.
- F112 (2026-09-24): step 7 (baselines built to the lock, EUROPA use-after-free patched) and step 8 (physical
  validation: every held-out action form executed; shared-layer fixes in nav map, pick, place, press, capability
  boundary, run farm). Final batch `artifacts/runs/chain_*_f` (see the F112 table).

## Work order -- `docs/heldout_design.md` §10

7. [x] Baselines built to the lock (offline): PLEXIL 51 cases, EUROPA A x 5 units + failure paths, B 15 x 3.
8. [x] Physical validation: nine scripted chains, final batch on frozen code (F112 table; fill any gap there first).
9. [ ] Covered live re-runs on the final scene: PLEXIL, EUROPA, Ours x Mission A (one PDU, BESS, ISRU) and Mission B
       (ORU to a PDU shelf, container to habitat). One run each; failures classified by the lock's change-control table.
       Before launching: the PLEXIL adapter is rebuilt in main's `ros/` (done 2026-09-24); Mission B's goal comes from
       `D0_ENV` cargo/destination (`d0_common.mission_b_goal`); EUROPA runs the patched build.
10. [ ] **Ours development on the held-out ladder** (paper §4, §6.3 trace figure). Generic changes only (§13.1), each
        in `research_findings.md`; development runs never count. L2-A -> L2-B -> L3 -> L4-near -> L4-far. Watch: a
        reset reported done before the L2-A re-trip (30 s, false success); requesting approval before LOS in L4.
11. [ ] **Freeze** (paper §5.3): manifests, closed-capability certificates, freeze audit, git tags in all repos; the
        run-farm image + synced home installs are the campaign environment. Then offline retry-budget sensitivity
        (N = 1, 2, 3, 5 on every held-out state).
12. [ ] **Campaign** (paper §6), entirely on the run farm, a paired instance's three methods on the same hardware:
        Experiment I (ladder x units x 3 methods, repeated for model variance) -> §5.7 ablations -> build `scan_label`
        -> Experiment II -> §8 re-authoring cost per held-out case.
13. [ ] Real LunarBot segment (§5.8): design deferred until 12 is stable; ask the user before planning it.

## Paper drafting (parallel; LaTeX, Acta Astronautica)

- [ ] Introduction, Related Work, Problem Setting, Method: writable now (no results language), verified citations.
- [ ] Experimental Methodology (§5): after 11. Baseline paragraph: ECSS E3 (PLEXIL) / E4 (EUROPA), pre-planned
      responses for covered failure modes, the rest to ground (ECSS-E-ST-70-11C §5.7.5.2g); sources in authoring_spec.
- [ ] Results, trace figure, Discussion: after 12.
- [ ] Limitations must state: one engineer (no double-blind baseline authoring); "covers closed for landing ejecta"
      is our extrapolation; L2-B precedent is category-level only; look-alike module masses (1 kg); baselines authored
      to the covered specification (a wider failure-mode analysis would cover L2-A at the measured re-authoring cost);
      EUROPA solves one goal at a time and needed an upstream memory fix (F112); a dropped item is unrepresentable in
      the EUROPA domain; physical-layer failures reported per leg; one LLM/VLM (DeepSeek-V4.1-Flash, 60 s VLM choices);
      `retrip_delay_s` 30 s is our thermal estimate.

## Open decisions (user)

- Push the 2026-09-24 commits (research, openral, SRB) -- ask first.
- `artifacts/runs/` development dirs of this session (site_check_11/12, navrepro_*, chain_* before `_f`, diag_nav_1):
  keep or delete? Dev machine: ~100 old run dirs, 330 GB, cleanup deferred.

## Open (fix when a run meets it)

- MPPI "Resulting plan has 0 poses" (~1 in 15 legs): the global planner's start pose freezes while TF and AMCL stay
  fresh (bag `chain_l2a_pdu_f`, F112 §3; `artifacts/runs/bag_plan_lag.py`). Cause inside planner_server not found.
- VLM region choice takes ~60 s median; if the campaign time budget needs it, measure a non-reasoning setting.
- `observe`'s own VLM timeout is still 120 s (answers in seconds today).

## Design items not yet built (pick up when a run needs them)

- [ ] Claims/reconcile: `check_item_at`, `read_indicator`, a claim ledger.
- [ ] Dock error band from localization's own uncertainty (real bias 12-13 cm; `DOCK_ERROR_M` 0.06).
- [ ] Unify pick's and press's per-frame tracking class.
- [ ] An exception inside `_execute` leaves `failure_reason` blank; `OURS_RESET=1` reads TF before seeding AMCL.
- [ ] Single-frame VLM held/identity negatives can contradict visible geometry; unknown is correct, not "empty".
- [ ] Cache the views within one `pick` call.
- [ ] The scene generator's `REACH` table is superseded by the reach model; delete it with `robot.reach_m` copies.
- [ ] If sim speed is ever needed: TF publishing (24 ms/tick) and `_get_dones` (17 ms) outweigh everything but physics.

## Numbers still owed a measured source

`bring_in`'s sag margin (`held_drop_m`); the posture-window margin; the fit's agreement floor of one half; the
posture pull's 0.05/s.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15-77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).
- Teardown prints tracebacks and a move_group segfault after SIGINT: shutdown noise, not a run failure.

## Rules

- Branch + worktree for larger tasks only; delete both after merge. Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; <=150 lines each; update at every milestone.
- No pytest beyond upstream suites; offline checks before one decisive live run. No base-rate reruns.
- No defensive coding, corner-case guards, hash checks or ad-hoc patches (AGENT.md §4).
- Baselines: native mechanism + covered knowledge only; never strengthened after a failed run (lock change control).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- One simulation per GPU; never navigate on truth; kill only your own processes / containers.
- Never edit the shared skills (openral rskill modules) while runs are live: runners import them lazily.
- Replies to the user: Simplified Chinese, plain words, concise; design choices are the user's to make.
