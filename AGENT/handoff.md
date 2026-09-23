# Handoff

Updated 2026-09-23 (held-out set decided; no code yet). Read `AGENT/research_content.md` and
`AGENT/execution_plan.md` first, then **`docs/heldout_design.md`** (the current plan), then `AGENT/todo.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Heads

- Research repo and `space_robotics_bench`: branch `feat/heldout-ladder`, cut from `feat/experiment-campaign`
  (`fb47fd8`, F107). `openral` stays on `feat/experiment-campaign` (branch it when it needs a change).
- Nothing pushed; `feat/experiment-campaign` not merged to `main` (user decides when).
- `artifacts/runs/_debug_archive/` (117 GB) still present -- ask before deleting.

## Where it stands

All three methods (Ours, PLEXIL, EUROPA→PLEXIL) complete Mission A and Mission B **covered** live on the
corrected-arm stack, each with video and overlay panel (runs `*_mission_{a,b}_success_20260922`); evaluation /
manifest infra exercised on those six runs (F107). No held-out case has run on the current stack; nothing frozen.

## Decision of 2026-09-23 (with the user): the held-out ladder

Full design, sources and implementation order: `docs/heldout_design.md`. In short, levels by what the frozen
baseline model lacks:

- L1 covered variants: other faulted unit; fault report names the wrong unit (ISS 2015 erroneous MDM indication).
- L2-A radiator cover left closed → over-temperature re-trip; fix = press a dummy cover button, then reset
  (LRV radiator covers, Creel; Apollo 16/17 battery over-temp, Gaier).
- L2-B destination tray occupied by a returned crate (exists in SRB).
- L3 reset does not hold (ORU self-test fail) → remove-and-replace with the depot spare: the composition of the
  two covered missions that neither baseline has (Dextre RPCM R&R 2011; Lewis 2022).
- L4 no serviceable spare → take PDU-3's (energized, science) ORU for PDU-1 (life support); needs ground approval
  before the SPICE-derived Earth-visibility window closes (14 CFR 1214.403; Apollo 17 fender repair). This is also
  the H3 / space-native evidence (resolves the old "which hard boundary" question).
- Control: route_block. Experiment II: new shared capability `scan_label` (wrist-camera Data Matrix, NASA-STD-6002)
  on hidden inventory-record mismatches.

How we got there (so it is not re-litigated): the user rejected (1) tags / placards / cloth -- no precedent for
the *situation*, only for the category; (2) A2 cover obstruction -- a leaning plate is not `pick`-compatible;
(3) B3 spare swapped -- `depot_stand/slot_1` has no legal stand, and it is a known unknown; (4) re-running covered
missions to get a base success rate -- it changes no decision. The user chose a visible barcode over RFID for
the demo (a real decode on the rendered frame, visible in the overlay).

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
