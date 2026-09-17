# TODO

Order: `execution_plan` §21 (revised 2026-09-17) — the proposed method before the external baselines.
Current goal: all six steps of Ours, then a 1x-sim-time video with the agent's phases.

## Done (Phase A–D0, F1–F52)

- LunarBot stack on SRB (HAL, kernel, Nav2 + AMCL, MoveIt + site planning scene, gripper, sensors); Mission A/B
  `covered` end to end; common capability boundary; PLEXIL Mission A through it.
- Tasks grounded in literature: `docs/lunar_task_catalog.md` (existing 7 situations kept).

---

## Step 1–2: Ours runtime + Mission A `covered` — DONE (F53 §1–2)

- [x] `space_runtime/` on OpenRAL `ReasonerCore`: facts/evidence log + reducer, context builder, guard, effect
      verification, report; palette from `contracts.yaml`; plan tool on `MissionState`.
- [x] Run oa1: verifier success, 43 steps, DeepSeek-V4.1-Flash (arm targets then still the truth stand-in).

## Step 3: harness parts — IN PROGRESS

- [x] FDIR: safety kernel latched status → `estop` fact → guard denies effects.
- [x] Restart/switch mechanism: `--resume` replays the record; `OURS_RESTART_AT_STEP` / `OURS_RESTART_MODEL` in
      `ours_mission_check.py`; in-flight effect becomes an anomaly.
- [ ] Live restart/switch run (e.g. kill at step 12, resume on GLM-5.2) → Phase E exit 1.
- [ ] Space context: only variables the chosen scenarios exercise (none yet; decide with the held-out set).

## Step 4: VLM observation — PARTLY DONE

- [x] `observe` (DeepSeek-V4.1-Flash): lamp colours reliable from the wrist camera; gravity-upright frames.
- [ ] Check shelf occupancy / which object is the ORU on real frames (Mission B held-out needs).

## Step 5: relative perception replaces truth — IN PROGRESS (user decision: visual servoing)

- [x] Fiducials tried and removed. No simulator truth left in `openral_ext` / `space_runtime`.
- [x] Camera TF was frozen at spawn → bridge chains cameras through Link7 / rgbd_camera_frame + extrinsics
      (openral `feat/wrist-depth-relay`); wrist depth relayed (both cameras D435i).
- [x] `approach_target` (VLM locate + depth + servo + one correction), `move_tool`, `locate_in_view`.
- [ ] vc3: first RGB-D run — VLM gave the button once, a rail point the next call → two-answer agreement added.
- [ ] vc4: press PDU-2 + grasp ORU handle through vision only (views with the camera level: `grip`).

## Step 6: Mission B covered + the 7 situations with Ours

- [ ] Mission A `covered` again with vision contact (no truth); Mission B `covered`.
- [ ] Held-out: cover_obstruction, status_mismatch, destination_occupied, spare_swapped, route_block.
- [ ] Failures → mission-generic changes only (§13.1).

## Final

- [ ] Video run (SRB_VIDEO_SPEEDUP=1, `.times` sidecar) + `experiments/video/overlay.py`.
- [ ] Merge branches (research `feat/ours-space-runtime`, openral `feat/wrist-depth-relay`, SRB
      `feat/fiducials-video-times` → video times only); F53+ findings; handoff.

## Known stack issues (fix only when a run fails on them)

- Wedged rover with spinning wheels defeats AMCL; Nav2/MPPI cuts the charging station's corner.
- MoveIt plans take 15–77 s sim; an arm pushing a structure moves the rover (vc3: 7 cm).

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1). Clean debug/pilot artifacts.
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream suites; pure-Python offline checks before one decisive live run.
- No defensive coding, no corner-case guards (AGENT.md §4).
- Ours gets generic improvements only; never a situation-specific solution hint (§13.1).
- Tasks must match documented future lunar mission needs (§6.3); choose from the catalog.
- **Do not restrict LunarBot's manoeuvres to avoid slip**; fix estimation. **Carry payloads clamped** (check the jaw).
- **Never navigate on truth.** Truth is for measuring only.
- Kill only your own run's processes by explicit PID; never `pkill -f` / `pgrep -f` loops (a pattern matched the
  killing shell itself on 2026-09-17).
- Never edit a script a live run is executing (runs execute frozen copies of `run_d0.sh`; checks load at start).
- Measure motion in sim time, never wall time — including check-script deadlines.
