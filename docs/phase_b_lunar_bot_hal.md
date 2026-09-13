# Phase B, slice 1 — LunarBot BODY_TWIST through the real safety chain

Verified 2026-09-13 on openral branch `feat/lunar-bot-hal` (off `4c1867c`).
Live end-to-end test against a running SRB instance; no upstream files
modified outside the new additions below.

## What this proves

The mobile base of `lunar_bot` can be driven through OpenRAL's real,
safety-checked actuation path — not a shortcut around it:

```
test script -> ROSPublishingHAL.send_action()      (existing, unmodified)
  -> /openral/candidate_action                     (real ActionChunk, BODY_TWIST)
    -> C++ safety kernel                            (existing, unmodified;
                                                       envelope loaded from
                                                       robots/lunar_bot/robot.yaml)
      -> /openral/safe_action
        -> openral_hal_lunar_bot lifecycle node     (NEW)
          -> LunarBotSRBHAL.send_action()            (NEW)
            -> /srb/env0/action/cmd_vel              (real geometry_msgs/Twist)
              -> SRB moves lunar_bot
                -> /srb/env0/robot/joint_states       (real state)
                  -> HAL's read_state() (round-trips through /joint_states)
```

Measured result: 4 s of `linear.x=0.2 m/s, angular.z=0.1 rad/s` moved
`srb/env0/robot`'s `/tf` pose from `x=0.428, y=-0.536` to `x=-0.356,
y=-0.003` — no rejection, no error, in either the kernel or the HAL log.

## What was built (all new; nothing upstream modified)

- `robots/lunar_bot/robot.yaml` — `RobotDescription` for lunar_bot. Every
  joint name and every velocity/effort limit is sourced from the real SRB
  asset (`space_robotics_bench/srb/assets/robot/mobile_manipulation/lunarbot.py`),
  not invented — see the manifest's own header comment for the exact
  provenance and the honest caveats (placeholder `parent_link`/`child_link`
  labels, no URDF/self-collision yet). `hal.real` (not `hal.sim`) — SRB is an
  externally-owned system reached over ROS, structurally like real hardware
  from OpenRAL's point of view, not OpenRAL's own in-process MuJoCo physics.
  Safety bounds (`max_base_linear_speed_m_s: 0.3`,
  `max_base_angular_speed_rad_s: 0.5`) are deliberately conservative
  provisional values for this first bring-up, not a validated operating
  envelope — see the manifest's inline comment.
- `python/hal/src/openral_hal/lunar_bot_srb.py` — `LunarBotSRBHAL`. Mirrors
  `RosControlHAL`'s established shape exactly (no `rclpy` import, constructed
  before any ROS node exists, wired to a real transport after the fact via
  `attach_transport`) so it stays unit-testable and fits the same seam every
  other real-hardware HAL uses. BODY_TWIST only; requires `horizon == 1`
  (a plain `Twist` has no chunking semantics).
- `packages/openral_hal_lunar_bot/` — the lifecycle node package. Subclasses
  `openral_hal.lifecycle.ManifestHALLifecycleNode` (inherits its manifest-driven
  `_create_hal`, estop/heartbeat/safe_action-subscription plumbing unchanged)
  and overrides only `on_configure_post_hal` to create the real
  `geometry_msgs/Twist` publisher + `sensor_msgs/JointState` subscriber on
  SRB's topics and call `attach_transport`. A bespoke subclass, not an
  extension of `_attach_ros_control_transport`, because that hook is
  structurally gated on `RosControlDrivable` (joint-trajectory/`ControllerKind`
  shaped) — SRB's plain-topic interface doesn't fit it.

## What this does NOT yet cover

- **Not run through `rskill_runner_node`'s skill-loading or the reasoner.**
  The test used `ROSPublishingHAL` directly (the same wire mechanism a real
  rSkill uses) to isolate and prove the new HAL/kernel path. Getting a real,
  dispatchable rSkill registered is a separate problem:
  `rskill_runner_node`'s `make_default_skill_resolver` only handles
  `kind: vla` / `ros_action` / `ros_service` today (`wam` raises
  "not implemented"); `kind: playbook` (which exists, e.g.
  `rskills/preflight-reach`) is an S2 decision procedure the *reasoner*
  composes, not something that emits `Action` chunks itself. None of these
  cleanly fit "a small scripted body_twist motion for integration testing" —
  this needs its own decision, not a forced fit into `kind: vla`.
- Arm (CARTESIAN_TWIST via SRB's `differential_inverse_kinematics`) and
  gripper (GRIPPER_BINARY via SRB's `binary_joint_position`) are not wired —
  deliberately deferred until this base-only slice was proven.
- The C++ kernel's actual BODY_TWIST-specific validation was not fully
  characterized: it did not reject a 6-wide BODY_TWIST chunk against a
  21-dof-declared envelope, but the source has no dedicated
  `max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` consumption
  (grep confirmed — only comments mention BODY_TWIST). What check, if any,
  actually bounds a BODY_TWIST chunk's magnitude is unconfirmed; do not
  assume the manifest's conservative 0.3 m/s / 0.5 rad/s bounds are enforced
  by the kernel today.

## Environment notes for reproducing this

- Same SRB launch as `docs/srb_integration_notes.md` §2
  (`PYTHONPATH` unset, `ISAAC_SIM_PATH` set, conda stripped).
- `ros2 lifecycle` / `ros2 node list` do not enumerate nodes by name in this
  environment (same `_NODE_NAME_UNKNOWN_`-shaped quirk seen with SRB's own
  bridge) even though the node is alive and its services/topics work — call
  `lifecycle_msgs/srv/ChangeState` and `GetState` directly by service name
  (`/openral_safety_kernel/change_state` etc.) instead of `ros2 lifecycle set`.
- The safety kernel needs its envelope as ROS parameters
  (`n_dof`, `joint_position_min/max`, `joint_velocity_max`, `joint_torque_max`,
  `max_ee_speed_m_s`, ...) — it does **not** read `robot_yaml` itself. Generate
  them correctly via
  `openral_safety.envelope_loader.compute_intersection(desc, None)` +
  `kernel_params_from_envelope(...)`, dump to a YAML params file, launch with
  `--ros-args --params-file <path>`. Hand-guessing these (tried first, twice)
  wastes time and produces confusing "envelope load failed" errors that name
  the wrong thing.
- `ros2 run <pkg> lifecycle_node` fails with "No executable found" — the
  registered executable name includes the `.py` suffix
  (`ros2 pkg executables <pkg>` shows the real name). Separately, `ros2 run`
  invokes the script via its shebang (`/usr/bin/env python3` = system Python,
  no `structlog`); launch it directly with `.venv/bin/python
  install/lib/<pkg>/lifecycle_node.py --ros-args ...` instead.

## Next

- Decide how a scripted (non-learned) test rSkill gets registered so this
  path can be driven by `rskill_runner_node` end to end, then by the
  reasoner itself — see "What this does NOT yet cover" above.
- Characterize the C++ kernel's actual BODY_TWIST validation before relying
  on it for anything safety-relevant.
- Arm (CARTESIAN_TWIST) and gripper (GRIPPER_BINARY) wiring, once the above
  is settled.
