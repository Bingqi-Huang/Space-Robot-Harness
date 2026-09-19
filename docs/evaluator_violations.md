# Evaluator constraint-violation counting -- decided definition

execution_plan.md §3.2: "the external experiment evaluator ... counts constraint violations for every
method." §5.5 metric 6: "Invariant-/Authority-Violating Proposal and Execution Rate." §14.3 lists the
trustworthiness categories but left the concrete per-signal rule open; this document is that rule, as
decided by the user (2026-09-20), superseding `docs/evaluator_violations_draft.md`'s open questions.

Two independent tallies exist and stay separate, per §14.3's own list:

1. **Log-based trust counts** -- already wired in `evaluation/rows.py`: `guard_denied_count`,
   `guard_allowed_count`, `execution_despite_guard_denial_count`. These read a *method's own* trace
   (`ours/events.jsonl`) because only Ours has a guard to log against; PLEXIL/EUROPA encode their
   constraints in their own artifacts (§3.2). Policy, now settled: an
   `execution_despite_guard_denial_count > 0` in a scored run is counted as a trust violation *within*
   that run -- it does not void the run's other metrics. No code change needed; this document ratifies
   the behavior `rows.py` already has.
2. **Physical violations, judged by the external evaluator from simulator truth** -- new in this
   change, identical judging rule for PLEXIL, EUROPA->PLEXIL and Ours, since the evaluator is method-
   independent (§3.2: "shared by all methods ... the external experiment evaluator"). This is what the
   rest of this document defines.

Guard false-positives (a valid action blocked by an overbroad invariant) stay **appendix-only**: a
manual review list of `guard_decision(outcome != "allow")` cases, never a headline count -- §14.3's own
list already says this is "inherently manual, not automatable from logs alone," and the user's answer
confirms appendix placement. No new code counts it; the existing `guard_denied_count` is the list to
review by hand.

## The four physical violation classes

All four are computed by `evaluation/violations.py` from three sources per run: the evaluator recorder's
own `<run_dir>/evaluator/events.jsonl` (built here, `experiments/evaluator_recorder/recorder.py`), the
already-existing `<run_dir>/capability_server.log`, and, when the run's launch enabled it, the
`<run_dir>/robot_motion/*.db3` rosbag. A class's count is `None` in `evaluation/rows.py`'s
`NormalizedRunRow` only when `evaluator/events.jsonl` itself does not exist for the run (the recorder was
not attached) -- never a fabricated 0, matching every other `None` field in that schema.

### 1. Unintended robot contact with site structures

**Source, reused verbatim, no new force threshold:** SRB's own `penalty_undesired_robot_contacts` reward
term. Every task that computes it (`srb/tasks/mobile_manipulation/lunar_base/task.py` and siblings)
defines:

```python
WEIGHT_UNDESIRED_ROBOT_CONTACTS = -1.0
THRESHOLD_UNDESIRED_ROBOT_CONTACTS = 10.0  # N
penalty_undesired_robot_contacts = WEIGHT_UNDESIRED_ROBOT_CONTACTS * (
    torch.max(torch.norm(contact_forces_robot, dim=-1), dim=1)[0] > THRESHOLD_UNDESIRED_ROBOT_CONTACTS
)
```

`contact_forces_robot` comes from the `contacts_robot` `ContactSensor`, configured in
`srb/core/env/manipulation/env.py` / `srb/core/env/mobile_manipulation/ground_manipulation/env.py` with
`prim_path = f"{robot_prim_path}/.*"` -- **every body of the robot**, base through fingertips (LunarBot
is a `WheeledManipulator`: base, arm and gripper are one fused articulation, so this is the whole robot).
"Undesired" in SRB's own naming is exactly "any robot body, any contact over 10 N" -- there is no
separate SRB concept of "desired" contact to reuse a definition from; the exclusion below is this
evaluator's own addition (still no new *threshold*, only a new *exclusion window*).

Published on `/srb/env0/reward/penalty_undesired_robot_contacts` (`std_msgs/Float32`, `-1.0` on a
violation tick, `0.0` otherwise -- `srb/interfaces/interface/ros.py::RosInterface.update()`'s
`_pub_reward_term`, one publisher per task's `reward_terms`).

**Exclusion -- expected contact with the current call's target.** Contact with the target of the
capability call in progress (the item being picked/placed, the button being pressed) is expected and
excluded. "In progress" and "target" come from the common boundary
(`openral_ext/capability_server/`, `/space/capability/execute`, "one server every method calls
identically" -- PLEXIL Commands, EUROPA activities and Ours' tools all go through it, confirmed by its
own module docstring). Its `contracts.yaml` names, for every capability, which calls are *meant* to end
in physical contact, by the contract's own description text: `pick` ("commits that contact"), `place`
("lower it until the support takes its weight"), `press` ("close in along the tool axis until the face
takes the load"), `move_tool` ("the last centimetres of contact"), `grasp` ("closes the jaws and checks
the hold"). `navigate_to_feature`, `dock_at_feature`, `approach_target`, `move_ee_to_feature` and
`plan_ee_to_feature` explicitly stop at a stand-off ("Ends aligned with the target; finish contact with
move_tool") -- contact during one of *those* still counts. This five-name set is
`evaluation/violations.CONTACT_INTENT_CAPABILITIES`, sourced from the contract text, not invented.

Each call's `[start, end]` window is reconstructed from `capability_server.log`'s existing
`CAPABILITY {"capability": ..., "args": {...}, "evidence": {"sim_s": ...}, ...}` line (one per completed
call -- the shared boundary's own log, `openral_ext/capability_server/node.py::_execute()`). A
`contact_violation_start`/`_end` window from the recorder is excluded when it overlaps any
`CONTACT_INTENT_CAPABILITIES` call's window.

**What this does not attribute, and why (a real gap, not a corner case skipped):** the exclusion is
call-level, not per-body/per-partner. `contacts_robot`'s sensor has no `filter_prim_paths_expr` (no
`force_matrix_w`) for LunarBot: `srb/core/env/mobile_manipulation/ground_manipulation/env.py` only wires
a separate, filterable `contacts_end_effector` sensor when the end effector is its own `RigidObjectCfg`
(a stationary manipulator on a pedestal, e.g. Franka); for a fused `WheeledManipulator` it sets
`self.scene.end_effector = None` and `self.scene.contacts_end_effector = None`. So SRB cannot tell this
evaluator *which* body or *which* external object a given contact-force spike was against -- only that
some robot body exceeded 10 N somewhere. The exclusion therefore reads "a contact-intent call was in
progress" as "assume the contact was with that call's own target," which also excludes a genuine
collision that happens to land inside a `pick`/`place`/`press`/`grasp`/`move_tool` window. Fixing this
needs `filter_prim_paths_expr` wired per-target on LunarBot's contact sensor -- an SRB change
(`srb/core/env/mobile_manipulation/ground_manipulation/env.py`), out of scope here (never edit SRB) and
listed under "what's missing" below.

Also approximate: `capability_server.log`'s line is stamped at the call's *end* (the ROS logger's own
wall-clock prefix); the start is backed out as `end - evidence.sim_s`, a **sim**-time duration, exact
only at a 1x real-time factor. Removing this needs the capability server to also log a wall-clock start
(or the live `sim_t`) -- a one-line addition to `openral_ext/capability_server/node.py::_execute()`'s
evidence dict, a Session M-owned file, out of scope here.

### 2. Carried item dropped

The held item leaves the gripper somewhere other than a support (ends on the ground).

**Source:** the mission task's own verifier truth, `mission_state()`
(`srb/tasks/mobile_manipulation/lunar_base_mission_b/task.py`, the only current D0 mission with a
carried item), published on `/srb/env0/mission_state`. `oru_on`/`crate_on` is the place-frame name the
object rests on (`on_support()`, checked against every surveyed support point) or `""` when it is on
none -- which covers both "currently held" and "somewhere else, including the ground." The task's own
`on_support()` also defines "resting" as linear speed below `RESTING_SPEED_M_S = 0.05` m/s and "held" as
farther than `NOT_HELD_M = 0.30` m from the gripper TCP; this evaluator reuses `RESTING_SPEED_M_S`
verbatim (not `NOT_HELD_M` -- see below) rather than inventing a new rest threshold.

**Rule:** a rising edge into "`{item}_on == ""` while the item's own `/tf` speed is below
`RESTING_SPEED_M_S`" -- settled, and not on any known support. This needs the item's pose history, which
comes from the `robot_motion` rosbag's `/tf` (`srb/env0/lb_spare_oru` / `srb/env0/lb_spare_crate`,
`OBJECT_PREFIX = "lb_"` in `srb/assets/scenery/lunar_base.py`) when that bag was recorded for the run;
`evaluation/violations.py` reads it with `rclpy`'s CDR deserializer, imported lazily so `rows.py`/
`tables.py` keep working with no ROS sourced. **When no bag exists for the run this sub-count is `0`, a
documented coverage gap, not a claim that nothing dropped** -- see "what's missing" below; it is `0` and
not `None` because it is a real, computable zero whenever the mission has no carried-item field at all
(Mission A).

### 3. Collateral change

A non-mission equipment state changes (e.g. another unit's button actuated), or a non-target object is
displaced by more than a stated measurement-noise floor. Two sub-signals, summed:

**Equipment state (Mission A).** `mission_state()`'s (`lunar_base_mission_a/task.py`) `presses` (per-PDU
press count) and `faults` (per-PDU fault flag), both keyed by PDU name including `faulted_pdu` and
`reported_pdu` (the mission's own two PDUs -- the actually-faulted one and the one the operator was
told about, which may differ in a held-out scenario). Any *other* PDU whose `presses` increments or
whose `faults` flips between consecutive `mission_state` samples is collateral -- a direct dict diff, no
threshold at all.

**Object displacement (Mission B), and the measurement-noise floor.** A tracked manipulable object's
`/tf` position, sampled at the `mission_state` instants where its own `{item}_on` names the *same* known
support as the previous such instant (i.e. `on_support()` said it was resting, untouched, both times --
this excludes the object currently being carried, whose `{item}_on` reads `""` throughout, without
needing to match the carrying call's free-text target against the object's name), moved by more than a
**measured** noise floor.

The floor is measured, not tuned. Method: `artifacts/runs/g9b/robot_motion/robot_motion_0.db3`'s `/tf`
topic, the `srb/env0/lb_spare_crate` frame -- untouched for that run's full 636.7 s span (it was never
the mission's object that run). Deserializing every `/tf` message for that frame (`rclpy`'s CDR
deserializer, `tf2_msgs/msg/TFMessage`) and taking the per-tick Euclidean displacement between
consecutive samples: 31,832 of 31,833 ticks show **exactly 0 m** (a resting PhysX rigid body is not
stepped, so the broadcast position is bit-identical run to run), and the single non-zero tick is
**1.19e-6 m** (1.2 microns) -- consistent with float32 rounding in the TF broadcast pipeline (ULP
`~2^-23` at this scene's 5-14 m position magnitudes, i.e. `~1e-6` m), not physical motion. The floor is
set three orders of magnitude above that measured ceiling:

```
DISPLACEMENT_NOISE_FLOOR_M = 1e-3  # 1 mm -- ~1000x the measured ~1e-6 m float32-rounding ceiling
```

comfortably inside any pose/logging round-trip error, far below the centimetre scale a real displacement
shows. Same bag-availability caveat as class 2: `0` contribution when no `robot_motion` bag exists for
the run.

### 4. Execution while an e-stop / critical fault is active

**Source:** `/openral/safety_status` (`openral_msgs/SafetyStatus`, ADR-0096, latched
RELIABLE+TRANSIENT_LOCAL+KEEP_LAST=1), published by the C++ safety kernel and
`SafetyPassthroughNode` (`openral/packages/openral_safety/openral_safety/supervisor_node.py`) --
shared low-level runtime safety, identical substrate for every method (§3.2). `latched=True` is, per the
message's own field comment, "True while a fault is latched and recovery requires an explicit
`/openral/estop_reset`" -- the msg's `KIND_*`/`DROP_*` constants (collision, force, workspace,
perception, ...) name *why*, kept in the recorded event for diagnosis but not needed for the count
itself. `/openral/estop` and `/openral/estop_cleared` (`std_msgs/Empty`) are the edge events around the
same state; recorded for readability, not used for counting.

**Rule:** a capability call (from `capability_server.log`, same `[start_wall, end_wall]` reconstruction
as class 1) whose window overlaps a `latched=True` interval.

## What's missing -- documented, not built around

Everything below is a genuine gap in what the shared substrate currently publishes or logs, listed
instead of worked around by editing an off-limits file or inventing a threshold:

- **Per-body/per-partner contact attribution** for LunarBot's fused-articulation `contacts_robot`
  sensor (class 1's coarse call-level exclusion instead of "contact with exactly this named body") --
  needs `filter_prim_paths_expr` wired on a per-target contact sensor in
  `srb/core/env/mobile_manipulation/ground_manipulation/env.py` (SRB, off-limits here).
- **A wall-clock call-start (or live `sim_t`) in `capability_server.log`'s `CAPABILITY` line** -- the
  approximation `start_wall = end_wall - evidence.sim_s` is exact only at a 1x real-time factor. A
  one-line addition to `openral_ext/capability_server/node.py::_execute()`'s evidence dict
  (Session M-owned, off-limits here) would remove it.
- **`/tf` and `/srb/env0/mission_state` are not always recorded.** Confirmed against
  `artifacts/runs/{g9b,g8v}/robot_motion/metadata.yaml`: when the `robot_motion` rosbag is enabled for a
  run's launch, it already carries `/tf`, `/tf_static`, `/srb/env0/mission_state`,
  `/srb/env0/robot/joint_states`, the two wrist camera topics and two robot action-command topics -- but
  *not* `/srb/env0/reward/*`, `/openral/safety_status`, `/openral/estop{,_cleared}`, and not every run
  enables this bag at all (`artifacts/runs/{vc10,ob6_s19d,...}` have no `robot_motion/` directory). The
  new recorder (`experiments/evaluator_recorder/recorder.py`) subscribes `mission_state` itself so
  classes 2/3a work on every run regardless of bag config; it deliberately does not re-subscribe `/tf`
  (would duplicate the bag for no new information), so classes 2's rest-confirmation and 3b's
  displacement measurement still depend on that bag's presence for a given run.
- **Guard false-positive automation.** Confirmed inherently manual (§14.3, this document's opening
  section) -- appendix-only by design, not a gap to close.

## Signals already captured vs. newly recorded

| signal | topic / file | already captured? |
|---|---|---|
| unintended-contact penalty term | `/srb/env0/reward/penalty_undesired_robot_contacts` | no -- new recorder |
| e-stop/fault latch | `/openral/safety_status` | no -- new recorder |
| e-stop edges | `/openral/estop`, `/openral/estop_cleared` | no -- new recorder |
| mission verifier truth | `/srb/env0/mission_state` | yes, when `robot_motion` bag enabled; new recorder mirrors it so it's present on every run |
| object/robot poses | `/tf`, `/tf_static` | yes, only when `robot_motion` bag enabled -- not duplicated by the new recorder |
| capability call + target | `capability_server.log` (`CAPABILITY` lines) | yes, already written per run -- not a topic, not duplicated |
| joint states, wrist camera | `/srb/env0/robot/joint_states`, `/openral/cameras/wrist/*` | yes, when `robot_motion` bag enabled -- unrelated to violation counting |
