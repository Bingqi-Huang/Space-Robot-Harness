# mission_verifier

Independent mission-effect verifier (execution_plan.md §8.3 item 7 / §4.4
"Independent effect verification"), for the `panel_remount` task.

## Why this exists

§4.4's stated purpose: "establish what physically happened without asking
the model to certify itself and without encoding a hidden procedure." The
`panel_remount` task already computes its own binary success signal
(`termination_success` in `task.py`, published as `/srb/env0/terminated`)
— this node does **not** just relay that. It independently recomputes the
same geometric test (panel pose vs. a fixed target pose, position +
orientation tolerance) from a completely separate input (`/tf`, read
directly, not via the task's internal reward/termination code path), then
cross-checks its own judgment against the task's self-report when the task
reports success — logging a warning if they ever disagree.

## Layout

- `schemas.py` — `VerifierEvent` (Pydantic): the generic, task-agnostic
  event envelope from §4.4's spec (condition, holds, evidence source/ref,
  timestamp/state version, confidence, detail). No mission-specific logic.
- `panel_remount_logic.py` — pure functions (`panel_at_target`,
  `panel_displaced`), no ROS/torch import, independently testable.
  Constants (target pose, tolerances) transcribed from `task.py`, cited by
  line.
- `node.py` — the rclpy node. Subscribes `/tf` (`srb/env0/panel`),
  `/srb/env0/terminated`, `/srb/env0/truncated`; publishes `VerifierEvent`
  JSON on `/space_harness/verifier_events` (`std_msgs/String`).
- `smoke_test_logic.py` — offline check (no ROS/sim), run directly with
  `python3`.

## Topic / schema

- Publishes: `/space_harness/verifier_events` (`std_msgs/String`, JSON body
  = `VerifierEvent.model_dump_json()`).
- `VerifierEvent.condition` ∈ `{object_displaced, object_at_target,
  episode_terminated}`.
- `VerifierEvent.evidence_source` ∈ `{simulator_truth, task_self_report}`
  — `object_displaced`/`object_at_target` are always `simulator_truth`
  (computed from raw `/tf`); `episode_terminated` is `task_self_report`
  (mirrors `/srb/env0/terminated`, `detail` records whether the
  independent judgment agreed).

## What it deliberately does NOT do

- Does not write to `space_runtime/` (out of scope until Phase B hits a
  real failure — execution_plan.md §21.6-7).
- Does not duplicate full `WorldState` (§4.4: "Robot kinematics,
  detections, transforms... remain owned by OpenRAL WorldState").
- Does not use OpenRAL's perception-based object detector (a different,
  already-existing layer — see `sensor_bridge_node.py`'s docstring,
  "the object detector"). This verifier reads simulator ground truth
  directly instead, per §4.4's explicit allow-list ("deterministic
  simulator truth for evaluation/verification").
- No mission-specific *strategy* logic (§8.2's forbidden-mission-logic
  rule) — only effect questions.

## Running it

Needs the same ROS environment activation this project already uses
elsewhere (`docs/openral_py310_patch.md`) — ROS Humble's system Python 3.10,
conda unset, `miniconda3` stripped from `PATH`:

```bash
cd space-robot-harness-item7-verifier   # this worktree
env -u CONDA_PREFIX -u CONDA_EXE -u CONDA_PYTHON_EXE -u CONDA_DEFAULT_ENV \
    -u CONDA_SHLVL -u CONDA_PROMPT_MODIFIER \
    PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniconda3 | paste -sd:)" \
    PYTHONPATH="$(pwd)" \
    ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    bash -c 'source /opt/ros/humble/setup.bash && python3 -m openral_ext.mission_verifier.node'
```

Requires `pydantic` in that Python 3.10 environment (confirmed present at
2.10.5 via the system ROS install — no extra install needed on this host).
Deliberately uses stdlib `logging`, not `structlog` — this package doesn't
depend on `openral`'s own venv being active, only on ROS Humble's `rclpy` +
system `pydantic`.

## Live-verifying against a running `openral deploy sim` graph

1. Bring the graph up (`openral deploy sim --config
   scenes/deploy/srb_panel_remount_gui.yaml`, ROS_DOMAIN_ID=77) and confirm
   `/srb/env0/terminated` and `/tf` are flowing (e.g. `ros2 topic echo
   /srb/env0/terminated`).
2. Run this node (command above) in a third terminal, same domain.
3. `ros2 topic echo /space_harness/verifier_events` — expect a steady
   stream of `object_at_target`/`object_displaced` events at ~5 Hz once
   `/tf` has `srb/env0/panel`.
4. Manually drive the panel to its target (e.g. via the existing procedural
   rSkills — `move_ee_to_pose` + `grasp` + `release`, or just teleport it
   in the GUI for a quick check) and confirm `object_at_target.holds`
   flips `true` at the same moment `/srb/env0/terminated` does, and that
   `episode_terminated`'s `detail` says `independent_check=agrees`.
5. A pass is: no `mission_verifier.crosscheck_mismatch` warning logged
   across a run that reaches `terminated=True`, and `object_displaced`
   flips `true` before `object_at_target` does (panel visibly moves before
   it arrives).
