# Handoff

Updated 2026-09-24 afternoon (steps 7-8 done, Nav2 freeze fixed (F113); sim speed done; next: step 9). Read `AGENT/research_content.md` and
`AGENT/execution_plan.md` first, then **`docs/heldout_design.md`** (the current plan; §14 = the campaign instances), **`docs/baselines/authoring_spec.md`**
(the locked baseline specification), then `AGENT/todo.md`, then `docs/research_findings.md` F108-F113.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Heads

- research `main`, openral `master`, SRB `main`: committed 2026-09-24 (F114 fixes). No feature branches/worktrees.
- **After step 9: follow todo item "9+" in order** (results + F115, commits, arm_ready keep-out, labels, raw-data
  recording, PLEXIL node ids + tool fixes, one selected live batch, checklist). `docs/preflight_checklist.md` gates the freeze.
- **Step 9 (restarted 15:01, tmux `step9`) was running at the last update**; earlier note: its first launch (14:38) stopped on the F114 livelock and was deleted; restart only on the
  user's go. Launch: `tmux new-session -d -s step9 "experiments/launch/lunar_base_d0/farm_queue.sh
  experiments/launch/lunar_base_d0/jobs/step9_covered.txt artifacts/runs/step9"` (`tmux attach -t step9`; it outlives
  the Claude session). 21 runs, Ours first; progress in `artifacts/runs/step9/queue.log`; containers `rf-<run name>`.
- Image `runfarm:22.04` now carries gdb, Cyclone (unused) and tf2 rebuilt from geometry2 9997e969 (F113); the old
  `runfarm-gdb:22.04` is obsolete. Host sysctl: socket-buffer ceiling 64 MB (`/etc/sysctl.d/60-runfarm-dds.conf`).
- Development runs on `pro6000` (host astroeng, uid 1007). The dev machine (z890) syncs only through origin.

## Run farm (pro6000; heldout_design §11, F111, F112)

- Repo at `/mnt/SharedData/Research/Space_Robot_Harness` (bind mount of `/nvme02/bingqi/SharedData`; never `/nvme01`).
- Image `runfarm:22.04` (Dockerfile in git; build with the proxy variables unset: every source is a domestic mirror,
  except the tf2 tarball from GitHub); home installs and caches mounted, incl. `~/.nv`.
- **One run = one container**: `docker/runfarm/runfarm.sh <gpu 0-5> <name> "<env vars> <abs path>/run_d0.sh <abs run
  dir>"`. Each container gets ROS domain 77 + GPU (they share the docker bridge; Humble ignores
  `ROS_AUTOMATIC_DISCOVERY_RANGE`). Two containers on one GPU share a domain and break each other's launch.
- Interactive shell: `runfarm.sh 0 rf-dev-0 sleep infinity`, then `docker exec -it rf-dev-0 bash -l`.
- runfarm.sh also binds memory to the GPU socket's NUMA nodes, sets ROS_DOMAIN_ID container-wide, grants SYS_PTRACE
  (gdb as root: `docker exec -u root`; the host's yama ptrace_scope is 1).
- Throwaway containers (builds, offline checks) without a GPU and ALWAYS `--cpuset-cpus 30,31,62,63` + `nice -n 19`:
  an unpinned build starved six pinned simulations (F112).
- `D0_BAG="<topics>"` records a tagged bag; the scripted chains record nav topics by default (scratchpad launcher).
- Speed: sim/wall ~0.19-0.22 per run with six at once. sudo needs the user's password; never touch kernel/GRUB/daemon.
- Physics stays CPU PhysX (user decision).

## Models (F111, F112)

Reasoner, scene VLM and pick/press VLM: `DeepSeek-V4.1-Flash` at `https://llmapi.paratera.com/v1`, key = the first
`sk-` in `AGENT/VLM_provider.md` (gitignored). Do not switch back to DeepSeek's own API. One 640x480 view per request.
Pick's region choice answers in 10-115 s (median 61 s); pick/press allow 300 s per view.

## What step 8 established (F112)

- Every held-out action form executed: press (PDU/BESS/ISRU panels, PDU and BESS shutter buttons), pick/place of ORU,
  battery module, filter cartridge, crate, return container, consumables container, at PDU bays/shelves, BESS
  cradle/stand, ISRU cradles/stands, depot, landing and habitat stands; L4-far's 40 m carry.
- Shared-layer fixes: survey map keeps lumps >= 5 cells (stray cells had inflated into no-go areas); a navigation
  after a dock first backs out along the dock axis; pick seeds at the declared work point and splits depth lumps;
  place's settle "not judged" is not a failure; press backs out of proud panel boxes and folds the arm after;
  launcher waits for a fresh `map -> odom`; `retrip_delay_s` 30 s; uniform handle neck height; ISRU set-down stand.
- Baselines (step 7): PLEXIL 3-attempt Try everywhere, Mission B parameterized, hold after escalation
  (`UncheckedSequence`); EUROPA one domain, goals restored/delivered, upstream TemporalNetwork use-after-free patched
  (`baselines/europa/patches/`, applied by `build_europa.sh`). Adapter rebuilt in main's `ros/`.

## Method rules earned the hard way

- Never edit shared skill modules (openral rskill) while runs are live: runners import them lazily, and old+new code
  mixed (`cannot import name 'STOW'`). Capability server / contracts are loaded at run start (safe).
- Judge a run by `CHECK_EXIT`/`RESULT`/`CHAIN_DONE`; teardown tracebacks and move_group segfaults are shutdown noise.
- Look first: pick evidence has `view.jpg`, `regions.jpg`, `fit.jpg`, depth, and now K + camera pose (offline replay).
- Live diagnosis tools in `experiments/analysis/` (README there); never open a live bag.
- Do not run more than one hypothesis batch without reporting: the freeze hunt burned hours on A/B batches.
- Isaac can abort on a carb mutex assertion: not ours, relaunch. Monitor pipes: `grep --line-buffered`, no `cut`.
- Killing a check mid-navigation: cancel `/navigate_to_pose/_action/cancel_goal` (all-zero goal_id) first.
- PLEXIL: `if/endif` on live state, never SkipCondition; root `UncheckedSequence` so escalation can run.
- `git merge -F -` does not read stdin: write the message to a file. rsync exclude anchoring: check what it matches.

## Running it

Queued batches: `tmux new-session -d -s <name> "experiments/launch/lunar_base_d0/farm_queue.sh <jobs file> <run root>"`
(one worker per GPU; a jobs line = `<run name> <env assignments>`). Ours: `D0_CAPABILITY_SERVER=1 D0_CHECK=ours_mission_check.py`; PLEXIL: `D0_CAPABILITY_SERVER=1
D0_CHECK=d0_plexil_mission_{a,b}_check.py`; EUROPA: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_europa_mission_{a,b}_check.py
D0_SCENE=scenes/deploy/srb_lunar_base_mission_{a,b}.yaml`; Mission B cargo/destination via `D0_ENV="env.cargo=...
env.destination=..."` (both baselines read the same goal). Scripted chains: `D0_CAPABILITY_SERVER=1
D0_CHECK=scripted_chain_check.py CHAIN_JSON=<abs>/experiments/launch/lunar_base_d0/chains/<name>.json` + the
scenario (`D0_SCENARIO`, `D0_ENV`, `D0_SCENE`); each call gets 3 attempts. Site acceptance: `D0_CONTINUE_ON_FAIL=1
D0_CAPABILITY_SERVER=1 D0_CHECK=d0_site_check.py D0_SCENARIO=heldout_radiator_cover D0_ENV="env.faulted_unit=bess"
D0_SCENE=scenes/deploy/srb_lunar_base_mission_a.yaml`. PLEXIL adapter rebuild: `colcon build --merge-install
--packages-select plexil_capability_adapter` from `ros/` in a pinned container. EUROPA offline:
`baselines/europa/run_offline_mission_{a,b}.sh`; PLEXIL offline: `baselines/plexil/scripts/offline_check.py`.
Scene: `scene/build_scene.py` (+ `--variant route_block`); assets `process/process.py --only <name>` (needs zxing-cpp,
opencv: `uv run --no-project --with ...`); handle check `process/check_handles.py`. Map survey:
`~/Programs/isaac-sim/python.sh assets/lunar_base/scene/srb_nav_map_survey.py <out_dir>` in a runfarm container
(~27 min); only when the structural footprint changes.

## Rules

- All paths absolute. Kill only positively identified own PIDs / own containers.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development runs are not campaign results; never count them in paper metrics.
- Ask before pushing; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies in concise Simplified Chinese.
