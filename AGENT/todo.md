# TODO — Phase A: Upstream Verification

Scope: `execution_plan.md` §18 Phase A + §5.1/§5.2 + §6.1 + §21.1–21.3.
Exit condition: the actual upstream execution path of OpenRAL and SRB runs on
this machine, and the real APIs/topics of the pinned revisions are written down.

**Do not start Phase B (OpenRAL↔SRB control loop) until A4 passes.**

## Decision D1 — Humble + Python 3.10, fully native ✅ verified

Evidence: `docs/upstream_pins.md`. Fork deviations: `docs/openral_py310_patch.md`.

## Embodiment decision — LunarBot ✅ (user directive, overrides §6.2 heuristic)

Already substantially integrated into SRB (category `mobile_manipulator`,
type `WheeledManipulator`); teleop/self-collision still WIP by another agent,
not blocking. Confirmed working end to end in A3.

---

## A0 — Research repo skeleton ✅ (commit `baa2799`)

## A1 — OpenRAL fork → Python 3.10 on Humble ✅ (openral `4c1867c`, pushed)

5236 passed / 4 failed (verified pre-existing) / 2 errors. Details:
`docs/openral_py310_patch.md`.

## A2 — Map the pinned OpenRAL revision ✅ (`docs/openral_integration_notes.md`)

Reasoner → dispatch → rSkill → safety path traced; insertion point decided
(subclass `ReasonerNode`, override `_dispatch_execute_rskill` only, zero
upstream changes needed).

## A3 — Map the pinned SRB revision ✅ (`docs/srb_integration_notes.md`)

**Read-only throughout — no edits/commits/branches under `space_robotics_bench/`.**

- `lunar_bot` + `_ground_manipulation` (`env.robot=lunar_bot` Hydra override)
  runs headless: 729 steps / 20s, ~36 steps/s.
- ROS interface verified in both directions: `agent zero/rand` publish
  observation topics + one combined action *echo* (no external control);
  `agent ros` mode instead subscribes per action-term (`cmd_vel` Twist, IK
  Twist, gripper Bool, four-wheel-steer array) — this is the real control
  surface, not the combined vector.
- **Verified a ROS command actually moves the robot**: publishing
  `geometry_msgs/Twist` on `/srb/env0/action/cmd_vel` moved `srb/env0/robot`'s
  base from x=-0.131 to x=0.496 over ~4s.
- Two host-environment traps found and fixed (both pre-existing conditions of
  this machine, not SRB bugs): (1) `~/.bashrc`'s default ROS-Humble sourcing
  puts the system cpython-310 `rclpy` on `PYTHONPATH` ahead of Isaac Sim's own
  bundled cpython-311 one, breaking `enable_ros2_bridge()`'s early-return
  check — unset `PYTHONPATH` for the SRB launch. (2) `ISAAC_SIM_PATH` was never
  set (only `ISAAC_SIM_PYTHON` was), so `get_isaacsim_path()` fell through to
  the hardcoded `/root/isaac-sim` (permission denied) — set it explicitly per
  launch; recommended (not done) to add to `~/.bashrc`.
- 21-joint `JointState` confirms the WheeledManipulator layout (4 steer + 4
  wheel + 7-DoF arm + 6-DoF gripper).
- **Process-hygiene incident**: a `pkill -f "srb agent zero"` pattern-matched
  and killed two of the other agent's long-running debug processes by
  accident (their command line only differed from this session's test by
  flag spelling). No repo damage — process-only, user said not to worry about
  it. Lesson recorded in `docs/srb_integration_notes.md` §4: resolve and kill
  the exact PID only, never a substring pattern, on this shared host.

## A4 — Phase A exit demonstration — next

- [ ] OpenRAL and SRB alive at the same time; one SRB topic readable from the
      OpenRAL side (a plain `ros2 topic echo` from an OpenRAL-side shell is
      sufficient evidence — no rSkill dispatch wiring required yet, that is
      Phase B). Clear stale `/dev/shm/fastrtps_*` first if Fast-DDS complains.
- [ ] Commit `docs/srb_integration_notes.md` (done) is already staged;
      finalize this file's own "done" state once the joint demo runs once.
- [ ] Seed `docs/research_findings.md` (§21.10) with the mission-relevant
      findings from A2/A3 (existing mission-invalidity gates, reward-gated
      verification, per-term action topics as the likely OpenRAL↔SRB seam).

---

## Rules

- Branch or worktree per task; delete after merge (AGENT.md §1).
- Overwrite-update this file and `handoff.md`; ≤150 lines each (AGENT.md §2).
- No pytest beyond upstream's own suites (AGENT.md §3).
- No defensive coding, no hash checks, no corner-case guards (AGENT.md §4).
- **No `space_runtime` / `space_context` code until Phase A is finished.**
- Upstream modifications confined to `docs/openral_py310_patch.md`.
  `space_robotics_bench/` stays untouched — another agent owns it; on this
  shared host, kill only exact PIDs you launched yourself, never a pattern.
