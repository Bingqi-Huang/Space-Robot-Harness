# Phase B, slice 2 — a `procedural` rSkill kind, and F11 resolved

Verified 2026-09-13 on openral branch `feat/lunar-bot-hal` (built on top of
`af61568`). Live end-to-end test through the real `ExecuteRskill` action
server against a running SRB instance.

## What this resolves

F11 (`docs/research_findings.md`): no existing `RSkillKind` fit a
deterministic, non-learned actuating skill. `vla` requires `model_family` +
`weights_uri` and routes through `openral_sim.factory.make_policy` (a real
policy-adapter factory, confirmed by reading it — not a lightweight generic
loader); `ros_action`/`ros_service` require a running ROS server this project
does not own; `playbook` is schema-forbidden from ever emitting an `Action`
(role must be `s2`, `actuators_required` must be empty — it is a reasoner-side
decision procedure, not an actuator). This is also directly needed for
execution_plan.md §5.2's Baseline A ("a conventional pre-engineered procedure
... coordinates the same underlying capabilities") — every baseline in the
planned comparison needs *some* way to dispatch a non-learned, deterministic
motion through the real rSkill/safety/ROS path, and none existed.

## What was built (upstream OpenRAL schema/loader extension, not a workaround)

- `RSkillKind` gains `"procedural"` (`python/core/src/openral_core/schemas.py`).
- `ProceduralIntegration` — new manifest block mirroring `RosIntegration`'s
  `entrypoint` + `default_goal_json` + per-dispatch-merge contract, so the
  reasoner/LLM tool-call path is identical regardless of kind. Field-level
  JSON validation matches `RosIntegration`'s.
- `RSkillManifest._check_kind_consistency` gained a full `"procedural"`
  branch (requires the `procedural` block, forbids every VLA/ROS-wrapper/
  perception field, pins `chunk_size=1` for the same row-0-only-checked
  reason `ros_action`/`ros_service` do) — and the five other kinds'
  forbidden-field dicts were extended to forbid `procedural` too, keeping
  the closed-world exclusivity the validator already enforces.
- `rskill_runner_node.make_default_skill_resolver` gained a `"procedural"`
  branch: resolves `procedural.entrypoint` via the same
  `"module.path:ClassName"` convention `openral_hal.build_hal` uses for
  `hal.real`/`hal.sim`, constructs the class, `configure()`s + `activate()`s
  it — structurally identical to the `ros_action`/`ros_service` branch, just
  without a ROS client to build.
- `python/rskill/src/openral_rskill/procedural_body_twist.py` —
  `ProceduralBodyTwistRskill`, the first (and so far only) concrete
  `kind: "procedural"` skill: holds a fixed `(linear, angular)` body-twist
  velocity for `duration_s` seconds, one `Action(BODY_TWIST, horizon=1)` per
  `step()`, then raises `ROSRskillGoalSatisfied` — the same termination
  contract `ROSActionRskill`'s result-only mode uses.
- `rskills/rskill-procedural-body_twist/rskill.yaml` — the manifest.
  `embodiment_tags: ["mobile_base"]`, so any mobile-base robot can use it,
  not just `lunar_bot`.

## Verified live, through the real path (not `ROSPublishingHAL` called directly)

```
ros2 action send_goal /openral/execute_rskill ...
  -> rskill_runner_node's real ExecuteRskill action server
    -> make_default_skill_resolver's new "procedural" branch
      -> ProceduralBodyTwistRskill (configure/activate/step)
        -> ROSPublishingHAL.send_action() (unmodified)
          -> /openral/candidate_action -> C++ safety kernel -> /openral/safe_action
            -> openral_hal_lunar_bot (slice 1) -> SRB's cmd_vel -> robot moves
```

`ros2 action send_goal` with `goal_params_json:
'{"linear": [0.25, 0.0, 0.0], "angular": [0.0, 0.0, 0.15], "duration_s": 3.0}'`
was accepted, streamed real feedback (`chunk_index` climbing 1→80,
`progress` increasing monotonically), and `srb/env0/robot`'s `/tf` pose moved
from `(0.074, 0.649)` to `(-0.633, 0.698)` — confirming the goal's per-dispatch
JSON override correctly reached the skill and drove the real robot.

A resolver-level test (bypassing the action server, calling
`make_default_skill_resolver(...)` and stepping the returned skill directly)
independently confirmed configure/activate/step/termination semantics before
the live test, isolating "does the new kind's plumbing work" from "does it
survive going through the actual action server."

## F15 (new) — the run aborted at ~2.7s on a safety-status staleness latch, unrelated to the new kind

The goal did not finish cleanly — `rskill_runner_node` aborted it at chunk 81
with `failure_kind: 4` (`FAILURE_SAFETY_ESTOP`):

```
safety_estop:safety stop latched (/openral/safety_status:stale
(last update 3.0s ago > 3.0s; safety publisher may be gone)) while about to
dispatch inference tick 81
```

Diagnosed, not just observed: `rskill_runner_node.py` hardcodes
`_SAFETY_STATUS_LIVENESS_S = 3.0` and treats any gap longer than that on
`/openral/safety_status` as "the safety publisher may be gone" → latches an
e-stop, fail-safe. The C++ kernel, however, only calls
`publish_safety_status_now()` on activation and on actual state **changes**
(a violation, an estop, a reconfigure) — confirmed by reading every call site
in `lifecycle_kernel.cpp`; its only `create_wall_timer` is the unrelated
`/diagnostics` heartbeat. A live message was confirmed
(`ros2 topic echo /openral/safety_status --once` returned one, stamped at
kernel activation, `detail: "kernel activated"`), but `ros2 topic hz` over 5s
showed **zero** further messages. Nothing in `deploy_e2e.launch.py` sets up a
periodic republish either (grepped for "safety_status"/"heartbeat" there —
no hits).

**This is not a defect in the new `procedural` kind or its resolver
branch** — it would affect *any* rSkill dispatch (`vla`/`ros_action`/
`ros_service` included) that runs longer than 3s without a kernel-side state
change, which our multi-second body-twist hold was simply the first thing in
this project to actually do. Left open, not chased further this session — a
genuine question about whether this is a bring-up gap (something the full
`deploy_e2e.launch.py` stack supplies that our minimal bring-up script
didn't) or a latent bug that would surface at any sufficiently long,
otherwise-uneventful dispatch. Recorded as its own finding
(`docs/research_findings.md` F15) rather than folded into F11 or F12, since
it is a different mechanism (staleness watchdog) from either.

## Environment note

`ros2 action send_goal`/`ros2 topic echo` on an `openral_msgs`-typed
interface silently fails ("Unknown package" / "invalid action type") unless
**both** `/opt/ros/humble/setup.bash` **and** `install/setup.bash` are
sourced in that shell — a bare `ros2 <verb>` call in a fresh shell only has
the first. Easy to forget per-shell; cost two retries this session.

## Still open

- F15 above.
- F12 (kernel's actual BODY_TWIST magnitude bound, still uncharacterized).
- Arm (CARTESIAN_TWIST) / gripper (GRIPPER_BINARY) wiring on `lunar_bot`'s HAL.
- Mission A can now proceed in principle (a working, dispatchable, non-learned
  skill exists) — still worth deciding whether to resolve F15 first, since an
  e-stop latch mid-mission would confound any trace collected before it's
  understood.
