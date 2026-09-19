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

Pick in this order; each gets its own worktree branch, a findings section and a note in `handoff.md`.

1. [ ] **EUROPA baseline build** (§21 item 6, execution_plan §11.2): pin/build NASA EUROPA, run its examples, write
       the minimal NDDL domain for Mission A/B covered, the host with online replanning, and the EUROPA→PLEXIL
       activity bridge. Live check later through the common boundary (Session M's sim).
2. [ ] **PLEXIL Mission B** (§21 item 5, §11.1): covered plan, reusable library nodes, predefined recovery set,
       over the same boundary commands (`pick`/`place` now take the optional catalogue `item`).
3. [ ] **Experiment infrastructure** (§21 item 7, §12–§14): scenario manifests, evaluator-only success annotations,
       run-manifest writer (§19 layout), freeze tooling (tags), closed-capability validator, and scripts that
       compute the ALFUS measures and trustworthiness counts from `events.jsonl` + `check.log` (no hand-edited CSV).
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
