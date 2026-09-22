# TODO

Order: `execution_plan` §21 -- the proposed method before the external baselines. All three methods (Ours, PLEXIL,
EUROPA→PLEXIL) now complete both Mission A and Mission B covered live (F92-F100, F104, F105, F106, 2026-09-22) --
see handoff.md. **Next: baselines / freeze / experiments**, not yet started as one coherent pass.

## Now -- small follow-ups

- [x] Rebuild `ros/plexil_capability_adapter`; fix its premature-completion ack bug (F104).
- [x] Merge `feat/plexil-baseline-live` back into `feat/experiment-campaign`.
- [x] Delete the three failed PLEXIL Mission B debug run dirs; rename the successful one to
      `plexil_mission_b_success_20260922`.
- [x] Merge `feat/europa-mission-b` back into `feat/experiment-campaign`.
- [x] PLEXIL Mission A rewritten onto shared `press`; EUROPA Mission A domain built; both live, both succeed (F106)
      -- uncommitted on `feat/experiment-campaign` directly, ask before committing.
- [ ] `mission-a-model.nddl`/`mission-b-model.nddl` duplicate their shared Base/Posture/Jaws timelines and rules --
      consolidate into one frozen capability model before the artifact freeze, not before (F105/F106 both note it).
- [ ] Wire the evaluator-violations recorder (`experiments/evaluator_recorder/`) into every method's launch script
      (Ours, PLEXIL, EUROPA), not just where it was developed.
- [ ] Add a call-start timestamp to the capability-server log (needed by the recorder's attribution).
- [ ] Servo gains/ramps/margins were tuned against the soft arm (F95/F96/F98): re-check a stall or dip only if a run
      shows one, do not retune preemptively.
- [ ] Killing a check script mid-navigate leaves Nav2's own goal running: cancel it
      (`/navigate_to_pose/_action/cancel_goal`, all-zero goal_id) before any restore.

## Path to the campaign (§21 order)

1. [ ] **Held-out grounding** (§21 item 1): tie each candidate held-out case (destination_occupied, spare_swapped,
       cover_obstruction, status_mismatch, route_block) to lunar-mission literature in `docs/lunar_task_catalog.md`;
       decide the final set (see "Open questions" below) *before* extending any baseline artifact, or a covered case
       for one method becomes held-out fiction for another.
2. [x] PLEXIL: Mission A rewritten onto `press`, both missions covered live end to end (F104, F106). Predefined
       recovery: base-move legs (`DriveAndDock`/`StowAndReturn`) now retry once (F106); pick/place legs' recovery
       set still not written (their failure kinds are settled, F92-F100, but no policy authored yet).
3. [x] EUROPA: Mission A + B domains, offline verification, live runs all done (F105, F106).
4. [ ] **H3 has no evidence yet**: every capability is `routine`, the guard has only ever fired on e-stop. Add the
       explicit hard invariant/approval classes the chosen held-out scenarios actually need (§4.3, §10.2) -- see
       "Open questions".
5. [ ] All three methods now complete both Mission A and Mission B covered live independently; still need a
       run-manifest/freeze pass actually exercising the merged evaluation infra
       (operator console, PLEXIL/EUROPA trace normalizers) against these corrected-arm runs, not just F103's dev runs.
6. [ ] Scenario manifests + closed-capability certificates (`experiments/scenarios/`) exist for 2 covered + 5 held-out
       candidates but were only ever exercised on 5 development runs (F103) -- re-validate.
7. [ ] Freeze method artifacts (git tags), run Experiment I, then the §5.7 Ours-internal ablations, then Experiment II
       (needs an extension case -- see "Open questions", B7).

## Paper drafting (parallel, does not block the campaign)

- [ ] Introduction, Related Work, Method (research_content §1-§4) as LaTeX for Acta Astronautica, verified citations,
      no results language before measurements.

## Open questions (need a user decision before the freeze)

- **Space context / hard boundaries for H3**: nothing currently makes "space-native" true. Candidates: a contact-
  interruption window (SPICE Earth visibility) paired with an approval-required operation class; an energy limit;
  which model plays the onboard tier. Pick at least one.
- **Held-out set**: admit `route_block` (never run with a mission variant)? A3/A4 (dust-fused lamp) and A5
  (substitution) don't exist in the scene yet -- build them or drop them.
- **Experiment II extension case**: needs a new capability other than the VLM (candidate: B7, undefined).

## Design items not yet built (pick up when a run needs them, not preemptively)

- [ ] Claims/reconcile: `check_item_at`, `read_indicator`, a claim ledger (a place that failed while the item sits on
      the shelf, gc3).
- [ ] Dock error band from localization's own uncertainty (real bias 12-13 cm; `DOCK_ERROR_M` 0.06).
- [ ] Unify pick's and press's per-frame tracking class (the press/place `interface` schema already agrees).
- [ ] `lower`'s stall is read as contact without checking `stopped_above_expected_m` against a bound first -- not yet
      observed to matter.
- [ ] An exception inside `_execute` leaves `failure_reason` blank (F62 §2); `OURS_RESET=1` reads TF before seeding
      AMCL (seed first).
- [ ] Single-frame VLM held/identity negatives can contradict visible geometry; unknown is correct, not "empty".
- [ ] Cache the views within one `pick` call (a pick costs 15-40 min wall; `find` alone ~10 min).
- [ ] The scene generator's `REACH` table is superseded by the reach model; delete it with `robot.reach_m` copies.
- [ ] `depot_stand/slot_1` (crate) has no legal stand at any reach distance.
- [ ] `space_runtime/facts.py` has no reducer branch for `operator_answered` (only needed if an answer must reach
      `guard.py`'s `approval_required`; the exchange already renders in context without it -- see `docs/operator_console.md`).

## Numbers still owed a measured source

`bring_in`'s sag margin (`held_drop_m`); the posture-window margin; the fit's agreement floor of one half; the
posture pull's 0.05/s.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15-77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; <=150 lines each; update at every milestone.
- No pytest beyond upstream suites; offline checks before one decisive live run.
- No defensive coding, corner-case guards, hash checks or ad-hoc patches (AGENT.md §4).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Model-facing tools are operations, not stages; no mechanical parameters in contracts (execution_plan §8.2).
- A check that cannot certify is evidence, not a veto; recovery belongs to the model through the harness.
- Never rerun a whole mission after a failure: restore the jaws-open snapshot before the failed step.
- One simulation at a time. Never navigate on truth. Kill only your own processes by explicit PID.
- Replies to the user: Simplified Chinese, plain words, concise; design choices are the user's to make.
