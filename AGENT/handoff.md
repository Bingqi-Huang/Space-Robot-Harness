# Handoff

Updated 2026-09-22 (F92-F100). Read `AGENT/research_content.md` and `AGENT/execution_plan.md` first, then `AGENT/todo.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence, verification and hard
boundaries. No Mission-specific skill, hidden hint, numeric tuning or recovery graph. Simulator truth is for post-hoc diagnosis and
drawing only, never for a decision (user: "that is cheating").

## Heads

research `feat/manipulation-contracts` (116 commits ahead of `main`), openral `feat/manipulation-contracts` (71 ahead of `master`),
SRB `feat/lunar-base-scene` (44 ahead of `main`). All committed, nothing merged back yet -- ask before merging; each branch still
has the rest of `execution_plan` §21 (baselines, the freeze, the campaign) queued on it.

## Where it stands -- Mission A and Mission B both reliable on the corrected arm, full recorded runs, both succeeded

This closes the sequence the user set (`todo.md`: Mission B reliable, Mission A, then baselines/freeze/experiments). Next up is
that last item, not yet scoped.

- **Mission A**: `mc6`, from scratch, video sent (PDU-2 fault found, pressed, verified, dock, arm stowed, evaluator `success: true`).
- **Mission B**: `mc7b`, from scratch, video sent (ORU delivered to PDU-1's shelf, dock, arm stowed, evaluator `success: true`).

Getting there fixed real bugs, found by auditing rather than by reacting to one more failed run (the user's explicit correction
mid-session, after two rejected patches):

- **F96/F98 -- the robot model itself.** USD joint friction 0.1-0.4 (unitless, x transmitted force) stuck the arm; separately, the
  arm's drive gains are applied by PhysX per degree, so every joint was 57x softer than configured. Both found in a bare Isaac
  script with the base fixed (`experiments/robot_check/{arm_steps,carry_static}.py`), one minute per variant, not in a run.
- **F97 -- two joint-space defaults the soft arm had been hiding.** A planned IK solution can answer with the wrist roll a full
  turn from the arm's own (`nearest_equivalent` takes the nearest turn inside the stop's margin); the servo's pull toward the
  working posture was a step at the joint-rate limit, now a rate (0.05/s, ~20 s time constant).
- **F99/F100 -- `place`'s retreat and `over`.** Both are local, no-lookahead Cartesian tracking with no look-ahead, so neither
  chooses a configuration with room to move on from; a joint can end up pinned at its own stop with nothing in the way. The
  accepted fix (after two rejected ones -- see F99/F100 in `docs/research_findings.md` for what was wrong with "tolerate the
  stall" and "re-solve IK for the same pose") is pure joint arithmetic: `joints_off_their_stops` walks a joint found within 0.3 rad
  of its stop (`posture_cost`'s own margin) back to exactly that clear, towards its own centre, nothing else touched, then
  `plan_to` (which now also tells the planner about a carried item -- it never did). Retreat's distance was widened to clear the
  evaluator's own "not held" check (0.30 m) in the worst case, not just the nominal one (0.30/0.25 m, not 0.25/0.20).

## Method rules earned the hard way this session

- **Audit before reacting.** Told explicitly to stop patching one failure at a time and instead read the whole of `place` for
  every way it could still be wrong: found two more real gaps (`over` had no escape either; `plan_to` never saw a carried item)
  without running anything.
- **`check.log`'s bare `t` field is wall-clock seconds since the script started, not sim time** (`d0_common.log()`:
  `time.time() - T0`). `sim_t`/`sim_s` fields are the real simulation clock. Conflating them cost a wrong "the mission is 46
  minutes of sim time" explanation to the user; the actual sim-time content of a mission is much shorter (Mission A ~8 min,
  Mission B ~8.5 min) -- the rest of a raw composed video is wall-clock padding (rendering overhead, or the graph left idle).
  `mission_video.py --to-sim` filters on genuine `sim_t`; get the cutoff from `PROGRESS`'s `sim_s`, not `RESULT`'s `t`.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's own goal -- the client process dies, the server keeps
  driving. Cancel it before any snapshot restore or the robot just fights the restore: `ros2 service call
  /navigate_to_pose/_action/cancel_goal action_msgs/srv/CancelGoal "{goal_info: {goal_id: {uuid: [0]*16}, stamp: {sec: 0,
  nanosec: 0}}}"` (all-zero goal_id + zero stamp cancels every goal on that server).
- Never open a run's bag while its recorder is alive (SQLite lock kills the recorder, truncating the bag). Read closed bags.
- Scripted capability chains (`experiments/launch/lunar_base_d0/scripted_chain_check.py` + `chain_*.json`, attach to a held graph,
  no model, no video) turn a 30-minute mission into a 10-minute test of one or two skills. `RESUME_SNAPSHOT=<snap>.pt` restores a
  jaws-open state (shared with `ours_mission_check.py` via `d0_common.put_scene_back`, no longer duplicated between them).
- A skill failure is not always a bug: `pick`'s `find` has no internal retry by design ("the model answers within the deadline or
  the stage returns with what it has") -- retrying a bad VLM read is the reasoner's job. The scripted chains have no reasoner, so
  they just get relaunched once, same as the real loop would retry.
- Don't let a script depend on an old run directory as if it were committed infra (`record_qos.yaml` was being copied out of a
  15 GB scratch run, `gb2`; now lives at `experiments/launch/lunar_base_d0/record_qos.yaml`).

## Running it

Skills are import-cached in `runtime_node`; a skill change needs the runtime restarted (`D0_RESTART_RUNTIME_PID`), an SRB or asset
change needs the graph rebooted. Kill by run tag, never by name: `teardown_d0.sh <run dir>` with `D0_VIDEO=<mp4>` set to finalize the
video. Full pair: `experiments/launch/lunar_base_d0/launch_full_pair.sh <tagB|-> <tagA|->` (1080p video + bag; A on GPU 1, `-` skips
one side). Monitor `artifacts/runs/<tag>/ours/events.jsonl`; the evaluator's `RESULT` line is in `<tag>/check.log` (its own `t` is
wall time -- see above). Stop the recorder by PID (`recorder.pid` can be stale: find it with `ps`), then `track_from_bag.py
<run>/robot_motion <run>/track.json`, then `mission_video.py <run>/mission_x.mp4 <run>/ours/events.jsonl <out> --times <mp4>.times
--track <run>/track.json --to-sim <from PROGRESS's sim_s, not RESULT's t> --title ...`, then x264 (1280 wide, crf 29-38 depending
on length) to stay under the 30 MiB send limit.

## Rules

- One graph per GPU (A on 1, B on 0). All paths absolute. No `pgrep -f` / `pkill -f`.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills. A skill retries the same target,
  never moves the base. Keys in `AGENT/VLM_provider.md` never enter logs or output.
- Development resumes/scripted chains are not campaign results; never count them in paper metrics.
- Ask before merging a feature branch back to its main/master; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies to the user in concise Simplified Chinese.
