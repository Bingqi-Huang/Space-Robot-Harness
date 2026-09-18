# Handoff

State as of 2026-09-18 midday. Research goal and plan: `AGENT/research_content.md`, `AGENT/execution_plan.md` (§21 order:
the proposed method before the baselines; §8.2 granularity rule). Findings F1–F57 in `docs/research_findings.md` —
**read F53–F57**. Tasks: `AGENT/todo.md`. Current design: **`docs/semantic_to_metric_manipulation_plan.md` (v4)**.

**The picture in one line:** Claude Code for a lunar robot. The model owns the mission (what to observe, where to go,
what to pick, what to try after a failure); tools are whole operations (`navigate`, `dock`, `pick`, `place`, `press`,
`observe`), never stages; the harness runs them, keeps the record, verifies effects automatically and holds the
boundaries; OpenRAL is the borrowed tool runner / skill format.

## Where the research stands

- Ours (`space_runtime/`, on OpenRAL `ReasonerCore`) runs Mission A `covered` end to end with vision-only contact (oa2,
  verifier success). Restart/model switch on the same record works (rs1).
- Mission B (fetch the spare ORU, deliver to PDU-1): plan v4 is **implemented** — `pick(target, part)` and
  `place(support)` are procedural rSkills in the fork (`openral/python/rskill/src/openral_rskill/{procedural_pick,
  procedural_place,grasp_perception,_eye_in_hand}.py`, manifests in `openral/rskills/rskill-procedural-{pick,place}`),
  the boundary has one contract line each, the model's palette is operations only, and the harness verifies
  `item_held` / `item_placed` from the raw evidence. G0–G2 passed; **G3's nominal placement holds the ORU** (g3bn),
  perturbed placements running; `place` and G4 are next. Branch `feat/pick-place-rskills` (fork),
  `feat/g0-wrist-rgbd` (research repo).
- Rule that keeps costing runs (F57): nothing about the camera–gripper geometry may be a constant. `find` aims at the
  structures the views measure; `tool_in_view()` derives the self-occlusion depth, the free image band and the
  gripper's silhouette from TF. When a run fails, read the evidence pictures first — every one of these was visible
  in one image and invisible in the numbers.
- Baselines: PLEXIL runs Mission A through the common boundary (F52); PLEXIL Mission B, EUROPA→PLEXIL, Experiments I/II
  not started.

## User decisions (keep)

- Ours before the baselines; tasks from `docs/lunar_task_catalog.md`; Ours may meet held-out situations before the
  freeze with mission-generic changes only; freeze = git commits/tags, **no hash checks anywhere**.
- Reasoner **DeepSeek-V4-Pro**, thinking on (offline replay, F55 §4). Shared VLM **GLM-5.3-Flash**. Gateway key in
  `AGENT/VLM_provider.md` (never in code).
- **Method boundary (research_content §3.2/§5.2–5.3/§5.7, revised):** baselines share robot, capabilities,
  perception sources, raw evidence, low-level safety and the external evaluator — not Ours' mechanisms. Ours' facts,
  context reconstruction, guard, internal effect verification and traces are the method; attribution by Ours-internal
  ablations. **Architecture (plan v4 §2):** physical-effect capabilities = OpenRAL rSkills; perception control and
  read-only queries = perception / world-state services; thin method-neutral capability contract. Fixed infrastructure
  may use surveyed named places; movable objects only via perception → tracking → visual servo inside the skill.
  No playbook-style decision rSkills. No big refactor: move logic out of `capability_server` when new work touches it.
- **Granularity (plan v4, 2026-09-17):** model-facing tools are whole operations with mission-level arguments
  (`pick(target, part)`, `place(support)`, `press(target)`); stages (candidates, VLM selection, tracking, servo,
  close-in, hold check) and mechanical parameters live inside the skill. A skill retries only on the same target;
  changing target, moving the base, another operation or asking the operator returns to the model with the stage and
  evidence. Harness verifies `held` / `placed` automatically. Hardware-protecting limits while driving/holding go to
  the shared low-level safety; the v3 guard rule "no base motion while holding" is withdrawn (Mission B carries).
- **Manipulation internals (kept from v3):** no object models, no world-coordinate targets; grasp candidates from the
  wrist RGB-D view (classical first), VLM set-of-mark choice, KLT/depth tracking + IBVS, guarded close-in, image
  checks. Isaac ROS FoundationPose rejected (needs meshes, ROS 2 Jazzy).
- Ad-hoc patches are not acceptable; fix causes or redesign (F55 §5 lists what was reverted).
- **Step-wise development:** never rerun a mission from scratch after a failure; restore the snapshot before the failed
  step, fix, rerun that step. One simulation at a time.
- Replies to the user: Simplified Chinese, plain words, concise; ask before deciding design questions for the user.

## How to run

- Mission dev run with snapshots (from `openral/`):
  `D0_HOLD=1 OURS_STOP_ON_FAILURE=1 D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml D0_CHECK=ours_mission_check.py
  D0_CAPABILITY_SERVER=1 OURS_MISSION=b setsid nohup ../experiments/launch/lunar_base_d0/run_d0.sh <log>
  > <log>/runner.out 2>&1 < /dev/null &` (`OURS_MISSION=a` for Mission A; `D0_TRACE_OBJECT=spare_oru` logs the object).
- Snapshots: `<log>/snapshots/before_step_<n>.{pt,json}` (SRB `envs/snapshot` + the AMCL estimate). Resume after a fix:
  `[D0_RESTART_BOUNDARY=1] OURS_MISSION=b OURS_STOP_ON_FAILURE=1 OURS_RESUME_FROM=<log> OURS_RESUME_BEFORE_STEP=<n>
  setsid nohup experiments/launch/lunar_base_d0/attach_d0.sh <graph log> <new log> &` (works on a held graph or a fresh one).
- Take a held graph down: `experiments/launch/lunar_base_d0/teardown_d0.sh <graph log>` — **the absolute path** the
  run was started with (the tag is matched exactly; a relative path finds nothing and reports `TREE 0 pids`).
- One `pick` trial per placement (G3): `D0_CAPABILITY_SERVER=1 D0_HOLD=1 D0_CHECK=../../perception/g3_pick.py
  G3_TRIALS="0,0,0,0;0.08,0,20,0" setsid nohup experiments/launch/lunar_base_d0/run_d0.sh <log> &` (a trial is
  `dx,dy,dyaw_deg,rover_dx`). Changing skill code needs a new graph: the runner imports it once per process.
- Read a pick failure from its pictures, not its numbers: `<log>/evidence/pick_*/` has the overview, each side view
  with its numbered candidates, and `servo_NN.jpg` per approach frame with the tracked point and the match score
  (`evidence.approach_track` lists them even when the stage fails).
- Record: `<log>/ours/{events.jsonl,report.md,agent.log}`; boundary `capability_server.log`; frames `evidence/`.
- Offline reasoner comparison on recorded decision points: `experiments/reasoner_replay/replay.py`.
- Scripted checks: `D0_CHECK=d0_mission_{a,b}_check.py`, `vision_check.py`, `d0_plexil_mission_a_check.py`; options
  `D0_VIDEO`, `D0_SCENARIO=<heldout_…>`, `D0_SCENERY=lunar_base_route_block`, `D0_STEPS`, `D0_PLANNING_SCENE=0`.
- Video: `D0_VIDEO=<mp4>` + `SRB_VIDEO_SPEEDUP=1` → `<mp4>.times`; `python3 experiments/video/overlay.py`.
- Speed: sim ≈ 0.375× wall; reasoner steps take minutes (V4-Pro), so dev runs are long. GPU PhysX crashes in SRB.

## Stack facts (don't rediscover)

- `/odom` wheel-inertial; AMCL on a lidar-surveyed map; Nav2 goals in `map`; SLAM off; truth only for evaluation
  (and dev-only snapshot restore). Cameras D435i front + wrist, 15 Hz, work lights; wrist image level in `grip`.
- Capability boundary: `openral_ext/capability_server/{contracts.yaml,node.py}` (`/space/capability/execute`, `/query`);
  PLEXIL adapter `ros/plexil_capability_adapter`. Today it still implements `approach_target`, VLM `observe` /
  `locate_in_view` and feature-pose lowering (to move per plan v3 §2). Effect verification and the guard live in
  `space_runtime/` (Ours' harness — correct per the method boundary).
- Arm: RM-75 (`docs/lunar_bot_rm75_spec.md`); MoveIt plans end 0.9–3 cm from goal; 1 kg payload sags ~4.5 cm — a held
  item settles back after the call returns, so read the lift *during* it (the truth track), not after.
- Wrist camera (changed 2026-09-18, F57 §6): 0.12 m off the tool axis, 0.22 m behind the TCP, aimed 0.15 m beyond it,
  D435i colour intrinsics at 640×480 (fx = fy = 616). The numbers live in SRB's `lunarbot.py` and, identically, in the
  HAL's `CAMERA_MOUNTS`. Nothing in the skills may hard-code them: `tool_in_view()` derives the self-occlusion depth
  and the free image band from TF.
- OpenRAL rSkill manifests: `openral/rskills/*/rskill.yaml` (kinds procedural, ros_action, detector, segmenter, vlm,
  playbook); entrypoints `openral/python/rskill/src/openral_rskill/`; reasoner palette/tools in
  `openral/python/reasoner`; integration notes `docs/openral_integration_notes.md`.

## Things that bit (keep)

- `openral deploy sim` reaps openral processes → `OPENRAL_SKIP_ORPHAN_REAP=1` (run_d0.sh).
- Runs execute a frozen copy of `run_d0.sh`; checks load at start — never edit a script a live run executes.
- Kill only explicit PIDs; `pgrep -f`/`pkill -f`/pattern `case` matches have killed the calling shell.
- Stale agents ignore SIGTERM → kill -9; check the ROS domain is clean before a run. Parallel sims → 0.05×.
- A publisher's first message is lost before discovery (AMCL `/initialpose`): wait for the match.
- Verifier `oru_on: ""` can mean knocked off, not grasped — check jaw and handle height.
- `move_group` can wedge: idle (1% CPU) and answering nobody after a planning request that never completes. Every
  service call in the skills now has a deadline, so this ends the call with its stage instead of hanging a run
  (one run lost 40 minutes to an `fk` call with no deadline).
- Teardown takes the run's **absolute** path (the tag is matched exactly); a relative one reports `TREE 0 pids`.

## Where things are

- Research repo `main` (feature branch merged 2026-09-17). openral fork `master` (camera mounts, wrist depth relay,
  servo zero-twist fix). SRB `feat/lunar-base-scene` (lunar base, 15 Hz cameras, work lights, lidar 10 Hz,
  publish-on-new, video `.times`, `envs/snapshot`); SRB `main` untouched.
- Runs (not in git): `artifacts/runs/` (oa*, ob*, vc*, rs1, pf*); replay results `artifacts/reasoner_replay/`.
