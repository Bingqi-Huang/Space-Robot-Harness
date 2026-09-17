# TODO

Order: `execution_plan` §21 (revised 2026-09-17) — the proposed method before the external baselines.
Current goal: all six steps of Ours, then a 1x-sim-time video with the agent's phases.

## Done (Phase A–D0, F1–F54)

- LunarBot stack on SRB (HAL, kernel, Nav2 + AMCL, MoveIt + site planning scene, gripper, sensors); Mission A/B
  `covered` end to end; common capability boundary; PLEXIL Mission A through it.
- Tasks grounded in literature: `docs/lunar_task_catalog.md` (existing 7 situations kept).

---

## Step 1–2: Ours runtime + Mission A `covered` — DONE (F53)

- [x] `space_runtime/` on OpenRAL `ReasonerCore`: facts log + reducer, context builder, guard, effect verification,
      report; palette from `contracts.yaml`; plan tool on `MissionState`.
- [x] oa1: verifier success, 43 steps (arm targets then truth stand-in).

## Step 3: harness parts — MOSTLY DONE

- [x] FDIR: kernel latched status → `estop` fact → guard denies effects.
- [x] Restart/switch live (rs1): DeepSeek killed at step 6, GLM-5.2 resumed on the same record correctly.
- [ ] Space context: only variables the chosen scenarios exercise (decide with the held-out set).

## Step 4: VLM observation — PARTLY DONE

- [x] `observe` / `locate_in_view`; gravity-upright frames; shared VLM = **Kimi-K3** (bench on real wrist frames:
      Kimi-K3 15/15, GLM-5.3-Flash 15/15, Qwen3.8-Flash 14/15, DeepSeek 12/15, Qwen3.8-Max 5/15). Reasoner stays
      DeepSeek-V4.1-Flash with thinking ON (user decision).
- [ ] Shelf occupancy / which object is the ORU on real frames (Mission B held-out needs). Not yet written to findings: Kimi-K3 bench.

## Step 5: vision replaces truth — DONE (F54)

- [x] No simulator truth in `openral_ext` / `space_runtime`; camera TF through mount bodies; wrist depth.
- [x] `approach_target` (VLM locate + D435i depth + servo + correction), `move_tool`, `locate_in_view`.
- [x] vc4 press PDU-2, vc10 grasp ORU handle (jaw 0.181, lifted) — vision only.
- [x] oa2: Mission A `covered` WITHOUT truth, verifier success, 33 steps, 30 min.
- [x] Speed: lidar 10 Hz + publish sensors only on new frames → sim 0.155× → 0.375×. Cameras 15 Hz. GPU PhysX crashes (dropped).

## Step 6: Mission B covered + held-out with Ours — IN PROGRESS

- [x] ob1–ob4 lessons (lost query response; TCP semantics; ORU knocked; wrist camera cannot frame the handle).
- [x] **Step-wise development**: full-state snapshot before every agent step (SRB `envs/snapshot`), stop at the first
      failure, restore to before the failed step (also into a fresh sim from disk), fix, rerun only that step.
- [x] Stack defects found on the way (all fixed, committed):
      servo completed on a nonzero twist → arm crept ~1.5 cm/s after every `move_ee_to_pose` (openral skill);
      verification band for MoveIt plans too tight (measured 0.9–3 cm execution error);
      AMCL re-seed after a restore lost (publisher not matched);
      a VLM gateway timeout crashed `approach_target` with no reason.
- [x] Interface gaps (generic, shared by every method): arm mount / working radius / ready posture in the contracts;
      a failed arm goal reports distance from the mount + MoveIt IK reachability + how far along the mount line it
      becomes reachable; docking warns that a raised arm sweeps; **`look_at_feature`** (camera aiming from a reachable
      viewing pose) — first use framed ORU + handle, both located.
- [x] Reasoner → DeepSeek-V4-Pro (offline replay); VLM → GLM-5.3-Flash (Kimi-K3 latency).
- [x] ob6_s19d: first vision grasp in the agent loop clamped the ORU neck (jaw 0.175); lift blocked by joint3 at its stop.
- [ ] ob6_s15e (running): look_at → approach → grasp → lift with joint3 constrained; then carry, place, return.
- [ ] Design (user direction): on-board CAD-model pose tracking (FoundationPose / ViSP) + PBVS + pre-grasp visual check;
      offline test on saved wrist frames first.
- [ ] Analysis for the paper: failures were mostly interface granularity/feedback, not reasoner IQ; offline replay of
      the bad decision points on stronger reasoners to confirm.
- [ ] Guard invariant candidate: no base motion while the arm is out past the hull (generic safety rule).
- [ ] Held-out: cover_obstruction, status_mismatch, destination_occupied, spare_swapped, route_block.

## Final

- [ ] Video run (SRB_VIDEO_SPEEDUP=1, `.times` sidecar) + `experiments/video/overlay.py` (check panel font size).
- [ ] Findings F55 (Kimi-K3 bench, ob1–ob5, step-wise snapshots); merge branches (research `feat/ours-space-runtime`,
      openral `feat/wrist-depth-relay`, SRB `feat/camera-budget-video-times`); handoff.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans take 15–77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).
- Movable objects are not in MoveIt's planning scene any more (truth removed) — suspect if the arm sweeps the ORU.

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2). Update them at every milestone.
- No pytest beyond upstream suites; pure-Python offline checks before one decisive live run.
- No defensive coding, no corner-case guards, no hash checks (AGENT.md §4).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Tasks must match documented future lunar mission needs (§6.3); choose from the catalog.
- **Never rerun a whole mission after a failure**: restore the snapshot before the failed step, fix, rerun that step.
- One simulation at a time (parallel sims ran at 0.05×).
- **Do not restrict LunarBot's manoeuvres to avoid slip**; fix estimation. **Carry payloads clamped** (check the jaw).
- **Never navigate on truth.** Truth is for measuring (and dev-only snapshot restore) only.
- Kill only your own run's processes by explicit PID; never `pkill -f` / `pgrep -f` loops.
- Never edit a script a live run is executing (runs execute frozen copies of `run_d0.sh`; checks load at start).
- Measure motion in sim time, never wall time — including check-script deadlines.
- Replies to the user: always Simplified Chinese, plain words, no code names, concise.
