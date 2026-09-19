# TODO

Order: `execution_plan` §21 — the proposed method before the external baselines.
Goal of this phase: Ours completes Mission A/B covered and the held-out situations, then a 1x-sim-time video.

**Sequence in force (user): finish Mission B → then `press` live → then Mission A.** Do not open the next one
while the previous one still has an unverified fix in it.

**Before anything: read `handoff.md`'s first section.** Iterating on a skill costs ~20 s (attach + resume), not
half an hour (new graph). Three graphs were booted before this was noticed.

## Now: Mission B end to end — the blocker is where the rover stands, not the servo

- [ ] **The blocker is now the stand, not the servo** (handoff "What g6e did"): far enough to see the 12 mm neck and the arm cannot reach it; close enough to reach it and no view measures it; at the near stand `READY` no longer fits. Nothing owns base position + viewing geometry + arm reach together. Same root cause as F62 §3, F61 §1, F63 §3.
- [x] **Three `pick` defects behind one error message** (F64), all fixed, offline-verified, committed:
      the goal orientation was a function of the tool's own pose (180° bang-bang limit cycle → `set_view_dir`);
      a 12 mm neck against sky gives no depth at a pixel matched at 1.00 (eight such frames ended the call);
      and my own regression — returning the predicted range as measured let the part walk down the line of sight
      (10.0 → 36.4 cm in 19 s). An unranged frame now says "still there, still matched" and nothing about where.
- [ ] **Verify the turn limit** (F63 §2) — still never exercised, because every run since g5m has failed in `pick`:
      the boundary derives Nav2's angular limit from the measured lever (α = 0.5 / lever). Look for
      `drive limits: carrying … lever_m` in `capability_server.log` and `item_still_held` after the dock at PDU-1.
- [x] The carry holds for a drive (F63 §1): `bring_in()` (lever 1.144 → 0.838 m) plus carrying drive limits; g5m
      completed the depot → PDU-1 leg with the payload verified held on arrival.
- [ ] `place` live: never yet reached with a payload in the jaws.
- [ ] Stow + dock at the far end: never reached either, and likely to hit the same wall as Mission A (below).
- [ ] Then G5 held-out: destination_occupied, spare_swapped, cover_obstruction, status_mismatch, route_block.

## Next: `press` live, then Mission A

- [x] `press(target)` built and wired (F62): locate → approach → press → retreat, `locate_point` for a target that
      is a patch on a surface, one contract line, `pressed` verified from the robot's own kinematics.
      `actions: ["push"]` — the controlled vocabulary has no `press` (F63 §3).
- [ ] **`press` has never pressed anything live.** ma4 photographed empty sky; `face_the_work_zone()` derives a
      looking posture instead of assuming one. Untested.
- [ ] **Mission A deadlocks before it presses** (F62 §3) and no part of it is wrong: the reach model stands the
      rover 0.905 m out; at 0.905 m the written-down `ready` posture has no collision-free path; raising the arm
      1.5 m out and driving in stops 7 cm short because Nav2 will not push a raised arm into a panel; from there
      the arm can neither rise nor stow. **Nothing owns the joint feasibility of arm posture and base position** —
      the reach model asks only about the arm, Nav2 only about the hull, and `READY`/`STOW` are constants from when
      the rover parked further back. Same disease as F61 §1, F63 §3 and F64 §2: **a written-down constant that does
      not know what is around it is a bug until proven otherwise.**

## Harness gaps — infrastructure, not this mission

- [x] Reasoner and VLM on DeepSeek's own endpoint; `openral_ext/workspace/` (the robot's reach decides the stand);
      `/space/manipulation_target`; `held_item` + continuous held-check; carrying drive limits at the boundary;
      **snapshot restore now verified, arm included** (F65).
- [ ] **Cache the views within a `pick` call.** Six views are re-taken on every attempt; one `pick` costs 15–40 min
      of wall time, and that cost is what pushes everyone (me included) toward "run it again" instead of reading
      the evidence. This is the single biggest speed-up left.
- [ ] Effects need the query path's error handling: an exception inside `_execute` leaves `failure_reason` empty
      and the agent gets a blank failure (F62 §2 — it cost five steps of re-wording against a `KeyError`).
- [ ] `item_cells` finds ~6 of the ~70 cells the grasped lid occupies, so most of what the robot is holding is
      still an obstacle to its own clearance check.
- [ ] `OURS_RESET=1` leaves AMCL without a pose (the reset teleports the rover, and the check re-seeds
      `/initialpose` after reading TF): the run dies with `no TF map <- chassis_base_link`. Seed first, then read.
      (Resume-by-step works; only the reset-to-start path has this bug.)
- [ ] The `REACH` table in the scene generator is superseded — still to delete, with `interaction.json`'s
      `robot.reach_m` and `d0_common`'s copy; regenerate the site's work poses from the reach model.
- [ ] **Two features have no legal stand at all** (`depot_stand/slot_1` and the crate on it): the hull cannot clear
      the stand at any distance from which the arm reaches the handle.
- [ ] The guard has never fired — every effect `routine`, `invariants: []`. H3 has no evidence yet.

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
- No pytest beyond upstream suites; **offline checks before one decisive live run** — every F64 fix was settled
  offline first, and that is the only reason three of them could be separated at all.
- No defensive coding, no corner-case guards, no hash checks, no ad-hoc patches (AGENT.md §4, F55 §5).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Model-facing tools are operations, not stages; no mechanical parameters in contracts (execution_plan §8.2).
- **Never rerun a whole mission after a failure**: restore the snapshot before the failed step, fix, rerun that
  step. Only a jaws-open snapshot is a valid resume point (F60 §1), and check `RESTORED_ARM` (F65).
- One simulation at a time. Never navigate on truth. Measure motion in sim time.
- **Kill only your own run's processes by explicit PID, and check afterwards that none survived** (F60 §8).
- Replies to the user: always Simplified Chinese, plain words, concise; design choices are the user's to make.
