# Handoff

State as of 2026-09-19 midday. Goal and plan: `AGENT/research_content.md`, `AGENT/execution_plan.md` (§21 order,
§8.2 granularity). Findings F1–F65 in `docs/research_findings.md` — **read F61–F65**. Tasks: `AGENT/todo.md`.
Design: **`docs/semantic_to_metric_manipulation_plan.md` (v4)**.

**The picture in one line:** Claude Code for a lunar robot. The model owns the mission; tools are whole operations
(`navigate`, `dock`, `pick`, `place`, `press`, `observe`), never stages; the harness runs them, keeps the record,
verifies effects automatically and holds the boundaries; OpenRAL is the borrowed tool runner / skill format.

## Read this first: how to iterate without wasting an hour

**Changing skill code does NOT need a new graph.** The rSkills run inside `capability_server`, which
`D0_RESTART_BOUNDARY=1` kills and restarts. A previous note said otherwise and three graphs were booted for
one-line `pick` changes (F65 §1). The loop that works, ~20 seconds:

1. Stop the old agent **by explicit PID** (`ps -eo pid,cmd | grep space_runtime.agent`), leave Isaac running.
   Never `pkill -f` — it matches the calling shell (F60 §8, and I did it again on 2026-09-19).
2. `D0_RESTART_BOUNDARY=1 OURS_MISSION=b OURS_RESUME_FROM=<earlier log> OURS_RESUME_BEFORE_STEP=<n> setsid nohup
   experiments/launch/lunar_base_d0/attach_d0.sh <graph log> <new log> &`
3. Check `RESTORED_ARM` in the new `check.log` before believing anything (F65 §3).

`<log>/snapshots/before_step_<n>.{pt,json}` exists for every step; `pick` in Mission B is **step 7**.

## Where the research stands

- Ours runs Mission A `covered` end to end (oa2); restart/model switch on the same record works (rs1).
- **The carry works for a drive and fails on the dock** (F63). `bring_in()` shortens the lever after the lift
  (1.144 → 0.838 m) and the boundary retunes Nav2 whenever the jaws hold something. g5m drove the whole depot →
  PDU-1 leg with `item_still_held` verified true on arrival — the first completed carry. The payload came out on
  the dock at the far end; the boundary now derives the angular limit from the lever (α = 0.5 / lever) so the
  payload sees the 0.5 m/s² it survived in a straight line. **That fix has still never been exercised** — every run
  since has failed earlier, in `pick`.
- **`pick` is the blocker, and it was three defects wearing one error message** (F64). All three said "lost sight of
  the chosen grasp 8 frames running":
  1. **Fixed, verified.** The goal orientation was recomputed every frame from the current camera position, and the
     camera is bolted to the tool — so the goal pose was a function of the tool's own pose, and `grasp_rotation`'s
     "point z away from the camera" made it a 180° bang-bang limit cycle. `set_view_dir()` fixes the approach
     direction at the view that chose the grasp. After it: **43 frames tracked, 0 missed**, roll within 0.1°.
  2. **Fixed.** The neck is 12 mm across with sky behind it, so the depth image has no value at a pixel the
     template matches at 1.00, and eight such frames in a row ended the call.
  3. **Fixed (my own regression from 2).** Returning the predicted range as if measured let the caller rebuild the
     part's point from it — the point walked down the line of sight, 10.0 cm → 36.4 cm in nineteen seconds. The
     part is a static rigid body: an unranged frame now says "still there, still matched" and nothing about where.
- **g6e is running as of this handoff**, resumed at step 7 with all three fixes. Its last servo frame reads
  `hit 0.87 d 0.317 left 9.3cm` with the neck square between the fingers — nearer than any approach has held
  before. **Read `artifacts/runs/g6e/` first: it either grasped or it did not, and that decides the next move.**
- `place` has never run with a payload in the jaws. Mission B has never reached stow/dock.
- **`press` is built and wired** (F62, F63 §3) and has **never pressed a button live**. ma4 photographed empty sky;
  `face_the_work_zone()` is the untested fix.
- **Mission A deadlocks before it presses** (F62 §3): the reach model parks at 0.905 m; there the written-down
  `ready` posture has no collision-free path; raising the arm further out and driving in stops 7 cm short because
  Nav2 will not push a raised arm into a panel; from there the arm can neither rise nor stow. **Nothing owns the
  joint feasibility of arm posture and base position.**

## If g6e failed, the next thing to look at

The remaining geometry, computed but never yet the cause of a failure: the wrist camera sits 0.12 m off the tool
axis and 0.22 m behind the TCP, vertical half-FOV 21.3°. The target's angle off the camera axis is
`atan(0.12 / (d + 0.22))` — 18.0° at 15 cm, 20.6° at 10 cm (画面最边缘), 23.2° at 6 cm (**out of frame**).
`blind_ok_m` is 0.06, exactly where it leaves the frame, so 6–10 cm is a stretch where the part is at the very edge
of the image and blind close-in is not yet allowed. Every failure so far happened at 13–15 cm for other reasons, so
this has never been demonstrated — do not change it without a run that fails there.

## User decisions (keep)

- Ours before the baselines; tasks from `docs/lunar_task_catalog.md`; freeze = git commits/tags, **no hash checks**.
- **Finish what is under test before opening the next thing** (F63 §4). Mission B → `press` live → Mission A.
- **Don't rerun from the top.** Restore the snapshot before the failed step (above). Only a jaws-open snapshot is a
  valid resume point — a restore cannot rebuild a grasp (F60 §1).
- Everything model-facing runs on DeepSeek's own endpoint (`deepseek-flash`, `https://api.deepseek.com`, key in
  `AGENT/VLM_provider.md` as `SPACE_REASONER_API_KEY` / `SPACE_LLM_API_KEY`). Latency is not a design constraint:
  the VLM may be given several images at once (F60 §5).
- **Method boundary (research_content §3.2):** baselines share robot, capabilities, perception services, raw
  evidence, low-level safety, evaluator — not Ours' mechanisms. `held_item` and the carrying drive limits are
  shared substrate; using them to keep authoritative facts honest is Ours'.
- **Granularity (plan v4):** model-facing tools are whole operations; stages and mechanical parameters live inside
  the skill; a skill retries only on the same target.
- Manipulation internals: no object models, no world-coordinate targets; candidates from the wrist RGB-D view, VLM
  set-of-mark choice over every view at once, KLT/depth tracking + IBVS, guarded close-in, image checks.
- Ad-hoc patches are not acceptable; fix causes or redesign. One simulation at a time. Never navigate on truth.
- Replies to the user: Simplified Chinese, plain words, concise; design choices are the user's to make.

## How to run

- Fresh graph (only when the scene itself must change):
  `D0_HOLD=1 D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml D0_CHECK=ours_mission_check.py
  D0_CAPABILITY_SERVER=1 OURS_MISSION=b [D0_TRACE_OBJECT=spare_oru] setsid nohup
  experiments/launch/lunar_base_d0/run_d0.sh <absolute log dir> > <log>/runner.out 2>&1 &`
  — **absolute paths only**: the runner executes a frozen copy of the script from the log dir.
- Iterate: the resume loop at the top of this file. Take a graph down:
  `experiments/launch/lunar_base_d0/teardown_d0.sh <absolute graph log>`.
- Read a `pick` failure **from its pictures**: `<log>/evidence/pick_*/servo_NN.jpg` carry `hit/MISS`, the match
  score, the range (`~` prefix = inferred, not measured), the roll and the distance left. The trace with the same
  numbers is in `capability_server.log` under `approach_track`, written only when the call ends.
- Record: `<log>/ours/{events.jsonl,report.md,agent.log}`; boundary `capability_server.log`; frames `evidence/`.
- Speed: sim ≈ 0.25–0.375x wall. A `pick` takes six views and their rolled shots — 15–40 min of wall time — and an
  attempt after a failure re-takes all of them. **Caching the views is the single biggest speed-up left.**

## Stack facts (don't rediscover)

- `/odom` wheel-inertial; AMCL on a lidar-surveyed map; Nav2 goals in `map`; SLAM off; truth only for evaluation.
- Capability boundary: `openral_ext/capability_server/{contracts.yaml,node.py}`. Effect verification and the guard
  live in `space_runtime/`.
- Arm RM-75 (`docs/lunar_bot_rm75_spec.md`); MoveIt plans end 0.9–3 cm from goal; 1 kg payload sags ~4.5 cm.
- Wrist camera 0.12 m off the tool axis, 0.22 m behind the TCP, D435i colour intrinsics 640x480 (fx = fy = 616).
  Nothing in the skills may hard-code them — `tool_in_view()` derives what it needs from TF.
- **Jaw bands defined once** in `openral_rskill._eye_in_hand` (0.13 empty / 0.6 open); the boundary imports them.
  The angle is never evidence for a grip — `held_item` (wrist image, vision model) is.
- **`actions:` in an rSkill manifest must come from `openral_core`'s controlled vocabulary** (`push`, not `press`):
  otherwise the local index skips the skill silently and the runner reports "network unreachable" (F63 §3).
- The ORU's lifting interface is a T-handle: **12 mm neck, 55 mm free height, 90×45×14 mm head** (F49 §2). Seen
  from above the neck projects to 8 mm and is correctly refused; the side view is what makes the grasp findable.

## Things that bit (keep)

- **Kill only explicit PIDs, then check none survived.** `pgrep -f`/`pkill -f` match the calling shell.
- `openral deploy sim` reaps openral processes → `OPENRAL_SKIP_ORPHAN_REAP=1` (run_d0.sh).
- **Fast-DDS leaks `/dev/shm` across graphs**; a dozen boots and the next graph cannot come up. With no ROS process
  running: `find /dev/shm -maxdepth 1 -name "fastrtps*" -delete`. `teardown_d0.sh` does not do it.
- A ROS service client called from inside another callback needs its own `callback_group` or it deadlocks.
- A publisher's first message is lost before discovery (AMCL `/initialpose`): wait for the match.
- `move_group` can wedge; every service call in the skills has a deadline.
- A snapshot restore cannot rebuild a grasp (F60 §1), and does not by itself put the arm back (F65 §2).

## Where things are

- Research repo `feat/g0-wrist-rgbd`, openral fork `feat/pick-place-rskills`, SRB `feat/lunar-base-scene`.
  **Everything through F65 is committed on both; both trees are clean.**
- Runs: `artifacts/runs/` — **g6e** (running, all three `pick` fixes, resumed at step 7), g6b/g6c (the servo-loop
  and depth evidence), g5m (the completed carry), ma2/ma4 (Mission A deadlock, `press` seeing only sky).
- **The g6c graph is still up** and g6e is attached to it. Resume from it, or tear it down with the absolute path.

## Open, unsettled

- `item_cells` finds ~6 of the ~70 cells the grasped lid occupies, so most of what the robot holds is still an
  obstacle to its own clearance check.
- Effects need the query path's error handling: an exception in `_execute` leaves `failure_reason` empty (F62 §2).
- The guard has never fired — every effect `routine`, `invariants: []`. H3 has no evidence yet.
- Whether the `shoulder` measurement filters candidates or is told to the VLM alongside them is the user's call.
