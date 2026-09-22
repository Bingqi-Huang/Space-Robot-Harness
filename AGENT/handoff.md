# Handoff

Updated 2026-09-22 (F106, PLEXIL + EUROPA Mission A both live -- full success). Read `AGENT/research_content.md`
and `AGENT/execution_plan.md` first, then `AGENT/todo.md`. Goal: the Acta Astronautica paper. The model owns
mission strategy; a thin harness owns facts, evidence, verification and hard boundaries. Simulator truth is for
post-hoc diagnosis only, never a decision.

## Heads

On `feat/experiment-campaign` directly (this session's Mission A work is uncommitted on it, not a side branch --
ask before committing/pushing). openral/SRB unchanged on `feat/experiment-campaign`/`feat/lunar-base-scene`.
Nothing pushed.

## Where it stands

**All three methods now complete both Mission A and Mission B covered live on the corrected-arm stack, each with
video and its own overlay panel.** Mission B: Ours (F92-F100, `mission_b_success_20260922`), PLEXIL (F104,
`plexil_mission_b_success_20260922`), EUROPA->PLEXIL (F105, `europa_mission_b_success_20260922`). Mission A: Ours
(F92-F100, `mission_a_success_20260922`), PLEXIL (F106, `plexil_mission_a_success_20260922`), EUROPA->PLEXIL (F106,
`europa_mission_a_success_20260922`). **Still no campaign**: all six covered runs happened independently, never
side by side on one frozen instance set, and nothing is frozen yet.

- `artifacts/runs/` debug archive from earlier this session (117 GB) still sits at `_debug_archive/`, not deleted.

## F106 -- Mission A: a dropped PLEXIL recovery, and a Nav2 flake both baselines hit identically

Full account: `docs/research_findings.md` F106, `docs/baselines/plexil.md`, `docs/baselines/europa.md`. Both
baselines' Mission A were built and offline-verified before any live time, launched live in parallel (one graph per
GPU), and both hit the identical `navigate_to_pose` (return-to-dock) `STATUS_ABORTED` -- strong evidence of a
generic Nav2/environment flake, not either baseline's own bug. EUROPA needed no code change: `host.py`'s existing
replan-on-failure loop (F102) just retried and completed. PLEXIL did need a fix, but a restored one: rewriting
`MissionA_Covered.ple` onto Mission B's shared library (`DriveAndDock`/`StowAndReturn`, "nominal path only -- no
retry yet") silently dropped the `Try`-wrapped retry the *old*, pre-rewrite Mission A plan already had on this
exact class of leg. Restored at the library level (benefits Mission B too), verified offline (nominal regression
unchanged, a fail-injection script confirms the retry fires), then both re-run live to genuine success (PLEXIL
0.18 m/-9.9 deg dock error, EUROPA 0.23 m/-10.3 deg). PLEXIL's panel (`plexil_mission_video.py`,
`plexil_timeline_from_logs.py`) also needed its top-level node list generalized (`--top`, was hardcoded to Mission
B's five names) to draw Mission A's own three (`ToUnit`, `Press`, `Return`).

## Method rules earned the hard way this session

- **A manually-started `ros2 bag record` does not inherit `D0_RUN_TAG`** (only `run_d0.sh`'s own launched tree
  does), so `teardown_d0.sh`'s tagged-kill leaves it running, orphaned, writing into the old run's bag -- bit both
  the PLEXIL and EUROPA Mission A teardowns this session. Check `pgrep -fa "ros2 bag record"` after any teardown
  before trusting a run's bag is closed/isolated; kill the specific orphaned PID (identified by its exact command
  line matching the run path) with `SIGINT` so `ros2 bag` closes cleanly. If two launches on the same domain share
  one bag (teardown + immediate relaunch without a fresh recorder), `/clock` resets at the boundary -- segment a
  sim-time-keyed reader on a clock decrease and keep the last segment; wall-clock-keyed readers (`sim_clock.py`'s
  `wall_to_sim`) are unaffected since wall time stays monotone across the reset.
- **`teardown_d0.sh <log_dir>` needs an absolute path.** Its `tagged()` match is an exact string compare against
  `D0_RUN_TAG`, which `run_d0.sh` always sets absolute; a relative path silently tags zero processes (`TREE 0
  pids`) and looks like success while the graph keeps running.
- **Pass `D0_VIDEO=<the run's own mp4>` to `teardown_d0.sh`**, not just to `run_d0.sh` -- without it, the clean
  `-c copy` remux over the SIGINT-interrupted raw stream is skipped and the mp4 can end a few seconds short
  (ffmpeg recovers what it can from the truncated tail, but frames are lost).
- Read the source before guessing; reproduce minimally before calling something a bug (F104, F105 root causes both
  came from the upstream executive's own source / a `gdb` backtrace).
- `check.log`'s bare `t` field is wall-clock seconds since the script started, not sim time; `sim_t`/`sim_s` are.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's own goal -- cancel it explicitly first.
- Never open a run's bag while its recorder is alive. Read closed bags.

## Running it

PLEXIL: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_a_check.py D0_HOLD=1 D0_VIDEO=<mp4>
experiments/launch/lunar_base_d0/run_d0.sh <run dir>` (swap `_a_` for `_b_` for Mission B). Rebuild the adapter
after any `.cc` change: `PATH` without conda, `PLEXIL_HOME` set, source ROS Humble + `openral/install/setup.bash`,
`colcon build --merge-install --packages-select plexil_capability_adapter` from `ros/`. PLEXIL's overlay panel:
`track_from_bag.py` + `plexil_timeline_from_logs.py <run> <out.json> [top,node,names]` (ROS python, needs
`rosbag2_py`; the third arg defaults to Mission B's five names) then `plexil_mission_video.py ... --top
ToUnit,Press,Return` for Mission A (`openral/.venv`).

EUROPA offline: `baselines/europa/run_offline_mission_a.sh <run_dir> [--fail CAP:N[:far]]` (swap `_a_`/`_b_`
likewise); builds `planner/build/europa_plan` and `plexil/build/libHostLink.so` itself if missing. Live:
`D0_CAPABILITY_SERVER=1 D0_CHECK=d0_europa_mission_a_check.py D0_HOLD=1 D0_VIDEO=<mp4>
D0_SCENE=scenes/deploy/srb_lunar_base_mission_a.yaml run_d0.sh <run dir>`. EUROPA's overlay panel:
`track_from_bag.py` + `europa_timeline_from_logs.py` (reads `host.py`'s own `events.jsonl`) then
`europa_mission_video.py` (`openral/.venv`) -- GOALS (fixed) + PLAN (the solver's current derived activities,
replaced whole on every replan), no `--top`-equivalent needed since it reads goals/activities from the log
directly, not a hardcoded node list.

## Rules

- One graph per GPU (A on 1, B on 0 by convention, but check `D0_DOMAIN`/`D0_GPU` actually used -- this session
  ran A on both 0 and 1 simultaneously since both baselines needed Mission A at once). All paths absolute. No
  `pgrep -f` kills except after positively identifying one specific orphaned PID by its full command line.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development resumes/debugging runs are not campaign results; never count them in paper metrics.
- Ask before merging/pushing/committing; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies to the user in concise Simplified Chinese.
