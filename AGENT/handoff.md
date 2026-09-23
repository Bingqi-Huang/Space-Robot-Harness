# Handoff

Updated 2026-09-23 (held-out ladder: scene, scenarios, authority and link built; site check live). Read `AGENT/research_content.md` and
`AGENT/execution_plan.md` first, then **`docs/heldout_design.md`** (the current plan), then `AGENT/todo.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Heads

- Research repo and `space_robotics_bench`: branch `feat/heldout-ladder`, cut from `feat/experiment-campaign`
  (`fb47fd8`, F107); docs committed (`ca492cf`), steps 2-5 work uncommitted at this writing. `openral` unchanged.
- Nothing pushed; nothing merged to `main`. `artifacts/runs/_debug_archive/` never existed (old handoff error).

## Where it stands (2026-09-23)

All three methods complete Mission A/B **covered** on the old scene (runs `*_mission_{a,b}_success_20260922`).
The scene has since changed (bays, installed ORUs, radiators; service cover gone), so covered must be re-run for
every method before the freeze -- that is a campaign prerequisite, not a base-rate rerun.

Built today (todo steps 2-5, details there): the shared site model `srb/.../lunar_base/site.py` (one physics for all
scenarios: breaker trips, radiator overheating under a closed shutter, ORU self-test, ORU missing), telemetry +
inventory record through the boundary, the new props/labels, the four new scenarios, authority by target in Ours'
guard with the approval handshake through the console, SPICE Earth-link profile + DTN link gate. Live-verified in
`artifacts/runs/site_check_2` (`d0_site_check.py`): telemetry/inventory reach the boundary, every bay and cover button
has a legal stand, the open radiator reads as open. The closed shutter was misread (light grey, slat seams looked
like fins) -> recoloured charcoal; `site_check_3` reads both states right. Baselines made competent on the covered
brief and offline-verified (F108).

## Next

Work order: `docs/heldout_design.md` §10 / `AGENT/todo.md`. Ground protocol decided (§8: scripted, 300 s decision
time, flight-rule grant table, HOLD reply for "no procedure applies", ALFUS labels); base-wide expansion decided (§9:
battery-container unit, ISRU donor unit, landing -> habitat logistics, habitat shelf occupancy; equipment as a
blocking factor). Next up: step 1, the scene expansion.

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
