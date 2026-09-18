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

- [x] G0–G2 offline: wrist RGB-D recorder (29 views), classical candidates (28/29 with a correct neck grasp),
      VLM set-of-mark selection (20/28; a single ask scores the same as the majority of three).
- [x] `pick(target, part)` and `place(support)` as procedural rSkills in the fork; one contract line each at the
      boundary; Ours-side object facts, automatic `item_held` / `item_placed`, attempt record.
- [x] G3: `pick` live, one call per trial — nominal holds, out-of-envelope placements return the stage (g3bn, g3br).
      Read with hindsight (F59): that gate passed on a dock that landed 6 cm short, which hid two defects.
- [x] **`pick` works inside the agent loop (g4m)**: one call, two attempts on the same target, `item_held` verified
      independently (jaw 0.327 rad, 11.7 cm lift, 19.5 px of item motion against 315 px expected if left behind).
- [ ] **G4**: Mission B `covered` end to end. The agent composes it correctly and pick now works; what is left is
      carry → `place` (never run live) → stow → dock, from g4m's snapshot before step 9.
- [ ] `place` live, then the pick→place pair on one snapshot.

## Harness gaps found on the way (F58/F59) — infrastructure, not this mission

- [x] Reasoner and scene/grasp VLM both on DeepSeek's own endpoint (`deepseek-flash`); the shared gateway is gone.
- [x] `openral_ext/workspace/`: the robot's own reach (arm kinematics sampled from the live URDF) + footprint
      clearance decide where the rover parks; `dock_at_feature` settles each candidate with the robot's own IK.
      The `REACH` table in the scene generator is superseded — **still to delete, with `interaction.json`'s
      `robot.reach_m` and `d0_common`'s copy**, and the site's own work poses regenerated from the reach model.
- [x] A skill declares the volume its tool is about to be inside (`/space/manipulation_target`); the world model
      stops calling that measurement an obstacle. Without it no arm configuration was allowed at the ORU's handle.
- [ ] **Two features have no legal stand at all** (`depot_stand/slot_1`, the crate on it): the hull cannot clear the
      stand at any distance from which the arm reaches the handle. The depot needs items staged where this arm can
      take them, or a shallower stand.
- [ ] The PDU presses are approached from 0.20 m too far (Mission A's own record has a `move_tool` failing at 1.127 m
      and succeeding at 1.082 m). Re-dock them from the reach model and re-run Mission A as a regression.
- [ ] **Open and unexplained: the wrist view in `servo_*.jpg` is upside down** while `view_*.jpg` / `candidates_*.jpg`
      are uprighted (`upright(bgr, up_cam)`). Either the servo frames merely miss that call, or the camera-above-tool
      branch is being entered where it should not be. Settle it from the images before trusting another approach run.

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
