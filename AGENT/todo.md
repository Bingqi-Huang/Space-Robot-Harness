# TODO

Order: `execution_plan` §21 (revised 2026-09-17) — the proposed method before the external baselines.
Goal of this phase: Ours completes Mission A/B covered and the held-out situations, then a 1x-sim-time video.

## Done

- LunarBot stack on SRB; common capability boundary; PLEXIL Mission A through it (F51–F52).
- Ours runtime (facts, context, guard, verification, trace, restart/switch) and Mission A `covered` with vision-only
  contact (F53–F54). Tasks grounded in `docs/lunar_task_catalog.md`.
- Mission B pick analysis, step-wise snapshot workflow, reasoner/VLM choice, patches reverted (F55).
- Manipulation design **v4** (`docs/semantic_to_metric_manipulation_plan.md`): `pick` / `place` / `press` are single
  skills; the model composes operations, never stages (F56).

## Now: manipulation skills (plan v4, gates G0–G5)

- [x] G0: wrist RGB-D recorder, 29 viewpoints of the ORU and crate on the depot stand (truth only for scoring).
- [x] G1: grasp candidates offline, classical (OpenCV + depth): a correct neck grasp in 28/29 views, ~0.1 s a view.
- [x] G2: candidate rendering + VLM set-of-mark selection offline: 20/28 correct; the wrong-item flag is weak (7/29).
      Live, with the site's payload-handle convention in the prompt, the three asks agree on the neck (g3bf).
- [x] `pick(target, part)` as an OpenRAL procedural rSkill in the fork (find → select → approach → grasp → hold as
      internal stages; VLM chooses once, then the part's own template closes the loop; same-target local retries only;
      staged failure + evidence); one contract line in the boundary. `place(support)` written, not yet live.
- [x] Ours side (plan v4 §5): movable-object facts, automatic `item_held` / `item_placed` verification recomputed from
      the raw evidence, attempt record in the context. Guard unchanged (no posture/payload rules).
- [ ] G3: `pick` live, unknown placement, one call per trial; every failure returns a stage. **Nominal passed**
      (g3bn: one call, a same-target retry inside it, jaw 0.172, `item_held` true with 7.85 cm of lift). Running:
      ±8 cm / ±20–30° placements and a perturbed dock (g3bo).
- [ ] `place` live, then the pick→place pair on one snapshot.
- [ ] `find` still carries three tuned tables (`overview_pose`, `reach_zone_x_m`, `side_view_*`). Per plan v4 they
      should be a sweep of the arm's own reachable workspace with a measured stopping rule, like `tool_in_view` now
      replaces the camera constants (F57 §5). Do it when `find` next fails, not before.

## Architecture follow-ups (plan v4 §2, when touched — no big refactor)

- [ ] `press(target)` folds `approach_target` + `move_tool` + `grasp`; then `approach_target`, `move_tool`,
      `plan_ee_*`, `move_ee_*`, `move_joints`, `grasp` leave the model palette; regression: Mission A `covered`.
- [ ] Move VLM `observe` / `locate_in_view` and feature-pose lowering out of `capability_server`; fixed-infrastructure
      places into OpenRAL world state.
- [ ] Hardware-protecting limits while driving/holding (arm posture, base speed) into the kernel envelope / Nav2
      parameters, shared by all methods.
- [ ] PLEXIL adapter Lookups expose the same raw evidence (capability results, jaw, poses, availability) — not Ours'
      verified facts. Evaluator counts constraint violations and false success declarations for all methods.
- [ ] `requires_remote_service` availability metadata for VLM-backed capabilities.

## Then

- [ ] G4: Mission B `covered` with the agent (snapshot workflow); G5 held-out: destination_occupied, spare_swapped,
      cover_obstruction, status_mismatch, route_block. Failures → mission-generic changes only.
- [ ] Space context variables only if the chosen scenarios exercise them.
- [ ] 1x video run + `experiments/video/overlay.py`.
- [ ] Baselines (§21 items 5–6: PLEXIL Mission B with `pick`/`place` as Commands, EUROPA→PLEXIL), scenario manifests
      and freeze, Experiment I, Ours-internal ablations (research_content §5.7), Experiment II.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15–77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).
- Movable objects are not in MoveIt's planning scene.

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each; update at every milestone.
- No pytest beyond upstream suites; offline checks before one decisive live run.
- No defensive coding, no corner-case guards, no hash checks, no ad-hoc patches (AGENT.md §4, F55 §5).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Model-facing tools are operations, not stages; no mechanical parameters in contracts (execution_plan §8.2).
- Never rerun a whole mission after a failure: restore the snapshot before the failed step, fix, rerun that step.
- One simulation at a time. Never navigate on truth. Measure motion in sim time.
- Kill only your own run's processes by explicit PID. Never edit a script a live run executes.
- Replies to the user: always Simplified Chinese, plain words, concise; design choices are the user's to make.
