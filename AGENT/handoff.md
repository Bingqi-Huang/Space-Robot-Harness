# Handoff

Updated 2026-09-19 (F78). First read `AGENT/research_content.md` and `AGENT/execution_plan.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence, verification
and hard boundaries. No Mission B-specific skill/tool, hidden solution hint, numeric tuning or recovery graph.
Order in force: **finish Mission B → press live → Mission A → baselines/freeze/experiments**.

## Two sessions now run in parallel (user, 2026-09-19)

- **Session M (manipulation, live sim):** owns the one running simulation and Mission B pick/carry/place.
  Owns these files: `openral/python/rskill/src/openral_rskill/{_eye_in_hand,procedural_pick,procedural_place,
  grasp_perception}.py`, pick/place manifests, `openral_ext/planning_scene/`, pick/place contract lines,
  `space_runtime/facts.py`, `experiments/launch/lunar_base_d0/{attach_d0.sh,run_d0.sh,ours_mission_check.py,
  restart_runtime.py,teardown_d0.sh}`, SRB `assets/lunar_base/`. Baseline code: `baselines/plexil/`,
  `experiments/launch/lunar_base_d0/d0_plexil_*` (free for Session P).
- **Session P (parallel, offline only):** takes the "Parallel track" in `todo.md`. It must not start or attach to a
  simulation, must not touch processes or the live graph, and must not edit Session M's files.
- **Never `git checkout`/switch branches in the main working tree**: the live graph imports OpenRAL from
  `openral/python/...` (editable) and `openral/install/`. Session P works in worktrees inside the repo:
  `git worktree add .worktree/<name> -b p/<name> <base>` (`.worktree/` is gitignored). Merge back through the user.
- Findings: Session P used F79–F81 (on `p/integration`); renumber on merge if Session M took them meanwhile.

## Session P state (2026-09-20)

- **Integration branch `p/integration`** (`.worktree/integration`) holds all Session P work, merged from
  `p/plexil-mission-b`, `p/europa`, `p/eval-infra`. **Not merged into `feat/manipulation-contracts`** (user):
  merge after Session M finishes Mission B, then delete the merged `p/*` branches/worktrees and the stale
  `feat/g0-wrist-rgbd`, `fix/mission-operation-evidence` (todo). Merge touches `ros/plexil_capability_adapter`
  (rebuild it) and `openral_ext/run_manifest/`.
- PLEXIL (F79): Mission B covered plan on library nodes, nominal path only (`plexiltest`); recovery set waits for
  pick/place failure kinds. Mission A keeps stage-level tools until `press` is fixed (user).
- EUROPA (F80): native build in `~/Programs/europa`, deps `~/Programs/europa-deps`; generic host/bridge verified on a
  base-only skeleton domain. Mission B domain waits for the manipulation contracts.
- Evaluation (F81): manifests, run manifest/freeze (dry-run), metrics rows/tables, console, PLEXIL normalizer, worklog.
- Also merged: operator pause-for-answer mechanism + protocol (`docs/operator_protocol.md`), evaluator violations
  (`docs/evaluator_violations.md`, `experiments/evaluator_recorder/`). Nothing running. Merge-time work: todo 3b–3d.

## Where Mission B stands (F78, `docs/research_findings.md`)

Committed heads: research `feat/manipulation-contracts`, openral `feat/manipulation-contracts` 0179a1d,
SRB `feat/lunar-base-scene` 6839574. Workspaces clean.

- **Principle (user):** a skill check that cannot certify is evidence, not a veto; confirmed problems return typed
  facts and the model recovers (retry / re-observe / re-dock). Never per-task tuning; never mechanical parameters
  to the model (execution_plan §8.2). Memory: `feedback-checks-fall-back-to-harness`.
- **Close-in fixed:** g8q's stall was the sag integral + null-space posture pull under 0.3–1.4 s joint lag
  (bag + FK replay). Empty-jaw close-in now runs without both (openral f925430).
- **Pick results on that code:** g8s ✓ and g8t ✓ (neck, lift, carry, dock PDU-1 held); g8r ✗ VLM chose the 27 mm
  pedestal; g8u ✗ zero-triangle contact permission (now evidence, not a veto). g8v (running) first pick again chose
  the pedestal (27.8 mm) and lost track; the model observed and retried with a clearer part description.
- **Carry root cause:** bring_in pulled the hanging ORU onto the rover's rear deck (13–93 mm overlap all carry):
  joint lag 0.4–0.75 rad, ORU pivot 16–32°, jaws pried to 0.23. State validity never saw the item. Now the catalogue
  envelope is attached in every validity check while held; bring_in may raise first (openral 0179a1d).
- **Place root cause:** `over` swept at carry height, and the old shelf left 2.4 cm behind a centred ORU; g8s/g8t hit
  the back strip (g8t dropped it). Shelf now 0.60 x 0.72 m, place point at plate centre (SRB 6839574); place lifts
  the envelope over the support; over tolerance 3 cm / 0.08 rad. Evaluator window unchanged (already wider).
- **Boundary:** pick/place take an optional catalogue `item` → `held_item` envelope for the skills.
- **Not yet validated live:** envelope, raised bring_in, new place, new shelf. Needs a fresh graph (old shelf loaded).
- Still open: selection has no width-vs-catalogue check (the model now sees `selected_mark` width/range);
  servo command wind-up at a joint stop; stow + return dock never reached.

## Live processes (Session M only)

- Graph `artifacts/runs/g8m_contact` (Isaac 1044122, old shelf). runtime_node 1505904, planning_scene 1504068.
- g8v: agent/check running without STOP_ON_FAILURE from g8b before_step_10; a background monitor stops it after a
  verified dock at PDU-1 and closes its recorder. Recheck with `ps -eo pid,ppid,args` before any control.
- Evidence of g8s–g8v sits under `artifacts/runs/g8r/evidence/` (the runtime restarted in g8r keeps its log dir).

## Development loop without rebooting Isaac (F65/F66)

Skills run in `openral_rskill_ros/runtime_node`, which caches imports: restarting only the capability server does
not reload skills. The planning-scene node is separate as well.

1. Stop the old attach parent, check and agent by explicit PID; confirm none survived.
2. `openral/.venv/bin/python experiments/launch/lunar_base_d0/restart_runtime.py <pid> <graph> <newlog>` restarts
   runtime_node or `planning_scene/node.py` with its real argv/env/cwd (records `<name>_restart.json`).
3. Recorder first (topics as in `g8v/`, QoS file `record_qos.yaml`), then
   `D0_RESTART_RUNTIME_PID=<pid> OURS_MISSION=b [OURS_STOP_ON_FAILURE=1] OURS_RESUME_FROM=<log>`
   `OURS_RESUME_BEFORE_STEP=<n> setsid nohup <repo>/experiments/launch/lunar_base_d0/attach_d0.sh <graph> <newlog>`.
   ROS env for manual tools: `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
   `FASTRTPS_DEFAULT_PROFILES_FILE=<repo>/experiments/launch/lunar_base_d0/fastdds_large_shm.xml`.
4. Check `RESTORED_ARM` in `check.log`. Only jaws-open snapshots are valid restore points (a grasp cannot be restored).
5. Fixture used for pick: `artifacts/runs/g8b/snapshots/before_step_10.pt` (docked at depot slot 0, jaws open).
6. Analyse only closed bags (stop the recorder with SIGINT). System ROS python: `/usr/bin/python3.10`.
Attach executes a frozen copy in the run directory: never edit a script that is executing.

## Established context

- Ours completed Mission A covered before the new manipulation stack (oa2); record-based restart worked (rs1).
- g8d earlier placed and released on the old shelf; the release retreat constraint `below_overhang` exists (F73).
- Press is built but has never pressed a button live; Mission A's ready/stand deadlock is unresolved (F62 §3).
- PLEXIL Release 6 builds and runs Mission A covered through the common boundary (F52); EUROPA not started.

## Operational rules and locations

- One simulation only (Session M). All paths absolute. No `pgrep -f` / `pkill -f`; kill explicit PIDs and verify.
- Never navigate on simulator truth. `/odom` is wheel-inertial; AMCL on the lidar-surveyed map; Nav2 goals map-frame.
- Simulator truth is evaluator/diagnosis only, never control, prompts, guards or verifiers.
- Whole-operation tools only; mechanics stay inside skills. A skill retries the same target, never moves the base.
- Model-facing services use DeepSeek's own endpoint; keys in `AGENT/VLM_provider.md` never enter logs or output.
- Wrist intrinsics/extrinsics from CameraInfo/TF; jaw bands shared from `_eye_in_hand`.
- Boundary: `openral_ext/capability_server/{contracts.yaml,node.py}`. Ours: `space_runtime/`.
- Logs: `<log>/ours/events.jsonl`, `capability_server.log`, `runtime.log`, `evidence/`, `check.log`, `snapshots/`,
  `robot_motion/` (bag).
- Teardown: `<repo>/experiments/launch/lunar_base_d0/teardown_d0.sh <absolute graph log>`.
- Development resumes/edits are not campaign results; never count them in paper metrics.
- Keep this file and todo.md ≤150 lines, overwrite at milestones. No hashes, defensive corner-case code,
  broad test campaigns or unrelated refactors. Replies to the user in concise Simplified Chinese.
