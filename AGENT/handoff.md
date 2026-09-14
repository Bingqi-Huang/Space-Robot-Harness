# Handoff

State as of 2026-09-14. Phase A complete. Phase B1 done and verified
live: LunarBot is a genuine mobile manipulator — base (BODY_TWIST), arm
(CARTESIAN_TWIST + JOINT_POSITION, RM-75 limits enforced), gripper
(GRIPPER_BINARY) — all through the real safety chain from one HAL.
Mission A's SRB task (`panel_remount` v1) is built. But the reasoner has
never been in the loop for this robot, no sensor reaches OpenRAL, and no
rSkill can move the arm (F21) — Phase B2 (capability set) is next.
Task list: `todo.md`. Findings: `docs/research_findings.md`. Key docs:
`docs/lunar_bot_capability_set_plan.md`, `docs/mission_a_panel_remount.md`,
`docs/lunar_bot_joint_position_control.md`, `docs/lunar_bot_rm75_spec.md`.

## Where things stand

Branch chains — openral: `feat/py310-humble` → `feat/lunar-bot-hal`
(`f47e966`) → `fix/body-twist-speed-envelope` (`fabe588`) →
`feat/lunar-bot-arm-gripper` (`af8fba2`) → `feat/arm-joint-position-control`
(current). SRB: `main` (`9caeb46`) → `feat/panel-remount-mission-a`
(`b3e8d92`) → `feat/switchable-arm-control` (`90f9d5e`). All pushed, all
still open, none merged.

**`space_robotics_bench/` is a real git submodule** (`docs/upstream_pins.md`)
— the agent that developed it independently no longer manages it, so this
project edits/commits there directly now, same discipline as `openral/`.

## Next — Phase B2, the LunarBot capability set (plan revised 2026-09-14)

The user's ruling: Mission A does not start until its prerequisites exist,
and every blocking piece of infrastructure gets built (only IL data
collection and VLA training are out of scope). `execution_plan.md` was
revised accordingly (rules 0.11/0.12, §2 layout, §6.2, §6.4 status, §8.1
filled in, new §8.3, §9.1, Phase B split B1/B2/B3, §21 reordered). The
capability-set design and reuse survey is `docs/lunar_bot_capability_set_plan.md`;
the task list is in `todo.md`. Item 1 (RM-75 limits, F22) is done on
`openral/feat/lunar-bot-capability-set` @ `f7b5ccd`; items 2–9 not started.
**Open questions for the user** (plan doc §4): does the real LunarBot have
a lidar; keep MoveIt in scope; confirm no `openral deploy sim` SRB backend.
The user separates planning rounds from coding rounds — wait for an
explicit go before building item 2.

Also open: F19 (base `cmd_vel` in-place-rotation instability — probably
don't rely on it for precise heading control yet), no arm joint position
limits declared (a real, flagged gap), and the same missing-magnitude-check
gap for `kJointTrajectory`/`kCartesianDelta`/`kGripperBinary`(per-joint)/
`kGripperPosition`/`kCompositeMode` (F12/F16's sibling gap, untouched).

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
- **F18 — SRB's procedural moon terrain is only flat within ~4 m of the env
  origin** (`flat_area_size` in `srb/core/env/common/base/env_cfg.py`).
  A rigid object spawned outside that pad can end up embedded in uneven
  terrain; PhysX's depenetration solver then ejects it and it falls/flies
  indefinitely in the Moon's weak gravity instead of settling. Keep any new
  scene object within ~1.5–2 m of the env origin unless you've confirmed
  the terrain is flat further out.
- **F19 — LunarBot's base drifts/rotates incoherently on a large in-place
  `cmd_vel` turn** (likely the 4WIS/4WID `max_steering_angle: 120°` limit
  saturating for a real pivot). Also don't forget `scale_linear=-1.0`/
  `scale_angular=-1.0` (already in `lunarbot.py`) — a naive P-controller
  drives the wrong way unless negated. Not resolved; avoid relying on
  `cmd_vel` for precise heading control until this is understood.
- **F20 — a JOINT_* chunk's wire row is ALWAYS the full robot-wide vector**,
  even when `action.joint_names` names a subset (ADR-0102) — the C++
  kernel's structural check forces `chunk.n_dof == envelope.n_dof`
  regardless. `joint_names` only marks which slots are the real ones; it
  never shrinks the row. Caught this the hard way (silently dropped every
  JOINT_POSITION dispatch) — see `docs/lunar_bot_joint_position_control.md`.
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
- Colcon rebuild of the safety kernel: conda stripped from env (`env -u
  CONDA_PREFIX ...` + miniconda stripped from `PATH`), `--merge-install`
  (this workspace's `install/` layout), both `PYTHON_EXECUTABLE` and
  `Python3_EXECUTABLE` pointed at `.venv/bin/python`.

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
