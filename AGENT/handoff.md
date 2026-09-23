# Handoff

Updated 2026-09-23 (held-out ladder steps 1-4 reviewed and merged; next: step 5, baseline competence). Read `AGENT/research_content.md` and
`AGENT/execution_plan.md` first, then **`docs/heldout_design.md`** (the current plan), then `AGENT/todo.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Heads

- `feat/heldout-ladder` (with `feat/experiment-campaign` beneath it) merged: research repo `main`, SRB `main`,
  openral `master`; the research repo's submodule pointers are the merged tips. Nothing pushed (ask first).
- Start each new task on a fresh `feat/<name>` branch in every repo it touches.

## Where it stands (2026-09-23)

Steps 1-4 of `docs/heldout_design.md` §10 are built (F109) and redone after the user's review (F110):
- Five serviced units as scene data (layout.yaml `units` -> interaction.json; site points tagged `unit`): PDU-1..3
  (panel, shelf, ORU bay, radiator), BESS (container on the pad, wall BMS enclosure + graphite panel, battery cradle,
  HVAC condenser with shutter), ISRU plant (plant panel, filter + power-ORU cradles). `site.py` has no unit list;
  module fault codes per module kind; telemetry lists installed serials per bay.
- Mission A `env.faulted_unit` in {pdu_1..3, bess, isru}; Mission B `env.cargo` / `env.destination`.
- Console protocol (§8), async operator requests, evaluator class 5 keyed on unit + granted bay, interaction measures.
- Nav2: global costmap = the AMCL surveyed map (static + live obstacle + inflation, 0.05 m); the capability server's
  drive limits no longer zero the crab (they were a hand-copied [0.5, 0.0, 2.0] -- F110 c).
- Baselines: PLEXIL Identify and EUROPA button descriptions span all five units (plexiltest offline ok).
Live acceptance: `artifacts/runs/site_check_10` (`d0_site_check.py`; 7-9 are the fixes' intermediate runs).

## Next

Step 5 (`AGENT/todo.md`): make PLEXIL and EUROPA cover every unit and both missions' parameters, then re-run
covered live for PLEXIL, EUROPA and Ours on the final scene -- covered runs from before the scene change do not
count for the freeze. Then step 6 (Ours L2-A -> L2-B -> L3 -> L4 near/far), 7 (freeze), 8 (campaign).

## Constraints the new assets must meet

- Every new item/support must be `pick`/`place`-compatible: horizontal surveyed tray, ~10 cm clearance around a
  0.45 × 0.39 m ORU, T-handle up, a legal stand from `work_stands` -- computed offline before any live run.
- Rigid only; mechanism states are visual variants toggled by the task (like `set_status_lamp`), actuators are
  dummy push buttons.
- Labels must decode from the wrist view at 640×480 (≈0.6 mm/px at 0.3 m): check with one still render first.

## Method rules earned the hard way

- A manually started `ros2 bag record` does not inherit `D0_RUN_TAG`: after any teardown check
  `pgrep -fa "ros2 bag record"` and SIGINT the orphan by exact PID. A shared bag across a relaunch resets
  `/clock` -- segment sim-time readers at the clock decrease.
- `teardown_d0.sh <log_dir>` needs an absolute path; pass `D0_VIDEO=<mp4>` to it too (clean remux).
- Read the source before guessing; reproduce minimally before calling something a bug.
- `check.log`'s bare `t` is wall seconds since script start; `sim_t`/`sim_s` are sim time.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's goal -- cancel it first.
- Never open a run's bag while its recorder is alive.
- Isaac can abort mid-run on a carb mutex assertion ("unlock() called by non-owning thread", 5 runs so far):
  intermittent, not ours -- tear down and relaunch. A Monitor pipe must not end in `cut` (it buffers; use `grep -o`).

## Running it

Ours: `D0_CHECK=ours_mission_check.py OURS_MISSION={a,b} run_d0.sh <abs run dir>` (`D0_SCENARIO=` selects the SRB
scenario). PLEXIL: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_{a,b}_check.py D0_HOLD=1 D0_VIDEO=<mp4>
experiments/launch/lunar_base_d0/run_d0.sh <run dir>`; rebuild the adapter after any `.cc` change (`PATH` without
conda, `PLEXIL_HOME`, ROS Humble + `openral/install/setup.bash`, `colcon build --merge-install --packages-select
plexil_capability_adapter` from `ros/`). EUROPA offline: `baselines/europa/run_offline_mission_{a,b}.sh <run_dir>
[--fail CAP:N[:far]]`; live: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_europa_mission_{a,b}_check.py D0_HOLD=1
D0_VIDEO=<mp4> D0_SCENE=scenes/deploy/srb_lunar_base_mission_{a,b}.yaml run_d0.sh <run dir>`. Overlay panels:
`track_from_bag.py` + `{plexil,europa}_timeline_from_logs.py` then `{plexil,europa}_mission_video.py`
(`--top ToUnit,Press,Return` for PLEXIL Mission A). Scene assets: Blender `process/author_props.py` → layout →
generated `interaction.json` (see `space_robotics_bench/assets/lunar_base/`).

## Rules

- One graph per GPU (check `D0_DOMAIN`/`D0_GPU`). All paths absolute. No `pgrep -f` kills except one positively
  identified orphan PID.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development runs are not campaign results; never count them in paper metrics.
- Ask before merging/pushing/committing; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies in concise Simplified Chinese.
