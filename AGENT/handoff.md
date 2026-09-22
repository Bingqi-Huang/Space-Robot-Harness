# Handoff

Updated 2026-09-22 (p/integration merged). Read `AGENT/research_content.md` and `AGENT/execution_plan.md` first, then `AGENT/todo.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence, verification and hard
boundaries. No Mission-specific skill, hidden hint, numeric tuning or recovery graph. Simulator truth is for post-hoc diagnosis and
drawing only, never for a decision (user: "that is cheating").

## Heads

Single branch now: research `feat/experiment-campaign`, openral `feat/experiment-campaign`, SRB `feat/lunar-base-scene`.
`p/integration` (Session P's parallel offline track: PLEXIL Mission B, EUROPA, evaluation infra, operator mechanism,
evaluator violations) merged in today -- see "Merge note" below. Nothing pushed yet; ask before pushing.

## Where it stands -- Mission A and Mission B both reliable on the corrected arm; baseline/eval infrastructure now merged in

Ours: Mission A and Mission B both run from scratch on the corrected arm, evaluator `success: true`, video recorded
(`artifacts/runs/mission_a_success_20260922/`, `artifacts/runs/mission_b_success_20260922/`; F92-F100).
PLEXIL: Mission B covered plan on reusable library nodes, nominal path verified offline (F101); Mission A already ran
covered through the common boundary (F52). EUROPA: builds natively, generic host/bridge/replan verified offline on a
skeleton domain (F102); Mission B domain not yet written. Evaluation/operator/violations infrastructure exists but is
untested against the current manipulation contracts (F103). **None of this has been run together as one campaign.**
The next item in the user's stated order (`execution_plan` §21) is baselines / freeze / experiments, not yet started.

- `artifacts/runs/` was cleaned earlier this session: kept only what's cited as evidence in some doc, or read by
  another worktree's code; everything else is in `artifacts/runs/_debug_archive/` (117 GB, not deleted -- ask first).

### Robot-model fixes this session (F96-F100, `docs/research_findings.md`)

- **F96/F98 -- the robot model itself.** USD joint friction 0.1-0.4 (unitless, x transmitted force) stuck the arm; separately, the
  arm's drive gains are applied by PhysX per degree, so every joint was 57x softer than configured. Both found in a bare Isaac
  script with the base fixed (`experiments/robot_check/{arm_steps,carry_static}.py`), one minute per variant, not in a run.
- **F97 -- two joint-space defaults the soft arm had been hiding.** A planned IK solution can answer with the wrist roll a full
  turn from the arm's own (`nearest_equivalent` takes the nearest turn inside the stop's margin); the servo's pull toward the
  working posture was a step at the joint-rate limit, now a rate (0.05/s, ~20 s time constant).
- **F99/F100 -- `place`'s retreat and `over`.** Both are local, no-lookahead Cartesian tracking, so neither chooses a
  configuration with room to move on from; a joint can end up pinned at its own stop with nothing in the way. Fix is pure joint
  arithmetic: `joints_off_their_stops` walks a joint found within 0.3 rad of its stop back to exactly that clear, towards its
  own centre, then `plan_to` (which now also tells the planner about a carried item -- it never did). Retreat's distance
  widened to clear the evaluator's own "not held" check (0.30 m) in the worst case, not just the nominal one.

## Merge note (`p/integration` -> `feat/experiment-campaign`, 2026-09-22)

Submodule pins auto-resolved (Session P's openral/SRB commits were ancestors of the current ones -- no actual conflict).
Real conflicts, hand-resolved:

- `space_runtime/agent.py` -- combined both sides: `proposed()` (records the model's own reply text/reasoning next to
  every `tool_proposed` event, this session's F90-era work) with Session P's operator request/reply mechanism
  (`request_operator` now blocks the loop on `/space/operator/reply`, matched by `request_id`, instead of ending the
  run). `context.py`/`tools.py`/`report.py` auto-merged cleanly (non-overlapping hunks).
- `docs/research_findings.md` -- Session P's F79/F80/F81 renumbered to **F101/F102/F103** (this session had already
  used F79-F100 for the robot-model work); no other file cited the old numbers except `handoff.md`/`todo.md`, both
  rewritten here.
- `AGENT/handoff.md`, `AGENT/todo.md` -- rewritten (both were due an overwrite anyway).

**Not done as part of the merge, left as todo** (each needs either a live graph or a deliberate build step, not just a
merge): rebuild `ros/plexil_capability_adapter` (its `CapabilityAdapter.cc` changed -- new `RequestOperator` Command
and `LastFailureKind`/`LastFailureStage` Lookups); wire the evaluator-violations recorder into every method's launch
script; add a call-start timestamp to the capability-server log; optionally give `space_runtime/facts.py` a reducer
branch for `operator_answered` (`docs/operator_console.md` has the exact spec) if an operator answer ever needs to
reach `guard.py`'s `approval_required` check -- not needed for the mechanism to work, since `context.py` already
renders the exchange from the raw event log.

## Method rules earned the hard way this session

- **Audit before reacting.** Read the whole of a suspect skill for every way it could still be wrong before touching code,
  rather than patching one observed failure and re-running.
- **`check.log`'s bare `t` field is wall-clock seconds since the script started, not sim time** (`d0_common.log()`:
  `time.time() - T0`). `sim_t`/`sim_s` fields are the real simulation clock. `mission_video.py --to-sim` filters on genuine
  `sim_t`; get the cutoff from `PROGRESS`'s `sim_s`, not `RESULT`'s `t`.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's own goal -- the client process dies, the server keeps
  driving. Cancel it before any snapshot restore: `ros2 service call /navigate_to_pose/_action/cancel_goal
  action_msgs/srv/CancelGoal "{goal_info: {goal_id: {uuid: [0]*16}, stamp: {sec: 0, nanosec: 0}}}"`.
- Never open a run's bag while its recorder is alive (SQLite lock kills the recorder, truncating the bag). Read closed bags.
- Scripted capability chains (`experiments/launch/lunar_base_d0/scripted_chain_check.py` + `chain_*.json`, attach to a held
  graph, no model, no video) turn a 30-minute mission into a 10-minute test of one or two skills. `RESUME_SNAPSHOT=<snap>.pt`
  restores a jaws-open state; only jaws-open snapshots are valid restore points.
- A skill failure is not always a bug: `pick`'s `find` has no internal retry by design -- retrying a bad VLM read is the
  reasoner's job.

## Running it

Skills are import-cached in `runtime_node`; a skill change needs the runtime restarted (`D0_RESTART_RUNTIME_PID`), an SRB or
asset change needs the graph rebooted. Kill by run tag, never by name: `teardown_d0.sh <run dir>` with `D0_VIDEO=<mp4>` set to
finalize the video. Full pair: `experiments/launch/lunar_base_d0/launch_full_pair.sh <tagB|-> <tagA|->` (A on GPU 1, `-` skips
one side). Monitor `artifacts/runs/<tag>/ours/events.jsonl`; the evaluator's `RESULT` line is in `<tag>/check.log` (its own `t`
is wall time). Stop the recorder by PID, then `track_from_bag.py <run>/robot_motion <run>/track.json`, then
`mission_video.py <run>/mission_x.mp4 <run>/ours/events.jsonl <out> --times <mp4>.times --track <run>/track.json --to-sim
<PROGRESS's sim_s> --title ...`, then x264 (1280 wide, crf 29-38) to stay under 30 MiB.

## Rules

- One graph per GPU (A on 1, B on 0). All paths absolute. No `pgrep -f` / `pkill -f`.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills. A skill retries the same
  target, never moves the base. Keys in `AGENT/VLM_provider.md` never enter logs or output.
- Development resumes/scripted chains are not campaign results; never count them in paper metrics.
- Ask before merging/pushing a branch back; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies to the user in concise Simplified Chinese.
