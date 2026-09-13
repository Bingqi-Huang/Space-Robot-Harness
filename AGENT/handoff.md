# Handoff

State as of 2026-09-13. Phase A complete. Phase B slices 1 (LunarBot HAL) and
2 (`procedural` rSkill kind) both verified live. Task list: `todo.md`.
Records: `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_procedural_kind.md`.
Findings: `docs/research_findings.md`.

## What just happened

Resolved F11: added a genuine, permanent `RSkillKind` — `"procedural"`, for
deterministic/non-learned actuators. No existing kind fit this (`vla` needs
real weights + routes through a policy-adapter factory; `ros_action`/
`ros_service` need a running server we don't own; `playbook` is
schema-forbidden from ever emitting an `Action`). This isn't a test
convenience — it's exactly what execution_plan.md §5.2's Baseline A
(procedure-driven mission execution) needs, so every baseline in the planned
comparison now has a way to dispatch through the real path.

Built: `RSkillKind`/`ProceduralIntegration` schema addition + full
`_check_kind_consistency` branch; a resolver branch in
`make_default_skill_resolver`; `ProceduralBodyTwistRskill` (the first
concrete skill); `rskills/rskill-procedural-body_twist/rskill.yaml`.

**Verified live through the real path**: `ros2 action send_goal` against the
actual `ExecuteRskill` action server → resolver → skill → `ROSPublishingHAL`
→ candidate_action → C++ safety kernel → safe_action → the lunar_bot HAL
(slice 1) → SRB's `cmd_vel` → the robot moved. Not a shortcut — the same path
a real dispatch would use.

openral branch `feat/lunar-bot-hal` (`f47e966`, pushed, **not merged** —
Phase B continues on it).

## New finding while proving this: F15

The 3-second dispatch aborted at ~2.7s: `rskill_runner_node` hardcodes a
3.0s liveness check on `/openral/safety_status` and latches a fail-safe
e-stop if it goes stale; the C++ kernel only publishes that topic on
activation and on state *changes*, never on a heartbeat (confirmed by
reading every call site — its only wall timer is the unrelated
`/diagnostics` one). **Not a defect in the new kind** — it would hit any
rSkill's dispatch lasting >3s without a kernel-side state change. Not chased
down yet; recommended next per `todo.md` since an unexplained mid-mission
e-stop would confound any Mission A trace collected before it's understood.

## Next

`todo.md`'s Phase B checklist: F15 (safety-status staleness) is the
recommended next step, then F12 (kernel's actual BODY_TWIST bound), then
arm/gripper wiring, then Mission A (plan §21 items 5–6).

## Environment reference (reusable, don't rediscover)

- SRB / kernel / HAL launch: `docs/srb_integration_notes.md` §2 +
  `docs/phase_b_lunar_bot_hal.md`'s "Environment notes."
- `RskillRunnerNode` is constructed directly in Python (not manifest-driven
  via ROS params like the HAL nodes) — mirror `compose.py`'s pattern:
  construct with `skill_resolver=None`, then swap `node._skill_resolver =
  make_default_skill_resolver(node, search_paths=["rskills"])` before
  `configure()`.
- **Any shell calling `ros2 action send_goal`/`topic echo` on an
  `openral_msgs` interface needs both `/opt/ros/humble/setup.bash` and
  `install/setup.bash` sourced** — missing either fails with a misleading
  "Unknown package"/"invalid action type", not an obvious "not sourced" error.

## Watch out

- **Never `pkill -f` on this host** — exact PIDs only, every time, including
  the reparented kit-python child.
- `space_robotics_bench/` stays untouched — read/run only, ever.
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
