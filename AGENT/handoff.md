# Handoff

State as of 2026-09-17 (early morning). **Phase D0's core has passed: Mission A and Mission B `covered` run end
to end through the shared capability stack with realistic localization. §21.4's common capability boundary is
proven live (Mission A through the boundary = direct run), and the PLEXIL baseline runs Mission A through it
(F52). World-aware MoveIt + fixed arm hold: `heldout_cover_obstruction` capabilities pass.** Findings: `docs/research_findings.md` F1–F51 — **read F51 first**. Tasks: `todo.md`.

## What D0 established (F51)

- `/odom` is wheel-inertial (bridge least squares over the 4WIS wheels for vx, vy + IMU yaw rate). AMCL
  (omni model) localizes against a 2D map surveyed inside SRB with the rover's own lidar slice
  (`space_robotics_bench/assets/lunar_base/scene/srb_nav_map_survey.py`, cells hit from ≥3 poses →
  `usd/scene/lunar_base/nav_map/`). SLAM off. Nav2 goals and docking are in `map`; truth only measures.
- Mission A `covered` (a5): dock 0.090 m, press clears PDU-2, return to dock 0.077 m, verifier success.
- Mission B `covered` (b7): depot dock 0.017 m, ORU clamped (jaw 0.17 rad) through Nav2 carry, placed upright on
  PDU-1's shelf, dock 0.028 m, verifier success.
- Held-out `route_block` passes (Nav2 detour, AMCL 0.074 m with an unmapped obstacle).
- Videos (robot-following camera, 4× playback): `artifacts/videos/mission_a_covered.mp4`,
  `artifacts/videos/mission_b_covered.mp4`.

## Open D0 gaps (not blocking §21.4, blocking Experiment I)

1. (closed, F52) world-blind MoveIt → `openral_ext/planning_scene` (site boxes + truth-posed movable objects).
2. **Perception held-out primitives** (lamp state, occupied shelf, which object is the ORU) need Phase E.
3. **Truth stand-ins** (`locate_feature`, feature targets, movable objects in the planning scene) — replace before the freeze.
4. Stuck rover with spinning wheels defeats AMCL; MPPI cuts structure corners.

## §21.4: the common capability boundary

- `ros/space_harness_msgs` (build: `cd ros && colcon build --merge-install --packages-select space_harness_msgs
  --cmake-args -DPYTHON_EXECUTABLE=/usr/bin/python3 -DPython3_EXECUTABLE=/usr/bin/python3`, PATH without conda).
- `openral_ext/capability_server/{contracts.yaml,node.py}`: `/space/capability/execute` (ExecuteCapability),
  `/space/capability/query` (QueryCapability). One call → one ExecuteRskill; off-contract → failure_kind 20;
  evidence is robot-observable only (verifier stays evaluator-side).
- Proof: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_capability_mission_a_check.py` (Mission A through the boundary only).
- PLEXIL: `docs/baselines/plexil.md` (6.1.3, `~/Programs/plexil`; ant and gperf under `~/Programs`, no apt).
  `ros/plexil_capability_adapter` → `libCapabilityAdapter.so`: Command `ExecuteCapability(capability, args_json)`,
  every other Command = a capability with positional args; Lookups `QueryCapability`, `jaw`, `LastCapabilityResult`.
  Plan `baselines/plexil/plans/MissionA_Covered.ple`; live: `D0_CAPABILITY_SERVER=1 D0_CHECK=d0_plexil_mission_a_check.py`
  (success, p1). Adapter build: as msgs, plus `PLEXIL_HOME=$HOME/Programs/plexil`.

## How to run (don't rediscover)

- One run (from `openral/`): `D0_SCENE=scenes/deploy/srb_lunar_base_mission_{a,b}_fast.yaml
  D0_CHECK=d0_mission_{a,b}_check.py D0_CONTINUE_ON_FAIL=1 setsid nohup ../experiments/launch/lunar_base_d0/run_d0.sh <logdir> > <logdir>/runner.out 2>&1 < /dev/null &`
  — one run per launch command, nothing after it in the same call. Output: `STEP` JSON in `<logdir>/check.log`.
- Options: `D0_GPU=1 D0_DOMAIN=78` (parallel graph), `D0_VIDEO=<mp4>`, `D0_SCENARIO=<heldout_…>`,
  `D0_SCENERY=lunar_base_route_block`, `D0_TRACE_OBJECT=spare_oru` (object/TCP/jaw every 0.5 s),
  `D0_CAPABILITY_SERVER=1`, `D0_STEPS=1,2,…`; planning scene on by default (`D0_PLANNING_SCENE=0` off).
- Checks: `d0_mission_a_check.py`, `d0_mission_b_check.py`, `d0_route_block_check.py`,
  `d0_mission_a_cover_check.py` (passes with the planning scene, ac5), `d0_capability_mission_a_check.py`,
  `d0_plexil_mission_a_check.py`.
- Runs: ~15 min wall (Mission A), ~35 min (Mission B), ×3 with video. Sim 0.2× alone, 0.06× beside a render.
- Teardown is by run tag (`D0_RUN_TAG` in the deploy's env); `LEFT 0 tagged processes` in `deploy.pid`.

## Things that bit this session (keep)

- `openral deploy sim` reaps every openral-graph process at start AND exit and purges Fast-DDS SHM: a sibling
  graph dies. `run_d0.sh` exports `OPENRAL_SKIP_ORPHAN_REAP=1` (now covers all three).
- bash reads scripts incrementally: editing `run_d0.sh` under a live run killed runners mid-script. Runs now
  exec a frozen copy. Check scripts load at start — editing them is safe once a check has begun.
- Skills in the deploy graph ran on `time.monotonic` (runtime_node's resolver lacked the clock); same-stamp
  sim ticks then broke settle/speed logic; check-script deadlines were wall-clock. All sim-clock now.
- SRB's `cmd_vel` callback rebuilt the whole action row and opened the gripper; binary commands are latched now.
  "Held" (handle–TCP distance) cannot tell a clamp from a hook — read the jaw.
- `terminate_on_success` teleports the rover to the dock at success; deploy scenes set it false.
- Nav2 omni caps must keep the planar speed norm inside the kernel bound (`nav2_max_lateral_speed_m_s`).
- SRB arm hold: never persist a leashed/clamped command into held state — transients became permanent sag.
- Humble `async_send_request` returns a `std::future`: `get()` once.

## Where things are

- openral: `master` (merged from `feat/d0-localization`), not pushed.
- SRB: `feat/lunar-base-scene` (merged from `feat/d0-nav-map`), not pushed.
- Research repo: `main` (merged from `feat/d0-localization`), not pushed.
