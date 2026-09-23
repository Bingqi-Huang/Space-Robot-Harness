# Handoff

Updated 2026-09-23 late (baseline lock decided; run farm on `pro6000` built; next: its equivalence test). Read
`AGENT/research_content.md` and `AGENT/execution_plan.md` first, then **`docs/heldout_design.md`** (the current plan),
**`docs/baselines/authoring_spec.md`** (the locked baseline specification), then `AGENT/todo.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Heads

- research `main` = steps 1-4 (pushed). `feat/baseline-lock` (2b13070, docs) and `feat/run-farm` (on top of it:
  `docker/runfarm/`, §11 storage/pinning, this file) are both pushed to origin; merging into `main` awaits the user.
- SRB `main`, openral `master`: unchanged since the steps 1-4 push.
- Development now also happens on `pro6000` (Claude Code there; memory and session history synced). The two checkouts
  sync through origin: commit + push on one, pull on the other (ask before every push).

## Run farm (`pro6000`, heldout_design §11)

- ssh `pro6000` (host astroeng), uid 1007, sudo needs the user's password: give the user root commands to run.
- Repo at `/mnt/SharedData/Research/Space_Robot_Harness` (nofail bind of `/nvme02/bingqi/SharedData`; not `/nvme01`).
  `artifacts/` is not synced (old dev runs stay on the dev machine); new runs go to `artifacts/runs/` there.
- `~/Programs`, `~/isaaclab`, `~/.cache/{ov,openral,simforge,robot_descriptions}` rsynced from the dev machine.
- Image `runfarm:22.04` built there (`docker build --network host --build-arg UID=$(id -u) --build-arg GID=$(id -g)
  -t runfarm:22.04 docker/runfarm`). One run = one container: `docker/runfarm/runfarm.sh <gpu> <name> <cmd>` (own
  network namespace; pinned cores; inside, the one GPU is device 0 -- leave `D0_GPU` unset).
- git-lfs is in `~/.local/bin` (non-interactive ssh: `export PATH=$HOME/.local/bin:$PATH`).
- Never touch the kernel / GRUB / Docker daemon there: a half-installed 7.0.0-31 kernel (DKMS fails) predates us;
  GRUB is pinned to 6.17.0-29 by the admin.
- The dev machine runs one simulation at a time (two unpinned Isaac processes ran at 0.05x each, F54 §4).
- Physics stays CPU PhysX (user decision 2026-09-23).

## Next

1. Equivalence + profile on pro6000 (todo 6): `runfarm.sh 0 rf-equiv D0_PROFILE=1 D0_CAPABILITY_SERVER=1
   D0_CHECK=d0_plexil_mission_a_check.py D0_SCENE=scenes/deploy/srb_lunar_base_mission_a.yaml
   /mnt/SharedData/Research/Space_Robot_Harness/experiments/launch/lunar_base_d0/run_d0.sh
   /mnt/SharedData/Research/Space_Robot_Harness/artifacts/runs/rf_equiv_1` -- outcome (fault cleared, docked),
   sim/wall ratio (dev machine: PLEXIL A 0.28 on the pre-F109 scene), SRB per-tick buckets. First container run:
   expect a few minutes of shader compilation. Then 6 ways at once; re-cost the campaign from the measurement.
2. In parallel: todo 7 (baselines to the lock, offline) and todo 8 (physical validation, offline geometry first).

## Decisions of 2026-09-23 (with the user)

- **Baseline lock** (authoring_spec): native PLEXIL/EUROPA + covered knowledge. Tier 1: a failed call repeated, 3
  attempts (= Ours' identical-call cap), then hold in place and ask mission control. Tier 2: the goal checks the brief
  asks for. Tier 3 forbidden: any branch keyed on a cause/situation/failure stage. Mission A goal = every unit restored;
  Mission B parameterized (item, source, destination) from one shared launcher goal; one NDDL domain; all inventoried
  items in EUROPA's instance; delete adapter stage/kind/jaw Lookups and EUROPA `--power-field`. Change control: only
  infrastructure and conformance fixes after the lock. Grounded in ECSS-E-ST-70-11C §5.7.5, RAX, MEXEC (Wang 2022),
  PLEXIL TM-2006-213483, Morris 2013, COWP.
- **Physical validation** (heldout_design §12): no held-out press/pick/place was ever executed (only IK reach and VLM
  views). Offline geometry, then seven scripted chains, one run each, before any further live method run.
- **Run farm** (§11): `pro6000` via ssh (`~/.ssh/config`), 6 x RTX PRO 6000 96 GB, 128 threads, 503 GB, Ubuntu 24.04,
  Docker 29.3, no ROS, no nvidia-container-toolkit yet, user has sudo, network prepared by the user; SSD `/nvme01`
  (not `/nvme02`, 97% full); shared with another user. Plan: 22.04 image built here, rsync (gigabit), same paths.
- Rejected: a dev/test split of units for Ours' held-out development (user: over-cautious; §13.1 rules + freeze audit).

## Measured run costs (dev machine, 2x RTX 5090, 24 cores)

Sim runs at 0.17-0.31 x real time. PLEXIL A 11 min / B 19 min wall; EUROPA A 24 / B 20 min; Ours covered A 46 min
(`artifacts/runs/*_success_20260922`). Remaining live work ~310 GPU-h (±50%), campaign ~170.

## Where it stands

Steps 1-4 of `docs/heldout_design.md` §10 are built (F109) and redone after review (F110): five serviced units as scene
data (PDU-1..3, BESS, ISRU), Mission A `env.faulted_unit`, Mission B `env.cargo`/`env.destination`, console protocol,
evaluator class 5, Nav2 global costmap = AMCL surveyed map, crab restored. Live acceptance `artifacts/runs/site_check_10`.
Ours has never run a held-out case; baselines only offline on re-trip/no-hold.

## Next

After approval: commit the docs; then in parallel 6 (run farm), 7 (baselines to the lock, offline), 8 (physical
validation, offline geometry first). Then 9 (covered live re-runs), 10 (Ours on the ladder), 11 (freeze), 12.

## Method rules earned the hard way

- A manually started `ros2 bag record` does not inherit `D0_RUN_TAG`: after any teardown check
  `pgrep -fa "ros2 bag record"` and SIGINT the orphan by exact PID. A shared bag across a relaunch resets
  `/clock` -- segment sim-time readers at the clock decrease.
- `teardown_d0.sh <log_dir>` needs an absolute path; pass `D0_VIDEO=<mp4>` to it too (clean remux).
- Read the source before guessing; reproduce minimally before calling something a bug.
- `check.log`'s bare `t` is wall seconds since script start; `sim_t`/`sim_s` are sim time.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's goal -- cancel it first.
- Never open a run's bag while its recorder is alive.
- Isaac can abort mid-run on a carb mutex assertion ("unlock() called by non-owning thread"): intermittent, not ours
  -- tear down and relaunch. A Monitor pipe must not end in `cut` (it buffers; use `grep --line-buffered -o`).
- PLEXIL: decisions on live state with `if/endif`, never SkipCondition; reusing a library can silently drop a retry
  (F106) -- check every leg's `Try`. `git merge -F -` does not read stdin: write the message to a file.

## Running it

Ours: `D0_CHECK=ours_mission_check.py OURS_MISSION={a,b} run_d0.sh <abs run dir>` (`D0_SCENARIO=` selects the SRB
scenario). PLEXIL: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_{a,b}_check.py D0_HOLD=1 D0_VIDEO=<mp4>
experiments/launch/lunar_base_d0/run_d0.sh <run dir>`; rebuild the adapter after any `.cc` change (`PATH` without
conda, `PLEXIL_HOME`, ROS Humble + `openral/install/setup.bash`, `colcon build --merge-install --packages-select
plexil_capability_adapter` from `ros/`). EUROPA offline: `baselines/europa/run_offline_mission_{a,b}.sh <run_dir>
[--fail CAP:N[:far]]`; live: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_europa_mission_{a,b}_check.py D0_HOLD=1
D0_VIDEO=<mp4> D0_SCENE=scenes/deploy/srb_lunar_base_mission_{a,b}.yaml run_d0.sh <run dir>`. Site acceptance:
`D0_CONTINUE_ON_FAIL=1 D0_CAPABILITY_SERVER=1 D0_CHECK=d0_site_check.py D0_SCENARIO=heldout_radiator_cover
D0_ENV="env.faulted_unit=bess" D0_SCENE=scenes/deploy/srb_lunar_base_mission_a.yaml run_d0.sh <abs run dir>`.
Scene: `python3 scene/build_scene.py` (+ `--variant route_block`); assets `blender -b --factory-startup -P
process/author_props.py -- authored` -> `python3 process/process.py --only <name>`; renders with the sim on GPU 0:
`CUDA_VISIBLE_DEVICES=1 ~/Programs/isaac-sim/python.sh scene/render_review.py <out> "name=ex,ey,ez,tx,ty,tz"`.

## Rules

- One graph per GPU (check `D0_DOMAIN`/`D0_GPU`). All paths absolute. No `pgrep -f` kills except one positively
  identified orphan PID.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development runs are not campaign results; never count them in paper metrics.
- Ask before merging/pushing/committing; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies in concise Simplified Chinese.
