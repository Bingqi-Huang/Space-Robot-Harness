# Handoff

Updated 2026-09-23 (everything merged and pushed; next: todo steps 7 and 8). Read `AGENT/research_content.md` and
`AGENT/execution_plan.md` first, then **`docs/heldout_design.md`** (the current plan), **`docs/baselines/authoring_spec.md`**
(the locked baseline specification), then `AGENT/todo.md`, then `docs/research_findings.md` F108-F111.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Heads

- research `main`, openral `master`, SRB `main`: all merged and pushed 2026-09-23. No open feature branches.
- Development runs on `pro6000` (this machine: host astroeng, uid 1007). The dev machine (z890) still has a checkout;
  the two sync only through origin (commit + push on one, pull on the other; ask before every push). Claude Code
  memory lives in `~/.claude/projects/-mnt-SharedData-Research-Space-Robot-Harness/memory/` on each machine
  separately -- pro6000's is the current one.

## Run farm (pro6000; heldout_design §11, F111)

- Repo at `/mnt/SharedData/Research/Space_Robot_Harness` (nofail bind mount of `/nvme02/bingqi/SharedData`; never
  `/nvme01`). New runs under `artifacts/runs/`; the dev machine's 330 GB of old runs are not here.
- `~/Programs/{isaac-sim,plexil,europa,europa-deps,blender,gperf,apache-ant-1.10.18}`, `~/isaaclab`, `~/.cache/{ov,
  openral,simforge,robot_descriptions}` were rsynced from the dev machine; the image mounts them.
- Image `runfarm:22.04` (`docker/runfarm/Dockerfile`: Ubuntu 22.04 + the dev machine's ROS Humble set). Rebuild:
  `docker build --network host --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t runfarm:22.04 docker/runfarm`.
- **One run = one container**: `docker/runfarm/runfarm.sh <gpu 0-5> <name> "<env vars> <abs path>/run_d0.sh <abs run
  dir>"`. Own network namespace (no ROS domain / port collisions), pinned to 10 cores + HT on the GPU's socket, public
  DNS, GPU via CDI (inside, it is device 0: leave `D0_GPU` unset). The container ends with the run; `docker stop <name>`
  takes one down. Example that passed (`rf_equiv_1`): `D0_PROFILE=1 D0_CAPABILITY_SERVER=1
  D0_CHECK=d0_plexil_mission_a_check.py D0_SCENE=scenes/deploy/srb_lunar_base_mission_a.yaml`.
- Speed: sim/wall 0.185 per run (dev machine 0.28, but it can only run one at a time); first container render
  compiles shaders for a few minutes. Per tick 102 ms: physics 30, TF 24, `_get_dones` 17, lidar 12.
- sudo needs the user's password: write root commands for the user. Never touch the kernel / GRUB / Docker daemon (a
  half-installed 7.0.0-31 kernel predates us; GRUB is pinned to 6.17.0-29). git-lfs is in `~/.local/bin`.
- Physics stays CPU PhysX (user decision; GPU PhysX crashes in SRB, F54 §5).

## Models (F111)

Reasoner, scene VLM and pick/press VLM: `DeepSeek-V4.1-Flash` at `https://llmapi.paratera.com/v1`, key = the first
`sk-` in `AGENT/VLM_provider.md` (gitignored: only in the main checkout, not in worktrees). DeepSeek's own API is
unaffordable -- do not switch back. Keep one 640x480 view per VLM request (large requests are slow on this gateway).

## Decisions of 2026-09-23 (with the user)

- **Baseline lock** (authoring_spec): tier 1 identical-call retry, 3 attempts, then hold and ask mission control;
  tier 2 the goal checks the brief asks for; tier 3 (cause/situation/stage branches) forbidden. Mission A goal = every
  unit restored; Mission B parameterized; one NDDL domain; all inventoried items in EUROPA's instance; delete adapter
  stage/kind/jaw Lookups and EUROPA `--power-field`. After the lock only infrastructure and conformance fixes.
- **Physical validation** before any further live method run: no held-out press/pick/place was ever executed.
- Rejected: a dev/test split of units for Ours' held-out development; a separate 6-way concurrency test.

## Where it stands

Steps 1-5 of heldout_design §10 done (site, scenarios, protocol, evaluator, lock); run farm built and validated.
Ours has never run a held-out case; baselines only offline on re-trip/no-hold. Next: todo 7 (baselines to the
lock, offline) and 8 (physical validation: offline geometry first, then seven scripted chains) in parallel.

## Method rules earned the hard way

- Teardown after SIGINT prints tracebacks and a move_group segfault: noise; judge a run by `CHECK_EXIT` and RESULT.
- A manually started `ros2 bag record` does not inherit `D0_RUN_TAG`: after teardown check `pgrep -fa "ros2 bag
  record"` and SIGINT the orphan by exact PID.
- Killing a check script mid-`navigate`/`dock` does not cancel Nav2's goal -- cancel
  `/navigate_to_pose/_action/cancel_goal` (all-zero goal_id) first. Never open a run's bag while its recorder is alive.
- Isaac can abort on a carb mutex assertion ("unlock() called by non-owning thread"): not ours, relaunch.
- A Monitor pipe must not end in `cut` (it buffers; use `grep --line-buffered -o`).
- PLEXIL: decisions on live state with `if/endif`, never SkipCondition; reusing a library can silently drop a retry
  (F106). `git merge -F -` does not read stdin: write the message to a file.
- rsync with a source without a trailing slash anchors `--exclude /x/` at the parent: check what an exclude matches.

## Running it

Ours: `D0_CHECK=ours_mission_check.py OURS_MISSION={a,b}`; PLEXIL: `D0_CAPABILITY_SERVER=1
D0_CHECK=d0_plexil_mission_{a,b}_check.py`; EUROPA: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_europa_mission_{a,b}_check.py
D0_SCENE=scenes/deploy/srb_lunar_base_mission_{a,b}.yaml`; site acceptance: `D0_CONTINUE_ON_FAIL=1
D0_CAPABILITY_SERVER=1 D0_CHECK=d0_site_check.py D0_SCENARIO=heldout_radiator_cover D0_ENV="env.faulted_unit=bess"
D0_SCENE=scenes/deploy/srb_lunar_base_mission_a.yaml` -- each through `runfarm.sh` with
`experiments/launch/lunar_base_d0/run_d0.sh <abs run dir>`. Options: `D0_SCENARIO`, `D0_ENV`, `D0_VIDEO`, `D0_PROFILE`,
`D0_HOLD` (see run_d0.sh). PLEXIL adapter rebuild after a `.cc` change: `colcon build --merge-install
--packages-select plexil_capability_adapter` from `ros/` (PLEXIL_HOME set). EUROPA offline:
`baselines/europa/run_offline_mission_{a,b}.sh <run_dir> [--fail CAP:N[:far]]`. Scene: `python3 scene/build_scene.py`
(+ `--variant route_block`); assets `blender -b --factory-startup -P process/author_props.py -- authored` ->
`python3 process/process.py --only <name>`; renders `scene/render_review.py` in a container.

## Rules

- All paths absolute. Kill only positively identified own PIDs / own containers.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development runs are not campaign results; never count them in paper metrics.
- Ask before merging/pushing/committing; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies in concise Simplified Chinese.
