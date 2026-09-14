# Handoff

State as of 2026-09-14 (evening). Phase A complete. Phase B1 done. Phase B2
items 1/2/2b/2c/3/4 done+verified; items 5–9 and B3 remain.
Task list: `todo.md`. Findings: `docs/research_findings.md` (F1–F30). Key
docs: `docs/lunar_bot_capability_set_plan.md`, `docs/mission_a_panel_remount.md`,
`docs/lunar_bot_rm75_spec.md`.

## Where things stand

Branch chains — openral: `feat/py310-humble` → `feat/lunar-bot-hal` →
`fix/body-twist-speed-envelope` → `feat/lunar-bot-arm-gripper` →
`feat/arm-joint-position-control` → `feat/lunar-bot-capability-set`
(current, 3 new commits this session: tf_lookup wiring + lunar_bot
embodiment tag, the five procedural rSkills, tcp_frame). SRB: `main` →
`feat/panel-remount-mission-a` → `feat/switchable-arm-control` →
`feat/mid360-lidar` → `fix/ros-bridge-array-fast-path` →
`feat/four-wheel-steer-alignment` (current, 2 new commits: the pre-existing
`map_cmd_to_action` twist-index bug, then the F19 steer-before-drive fix).
All pushed*, all still open, none merged. (*local commits this session not
yet pushed — push before ending the session if that's expected.)

## Items 3+4 — done this session (F30, full detail in research_findings.md)

**Item 3 — five procedural rSkills** (`move_joints`, `stow`,
`move_ee_to_pose`, `grasp`, `release`) in `openral/python/rskill/src/
openral_rskill/procedural_{move_joints,move_ee_to_pose,gripper}.py` + five
`rskills/rskill-procedural-*` manifests. New `tcp_frame` TF (sensor bridge,
`Link7` + 0.14 m offset) and `tf_lookup` wired through the procedural
resolver branch for `move_ee_to_pose`. All five live-dispatched as real
`ExecuteRskill` goals against the running `deploy sim` graph:
- `stow`/`move_joints`, `grasp` (empty gripper → correctly fails), `release`
  — all converge/terminate correctly.
- `move_ee_to_pose` — works end-to-end but has a real, documented residual
  precision/oscillation limitation (SRB's `arm_ik` term has no passive
  holding stiffness — re-syncs to current joint state every step, so a
  converged axis can drift back out between ticks). Gain retuned
  (2.0→1.0), stall-detection now tracks position+orientation independently.
  Not fully solved; good lead for item 6 (MoveIt).

**Item 4 — F19 fix** in SRB `four_wheel_steer.py` (steer-before-drive,
`drive_velocity *= cos(steer_target - steer_measured).clamp(min=0)`).
Verified: steering now ramps correctly to the right per-wheel target
instead of snapping. Net point-turn precision still imperfect (wheel
scrub, not fully isolated from tuning). **Along the way**: found+fixed a
separate pre-existing bug in `WheeledManipulatorActionGroup.
map_cmd_to_action` — `twist[:2]` took `(vx,vy)` instead of `(vx,wz)`, so
every `angular.z` cmd_vel command was silently dropped before reaching the
base controller at all. This is why F19 couldn't be observed before fixing
it (own commit, separate from the F19 fix itself).

## Next — item 5 (Navigation)

Per `docs/lunar_bot_capability_set_plan.md` §3.5 and
`docs/srb_deploy_backend_plan.md` §5: Nav2 via `openral_nav2_bringup`,
lidar profile from the Mid-360 (RayCaster, permanent per F24), needs
`pointcloud_to_laserscan` apt-installed. **Important**: route Nav2's
`/cmd_vel` through the kernel via a `cmd_vel → candidate_action` relay
node — upstream lets Nav2 write the base directly, which violates §10.1
(never bypass safety). Given F30's `map_cmd_to_action` finding, double-check
that relay maps `(linear.x, angular.z)` correctly too — don't assume.
The user separates planning rounds from coding rounds — wait for an
explicit go before starting item 5's code.

## Environment reference (reusable, don't rediscover)

- SRB / kernel / HAL / runner launch: `docs/srb_integration_notes.md` §2,
  `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_lunar_bot_arm_gripper.md`.
- `openral deploy sim --config scenes/deploy/srb_panel_remount.yaml
  --no-enable-slam --no-enable-nav2 --no-enable-octomap --no-dashboard`
  brings up kernel+HAL+SRB (+reasoner, which will time out configuring
  after 300s if no LLM credential is set on this host — benign, rest of
  graph is unaffected, don't wait for it). Sensor bridge is a **separate**
  process: `.venv/bin/python -m openral_hal_lunar_bot.sensor_bridge_node
  --ros-args -p robot_yaml:=robots/lunar_bot/robot.yaml` (not `ros2 run` —
  lacks structlog). Both need `ROS_DOMAIN_ID=77
  ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` and both ROS setup.bash files
  sourced.
- **Readiness is NOT `ros2 topic list | grep <topic>`** — false-positived
  repeatedly right after a teardown/relaunch this session (stale DDS state
  from the just-killed instance). Use a real functional check: an actual
  `tf2_ros.Buffer.lookup_transform(...)` call, or an actual dispatch.
  Expect ~15-80s from launch to genuinely ready even with a warm shader
  cache; don't trust "ready" until 2-3 consecutive real checks pass.
- Dispatch an in-tree rSkill for testing: a real `rclpy.action.ActionClient`
  against `/openral/execute_rskill` (`openral_msgs.action.ExecuteRskill`)
  works directly against the production graph's own action server — no
  need to build a second `RskillRunnerNode`. **Use a unique `prompt` per
  test dispatch** — the resident-skill cache keys on `(rskill_id, revision,
  prompt)` and reuses a cached instance (skipping `configure()`/
  `activate()`, so a new `goal_params_json` and the skill's own clock are
  silently ignored) on a repeat of the same key. Noted, not fixed —
  pre-existing, affects every `kind: procedural` skill.
- **Never `pkill -f`** — exact PIDs only, every time. **Always re-`pgrep`
  the exact current PID immediately before signaling it** — reusing a PID
  echoed by an earlier command can target a process that's already been
  superseded by a fresh relaunch (F30: caused a duplicate
  `sensor_bridge_node`, ~76s of spurious TF failures).
- A bare `time.sleep()` before reading a ROS subscription callback is a
  race — spin through the wait (`rclpy.spin_once` in a loop), don't sleep.
- Colcon rebuild of the safety kernel: conda stripped from env + `PATH`,
  `--merge-install`, `PYTHON_EXECUTABLE`/`Python3_EXECUTABLE` →
  `.venv/bin/python`.
- **F17**: `/openral/estop_reset` only clears the kernel's own latch —
  also publish `/openral/estop_cleared` (`std_msgs/Empty`).
- **F18**: SRB's moon terrain is only flat within ~4 m of env origin.
- **F20**: a JOINT_* chunk's wire row is ALWAYS the full 21-wide robot
  vector, even when `joint_names` names a subset.
