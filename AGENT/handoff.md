# Handoff

Updated 2026-09-20 (F79). First read `AGENT/research_content.md` and `AGENT/execution_plan.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence, verification
and hard boundaries. No Mission B-specific skill/tool, hidden solution hint, numeric tuning or recovery graph.
Order in force: **finish Mission B → press live → Mission A → baselines/freeze/experiments**.

## Heads (all three workspaces clean)

research `feat/manipulation-contracts` da94760, openral `feat/manipulation-contracts` fbb33c9,
SRB `feat/lunar-base-scene` 12203ba.

## Where Mission B stands (F79, `docs/research_findings.md`)

**Solved today.** Selection (candidates filtered to what measures as the declared contact — the VLM is no longer
offered the 27 mm pedestal), closure by three separate direction budgets, the lift (joint servo + damping per the
spec sheet), place's shelf and over-tolerance, fragile checks turned into evidence, the carried item in every
collision check.

**The IK acceptance rule (fbb33c9).** A solution is this arm's own configuration when it is on the working branch
**or** within `BRANCH_JUMP_RAD` of the seed; refused only when neither. Each criterion alone was wrong in one
direction: the window refused poses the arm was already in (g9l), the seed distance refused every reconfiguration
seeded at `READY` and killed `find` outright (g9n). Measured offline against the live MoveIt before the run.

**g9o, the state of the chain.** pick works end to end: overview, neck selected, close-in, grasp, lift 0.154 m,
`item_held` verified. bring_in now has real heights (0.04–0.10 reachable and clear, against only 0.02 in g9m) and
travels ~14 cm instead of 0. **The carry still loses the ORU**: on the drive to PDU-1 the jaw fell 0.169 → 0.100 and
the evaluator returned `oru_on: depot_stand/slot_0`, which by its own definition means out of the gripper. The
harness caught it (`item_still_held` false on jaw + wrist image, against a skill that reported success) and the model
began recovering on its own.

**The one open question, and how to answer it.** Did the ORU ever leave the stand's support, and when did it come
down? One pass over the closed bag: evaluator `/tf` object poses plus `/srb/env0/mission_state`, plotting the ORU's
base height over the stand across grasp → hold lift → bring_in → the first metres of the drive. Insufficient raise
(IK ceiling 0.10), sag after `hold_here`, and drive acceleration need different fixes — do not guess between them.

**Still never reached:** place with the new shelf, stow, return dock.

## Live processes

- Graph `artifacts/runs/g9n` (held): Isaac 2201342, runtime_node **2208197** (fbb33c9), planning_scene 2202719,
  capability_server 2202718.
- Run `artifacts/runs/g9o`: check 2208199, agent 2208511, recorder 2207925. Skill evidence lands in
  `g9n/evidence/` (the graph's log dir), not in `g9o/`.
- Recheck with `ps -eo pid,ppid,args` before any control. Stop the attach parent, then check, then agent, by PID.

## Method rule earned today

The IK rule is a pure function of a solution, a seed and `POSTURE`. g9m and g9n each cost a graph and a pick to
learn what a read-only `/compute_ik` query on the held graph answered in seconds. **Before restarting a runtime,
exercise the changed logic offline against the live graph** (`/compute_ik`, `/compute_fk`, closed bags) and only
then run. A bench that asserts more than the code promises cries wolf — assert what the skill actually needs
(`find` takes the first posture that works; bring_in needs one height with margin).

## Development loop without rebooting Isaac (F65/F66)

Skills run in `openral_rskill_ros/runtime_node`, which caches imports: restarting only the capability server does
not reload skills. The planning-scene node is separate as well.

1. Stop the old attach parent, check and agent by explicit PID; confirm none survived.
2. Recorder first (topics as in `g9o/`, QoS file `record_qos.yaml`), then
   `D0_RESTART_RUNTIME_PID=<pid> D0_CHECK=ours_mission_check.py OURS_MISSION=b [OURS_STOP_ON_FAILURE=1]`
   `OURS_RESUME_FROM=<log> OURS_RESUME_BEFORE_STEP=<n>`
   `setsid nohup <repo>/experiments/launch/lunar_base_d0/attach_d0.sh <graph> <newlog>`.
   attach_d0.sh restarts the runtime itself with its real argv/env/cwd (records `runtime_restart.json`).
   ROS env for manual tools: `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
   `FASTRTPS_DEFAULT_PROFILES_FILE=<repo>/experiments/launch/lunar_base_d0/fastdds_large_shm.xml`.
3. A fresh graph: `D0_CAPABILITY_SERVER=1 D0_HOLD=1 D0_CHECK=ours_mission_check.py OURS_MISSION=b`
   `OURS_RESUME_FROM=<log> OURS_RESUME_BEFORE_STEP=<n> setsid nohup run_d0.sh <newlog>`; start the recorder
   alongside (rosbag waits for its topics). Teardown by tag: `teardown_d0.sh <graph log>`.
4. Check `RESTORED_ARM` in `check.log`. Only jaws-open snapshots are valid restore points (a grasp cannot be
   restored), so a failure after the grasp costs the whole pick again.
5. Fixture for pick: `artifacts/runs/g8b/snapshots/before_step_10.pt` (docked at depot slot 0, jaws open).
6. Analyse only closed bags (stop the recorder with SIGINT). System ROS python: `/usr/bin/python3.10`.
   `openral/.venv/bin/python` for anything importing the skills.
Attach and run execute a frozen copy in the run directory: never edit a script that is executing.

## Established context

- Ours completed Mission A covered before the new manipulation stack (oa2); record-based restart worked (rs1).
- The release retreat constraint `below_overhang` exists (F73).
- Press is built but has never pressed a button live; Mission A's ready/stand deadlock is unresolved (F62 §3).
- PLEXIL Release 6 builds and runs Mission A covered through the common boundary (F52); EUROPA not started.
- `oru_on`/`crate_on` name a support only when the item is **not** in the gripper (`on_support`'s `free` term):
  an empty string means held *or* airborne, a support name means released. Read it that way.

## Operational rules and locations

- One simulation only. All paths absolute. No `pgrep -f` / `pkill -f`; kill explicit PIDs and verify.
- Never navigate on simulator truth. `/odom` is wheel-inertial; AMCL on the lidar-surveyed map; Nav2 goals map-frame.
- Simulator truth is evaluator/diagnosis only, never control, prompts, guards or verifiers.
- Whole-operation tools only; mechanics stay inside skills. A skill retries the same target, never moves the base.
- Model-facing services use DeepSeek's own endpoint; keys in `AGENT/VLM_provider.md` never enter logs or output.
- Wrist intrinsics/extrinsics from CameraInfo/TF; jaw bands shared from `_eye_in_hand` (0.10 empty, ~0.17 on the
  12 mm neck, 0.33 on the bail, 0.82 commanded open).
- Boundary: `openral_ext/capability_server/{contracts.yaml,node.py}`. Ours: `space_runtime/`.
- Logs: `<log>/ours/events.jsonl`, `capability_server.log`, `runtime.log`, `check.log`, `snapshots/`,
  `robot_motion/` (bag); skill evidence under `<graph log>/evidence/`.
- Development resumes/edits are not campaign results; never count them in paper metrics.
- Keep this file and todo.md ≤150 lines, overwrite at milestones. No hashes, defensive corner-case code,
  broad test campaigns or unrelated refactors. Replies to the user in concise Simplified Chinese.
