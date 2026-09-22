# Handoff

Updated 2026-09-22 (F105, EUROPA Mission B offline). Read `AGENT/research_content.md` and `AGENT/execution_plan.md`
first, then `AGENT/todo.md`. Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns
facts, evidence, verification and hard boundaries. Simulator truth is for post-hoc diagnosis only, never a decision.

## Heads

research `feat/europa-mission-b` (off `feat/experiment-campaign`, not merged back -- ask first), openral/SRB
unchanged on `feat/experiment-campaign`/`feat/lunar-base-scene`. Nothing pushed.

## Where it stands

Ours: Mission A and Mission B both run from scratch on the corrected arm, evaluator `success: true`, video recorded
(F92-F100). PLEXIL: Mission B covered runs end to end live, video recorded (F104,
`artifacts/runs/plexil_mission_b_success_20260922`) -- the first baseline to complete a full mission on the current
stack. **EUROPA: Mission B domain built and verified end to end offline (F105)** -- given only the mission's own
outcomes as goals (item delivered, arm stowed, base at dock), the solver derives the full 9-step plan itself
(matching PLEXIL's hand-sequenced one) through `sim_boundary.py`'s stand-in boundary; not yet run live. Mission A
PLEXIL already ran covered once (F52, older stack) but its plan still uses stage-level tools instead of the shared
`press` capability, which has never been tested live at all. **Still no campaign**: the three methods have never run
the identical instance side by side, and nothing is frozen.

- `artifacts/runs/` debug archive from earlier this session (117 GB) still sits at `_debug_archive/`, not deleted.

## F105 -- EUROPA Mission B: one domain bug, two EUROPA/host.py bugs, all found offline

Full account: `docs/research_findings.md` F105, `docs/baselines/europa.md`. `domain/mission-b-model.nddl` adds
posture/jaws/item timelines to the existing base-only skeleton (F102). Three bugs, each confirmed by a minimal
reproduction before being called a bug:
1. **Domain**: `pick`/`place`/`stow` used `met_by` for preconditions on a timeline the action itself does not
   change (base position, posture) -- the solver satisfied it with a token never connected to any real fact,
   producing a `place` with no preceding `pick`. Fixed with `contained_by`, matching nasa/europa's own Rover
   example's identical cross-timeline pattern.
2. **EUROPA itself**: `europa_plan` segfaults inside `TemporalNetwork::cleanupTEQ` (confirmed with `gdb -batch -ex
   run -ex bt`) once two `precedes`-chained goals are given to one `solve()` call; any single goal alone never
   crashed. Worked around in `host.py`: each solve now gets only the next unmet goal (`goals[:1]`), not the chain
   -- the sequencing semantics are unchanged, only which layer holds the chain.
3. **`host.py`**: a `met_by` condition slave's token owner comes back empty from EUROPA's own API, which
   `post_state()` was keying facts by -- corrupting the *next* solve's NDDL (`fact(.Stowed ...)`, invalid syntax,
   read as "no plan" rather than a bug). Fixed: skip slaves with no owner.

`run_offline.sh` (skeleton) also needed `openral/install/setup.bash` sourced -- missing since `host.py`'s later
operator-console `PromptStamped` import, unrelated to Mission B; caught by re-running the existing regression
before trusting a new result. `run_offline_mission_b.sh` is the Mission B equivalent; verified nominal and with an
injected `pick` failure (replans, retries, completes).

## Method rules earned the hard way this session

- **Read the source before guessing; reproduce minimally before calling something a bug.** Both PLEXIL's (F104)
  and EUROPA's (F105) root causes came from reading the upstream executive's own source and/or a `gdb` backtrace,
  and every fix was confirmed against a small standalone reproduction before touching the full chain again.
- `py-spy dump --pid <p> --locals` (needs `sudo`; no non-interactive root here, so the user ran it) and `gdb -batch
  -ex run -ex bt` are the decisive tools for "a process is stuck" / "a process segfaults" -- they name the exact
  line, not just symptoms to guess from.
- `check.log`'s bare `t` field is wall-clock seconds since the script started, not sim time; `sim_t`/`sim_s` are.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's own goal -- cancel it explicitly first.
- Never open a run's bag while its recorder is alive. Read closed bags.

## Running it

PLEXIL: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_b_check.py D0_HOLD=1 D0_VIDEO=<mp4>
experiments/launch/lunar_base_d0/run_d0.sh <run dir>`. Rebuild the adapter after any `.cc` change: `PATH` without
conda, `PLEXIL_HOME` set, source ROS Humble + `openral/install/setup.bash`, `colcon build --merge-install
--packages-select plexil_capability_adapter` from `ros/`. PLEXIL's overlay panel
(`experiments/video/plexil_mission_video.py`, same layout as Ours' `mission_video.py`): `track_from_bag.py` +
`plexil_timeline_from_logs.py` (ROS python, needs `rosbag2_py`) then the video script itself (`openral/.venv`).

EUROPA offline: `baselines/europa/run_offline_mission_b.sh <run_dir> [--fail CAP:N[:far]]`; builds
`planner/build/europa_plan` and `plexil/build/libHostLink.so` itself if missing (plain `cmake`, no colcon). Live
run: not yet built -- needs a check script modelled on `d0_plexil_mission_b_check.py` that starts `host.py` against
the real graph instead of `sim_boundary.py`.

## Rules

- One graph per GPU (A on 1, B on 0). All paths absolute. No `pgrep -f` / `pkill -f`.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development resumes/debugging runs are not campaign results; never count them in paper metrics.
- Ask before merging/pushing a branch back; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies to the user in concise Simplified Chinese.
