# Handoff

Updated 2026-09-20 (F81-F91). Read `AGENT/research_content.md` and `AGENT/execution_plan.md` first, then
`AGENT/todo.md`. Goal: the Acta Astronautica paper. The model owns mission strategy; a thin harness owns facts,
evidence, verification and hard boundaries. No Mission B-specific skill, hidden hint, numeric tuning or recovery
graph.

## Heads (all clean, all committed)

research `feat/manipulation-contracts`, openral `feat/manipulation-contracts`, SRB `feat/lunar-base-scene`.

## Where it stands

**Mission B ran end to end once** (ga8, F87). **It is not reliable**, and eleven defects have been fixed since,
**none of them with a successful run behind it**. The next action is a run, not more code (`todo.md`).

## What was fixed today, by kind (F81-F91 carry the detail)

- **The simulator's action boundary.** Every `cmd_vel` rebuilt the whole action vector through the *teleoperation*
  mapping and kept only `_held_mask` dimensions; only the Bool gripper was masked, so the first cmd_vel of each
  drive switched the arm out of joint-position mode and zeroed its targets. **This was the carry** (F81). And the
  buffer started at zeros, which for that arm selects twist mode against a pose never set — so before any skill
  claimed it the arm ran at its velocity limit for 150 s (F89).
- **The harness withholding what it knew.** `held_item` answered with a camera clamped to the handle, which
  cannot see the payload (F82). Every place point carries a surveyed outward normal `place` was never given (F85).
- **Geometry, found by computing not inferring** (F86). A prop's box was built from how tall it is rather than
  where it is (shelf 16 cm low, PDU panel 60 cm low); the shelf was 0.6 m deep against a 0.485 m envelope with a
  wall behind it; the handle's bars occluded the slot they bound.
- **The harness's own numbers wrong about themselves.** One constant as both the seat depth and its tolerance; a
  transient swing tolerance spent as a sustained one; `work_stands` checking reach at the part rather than where
  the tool ends up; one query timer serving both a lost response and the slowest legitimate answer (F90).
- **The payload interface.** F49 gave the T-handle form closure against a vertical pull and left rotation to
  friction; ga4 rolled it 23.7 deg round the neck during a turn and lost it. A collar below the slot makes the
  fingers captive (F83/F84).
- **A capability weaker than the robot, and a promise weaker than the dock** (F91). `find` took one frame from the
  first pose the arm could reach and gave up; the candidate search made the image re-certify a contact length the
  catalogue declares. So 6 cm of docking error lost `pick` three times with the part in plain view. `find` now
  takes the views the arm can reach, and `work_stands` answers reach and look at the end of the docking band where
  each is hardest, instead of at a point with a caveat.

The model's side needed no correction at any point.

## Method rules that were earned the hard way

- **Look at the pictures before the numbers.** Four wrong hypotheses came out of one day of reading bags; 44
  wrist frames showed the load being flung in a glance (F81). The saved `find` view showed the part the search
  said was not there (F91). Record the chassis camera too.
- **Whether one solid fits on another is arithmetic over data the repository already holds.** Three of ga8's ten
  defects were sitting in the asset files (F86); the asset file also refuted a plausible fix in one line (F91).
- **Read your own code back before running it.** This session it caught a collar placed off the old pedestal
  origin, `self.geom` undefined in the place skill, and a mesh bound taken after the scale proxy joined the scene.
- **Subtract.** Do not add a tool, a script or a file unless something is impossible without it.

## Running it

Skills are import-cached in `openral_rskill_ros/runtime_node`; a skill change needs the runtime restarted, an SRB
or asset change needs the whole graph rebooted.

1. Stop by explicit PID (never `pkill -f`), then confirm `ros2 node list` is **empty** — a leftover
   `planning_scene` from an earlier graph published TF frozen at its last clock and cost ga3 the whole run. Kill
   the ros2 daemon too; it caches nodes that no longer exist.
2. Recorder: topics as in `gb2/`, QoS `record_qos.yaml`, **including `/openral/cameras/front/image`**.
3. Fresh graph (absolute log dir): `D0_CAPABILITY_SERVER=1 D0_HOLD=1 D0_CHECK=ours_mission_check.py OURS_MISSION=b`
   `[D0_VIDEO=<dir>/mission_b.mp4 D0_VIDEO_RES=1920,1080 D0_VIDEO_STRIDE=2 D0_VIDEO_SPEEDUP=1]`
   `setsid nohup experiments/launch/lunar_base_d0/run_d0.sh <dir>`. Rendering costs ~14 % of the sim rate, not the
   5x an old note feared.
4. Attach to a live graph: `D0_RESTART_RUNTIME_PID=<pid> [D0_RESTART_BOUNDARY=1] ... attach_d0.sh <graph> <newlog>`.
   Resume points are jaws-open only.
5. Asset or scene change: `assets/lunar_base/process/process.py --only <names>` then `scene/build_scene.py`, then
   reboot the graph. The builder's `problems` list is a real check — it refused a deeper shelf that reached into
   the rover's own work pose.
6. Analyse only closed bags. `/usr/bin/python3.10` for rosbag2, `openral/.venv/bin/python` for the skills.
   `ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` plus `fastdds_large_shm.xml`.

Video: `experiments/video/track_from_bag.py <run>/robot_motion <run>/track.json`, then
`experiments/video/mission_video.py <run>/mission_b.mp4 <run>/ours/events.jsonl <out> --track <run>/track.json
--width 1920`. Re-encode with x264 before sending anything anywhere; the composer writes mp4v at ~6x the size.

## Established context

- Ours completed Mission A covered before the new manipulation stack (oa2); record-based restart worked (rs1).
- Press is built but has never pressed a button live; Mission A's ready/stand deadlock is unresolved (F62 §3).
- PLEXIL Release 6 builds and runs Mission A covered through the common boundary (F52); EUROPA not started.
- `oru_on`/`crate_on` name a support only when the item is **not** in the gripper.
- The jaw reading is what the fingers closed on; it rising means something is prying them apart. The drives sit at
  their 4.0 N.m limit the whole time an item is held — 3-4x the real EG2-4C2's 0-20 N. The user's decision is to
  keep that (lunar equipment is not a catalogue part) and give the interface form closure instead.

## Rules

- One simulation only. All paths absolute. No `pgrep -f` / `pkill -f`.
- Never navigate on simulator truth; it is evaluator/diagnosis only, never control, prompts, guards or verifiers.
- Whole-operation tools only; mechanics stay inside skills. A skill retries the same target, never moves the base.
- Model-facing services use DeepSeek's own endpoint; keys in `AGENT/VLM_provider.md` never enter logs or output.
- Boundary: `openral_ext/capability_server/{contracts.yaml,contracts.py,node.py}`. Ours: `space_runtime/`.
- Development resumes/edits are not campaign results; never count them in paper metrics.
- Keep this file and todo.md <= 150 lines, overwrite at milestones. Replies to the user in concise Simplified
  Chinese.
