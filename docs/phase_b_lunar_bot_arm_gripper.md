# Phase B, slice 3 — LunarBot arm + gripper unified into one mobile-manipulator HAL

Built 2026-09-13 on openral branch `feat/lunar-bot-arm-gripper` (off
`fix/body-twist-speed-envelope`, i.e. F12 already landed). Extends
`LunarBotSRBHAL` (Phase B slice 1 was BODY_TWIST-only) with CARTESIAN_TWIST
(arm) and GRIPPER_BINARY (gripper), so one HAL instance drives all three of
LunarBot's actuator surfaces through the real safety-checked path — a
genuine mobile manipulator, not three independent single-actuator slices.

## What motivated this

The user reported the SRB-side arm/gripper action wiring (owned by another
agent working in `space_robotics_bench/`, read-only from this project's
side) was now functionally complete, and asked for OpenRAL's side to be
unified so the base, arm, and gripper act as one coherent embodiment. Per
`execution_plan.md` §6.4, Mission A's capability mix needs manipulation, not
just navigation — this was a real prerequisite for Mission A, not
gold-plating.

## A second instance of F12's bug class, found and fixed first

Before wiring the arm, reading `SafetyEnvelope.max_ee_angular_speed_rad_s`
(already declared on `panda_mobile`'s manifest at `1.0`) turned up the same
shape of gap F12 fixed for BODY_TWIST: the C++ kernel's `kCartesianTwist`
validator case checked only linear speed against `max_ee_speed_m_s`; the
angular bound's enforcement was "documented" as living in the Python
`openral_safety/supervisor_node.py` — which does implement the check, but
`deploy_e2e.launch.py` never launches that node, so it's dead code in every
real deployment. `envelope_loader.py` didn't forward the field into the
kernel's ROS parameters at all either. Since this project was about to
actually exercise CARTESIAN_TWIST for the first time, this was fixed first,
mirroring F12's exact pattern:

- `EnvelopeIntersection` (both Python dataclass and C++ struct) gained
  `max_ee_angular_speed_rad_s`, default `math.inf`/`kPosInfinity`.
- `envelope_loader.kernel_params_from_envelope()` now forwards it.
- `validator.cpp`'s existing `kCartesianTwist` case gained the angular
  check (`sqrt(wx²+wy²+wz²)` vs. the bound), mirroring the existing linear
  check exactly.
- 2 new gtest cases (`CartesianTwistAngularSpeedCapEnforced`,
  `CartesianTwistAngularSpeedDefaultsToUnboundedWhenUnset`); full `ctest`
  suite (4 binaries) passes.

This is a self-contained fix, independent of the arm-wiring work below, and
could in principle be its own PR — kept in the same branch/session here
because it was discovered as a direct prerequisite for trusting the new
CARTESIAN_TWIST wiring's safety bound.

## SRB-side facts this HAL had to get right (verified, not assumed)

Read `space_robotics_bench/srb/assets/robot/mobile_manipulation/lunarbot.py`
(read-only — that repo stays untouched) plus the vendored Isaac Lab source
at `~/isaaclab/source/isaaclab/isaaclab/envs/mdp/actions/` to understand the
actual mechanism, then confirmed both facts live:

1. **The arm's `differential_inverse_kinematics` action is NOT a native
   velocity controller.** `DifferentialInverseKinematicsActionCfg(
   use_relative_mode=True, scale=0.1)` — Isaac Lab's own
   `process_actions()`/`DifferentialIKController.set_command()` scale the
   raw Twist and add it to the end-effector's *current measured pose* as a
   one-shot position delta, recomputed fresh every control step from
   whichever raw value is currently held. Since SRB's ROS bridge holds the
   last published Twist as a zero-order-hold buffer (same mechanism
   `cmd_vel` uses), *sustaining* a constant raw value does produce
   continuous motion proportional to the raw magnitude — functionally a
   velocity from outside, just realised through repeated position deltas
   rather than a native rate controller. This is why `openral_hal.
   lunar_bot_srb` needs an explicit raw↔physical conversion for the arm,
   unlike the base's `cmd_vel` (which SRB's own `FourWheelSteerActionCfg`
   already speaks in real m/s and rad/s — sign flip only).

2. **The gripper's `binary_joint_position` action is direction-inverted
   from the naive reading.** Isaac Lab's `BinaryJointAction` maps a
   positive raw value to `open_command_expr`, negative to
   `close_command_expr`; SRB's ROS bridge extractor is
   `lambda msg: [-1.0 if msg.data else 1.0]` — so `Bool(True)` → raw
   `-1.0` → **close**, `Bool(False)` → raw `+1.0` → **open**. Confirmed
   live before writing any HAL code: publishing `True` moved
   `eg2_joint1` from ~0.82 rad (open) to ~0.0 rad (closed); `False`
   reopened it.

Both facts are the kind of thing that's easy to get backwards from a
message-type name alone (`Twist` "should" mean velocity; `Bool` "should"
mean the obvious direction) — worth stating plainly since they will surprise
the next person touching this HAL.

## Arm calibration (empirical, deliberately conservative, not a precise physical constant)

A 7-DoF arm's differential-IK Jacobian conditioning varies across the
workspace (`ik_method="dls"` bounds but doesn't eliminate this), so — unlike
the base — there is no single exact raw↔m/s ratio. Measured live 2026-09-13
against a freshly-reset SRB env, holding one raw axis at `1.0` for 2.0 s and
reading `Link7`'s TF displacement / rotation:

| Command | Linear (m/s) | Angular (rad/s) |
|---|---|---|
| `linear.x=1.0` | 0.431 | 0.175 (coupled) |
| `linear.y=1.0` | 0.293 | 0.467 (coupled) |
| `angular.z=1.0` | 0.022 (coupled) | 0.388 |
| `angular.x=1.0` | 0.069 (coupled) | 0.461 |

`openral_hal.lunar_bot_srb._ARM_LINEAR_MPS_PER_RAW_UNIT = 0.5` and
`_ARM_ANGULAR_RADPS_PER_RAW_UNIT = 0.6` were chosen by rounding up from the
observed maxima (0.431, 0.461) — same epistemic status as `robot.yaml`'s own
BODY_TWIST bounds ("conservative... not a validated operating envelope"),
not a precise calibration. Rounding up means `raw = desired / k` computes a
*smaller* raw command than the 1:1 ratio would at the measured poses, so a
chunk that just cleared the kernel's `max_ee_speed_m_s` / `max_ee_angular_
speed_rad_s` bound is unlikely to exceed it in practice — not a guarantee
against every configuration in the workspace. The cross-axis coupling in the
table (a pure linear command inducing some rotation and vice versa) is an
inherent property of driving a redundant 7-DoF arm's full 6-vector twist
through Jacobian IK, not a wiring bug — the safety kernel's linear/angular
checks each look at their own 3 components regardless.

`robot.yaml` declares `max_ee_speed_m_s: 0.2` / `max_ee_angular_speed_rad_s:
0.3` — conservative first-bring-up values chosen so the HAL's raw
conversion stays under the measured range at every pose tested.

## What was built

- `python/hal/src/openral_hal/lunar_bot_srb.py` — `send_action` now
  dispatches on `control_mode` across `BODY_TWIST` / `CARTESIAN_TWIST` /
  `GRIPPER_BINARY` (previously BODY_TWIST-only); new `arm_ik_topic` /
  `hand_topic` constructor args + properties; the calibration constants and
  gripper-direction helper above.
- `packages/openral_hal_lunar_bot/openral_hal_lunar_bot/lifecycle_node.py`
  — `_LunarBotSRBTransport` gained an `arm_ik` `Twist` publisher and a
  `hand` `Bool` publisher alongside the existing `cmd_vel` one;
  `publish(topic, msg)` dispatches on the topic argument to pick the right
  one and message shape, so `LunarBotSRBHAL` stays transport-agnostic.
- `robots/lunar_bot/robot.yaml` — `supported_control_modes` gains
  `cartesian_twist` + `gripper_binary`; `safety` gains `max_ee_speed_m_s:
  0.2` / `max_ee_angular_speed_rad_s: 0.3`; joint/module comments updated
  from "follow-up work" to "driven via ...".
- `python/hal/tests/test_lunar_bot_srb.py` (new) — 9 unit tests against the
  real `robots/lunar_bot/robot.yaml` manifest with an injected `publish_fn`
  (the sanctioned test seam, not a HAL mock): BODY_TWIST passthrough
  regression, CARTESIAN_TWIST raw-unit conversion, GRIPPER_BINARY's
  inverted-direction table (parametrised over the 0.5 threshold), horizon/
  payload rejection, unsupported-mode rejection. All pass.

## Verified live, through the real path, not the isolated kernel

```
test script -> /openral/candidate_action (real ActionChunk)
  -> C++ safety kernel (existing + this session's angular-speed fix)
    -> /openral/safe_action
      -> openral_hal_lunar_bot lifecycle node
        -> LunarBotSRBHAL.send_action() (BODY_TWIST / CARTESIAN_TWIST / GRIPPER_BINARY)
          -> SRB's cmd_vel / differential_inverse_kinematics / binary_joint_position
            -> real robot motion, read back via /tf and /joint_states
```

Both `safety_kernel_node` and `openral_hal_lunar_bot`'s lifecycle node
configured + activated via direct `lifecycle_msgs` service calls (`ros2
lifecycle` doesn't enumerate nodes on this host — F14). Envelope parameters
generated the sanctioned way (`compute_intersection()` +
`kernel_params_from_envelope()` against the real, updated
`robots/lunar_bot/robot.yaml`).

- **CARTESIAN_TWIST in-bound** (0.1 m/s commanded x): `Link7` measurably
  moved (0.007–0.013 m/s actual, depending on pose — consistent with the
  calibration table's conservative rounding), `safety_status.latched`
  stayed `False`.
- **CARTESIAN_TWIST over-limit, linear** (1.0 m/s x vs. the declared 0.2
  m/s bound): rejected — `drop_reason=KIND_FORCE, detail="ee_speed"`,
  `Link7` did not move (residual ≤ ~0.03 m over 2 s, consistent with the
  arm's known settling jitter, not partial pass-through).
- **CARTESIAN_TWIST over-limit, angular** (1.0 rad/s vs. the declared 0.3
  rad/s bound): rejected — `drop_reason=KIND_FORCE,
  detail="ee_angular_speed"` — confirms today's angular-speed kernel fix
  works end-to-end, not just in the isolated-kernel test that accompanied
  its own commit.
- **GRIPPER_BINARY**: commanding CLOSE (`gripper=0.0`) drove
  `eg2_joint1` from ~0.82 rad to ~0.0 rad; commanding OPEN (`gripper=1.0`)
  drove it back to ~0.82 rad — through the full chain, with the HAL's
  inverted-direction conversion applied correctly (not just the direct-SRB
  isolated confirmation done earlier).
- **BODY_TWIST regression**: unchanged, no rejection, same as Phase B
  slice 1.

## A real operational gotcha found along the way (not a bug, but easy to trip on)

The first end-to-end run's gripper/second-body-twist commands silently did
nothing — no kernel rejection, no HAL error in the *response*, just
nothing happening. Root cause: after the kernel's `/openral/estop_reset`
service clears **the kernel's own** latch, every OTHER node that latched on
`/openral/estop` (here, `openral_hal_lunar_bot`'s lifecycle node) stays
latched — `openral_hal/lifecycle.py` already documents this explicitly:

> "the estop TRIGGER is a topic every node latches on, but reset was a
> kernel-only service, so the HAL stayed latched after
> `/openral/estop_reset` — the robot never resumed until a restart."

The intended fix is `/openral/estop_cleared` (`std_msgs/Empty`), which every
`ManifestHALLifecycleNode` also subscribes to — but in production that's
published by the **dashboard** (`openral_observability.dashboard.
estop_publisher.EstopPublisher`), not the kernel itself; a human operator
is meant to consciously broadcast "cleared" after confirming the reset,
which is a deliberate safety design, not an oversight. Any test/bring-up
script that drives the kernel directly (no dashboard running) must publish
`/openral/estop_cleared` itself after every `/openral/estop_reset` call, or
every node downstream of the first violation stays silently inert. Recorded
here so the next person doesn't lose the same hour rediscovering it.

## What this does NOT cover

- Same scope boundary as the angular-speed fix above: `kJointTrajectory`/
  `kCartesianDelta`/`kGripperBinary` (the shared per-joint bound, distinct
  from GRIPPER_BINARY's binary command itself)/`kGripperPosition`/
  `kCompositeMode` still delegate to the unlaunched Python supervisor
  stub — untouched.
- The arm calibration is a single-session, few-pose measurement, not a
  swept characterization of the whole workspace — treat
  `_ARM_LINEAR_MPS_PER_RAW_UNIT`/`_ARM_ANGULAR_RADPS_PER_RAW_UNIT` as
  provisional bring-up constants, same as the manifest's own bounds.
- No dashboard/`estop_cleared` automation added — the gotcha above is
  documented, not automated away, since the human-in-the-loop reset is a
  deliberate design choice elsewhere in the codebase, not this project's
  call to change.
