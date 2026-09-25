# Handoff

Updated 2026-09-24 night (step 9, its live checks and the 1.5 m blocker done, F115; next: step 10). Read `AGENT/research_content.md` and
`AGENT/execution_plan.md` first, then **`docs/heldout_design.md`** (the current plan; §14 = the campaign instances), **`docs/baselines/authoring_spec.md`**
(the locked baseline specification), then `AGENT/todo.md`, then `docs/research_findings.md` F108-F115.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Heads

- research `main`, openral `master`, SRB `main`: committed 2026-09-24 (F114 fixes). No feature branches/worktrees.
- **Step 9 done (F115): 18/21, the three failures shared-layer and fixed.** Live checks done (artifacts/runs/check{1,2}).
  Blocker fixed: the shared 1.5 m (approach point, dock corridor entry, inserted undock; PLEXIL plans, EUROPA domain)
  drove the rover into the return stand leaving the depot spares stand -> 1.2 m everywhere (offline: 0 hits over 28
  features; live verify12: delivered, no non-wheel contact). The audit's other items (fixed arm retreats, press fold, unsourced thresholds) stay (user).
- **Step 10 stopped at 4/6 (F116-F118)**: runs `artifacts/runs/step10_r{1,2,3}`. Solved L2-A x2, L3 x2; L2-B and L4
  unsolved on the model's reasoning after three generic fixes (place verifier; time/link/decision time/approval
  mechanics in the snapshot). L4 round 4 by day (51 s/step): still no transfer idea. L2-B offline (F119): Kimi-K3
  plans the relocation 4/6, the live model places onto the occupier. Live (F122): Qwen3.8-Max solves L4, Kimi-K3
  solves L2-B. **Reasoner is now Qwen3.8-Max (F123, user).** Next: model-facing texts into files
  (docs/prompt_text_design.md), then Qwen on the six held-out states. Session B (pre-freeze infra) works in
  `.worktree/prefreeze` (docs/prefreeze_workorder.md, findings F130+, GPUs 4-5).
- PLEXIL adapter rebuilds need `export PLEXIL_HOME=$HOME/Programs/plexil` in the container.
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

- Never regenerate SRB assets or the scene (USD, textures, interaction.json) while any simulation runs: Isaac reloads a
  changed layer and aborts ("unlock() called by non-owning thread") -- three check runs died at the second
  oru_0417.usdc was rewritten (2026-09-24).
- No hard-coded distances or blind straight-line motions in the shared layer, and no action the boundary inserts
  on its own without the method seeing it (user, 2026-09-24; the 1.5 m undock into the return stand, F115).
- Name the other body of a contact only from ground-truth poses + the site layout, never from the link name
  (F115: "palm rubs the battery" and "steering link on the ground" were both wrong).
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
