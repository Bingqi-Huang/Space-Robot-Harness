# TODO

Order: `execution_plan` §21 (revised 2026-09-17) — the proposed method before the external baselines.
Goal of this phase: Ours completes Mission A/B covered and the held-out situations, then a 1x-sim-time video.

**Sequence in force (user, F63 §4): finish Mission B → then `press` live → then Mission A as a regression.**
Do not open the next one while the previous one has an unverified fix in it.

## Done

- LunarBot stack on SRB; common capability boundary; PLEXIL Mission A through it (F51–F52).
- Ours runtime (facts, context, guard, verification, trace, restart/switch) and Mission A `covered` with vision-only
  contact (F53–F54). Tasks grounded in `docs/lunar_task_catalog.md`.
- Manipulation design **v4** (`docs/semantic_to_metric_manipulation_plan.md`): `pick` / `place` / `press` are single
  skills; the model composes operations, never stages (F56).
- G0–G2 offline; `pick`/`place` as procedural rSkills; G3 live; `pick` inside the agent loop (g4m).
- **Scheduling and verification defects cleared (F60)**: the jaw band defined once and read from the picture, not the
  angle; `select` judges every view at once; a blocked view / an unreachable candidate / a failed retreat are local,
  not fatal; `item_held` re-checked after every call; `held_item` query; `OURS_RESET=1`.
- **Where to look is computed, not written down (F61)**: the item is found once on the overview, every working view
  aims at its own top, the viewing direction includes the horizontal. `pick` then took the 12 mm neck four times
  running (g5h, g5i, g5k, g5m).

## Now: G4 — Mission B end to end

- [ ] **Verify the turn limit** (F63 §2) — the one unexercised fix: the boundary derives Nav2's angular limit from
      the measured lever (α = 0.5 / lever) so a turn puts the same 0.5 m/s² on the payload that the straight leg
      survived. **g6a is running for this.** Look for `drive limits: carrying … lever_m` in `capability_server.log`
      and `item_still_held` after the dock at PDU-1.
- [x] **The carry holds for a drive** (F63 §1): `bring_in()` (lever 1.144 → 0.838 m) plus carrying drive limits;
      g5m completed the depot → PDU-1 leg with the payload verified held on arrival.
- [ ] **`pick` is not yet reliable**: g5p failed twice at `approach` — "lost sight of the chosen grasp 8 frames
      running while still 6 cm away" and "the close-in stopped 14.6 cm from the grasp". Both are the tracker or the
      guard giving up near the target, where the item fills the frame. Read `g5p/evidence/pick_*/servo_*.jpg`.
- [ ] `place` live: never yet reached with a payload in the jaws. Then stow + dock, and Mission B is end to end.
- [ ] Then G5 held-out: destination_occupied, spare_swapped, cover_obstruction, status_mismatch, route_block.

## Next: `press` live, then Mission A

- [x] `press(target)` built and wired (F62): procedural rSkill (locate → approach → press → retreat),
      `locate_point` for a target that is a patch on a surface, one contract line, `pressed` verified from the
      robot's own kinematics. `actions: ["push"]` — the controlled vocabulary has no `press` (F63 §3).
- [ ] **`press` has never pressed anything live.** ma4 photographed empty sky; `face_the_work_zone()` derives a
      looking posture from where a dock puts the work instead of assuming one. Untested.
- [ ] **Mission A deadlocks before it presses** (F62 §3) and no part of it is wrong: the reach model stands the rover
      0.905 m out; at 0.905 m the written-down `ready` posture has no collision-free path; raising the arm 1.5 m out
      and driving in stops 7 cm short because Nav2 will not push a raised arm into a panel; from there the arm can
      neither rise nor stow. **Nothing owns the joint feasibility of arm posture and base position** — the reach
      model asks only about the arm, Nav2 only about the hull, and `READY`/`STOW` are constants from when the rover
      parked further back. Same disease as F61 §1 and F63 §3: a posture constant is a bug until proven otherwise.

## Harness gaps found on the way — infrastructure, not this mission

- [x] Reasoner and VLM on DeepSeek's own endpoint; `openral_ext/workspace/` (the robot's own reach decides the
      stand); `/space/manipulation_target` (what a skill works on is not an obstacle); `held_item` + continuous
      held-check; carrying drive limits at the boundary (shared substrate).
- [ ] Effects need the query path's error handling: an exception inside `_execute` leaves `failure_reason` empty and
      the agent gets a blank failure (F62 §2 — it cost five steps of re-wording against a `KeyError`).
- [ ] `item_cells` finds ~6 of the ~70 cells the grasped lid occupies, so most of the item the robot is holding is
      still an obstacle to its own clearance check.
- [ ] Views are re-taken on every attempt, and there are six of them: one `pick` costs 15–40 min of wall time.
      Cache the views per call and re-ask only the choice.
- [ ] `OURS_RESET=1` leaves AMCL without a pose (the reset teleports the rover, and the check re-seeds
      `/initialpose` after reading TF): the run dies with `no TF map <- chassis_base_link`. Seed first, then read.
- [ ] The `REACH` table in the scene generator is superseded — **still to delete**, with `interaction.json`'s
      `robot.reach_m` and `d0_common`'s copy; regenerate the site's work poses from the reach model.
- [ ] **Two features have no legal stand at all** (`depot_stand/slot_1`, the crate on it): the hull cannot clear the
      stand at any distance from which the arm reaches the handle.
- [ ] The guard has never fired — every effect is `routine`, `invariants: []`. H3 has no evidence yet.

## Then

- [ ] Space context variables only if the chosen scenarios exercise them.
- [ ] 1x video run + `experiments/video/overlay.py`.
- [ ] Baselines (§21 items 5–6: PLEXIL Mission B, EUROPA→PLEXIL), scenario manifests and freeze, Experiment I,
      Ours-internal ablations (research_content §5.7), Experiment II.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans 15–77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).
- Movable objects are not in MoveIt's planning scene (a skill declares its own working volume instead).

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each; update at every milestone.
- No pytest beyond upstream suites; offline checks before one decisive live run.
- No defensive coding, no corner-case guards, no hash checks, no ad-hoc patches (AGENT.md §4, F55 §5).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Model-facing tools are operations, not stages; no mechanical parameters in contracts (execution_plan §8.2).
- Never rerun a whole mission after a failure: restore the snapshot before the failed step, fix, rerun that step.
  **Only a jaws-open snapshot is a valid resume point** — a restore cannot rebuild a grasp (F60 §1).
- One simulation at a time. Never navigate on truth. Measure motion in sim time.
- Kill only your own run's processes by explicit PID — **and check afterwards that none survived** (F60 §8).
- Replies to the user: always Simplified Chinese, plain words, concise; design choices are the user's to make.
