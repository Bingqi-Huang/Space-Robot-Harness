# Handoff

State as of 2026-09-13. Phase A nearly done — A0/A1/A2/A3 complete, A4 next.
Task list: `todo.md`. Decisions: `docs/upstream_pins.md`.
OpenRAL: `docs/openral_py310_patch.md`, `docs/openral_integration_notes.md`.
SRB: `docs/srb_integration_notes.md`.

## Done: A0, A1, A2, A3

A0–A2 recap: research repo on `main`, OpenRAL fork downgraded to Python
3.10/Humble (submodule pinned to `4c1867c`, 5236 tests passing), full
reasoner→dispatch→safety path mapped, insertion point decided (subclass
`ReasonerNode`, override `_dispatch_execute_rskill` only).

**A3 (new this session)** — embodiment is **LunarBot** per explicit user
decision (already integrated; teleop/self-collision still WIP by another
agent, not blocking). Verified end to end:

- `srb agent rand --env _ground_manipulation env.robot=lunar_bot --headless`
  runs clean.
- ROS interface confirmed in both directions. `agent zero/rand` only echo an
  action vector (no external control possible there). **`agent ros` mode is
  the real control surface** — per-action-term subscriptions:
  `/srb/env0/action/cmd_vel` (Twist, base), `.../robot/robot/differential_inverse_kinematics`
  (Twist, 7-DoF arm), `.../robot/robot/binary_joint_position` (Bool, gripper),
  `.../robot/robot/four_wheel_steer` (Float32MultiArray, per-wheel).
- **Verified a published Twist actually moves the robot** — base x went
  -0.131 → 0.496 over ~4s of commanding.
- 21-joint `JointState` matches the WheeledManipulator layout (4 steer + 4
  wheel + 7-DoF arm + 6-DoF gripper).

Two host-environment fixes (both environment pollution on this machine, not
SRB bugs), full detail in `docs/srb_integration_notes.md` §2:
1. `~/.bashrc` sources ROS Humble by default → system cpython-310 `rclpy`
   lands on `PYTHONPATH` before Isaac Sim's own bundled cpython-311 one,
   short-circuiting `enable_ros2_bridge()`'s `find_spec("rclpy")` check and
   crashing. Fix: unset `PYTHONPATH` for the SRB launch.
2. `ISAAC_SIM_PATH` was never set (only `ISAAC_SIM_PYTHON` was) →
   `get_isaacsim_path()` falls through to the hardcoded `/root/isaac-sim`
   (permission denied). Fix: set it explicitly per-launch. **Recommended to
   the user to add to `~/.bashrc` — not done unilaterally.**

**Incident, disclosed to and cleared by the user**: `pkill -f "srb agent
zero"` (meant to stop this session's own test process) pattern-matched and
killed two of the other agent's long-running debug processes — their command
line differed only by flag spelling. No repo/file damage; process-only. User
said not to worry about it. **Lesson, recorded in `docs/srb_integration_notes.md`
§4: on this shared host, resolve and kill only the exact PID you launched —
including the reparented kit-python child (killing the wrapper does not
reliably take it down) — never a substring pattern.**

## Next: A4, then Phase B can start

- Bring up OpenRAL and SRB at the same time; confirm one SRB topic is
  readable from the OpenRAL side (a bare `ros2 topic echo` is enough — no
  rSkill wiring yet, that's Phase B). Clear stale `/dev/shm/fastrtps_*` first
  if Fast-DDS complains.
- Seed `docs/research_findings.md` (§21.10) — carry forward: OpenRAL's
  existing mission-invalidity gates (§A2), the reward-gated verification
  mechanism already in place, and that SRB's per-action-term topics (not the
  combined vector) are the natural OpenRAL↔SRB seam for Phase B.

## Watch out

- SRB launches on this host need: `PYTHONPATH` unset, `ISAAC_SIM_PATH` set,
  conda stripped (same as the OpenRAL C++ build) — the exact invocation is in
  `docs/srb_integration_notes.md` §2.
- **Never `pkill -f` on this host.** Always `ps`/`pgrep -a -f`, read the full
  command line, kill the exact PID(s) — this machine runs concurrent Isaac Sim
  instances across sessions.
- `space_robotics_bench/` stays untouched — read/run only, ever.
- No `space_runtime` / `space_context` code until Phase A is fully finished
  (plan §21.6–7 — mechanisms follow observed failures, not the other way
  around).
