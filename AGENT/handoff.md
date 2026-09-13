# Handoff

State as of 2026-09-13. Phase A complete. Phase B slice 1 (LunarBot BODY_TWIST
through the real safety chain) just verified live. Task list: `todo.md`.
Full record: `docs/phase_b_lunar_bot_hal.md`. Findings: `docs/research_findings.md`.

## What just happened

Built and live-verified a new HAL bridging OpenRAL's safety-checked chunk
path to SRB for `lunar_bot`'s mobile base, per the user's explicit choice to
go through the real chain rather than bypass it (like the pre-existing Nav2
rskill does for real hardware):

```
ROSPublishingHAL (existing) -> /openral/candidate_action
  -> C++ safety kernel (existing) -> /openral/safe_action
    -> openral_hal_lunar_bot (NEW) -> LunarBotSRBHAL (NEW)
      -> /srb/env0/action/cmd_vel -> SRB moves the robot
        -> /srb/env0/robot/joint_states -> read_state() round-trips
```

Measured: 4s of `linear.x=0.2, angular.z=0.1` moved the base from
`(0.428, -0.536)` to `(-0.356, -0.003)` in `/tf`. No rejection anywhere.

openral branch `feat/lunar-bot-hal` (`af61568`, pushed to the fork, **not
merged** — Phase B keeps landing on it). Submodule bumped in this repo.

## Four things deliberately left open (not silently skipped)

1. **No rSkill kind fits a scripted test motion.** `make_default_skill_resolver`
   only handles `vla`/`ros_action`/`ros_service` (`wam` unimplemented);
   `playbook` is a reasoner-side decision procedure, not an actuator. The
   live test used `ROSPublishingHAL` directly to isolate the new mechanism
   from this open question — it still needs its own decision before the
   reasoner/`rskill_runner_node` can drive this path.
2. **The kernel's BODY_TWIST bound is unconfirmed.** `max_base_linear_speed_m_s`
   exists in the manifest schema; grep found zero C++ consumption of it.
   The chunk wasn't rejected, but *why* is uncharacterized — don't trust the
   0.3 m/s bound is enforced until tested by deliberately exceeding it.
3. Arm (CARTESIAN_TWIST) and gripper (GRIPPER_BINARY) — same HAL, same
   pattern, deferred until base-only was proven.
4. Mission A / generic-OpenRAL trace-collection (plan §21 items 5–6) —
   blocked on (1) above.

## Next

Pick up `todo.md`'s Phase B checklist — item 1 (rSkill registration
decision) unblocks everything else. Read `docs/research_findings.md`
F11–F14 first; they're the reasoning behind each open item above.

## Environment reference (reusable, don't rediscover)

- SRB launch: same as before (`docs/srb_integration_notes.md` §2 —
  `PYTHONPATH` unset, `ISAAC_SIM_PATH` set, conda stripped).
- Safety kernel needs its envelope as **flat ROS parameters**, not a
  `robot_yaml` path — generate them with
  `openral_safety.envelope_loader.compute_intersection(desc, None)` +
  `kernel_params_from_envelope(...)`, dump to YAML, launch with
  `--ros-args --params-file <path>`. Guessing them wastes time.
- `ros2 run <pkg> lifecycle_node` fails ("No executable found" — the real
  name has a `.py` suffix; `ros2 pkg executables <pkg>` shows it) and even
  then hits `ModuleNotFoundError` (shebang picks system Python). Launch
  directly: `.venv/bin/python install/lib/<pkg>/lifecycle_node.py --ros-args ...`.
- `ros2 lifecycle`/`node list` don't enumerate nodes here even when alive —
  call `lifecycle_msgs/srv/ChangeState`/`GetState` on the service name
  directly (`ros2 service call /openral_safety_kernel/change_state ...`).

## Watch out

- **Never `pkill -f` on this host** — killed another agent's processes once
  already this project. Exact PIDs only, every time, including the
  reparented kit-python child (killing the wrapper alone doesn't take it
  down).
- `space_robotics_bench/` stays untouched — read/run only, ever.
- No `space_runtime`/`space_context` code until Phase B observes real
  failures calling for it (plan §21.6–7).
