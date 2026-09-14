# Handoff

State as of 2026-09-14. Phase A complete. Phase B1 done and verified
live: LunarBot is a genuine mobile manipulator — base (BODY_TWIST), arm
(CARTESIAN_TWIST + JOINT_POSITION, RM-75 limits enforced), gripper
(GRIPPER_BINARY) — all through the real safety chain from one HAL.
Mission A's SRB task (`panel_remount` v1) is built. Phase B2 (capability
set, items 1/2/2b/2c) is done+verified — sensors reach OpenRAL and
`openral deploy sim` can bring up the whole graph against SRB — but the
reasoner has still never been in the loop for this robot and no rSkill can
move the arm (F21); items 3-9 are next.
Task list: `todo.md`. Findings: `docs/research_findings.md`. Key docs:
`docs/lunar_bot_capability_set_plan.md`, `docs/mission_a_panel_remount.md`,
`docs/lunar_bot_joint_position_control.md`, `docs/lunar_bot_rm75_spec.md`.

## Where things stand

Branch chains — openral: `feat/py310-humble` → `feat/lunar-bot-hal`
(`f47e966`) → `fix/body-twist-speed-envelope` (`fabe588`) →
`feat/lunar-bot-arm-gripper` (`af8fba2`) → `feat/arm-joint-position-control`
(current). SRB: `main` (`9caeb46`) → `feat/panel-remount-mission-a`
(`b3e8d92`) → `feat/switchable-arm-control` (`90f9d5e`) →
`feat/mid360-lidar` (`4baea49` RayCaster Mid-360, `9bae384` RTX Lidar
attempt, parked — F24). All pushed, all still open, none merged.

**`space_robotics_bench/` is a real git submodule** (`docs/upstream_pins.md`)
— the agent that developed it independently no longer manages it, so this
project edits/commits there directly now, same discipline as `openral/`.

## Next — Phase B2, the LunarBot capability set (plan revised 2026-09-14)

The user's ruling: Mission A does not start until its prerequisites exist,
and every blocking piece of infrastructure gets built (only IL data
collection and VLA training are out of scope). `execution_plan.md` §8.3 has
the ordered build list; design/reuse survey in
`docs/lunar_bot_capability_set_plan.md`; task list in `todo.md`.

Done: **1** RM-75 limits (F22, `f7b5ccd`). **2** Sensor bridge (F25,
`openral_hal_lunar_bot.sensor_bridge_node`) — relays SRB's cameras/depth/
IMU/lidar to OpenRAL conventions, re-roots TF, publishes `/odom`; verified
live, including a real `rclpy` executor gotcha (spin a `MultiThreadedExecutor`
on a background thread, not `rclpy.spin(node)`/`.spin()` on the main thread —
both silently stall). Not yet wired into `deploy_e2e.launch.py` (runs
standalone) — needs a generic mechanism (this launch is robot-agnostic by
design), a follow-up. **2b** SRB backend for `openral deploy sim` (F26/F27,
`docs/srb_deploy_backend_plan.md`) — `DeployScene.simulator` schema, `srb`
scene backend + provision check, launch spawn/gate, `lunar_bot` HAL registry
entry (`bare_twin_sim=True`), `scenes/deploy/srb_panel_remount.yaml`. Found
+ fixed two real bugs: `deploy_config:=` never reached the sim-path launch
(F26), and SRB's Kit/PhysX process outlived `ros2 launch` by over an hour
after shutdown, still holding GPU memory — root-caused to NVIDIA's
`python.sh` forking without `exec` plus `ExecuteLocal` having no
process-group handling at all; fixed with `tools/process_group_wrapper.py`
(new process-group leader, kills the whole group on SIGTERM), tested
against the real failure mode in `tests/unit/test_process_group_wrapper.py`
(F27). **The ~0.36 Hz SRB tick is solved (F28, SRB `04c308a` on
`fix/ros-bridge-array-fast-path`)**: 0.36 → ~12 Hz through the full graph,
five SRB-side causes (rosidl per-byte `bytes` validation → `array.array`;
CPU pointcloud unprojection + publishing to nobody; Mid-360 RayCaster on
warp-CPU → `srb.core.sensor.RayCaster` on CUDA; unread RL image
observations → `skip_observations`; eager trace f-string), all because
SRB pins `sim.device=cpu`. `SRB_ROS_PROFILE=1` prints a per-tick bucket
breakdown every 100 ticks — use it before guessing. Residual ~82 ms =
GPU render ~30 ms (3 cams; lands in the first sensor that syncs) + CPU
PhysX ~21 ms; RTF ≈ 0.24. `staleness_limit_s` untouched. Also fixed:
scripted `deploy sim` teardown never reached SRB — `&` in a
non-interactive shell inherits `SIGINT=SIG_IGN` (`openral/845483c`,
trampoline + SIGTERM-the-wrapper sweep), verified clean twice. **Open**:
camera topics arrive in OpenRAL at ~2 Hz while SRB publishes at 12 Hz —
Fast-DDS large-message loss (both sides Fast-DDS, `rmem_max` 208 KB), fix
= XML profile for both + sysctl (F28). NOT yet reached: a
reasoner-dispatched body_twist observed moving the base — nothing blocks
it now. **Debugging a live `deploy sim` graph**: `ROS_DOMAIN_ID=77` +
`ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (`confine_sim_scope`) — export
both or `ros2 topic` sees only `/parameter_events`/`/rosout` (F27). The
sensor bridge must be started with `.venv/bin/python -m
openral_hal_lunar_bot.sensor_bridge_node` (system `ros2 run` lacks structlog).
**2c** RTX Lidar for the Mid-360: blocked on a confirmed upstream Isaac
Sim bug (F24), **parked by user decision** — RayCaster is permanent.

Not started: **3–9** — procedural rSkills, F19 fix, Nav2
(`pointcloud_to_laserscan` apt install needed), MoveIt (required), verifier
node, run-manifest writer, remaining kernel magnitude checks. The user
separates planning rounds from coding rounds — wait for an explicit go
before each.

Also open: F19 (don't rely on `cmd_vel` for precise heading control yet —
item 4 fixes it) and the same missing-magnitude-check gap for
`kJointTrajectory`/`kCartesianDelta`/`kGripperBinary`(per-joint)/
`kGripperPosition`/`kCompositeMode` (F12/F16's sibling gap, item 9).

## Environment reference (reusable, don't rediscover)

- SRB / kernel / HAL / runner launch: `docs/srb_integration_notes.md` §2,
  `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_lunar_bot_arm_gripper.md`.
- Standalone kernel bring-up (no SRB/HAL needed to test the kernel itself):
  `docs/f12_body_twist_envelope_fix.md`'s "Live" section.
- To read SRB's actual action-term mechanics (not just the topic/message
  type, which can mislead — see the arm/gripper facts above), the vendored
  Isaac Lab source lives at `~/isaaclab/source/isaaclab/isaaclab/envs/mdp/
  actions/` and `~/isaaclab/source/isaaclab/isaaclab/controllers/` on this
  host — read it, don't guess from `srb/core/action/`'s thin wrapper alone.
- **F17 — multi-node estop reset**: the kernel's `/openral/estop_reset`
  service only clears the kernel's own latch. Every other node that latched
  on `/openral/estop` (e.g. a HAL lifecycle node) stays latched and
  silently drops commands until `/openral/estop_cleared` (`std_msgs/Empty`)
  is also published — normally the operator dashboard's job. Any test
  script driving the kernel directly must publish it too after every reset.
- **F18 — SRB's moon terrain is only flat within ~4 m of the env origin**
  (`flat_area_size`); an object spawned outside gets embedded, then flung
  by PhysX depenetration forever in lunar gravity. Keep scene objects
  within ~1.5–2 m of the origin.
- **F19 — base drifts on a large in-place `cmd_vel` turn** — no
  steer-before-drive sequencing (item 4). `scale_linear`/`scale_angular`
  are `-1.0` in `lunarbot.py`; a naive P-controller drives the wrong way.
- **F20 — a JOINT_* chunk's wire row is ALWAYS the full robot-wide vector**,
  even when `action.joint_names` names a subset (ADR-0102) — the C++
  kernel's structural check forces `chunk.n_dof == envelope.n_dof`
  regardless. `joint_names` only marks which slots are the real ones; it
  never shrinks the row. Caught this the hard way (silently dropped every
  JOINT_POSITION dispatch) — see `docs/lunar_bot_joint_position_control.md`.
- `RskillRunnerNode`: mirror `compose.py` — construct with `skill_resolver=
  None`, then swap `node._skill_resolver = make_default_skill_resolver(node,
  search_paths=["rskills"])` before `configure()`.
- Any shell calling `ros2 action send_goal`/`topic echo`/`topic hz` on an
  `openral_msgs` interface needs both `/opt/ros/humble/setup.bash` and
  `install/setup.bash` sourced.
- When checking a topic's publish rate, redirect `ros2 topic hz` to a file
  instead of piping through `tail`/`grep` — piping after a `timeout` kill
  loses the buffered output and reads as "zero messages" even when the
  topic is publishing fine.
- Colcon rebuild of the safety kernel: conda stripped from env + `PATH`,
  `--merge-install`, `PYTHON_EXECUTABLE`/`Python3_EXECUTABLE` → `.venv/bin/python`.

## Watch out

- **Never `pkill -f` on this host** — exact PIDs only, every time, including
  the reparented kit-python child.
- A bare `time.sleep()` before reading a ROS subscription callback's result
  is a race — spin through the wait (`rclpy.spin_once` in a loop), don't
  sleep through it, or a stale TRANSIENT_LOCAL message gets misread as a
  fresh response.
- `space_robotics_bench/` is now a real git submodule, formally pinned like
  `openral/` (2026-09-13) — the agent that developed it independently no
  longer manages it, so editing/committing there is fine now, same branch +
  commit discipline as `openral/`. (This reverses the earlier "read/run
  only" rule from Phase B slices 1–3 — that was about not colliding with
  concurrent work, not a permanent restriction.)
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
