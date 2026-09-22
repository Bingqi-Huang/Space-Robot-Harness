# Handoff

Updated 2026-09-22 (F104, PLEXIL Mission B live). Read `AGENT/research_content.md` and `AGENT/execution_plan.md`
first, then `AGENT/todo.md`. Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns
facts, evidence, verification and hard boundaries. Simulator truth is for post-hoc diagnosis only, never a decision.

## Heads

research `feat/plexil-baseline-live` (off `feat/experiment-campaign`, not merged back -- ask first), openral/SRB
unchanged on `feat/experiment-campaign`/`feat/lunar-base-scene`. `p/integration` (PLEXIL Mission B, EUROPA,
evaluation infra, operator mechanism, evaluator violations) merged into `feat/experiment-campaign` earlier today.
Nothing pushed.

## Where it stands

Ours: Mission A and Mission B both run from scratch on the corrected arm, evaluator `success: true`, video recorded
(F92-F100). **PLEXIL: Mission B covered now runs end to end on the live, corrected-arm graph** --
`delivered: true, success: true`, video recorded (F104, `artifacts/runs/plexil_mission_b_success_20260922`) -- the
first time any baseline has completed a full mission on the current stack. Mission A already ran covered before
(F52, older stack -- worth a fresh confirmation once `press` is fixed). EUROPA: generic host/bridge verified offline
on a skeleton domain only (F102); Mission B domain not started. **Still no campaign**: the three methods have never
run the identical instance side by side, and nothing is frozen. `execution_plan` §21's next item (baselines / freeze
/ experiments) is closer but not started.

- `artifacts/runs/` debug archive from earlier this session (117 GB) still sits at `_debug_archive/`, not deleted.
- The three failed PLEXIL Mission B debug runs (F104) are deleted; the successful one is kept, renamed
  `artifacts/runs/plexil_mission_b_success_20260922` (same convention as Ours' `mission_a/b_success_20260922`).

## F104 -- the PLEXIL adapter's early ack, not the plan, raced the whole mission to "done" in under a second

Full account: `docs/research_findings.md` F104, `docs/baselines/plexil.md`. In short: `CapabilityAdapter.cc`'s
`send()` acked `COMMAND_SENT_TO_SYSTEM` the instant a ROS action goal was merely *accepted* (a handshake); PLEXIL's
own `CommandHandleKnown` (`src/intfc/CommandImpl.cc`) treats *any* known command handle, terminal or not, as
"action complete" -- so every command in the plan "finished" the moment it was accepted, while the robot had done
nothing. `RequestOperator` had the identical bug. Fixed: ack only on genuine rejection or the real terminal result.
Root-caused by reading PLEXIL's own executive source, not guessed at, and confirmed with one `sudo py-spy dump
--locals` (the user ran the `sudo`; this session has no non-interactive root) that named the exact stuck line and
caught the buffered node-transition trace proving the whole plan had already "finished" before the robot moved. Two
smaller library bugs found and fixed the same day, each caught offline (`plexiltest`/`plexilc`) before a live retry:
missing `-L plans/lib` on the check script's `universalExec` invocation, and `PickItem` missing `pick`'s
practically-required `support` argument.

## Method rules earned the hard way this session

- **Audit before reacting; read the source before guessing.** The adapter bug was root-caused by reading PLEXIL
  6.1.3's own `CommandNode.cc`/`CommandImpl.cc`, not by trying fixes until one worked.
- **`py-spy dump --pid <p> --locals`** (needs `sudo`; this environment has no non-interactive root, so the user ran
  it once) is the decisive tool for "a process is alive but stuck": it named the exact line and the exact argument
  values for all 8 threads at once, versus an unbounded amount of guessing from process/thread CPU state alone.
- **`check.log`'s bare `t` field is wall-clock seconds since the script started, not sim time.** `sim_t`/`sim_s`
  fields are the real simulation clock.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's own goal -- cancel it explicitly before any
  snapshot restore.
- Never open a run's bag while its recorder is alive. Read closed bags.
- A skill failure is not always a bug: `pick`'s `find` has no internal retry by design -- a single bad VLM read is
  answered by the caller retrying (the reasoner for Ours; one more live attempt, by hand, for a nominal-path-only
  PLEXIL plan with no recovery branches yet), not by the skill looping internally.

## Running it

PLEXIL: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_b_check.py D0_HOLD=1 D0_VIDEO=<mp4>
experiments/launch/lunar_base_d0/run_d0.sh <run dir>` (default scene is Mission B's); start a bag recorder the same
way `launch_full_pair.sh` does for Ours if a diagnosis trace is wanted. Rebuild the adapter after any `.cc` change:
`PATH` without conda, `PLEXIL_HOME=$HOME/Programs/plexil` set, source `/opt/ros/humble/setup.bash` +
`openral/install/setup.bash`, `colcon build --merge-install --packages-select plexil_capability_adapter` from `ros/`.
Recompile a changed `.ple`: `plexilc <file>.ple` (library nodes need `-L <lib dir>` at run time, not compile time);
a changed `.pst` simulator script: `plexilscript <file>.pst`.

Skills are import-cached in `runtime_node`; a skill change needs the runtime restarted (`D0_RESTART_RUNTIME_PID`), an
SRB or asset change needs the graph rebooted. Kill by run tag, never by name: `teardown_d0.sh <run dir>` with
`D0_VIDEO=<mp4>` set to finalize the video. Stop the recorder by PID before teardown. A video near the 30 MiB send
limit: `ffmpeg -c:v libx264 -crf 31 -c:a aac -b:a 96k` re-encode (a decode warning mid-file from the teardown's own
SIGINT-mid-fragment remux is harmless if the output duration still matches the source).

## Rules

- One graph per GPU (A on 1, B on 0). All paths absolute. No `pgrep -f` / `pkill -f`.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development resumes/debugging runs are not campaign results; never count them in paper metrics.
- Ask before merging/pushing a branch back; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies to the user in concise Simplified Chinese.
