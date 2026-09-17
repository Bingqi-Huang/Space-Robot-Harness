# TODO

Order: `execution_plan` §21 (revised 2026-09-17) — the proposed method before the external baselines.
Goal of this phase: Ours completes Mission A/B covered and the held-out situations, then a 1x-sim-time video.

## Done

- LunarBot stack on SRB; common capability boundary; PLEXIL Mission A through it (F51–F52).
- Ours runtime (facts, context, guard, verification, trace, restart/switch) and Mission A `covered` with vision-only
  contact (F53–F54). Tasks grounded in `docs/lunar_task_catalog.md`.
- Mission B pick analysis, step-wise snapshot workflow, reasoner/VLM choice, patches reverted (F55).
- Manipulation + architecture design: `docs/semantic_to_metric_manipulation_plan.md` v3.

## Now: manipulation capabilities (plan v3, gates G0–G7)

- [ ] G0: wrist RGB-D recorder, ~30 viewpoints of the ORU and crate on the depot stand (truth only for scoring).
- [ ] G1: grasp candidates offline — classical (OpenCV + depth) first, then Contact-GraspNet / GraspNet baseline.
- [ ] G2: candidate rendering + VLM set-of-mark selection offline; swapped-item flag.
- [ ] Tools per plan v3 §2–§3: effects as OpenRAL rSkills (`servo_to_target`, `approach_guarded`, camera moves);
      perception control / queries as services (`grasp_candidates`, `choose_candidate`, `lock_target`,
      `target_status`, `hold_check`); thin contracts in the boundary.
- [ ] Ours side (plan v3 §5): object facts, reconciliation with provenance, attempt record in the context, budgets.
- [ ] G3–G5 live (servo, pick with unknown placement, generality), G6 ablation.

## Architecture follow-ups (plan v3 §2, when touched — no big refactor)

- [ ] Move `approach_target`, VLM `observe` / `locate_in_view`, feature-pose lowering out of `capability_server`;
      fixed-infrastructure places into OpenRAL world state; regression: Mission A `covered`.
- [ ] PLEXIL adapter Lookups expose the same raw evidence (capability results, jaw, poses, availability) — not Ours'
      verified facts. Evaluator counts constraint violations and false success declarations for all methods.
- [ ] `requires_remote_service` availability metadata for VLM-backed capabilities.

## Then

- [ ] G7: Mission B `covered` with the agent (snapshot workflow), then held-out: destination_occupied, spare_swapped,
      cover_obstruction, status_mismatch, route_block. Failures → mission-generic changes only.
- [ ] Space context variables only if the chosen scenarios exercise them.
- [ ] 1x video run + `experiments/video/overlay.py`.
- [ ] Baselines (§21 items 5–6), scenario manifests and freeze, Experiment I, Ours-internal ablations
      (research_content §5.7), Experiment II.

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
- Never rerun a whole mission after a failure: restore the snapshot before the failed step, fix, rerun that step.
- One simulation at a time. Never navigate on truth. Measure motion in sim time.
- Kill only your own run's processes by explicit PID. Never edit a script a live run executes.
- Replies to the user: always Simplified Chinese, plain words, concise; design choices are the user's to make.
