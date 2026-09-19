# TODO

Order: `execution_plan` §21 — the proposed method before the external baselines.
Goal of this phase: Ours completes Mission A/B covered and the held-out situations, then a 1x-sim-time video.
**Sequence in force (user): finish Mission B → `press` live → Mission A.** Two sessions work in parallel; the split
and file ownership are in `handoff.md` ("Two sessions"). Only Session M runs a simulation.

## Session M — Mission B manipulation (live sim)

- [x] g8q close-in stall → no sag integral / posture pull in empty-jaw close-in (openral f925430).
- [x] Fragile vetoes → evidence (zero-triangle permission, insertion free-rays); selected mark width/range in context.
- [x] Carry root cause (ORU on the rear deck) → catalogue envelope in every validity check; bring_in may raise.
- [x] Place root cause (sweep at carry height, 2.4 cm shelf clearance) → envelope over support, 3 cm over tolerance,
      shelf 0.60 x 0.72 m (SRB 6839574).
- [ ] g8v result on the old graph: does the model recover pick failures and reach PDU-1 holding?
- [ ] Teardown g8m_contact → fresh graph (new shelf) → pick → carry → place with `item`; check no deck contact,
      over reached, item_placed, evaluator delivered.
- [ ] Repeat pick+carry from one snapshot without STOP_ON_FAILURE; count mission-level success and recoveries.
- [ ] If the VLM keeps choosing the pedestal: decide with the user between a catalogue width filter inside pick
      (source the tolerance) and leaving it to model recovery.
- [ ] Servo command wind-up at a joint stop (release command to measured when stalled).
- [ ] Stow + return dock (never reached), then full Mission B covered from the initial state.
- [ ] Then G5 held-out: destination_occupied, spare_swapped, cover_obstruction, status_mismatch, route_block.
- [ ] Then `press` live (never pressed a button), then Mission A's ready/stand deadlock (F62 §3).

## Parallel track — Session P (offline only; no sim, no Session M files)

Worktrees `.worktree/<name>`, branches `p/<name>`, collected on `p/integration` (handoff "Session P state").

1. [x] EUROPA build + generic host/replan/bridge on a skeleton domain (F80). [ ] Mission B NDDL domain, retry cap and
       "near" distance into config — after the manipulation contracts settle; live check on Session M's sim.
2. [x] PLEXIL Mission B covered on library nodes, nominal path (F79). [ ] predefined recovery set (after pick/place
       failure kinds settle); [ ] Mission A on `press` only after `press` is fixed (user).
3. [x] Experiment infrastructure (F81). [ ] review fixes (false-completion = reports claiming success only; drop
       smoke tests) → re-merge into `p/integration`.
3b. [x] Operator mechanism (request pauses Ours/PLEXIL/EUROPA until the console answers; PLEXIL node trace kept) and
       the literature-grounded protocol (`docs/operator_protocol.md`), both offline-verified. [ ] At merge: the
       operator answer is read from the event record, not `facts.py`'s reducer (Session M's file) — add the reducer
       branch in `docs/operator_console.md` then. [ ] Answer-policy script text once the scenes are fixed.
       [ ] `report_to_operator` could carry a structured "mission complete" field (false-completion count now reads
       the final ledger).
3c. [ ] Evaluator violation list (`docs/evaluator_violations_draft.md`): explained to the user, awaiting decision.
3d. [ ] **Merge `p/integration` into `feat/manipulation-contracts` after Session M finishes Mission B** (user), rebuild
       the PLEXIL adapter, then delete merged `p/*` branches/worktrees and stale `feat/g0-wrist-rgbd`,
       `fix/mission-operation-evidence`.
4. [ ] **Harness gaps in `space_runtime`/boundary** (not Session M's files): an exception inside `_execute` leaves
       `failure_reason` blank (F62 §2); `OURS_RESET=1` reads TF before seeding AMCL (seed first); the thin guard has
       never fired — add the explicit hard invariants/approval classes the scenarios need for H3 (§4.3, §10.2).
5. [ ] **Held-out grounding** (§21 item 1): tie each G5 held-out case to lunar-mission literature in
       `docs/lunar_task_catalog.md`; list scene changes needed (implemented later by Session M in SRB).
6. [ ] **Paper drafting**: Introduction, Related Work and Method (research_content §1–§4) as LaTeX for Acta
       Astronautica, with verified citations; no results language before measurements.

## Harness gaps (either session, when a run needs them)

- [ ] Single-frame VLM held/identity negatives can contradict visible geometry; unknown is correct, not "empty".
- [ ] Cache the views within one `pick` call (a pick costs 15–40 min wall; `find` alone ~10 min).
- [ ] The scene generator's `REACH` table is superseded by the reach model; delete it with `robot.reach_m` copies.
- [ ] `depot_stand/slot_1` (crate) has no legal stand at any reach distance.

## Open questions (user deferred, 2026-09-20)

- Space context + hard boundaries for H3/space-native: all capabilities are `routine`, guard fires only on estop.
  Candidates: contact interruption (SPICE Earth visibility) + approval-required operation class; energy limit; which
  model plays the onboard tier.
- Held-out set: admit `route_block` (never run with a mission variant)? A3+A4 dust-fused lamp and A5 substitution do
  not exist in the scene; Experiment II needs a new capability other than the VLM (B7).

## Then

- [ ] Space-context variables only if the chosen scenarios exercise them.
- [ ] 1x video run + `experiments/video/overlay.py`.
- [ ] Freeze, Experiment I, Ours-internal ablations (research_content §5.7), Experiment II.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15–77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each; update at every milestone.
- No pytest beyond upstream suites; offline checks before one decisive live run.
- No defensive coding, corner-case guards, hash checks or ad-hoc patches (AGENT.md §4).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Model-facing tools are operations, not stages; no mechanical parameters in contracts (execution_plan §8.2).
- A check that cannot certify is evidence, not a veto; recovery belongs to the model through the harness.
- Never rerun a whole mission after a failure: restore the jaws-open snapshot before the failed step.
- One simulation at a time. Never navigate on truth. Kill only your own processes by explicit PID.
- Replies to the user: Simplified Chinese, plain words, concise; design choices are the user's to make.
