# Handoff

State as of 2026-09-19 morning. Research goal and plan: `AGENT/research_content.md`, `AGENT/execution_plan.md`
(§21 order: the proposed method before the baselines; §8.2 granularity rule). Findings F1–F63 in
`docs/research_findings.md` — **read F60–F63**. Tasks: `AGENT/todo.md`. Design:
**`docs/semantic_to_metric_manipulation_plan.md` (v4)**.

**The picture in one line:** Claude Code for a lunar robot. The model owns the mission (what to observe, where to go,
what to pick, what to try after a failure); tools are whole operations (`navigate`, `dock`, `pick`, `place`, `press`,
`observe`), never stages; the harness runs them, keeps the record, verifies effects automatically and holds the
boundaries; OpenRAL is the borrowed tool runner / skill format.

## Where the research stands

- Ours (`space_runtime/`, on OpenRAL `ReasonerCore`) runs Mission A `covered` end to end (oa2). Restart/model switch
  on the same record works (rs1).
- **`pick` works.** Four times inside full Mission B runs (g5h, g5i, g5k, g5m), each across the bail's 12 mm neck:
  jaw 0.171–0.184 rad, lifts 6–13 cm, verified independently. What had to change was **where the camera looks**
  (F61): the overview is a place to look *from*, not a written-down posture; the item is found once with
  `find_regions`/`locate_region`; every working view aims at the item's own top; the viewing direction includes the
  horizontal; and a blocked view, an unreachable candidate or a failed retreat is one fewer of something rather than
  a failed call. It is not yet reliable — g5p failed twice at `approach` (lost sight of the grasp at 6 cm; close-in
  stalled at 14.6 cm).
- **The carry works for a drive and fails on the dock** (F63 §1–2). Two things fixed it, both about the moment on a
  12 mm neck, not about speed: `bring_in()` shortens the lever after the lift (1.144 → 0.838 m), and the boundary
  retunes Nav2's smoother whenever the jaws hold something (0.25 m/s, 0.5 m/s²). g5m drove the whole depot → PDU-1
  leg with `item_still_held` verified true on arrival — the first completed carry in this project. The payload came
  out on the **dock** at the far end, where the rover turns; the boundary now derives the angular limit from the
  actual lever (α = 0.5 / lever) so the payload sees the same 0.5 m/s² it survived in a straight line.
  **That fix has never been exercised — g6a is running for exactly this.**
- `place` has never run with a payload in the jaws. Baselines: PLEXIL runs Mission A through the common boundary
  (F52); PLEXIL Mission B, EUROPA→PLEXIL, Experiments I/II not started.
- **`press` is built and wired** (F62, F63 §3): a procedural rSkill of the plan v4 shape (locate → approach → press →
  retreat), `locate_point` for a target that is a patch on a surface, one contract line, `pressed` verified by the
  harness from the arm's own kinematics. It has **never pressed a button live**: ma4 showed it looking at empty sky,
  and `face_the_work_zone()` (derive a looking posture instead of assuming one) is the untested fix.
- **Mission A deadlocks before it presses anything**, and every part of the deadlock is correct on its own (F62 §3):
  the reach model parks the rover 0.905 m out so the arm can work; there the written-down `ready` posture has no
  collision-free path; raising the arm 1.5 m out and driving in stops 7 cm short, because Nav2 will not push a raised
  arm into a panel; and from there the arm can neither rise nor stow. **Nothing owns the joint feasibility of arm
  posture and base position.**

## User decisions (keep)

- Ours before the baselines; tasks from `docs/lunar_task_catalog.md`; freeze = git commits/tags, **no hash checks**.
- **Finish what is under test before opening the next thing** (F63 §4). Mission B → then `press` → then Mission A.
- **Everything model-facing runs on DeepSeek's own endpoint** (`deepseek-flash`, `https://api.deepseek.com`, the
  second key in `AGENT/VLM_provider.md`, exported as `SPACE_REASONER_API_KEY` and `SPACE_LLM_API_KEY`). The shared
  gateway is gone (F58). **Its latency is no longer a design constraint**: a marked view is read in 1–6 s, so the VLM
  may be given several images at once — which is what fixed `select` (F60 §5).
- **Method boundary (research_content §3.2):** baselines share robot, capabilities, perception sources and services,
  raw evidence, low-level safety and the external evaluator — not Ours' mechanisms. `held_item` and the carrying
  drive limits are shared substrate; using them to keep authoritative facts honest is Ours'.
- **Granularity (plan v4):** model-facing tools are whole operations with mission-level arguments; stages and
  mechanical parameters live inside the skill. A skill retries only on the same target.
- **Manipulation internals:** no object models, no world-coordinate targets; candidates from the wrist RGB-D view,
  VLM set-of-mark choice over *every* view at once, KLT/depth tracking + IBVS, guarded close-in, image checks.
- Ad-hoc patches are not acceptable; fix causes or redesign.
- **Step-wise development:** restore the snapshot before the failed step, fix, rerun that step. One simulation at a
  time. **Only a jaws-open snapshot is a valid resume point** (F60 §1).
- Replies to the user: Simplified Chinese, plain words, concise; ask before deciding design questions for the user.

## How to run

- Mission dev run, graph held afterwards (from the repo root):
  `D0_HOLD=1 [OURS_STOP_ON_FAILURE=1] D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml D0_CHECK=ours_mission_check.py
  D0_CAPABILITY_SERVER=1 OURS_MISSION=b setsid nohup experiments/launch/lunar_base_d0/run_d0.sh <log> > <log>/runner.out 2>&1 &`
  (`OURS_MISSION=a` for Mission A; `D0_TRACE_OBJECT=spare_oru` logs the object). **Leave `OURS_STOP_ON_FAILURE` out
  when the point is to watch the agent recover.**
- Another check on the held graph, without booting Isaac again:
  `[D0_RESTART_BOUNDARY=1] OURS_MISSION=b [OURS_RESUME_FROM=<log> OURS_RESUME_BEFORE_STEP=<n> | OURS_RESET=1]
  setsid nohup experiments/launch/lunar_base_d0/attach_d0.sh <graph log> <new log> &`
  — `OURS_RESET=1` puts the scene back to the graph's own start (`<graph log>/snapshots/initial.pt`, saved at boot).
  **`D0_RESTART_BOUNDARY=1` reloads changed skill code too** — the rSkills run inside `capability_server`, which
  that flag kills and restarts. **Never boot a new graph to test a skill change**: attach with
  `OURS_RESUME_FROM=<earlier log> OURS_RESUME_BEFORE_STEP=<n>` and the scene goes back to just before that step,
  rover parked where it was. Booting Isaac and driving to the depot again costs ~30 min a turn and buys nothing
  (g6a/g6b/g6c each paid it for a `pick` change).
- Take a held graph down: `experiments/launch/lunar_base_d0/teardown_d0.sh <graph log>` — **the absolute path**.
- Read a pick failure from its pictures, not its numbers: `<log>/evidence/pick_*/` has the overview, each view with
  its numbered candidates, `servo_NN.jpg` per approach frame, `stall_*.jpg` where an arm stopped short, and
  `hold_before/after.png`.
- Record: `<log>/ours/{events.jsonl,report.md,agent.log}`; boundary `capability_server.log`; frames `evidence/`.
- Offline reasoner comparison on recorded decision points: `experiments/reasoner_replay/replay.py`.
- Speed: sim ≈ 0.25–0.375x wall. A `pick` takes six views and their rolled shots — 15–40 min of wall time — and an
  attempt after a failure re-takes all of them (cache them — `todo.md`).

## Stack facts (don't rediscover)

- `/odom` wheel-inertial; AMCL on a lidar-surveyed map; Nav2 goals in `map`; SLAM off; truth only for evaluation
  (and dev-only snapshot restore). Cameras D435i front + wrist, 15 Hz, work lights.
- Capability boundary: `openral_ext/capability_server/{contracts.yaml,node.py}`. Effect verification and the guard
  live in `space_runtime/` (Ours' harness).
- Arm: RM-75 (`docs/lunar_bot_rm75_spec.md`); MoveIt plans end 0.9–3 cm from goal; 1 kg payload sags ~4.5 cm.
- Wrist camera: 0.12 m off the tool axis, 0.22 m behind the TCP, aimed 0.15 m beyond it, D435i colour intrinsics at
  640x480 (fx = fy = 616). Nothing in the skills may hard-code them: `tool_in_view()` derives what it needs from TF.
- **Jaw bands are defined once**, in `openral_rskill._eye_in_hand` (0.13 empty / 0.6 open); the boundary imports them.
  The angle is never the evidence for a grip — `held_item` (wrist image, vision model) is.
- **`actions:` in an rSkill manifest must come from `openral_core`'s controlled vocabulary** (`push`, not `press`) —
  otherwise the local index skips the skill silently and the runner reports "network unreachable" (F63 §3).
- OpenRAL rSkill manifests: `openral/rskills/*/rskill.yaml`; entrypoints `openral/python/rskill/src/openral_rskill/`.

## Things that bit (keep)

- `openral deploy sim` reaps openral processes → `OPENRAL_SKIP_ORPHAN_REAP=1` (run_d0.sh).
- Runs execute a frozen copy of `run_d0.sh`; checks load at start — never edit a script a live run executes.
- **Kill only explicit PIDs, then check none survived.** `pgrep -f` matches the calling shell; one stale agent of a
  stopped run drove the robot alongside the next run's agent for twenty minutes (F60 §8).
- Stale agents ignore SIGTERM → kill -9; check the ROS domain is clean before a run.
- **Fast-DDS leaks shared memory across graphs.** A dozen boots left 528 `fastrtps*` files in `/dev/shm` and the next
  graph could not come up (`Failed init_port`, then Nav2's `smoother_server` timing out `configure` after 120 s).
  `teardown_d0.sh` does not clear them. With no ROS process running:
  `find /dev/shm -maxdepth 1 -name "fastrtps*" -delete`.
- A ROS service client called from inside another callback needs its own `callback_group` or it deadlocks — that is
  what made the first carrying-limits call hang.
- A publisher's first message is lost before discovery (AMCL `/initialpose`): wait for the match.
- `move_group` can wedge; every service call in the skills has a deadline.
- A snapshot restore cannot rebuild a grasp: an item restored in the jaws drops out (F60 §1).

## Where things are

- Research repo working branch `feat/g0-wrist-rgbd`; openral fork `feat/pick-place-rskills`; SRB
  `feat/lunar-base-scene`. Everything through F63 is **committed** on both.
- Runs (not in git): `artifacts/runs/` — **g5m is the one to read** (the completed carry), g5p for the two `pick`
  approach failures, ma2/ma4 for the Mission A deadlock and the press that saw only sky. g4n/g4o are void.

## Open, unsettled (read before the next run)

- `item_cells` (the flood fill that excludes the grasped item's own surface from the clearance guard) finds ~6 of
  the ~70 cells the lid actually occupies. The guard has not blocked a good grasp because of it yet.
- The guard has never fired: every effect is `routine` and `invariants: []` — an evidence gap for H3.
- Whether the `shoulder` measurement filters candidates or is told to the VLM alongside them is the user's call.
