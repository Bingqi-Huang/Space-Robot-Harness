# Handoff

State as of 2026-09-13. Phase A complete. Phase B slices 1–2 verified live;
F15 closed as a false alarm; **F12 investigated and CONFIRMED as a real
upstream safety gap** — needs a user decision before Mission A, not a
silent patch. Task list: `todo.md`. Records: `docs/phase_b_lunar_bot_hal.md`,
`docs/phase_b_procedural_kind.md`. Findings: `docs/research_findings.md`.

## F12: confirmed, not just suspected

`max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` (declared in
every robot's `robot.yaml`) are enforced by **nothing** in the current
OpenRAL stack. Root cause, found in the C++ source: the safety kernel's
`validate()` explicitly delegates these per-mode bounds to the Python
`openral_safety/supervisor_node.py` — whose own docstring says it's a Day-1
stub waiting for the C++ kernel to implement them. Each side's code names
the *other* as responsible; neither actually does it. Also:
`kernel_params_from_envelope()` doesn't even forward the value into the
kernel's ROS parameters, so there's nowhere for it to land even if the
kernel wanted to check it.

**Verified live, not just read**: commanded `lunar_bot`'s base at 6.0 m/s —
20× the manifest's declared 0.3 m/s bound — for 3 seconds through the real
`candidate_action` → kernel → `safe_action` → HAL → SRB path. Zero
rejection: `/openral/safety_status` stayed `latched=False` the whole time,
no `FailureTrigger`, no kernel warning, and the robot moved the full
commanded distance.

This is upstream OpenRAL's real, current behavior — for `kBodyTwist`,
`kJointTrajectory`, `kCartesianDelta`, `kGripperBinary`, `kGripperPosition`,
and `kCompositeMode` alike, on any robot, not something specific to
`lunar_bot` or something we misconfigured.

## This needs your decision, not mine

Per OpenRAL's own `CLAUDE.md` §3: touching `packages/openral_safety/` or
`cpp/openral_safety_kernel/` requires a safety-WG reviewer and a hazard-log
entry. I have not attempted to patch this — it's a genuine safety-relevant
gap in someone else's project, not ours to silently paper over. Two honest
paths:

1. **Report it as a known upstream limitation.** Scope the paper's
   trustworthiness claims around it (don't claim magnitude bounds are
   enforced for these modes; the shape/NaN/collision checks that *are* real
   still stand). Fastest path to Mission A.
2. **Treat implementing the missing per-mode bound check as real future
   work** — a genuine, reviewable contribution to OpenRAL, done carefully
   (tests, hazard-log entry, matching the existing kernel's style), not a
   quick local patch. Bigger scope, delays Mission A.

## Next

Once you decide on F12, either proceed straight to Mission A (option 1) or
scope the safety-kernel fix first (option 2). Arm/gripper HAL wiring
(CARTESIAN_TWIST/GRIPPER_BINARY) is still open too, same BODY_TWIST pattern,
whenever it's next needed.

## Environment reference (reusable, don't rediscover)

- SRB / kernel / HAL / runner launch: `docs/srb_integration_notes.md` §2,
  `docs/phase_b_lunar_bot_hal.md`, `docs/phase_b_procedural_kind.md`.
- `RskillRunnerNode` is constructed directly in Python — mirror `compose.py`:
  construct with `skill_resolver=None`, then swap `node._skill_resolver =
  make_default_skill_resolver(node, search_paths=["rskills"])` before
  `configure()`.
- Any shell calling `ros2 action send_goal`/`topic echo`/`topic hz` on an
  `openral_msgs` interface needs both `/opt/ros/humble/setup.bash` and
  `install/setup.bash` sourced.
- When checking a topic's publish rate, redirect `ros2 topic hz` to a file
  instead of piping through `tail`/`grep` — piping after a `timeout` kill
  loses the buffered output and reads as "zero messages" even when the
  topic is publishing fine.
- To regenerate the kernel's ROS parameters from a `robot.yaml`:
  `openral_safety.envelope_loader.compute_intersection(desc, None)` +
  `kernel_params_from_envelope(...)`, dump to YAML,
  `--ros-args --params-file <path>`.

## Watch out

- **Never `pkill -f` on this host** — exact PIDs only, every time, including
  the reparented kit-python child.
- `space_robotics_bench/` stays untouched — read/run only, ever.
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
