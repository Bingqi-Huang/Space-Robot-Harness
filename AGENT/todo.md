# TODO

Order: `execution_plan` §21 — the proposed method before the external baselines.
Goal of this phase: Ours completes Mission A/B covered and the held-out situations, then a 1x-sim-time video.
**Sequence in force (user): finish Mission B → `press` live → Mission A.** One simulation at a time.

## Now — Mission B carry (live sim, graph g9n / run g9o)

- [x] Selection by the declared contact width; closure by three direction budgets; lift; place shelf and tolerance;
      fragile checks as evidence; the carried item in every collision check.
- [x] IK acceptance rule: on the working branch **or** next to the seed (openral fbb33c9), measured offline first.
- [x] `find` and bring_in unblocked: heights 0.04–0.10 usable, ~14 cm of retraction (g9m had 0.02 alone and 0 cm).
- [ ] **The carry still loses the ORU** (g9o: jaw 0.169 → 0.100 on the drive, `oru_on` back to `depot_stand/slot_0`).
      Answer it with one pass over the closed g9o bag before changing anything: evaluator `/tf` object poses plus
      `/srb/env0/mission_state`, the ORU's base height over the stand across grasp → hold lift → bring_in → the
      first metres of the drive. It separates insufficient raise (IK ceiling 0.10) from sag after `hold_here` from
      drive acceleration; those need different fixes.
- [ ] Watch how far the model's own recovery gets in g9o (it found the empty jaw, then observed for the box). Its
      recovery is H1 evidence whether or not it succeeds — record it, do not steer it.
- [ ] Then place with the new shelf (never reached), stow, return dock, and full Mission B covered from the start.
- [ ] Then G5 held-out: destination_occupied, spare_swapped, cover_obstruction, status_mismatch, route_block.
- [ ] Then `press` live (never pressed a button), then Mission A's ready/stand deadlock (F62 §3).

## Numbers still owed a measured source

- [x] IK branch jump 1.2 rad — measured: accepted off-branch solutions jump ≤ 0.65, refused ones ≥ 2.90 (F79).
- [ ] bring_in sag margin 5 cm (`held_drop_m`) — from the bag, the actual sag of a held item after `hold_here`.
- [ ] Posture margin 0.10 rad.

## Then

- [ ] EUROPA baseline build (§21 item 6, execution_plan §11.2); PLEXIL Mission B (§21 item 5, §11.1).
- [ ] Experiment infrastructure (§21 item 7, §12–§14): scenario manifests, evaluator-only success annotations,
      run-manifest writer (§19 layout), freeze tooling, closed-capability validator, ALFUS/trustworthiness scripts
      computed from `events.jsonl` + `check.log` (no hand-edited CSV).
- [ ] Harness gaps: an exception inside `_execute` leaves `failure_reason` blank (F62 §2); `OURS_RESET=1` reads TF
      before seeding AMCL (seed first); the thin guard has never fired — add the explicit hard invariants/approval
      classes the scenarios need for H3 (§4.3, §10.2).
- [ ] Held-out grounding (§21 item 1) in `docs/lunar_task_catalog.md`; paper drafting of §1–§4 as LaTeX.
- [ ] Space-context variables only if the chosen scenarios exercise them.
- [ ] 1x video run (`D0_VIDEO=<file.mp4>`; `experiments/video/mission_video.py` + `track_from_bag.py` are done and
      tested on real data: follow view, harness panel, model chat with tool/skill calls, site plan).
- [ ] Freeze, Experiment I, Ours-internal ablations (research_content §5.7), Experiment II.

## Harness gaps (either way, when a run needs them)

- [ ] Single-frame VLM held/identity negatives can contradict visible geometry; unknown is correct, not "empty".
- [ ] Cache the views within one `pick` call (a pick costs 15–40 min wall; `find` alone ~10 min).
- [ ] The scene generator's `REACH` table is superseded by the reach model; delete it with `robot.reach_m` copies.
- [ ] `depot_stand/slot_1` (crate) has no legal stand at any reach distance.
- [ ] Servo command wind-up at a joint stop (release command to measured when stalled).

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15–77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).

## Rules

- **Exercise changed logic offline against the live graph before restarting a runtime** (F79): `/compute_ik`,
  `/compute_fk`, closed bags. g9m and g9n each cost a graph and a pick to learn what a query answered in seconds.
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
