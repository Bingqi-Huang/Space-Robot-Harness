# Handoff

Updated 2026-09-22 (F92-F100). Read `AGENT/research_content.md` and `AGENT/execution_plan.md` first, then `AGENT/todo.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence, verification and hard
boundaries. No Mission-specific skill, hidden hint, numeric tuning or recovery graph. Simulator truth is for post-hoc diagnosis and
drawing only, never for a decision (user: "that is cheating").

## Heads

research `feat/manipulation-contracts`, openral `feat/manipulation-contracts`, SRB `feat/lunar-base-scene`. All committed.

## Where it stands

**Mission A (PDU-2 fault) has run end to end from scratch, twice, with evaluator success** (mc4, mc5; 1 press, faults cleared, PDU-2
reported, dock, arm stowed); mc5 has video + a complete bag (`artifacts/runs/mc5`). **Mission B has not**: `pick`, the carry, the dock
and the `place` calls all reach the shelf, but the ORU leaves the fingers when `place` starts (gc3, gt1c2). Cause found late on
2026-09-22 (F98): the arm's drive gains are applied by PhysX per degree, so every joint was 57x softer than configured (10.5 N m/rad, damping
ratio 0.05): it sagged under a 1 kg unit and rang at 1 Hz after any move. Fixed in SRB `lunarbot.py` (gains x 180/pi); bare test: kick
settles in 0.3 s, ORU held to 0.004 rad.

**On the corrected arm: Mission A succeeded (mc6, evaluator success, video sent).** Mission B's pick+place chain is now verified
too (gt2c8, scripted, no model, no video, `delivered: true`) after three more fixes found by auditing the whole `place` flow rather
than reacting to one more run (F99, F100): `over` had no escape from a joint pinned at its own stop -- the same local, no-lookahead
tracking `retreat` had (F99's fix, `joints_off_their_stops`, pure joint arithmetic, no IK), so the same dead end could equally turn
up there; `plan_to` never told the planner about a carried item, a latent gap the `over` fix would have made live; `retreat_m`/
`retreat_up_m` cleared the evaluator's own "not held" distance (0.30 m) only in the nominal case, not the worst case once each leg's
own tolerance is spent (0.30/0.25, not 0.25/0.20). A full Mission B run with video is in progress (`mc7b`).

## What was done since ga8, by kind (F92-F98 carry the detail)

- **Press v2**: the catalogue declares the button (`interface`: mushroom on a collar on a plate); `locate_disc` fits it from the wrist depth
  with no thresholds; the shared servo drives it; jaws close first; contact is evidence (past-face, off-axis, jaw), the boundary's
  independent `pressed` check judges. **Place v2**: `fit_wall` corrects the surveyed wall; over/lower/retreat are the shared servo;
  `lower` stops on a stall and records where. No skill has a handwritten loop.
- **One IK rule** for the boundary's stand feasibility and the skills: non-planned IK keeps the working branch or the seed; planned IK takes
  any collision-free solution ranked by `posture_cost`; every solution is taken at the wrist-roll turn nearest the arm
  (`nearest_equivalent`, F97). A dock is advice (`stand_advice`), not a veto.
- **Claims**: `held_item` reads twice (neutral context, then the item) with a confidence; place verification is independent of the
  skill's completion. Not built yet: `check_item_at`, `read_indicator`, the claim ledger (gc3 showed the gap: place "not
  placed", a gold box on the shelf, the model tried to pick it up again).
- **The robot model** (F96, F98): USD joint friction 0.1-0.4 (unitless, x transmitted force) stuck the arm; arm drive gains per degree.
  Both were found in a bare Isaac script (`experiments/robot_check/{arm_steps,carry_static}.py`), not in a run.
- **Posture pull is a rate** (0.05/s), no longer a step at the joint-rate limit (F97); place waits for stillness before `over`.

## Method rules earned the hard way

- Separate the robot model from the stack first: a bare Isaac script with the base fixed took one minute per variant and found what
  three days of runs did not. `Articulation.data.applied_torque` (the joint_states effort) is Isaac's replica with the configured gains,
  not PhysX's torque.
- Never open a run's bag while its recorder is alive (SQLite lock kills the recorder; both gc3 and mc4 bags were cut). Read closed bags.
- Scripted capability chains (`experiments/launch/lunar_base_d0/scripted_chain_check.py` + `chain_*.json`, attach to a held graph,
  no model) turn a 60-minute mission into a 15-minute test of one skill. `RESUME_SNAPSHOT` restores a jaws-open state only.
- Look at the pictures before the numbers; compute geometry offline; read your own code back before running it; subtract.

## Running it

Skills are import-cached in `runtime_node`; a skill change needs the runtime restarted (`D0_RESTART_RUNTIME_PID`), an SRB or asset
change needs the graph rebooted. Kill by run tag, never by name: `teardown_d0.sh <run dir>` with `D0_VIDEO=<mp4>` set to finalize the
video. Full pair: `experiments/launch/lunar_base_d0/launch_full_pair.sh <tagB|-> <tagA|->` (1080p video + bag; A on GPU 1).
Monitor `artifacts/runs/<tag>/ours/events.jsonl`; the evaluator's `RESULT` line is in `<tag>/check.log`. Stop the recorder by PID
(`recorder.pid` can be stale: find it with `ps`), then `track_from_bag.py <run>/robot_motion <run>/track.json`, then
`mission_video.py <run>/mission_x.mp4 <run>/ours/events.jsonl <out> --times <mp4>.times --track <run>/track.json --title ...`, then
x264 (1280 wide, crf 29) to stay under the 30 MiB send limit.

## Rules

- One graph per GPU (A on 1, B on 0). All paths absolute. No `pgrep -f` / `pkill -f`.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills. A skill retries the same target,
  never moves the base. Keys in `AGENT/VLM_provider.md` never enter logs or output.
- Development resumes/scripted chains are not campaign results; never count them in paper metrics.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies to the user in concise Simplified Chinese.
