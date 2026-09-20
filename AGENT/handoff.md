# Handoff

Updated 2026-09-20 (F81-F87). First read `AGENT/research_content.md` and `AGENT/execution_plan.md`.
Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts, evidence, verification
and hard boundaries. No Mission B-specific skill/tool, hidden solution hint, numeric tuning or recovery graph.
Order in force: **Mission B done → press live → Mission A → baselines/freeze/experiments**.

## Heads (all clean)

research `feat/manipulation-contracts`, openral `feat/manipulation-contracts`, SRB `feat/lunar-base-scene`.

## Mission B is complete end to end (ga8, F87)

    RESULT {"oru_on": "pdu_1_shelf/shelf", "delivered": true, "success": true}   CHECK_EXIT 0

pick 179.52 (`item_held`, jaw 0.170, first attempt) -> carry (`item_still_held`, jaw 0.171) -> place 332.92
(`item_placed`, jaw 0.82) -> stow -> dock, map error 0.019 m. Before today: pick worked, carry always lost the
load inside the first metre, `place` had never been reached.

## The ten defects, by kind (F81-F86 carry the detail)

- **The simulator's action boundary.** Every `cmd_vel` rebuilt the whole action vector through the *teleoperation*
  mapping and kept only `_held_mask` dimensions; only the Bool gripper was masked, so the first cmd_vel of each
  drive switched the arm out of joint-position mode and zeroed its targets. `hold = True` for every term. **This
  was the carry.** (F81)
- **The harness withholding what it knew.** `held_item` answered with a camera clamped to the handle, which cannot
  see the payload; the boundary's own record of the pick it dispatched is now returned beside it (F82). Every place
  point carries a surveyed outward normal that `place` was never given, so a refused over-pose had no direction to
  move in (F85).
- **Geometry, found by computing not inferring** (F86). A prop's box was built from how tall it is rather than where
  it is (shelf 16 cm low, PDU panel 60 cm low); the shelf was 0.6 m deep against a 0.485 m envelope with a wall
  behind it; the handle's bars occluded the slot they bound, leaving 8.7 mm of neck where the search needs 14.
- **The harness's own numbers wrong about themselves.** One constant serving as both the seat depth and its
  tolerance; a transient swing tolerance spent as a sustained one; a turn taking the whole budget the comment above
  it split in half; an orphaned contact-scene freeze refusing every later operation.
- **The payload interface.** F49 gave the T-handle form closure against a vertical pull and left rotation to
  friction; ga4 rolled it 23.7 deg round the neck during a turn and lost it. A collar below the slot makes the
  fingers captive (F83/F84).

The model's side needed no correction at any point.

## Not verified yet

- **The collar through a turn.** ga8's route did not pivot with the load. The stop is geometric (roll limited to
  10.5 deg, where the neck still presents 14.3 mm to jaws holding 14.95) but it has not met the 23.7 deg case.
- **`CARRY_SUSTAINED_YAW_RAD_S = 0.15`** is a separation read off one failure and two successes, not a derivation.
  With the collar in place it may not be needed at all; it is owed either a second measurement or removal.
- **The contact-scene reclaim** has not been triggered since it was written.
- **The PDU panel's box grew from 0..0.52 to 0..1.12** (its real extent). That is correct, and it is a new obstacle
  in front of Mission A's `press`, which has not run since.

## Method rules earned (both are memory)

- **Look at the pictures first, then measure.** Four wrong hypotheses came out of the bags in one day; 44 wrist
  frames showed the load being flung in one glance (F81). Record the chassis camera too -- the wrist camera cannot
  see the rover.
- **A question about whether one solid fits on another is arithmetic over data the repository holds.** Three of
  ga8's ten defects were sitting in the asset files (F86). `$CLAUDE_JOB_DIR/tmp/shelf_fit.py`, `jaw_pocket.py`,
  `jaw_width.py`, `replay_find.py` are the instruments; keep using them before a simulator.
- **Read your own code back before running it.** This session it caught a collar placed off the old pedestal
  origin, `self.geom` undefined in the place skill, and a mesh bound taken after the scale proxy joined the scene.

## Development loop without rebooting Isaac (F65/F66)

Skills run in `openral_rskill_ros/runtime_node`, which caches imports: restarting the capability server alone does
not reload them, and an SRB or asset change needs the whole graph rebooted.

1. Stop the attach parent, check and agent by explicit PID; confirm none survived. **Then confirm `ros2 node list`
   is empty** -- a leftover `planning_scene` from an earlier graph published TF frozen at its last clock and cost
   ga3 the whole run. Clear the ros2 daemon too; it caches a node list that no longer exists.
2. Recorder first (topics as in `ga8/`, QoS file `record_qos.yaml`, **including `/openral/cameras/front/image`**).
3. Attach: `D0_RESTART_RUNTIME_PID=<pid> [D0_RESTART_BOUNDARY=1] D0_CHECK=ours_mission_check.py OURS_MISSION=b`
   `[OURS_RESUME_FROM=<log> OURS_RESUME_BEFORE_STEP=<n>] setsid nohup attach_d0.sh <graph> <newlog>`.
4. Fresh graph: `D0_CAPABILITY_SERVER=1 D0_HOLD=1 D0_CHECK=ours_mission_check.py OURS_MISSION=b`
   `setsid nohup run_d0.sh <absolute log dir>`. Teardown by tag: `teardown_d0.sh <graph log>`.
5. Only jaws-open snapshots restore: ga8's `before_step_9` (sim_t 96.4) is the point before the pick.
6. Analyse only closed bags. `/usr/bin/python3.10` for rosbag2; `openral/.venv/bin/python` for the skills.
   ROS env: `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` plus `fastdds_large_shm.xml`.

Asset or scene change: `process/process.py --only <names>` then `scene/build_scene.py`, then a full graph reboot.
The scene builder's `problems` list is a real check -- it refused a deeper shelf that reached into the rover's
own work pose.

## Established context

- Ours completed Mission A covered before the new manipulation stack (oa2); record-based restart worked (rs1).
- Press is built but has never pressed a button live; Mission A's ready/stand deadlock is unresolved (F62 §3).
- PLEXIL Release 6 builds and runs Mission A covered through the common boundary (F52); EUROPA not started.
- `oru_on`/`crate_on` name a support only when the item is **not** in the gripper (`on_support`'s `free` term).
- The gripper command is a Bool, not a position: the jaw reading is what the fingers close on, and it rising means
  something is prying them apart. Its drives sit at their 4.0 N.m limit the whole time an item is held -- which is
  3-4x the real EG2-4C2's 0-20 N. The user's decision is to keep it (lunar equipment is not a catalogue part) and
  give the interface form closure instead.

## Operational rules and locations

- One simulation only. All paths absolute. No `pgrep -f` / `pkill -f`; kill explicit PIDs and verify.
- Never navigate on simulator truth. `/odom` is wheel-inertial; AMCL on the lidar-surveyed map; Nav2 goals map-frame.
- Simulator truth is evaluator/diagnosis only, never control, prompts, guards or verifiers.
- Whole-operation tools only; mechanics stay inside skills. A skill retries the same target, never moves the base.
- Model-facing services use DeepSeek's own endpoint; keys in `AGENT/VLM_provider.md` never enter logs or output.
- Boundary: `openral_ext/capability_server/{contracts.yaml,contracts.py,node.py}`. Ours: `space_runtime/`.
- Logs: `<log>/ours/events.jsonl`, `capability_server.log`, `runtime.log`, `check.log`, `snapshots/`,
  `robot_motion/` (bag); skill evidence under `<graph log>/evidence/`.
- Development resumes/edits are not campaign results; never count them in paper metrics.
- Keep this file and todo.md <=150 lines, overwrite at milestones. No hashes, defensive corner-case code, broad test
  campaigns or unrelated refactors. Replies to the user in concise Simplified Chinese.
