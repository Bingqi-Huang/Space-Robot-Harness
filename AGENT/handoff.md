# Handoff

Updated 2026-09-29 evening. Exp I, Exp II done. Ablations (F148-F150): stages 1-2 done; stage 3 (6 live runs) and the
re-authoring study's live validation (F149) wait for the model gateway (account refused, user recharging). Swimlane fix
done; paper results draft in `paper/`. See AGENT/todo.md. Nothing pushed (research main ahead of origin; SRB 1).

Read `AGENT/research_content.md`, `AGENT/execution_plan.md`, **`docs/heldout_design.md`** (§6 Exp II, §8 protocol, §14
instances), **`docs/baselines/authoring_spec.md`** (locked baselines), **`docs/preregistration.md`** (metrics,
taxonomy, exclusion), `AGENT/todo.md`, then `docs/research_findings.md` F130, F131, F136, F140-F150. Goal: the Acta
Astronautica paper (H1 no rewrite for unplanned situations, H2 less engineering to add a capability, H3 open reasoning
inside hard boundaries). The model owns mission strategy; a thin harness owns facts, evidence, verification and hard
boundaries. Simulator truth is for evaluation / post-hoc diagnosis only, never a decision.

## Results so far

- **Experiment I = exp1b** (F142): Ours covered 7/7, held-out 18/18, 0 ground re-authoring; PLEXIL and EUROPA->PLEXIL
  covered 7/7, held-out 0/6 (every run detected -> escalated -> hold). False completions 0; guard held 3 (L4 donor
  picks), 0 executed despite a hold; no physical-layer failure. `artifacts/runs/exp1b/`, `artifacts/eval/exp1b/`
  (tables, failures, place offsets, trace completeness), `artifacts/figures/exp1b/` (swimlanes, six textured
  third-person videos). F143: PLEXIL N = 1/2/3/5 on derived plans never changes the outcome; a drop = a fall.
- **Experiment II** (F144-F147; new shared capability `scan_label`, Data Matrix serials by the wrist camera): each
  extension by a fresh autonomous Claude session that saw only `docs/exp2/extension_spec.md` + G3, timed, order Ours ->
  PLEXIL -> EUROPA, each from the previous merged state. All passed G3 on the first validation run. Active 54.5 / 46.3
  / 53.4 min, of it not waiting on the simulation 4.7 / 10.8 / 20.8. Ours registered the capability and made its
  reading a verified fact (no procedure); PLEXIL wrote check -> record-guided search -> 13-support sweep -> escalate;
  EUROPA modelled identity + a sensing activity, candidate narrowing in the host. Held-out (H1 mislocated spare, H2
  swapped records): before the extension 0/6 (Ours' two reports false completions); after it Ours 6/6, PLEXIL 2/2,
  EUROPA 2/2. Fixes found in the held-out runs, applied for all methods, only the runs they decided rerun (user rule):
  F145 wider scan view, F147 on-support fact + Ours' step budget counts calls on the robot (not plan bookkeeping).
  Tables `python3 experiments/exp2/tables.py` -> `artifacts/eval/exp2/tables.md`; cases, chains, launch lines
  `experiments/exp2/heldout/`; runs `artifacts/runs/exp2/{setup,g2_physical,validation,pre,post,post_superseded,checks}`.
- Paper-relevant facts: the Exp I system is tag `exp1b`; Exp II's final system adds F144-F147. Claude engineers compress
  coding time (user: a human-engineer round "plan B" not now). Ours' H1 search is less systematic than PLEXIL's sweep.
  rows.py's ledger rule cannot see a false completion when the report is the plan's still-active last task; the Exp II
  table reads the reports (`CLAIMS` in tables.py).

## Ablations (F148)

- Paper framing (user 2026-09-29): trustworthy AI -- the harness is what makes the model's autonomy safe; an FM embedded
  in the space-robot workflow that keeps the established engineering disciplines. Not "an LLM calling tools".
- Variants (`OURS_ABLATION`: no_facts / no_verification / no_guard / no_context; texts in `prompts/ours_ablation/`);
  unset = full, byte-identical (`experiments/ablation/render_check.py`). Accidents J1-J4 + natural N/NF
  (`accidents.py`); `stage1.py`; `stage2.py` (plan calls and static queries carried forward offline); `stage2_score.py`.
- Containers for the offline scripts: `runfarm:22.04`, `--dns 223.5.5.5 --dns 119.29.29.29` (the host DNS is fake-IP;
  without it the gateway times out), openral venv python, ROS + openral/install + worktree ros/install sourced.
- Live (stage 3): a restore puts a held item out of the jaws (F60) -- that is J1's drop; J3 live only at points with
  nothing held; J4 live with `SPACE_LINK_LOS_S=0` (link.py, env-gated), from r1/r2. Resumed runs start a new sim clock.

## Heads

- Tags: `freeze-1` (history), `exp1b` (Exp I; the ablations start here), `exp2-base`, `exp2-base-plexil`,
  `exp2-base-europa`, `exp2-ours`, `exp2-plexil`, `exp2-europa_plexil` (each method's extension base / result).
- Branches: research `main` (+ `feat/prefreeze-infra`, kept by the user), openral `master`, SRB `main`.
- **Reasoner Qwen3.8-Max** (configs/space_runtime.yaml, 600 s), VLM DeepSeek-V4.1-Flash, paratera gateway; key = the
  first `sk-` in `AGENT/VLM_provider.md` (gitignored; never print it, never write it anywhere).
- **What the reasoner reads** (F124): `prompts/ours/{system,step}.md`, `prompts/ours/tools.yaml`; `space_runtime/
  context.py` only fills them. Palette = every non-engineering contract in `openral_ext/capability_server/contracts.yaml`.
- **Mission control** (F125, console.py): answers by request kind + held calls; only `new_procedure` = re-authoring.
- **scan_label** (shared): `openral_ext/scan_label.py` via `CapabilityServer.scan_label`; widest of three views the arm
  can take (F145); `something_on_support` from the wrist depth (F147). zxing-cpp is in the openral venv.
- Mission B knobs (SRB): `env.name_serial`, `env.placement` / `env.records` ("obj:place_frame+..."); ORU-0272 (failed,
  landing_stand/slot_1) is a second identical ORU; `status` is an authored object field.
- Evaluator: rows -> tables (`python3 -m evaluation.rows --out <dir> <run dirs>`, then `evaluation.tables`, system
  python3); a call's window starts at the evaluator's sim->wall record (F142). Figures: `experiments/video/`.
- Experiment II engineer checkouts: `experiments/exp2/make_worktree.sh <method> <base>` (submodules as worktrees, links
  for venv/install/kernels/key, ros built there); removed after merging.
- Resume from a snapshot (`snapshots/before_step_<n>.pt`): `OURS_RESUME_FROM=<run dir> OURS_RESUME_BEFORE_STEP=<n>` on
  run_d0.sh; development only, never scored.
- PLEXIL: adapter rebuild `colcon build --merge-install --packages-select plexil_capability_adapter` from `ros/` in a
  pinned container with `PLEXIL_HOME=$HOME/Programs/plexil`, `$HOME/Programs` mounted, openral's install sourced;
  offline `baselines/plexil/scripts/offline_check.py` (plexil-setup.sh). EUROPA offline:
  `baselines/europa/run_offline_mission_{a,b}.sh` (`docker run --init`).

## Run farm (pro6000, host astroeng, uid 1007; heldout_design §11)

- Repo at `/mnt/SharedData/Research/Space_Robot_Harness` (bind mount of `/nvme02/bingqi/SharedData`; never `/nvme01`).
- **One run = one container** on one GPU: `docker/runfarm/runfarm.sh <gpu> <name> "<env> <abs>/run_d0.sh <abs run
  dir>"`; ROS domain 77 + GPU. Two containers on one GPU share a domain and break each other -- also while one is
  still tearing down: launch on a GPU only when `docker ps` shows no container there.
- Batches: `tmux new-session -d -s <name> "experiments/launch/lunar_base_d0/farm_queue.sh <jobs> <run root> '<gpus>'"`;
  `farm_join.sh` (run it with `bash`) adds a GPU worker. A worker re-reads the jobs file and `.next` at every claim:
  never touch a run root's `.next`/`.lock` or move its run dirs until its queue.log says "queue done" (F147: a
  duplicate run started that way).
- Throwaway containers (builds, offline checks): no GPU, `--cpuset-cpus 30,31,62,63`, `nice -n 19`.
- Speed: sim/wall ~0.2 with six at once; Ours covered ~10-15 min wall, held-out 0.5-1.5 h (Exp II H1 searches ~1 h).
- sudo needs the user's password; never touch kernel/GRUB/daemon. Physics stays CPU PhysX (user decision).

## Running it

Jobs line = `<run name> <env assignments>`. Ours: `D0_CAPABILITY_SERVER=1 D0_CHECK=ours_mission_check.py`; PLEXIL:
`D0_CHECK=d0_plexil_mission_{a,b}_check.py`; EUROPA: `D0_CHECK=d0_europa_mission_{a,b}_check.py`; with `D0_SCENE=
scenes/deploy/srb_lunar_base_mission_{a,b}.yaml`, `D0_SCENARIO=...`, `D0_ENV='env.cargo=... env.destination=...'`.
Scripted chains: `D0_CHECK=scripted_chain_check.py CHAIN_JSON=<abs json>` (3 attempts per call). Scene:
`assets/lunar_base/scene/build_scene.py` (`--interaction-only` for dynamic objects only); map survey only when the
structural footprint changes. Judge a run by `CHECK_EXIT` / `RESULT` / `CHAIN_DONE`; teardown tracebacks are noise.
`run_manifest.yaml` is written after teardown (read-only backfill, run_d0.sh's last step).

## Method rules earned the hard way

- Never regenerate SRB assets or the scene while any simulation runs (Isaac aborts on a changed layer).
- Never edit shared skill modules (openral rskill) while runs are live; capability server / contracts load at start.
- No hard-coded distances or blind straight-line motions in the shared layer; nothing the boundary inserts unseen.
- Name the other body of a contact only from ground-truth poses + the site layout, never from the link name.
- Look first (evidence images, frames), then numbers; never open a live bag; `experiments/analysis/` has the tools.
- A scripted chain reads the contracts when it starts: a temporary contract entry must stay until the check starts.
- Killing a check mid-navigation: cancel `/navigate_to_pose/_action/cancel_goal` (all-zero goal_id) first.
- PLEXIL: `if/endif` on live state, never SkipCondition; root `UncheckedSequence` so escalation can run.
- `git merge -F -` does not read stdin: write the message to a file. `rm` with a variable path is refused by the
  harness: use literal paths.

## Rules

- All paths absolute. Kill only positively identified own PIDs / own containers.
- Never navigate or decide on simulator truth. Whole-operation tools only; mechanics stay in skills.
- Development runs are not campaign results. Fixes found in a campaign: fix for all methods, record in findings,
  rerun only the runs they decided (user rule); no freeze ceremony.
- Ask before pushing; ask before deleting a run directory that might still be evidence.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies in concise Simplified Chinese.
