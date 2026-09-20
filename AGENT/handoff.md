# Handoff

Updated 2026-09-20 (F79/F80). First read `AGENT/research_content.md` and `AGENT/execution_plan.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence, verification
and hard boundaries. No Mission B-specific skill/tool, hidden solution hint, numeric tuning or recovery graph.
Order in force: **finish Mission B → press live → Mission A → baselines/freeze/experiments**.

## Heads (all clean)

research `feat/manipulation-contracts`, openral `feat/manipulation-contracts`, SRB `feat/lunar-base-scene`.

## What changed today, and why it matters to the paper

Three of the day's four faults were measurements; the fourth was the architecture, and that is the contribution.

1. **`site/depot_stand` was bounded at its back lip's height** (0.610) rather than its table (0.55), so an item on a
   slot began 6 cm inside the obstacle. A prop that declares a working surface is now bounded there.
2. **The held item was checked as a prism swept over every yaw** (0.597 m square against a 0.45 x 0.392 unit). Four
   bags say the ORU does not turn in the jaws and pivots at most 15.4 deg; it is checked as the box it is.
3. **`find` guessed where to point the camera** -- a fixed chassis overview, a 5 cm height map, the tallest cell
   within 0.2 m of a blob, 24 viewpoints aimed at that. One level view now, because an upright neck shows the width
   the jaws close on from the side and not at all from above. 5.7 s against 92 s. 99 lines of dead code removed.
4. **The boundary chose where to park and never said what the choice cost.** It takes the roomiest stand its reach
   model offers: 0.96 m at the depot, where the arm reaches the handle and can only look from 20 deg above, and from
   above the head hides the neck. Four predicates over the nominal work point could not tell that stand from the
   1.10 m one every successful pick had used. **`work_stands`** reports instead of deciding: per distance, whether
   the tool reaches and the shallowest look, and the `standoff_m` that parks there. `dock_at_feature` says its
   default is chosen for reach alone.
5. **The body the robot stands on is now a published fact.** `env0/space_context` (SRB, latched) carries the domain
   and its gravity; the boundary derives the carry limits from it (`a = g tan(theta/2)`, theta the swing the grasp
   was measured to take) and exposes the same fact for reasoning. Moon 0.071 m/s^2, Mars 0.163, asteroid 0.006, no
   code change. Unknown bodies fall back to the *least* gravity, never Earth's.

**The model uses all of it, unprompted.** It computes the grasp height as the place frame's z plus the catalogued
handle height (1.017, exact, offline and live), reads "a neck under an overhanging head", asks `work_stands`, docks
at `standoff_m` 0.12, and writes the reason into its own ledger. In g9x that produced the first pick that works end
to end: one view, one candidate, `bring_in` over **0.30 m without stalling** (0.228 was the best before, 0 in g9m),
`item_held` verified.

## Where it stands

- **pick: solved and verified** (g9x).
- **carry: was the day's last failure and is what ga1 tests.** g9x lost the ORU on the first drive: the jaw was
  never commanded open, the load swung to 51 deg and came off the neck 0.44 m from the slot. The bag says why --
  0.5 m/s^2 is 17 deg of lean at lunar gravity, the angular allowance added another 0.50 m/s^2 at the 0.787 m lever
  and 1 rad/s of turn another 0.79, and the jaw was untouched to 10.7 deg and opening by 16.3. The limits are
  derived now; ga1 is the run that says whether that is enough.
- **Never reached yet:** place on the new shelf, stow, return dock.

## Method rules earned today (both are now memory)

- **Settle it offline before a simulator runs.** The IK rule and the view sweep against the live MoveIt; the
  detector replayed on the run's own saved depth; the reasoner's inference asked of the real model with the real
  records (`$CLAUDE_JOB_DIR/tmp/ask_reasoner.py`, `ask_stand.py`, `ask_plan.py`, `ask_gravity.py`). Each found
  something in seconds that a run would have cost 20 minutes to find -- including an ambiguous query interface the
  model reasoned correctly about and then mis-filled.
- **Read your own code back before running it.** Two runs were lost to a `#` comment inside an embedded JSON block
  and a path passed where an image array was expected. Both were visible on a second reading.

## Live processes

Graph `artifacts/runs/ga1` (held), run `ga1`. Isaac, runtime_node, planning_scene, capability_server, recorder.
Recheck with `ps -eo pid,ppid,args` before any control; stop the attach parent, then check, then agent, by PID.
Skill evidence lands in the *graph's* log dir, not the run's.

## Development loop without rebooting Isaac (F65/F66)

Skills run in `openral_rskill_ros/runtime_node`, which caches imports: restarting the capability server alone does
not reload them, and an SRB change needs the whole graph rebooted.

1. Stop the attach parent, check and agent by explicit PID; confirm none survived.
2. Recorder first (topics as in `ga1/`, QoS file `record_qos.yaml`), then
   `D0_RESTART_RUNTIME_PID=<pid> [D0_RESTART_BOUNDARY=1] D0_CHECK=ours_mission_check.py OURS_MISSION=b`
   `[OURS_RESUME_FROM=<log> OURS_RESUME_BEFORE_STEP=<n>] setsid nohup attach_d0.sh <graph> <newlog>`.
3. A fresh graph: `D0_CAPABILITY_SERVER=1 D0_HOLD=1 D0_CHECK=ours_mission_check.py OURS_MISSION=b`
   `setsid nohup run_d0.sh <newlog>`. Teardown by tag: `teardown_d0.sh <graph log>`.
4. Only jaws-open snapshots are valid restore points, so a failure after the grasp costs the whole pick again.
5. Analyse only closed bags. `/usr/bin/python3.10` for rosbag2; `openral/.venv/bin/python` for anything importing
   the skills. ROS env: `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` plus `fastdds_large_shm.xml`.
Attach and run execute a frozen copy in the run directory: never edit a script that is executing.

## Established context

- Ours completed Mission A covered before the new manipulation stack (oa2); record-based restart worked (rs1).
- Press is built but has never pressed a button live; Mission A's ready/stand deadlock is unresolved (F62 §3).
- PLEXIL Release 6 builds and runs Mission A covered through the common boundary (F52); EUROPA not started.
- `oru_on`/`crate_on` name a support only when the item is **not** in the gripper (`on_support`'s `free` term).
- The gripper command is a Bool, not a position: the jaw reading is what the fingers close on, and it rising means
  something is prying them apart.

## Operational rules and locations

- One simulation only. All paths absolute. No `pgrep -f` / `pkill -f`; kill explicit PIDs and verify.
- Never navigate on simulator truth. `/odom` is wheel-inertial; AMCL on the lidar-surveyed map; Nav2 goals map-frame.
- Simulator truth is evaluator/diagnosis only, never control, prompts, guards or verifiers.
- Whole-operation tools only; mechanics stay inside skills. A skill retries the same target, never moves the base.
- Model-facing services use DeepSeek's own endpoint; keys in `AGENT/VLM_provider.md` never enter logs or output.
- Boundary: `openral_ext/capability_server/{contracts.yaml,node.py}`. Ours: `space_runtime/`.
- Logs: `<log>/ours/events.jsonl`, `capability_server.log`, `runtime.log`, `check.log`, `snapshots/`,
  `robot_motion/` (bag); skill evidence under `<graph log>/evidence/`.
- Development resumes/edits are not campaign results; never count them in paper metrics.
- Keep this file and todo.md <=150 lines, overwrite at milestones. No hashes, defensive corner-case code, broad test
  campaigns or unrelated refactors. Replies to the user in concise Simplified Chinese.
