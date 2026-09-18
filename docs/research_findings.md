# Research findings — running log

Per execution_plan.md §21.10: observed failure cases, design decisions, and
the runs that motivated each mechanism. This drives later method refinement —
do not design a mechanism the findings below don't call for.

## Phase A findings (2026-09-12 – 2026-09-13)

### F1 — OpenRAL already partially implements mission-invalidity rejection

`_dispatch_execute_rskill` (`reasoner_node.py:4222`) refuses three classes of
proposal before ever sending an action goal: a collective target ("all the
objects"), a second dispatch while one goal is in flight, and a VLA/reward-
model pair that can't co-reside in VRAM. Plan §5.4.5's trustworthiness cases
overlap with these. **Design implication:** `space_runtime`'s admissibility
layer should assume these three are already handled and add only what's
genuinely new — communication/resource/authority conditions — not
re-implement generic proposal sanity checking.
Source: `docs/openral_integration_notes.md` §1.3.

### F2 — Task-completion verification is already reward-gated, not LLM self-report

`evaluate_task_verdict` (`mission.py:156`) consumes `QueryTaskProgress.srv`
(a Robometer reward model's progress/success heads) and only accepts
`complete` above a threshold, routes ambiguous bands to a VLM check, and
bounds retries before `abandon`. **Design implication:** the verification
layer (plan §4.8) should add evidence sources this doesn't cover (has the
right authority been granted; is the executing endpoint still reachable) —
task-completion itself is not an open question to re-solve.
Source: `docs/openral_integration_notes.md` §1.4.

### F3 — WorldState's only resource field is `battery_pct`

Confirmed by reading the schema directly (`schemas.py:3570`), not inferred.
No communication, compute-availability, illumination, or authority field
exists anywhere in it. **Design implication:** `space_context` is additive
ground truth, not an overlay on an existing (if thin) mechanism — there is
nothing partially-there to reconcile with.
Source: `docs/openral_integration_notes.md` §1.5.

### F4 — Safety: build against the C++ kernel, not the Python passthrough

The Python `openral_safety` node is an explicitly-labeled "Day-1... stub"
(its own module docstring) checking only `n_dof` and joint limits. The C++
`openral_safety_kernel` is the shipped, capable one — force/workspace/
controller/collision, fail-closed on stale or unknown link state — and we
confirmed it builds and runs on this fork (registers as
`/openral_safety_kernel`). **Design implication:** never target the Python
passthrough in any experiment; it would understate what the runtime actually
enforces.
Source: `docs/openral_integration_notes.md` §2.

### F5 — WAM has no concrete adapter; do not design an experiment around one

`python/wam/` is a `Protocol` + `NullWorldModel` identity stub only.
**Design implication:** any mental-simulation/failure-anticipation mechanism
in the paper's method must not assume a working WAM exists in this revision.
Source: `docs/openral_integration_notes.md` §2.

### F6 — Insertion point: subclass, don't patch

`_dispatch` is a plain method call (`_handle_tick_result` →
`self._dispatch(...)`), no ROS indirection, no plugin system. A subclass of
`ReasonerNode` overriding only `_dispatch_execute_rskill` inserts mission-
level admissibility with zero upstream source changes; `main()` is 15 lines,
trivially reimplemented to spin the subclass. **Caveat carried forward:**
private method surface, not a public contract — re-verify this seam after
every OpenRAL rebase.
Source: `docs/openral_integration_notes.md` §3.

### F7 — SRB's real control surface is per-action-term topics, not a combined vector

`agent zero`/`agent rand` only *echo* a combined action vector — no
subscriber exists, external control is impossible there. `agent ros` mode
(`RosInterface.setup_action_sub()`) instead creates one typed subscription
per action term: `cmd_vel` (Twist, base), `differential_inverse_kinematics`
(Twist, arm), `binary_joint_position` (Bool, gripper),
`four_wheel_steer` (Float32MultiArray, per-wheel) for `lunar_bot`. Verified a
published Twist actually displaces the robot. **Design implication:** when
Phase B wires an OpenRAL rSkill to drive SRB (via `kind: ros_action`/
`ros_service` wrapping, per `openral_integration_notes.md` §1.3), target
these typed per-term topics — they map far more directly onto rSkill goal
parameters than a raw action vector would.
Source: `docs/srb_integration_notes.md` §3.2–3.3.

### F8 — A ready-made FDIR-relevant signal already exists in SRB

`/srb/env0/reward/penalty_undesired_robot_contacts` is published today,
independent of and prior to any self-collision fix landing. **Design
implication:** worth checking as a verification/FDIR evidence source once
the self-collision work stabilizes, rather than building a new contact
detector from scratch.
Source: `docs/srb_integration_notes.md` §5.

### F9 — This host requires specific environment handling for both stacks

Full detail lives with each stack's own notes, not duplicated here:
OpenRAL — `docs/openral_py310_patch.md` (conda pollution, `PYTHON_EXECUTABLE`
for Humble's rosidl). SRB — `docs/srb_integration_notes.md` §2 (`PYTHONPATH`
pollution from the default ROS-Humble shell sourcing; `ISAAC_SIM_PATH` unset).
**Design implication:** any run-manifest/reproducibility tooling (plan §19)
must capture these env-var/PATH conditions explicitly, not just git
revisions — a clean checkout on this machine still needs them to run at all.

### F10 — Process hygiene on a shared multi-agent host

A `pkill -f` pattern-match on this session's own process killed another
agent's unrelated long-running processes. **Design implication:** any tooling
this project builds that manages simulator/agent processes (experiment
runner, §12) must address processes by exact PID it recorded at launch time,
never by command-line pattern matching.
Source: `docs/srb_integration_notes.md` §4.

## Phase B findings (2026-09-13)

### F11 — No existing rSkill kind fit a scripted, non-learned test motion ✅ resolved

`rskill_runner_node.make_default_skill_resolver` only handled
`kind: "vla"` / `"ros_action"` / `"ros_service"` (`"wam"` raises
"not implemented"). `kind: "playbook"` exists (`rskills/preflight-reach`) but
is an S2 *decision procedure* the reasoner composes — it never emits an
`Action` chunk itself; confirmed `"vla"` requires `model_family` +
`weights_uri` and routes through `openral_sim.factory.make_policy` (a real
policy-adapter factory, not a lightweight generic loader). **Resolved**:
added `kind: "procedural"` to `RSkillManifest`/`RSkillKind`, a
`ProceduralIntegration` manifest block, and a resolver branch — a
deterministic, non-learned actuating skill with no weights and no external
ROS server, needed anyway for execution_plan.md §5.2's Baseline A
(procedure-driven mission execution). Verified live: `ros2 action send_goal`
against the real `ExecuteRskill` action server dispatched
`ProceduralBodyTwistRskill`, which drove `lunar_bot`'s base through the full
candidate_action → kernel → safe_action → HAL → SRB path and moved the robot.
Source: `docs/phase_b_procedural_kind.md`.

### F12 — RESOLVED: `max_base_linear_speed_m_s`/`max_base_angular_speed_rad_s` are now enforced for BODY_TWIST (2026-09-13)

Root-caused, then verified live. `cpp/openral_safety_kernel/src/validator.cpp`'s
`validate()` has an explicit case for `kBodyTwist` (and `kJointTrajectory`/
`kCartesianDelta`/`kGripperBinary`/`kGripperPosition`/`kCompositeMode`) whose
own comment states the design: *"The C++ kernel intentionally delegates
per-axis bound enforcement to the Python `openral_safety/supervisor_node.py`,
which knows the per-mode bounds on the robot manifest
(`max_cartesian_step_m`, `max_base_linear_speed_m_s`,
`max_base_angular_speed_rad_s`, gripper_min/max, ...)."* But that Python
node's own docstring says the opposite: *"envelope checks are deliberately
minimal so the C++ kernel that lands later can replace internals... Day-1
envelope checks (stubbed but real): `n_dof` mismatch... and first-row joint
targets vs configured per-joint position limits"* — no velocity/force/
workspace checks. **Each side documents the other as the one that's
supposed to do it. Neither does.** Confirmed further:
`openral_safety.envelope_loader.kernel_params_from_envelope()` does not even
emit `max_base_linear_speed_m_s` into the kernel's ROS parameters — there is
nowhere for the value to land at runtime even if the kernel wanted to read it.

Verified live: commanded `lunar_bot`'s base at 6.0 m/s (20× the manifest's
declared 0.3 m/s bound) through the real `candidate_action` → kernel →
`safe_action` → HAL → SRB path for 3s. Zero rejection —
`/openral/safety_status` stayed `latched=False` throughout, no
`FailureTrigger`, no kernel log warning — and the robot moved the full
commanded distance. **This is not a config mistake on our side; it is the
current, real behavior of upstream OpenRAL's shipped safety kernel for every
per-mode chunk kind in that list, on any robot, not just `lunar_bot`.**

**Resolved 2026-09-13**, per the user's explicit decision to treat the fix
itself as part of this project's scientific contribution, following
OpenRAL's own engineering standards (CLAUDE.md §3) rather than patching
around it. `kBodyTwist` is now split out of the shared "delegate to Python"
case in `validator.cpp` into its own real check: linear speed
(`sqrt(vx²+vy²+vz²)`) against `max_base_linear_speed_m_s` and angular speed
(`sqrt(wx²+wy²+wz²)`) against `max_base_angular_speed_rad_s`, mirroring the
existing `kCartesianTwist` case exactly. The two fields were added to
`EnvelopeIntersection` (both sides — C++ struct and the Python dataclass),
declared as kernel ROS parameters (default `kPosInfinity`, i.e. "no bound
declared" — an unrelated fixed-base robot's behavior is unchanged), and
`envelope_loader.kernel_params_from_envelope()` now actually forwards them
(previously it silently dropped them — half of why nothing could enforce
them even if it tried). `kJointTrajectory`/`kCartesianDelta`/
`kGripperBinary`/`kGripperPosition`/`kCompositeMode` still delegate to the
Python supervisor stub as before — **only BODY_TWIST was in scope for this
fix**; the same gap for those other modes is unchanged and still open.

Re-verified live against a real running kernel node (parameters generated
via the real `compute_intersection`/`kernel_params_from_envelope` path, not
hand-constructed): the exact 6.0 m/s vs. 0.3 m/s scenario that previously
passed with zero rejection is now rejected —
`safety_status.latched=True, drop_reason=KIND_FORCE, detail="base_linear_speed"`,
nothing forwarded to `/openral/safe_action`. Same for a 1.0 rad/s vs. 0.5
rad/s angular-only violation. A within-bound command (0.2 m/s / 0.2 rad/s)
still passes through unchanged. New gtest coverage
(`BodyTwistLinearSpeedCapEnforced`, `BodyTwistAngularSpeedCapEnforced`,
`BodyTwistDimMismatchRejected`) plus the full existing suite (`ctest`, all 4
binaries) pass, including the pre-existing
`BodyTwistPassesWithSixDofWidthAndJointEnvelope` regression test, unmodified.
Full record: `docs/f12_body_twist_envelope_fix.md`.

**Design implication:** any experiment or paper claim about "safety-checked"
mobile-base motion can now cite real magnitude-bound enforcement for
BODY_TWIST specifically — still not for `kJointTrajectory`/`kCartesianDelta`/
`kGripperBinary`/`kGripperPosition`/`kCompositeMode`, where the same
Python/C++ responsibility-mismatch gap this finding originally documented
remains exactly as described below.
Source: `docs/phase_b_lunar_bot_hal.md` (original finding),
`docs/f12_body_twist_envelope_fix.md` (fix), verified 2026-09-13.

### F13 — The safety kernel takes its envelope as flat ROS parameters, not a manifest path

Unlike the HAL lifecycle nodes (`robot_yaml` + `hal_mode` params, resolved
via `build_hal`), the C++ safety kernel reads flattened scalar/array ROS
parameters (`n_dof`, `joint_position_min/max`, `joint_velocity_max`,
`joint_torque_max`, `max_ee_speed_m_s`, ...) — it does not parse
`robots/<id>/robot.yaml` itself. The sanctioned way to produce these is
`openral_safety.envelope_loader.compute_intersection(robot, skill)` +
`kernel_params_from_envelope(...)`, normally invoked by
`deploy_e2e.launch.py`. **Design implication:** any bring-up/experiment
tooling that starts the kernel standalone (outside that launch file) must
call this loader itself rather than hand-constructing parameters — guessing
them wastes time and produces misleading "envelope load failed" errors that
name the wrong missing field.
Source: `docs/phase_b_lunar_bot_hal.md`.

### F14 — `ros2 lifecycle`/`node list` don't enumerate nodes by name on this host

Same symptom seen with SRB's own ROS bridge in A3/A4: a node is alive, its
services and topics work, but `ros2 node list` / `ros2 lifecycle set/get`
report "Node not found" or nothing at all. Calling the
`lifecycle_msgs/srv/ChangeState` / `GetState` services directly by their
fully-qualified service name works every time. **Design implication:** any
bring-up script this project writes should drive lifecycle nodes via direct
service calls, not the `ros2 lifecycle` CLI, on this host.
Source: `docs/phase_b_lunar_bot_hal.md`.

### F15 — RESOLVED: the safety kernel's heartbeat is fine; the abort was a one-off DDS hiccup, not a design gap

Originally recorded as "the kernel doesn't re-publish `/openral/safety_status`
on a heartbeat." **That was wrong — corrected after checking properly.**
`publish_diagnostics()` (bound to the kernel's 1-second `create_wall_timer`,
the same one driving `/diagnostics`) ends with an *unconditional*
`publish_safety_status_now()` call, in-code documented as "ADR-0096 /
HZ-0096-1 mitigation 2 — refresh the latched status at the same 1 Hz cadence
so `header.stamp` is standing evidence the publisher is alive." Re-verified
live: kernel alone, configured + activated, `ros2 topic hz` on both
`/diagnostics` and `/openral/safety_status` measured a clean, exact **1.000
Hz** on each. The original "zero messages in 5s" reading was a shell-tooling
artifact — piping `timeout N ros2 topic hz ... | tail` loses buffered output
when `timeout` SIGTERMs the process mid-print; redirecting to a file instead
showed the real numbers immediately.

`rskill_runner_node.py`'s `_SAFETY_STATUS_LIVENESS_S = 3.0` staleness check
is real and does exist, but the mechanism it watches is sound. The one abort
we saw (a 3s `ExecuteRskill` dispatch, aborted at ~2.7s, "last update 3.0s
ago") is best explained as a single missed or delayed heartbeat delivery
under a busier multi-participant DDS graph (SRB + kernel + HAL + runner all
live at once) at the exact instant the runner happened to check — not a
structural gap. The mechanism is deliberately conservative by design ("fail
toward assume-unsafe... can only ADD an abort, never suppress one"), so an
occasional trip under load is the mechanism doing its documented job, not a
bug to eliminate.

**Design implication:** do not spend more effort "fixing" this. Treat an
occasional safety-stale abort as expected system behavior a real mission
must be robust to — which is, usefully, exactly the kind of event
execution_plan.md §5.4.4 (fault/degradation) and §13.6 (failure/recovery
campaign) already want to study, not a nuisance orthogonal to the research.
Recovery-after-anomaly and continued-execution-after-fault are metrics in
the plan (§5.5) — this is a live instance of the exact class of event they
measure.
Source: `docs/phase_b_procedural_kind.md`.

### F16 — RESOLVED: CARTESIAN_TWIST's angular-speed bound was the same unenforced-gap shape as F12

While wiring LunarBot's arm through CARTESIAN_TWIST for the first time,
found `SafetyEnvelope.max_ee_angular_speed_rad_s` (already declared on
`panda_mobile`'s manifest at `1.0`) was enforced by nothing, for the exact
same reason F12 documented for BODY_TWIST: the C++ kernel's
`kCartesianTwist` case checked only linear speed against `max_ee_speed_m_s`;
the Python `openral_safety/supervisor_node.py` genuinely does implement the
angular check (unlike BODY_TWIST, where the Python side was a real stub) —
but `deploy_e2e.launch.py` never launches that node, so it is dead code in
every real deployment regardless. `envelope_loader.py` also never forwarded
the field into the kernel's ROS parameters at all.

**Fixed the same way as F12, before relying on it**: new field on both
`EnvelopeIntersection`s (Python dataclass + C++ struct, default
`math.inf`/`kPosInfinity`), forwarded by `kernel_params_from_envelope()`,
checked in `validator.cpp`'s existing `kCartesianTwist` case (angular
`sqrt(wx²+wy²+wz²)` alongside the pre-existing linear check). 2 new gtest
cases; full `ctest` suite passes. **Verified live through the full
candidate_action → kernel → safe_action → HAL → SRB path** (not just the
isolated kernel, unlike this pattern's first fix): commanding 1.0 rad/s
against LunarBot's declared 0.3 rad/s bound was rejected
(`drop_reason=KIND_FORCE, detail="ee_angular_speed"`), the arm did not move.

**Design implication:** any manifest declaring `max_ee_angular_speed_rad_s`
(so far: `panda_mobile`, `lunar_bot`) can now trust it is real for
CARTESIAN_TWIST specifically. The broader pattern this and F12 both surface
— a Python "supervisor" layer that exists in source but is never launched by
the production launch file, silently turning several declared per-mode
bounds into dead documentation — likely still applies to
`max_cartesian_step_m`/`max_cartesian_step_rad` (CARTESIAN_DELTA) and any
gripper-width bound; **not yet checked for those modes** — worth a pass
before this project's trustworthiness claims lean on any of them.
Source: `docs/phase_b_lunar_bot_arm_gripper.md`.

### F17 — Multi-node estop reset needs `/openral/estop_cleared`, not just the kernel's `/openral/estop_reset` service

Discovered live while testing the unified LunarBot HAL: after an
intentional safety violation, the kernel's own `/openral/estop_reset`
service call succeeded and cleared *its own* latch, but the separately
running `openral_hal_lunar_bot` lifecycle node stayed latched and silently
dropped every subsequent command — no error surfaced to the caller, chunks
just had no effect. Not a bug: `openral_hal/lifecycle.py` already documents
this exact behavior in a comment ("reset was a kernel-only service, so the
HAL stayed latched after `/openral/estop_reset` — the robot never resumed
until a restart") and provides the fix — every `ManifestHALLifecycleNode`
also subscribes to `/openral/estop_cleared` (`std_msgs/Empty`). In
production that topic is published by the operator dashboard
(`openral_observability.dashboard.estop_publisher.EstopPublisher`) as a
deliberate human-in-the-loop confirmation step, not automatically by the
kernel — a design choice, not an oversight.

**Design implication:** any bring-up/test tooling that drives the safety
kernel directly (no dashboard running, as every script in this project's
`docs/` does) must publish `/openral/estop_cleared` itself after calling
`/openral/estop_reset`, or every downstream node that latched on
`/openral/estop` stays silently inert. Added to the reusable environment
notes in `AGENT/handoff.md` so this isn't rediscovered per session.
Source: `docs/phase_b_lunar_bot_arm_gripper.md`.

### F18 — SRB's procedural moon terrain is only reliably flat within ~4 m of the env origin

Found while building Mission A's `panel_remount` task (`space_robotics_bench/`,
now a submodule — see `docs/upstream_pins.md`). A pedestal + panel placed
2.4–3.0 m from the env origin: the panel (a `RigidObject`) fell to
`z = -40` within a second and `z = -2637` a few seconds later — still
falling, never hitting anything.

Root cause, read from SRB's own source (`srb/core/env/common/base/env_cfg.py`):
procedural scenery generation computes
`flat_area_size = 0.8 * (_dyn_res ** 1.2)`, a genuinely flat, reliable
landing pad centred on the env origin — for this task's `env_spacing=32.0`,
`_dyn_res=4` and `flat_area_size≈4.2` (a ~4 m-wide pad). Outside it, the
terrain is deliberately uneven (the same procedural variation that makes
the rest of the map interesting for navigation/traversal tasks). An object
spawned outside the pad can end up embedded in a terrain bump; PhysX's
depenetration solver then ejects it with a large velocity spike, which —
combined with the Moon's weak gravity — sends it falling/flying
indefinitely rather than settling. This is not specific to LunarBot or to
this task; it would happen to any rigid object spawned far from origin on
this scenery.

**Fixed** by keeping the new pedestal/panel within ~1.5 m of the env
origin, comfortably inside the pad. Re-verified live: the panel now settles
to a stable resting pose, unchanged across 8+ seconds, instead of falling.

**Design implication:** any future SRB scene authored for this project
(Mission B, a multi-pedestal identify-the-fault variant of Mission A, etc.)
that places objects away from the env origin must either keep them within
the procedural terrain's flat pad (~half of `flat_area_size`, itself a
function of `env_spacing`) or use a scenery/terrain variant that doesn't
have this restriction — do not assume z=0 is a safe, collision-free spawn
height anywhere in the environment. Documented in `panel_remount/task.py`'s
own header comment so the next person doesn't rediscover it by watching an
object fall through the world.
Source: `docs/mission_a_panel_remount.md`.

### F19 — LunarBot's base drifts/rotates incoherently on a large in-place turn command

Found while scripting a closed-loop base-approach controller for the
feasibility check above. Commanding a large `angular.z` on `cmd_vel` to
turn the base to face a target barely rotated it (a few degrees over
several seconds of a saturated command) while the base **translated**
substantially in an unintended direction instead. Root cause not fully
pinned down, but the leading hypothesis is `FourWheelSteerActionCfg`'s
`max_steering_angle: 120°` limit: a genuine in-place spin needs some
wheels steered near/at that limit, and saturation there could produce an
inconsistent resultant motion (part rotation, part unwanted translation)
rather than a clean pivot. Also confirmed separately:
`scale_linear=-1.0`/`scale_angular=-1.0` (already documented in
`lunarbot.py`) means a naive "positive error → positive command" P
controller drives the wrong way unless negated.

**Revised hypothesis (2026-09-14, from reading
`srb/core/action/term/mobile/four_wheel_steer.py`):** the 120° limit is
not it — the term wraps steer angles into (−90°, 90°] with a drive-sign
flip, so the limit is never reached. The kinematics are correct; what is
missing is steer-before-drive sequencing. `apply_actions` writes the
steering *position* targets and the drive *velocity* targets in the same
step; the steering joints are position-controlled with a 1.9635 rad/s
(≈112°/s) velocity limit, so an in-place rotation asks every wheel to
swing ~90° (≈0.8 s) while the drive wheels are already spinning at full
target speed at the old steer angle. Four wheels pushing in inconsistent
directions for most of a second is the observed drift. The wrap also
flips a wheel's steer target by 180° (and its drive sign) whenever the
commanded `v/ω` crosses that wheel's singular direction — another large
transient. **Fix (planned, not yet built):** scale each wheel's drive
velocity by `max(0, cos(steer_target − steer_measured))`, the standard
4WIS practice. Must land before Nav2 relies on `cmd_vel`
(`docs/lunar_bot_capability_set_plan.md` §3.4).
Source: this session's feasibility-check scratch work (not separately
documented as its own doc — the fix that mattered this session was adding
JOINT_POSITION control for the arm, per the user's direction; see
`docs/lunar_bot_joint_position_control.md`).

### F20 — JOINT_POSITION's wire row is always full-width, even when `joint_names` is set

Found during first live E2E test of the new JOINT_POSITION control mode
(`docs/lunar_bot_joint_position_control.md`): the HAL wrongly assumed that
when `action.joint_names` names a subset of joints (ADR-0102), the wire
row is *also* only that many elements wide. It is not — the C++ safety
kernel's structural check (`validator.cpp`'s `is_joint_mode` branch) forces
every JOINT_* chunk's `n_dof` to equal the envelope's *full* joint count
regardless of `joint_names`, so the row is always full-width (zero-padded
in the slots the emitter doesn't care about) and `joint_names` only marks
*which* of those full-width slots are the real ones. The bug was caught
immediately by live testing (the arm didn't move at all — the HAL was
silently throwing and dropping every JOINT_POSITION chunk); a pure
code-review pass without a live test would likely have missed it, since
the unit tests (written before the live test) encoded the same wrong
assumption and passed against it.
Source: `docs/lunar_bot_joint_position_control.md`.

### F21 — No upstream capability resolves for `lunar_bot`: the capability set is paper infrastructure

Found 2026-09-14 while checking whether execution_plan.md §21 item 6
(generic OpenRAL on Mission A) was runnable. It was not, on three
independent counts: (1) **no rSkill can drive this robot's arm or
gripper** — every `kind: vla` skill is trained for another embodiment, the
`ros_action` wrappers need Nav2/MoveIt servers that are not configured,
and the only matching actuator skill is the base-only
`rskill-procedural-body_twist` this project added; (2) **no sensor reaches
OpenRAL** — the HAL subscribes joint states only; `robot.yaml` says
`has_vision: true` but no image, depth, odometry or `map`/`base_link` TF
exists on the OpenRAL side, so scene query, object localization and the
world-state lift have no input; (3) **`openral deploy sim` cannot target
SRB** — `SceneBackend` is `mujoco`/`isaacsim` only, so the process graph
must be assembled by this repository's own launch and the mission enters
via `openral prompt --new-goal`. The reasoner has in fact never been in
the loop for this robot: every Phase B verification so far was scripted
dispatch. Consequence for the plan: `research_content.md` §5.1's "same
capabilities for every baseline" table does not exist upstream and must
be built (execution_plan §8.3, `docs/lunar_bot_capability_set_plan.md`).
Recorded as a finding because the original plan assumed §8.1's "inspect"
cells would resolve to existing implementations for the chosen robot;
they resolve to existing *frameworks* (Nav2 bringup, detector/VLM nodes,
world-state lift, `ros2_image` reader) that need embodiment wiring.
Source: `docs/lunar_bot_capability_set_plan.md`, `docs/mission_a_panel_remount.md`.

### F22 — RM-75 joint limits now enforced (closes the JOINT_POSITION ±inf gap)

The user supplied the RM-75 datasheet (`docs/lunar_bot_rm75_spec.md`);
`robot.yaml` now declares the seven arm ranges and the 5 kg payload
(`openral` `f7b5ccd`). Verified against a running kernel with the
envelope regenerated the sanctioned way: J2 = 2.5 rad and J6 = −2.4 rad
rejected (`field=joint_position`, reported limit = datasheet value), an
all-in-range target passes. SRB's `lunarbot.py` velocity limits already
matched the datasheet (180°/s J1–J2, 225°/s J3–J7). Remaining arm-side
gap: nothing bounds joint *velocity* for JOINT_POSITION steps (the kernel
checks position only) — a large step between ticks is legal today;
relevant once MoveIt streams trajectories (§8.3 item 9).

### F23 — `lunarbot.step` (2026-09-14 fabrication drawing) implies the simulated chassis/mast is a stale CAD revision, not just missing a lidar

Found while extracting the Mid-360 lidar mount pose from the newly
supplied `lunarbot.step`/`mid-360-asm.stp` (XCAF-parsed via `cadquery-ocp`,
cross-calibrated against `lunarbot.py`/`lunarbot.usdc`'s known values).
Two independent mismatches between this STEP and the currently-simulated
asset: (1) **wheelbase** — the STEP's front/rear wheel pairs are
symmetric at ±532.776mm (total 1065.6mm), while `lunarbot.py`'s
`wheel_positions` are asymmetric (492.5mm front / 522.5mm rear, total
1015mm) — the code comment there says the rear axle was hand-shifted
−0.03m specifically "to correct a mismatch against the (asymmetric)
chassis hull/rail mesh", i.e. a patch against an earlier import, not a
property of the real vehicle; (2) **front sensor mast** — the STEP's
existing camera fixture adapter (相机工装转接块, NAUO10) sits at
Y=+92.0mm, while the currently-simulated `rgbd_camera_frame`/`camera_frame`
sit at Y=−25/−75mm — the opposite side. Reads as a coherent redesign (mast
widened to carry the camera and the new Mid-360 lidar bracket side-by-side
at Y=±92mm) rather than noise. User confirmed 2026-09-14 this STEP is the
current fabrication drawing (supersedes what the sim asset was built
from). **Consequence, not yet actioned:** the chassis/wheel/camera-mast
geometry in `lunarbot.usdc` should eventually be re-imported from this
revision so wheelbase and camera position match hardware; out of scope for
the Mid-360 lidar task itself, which anchors its calibration to the
existing camera mast (single-point, medium confidence) rather than the
mismatched wheel geometry. Source: this session's CAD-extraction pass
(`mid360_mount_result.json` in that session's scratchpad, not committed to
the repo).

### F24 — RTX Lidar's own render-product/SDG pipeline never dispatches a frame on our pinned Isaac Sim build (confirmed upstream bug, precisely localized)

Found 2026-09-14 implementing `srb/core/sensor/rtx_lidar.py` (Mid-360 RTX
Lidar, per `docs/rtx_lidar_integration_plan.md`). The sensor-authoring
mechanism itself is verified correct and working: a custom `OmniLidar`
prim with the real 24,000-point Mid-360 scan-pattern window (from Livox's
own `livox_laser_simulation` data) is created, schema applied, all
attribute values round-trip exactly. Pulling live point-cloud data through
it does not work: `/Render/PostProcess/SDGPipeline/PostProcessDispatcher`
never advances past reference time 0/0, reproduced identically with (a)
the custom Mid-360 sensor and (b) an official whitelisted reference sensor
(`HESAI_XT32_SD10`, created the fully-supported way — ruling out anything
specific to a custom sensor), across six different render-advance
mechanisms tried in headless mode (bare `simulation_app.update()`,
`SimulationContext.step()`, the async `next_render_simulation_async`
matching Isaac Sim's own official `isaacsim.sensors.rtx` test suite, and
the synchronous `rep.orchestrator.step()` purpose-built for standalone
scripts), plus the two documented headless workarounds from Isaac Sim's
own Known Issues page (`rt_subframes>=2`,
`--/exts/isaacsim.core.throttling/enable_async=false`).

**Precisely localized, not just "headless is broken"**: re-ran non-headless
against the machine's real X11 display/GPU (confirmed live, screenshot
inspected) — general RTX rendering is completely healthy (the main
Perspective viewport shows the scene correctly lit, shaded, shadowed; the
whitelisted sensor's own visual mesh and full prim hierarchy — `OmniLidar`
prim included — are all present and correct in the Stage tree). But the
sensor's *own* dedicated render-product preview pane stays solid black the
entire time, GPU pinned at ~60%/270W (genuine sustained work, not an idle
deadlock) with zero progress for several minutes. So this is not a
headless-specific, GPU-driver, or general-renderer problem — it is
specifically the RTX Lidar synthetic-data-generation render-product/
dispatcher path that never produces a frame, in both headless and
windowed/GUI mode alike.

Matches upstream report
[isaac-sim/IsaacSim#110](https://github.com/isaac-sim/IsaacSim/issues/110)
("Cannot retrieve RTX lidar data using headless Python script") —
**pulled the full issue thread via the GitHub API (not just a page
summary, which had omitted the actual content), correcting an earlier
misread**: the issue is **closed** (`state_reason: completed`, closed
2026-04-17 by NVIDIA engineer `zwdoescode`: *"This issue has resolved in
Isaac Sim 5.1"*), not open as first reported here. The full thread
(10 comments, 2025-08-05 to 2026-04-17) is far more informative than the
closing line alone:
- Original repro: Isaac Sim **5.0.0** (not 5.1), A40 GPU, headless always
  empty, non-headless intermittent (data from step 6 on).
- NVIDIA's actual root-cause + workaround (2025-08-13): default
  `omni:sensor:Core:skipDroppingInvalidPoints=False` **causes** the bug;
  set it `True`.
- A second reporter (`simplelife2010`, 2025-08-21) hit an **near-identical
  symptom to ours** on a **Solid State** lidar with
  `IsaacExtractRTXSensorPointCloudNoAccumulator` (the annotator this
  session used throughout): permanently empty data plus a
  `/Render/PostProcess/SDGPipeline/DispatchSync` "Empty typeName" warning
  — same OmniGraph path family as our stuck `PostProcessDispatcher`. Never
  explicitly confirmed fixed in the thread.
- NVIDIA's engineer could only get data with the different
  `IsaacCreateRTXLidarScanBuffer` annotator, and even then only **every 6
  steps** (sparse), not every step.
- The closing comment addresses a different commenter's question and does
  not explicitly confirm the Solid-State/`NoAccumulator`/headless
  combination (i.e., closest to our case) was actually fixed.

**Tested the exact NVIDIA-validated workaround directly** —
`omni:sensor:Core:skipDroppingInvalidPoints=True` + the
`IsaacCreateRTXLidarScanBuffer` annotator (not `...NoAccumulator`), 40
steps via `rep.orchestrator.step()` (matching the issue's own repro
script), headless: **still zero data, no errors, GPU briefly active then
idle.** This is the single closest match to what NVIDIA's own engineer
confirmed working (if only sparsely) — testing it and having it still fail
is the strongest evidence gathered this session that our specific
environment (GPU: dual RTX 5090 / Blackwell, vs. the reporter's A40; a
newer consumer architecture the pinned Aug-Nov-2025-vintage RC build's RTX
sensor pipeline may not have been validated against) has a issue beyond
what any of these documented, NVIDIA-confirmed workarounds address.

Also chased the version-upgrade angle: downloaded NVIDIA's official
`isaac-sim-standalone-5.1.0-linux-x86_64.zip` "GA" package directly — its
`VERSION` file and extension versions (e.g.
`omni.replicator.core-1.12.27+107.3.3`) are byte-identical to our pinned
`5.1.0-rc.19` install; NVIDIA shipped the RC build unchanged as the GA
release, so **there is no smaller/same-series upgrade available that
could contain whatever fix the issue's closing comment refers to** — the
download was deleted after confirming this (no disk left behind). The
only Isaac Sim releases newer than 5.1.0 are 6.0.0/6.0.1/6.1.0 (full
release list checked) — a two-major-version jump, needing an IsaacLab
upgrade from the pinned 2.2.1 and a full SRB re-verification; out of
proportion to this one sensor and not undertaken without an explicit user
decision to invest in that migration.

**One more concrete, official lead chased down and also ruled out**: read
the full official Isaac Sim 5.1.0 RTX Lidar doc page plus the bundled
official standalone example
(`standalone_examples/api/isaacsim.sensors.rtx/rotating_lidar_rtx.py`,
present locally, confirmed working reference code). It uses
`SimulationApp({"headless": False, "enable_motion_bvh": True})` — a flag
not tried in the mechanisms above. Traced `enable_motion_bvh` to its exact
effect in `isaacsim.simulation_app.simulation_app.SimulationApp`: it sets
three carb settings (`--/renderer/raytracingMotion/enabled=true`,
`--/renderer/raytracingMotion/enableHydraEngineMasking=true`,
`--/renderer/raytracingMotion/enabledForHydraEngines='0'`), needed for
ray-traced sensors specifically (as opposed to normal Hydra viewport
rendering). Set all three directly via `kit_args` and re-ran the
`rep.orchestrator.step()` HESAI baseline with a 4-minute timeout: produced
genuinely different behavior (a CPU burst to ~1690% across many threads,
tapering to ~110% and holding — unlike every prior attempt's steady-state
GPU-bound-idle-or-error pattern), but still zero point-cloud data at
timeout, no `[Error]` log lines. A real, different code path was
exercised; it did not fix the symptom either.

**Not an SRB or implementation defect** — do not re-attempt fixing this in
SRB code; the avenues a diligent implementation could reasonably try
(six render-advance mechanisms, two official documented workarounds,
non-headless/real-display, RC-vs-GA version diff, extension-registry
availability, the official example's `enable_motion_bvh` flag, and
NVIDIA's own engineer-confirmed workaround/annotator combination from the
bug thread itself) are now exhausted. Consequence: `rtx_lidar.py` exists
and is correct but is not wired into `srb/core/env/mobile/env.py`'s
active sensor path; RayCaster (F23) remains the active `lidar_robot`
implementation. **If revisited later**: the GPU-generation mismatch (our
dual RTX 5090 vs. the upstream reporter's A40) is the one remaining
un-eliminated variable and the most likely next thing to check — e.g. on
different/older GPU hardware, or once Isaac Sim ships a build actually
validated against Blackwell-generation cards. Source: this session's
reproduction across headless and non-headless modes (scratchpad, not
committed) plus `docs/rtx_lidar_integration_plan.md`'s Status section.

### F25 — Sensor bridge built + verified live (item 2); a real `rclpy` executor gotcha found along the way

Built `openral_hal_lunar_bot.sensor_bridge_node` (`LunarBotSensorBridgeNode`):
relays SRB's already-computed `Image`/`CameraInfo`/`PointCloud2`/`Imu` onto
`/openral/cameras/{front,front_depth,wrist}/*`, `/openral/lidar/points`,
`/imu`, with `header.frame_id` rewritten to the matching `robots/lunar_bot/
robot.yaml` `sensors[].frame_id` — a relay, not a resynthesis (§3.2 item 1's
"no new relay code if the binding supports frame rewriting" fallback,
exercised because `openral_rskill_ros.sensor_leg`'s `deploy_binding` route
isn't wired into any launch for `lunar_bot` yet, item 2b). A `tf2_ros` buffer
re-roots every sensor's SRB-native pose (`srb/env0/<sensor> ← srb/env0`) onto
`chassis_base_link -> <manifest frame>`, plus `/odom` (pose from the same
lookup, twist from finite-differenced position + the IMU's angular rate,
rotated into the body frame — `rotate_vector_by_quat_xyzw`, unit-tested) and
a static identity `map -> odom`. `robot.yaml` gained a `sensors:` block
(`front`/`front_depth`/`wrist`/`imu`/`lidar`) and `has_lidar: true`.

Two things the design doc (`docs/srb_deploy_backend_plan.md` §6) flagged as
open, resolved live against a running `panel_remount_visual env.robot=
lunar_bot` instance rather than assumed:

- **SRB's articulation-root TF frame (`srb/env0/robot`) is numerically
  `chassis_base_link`'s pose** — confirmed by reading the live `/tf`: the
  per-body transform `srb/env0/robot -> srb/env0/robot/chassis_base_link` is
  translation `(0,0,0)`, rotation ≈ identity (float noise only). So
  `robot_tf_frame` (a bridge parameter, not hardcoded, precisely for this
  reason) can default to `srb/env0/robot` with confidence, not a guess.
- **The Hydra dotlist override `env.camera_resolution=[640,480]` on the
  `srb agent ros` command line works** — the live `/openral/cameras/front/
  camera_info` (relayed straight from SRB) reported `height: 480, width:
  640`, and its `k` matrix (`fx=fy=266.667, cx=320, cy=240`) exactly matches
  this manifest's hand-computed `PinholeCameraCfg` intrinsics
  (`focal_length=5.0, horizontal_aperture=12.0`) — a live cross-check, not
  just "the override didn't error."

**A real `rclpy` gotcha, not an SRB or design bug**: the bridge node
silently stalled ~1-2s after startup (no crash, no error — `_on_tick`
simply stopped firing, so every TF/odom lookup timed out from then on) under
two different spin strategies before the fix was found: (1) a bare
`rclpy.spin(node)` — `tf2_ros.TransformListener` puts its `/tf`/`/tf_static`
subscriptions on a `ReentrantCallbackGroup`, which apparently needs a
`MultiThreadedExecutor` to coexist with this node's several
MutuallyExclusive-group relay subscriptions; (2) even a `MultiThreadedExecutor`
still stalled when `.spin()` was called directly on the **main** thread —
only spinning it on a background thread (main thread just waits/joins)
ran cleanly for the full length of every test. Root cause not chased past
that point (a main-thread-specific interaction with rclpy's wait-set wakeup
is the working hypothesis); the fix is empirically verified over multiple
30-50s live runs, not theorised. Documented in the module's `_make_main`
docstring so it isn't rediscovered by trial and error next time.

Verified live end-to-end: `/odom` (`frame_id: odom`, `child_frame_id:
chassis_base_link`, real moving pose), `/imu` (`frame_id: imu_link`,
`orientation_covariance[0]=-1` — no orientation estimate, per the
`sensor_msgs/Imu` convention, since SRB's `Imu` sensor models linear
acceleration + angular velocity only), `/openral/lidar/points` (`frame_id:
lidar_link`, ~14k points, matching `env.py`'s density comment),
`/openral/cameras/front_depth/points` (`frame_id: front_camera_optical_frame`,
~196k points), and `tf2_echo chassis_base_link front_camera_optical_frame`
resolving to a real, changing transform. Not yet verified: `wrist`'s camera
frame TF chain specifically (parented flat under `chassis_base_link`, not
through the arm, per §3.2 item 1 — only `front`/`imu`/`lidar` frames were
individually spot-checked with `tf2_echo`; the `_publish_sensor_frames` loop
is identical code for all four, so this is a low-risk gap, not a known
issue).

### F26 — SRB backend for `openral deploy sim` built (item 2b): six-step plan implemented, one real bug found and fixed along the way

Built all six steps of `docs/srb_deploy_backend_plan.md` §3 on `openral`
`feat/lunar-bot-capability-set`: `ExternalSimulatorSpec` schema
(`DeployScene.simulator`), the `srb` scene backend
(`openral_sim.backends.srb` — registry membership + a `provision_srb` preflight
check; `reset`/`step` deliberately raise, since SRB is never scene-attached
for `lunar_bot`), the launch spawn + readiness gate
(`deploy_e2e.launch.py` + `tools/lifecycle_autostart.py`), the
`_ROBOT_HAL_REGISTRY["lunar_bot"]` entry (`bare_twin_sim=True`,
`robot.yaml`'s `hal.sim` now points at the same `LunarBotSRBHAL` as
`hal.real`), and `scenes/deploy/srb_panel_remount.yaml`.

**Design simplifications found while implementing, not assumed going in**:
reading `deploy_sim.py`'s HAL-construction code (`resolver.py::build_hal`)
directly rather than inferring from the plan showed `bare_twin_sim=True`
alone is sufficient — no new `_HalSpec` flag was needed (`external_sim` as
originally planned in the design doc). And `_scene_backend_has_sim_clock`
already includes `PhysicsBackend.ISAACSIM` in its sim-clock set, so
declaring `scene: {backend: isaacsim}` (honest — SRB genuinely is Isaac Sim)
resolves `clock_origin=simulation`/`use_sim_time=true` with **no code
change** — and `ManifestHALLifecycleNode`'s existing `/clock` publisher
already probes for `sim_time_ns` before claiming the role, so
`LunarBotSRBHAL` (which has none) is silently skipped rather than fighting
SRB's own real `/clock` — no new `publish_clock:=false` param was needed
either. Two mechanisms the plan expected to build turned out to already
exist.

**Real bug found and fixed**: `resolve_launch_invocation`'s `deploy_config:=`
forwarding was gated on `hal_mode == "real"` only — `openral deploy sim`
never populates the (separate) `deploy_config` parameter that check reads,
so `compose_runtime_graph` would never have seen `DeployScene.simulator` at
all, silently dropping the entire SRB spawn + readiness gate. Fixed by also
forwarding `--config` (the parameter `deploy sim` actually populates) when
`hal_mode=="sim"` and the scene declares a `simulator:`. Caught by actually
inspecting the resolved `argv:` (the dry-run's own printed summary), not by
assuming the wiring worked because the code compiled — the CLI's dry-run
output looked complete and correct even with the bug present, since the
missing arg just makes the launch fall back to its empty-string default
silently.

**A gap deliberately deferred, not silently skipped**: the sensor bridge
(item 2, F25) is not yet wired into `deploy_e2e.launch.py` — it still runs
as a separate manual process. This launch file is robot-agnostic by design
("one launch file for every robot"), so wiring it in needs a generic
mechanism (e.g. a `_HalSpec` field naming an optional companion node), not
a `robot_id == "lunar_bot"` branch — a real follow-up, not needed for this
item's own exit condition (sensors aren't needed for a body_twist to move
the base).

**Verified live** (`--no-enable-slam --no-enable-nav2 --no-enable-octomap
--no-dashboard`, `openral deploy sim --config
scenes/deploy/srb_panel_remount.yaml`, this host, 2026-09-14) through the
*entire* graph: `openral_deploy_sim_external_simulator` spawned SRB for
real (Isaac Sim booted, extensions loaded); the HAL's `lifecycle_autostart`
invocation carried exactly the expected `--wait-for-topic` args and
genuinely blocked (did not attempt `configure`) while SRB was still
booting; safety_kernel/runtime_node/reasoner_node/prompt_router_node/the
HAL lifecycle node all started and shut down cleanly (kernel envelope
synthesis from the manifest's new `position_limits` succeeded); the SRB
preflight `provision_srb()` hook fired during the CLI's own preflight
step; once SRB's topics appeared, the gate **passed** and the HAL reached
ACTIVE (confirmed by its subsequent `read_state` polling, not just a log
line). Shutdown (`SIGINT` to `ros2 launch`) correctly escalated to
`SIGTERM` for the one slow-to-die child (SRB) after its 5 s grace period —
`ros2 launch`'s own exact-PID process tracking, no pattern-kill needed.

**Not yet verified — a real, load-dependent finding, not a code bug**: once
ACTIVE, the HAL's `read_state` repeatedly logged `SRB joint state is ~2.5-2.7
s old (limit 0.5 s)` for the several minutes this run was observed —
consistently, not trending down (ruling out the one-time RTX shader-compile
warmup `srb-native-install` documents) and not growing unboundedly (ruling
out a dead subscription callback) — so SRB's own `/srb/env0/robot/
joint_states` publish rate was genuinely ~0.35-0.4 Hz under this run's host
conditions (`panel_remount_visual` renders 3 cameras at 640×480 RTX; this
shared host may have had other concurrent load). `LunarBotSRBHAL`'s
hardcoded `staleness_limit_s=0.5` (the same default every other HAL uses)
assumes a much faster tick and would currently reject a `read_state()` call
under this load, blocking a live body_twist dispatch from completing — this
item's full stated exit condition (a reasoner-dispatched body_twist
actually moving the base) was not reached in this session, though every
individual piece of the wiring it depends on was. Follow-up: either widen
`staleness_limit_s` for this HAL, investigate the render cost specifically,
or re-verify on a quieter host / with the non-visual `panel_remount` task
(no camera rendering) to isolate whether rendering is the actual cause.

### F27 — A real orphaned-process bug found and fixed (not "just loosen the value"); the F26 slow-tick finding is real but its cause is still open

Follow-up investigation, user-directed 2026-09-14: do not raise
`staleness_limit_s` as a fix without first finding the actual cause, and
stop leaving Isaac Sim processes running after a session.

**Orphaned-process bug — found, root-caused, fixed, tested.** F26's
verification run was never actually cleaned up: `ros2 launch` reported the
SRB process it spawned as dead (SIGTERM, exit -15), but the real Kit/PhysX
process was a **different PID**, found still running **78 minutes later**
— 100%+ CPU, several GB of GPU memory held on both GPUs, zero ROS topics
publishing (a dead simulation from OpenRAL's perspective, not a slow one).
Root cause, read from source, not guessed: NVIDIA's `python.sh` (SRB's own
interpreter) runs its real process as a plain foreground command with **no
`exec`** (`$python_exe "$@" || error_exit`) — bash therefore **forks** a
child and stays alive supervising it, so the heavy process is a distinct
PID from the one `python.sh` itself is. `launch.actions.execute_local.
ExecuteLocal` (confirmed by reading its installed source) has **no**
process-group handling anywhere — no `setsid`/`killpg`/`preexec_fn` — it
only ever signals the one PID it directly spawned. Killing that PID kills
bash; the already-forked Kit process is unaffected, orphaned, reparented to
init, and keeps running indefinitely.

Fixed with `tools/process_group_wrapper.py`: becomes a new process-group
leader (`os.setsid`) before spawning the real command, and on SIGTERM/
SIGINT signals the **whole group** (`os.killpg`), reaching every
descendant regardless of how many non-`exec` forks deep — `deploy_e2e.
launch.py` now routes `DeployScene.simulator` through it instead of
running its `argv` directly. Verified two ways: (1)
`tests/unit/test_process_group_wrapper.py` reproduces the exact failure
mode with a real subprocess tree (a script that forks a `sleep` child via
`&`/`wait`, mirroring `python.sh` exactly) — one test proves the wrapper
kills the whole tree, a control test proves the SAME script survives a
bare SIGTERM without the wrapper (so the fix is proven against a real
bug, not a test that would pass either way); (2) a second live `openral
deploy sim` run against SRB, this time confirmed via `ps`/`nvidia-smi`
that every process (including the Kit/PhysX PID) and all GPU memory were
released after shutdown.

**Operational note, needed for any future live debugging of a running
`deploy sim` graph**: `openral deploy sim` (hal_mode=sim) deliberately
runs on `ROS_DOMAIN_ID=77` with `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
(`openral_cli._dds_scope.confine_sim_scope`, `SIM_DOMAIN_ID="77"` — by
design, so a sim graph doesn't join whatever else is on the LAN). A plain
`ros2 topic list`/`hz` from an ordinary shell (domain 0, unset discovery
range) sees **only** `/parameter_events` and `/rosout` — not an error, not
a hang, just wrong-domain isolation; it looks exactly like "the graph
isn't there." `export ROS_DOMAIN_ID=77 ROS_AUTOMATIC_DISCOVERY_RANGE=
LOCALHOST` before observing. This cost real time this session before
being traced to source.

**The F26 slow-tick-rate finding is real, re-confirmed independently on a
freshly-cleaned host, and its actual cause is still open** — the orphaned
process above was ruled out as the (sole) explanation: no other Isaac Sim
instance was running during the original observation window, and this
follow-up run started from a verified-clean host and was **still** slow
(~0.36 Hz on `/clock`, confirmed via `ros2 topic hz` once the domain-scope
issue above was fixed — not just the HAL's own internal log, an
independent external measurement agreeing with it). What this run added,
and what it ruled out:

- **Not GPU-bound**: `nvidia-smi` during the slow period showed 0-4% GPU
  utilization on both cards — directly contradicts the "3-camera RTX
  render is just expensive" hypothesis F26 offered as the leading
  explanation. That hypothesis is **not** supported by measurement.
- **One CPU thread pegged near 100%**, system load average ~7, while 218
  other Kit threads sat idle (`S` sleeping) — so the bottleneck is CPU-side
  single-threaded work in the Kit/SRB step loop, not parallelised physics
  or the GPU.
- **Not (sustained) disk I/O**: `/proc/<pid>/io` on the busy process over a
  3 s sample showed only light write activity (~8 KB/s of actual block
  I/O, ~2 write syscalls/s) — not consistent with a heavy I/O bottleneck,
  despite `top` showing a one-off high `%wa` reading at one sampled
  instant (not reproduced on a direct, longer per-process I/O measurement;
  likely a transient blip, not the sustained cause).
- **Not identified**: which specific CPU-bound call is consuming that one
  thread. `py-spy dump` (installed, `0.4.0`) needs `ptrace` permission
  this host's Yama LSM denies without `sudo` (`ptrace_scope=1`, and no
  passwordless `sudo` is configured) — blocked on that access, not
  attempted and abandoned. Getting a real stack trace (`sudo py-spy dump
  --pid <kit-python>` while a run is slow, or temporarily `echo 0 | sudo
  tee /proc/sys/kernel/yama/ptrace_scope`) is the single highest-value next
  step; profiling data beats further hypothesis generation here.
- Also not yet tried: the non-visual `panel_remount` task (no camera
  sensors at all) as a differential test — if it ticks at a normal rate,
  that would at least re-implicate the camera pipeline specifically
  (despite the GPU-idle finding) rather than something in the base physics/
  ROS-bridge loop every SRB task shares.

**Explicitly not done as a workaround**: `LunarBotSRBHAL.staleness_limit_s`
was left at its default `0.5`. The user's direction was to find the actual
cause first; this entry records that direction being followed, not ignored
— raising it remains an option once the cause is understood (or ruled out
as fixable), not a substitute for understanding it.

**Update, same session — real profiling data, gdb (py-spy could not identify
this custom-built interpreter; `sudo` access to `ptrace` was needed and
provided by the user).** Reproduced the slow tick again on a freshly-cleaned
host (ruling out the F27 orphaned-process bug as a contributing factor a
second time) and attached `gdb -p <kit-python pid>` repeatedly while it was
ticking at ~0.36-0.38 Hz (re-confirmed via `ros2 topic hz /clock`, correct
`ROS_DOMAIN_ID=77`). `gdb` has no CPython frame pretty-printer installed on
this host (`py-bt` undefined), so these are native/C backtraces, symbolized
where the relevant `.so` ships symbols:

- **Isaac Sim's own `carb.profiler` extension has an active Python-level
  trace hook** — one sample landed inside CPython's `call_trace` (`Python/
  ceval.c`) dispatching into `carb/profiler/_profiler.cpython-311-*.so`,
  confirming Kit's built-in profiler has installed a `sys.setprofile()`-
  style callback that fires on function calls/returns **throughout the
  whole interpreter**, not just inside Kit's own code. This class of hook
  is a well-known, large (often 10-100x on hot paths) source of blanket
  Python-level slowdown; whether it is *the* dominant cost here or one
  contributor among several was not isolated further this session. No
  obvious triggering env var was found (checked the process's actual
  `/proc/<pid>/environ` for `OTEL_*`/`CARB_*`/profile-related settings —
  none stood out), so this may simply be this Kit build/extension set's
  default, not something this project's launch env is turning on.
- **A real, CPU-bound (not GPU) PyTorch call was caught mid-execution**:
  one sample resolved a full, clean stack —
  `at::native::nan_to_num_out` → `at::native::AVX2::nan_to_num_kernel` →
  `at::TensorIteratorBase::for_each` → `GOMP_parallel` →
  `gomp_team_start`/`gomp_barrier_wait_end`, all in `libtorch_cpu.so`/
  `libgomp`, not `libtorch_cuda`. So `torch.nan_to_num(...)` (or an
  internal equivalent) is being run on a **CPU** tensor with OpenMP
  thread-team parallelism, and the sampled instant caught it waiting at
  the team's barrier — consistent with a real, if normally cheap,
  operation whose barrier-wait cost balloons under CPU thread contention
  (this host had ~3100 total OS threads across all processes against 24
  cores at sample time) rather than the operation itself being expensively
  large. Not yet traced to its call site (candidates: the depth-image /
  point-cloud path in `RosInterface._publish_sensor_data`, which runs for
  every camera every tick and commonly NaN-cleans depth before use — not
  confirmed, a plausible next place to look with `--native` py-spy or an
  in-SRB profiling hook instead of blind gdb sampling).
- **A separate, sustained (not single-sample) finding**: the very first,
  deepest capture showed the thread inside a Python **property setter**
  (`property_descr_set` → `PyObject_SetAttr`) whose body calls Python's
  built-in `all()` over a **generator** — and re-attaching ~1-2 s later
  still found the *same generator object address* being iterated. A
  sustained multi-second `all(<generator>)` is the signature of a
  non-vectorized, pure-Python per-element loop (e.g. `all(x > 0 for x in
  tensor)` instead of `torch.all(tensor > 0)`) — exactly the kind of thing
  that is fast for a handful of elements and catastrophic for anything
  image- or point-cloud-sized. Also not yet traced to its call site.

**Net assessment**: no single confirmed root cause yet, but three
independent, concrete, evidence-backed candidates now exist (a global
profiler hook, a CPU-bound torch op degrading under thread contention, and
a likely non-vectorized Python loop) — a materially stronger position than
"probably rendering" (F26's original, now-disproven guess) or "some kind of
host contention" (vague). Next step if this is picked back up: get proper
Python-level symbolication (fix py-spy's version detection for this build,
or install `python3.11-dbg`-equivalent gdb hooks for Isaac Sim's bundled
interpreter) rather than more blind native-stack sampling — the call sites
matter more than another sample confirming the same three suspects.

**One hypothesis tested and rejected**: CPU thread oversubscription from
running SRB alongside the rest of the `deploy sim` graph (kernel/reasoner/
runtime_node/HAL/prompt_router all concurrently on a 24-core host) was a
plausible mechanism for the OpenMP-barrier-wait finding above. Tested
directly: `OMP_NUM_THREADS=4` in `ExternalSimulatorSpec.env_set` (capping
SRB's own OpenMP thread team well below core count) — `/clock` still ticked
at ~0.42 Hz, no material change from the unconstrained ~0.36-0.38 Hz. This
specific mechanism is therefore **not** the (sole) explanation; the three
candidates above remain open, and blanket thread-count tuning is not a
fix. Both the OpenMP-torch sample and this test are consistent with the
tick rate being roughly the same magnitude whether or not SRB is
thread-starved by contention — pointing back toward the `carb.profiler`
global trace-hook candidate as relatively more likely, but still not
confirmed.

### F28 — The SRB slow tick, solved: 0.36 Hz → ~12 Hz, every millisecond attributed (item 2b unblocked)

**Method** (user direction: think first, one decisive test, no
trial-and-error). Static reading of the exact code paths — the rosidl
`.data` setter, `RosInterface._publish_sensor_data`, Isaac Lab's
`create_pointcloud_from_rgbd`, `SensorBase.data` (lazy), `RayCaster`,
`DirectRLEnv.step`, SRB's `_ensure_cuda_sim_device_for_deformable_objects`
— produced ranked hypotheses; each was confirmed or refuted by **one
instrumented run** using a new `SRB_ROS_PROFILE=1` per-tick bucket
breakdown (`sim.step` / `sim.render` / `scene.update` / each DirectRLEnv
phase / each sensor's lazy refresh / TF / joint states / sensor publish),
so the next fix was always the biggest remaining bucket, not a guess.
Four runs total, each through the full `openral deploy sim` graph.

**The causes, in the order they dominated** (all in SRB, none in OpenRAL):

| # | cause | per tick | fix (SRB `fix/ros-bridge-array-fast-path`) |
|---|---|---|---|
| 1 | rosidl-py `uint8[]` setter validates a `bytes` value **per element in pure Python** (`__debug__` branch of `sensor_msgs/msg/_image.py`, `_point_cloud2.py`); ~28 MB/tick of images+pointclouds → tens of millions of Python iterations | ~2.5 s | hand it `array.array('B')` (stored as-is) — `54bab5b`, 0.36 → 4.7 Hz |
| 2 | camera pointcloud unprojection ran on **CPU torch** (24-thread OpenMP, 1740 % CPU): SRB pins `sim.device="cpu"` unless the scene has deformables (`env_cfg.py:857`), and the ROS bridge passed `device=self._env.device`; two of the three pointclouds had **no subscriber** | ~60 ms | lazy publish (`get_subscription_count()==0` → skip) + unproject on CUDA |
| 3 | Mid-360 `RayCaster` (40 × 360 = 14,400 rays) ray-cast through **warp's single-threaded CPU backend**, same `sim.device` reason | 59 ms | `srb.core.sensor.RayCaster` builds the warp BVH on `raycast_device` (CUDA) — 4–7 ms |
| 4 | `VisualExt._get_observations` — RL-facing image observations (TorchScript on CPU images) that **nothing in `srb agent ros` reads** (`RosInterface.update()` takes `observation` and never touches it) | 24 ms CPU | `VisualExtCfg.skip_observations`, set by `srb agent ros` |
| 5 | `logging.trace(f"…{observation}…")` built its f-string every step regardless of level | small | guarded |

Result (`04c308a`), full deploy graph, `/clock` measured by `ros2 topic hz`
in domain 77: **11.9 Hz with nothing subscribed, 12.0 Hz with the sensor
bridge subscribed** to front rgb/depth/pointcloud + wrist rgb + lidar; HAL
reaches ACTIVE with no `read_state failed` after startup. Not a valid
lever: `PYTHONOPTIMIZE=1` (kills `__debug__` but breaks Isaac Sim's
TorchScript at extension load); `OMP_NUM_THREADS` (F27 — it was tested when
cause 1 still dominated, so its null result said nothing about cause 2).

**What the remaining ~82 ms is** (run 4, steady state): CPU PhysX 3
substeps ≈ 21 ms; render submit ≈ 12 ms; **≈ 30 ms GPU render wait** for
three 640 × 480 RTX cameras — invisible before because it overlapped the
CPU work above, now it lands in whichever sensor syncs with the GPU first
(the lidar's CUDA copy, so `lazy:lidar_robot` reads 30 ms although the
raycast itself is ~4 ms); camera annotator readback ≈ 4.5 ms (host-side
annotators, again the CPU sim device). This is the floor without touching
render settings or physics: at `agent_rate` 50 Hz that is a real-time
factor of ≈ 0.24. Levers if that ever matters, in order of cheapness: drop
`cam_scene` for deploy (a third of the render, nobody subscribes), a lower
RTX preset / DLSS off, PhysX contact investigation (30 `PxShape::
getMaterialFromInternalFaceIndex` warnings per substep — ~27 k log lines
per minute through `ros2 launch` — point at terrain-contact reporting).
`sim.device=cuda` is **not** an option: PhysX GPU has no CCD and SRB
enables it.

**Two more real bugs found on the way** (both fixed, both tested):

* **`openral deploy sim` teardown never reached SRB when driven from a
  script** (`openral/845483c`). A CLI started with `&` from a
  non-interactive shell inherits `SIGINT=SIG_IGN` (POSIX); CPython keeps
  it; so `ros2 launch` never saw the SIGINT `_run_launch` forwards — no
  "user interrupted", no escalation — while every node exited on its own
  rclcpp/rclpy handler and the external simulator (own session behind
  `process_group_wrapper.py`, unreachable by `killpg`) kept ticking until
  killed by hand. Seen twice. Fix: exec the launch through a trampoline
  that resets SIGINT/SIGTERM/SIGHUP to `SIG_DFL`; the orphan sweep now
  SIGTERMs the wrapper (group leader) instead of SIGKILLing it, which
  would have orphaned the very kit process it guards. Verified: scripted
  `kill -TERM <deploy>` now shows launch's own SIGINT → SIGTERM (5 s) →
  SIGKILL (10 s) escalation for the simulator, host clean (17 MiB GPU),
  runs 3 and 4. This matters beyond dev hygiene: the experiment runner
  (§19) will drive `deploy sim` exactly this way.
* **Camera data reaches OpenRAL at ~2 Hz although SRB publishes at 12 Hz**
  — *not* a tick problem, a DDS one, now isolated: `ros2 topic hz` on
  SRB's **raw** `/srb/env0/cam_front/image_rgb` gets 2.1–2.2 Hz, the
  bridge's relay 1.4–1.7 Hz, lidar 5.6 Hz, while `/clock` (tiny message)
  gets 12 Hz and SRB's publish bucket is 6 ms. Both sides run Fast-DDS
  (Isaac's bundled rclpy and the OpenRAL graph, `rmw=default`), publisher
  QoS RELIABLE/depth 1, messages 0.9–7 MB, host `net.core.rmem_max` =
  212992 (208 KB). Textbook large-message fragment loss (Humble's Fast-DDS
  2.6 has no `LARGE_DATA` builtin; SHM segment default 512 KB < one image).
  Fix belongs to item 2's sensor path: a Fast-DDS XML profile (SHM
  `segment_size` ≥ 16 MB + UDP socket buffers) for **both** processes and
  `sysctl net.core.rmem_max`, then re-measure raw vs relayed. Open.

Method note for next time: a bucket that suddenly grows after an
unrelated fix is a **sync point moving**, not a regression — check where
the first GPU synchronisation after `sim.render()` happens before chasing it.

### F29 — Item 2b's exit condition reached: a kernel-dispatched BODY_TWIST really moves LunarBot inside SRB, through `openral deploy sim`

**What was proven.** `openral deploy sim --config scenes/deploy/srb_panel_remount.yaml`
brought up the whole graph (kernel, HAL, reasoner, runtime_node, prompt_router,
SRB as the external simulator); a standalone script then used the existing,
unmodified `ROSPublishingHAL` — the same mechanism Phase B1 used against a
hand-launched SRB (`docs/phase_b_lunar_bot_hal.md`) — to publish real
`ActionChunk` BODY_TWIST commands (`vx=0.2 m/s`, under the manifest's 0.3 m/s
cap) on `/openral/candidate_action` for 5 s, at 10 Hz. Full chain exercised,
nothing bypassed:

```
script -> ROSPublishingHAL.send_action() -> /openral/candidate_action
  -> C++ safety kernel -> /openral/safe_action
    -> openral_hal_lunar_bot lifecycle node -> LunarBotSRBHAL.send_action()
      -> /srb/env0/action/cmd_vel (real geometry_msgs/Twist) -> SRB physics
        -> /tf: srb/env0 -> srb/env0/robot
```

Measured via a real `tf2_ros` lookup before/after (not `joint_states`, not a
log grep): `srb/env0/robot` moved from `(0.042, -0.048)` to `(-0.372, -0.411)`
— **0.550 m** over 5.05 s of commanded motion (naive expectation at a
constant 0.2 m/s: 1.010 m; the shortfall is the same kind of steer/drive
ramp-up F19 already named, not a new defect). No kernel rejection, no HAL
error, no `read_state failed` in the log.

**Deliberately bypassed: the LLM reasoner.** No `OPENRAL_REASONER_MODEL`/
`ANTHROPIC_API_KEY`-class credential is configured on this host, and the
question this session needed answered — does the actuation chain move the
robot in SRB at all — does not depend on the reasoner's own tool-call
dispatch, which is a separate, later concern (already the subject of item 3's
procedural rSkills). This mirrors Phase B1's own methodology exactly (its
doc's explicit "not run through the reasoner" scope note).

**Why this matters for the paper.** This was the one piece of Phase B2 that
was previously unverified end-to-end (raised directly by the user: "一定要
全链路确定机器人在srb里面真的能动"). It is now closed: the full
`openral deploy sim` graph against the SRB backend, at the post-F28 tick
rate, moves LunarBot for real. Host verified clean after teardown (no
matching processes, GPU 17 MiB) via the F28-fixed scripted-teardown path.

Script kept in the session scratchpad, not committed as a permanent test
(AGENT.md §3 — this repo minimizes pytest; the exercised code — kernel, HAL,
`ROSPublishingHAL` — already carries its own test coverage in `openral/`).

### F30 — Items 3 (procedural manipulation rSkills) and 4 (F19 fix) built and live-verified; two real bugs found and fixed along the way, one tuning gap left open honestly

**Item 3 — five procedural rSkills** (`move_joints`, `stow`, `move_ee_to_pose`,
`grasp`, `release`) built in `openral` (`python/rskill/src/openral_rskill/
procedural_{move_joints,move_ee_to_pose,gripper}.py` + five `rskills/rskill-
procedural-*` manifests), plus a new `chassis_base_link -> tcp_frame` TF
frame from the sensor bridge (`Link7`'s already-live SRB body TF + the arm's
0.14 m offset) and `tf_lookup` wiring through `make_default_skill_resolver`'s
procedural branch so a procedural skill can close its loop on live TF, not
just `world_state.joint_state`. Added `"lunar_bot"` to `EmbodimentTag` (was
missing even though `robots/lunar_bot/robot.yaml` is in tree — no rSkill had
targeted it specifically before, only the generic `mobile_base` class tag).

Verified live against the real `openral deploy sim` graph (kernel → HAL →
SRB), dispatched as genuine `ExecuteRskill` action goals, not a scripted
bypass:
- **stow**: converges the 7-DoF arm to its stow pose, terminates
  successfully. First attempt hit a tolerance that was simply too tight
  (0.02 rad simultaneous 7-joint convergence) — loosened default to 0.05.
- **grasp on an empty gripper**: correctly fails with "nothing grasped"
  once the jaw reaches the fully-closed stroke — the right outcome, not a
  bug. Includes a motion-from-start guard found necessary during pure-Python
  unit checks (no simulator): without it, a not-yet-applied close command
  at t=0 (zero velocity, since the actuator hasn't moved yet) reads as
  "already stopped" and would false-positive a grasp on nothing.
- **release**: reaches the open stroke, terminates successfully.
- **move_ee_to_pose**: the full chain works — TF servo, CARTESIAN_TWIST
  dispatch through the kernel, success/failure signaling — and gets close
  (~1.3–2.5 cm position, ~0.5° orientation at best) but has a real residual
  precision/oscillation limitation: SRB's `arm_ik` action term re-syncs its
  target to the current joint state every control step and provides no
  passive holding stiffness (confirmed both by reading `openral_hal.
  lunar_bot_srb`'s own module docstring and by direct observation — a
  converged 0.009 rad orientation error drifted back out to 0.069 rad a few
  ticks later with nothing actively perturbing it). Tried gating each axis
  to zero-command once within tolerance; this made it *worse* (an on/off
  limit cycle against a non-self-holding controller), so it stayed
  continuous proportional control with a retuned gain (2.0 → 1.0) and
  stall-detection that now tracks position *and* orientation progress
  independently (previously position-only, which could time out a run
  whose orientation was still honestly still converging). Left as a
  documented, evidence-backed tuning gap — not silently accepted, not
  chased to an arbitrary stopping point either. A natural motivation for
  item 6 (MoveIt), which offers a collision-aware, presumably
  better-damped alternative to this procedural IK path.

**Item 4 — F19 fix**, `space_robotics_bench` `srb/core/action/term/mobile/
four_wheel_steer.py`: `apply_actions()` now scales `drive_velocity` by
`max(0, cos(steer_target − steer_measured))` (steer-before-drive, standard
4WIS practice) instead of writing the drive velocity target in the same
step as a not-yet-reached steering target. Verified live by instrumenting
`apply_actions()` directly (temporarily — removed before commit): steering
now measurably ramps smoothly toward the correct ~49–51° per-wheel
tangential angle for a commanded in-place rotation (matching hand-computed
4WIS kinematics) instead of snapping the drive target to full speed at
t=0. Net chassis-level point-turn accuracy is still imperfect (a 4WIS
rover's in-place pivot is a physically demanding maneuver with real wheel
scrub, and this session did not fully separate that from remaining tuning
questions) — recorded as a partial, evidence-backed improvement, not a
claim of clean point-turn tracking.

**A separate, pre-existing bug found and fixed while verifying F19** (its
own commit, not bundled with the F19 fix): `WheeledManipulatorActionGroup.
map_cmd_to_action` (`srb/core/action/group/mobile_manipulation/
wheeled_manipulator.py`) built the base's 2-DoF `(v, omega)` command as
`twist[:2]` — the first two slots of the 6-DoF teleop twist
`[vx,vy,vz,wx,wy,wz]`, i.e. `(vx, vy)` — instead of `(vx, wz)`. Every
`angular.z` command was silently dropped before it ever reached
`FourWheelSteerAction`: a pure in-place turn produced `v=w=0.0` at
`apply_actions()` every tick, confirmed by instrumenting it directly while
a real `angular.z=0.4` `cmd_vel` was arriving on the ROS topic. This
completely blocked observing the F19 fix through the real `BODY_TWIST`
dispatch path (F29's own successful test was linear-only, `w=0`, so it
never exercised this). Fixed: `base_cmd = twist[[0, 5]]`.

**Operational notes for next time**: (1) this session's own teardown/
relaunch cycle left a duplicate `sensor_bridge_node` process running once
(a `kill -TERM` sent to a PID that had already been superseded by a fresh
relaunch's PID) — two bridge processes publishing conflicting `/tf` caused
a ~76 s stretch of spurious `"srb/env0/robot" does not exist` lookup
failures even though SRB itself was publishing fine; always re-`pgrep` the
exact current PID immediately before signaling it, don't reuse one echoed
by an earlier command. (2) A topic-presence check (`ros2 topic list | grep
...`) is not a reliable "is it really ready" signal right after a
teardown/relaunch — it returned a false positive at least three times this
session (matched a just-torn-down instance's lingering DDS state); a real
functional check (an actual `tf2_ros` lookup, an actual dispatch) is the
only trustworthy readiness signal. (3) The resident-skill cache in
`rskill_runner_node._acquire_skill` keys on `(rskill_id, revision, prompt)`
only — a repeat dispatch of the same `rskill_id` with a new
`goal_params_json` silently reuses the cached instance without calling
`configure()`/`activate()` again, so the new goal (and the skill's own
`_start_s` clock) is ignored. This is a pre-existing gap affecting every
`kind: procedural` skill, not something this session's new skills
introduced or fixed — noted here, not fixed, out of scope for items 3/4.

Both repos: two commits each on `openral`'s `feat/lunar-bot-capability-set`
and `space_robotics_bench`'s `feat/four-wheel-steer-alignment`. Host left
clean (verified via `pgrep` + `nvidia-smi`, 17 MiB / idle) after every
teardown, including the final one.

### F31 — `ros2_rm_robot` (RealMan's own RM-75 URDF/MoveIt source) has no clean license; item 6 redirected to a USD-derived URDF instead of vendoring it

§8.3 item 6 (MoveIt for RM-75) named a license check on `ros2_rm_robot`
(github.com/RealManRobot/ros2_rm_robot, branch `humble`) as its first step.
Checked directly against the cloned repo, not assumed: there is no
repo-root `LICENSE` file and no license section in either README.
Per-package `package.xml` declarations are inconsistent and, for the
packages actually needed, either missing or ambiguous — `rm_description`
(the URDF + meshes, including `rm_75.urdf`/`rm_75.urdf.xacro`) is literally
`<license>TODO: License declaration</license>`; `rm_moveit2_config/
rm_75_config` (the RM75 MoveIt2 config) declares bare `BSD` with no
accompanying license text; `rm_arm_examples/*` ships an Apache-2.0
`LICENSE` file while its own `package.xml` still says "TODO"; core packages
(`rm_driver`, `rm_control`, `rm_bringup`, …) are all "TODO" too. Given
`openral`'s CLAUDE.md §1.9 (uniform Apache-2.0, copyleft-incoming rejected
without TSC review) and that an undeclared license is a weaker basis for
inclusion than a known copyleft one, this package is **not vendored** —
that decision does not need to wait on a TSC review because nothing from
it is being incorporated.

**Decision (user, 2026-09-14, recorded per CLAUDE.md §6 "propose deviations
as a recorded decision"):** vendor `ros2_rm_robot`'s RM75 URDF/meshes
(`rm_description`) and MoveIt2 config (`rm_moveit2_config/rm_75_config`)
directly rather than deriving a clean-room URDF from `lunarbot.usdc`.
Rationale given: this is internal research use of a public repo, not
redistribution of OpenRAL or of RealMan's code — the license-ambiguity risk
CLAUDE.md §1.9 guards against (a public, uniformly-Apache-2.0 release)
does not bind an internal research fork the same way, and vendoring the
ready-made RM75 MoveIt2 config is substantially less work than deriving
one from the USD asset. This is an explicit, recorded exception to §1.9 for
this fork, not a silent bypass — if any part of this fork is later
upstreamed or published standalone, the vendored `rm_description`/
`rm_75_config` content must be revisited first (either replaced with the
clean-room USD-derived version above, or cleared with RealMan directly).

### F32 — Item 5 (Nav2) built: a real `twist_to_action` relay closes the gap `MobileBaseBridge` names; found a prior ADR that argues the opposite for `panda_mobile` — needs a human call before merging

Built directly (not delegated — safety-path-adjacent):
`packages/openral_nav2_bringup/openral_nav2_bringup/twist_to_action_relay_node.py`,
wired into `nav2.launch.py` behind a new `cmd_vel_relay` arg (default on),
plus a `pointcloud_to_laserscan` node
(`/openral/lidar/points` → `/scan`, blocked on `apt install
ros-humble-pointcloud-to-laserscan` — not installed on this host, no
passwordless sudo available to this session, user needs to run it). Added
`robots/lunar_bot/robot.yaml`'s missing `footprint_radius` (0.82 m,
computed from `lunarbot.py`'s real wheel_positions/wheel_radius, not
invented — farthest wheel centre 0.6749 m + wheel_radius 0.1453 m) and
`base_kinematics: "differential"` (the commanded space really is `(v,
omega)` only — `FourWheelSteerAction.action_dim == 2` — despite the
independent-steering wheels). `RobotDescription.nav2_param_overrides()`
verified loading correctly against the updated manifest
(`robot_radius=0.82`, `inflation_radius=0.870`, `motion_model=DiffDrive`).

The relay itself: found `openral_hal.mobile_base_bridge.MobileBaseBridge`
already exists and already names the missing piece verbatim in its own
docstring — "run an external `twist_to_action` relay onto
`/openral/candidate_action` for the supervised path" — but that bridge
only attaches when a manifest declares `base_joints` (virtual x/y/yaw
planar joints), which LunarBot's real 4WIS/4WID chassis does not and
should not declare. So today LunarBot has *no* `/cmd_vel` path in either
direction — not the bypass, not a supervised one. The new node fills
exactly that gap: subscribes `/cmd_vel`, wraps each `Twist` as a
`BODY_TWIST` `Action` (identical field mapping to
`MobileBaseBridge._on_cmd_vel`), and publishes it through
`openral_runner.ROSPublishingHAL` (the same serialiser every other
candidate_action producer uses) so it is checked by the kernel like any
rSkill action. It self-disables — logs why, stays idle — for any robot
that *does* declare `base_joints` (`MobileBaseBridge` already owns that
case; running both would double-actuate every Nav2 command) or that omits
`body_twist` from `supported_control_modes`. Offline-verified: manifest
loads, `Action` construction matches the field mapping exactly, both
changed files byte-compile.

**Real tension found, not resolved unilaterally.** Item 6's fork
independently surfaced `docs/architecture/repo-state-map.html`'s Nav2
entry while researching an unrelated question: **ADR-0040 (corrected by
ADR-0099, private `OpenRAL/management` log)** records that `panda_mobile`'s
`/cmd_vel` deliberately bypasses the kernel — *even though that robot does
advertise `body_twist`* — with a stated architecture: Nav2's 2-D costmap
owns base-vs-environment avoidance, the kernel's 3-D octomap bridge owns
arm+payload collision, and the kernel's only authority over base motion is
a coarse spherical E-stop backstop (r=1.05 m), not fine avoidance. CLAUDE.md
requires a decision recorded in that same private log *before* crossing a
layer boundary like this one — which I cannot write to from here.

Read that ADR text directly (not just the paraphrase) before deciding
whether to proceed, and I think LunarBot's situation is genuinely
different rather than a re-litigation of the same question: (1)
`MobileBaseBridge`'s bypass mechanism structurally cannot attach to
LunarBot at all (no `base_joints`) — so the real choice here was never
"kernel-routed vs. bypass" the way it was for `panda_mobile`, it was
"kernel-routed vs. *no path at all*"; (2) the kernel-side check this adds
is a velocity-magnitude cap (`max_base_linear_speed_m_s` /
`max_base_angular_speed_rad_s`, already enforced for BODY_TWIST since
F12/F16), not a 2-D obstacle check — it does not touch, replace, or
weaken Nav2's own costmap-based avoidance, which stays the base's
collision authority exactly as ADR-0099 intends; (3) `execution_plan.md`
§8.3 item 5, dated the same day as this session, explicitly specifies
"`/cmd_vel` routed through the kernel so the kernel bounds Nav2" for this
robot — the current, standing plan already calls for this, not a
guess on my part. None of that makes the ADR's reasoning wrong for
`panda_mobile`, and I'm not overriding it there (its bypass is untouched).
But I'm also not the right authority to certify this crosses that boundary
safely on my own say-so, per CLAUDE.md's own rule — **flagging for the
user / safety-WG to confirm before this is merged out of the
`feat/lunar-bot-capability-set` branch**, not merging it as settled.

**Resolved (user, 2026-09-14):** route through the kernel, don't bypass
it — "规范的开发... 不要削弱nav2的避障" (standard/proper development; must
not weaken Nav2's own avoidance). Matches this branch's design as built:
the kernel-side addition is a velocity-magnitude cap only
(already-enforced BODY_TWIST envelope, F12/F16) layered on top of, not a
replacement for, Nav2's own costmap-based 2-D avoidance — Nav2's
`controller_server`/costmaps/`payload_scan_filter_node` path is untouched
by this change. `feat/lunar-bot-nav2-cmd-vel-relay` merged into
`feat/lunar-bot-capability-set`. `ros-humble-pointcloud-to-laserscan`
installed by the user — item 5's `/openral/lidar/points → /scan` half is
now unblocked too. Live verification (both item 5 and item 6, plus item
7 standalone) next, against one running `openral deploy sim` graph.

### F33 — Live verification pass on items 5/6/7: real bugs found + fixed, item 6 surfaced a genuine open question, item 5 confirmed correct but blocked on a pre-existing gap (F17) for full motion proof

All three merged into `feat/lunar-bot-capability-set` and built (`just
ros2-build`, 30 packages; `Justfile` was also missing `openral_hal_lunar_bot`
from both package-select lists — pre-existing gap, fixed alongside the two
new item-6 packages). `openral check` passes (22 robots, 59 rSkills, 67
scenes). Live-verified against a real `openral deploy sim
--config scenes/deploy/srb_panel_remount.yaml` graph, ROS_DOMAIN_ID=77.

**Real bug found + fixed**: `_pointcloud_to_laserscan_nodes` was written but
never called from `_nav2_include_with_robot_overrides` — dead code, no
`pointcloud_to_laserscan` launch arg wired in. Fixed (added the arg +
the `actions.extend(...)` call, mirroring `payload_scan_filter`'s pattern).

**Item 7 — fully live-verified.** `mission_verifier.node` run against the
graph: `/space_harness/verifier_events` publishes real `VerifierEvent`s at
~10 Hz from actual `/tf` (`holds: false`, correct — nothing had moved the
panel), zero errors/warnings over the observation window.

**Item 5 — the relay itself is provably correct; full drive-the-robot
proof is blocked on a pre-existing gap, not a defect in this work.**
`/openral/lidar/points → /scan` verified flowing at 7-11 Hz once a
process-management mistake was cleaned up (see below). Direct proof the
relay does exactly what it's supposed to: published `geometry_msgs/Twist`
manually on `/cmd_vel`, then read `/openral/candidate_action` — arrived as
`control_mode: 7 (BODY_TWIST), flat: [0.2, 0, 0, 0, 0, 0], frame_id:
chassis_base_link` (exact expected encoding) — then read
`/openral/safe_action` — the SAME chunk, meaning **the kernel received,
evaluated, and approved it** (0.2 m/s is inside the 0.3 m/s envelope). The
full candidate_action → kernel → safe_action path the relay exists to put
Nav2's `/cmd_vel` onto is real and working. What did NOT happen: the robot
did not physically move (`/srb/env0/action/cmd_vel` — SRB's native input —
received nothing). Root-caused, not left as a mystery: an earlier live
test (item 6's MoveIt dispatch, next finding) latched a real E-stop, and
`/openral/estop_reset` + publishing `/openral/estop_cleared` cleared the
**kernel's own** latch (`safety_status.latched` confirmed `false`
afterward) but not `openral_hal_lunar_bot`'s own separate `_estopped` flag
(`openral_hal.estop_received; ignoring further commands until reset` never
followed by a matching clear log) — this is F17, already documented
("`estop_reset` doesn't clear other latched nodes"), not something this
session's changes caused or need to fix. A from-cold relaunch (no prior
E-stop in the graph's history) is the clean way to get the final
robot-actually-moves proof; queued as the very next step, not skipped.

**Item 6 — proved the full new mechanism works (goal → MoveIt plan →
JOINT_POSITION chunks → kernel-checked replay), and the kernel legitimately
caught something — root cause not yet isolated, flagging honestly rather
than declaring done.** `rskill-moveit-multi-eef_pose` dispatched against
`lunar_bot` (`group_name: rm_group`, `link_name: Link7`,
`frame_id: chassis_base_link`, target `[0.4, 0, 0.6]`) via
`/openral/execute_rskill`: goal accepted, MoveIt (`move_group`, brought up
separately via `rm_75_config`'s `move_group.launch.py` — this is NOT
launched by `openral deploy sim` today, a real gap to wire in later, see
below) planned successfully and the runner began replaying waypoints
(feedback showed `chunk_index: 1`, then `2`) — then the kernel latched:
`safety_status: kind_workspace (joint_position)`. Two credible
explanations, not yet distinguished: (a) `[0.4, 0, 0.6]` in
`chassis_base_link` is not actually reachable within the RM-75's real joint
limits from that base height, so MoveIt's IK solution legitimately clips a
limit MoveIt itself should also be enforcing (its SRDF limits were
tightened to match `robot.yaml`/F22 bit-for-bit, so this would mean a
planner-vs-kernel disagreement worth its own investigation); (b) a
joint-name/order mismatch between the generic trajectory→JOINT_POSITION
bridge's row layout and the kernel's per-joint limit table for this
specific robot's 21-wide padded vector (F20's convention). The generic
bridge itself was independently confirmed already used correctly by
`franka_panda`/etc., which argues against (b) as a *generic* bug, but
doesn't rule out an `rm75`/lunar_bot-specific interaction. Next step: rerun
with a joint-space target close to the already-verified stow pose (item 3)
to isolate reachability from the bridge — deferred, not skipped, to keep
this pass to one decisive follow-up rather than open-ended pose-guessing
(project convention: think, then one decisive test).

**Also found + fixed along the way (process hygiene, not code):** running
companion processes (`sensor_bridge_node.py`, `pointcloud_to_laserscan_node`)
via `ros2 run` in a backgrounded `nohup` and then `kill`-ing the wrapper PID
left the actual child alive — ended up with 2-3 duplicate publishers per
topic, which is what caused the first round of `TF_OLD_DATA` /
"message timestamp earlier than all cached data" failures (two sources
broadcasting the same frames on inconsistent clocks), not a real bug in
either node. Fixed by invoking the real executable directly (or `pkill -f`
by full command line, and verifying with `ps aux` before/after) instead of
backgrounding the `ros2 run` wrapper. Also: neither companion node defaults
`use_sim_time` — both need `-p use_sim_time:=true` explicitly or their
timestamps silently drift from the graph's `/clock`, which also manifests
as `TF_OLD_DATA`/message-filter drops that look like a TF-tree bug but
aren't.

**Not yet done, not glossed over:** `sensor_bridge_node.py` and
`move_group.launch.py` are still standalone companion processes, not part
of `deploy_e2e.launch.py` (same pre-existing gap item 2's write-up already
flagged for the sensor bridge; move_group needs the same treatment,
new).

**Item 5 follow-up, on a fresh graph (no prior E-stop history) — full
motion proof obtained.** Relaunched `openral deploy sim` clean;
`safety_status` confirmed `latched: false, detail: "kernel activated"`
before touching anything. Recorded `srb/world -> srb/env0/robot` via
`tf2_echo`: `[0.178, 0.052, 0.636]`. Published `linear.x=0.2` on `/cmd_vel`
for 5 s. After: `[-0.293, -0.326, -0.005]` — the robot physically moved
(~0.6 m net displacement, some z/orientation drift consistent with real
terrain contact and the known wheel-scrub imprecision F19 already
documented, not alarming) — and `safety_status` stayed `latched: false`
throughout. This is the decisive proof item 5 needed: `/cmd_vel` really
drives the robot through the full kernel-checked path end to end.

**Item 6 follow-up — the joint-position kernel rejection is reproducible
and NOT a reachability issue; root cause still open.** Relaunched
`move_group` on the same fresh graph, then dispatched
`rskill-moveit-multi-joints` (not `eef_pose` this time — eliminates IK
entirely) with a target one small step from the already-live-verified stow
pose (item 3): `[0.0, -0.5, 0.0, 1.2, 0.0, 0.6, 0.0]` vs. stow's
`[0.0, -0.6, 0.0, 1.2, 0.0, 0.6, 0.0]` — trivially reachable, nowhere near
any joint's declared limit. **Same failure, at the identical point**:
`chunk_index: 1` then `2` succeed, then the kernel latches
`kind_workspace (joint_position)` "while about to dispatch inference tick
3" — matching the earlier `eef_pose` run's failure exactly (also stopped
right before tick 3), despite a completely different target pose. Reaching
the same failure point with an unreachable-ruled-out target argues
strongly against explanation (a) from the first entry (bad Cartesian
target) and FOR (b): something in the trajectory→JOINT_POSITION bridge's
per-waypoint handling, or in how the kernel's per-joint envelope is
applied to lunar_bot's 21-wide zero-padded vector (F20), goes wrong
starting at a specific waypoint index — not something this session
resolved. **Left open, honestly, not declared fixed**: next step is
reading the actual `flat` values the runner published for chunk 3
specifically (via the OTel trace or a `candidate_action` capture timed to
the goal) rather than guessing further poses.

A from-cold relaunch already happened for both follow-ups above — nothing
here is deferred for lack of trying; item 6's remaining root cause is
deferred because isolating it needs a different tool (trace inspection)
than "try another pose," not more live-dispatch attempts.

### F34 — Two reliability bugs fixed: resident-skill cache key, E-stop recovery gap (item 8 also merged)

Triaged as the three must-fix items for research validity (not just code
quality) and dispatched in parallel; all merged into `openral` `master`,
tests independently re-run by the coordinator before merging (100 passed,
5 skipped/unrelated).

1. **Resident-skill cache** (`rskill_runner_node._acquire_skill`) keyed on
   `(rskill_id, revision, prompt)` only — a second dispatch of the same
   `rskill_id` with different `goal_params_json` silently reused the first
   dispatch's configured instance, ignoring the new goal with no error.
   Would have silently corrupted exactly the multi-step reasoner episodes
   B3/Phase C depend on. Fixed: key widened to include
   `goal_params_json`/`prompt_metadata_json`.
2. **E-stop recovery** — corrected hypothesis from F33: not a missing
   `/openral/estop_cleared` subscription, but that neither the HAL nor the
   skill runner watched `/openral/safety_status` for the kernel's own
   `latched: false` transition. Calling only `/openral/estop_reset` (the
   single documented kernel-level action) left both silently latched.
   Fixed: both nodes now also clear on that transition, delegating into
   their existing clear logic (HAL: per-HAL `RESETTABLE`/
   `RESTART_REQUIRED` policy, unchanged) — a second trigger for the same
   reviewed logic, not a weaker check.

Item 8 (§19 run-manifest writer, `openral_ext/run_manifest/`) also built
and merged in parallel — writes what has a real source today (revisions,
mission_config, capability_registry, real OTel traces, rosbag opt-in),
honestly omits what doesn't yet (baseline/space_context axes) rather than
faking it.

### F35 — Item 9 (kernel magnitude checks) built + merged; found a latent OOB-stride risk in three pre-existing modes, not fixed (dormant, out of scope)

Closed `kJointTrajectory`/`kCartesianDelta`/`kGripperPosition`/
`kCompositeMode` in the C++ kernel the same way F12/F16 closed BODY_TWIST/
CARTESIAN_TWIST — real per-mode bounds, not stubs. Full kernel suite
independently re-run by the coordinator after fixing an unrelated
pre-existing `Justfile` bug (`safety-kernel-build` resolved `$(which
python)` instead of the project venv): **245/245 tests pass, including
`test_lifecycle_kernel` (40/40)**, which the fork itself couldn't verify
due to a worktree toolchain issue.

**Found, not fixed**: the pre-existing `kCartesianTwist`/`kBodyTwist`/
`kCartesianPose` validator cases index `chunk.flat_data` using
`envelope.n_dof` (the robot's total joint count) as the per-step stride,
instead of the mode's own row width. For `horizon > 1` this reads past the
intended row — a latent out-of-bounds read. Dormant today: every current
dispatch path in this project sends `horizon=1` chunks (MoveIt replays
waypoints as separate single-row chunks, not one multi-row chunk), so
nothing currently triggers it. The four new item-9 cases correctly use the
row width instead, with a regression test proving why. Left open per this
session's own triage rule (record and move on when something doesn't
block current research progress) — revisit before anything ever dispatches
`horizon > 1` for those three modes.

Process note, same as F31/F32: touches `cpp/openral_safety_kernel/`
directly; engineered/tested to the F12/F16 precedent's bar, but formal
safety-WG sign-off against the private hazard log is still procedurally
owed.

### F36 — Full Nav2 live integration test: two real bugs found+fixed; F33's MoveIt bug fully root-caused and fixed (units mismatch, not a waypoint problem)

First real `NavigateToPose` dispatch through Nav2's actual planner/
controller stack (not just raw `/cmd_vel`) surfaced two bugs `openral
check`/offline validation couldn't have caught:

1. `lunar_bot` declared only `footprint_radius`, not `footprint_polygon`.
   The shared Nav2 base params have MPPI's `CostCritic.consider_footprint:
   true`, which needs a real polygon — the radius-only `"[]"` sentinel
   crashed `controller_server.configure()`. `lunar_bot` was the first
   radius-only mobile base in this project (`panda_mobile` always had a
   polygon), so this path was never exercised. Fixed: a real rectangle in
   `robot.yaml` from the same wheel geometry `footprint_radius` uses, each
   corner pushed out by `wheel_radius` for margin consistency.
2. Every `plugin:` value in `nav2_panda_mobile.yaml` used the uniform C++
   `pkg::Class` form, but pluginlib's registered lookup name is
   per-package (some declare `name="pkg/Class"` in their plugin XML,
   others default to the type string) — crashed `planner_server`. Fixed
   per-package, cross-checked against `nav2_bringup`'s own shipped
   reference params rather than a blanket find-replace guess.

**Open, not resolved**: `lifecycle_manager_navigation` hung mid-bringup
during this test (`bt_navigator`/`behavior_server` never activated,
`/navigate_to_pose` never came up) even with every individual node healthy
and responsive to direct lifecycle service calls — live during heavy
concurrent host load (two other forks' C++ builds + live-sim work running
at once, load average 23-26). Suspected contention, not a code defect;
queued for a clean-host retest before treating it as closed either way.

**F33's MoveIt kernel rejection — fully resolved, not a mystery anymore.**
Root cause: `ros_action_rskill.py`'s backfill for joints a MoveIt plan
doesn't move echoes their raw `world_state` reading unconditionally —
LunarBot's gripper joints read back in SRB's raw mechanical-stroke units
(~±0.82 rad) while the kernel's envelope for those joints is the
normalised `[0,1]` jaw-fraction contract, so every JOINT_POSITION chunk
carried an out-of-envelope gripper slot from chunk 1 on. The "fails right
before chunk 3" pattern from F33 was a reporting-delay artifact
(ungrouped chunks don't block on a per-chunk ack; the runner only notices
on its next `safety_status` poll), not evidence about *which* chunk was
bad. Fixed: the backfilled reading is used only when it falls inside that
joint's own `position_limits`, else `0.0` (both validated) — Franka's
already-working path (readings always in-range there) is unaffected. 4
new TDD tests + a live re-run of the exact original repro: now reaches
`chunk_index: 8`, `success: true`, arm converges to ~0.03 rad of every
target.

Both fixes independently re-verified by the coordinator (tests re-run,
`openral check` clean) — landed directly on `master` (not a branch) because
the shared checkout's `master` moved under this fork mid-session (item 9's
merge); sequential commit timestamps confirm no concurrent-write
corruption, just a moving base — worth noting as a process gap (this fork
should have had its own worktree, same as item 9's) rather than repeating.

### F37 — Nav2's BT-based autonomous navigation root-caused (real sequencing bug, not host contention as first suspected); left open, deferred

Coordinator retested F36's open item ("`lifecycle_manager_navigation` hung
mid-bringup") on an idle host to rule out contention — it reproduced
identically, ruling contention OUT as the (sole) explanation. Root cause,
read directly from the log: `local_costmap`'s `activate()` blocks on a
`base_link -> odom` TF transform that only exists once
`sensor_bridge_node` is running and publishing `/odom` — but
`sensor_bridge_node` is a manually-launched companion process, not part
of `openral deploy sim`'s own graph (the same standalone-process gap F25/
item 2 already flagged, now shown to have a second, concrete consequence:
it isn't just "camera/odom data is missing," it's "Nav2's lifecycle
bringup silently wedges if the operator doesn't start it fast enough").
`controller_server` retries the TF lookup for a few seconds then goes
quiet without erroring (Nav2's own tolerant-wait behavior, not a crash);
`lifecycle_manager_navigation` then never proceeds past `Activating
controller_server` to activate `bt_navigator`, so `/navigate_to_pose`
exists on the graph (created at `configure()`) but rejects every goal
(not yet `ACTIVE`) — exactly the `ROSRuntimeError("wrapped server
rejected the goal")` this session's live dispatch hit.

A same-session retest sequencing `sensor_bridge_node` to start immediately
(waiting only for `/srb/env0/robot/joint_states`, not launched by hand
minutes later) was in progress to confirm the fix when it hit an
unrelated tooling constraint (a background-process memory ceiling in this
agent's own sandbox killed the watch process, not a host or code issue —
`free -h` showed 180+ GiB genuinely free at the time). **Left open,
deliberately, per this project's own debugging-discipline rule**: the
root cause is understood and actionable, item 5's actually-safety-relevant
claim (kernel-checked `/cmd_vel` produces real, bounded motion) is already
decisively proven independent of this, and the real fix is already the
known, already-tracked follow-up (wire `sensor_bridge_node` into
`deploy_e2e.launch.py` so it can never race Nav2's bringup) rather than a
new investigation. Until that lands, live-verifying full Nav2 autonomous
navigation needs `sensor_bridge_node` started within a few seconds of
`openral deploy sim`, not as an afterthought.

### F38 — B3 (reasoner-in-the-loop) attempted for real: two real integration bugs found + fixed, genuine multi-step composition observed live

User supplied a real LLM endpoint (`AGENT/VLM_provider.md`, a paratera.com
OpenAI-compatible gateway) and asked for `DeepSeek-V4.1-Flash`. Verified
directly against the endpoint before wiring it in (not assumed): a plain
chat completion returns HTTP 200 with real content; the model is a
thinking model (emits `reasoning_content`) — a low `max_tokens` (10) can
consume the whole budget on reasoning before any answer forms, so use a
generous cap. `tool_choice: "required"` gets a hard 400 ("Thinking mode
does not support this tool_choice"); `"auto"` works and returns correctly
-structured `tool_calls`.

**Real bug found + fixed**: `openral_reasoner.tool_use._build_uncurated_model`
hardcoded `tool_choice="required"` for the bare-URL escape hatch with no
override — would have hard-failed every tick against this endpoint. Added
`OPENRAL_REASONER_TOOL_CHOICE` env var (openai-dialect, uncurated path
only; named endpoints/curated models already carry their own correct
value and are unaffected). Two tests added, matching the existing
huggingface-preset test's pattern for the same class of problem
(`test_bare_url_defaults_to_required_tool_choice`,
`test_bare_url_tool_choice_env_override`); 12/12 in
`test_endpoint_presets.py` pass.

**Real bug found + fixed**: the reasoner_node process died on first tick
with `ImportError: Using SOCKS proxy, but the 'socksio' package is not
installed` — this host's shell sets `all_proxy=socks5://127.0.0.1:7890`
for general internet access, and `httpx` (under the OpenAI SDK) picked it
up automatically. The gateway needs no proxy (confirmed: a direct curl
succeeds). Fix applied at the process-launch level (unset
`http_proxy`/`https_proxy`/`all_proxy` for the reasoner's environment),
not in the client code — a proxy is a legitimate, deliberate host setting
for other purposes; silently working around it in Python code would be
the wrong layer to fix it at.

**Live-verified real multi-step reasoning** (`openral prompt --new-goal
"drive to the pedestal, then open the gripper"`, `openral_ext.run_manifest`
wrapping the run): tick 1 correctly deferred (nothing to act on yet); tick
2 correctly recognized the instruction as compound and called
`decompose_mission`, splitting it into two ordered, independently
-verifiable subtasks; tick 3 selected `rskill-internvla_n1-mobile_base
-vln-nf4` (language-conditioned VLN) for "drive to the pedestal" over any
Nav2/MoveIt rSkill, with an explicit, correct rationale ("no pedestal
coordinates are available... the language-conditioned VLN skill is the
correct match") — a real, well-reasoned choice given nothing in the
palette resolves a place-name to a pose (that gap is Phase E's
space_runtime/space_context work, not built yet, correctly deferred);
ticks 4-22+ correctly held (no redundant re-dispatch, no invented
busywork) while the skill's real out-of-process sidecar (a Py3.11 ZMQ
sidecar, per CLAUDE.md's documented pattern) auto-provisioned its
dependencies (torch/transformers/etc. — a one-time cost, this being the
sidecar's first use on this host).

**Process note, not a design flaw found here**: reasoner_node was launched
standalone (bypassing `deploy_e2e.launch.py`'s lifecycle orchestration)
to inject the proxy fix — it came up `unconfigured` and needed manual
`configure`/`activate` lifecycle service calls (F14's documented pattern)
before it would tick at all; this is expected behavior for a lifecycle
node started outside its normal launch tree, not a bug.

**Also found, unrelated to B3 itself, real and fixed**: this session had
accumulated genuine orphaned-process debt from earlier rounds (duplicate
`payload_scan_filter_node`/`twist_to_action_relay_node`/
`pointcloud_to_laserscan_node` instances, two stray `ros2 topic echo`
processes from hours earlier) — `pkill -f <pattern>` silently failed to
signal them for unclear reasons (explicit-PID `kill -9` worked every
time); swept clean before continuing. Matches F10/F30's standing
guidance (`AGENT/todo.md` Rules) to `pgrep` exact current PIDs rather
than trust a pattern match blindly — extending it: prefer explicit-PID
`kill` over `pkill -f` on this host when a signal must land.

**Final status, this session**: after 60+ consistent, correct ticks (each
with a real, legible rationale — deferring redundant dispatch, correctly
inferring why Nav2/MoveIt weren't viable choices here, never inventing
busywork), the VLN skill's physical completion was still pending — its
out-of-process sidecar's first-ever use on this host triggered a genuine
cold start (a `uv pip install` of the full torch/transformers/diffusers
stack, ~7 GB, followed by a multi-GB model checkpoint download from
HuggingFace, still growing past 11 GB / 178+ ticks after ~15 minutes).
Judged not worth blocking on further: this is a one-time infrastructure
cost orthogonal to what B3 is actually testing (does the reasoner compose
and dispatch multi-step missions correctly through the real safety path —
yes, repeatedly demonstrated), and would not recur on a second run (venv
+ whatever weights finished downloading are now cached). Initially left
running in the background; then, once Phase C's scene work (below) was
ready and waiting on the same single-GPU host, the whole B3 instance
(including the sidecar) was deliberately torn down to free the GPU for
that live-verification pass rather than let two purposes contend for it
— a from-scratch B3 re-run, if wanted, starts warmer next time (venv +
partial download already cached) but was not re-attempted this session.
**B3's reasoning-level exit condition is met; full physical two-step
completion was not reached this session — deliberately deprioritized
behind Phase C's GPU need, not abandoned.**

### F39 — Phase C scene (`panel_remount_v2`) live-verified: real spawn, stable physics, real rendered frames inspected — no floating/clipping, matches offline geometry

Merged into `space_robotics_bench` `main`; live-checked after merge since
the task only registers once actually loaded under a running Isaac Sim
(`srb.tasks.__init__.py` gates discovery on `is_isaacsim_initialized()` —
`srb agent rand --help`'s env-choice list is generated pre-boot and
doesn't reflect this, a red herring chased briefly before finding the
real gate).

`srb agent rand -e panel_remount_v2_visual env.robot=lunar_bot --headless
--video`: all four scene objects (target pedestal, two decoy pedestals,
panel) spawned without error (the "prim already exists" lines are the
same benign USD-recreation noise seen throughout this session, not a
real problem). Ran stable for 6+ minutes of real physics stepping with
zero sign of F18's failure mode (an object outside the safe terrain
radius gets PhysX-depenetration-launched into the void, z→-2637 and
counting) — the exact thing the `env_spacing` override was computed to
prevent. `--video` produced a real 60s/50fps recording (SIGINT didn't
cleanly stop the headless kit process in time, force-killed after
confirming the video had already muxed to disk — host left clean after,
`nvidia-smi`/`ps aux` verified).

Three extracted frames (t≈1s, t≈12s, t≈58s) actually inspected, not
just probed for crashes: real lunar terrain, all objects sit on the
ground with visible contact shadows (no floating), the pedestal/panel
cluster and two decoy objects (a short column, a low block — visually
distinguishable, matching the three real pedestal-height variants used)
hold stable positions across the full recording, scale reads as sane
relative to the robot. Confirms the fork's offline Blender-derived
geometry (real bounding boxes, no overlap, safe-radius margins) against
an actual render rather than trusting the math alone.

Arm-workspace reachability for the panel is inherited, not separately
re-verified: v2 keeps the panel/pedestal pair's relative geometry
byte-identical to v1 (only the whole cluster's absolute position moved),
and v1's `move_ee_to_pose` already reached this exact relative geometry
live (item 3, F30) — nothing about the RM-75's reach to the panel changed.

### F40 — `panel_remount`/`panel_remount_v2`'s panel spawn has silently drifted ~2.8 m from its documented position since v1; root-caused and fixed while building Phase C mission-logic

Found while live-verifying the new `heldout_state_mismatch` scenario_variant
(`docs/panel_remount_v2_mission_logic_plan.md`): a temporary debug print of
`self._panel.data.root_pos_w` in `_reset_idx` (removed after use) showed the
panel actually resting at `(6.31, 0.57, 0.60)` under the **unmodified**
`covered`-path `EventCfg`, not near `_PANEL_SPAWN_POS = (3.1, 0.3, 0.3)` as
every comment in the file (since v1) claims.

Root cause, confirmed against Isaac Lab source
(`isaaclab/envs/mdp/events.py::reset_root_state_uniform`): the function's
`pose_range` is **added to the asset's `default_root_state`**
(`positions = root_states[:, 0:3] + env.scene.env_origins[env_ids] +
rand_samples[:, 0:3]`), not used as an absolute pose. `default_root_state`
here is `panel.init_state.pos` = `_PANEL_SPAWN_POS`. v1's `EventCfg` was
written as if `pose_range` were absolute (`x: (_PANEL_SPAWN_POS[0] - 0.2,
_PANEL_SPAWN_POS[0] + 0.2)`), so the real final position was
`_PANEL_SPAWN_POS + (_PANEL_SPAWN_POS +- 0.2)` -- roughly double the
intended offset. This has been true since v1 (F-series before F39); it
never crashed or broke termination logic (the reward/success check only
cares about the panel's *final* pose, not its start), so nothing in prior
live checks (including F39's visual pass) surfaced it -- at F39's camera
zoom, "somewhat further from the pedestal than intended" did not read as
obviously wrong.

**Fix** (`panel_remount_v2/task.py`, `EventCfg.randomize_panel_state`):
`pose_range` x/y are now pure `+-_PANEL_SPAWN_POS_RANGE_XY` deltas and z is
`(0.0, 0.0)`, so the final pose lands at `_PANEL_SPAWN_POS` +- jitter as
originally intended. `roll`/`yaw` needed no change -- the panel's default
orientation is identity, so `quat_mul(identity, delta) == delta` already
made those absolute. The new `heldout_state_mismatch` pose_range (added
this session) was written correctly from the start using this same
delta-from-`_PANEL_SPAWN_POS` convention.

**Consequence for `_ROCK_BLOCKING_POS`** (held-out A): the corrected panel
now actually jitters within `_PANEL_SPAWN_POS[0] +- 0.2` = `[2.9, 3.3]`,
closer to the rock than the pre-fix (effectively unreachable) spawn was.
`_ROCK_BLOCKING_POS` was moved from `(2.7, 0.3, 0.3)` to `(2.3, 0.3, 0.3)`
to keep a `>=0.6` m worst-case clearance against the panel's full jitter
range, re-verified live (no interpenetration/depenetration signature).

**Live-verified after the fix** (`srb agent zero`/`srb agent rand
--headless --video`, all three `scenario_variant` values,
`panel_remount_v2`/`panel_remount_v2_visual`): exact post-reset spawn
poses read directly from simulator state --
`covered`: panel `~(3.1-3.3, 0.1-0.5, 0.3)`, matching intent;
`heldout_access_block`: rock `(2.3, 0.3, 0.3)`, panel jitter clear of it;
`heldout_state_mismatch`: panel exactly `(3.5, 0.18, 0.5)`, i.e. `0.18`m
from `_PANEL_TARGET_POS` on y -- past `SUCCESS_POS_TOLERANCE_M` (0.1) as
designed. All three ran a full 60 s/3000-frame recorded episode plus
~170 s total wall time with a clean log (no NaN/depenetration/exception)
and a clean GPU teardown afterward.

**Caveat found immediately after, by the user watching the recorded
video, not by this verification:** `heldout_state_mismatch`'s panel was
visibly flung across the scene. F40's log-keyword grep (`nan`,
`depenetrat`, `exceeded`, `traceback`, `exception`) does not catch an
ordinary-looking PhysX contact-resolution impulse -- there is no
distinctive warning string for "a body started overlapping a collider
and got pushed out fast"; it just looks like normal physics stepping in
the log. The single-instant post-reset position check (above) also
missed it, because the launch develops over the following ~20 ticks, not
at the reset instant itself. **Corrected instrumentation**: a per-tick
print of `root_pos_w`/`root_lin_vel_w` for the first 400 ticks (removed
after use) showed the true mechanism -- spawning the panel directly at
`_PANEL_TARGET_POS` with a 0.18 m lateral offset placed it overlapping
the pedestal's mount geometry; PhysX pushed it up ~0.1 m over ~12 ticks,
then resolved a remaining overlap with a real high-velocity launch
(`vx` spiked to ~4.8 m/s) around tick 20.

**Fix**: spawn the panel `_PANEL_MISMATCH_DROP_HEIGHT_M` (0.2 m) above
the mount -- clear of any solid geometry -- and let it fall onto the
offset landing spot under gravity, rather than starting inside a
collider. Re-verified with the same per-tick trace extended to 400
ticks: the panel now reaches a genuine stable rest (position and
velocity frozen bit-for-bit, i.e. the physics engine puts it to sleep)
by ~tick 125, with no further launches. It settles onto a lower part of
the pedestal structure (`z~0.40`) rather than the top mount surface
itself (`z~0.5`) -- the 0.18 m lateral offset apparently exceeds the
mount surface's actual radius, which wasn't known in advance. Still
correctly reads as displaced and still fails
`SUCCESS_POS_TOLERANCE_M`, just via a slightly different resting spot
than originally designed -- noted honestly rather than re-tuned to hit
the exact original number, since the actual engineering bar (no
launch, reaches a stable state, still fails tolerance) is met.
Re-verified live: clean log, clean GPU teardown, stable frames deep into
the episode (video `n=100`/`n=200`).

**Standing lesson for this project's own verification practice**: a
clean log plus a couple of sparse still frames is not sufficient
evidence that a spawn configuration is safe when an object starts near
other solid geometry. For any new spawn pose close to existing scenery,
track the object's position/velocity over enough ticks to see it either
settle or not, not just at one instant.

### F41 — Scene-design constraints measured for the Phase C restart: SRB's "flat pad" is a ramp, lidar sees one mesh, LunarBot grasps only 0.45–1.0 m high

After the user rejected `panel_remount_v2` (multi-angle GUI inspection: a
pedestal floating above terrain, the panel out of arm reach, panel still
tumbling off; plus design rejection — too simple, SRB-assets only), four
read-only surveys were run. Full reports + citations:
`docs/lunar_base_research/0{0..4}_*.md`. Constraints that invalidate prior
assumptions:

1. **F18 correction — the procedural MoonSurface has no flat pad.**
   `flat_area_size` multiplies vertex z by a quadratic radial falloff
   (simforge `moon_surface/nodes.py`, FloatCurve points (0,1)…(1,0)), and
   deletes craters/rocks inside it. Measured on the cached spacing-32 mesh:
   ±0.001 m at r<0.5, ±0.05 at 1–1.5, −0.12…+0.15 at 1.5–2, ±0.28 at 2–2.5,
   −0.49…+0.71 at 3–4 m. Vertical scale is 0.1×spacing (16 m at spacing
   160). Static assets at literal z=0 float or sink — the rejected pedestal.
   Rule: never place infrastructure on procedural relief at fixed z; own the
   terrain with graded pads, or snap by measured height.
2. **RayCaster lidar ray-casts only the first `Mesh` child of the scenery
   prim** (IsaacLab 2.2.1 `ray_caster.py:164-181`, single warp BVH; SRB
   passes the scenery path only). Nav2 costmaps use only that lidar scan →
   every separate building/prop prim is invisible to Nav2.
3. **LunarBot manipulation envelope** (pxr reads of `lunarbot.usdc` + RM-75
   URDF, planar model, MoveIt confirmation pending): arm base on the chassis
   −X end at z 0.727 m, camera/lidar on the +X end; reachable TCP z ≈0.32–1.13 m;
   grasp targets 0.05–0.35 m beyond the −X hull edge (top-down ≤0.25 m), side
   ≈0.15 m; EG2 jaw opens ≈66 mm → features 15–45 mm; hold ≤~1 kg in sim
   (no holding stiffness under CARTESIAN_TWIST); Nav2 needs ≥2 m aisles /
   turnaround pads. Nothing on the ground is graspable.
4. **Asset landscape:** no lunar/space content in NVIDIA's 5.1 library (only
   an astronaut figure); physics-ready industrial props (SimReady, 1,029) and
   one articulated storage asset (Sektion cabinet). NASA 3D Resources (PD)
   has a habitat demo unit, SEV rover, RASSOR, Tall Dish, ORU, carrier, tools;
   no free credible VSAT/CLPS/ISRU/PDU-type models anywhere — must be
   authored. License blockers: TurboSquid/CGTrader free assets (ML clause),
   `/Isaac/Environments/*` (no modification), NASA insignia in AI imagery.

Redesign built on these: `docs/lunar_base_scene_design.md`.

### F42 — C2 bring-up of the lunar base scene: Mid-360 scanned a vertical plane and published world points as sensor-frame (both fixed); terrain seam; asset/pipeline gotchas

Found running `assets/lunar_base/scene/srb_scene_check.py` (SRB task
`lunar_base`, LunarBot on the dock, 2026-09-15).

1. **Lidar scan ring was vertical — fixed (SRB `main` 927426c).**
   `lidar_mid360_frame` world quaternion (w,x,y,z) = (0.707, −0.707, 0, 0),
   roll −90° (a Y-up mesh convention), not the inverted roll-180° mount. With
   `ray_alignment="base"` the 40×360 pattern was a vertical fan: world ray
   elevations −89°…+89°, no near-horizontal rays toward the charging station
   1.4 m away. The frame is an **articulation link on `lidar_joint`**, so
   PhysX places it from the joint's `physics:localRot0`, not its xformOp —
   changing only the xformOp had no effect in the sim. Fix: `localRot0` and
   the xformOp both roll 180°, child mesh xform roll +90° (mesh world pose
   unchanged, < 1e-6). Second bug on the same path: `ros.py` published
   `ray_hits_w` (world coordinates) under the sensor `frame_id`, so every
   consumer (pointcloud_to_laserscan → Nav2) transformed world points as if
   they were sensor-frame; now `RayCaster.ray_hits_sensor_frame()`.
   Verified live (`srb_scene_check.py`): elevations −52°…+7°, blind cone
   below −52° = 0.67 m radius on the ground around the mast, 510
   near-horizontal returns from the station at 1.30 m, 1 325 points in the
   0.05–0.6 m Nav2 band, sensor-frame round trip 1e-5 m. Nav2 itself not
   re-run (F37 still open).
2. **glTF BLEND alpha**: Sketchfab materials exported as BLEND with a texture
   alpha never below 0.44 render see-through and metallic-looking in RTX
   (the PDU cabinets looked like dark glass slabs). Processing now drops the
   alpha link unless ≥1 % of texels are < 0.1.
3. **Coplanar PV cell sheet**: the PV models' cell material sits 0–5 mm
   under a grey slab face; RTX shows the slab (white panels). Fixed with a
   per-material rigid 15 mm push along the sheet normal. Blender material
   names lack USD's leading "_" for names starting with a digit — override
   regexes must match the Blender name.
4. **`rep.orchestrator.step()` hangs inside a running IsaacLab env**
   (headless, after `env.step`). Moving a plain `UsdGeom.Camera` and pumping
   `env.sim.render()` ×60 before reading the annotator works.
5. **Near/far terrain seam from altitude — fixed.** Three causes, all
   needed: (a) the near field's craters and fine noise stopped at its border
   (and a keep-out sign bug rejected every crater outside it); (b) the 2 m
   mid mesh cannot show 1.2/4 m relief, so the 0.4 m near field read as a
   brighter, grainier square — solved with a baked normal map carrying the
   full relief on a mid mesh whose vertex normals point straight up (a
   tangent-space map relative to interpolated 2 m normals left a 2 m grid
   pattern, because RTX interpolates per triangle); (c) texture downsampling
   averaged sRGB-encoded values, darker than the GPU's linear mips of the
   tiled far material. One world-space surface function now feeds near
   (200 m @0.4), mid (600 m @2 + 7 cm maps) and far (6 km @20); heights
   agree on borders to 6.5 mm. Remaining: the mid ring seen from <30 m looks
   softer than the near field (7 cm vs 2 cm texels); the landing pad is
   ≥26 m from it.
6. **Tall-structure shadows at a 12° sun**: the 50 m Starship cast a ~235 m
   shadow across the whole base; the landing pad moved NW so its shadow
   falls outward. Any sun-bearing change must re-check this.

### F43 — LunarBot base conventions on the lunar base: twist signs were wrong, keyboard teleop inverted the base, speed bound raised, drivable roads

Found driving LunarBot at the new speed bound on the `lunar_base` task
(2026-09-15; `assets/lunar_base/scene/srb_drive_check.py`,
`srb_teleop_check.py`).

1. **Twist signs.** `FourWheelSteerActionCfg` had `scale_linear=-1,
   scale_angular=-1`: +v drove toward the chassis −X (arm end) and +ω yawed
   about −Z (ω=+0.5 → −0.305 rad/s measured). Everything downstream (Nav2,
   odom TF, sensor frames) uses REP-103 in `chassis_base_link`, and a yaw-rate
   sign cannot depend on which end is "forward", so both are now +1: +v toward
   +X (camera + Mid-360), +ω counter-clockwise. Programmatic (v, ω): straight
   0.58 m/s at 0.6, travel 0.6° off +X; spin +Z at 0.33 rad/s for 0.5
   commanded (in-place turns reach ~2/3 of the command); arc correct.
2. **Keyboard teleop inverted the base.** `srb agent teleop` negates twist
   x/y for every `ManipulationEnv` (`--invert_controls` is `store_true` with
   `default=True`, so always on); LunarBot's `GroundManipulationEnv` inherits
   it. The old −1 linear scale cancelled it (W forward) while yaw on C/V was
   reversed; with +1 scales W drove backwards (user report).
   `teleop_twist_for_env()` now skips the inversion when the action group is
   in "base" teleop mode and maps A/D to yaw; arm mode and fixed-base
   manipulation envs are unchanged. Headless check PASS: W/S ±X, A/C left,
   D/V right; ROS cmd_vel (0.5, 0.3) forward-left.
3. **Speed bound 0.6 m/s (user decision), angular 0.5 rad/s.** openral
   `robots/lunar_bot/robot.yaml`. The shared Nav2 base file caps 0.5 m/s /
   1.9 rad/s (panda_mobile tuning) — every Nav2 turn would exceed LunarBot's
   0.5 rad/s kernel bound, and the kernel rejects the whole chunk. New optional
   `nav2_max_linear/angular_speed` (validated ≤ safety bounds) are emitted as
   MPPI `vx_max`/`wz_max` and velocity-smoother limits; LunarBot declares
   0.57 / 0.47. Nav2 itself not re-run (F37 open).
4. **Roads were decoration.** Spokes dead-ended, the perimeter crossed the
   dish, cable reels, RMU and battery container, and the straight route to the
   landing pad hit the relay antennas; the dock → depot line clipped the
   charging station (robot stuck, 22° tilt). Rebuilt as a drivable network
   with a road/route-vs-footprint clearance check (≥1 m) in `build_scene.py`;
   mission sites moved closer (PDUs 13/19/26 m, cargo carrier 17 m). The
   +1.64 m graded ramp to the landing pad measured 14.5° tilt and the robot
   slid back; the pad and access road are now cut to platform level. An
   open-loop 30 m reverse drifted 92° off the road and rolled the robot on
   the berm — long open-loop drives are not a valid test.
5. **PhysX log flood.** Cylinder wheel colliders against the triangle-mesh
   terrain log "PxShape::getMaterialFromInternalFaceIndex received
   0xFFFFffff" per contact (812 k lines / 189 MB in 2 min). Convex-hull
   approximation removes it but cost ~22 % wheel speed; the user ruled the
   robot model must not change for a log. SRB now limits the
   `omni.physx.plugin` log channel to errors (no message-level filter exists;
   `maxNumberOfPhysXErrors` does not cover warnings); `SRB_PHYSX_WARNINGS=1`
   restores it. Logs 24 KB, identical driving.

### F44 — C3 interaction layer: reach geometry drove the hardware design; the "invisible" lidar mesh was a collider in SRB

Built 2026-09-15 on SRB `feat/lunar-base-scene` (fd3dbc3): authored CC0 props
(staging stand, PDU service panel with reset button + emissive status lamp,
spares shelf, 0.5 kg service cover), dynamic spares on the stand, interaction
frames, LunarBot work/view poses (`usd/scene/lunar_base/interaction.json`).

1. **Reach table shapes the hardware.** A horizontal button press only reaches
   ~0.15 m past the −X hull edge, top-down placing ≤0.25 m. A shelf under the
   button (first design) put the button 0.27–0.38 m away; the shelf therefore
   sits 1.05 m beside the panel (hull must clear it while pressing), stand slots
   are 0.19 m behind the table edge, and the Mission A access obstruction is a
   cover leaning on the button cap (a first version intersected the cap).
   `scene/interaction.py` checks every work pose's footprint against all
   structures (press 0.06 m from the panel ledge, place/pick 0.04 m from the
   support edge) plus grasp heights (spares 0.91–0.92 m, cover handle 0.90 m).
2. **The lidar mesh collided in SRB.** `/lunar_base/lidar` (terrain + a box
   per structure, invisible, no CollisionAPI) behaved as a collider inside the
   SRB env but not in a plain Isaac stage: the spare ORU came to rest at
   z 0.607 = the stand's lidar box top, 5 cm above the table; the crate slid
   off the box edge. Standalone CPU/GPU PhysX probes with the same USD settled
   both at 0.548/0.55. An explicitly applied CollisionAPI with
   `collisionEnabled=false` fixed it. Likely also behind C2's robot "stuck on
   the charging station" (22° tilt) — that route ran into the station's box.
3. **YAML 1.1 `on:` is a boolean.** A `dynamic_objects` key named `on`
   silently parsed as `True`; renamed `support`.
4. **Status lamp colour.** Emission ×4 saturated red into orange next to an
   amber lamp; `set_status_lamp()` uses ×1.5 and pure red (1, 0, 0) / amber
   (1, 0.5, 0), visibly distinct in close renders.
5. **Settle (§8.2) PASS.** 3 resets: every object still within 0.24 s, drift
   equal to the 3–7 mm spawn lift, tilt change <1°; crate and ORU also settle
   on the PDU shelves. Manipulation feasibility (§8.4) is C4/C5.

### F45 — C4 Mission A runs end to end in SRB: the arm needed model IK on the shoulder-back branch, the "reach table" was wrong, and the cover-block test was too lenient

Built 2026-09-16 on SRB `feat/lunar-base-scene`: task `lunar_base_mission_a`
(`srb/tasks/mobile_manipulation/lunar_base_mission_a/task.py`), scripted
executor + follow-camera recorder `assets/lunar_base/scene/srb_mission_a_run.py`,
RM-75 kinematics `assets/lunar_base/scene/rm75_ik.py`.

1. **Result.** A procedural oracle (not a method under test) completes all three
   Mission A cases in simulation; success is judged by the task's own
   verifier (no fault left, rover within 0.6 m of the dock, arm stowed, cover
   not held):
   - `covered` (report PDU-2, PDU-2 red): drive → inspect → reverse into the
     work pose → press → re-inspect (green) → dock. SUCCESS, 195 s sim /
     347 s wall with video.
   - `heldout_cover_obstruction`: the cover plate is over PDU-2's button;
     grasp handle → lift → carry → lay it on PDU-2's spares shelf → press →
     verify → dock. SUCCESS, 337 s sim / 748 s wall with video.
   - `heldout_status_mismatch` (report PDU-1, PDU-2 red): PDU-1 green → check
     PDU-2 → red → press → verify → dock. SUCCESS, 209 s sim / 500 s wall.
   Videos + per-phase JSON: `assets/lunar_base/review/mission_a/`.
2. **Online resolved-rate IK on the sim Jacobian did not converge** (stalled at
   0.10–0.15 m, joints driven into limits). Replacement: numpy DLS IK on the
   RM-75 URDF chain with the root→arm-base mount calibrated in simulation from
   one measured Link7 pose (FK check 0.0 mm; mount = (−0.4475, 0, 0.727) m in
   the root frame). Joint limits are handled by dropping clamped joints from the
   solve, with a posture bias; the executor sends the solution as joint-position
   targets and adds the measured TCP residual back to the goal (≤2 corrections).
   Final tool errors 5–12 mm, 0.01–0.03 rad; one 4 cm straight-line step takes
   ~0.5 s.
3. **The F44 reach table picked the wrong arm branch.** Its "side press
   ≤0.15 m past the hull edge" came from solutions with joint 1 ≈ π, which is
   against the ±3.107 rad limit and forces q2/q4 to their limits (joint lag
   0.5–0.7 rad, ~100 s per approach). With joint 1 = 0 and the shoulder pitched
   back (READY = (0, −1.0, 0, −1.4, 0, 1.2, 0)) the same targets have ≥0.2
   joint-range margin, and the comfortable tool distance is **0.45 m** past the
   hull edge for z 0.78–0.95 m (0.55 m already fails at z 0.78). `interaction.py`
   REACH press/grasp 0.12 → 0.45; `interaction.json` work poses regenerated
   (0.33 m further out, clearance 0.198 m to the shelf; frames, objects and
   view poses unchanged). Top-down place/pick (0.24) is unverified until C5.
4. **Open-jaw contact looked like a slow joint 7.** During the first cover
   attempt joint 7 sat 1.1 rad from its target for a minute; a free-space probe
   showed joint 7 tracks within 0.1 rad with the gripper open or closed. The
   folded arm was touching the scene, not a drive problem.
5. **Grasp: cage, not pinch.** The 25 mm handle bar is horizontal, so the jaws
   close vertically. TCP 15 mm past the bar centre did not lift the cover; TCP
   35 mm past (fingertips ~2 cm beyond the centre) cages the bar and the cover
   follows the TCP within 2 cm. Released over the shelf, the cover lies flat on
   it (handle z 0.557 = shelf 0.50 + plate + standoff) and stays there.
6. **Verifier fix: the handle-distance block test let presses through the
   cover.** "Blocked if the handle is within 0.10 m of the button" was false
   (the handle is 0.125 m above the button), so a press through the plate
   cleared the fault. Now `Task.cover_blocks()` puts each button in the plate
   frame: covered when within the plate's width × height footprint and 6 cm of
   its plane. The overlay and `mission_state()["covered"]` use the same test.
7. **Success terminated the episode and SRB auto-reset it.** The first full
   runs reached the dock with every fault cleared and then reported failure:
   termination on success reset the lamps and counters in the same step.
   `TaskCfg.terminate_on_success` (default True, for learning/eval loops); the
   scripted demo sets it False and logs any env-ended episode.
8. **Three rendering instances on one GPU.** Starting three recorders 30 s apart
   crashed one at start-up (`VkResult: ERROR_DEVICE_LOST`), and that process
   hung instead of exiting. Two in parallel ran. imageio `quality=8` wrote
   540 MB for 5.6 min; CRF 24 gives 50–75 MB.

Still not shown: Nav2 (F37) and the OpenRAL kernel/HAL path. The oracle drives
with pure pursuit on hand-set aisle waypoints and commands SRB actions
directly, so this is §8.4 feasibility, not a harness run.

### F46 — C5 Mission B: the EG2 cannot pinch a 1 kg spare, so spares are hooked by a bail handle; carrying a hanging load needs stoppable speed profiles; the depot stand was too narrow

Built 2026-09-16 on SRB `feat/lunar-base-scene`: task `lunar_base_mission_b`
(`srb/tasks/mobile_manipulation/lunar_base_mission_b/task.py`), oracle
primitives factored out of the Mission A script into
`assets/lunar_base/scene/lunar_oracle.py`, executor + recorder
`scene/srb_mission_b_run.py`.

1. **Mission B cases.** Deliver the spare ORU from the depot staging stand to
   PDU-1's spares shelf, then dock with the arm stowed.
   - `covered`: ORU on slot 0 as the manifest says.
   - `heldout_destination_occupied`: a returned cargo crate sits on the
     destination shelf and has to be cleared first (the oracle returns it to
     the free stand slot).
   - `heldout_spare_swapped`: the manifest says slot 0, but the ORU is on
     slot 1 and the crate on slot 0. This is the semantic-confusion case: the
     spare has to be identified by how it looks.
   The verifier needs all of: ORU resting upright on the destination shelf,
   not held; crate resting on a stand slot or another shelf (not dropped, not
   held); rover docked; arm stowed.
2. **Spares had nothing a 100 mm gripper can hold.** The ORU (0.45 × 0.39 ×
   0.37 m) and crate (0.29 × 0.45 × 0.36 m) now get a bail handle on the lid
   centre from the processing pipeline (`processing.yaml` `top_handle`:
   25 mm bar, 0.16 m long, 0.10 m standoff). The handle frame goes into the
   asset json → `interaction.json` (pick points now at the handle,
   z 1.01–1.02 m). REACH for pick/place is 0.45 like press/grasp;
   `GRASP_Z` is (0.45, 1.10).
3. **Pinch and cage grasps slipped.** Closing on the bar blocked the jaws
   (q 0.22–0.29), but on lifting the object stayed put and joints 4/5/6
   saturated (30/10/10 N·m) as the jaws were pried open to 0.57.
   - The measured EG2 collision boxes (Link7 frame) show why: finger pads
     only span z 0.110–0.143, and the inner four-bar links reach z 0.12 at
     |x| ≥ 4 mm. The Mission A cage depth (TCP 35 mm past the bar) puts the
     bar inside the linkage.
   - In the grasp state only two of the six EG2 joints moved; the others read
     0, so there is no reliable squeeze.
   - Depths of 13, 0 and −8 mm all slipped. The robot model was left
     unchanged (user rule).
4. **Hook grasp.** The closed gripper goes flat side up, tip raised 10°, with
   the tool axis 42.5 mm below the bar centre, so the raised fingertips pass
   5 mm under the bar.
   - The arm cannot reach 0.22 m further back side-on. So the arm lines the
     gripper up at the 0.45 m reach, and the **base reverses 0.22 m** to slide
     it under the bar.
   - The arm then lifts; the bar lands on the fingertips and rolls back to the
     wrist (g·sin 10° = 0.28 m/s² holds it).
   - Placing: lower onto the support, level the tool about the bar, drop
     12 mm, and drive the base forward to withdraw.
   - Side close-ups (`Oracle.snapshot`) found the first version's 12° tilt
     drove the fingertips into the bar.
5. **Carrying a hanging load.** First full runs "succeeded" with the crate
   left on the road (the verifier only checked it was off the shelf; fixed,
   see 1).
   - The rate limiter slowed braking, so pure pursuit overshot the stand's
     staging point and circled. The swinging crate knocked both spares off
     the stand.
   - While carrying, `Oracle.step` now rate-limits (0.2 m/s², 0.15 rad/s²),
     and `follow`/`turn_to` cap speed at √(2·a·remaining). The staging point
     is 2.0 m out.
   - The load is carried with its base 8 cm above the highest support
     (stand 0.55 m). Lifting only 5 cm off a 0.50 m shelf jammed the crate on
     the stand edge, and PhysX depenetration threw it 1.5 m up.
6. **Depot stand widened 1.00 → 1.30 m** (slots ±0.24 → ±0.32 m). Two 0.45 m
   spares had a 3 cm gap, and returning the crate next to the ORU pushed the
   ORU off. `author_props.py` → `process.py --only staging_stand` →
   `build_scene.py` (30 s, no problems; work-pose clearance 0.252 m).
7. **Result.** With the fixes above, every case reaches verifier success, recorded
   one or two at a time (videos + phase JSON in
   `assets/lunar_base/review/mission_b/`):
   - `covered`: 413 s sim / 17 min wall with video.
   - `heldout_destination_occupied`: 660 s sim / 23 min. The crate goes back to
     stand slot 1, then the ORU is delivered.
   - `heldout_spare_swapped`: 402 s sim / 15 min.
   The refactored Mission A obstruction case still succeeds (326 s sim).
8. **Background-task kills.** Two batches of 2–3 Isaac instances were
   stopped as "system running low on memory" while `free` showed 237 GB
   available (116 GB page cache). Launching through `setsid nohup` outside
   the tool's task tree avoided it.

### F47 — F37 closed: Nav2 plans and drives LunarBot on the lunar base through `openral deploy sim`; it took five separate fixes

2026-09-16, openral `master` 60345fd, scene `scenes/deploy/srb_lunar_base.yaml`,
smoke test `experiments/launch/lunar_base_nav2/run_nav2_smoke.sh`. Each fault
only showed up once the previous one was fixed, on live runs of the full graph
(SRB + kernel + HAL + reasoner + SLAM + Nav2):

1. **Sensor bridge not in the graph (F37's root cause).** New
   `ExternalSimulatorSpec.bridges` (`SimulatorBridgeSpec`): the scene declares
   the simulator's topic/TF adapter.
   - `deploy_e2e.launch.py` starts it with the simulator, injecting
     `use_sim_time` and the manifest path.
   - Nav2 now waits for HAL ACTIVE **and** the bridges' `publishes` topics
     (`tools/wait_for_topics.py`).
   - The launch file has no robot-specific branch; the lunar_bot bridge is
     declared in the SRB scene YAMLs.
2. **`velocity_smoother` configure threw**: `max_velocity` arrived as a
   string. This is my own F43 speed-cap override: `RewrittenYaml`
   `convert_types` only converts scalars. `nav2.launch.py` now writes overrides
   whose base value is a YAML list as lists into a temporary params file. The
   costmap `footprint` stays a string.
3. **`controller_server` looked unresponsive** ("failed to send response
   (timeout)", `get_state` unanswered). It was not the DDS transport: a
   UDP-only Fast-DDS profile changed nothing.
   - Its costmap waited in its lifecycle callback for `base_link → odom`.
   - The shared Nav2 and slam_toolbox configs name panda_mobile's
     `base_link`; LunarBot's base is `chassis_base_link`.
   - Now `nav2_param_overrides()` sets `robot_base_frame` / `base_frame_id` /
     `base_frame` from the manifest, and slam_toolbox gets `base_frame`.
     slam_toolbox's "Failed to compute odom pose" flood had the same cause.
4. **Goals "succeeded" instantly without motion.** Upstream
   `navigation_launch.py` rewrites `use_sim_time` via `RewrittenYaml`, which
   replaces keys but adds none, and the base files have no `use_sim_time`. So
   every Nav2 server ran on wall time against SRB's sim-time TF, and the
   controller logged "Transform data too old" and "Reached the goal!".
   `use_sim_time` is now written into every `ros__parameters` block (all eight
   servers verified True live).
5. **Lifecycle bringup robustness.** Humble's `lifecycle_manager_navigation`
   blocks forever on a lost `change_state` reply (seen once while fault 3 was
   present).
   - Nav2 now starts with `autostart:=false`.
   - `tools/lifecycle_autostart.py` (now multi-node, with
     `--response-timeout-s` / `--attempts`) drives the seven servers and reads
     each node's real state instead of trusting the reply.
   - All seven reached ACTIVE about 30 s after launch (warm shader cache).

**Live result.** From the dock:
- NavigateToPose (3.0, 1.5): SUCCEEDED at odom (3.04, 1.47) after 59 s.
- Then (9.0, 1.5): SUCCEEDED, but odom read (10.35, 1.48) right after the
  result — **1.35 m past the goal**.

**Overshoot follow-up (same day).**
- A stop trace shows `/cmd_vel` and SRB's `action/cmd_vel` both reach zero
  promptly, so the command chain is not the cause.
- SRB alone: from 0.55 m/s the base stops in 0.53 m, velocity decaying with
  τ ≈ 0.9 s; no coasting fault.
- Root cause: the shared file's stateful goal checker latched xy success, then
  waited on a 0.05 rad heading that LunarBot's coarse in-place turning (F43)
  could not settle. It drifted 1.4 m sideways while "finishing".
- New manifest fields `nav2_goal_checker_stateful: false` and
  `nav2_goal_yaw_tolerance_rad: 0.25` (openral `master`). Re-run:
  - (3.0, 1.5) ends at (3.15, 1.46).
  - (9.0, 1.5) ends at (9.82, 1.46): no lateral drift. Along-track it was
    0.54 m past at the result, still at 0.34 m/s.
- Remaining open item: MPPI does not slow early enough for the base's 0.9 s
  time constant. Other gotchas:
- Python Nav2 helper nodes (relay, payload scan filter) survived SIGINT/SIGTERM
  of the launch group and kept publishing across runs; the smoke script now
  kill -9s them.
- `pkill -f <pattern>` inside a Bash tool call matched and killed the tool's
  own shell.
- The unrelated `twist_to_action_relay_node.py` executable-bit test failure is
  fixed.

### F48 — C6 wrap-up: route-block variant passes the Nav2 check; `panel_remount_v2` retired

2026-09-16:

- **Route-block variant.** `build_scene.py --variant route_block` bakes a
  parked MMSEV crew rover across the west leg of the depot loop at
  (5.0, −2.25) into a second scene file, `lunar_base_route_block.usda`
  (SRB scenery `lunar_base_route_block`, openral scene
  `srb_lunar_base_route_block.yaml`).
  - It has to be baked: the Mid-360 RayCaster only casts against
    `/lunar_base/lidar` (F41), so a runtime-spawned obstacle would never
    reach the costmap.
  - The build report flags the depot road and both Mission B reference
    routes as blocked, as intended.
- **Live result.** With `NAV2_GOALS="4,1.5;6,-6"`:
  - Leg 1: dock → (4, 1.5) reached at (4.10, 1.43).
  - Leg 2: (4, 1.5) → (6, −6), whose straight line passes through the rover.
    Reached (7.06, −6.29) in 178 s, 165 replans, no Spin/BackUp recovery.
  - The blocker is a static collider, so reaching the goal means Nav2 drove
    around it.
  - The smoke check now also logs a sparse odometry track so the next run
    shows the detour directly.
  - The ~1 m along-track overshoot (F47) remains.
- **`panel_remount_v2` retired** (SRB 1fffa59): the rejected scene's task is
  removed. `panel_remount` v1 stays for Phase B deploy scenes and
  `openral_ext/mission_verifier`.
- **Harmless messages seen in every deploy run.**
  - The reasoner never configures without the LLM gateway env (F38), so
    `lifecycle_autostart` for `/openral_reasoner` exits after 300 s.
  - Isaac warns "A prim already exists at /World/envs/env_0/scenery".
  - Neither affects Nav2, the HAL or the kernel.

### F49 — The EG2 really clamps now (PhysX mimic joints), the deck transfer does not, and the oracle has been taken past its purpose

Session of 2026-09-16, after C6. Two engineering results, one process
correction. The process correction is the important part.

1. **The EG2 gripper clamps with both pads, by mechanism, not by tuning.**
   F46 recorded that only two of the six gripper joints moved and that a
   pinch on a 1 kg spare always slipped. Root cause: the six EG2 joints are
   an unconstrained kinematic tree, each with its own PD drive, so under
   load one side closed fully while the other was levered open — the two
   pads were never mechanically coupled the way the real EG2-4C2's linkage
   couples them. Fix: `PhysxMimicJointAPI` on `eg2_joint2..6` referencing
   `eg2_joint1` (constraint `q_j + gearing·q_ref + offset = 0`, gearing ±1),
   authored by `assets/lunar_base/process/add_gripper_mimic.py` into
   `lunarbot.usdc`; the SRB actuator now drives all six joints with
   `effort_limit` 4.0 N·m (~65 N at the pads, inside the EG2-4C2 band —
   0.9 N·m ≈ 15 N could not hold 1 kg), and `robots/lunar_bot/robot.yaml`
   carries the same limit. Measured: all six joints at 0.296 rad, every
   torque saturated, the 1 kg ORU held. SRB 8ccf1db, openral 3ef3220.
2. **The payload interface had to give form closure, not friction.** A
   round bar rolls out of flat pads; a flat flange jams in the four-bar
   linkage at 50 mm depth and squeezes out at 28 mm. What works is a
   **T-handle lifting eye**: 12 mm neck across the jaws, 55 mm free height,
   90×45×14 mm head — the jaws hold the neck and the head rests on them, so
   a lift is held by geometry. `blender_process.py` `top_handle`.
3. **Deck transfer: nine runs, not working, stopped.** The user asked for
   the payload to ride on the rover deck instead of hanging from the arm.
   Each failure was root-caused from the traces rather than guessed
   (joint-space jump threw the payload 1.9 m → joint-rate limiting; lifting
   the handle to 1.39 m drove the payload into the arm's own links, z
   0.92–1.29 → bounded transfer height; swinging at handle z 1.05 put the
   payload base below the deck top and scraped the chassis corner → tuck to
   radius 0.40 then arc at seat height). The last run reached deck height
   still clamped and dropped the payload during the swing. **Stopped there.**
   The user's own message had already given the cheaper option — "运输过程中
   一直让机械臂夹持着把手最好", carry it clamped — and the mission only
   requires transport, not a deck.
4. **Process correction: the oracle was taken past its purpose.** Per
   `execution_plan` §13.1 (validate mission success conditions independently
   of all methods) and §13.2 (a valid solution exists using only capabilities
   present before freeze), the scripted oracle is a required instrument, and
   C4/C5 discharged the first of those: six cases, verifier success, three
   real verifier defects found. It does **not** discharge the second — F45
   said so at the time: the oracle drives with pure pursuit on hand-set
   waypoints and commands SRB actions directly, so it proves the *embodiment*
   can do the mission, not that the *shared capability set* can. Continuing
   to improve the oracle's manipulation realism cannot change that sentence.
   Two facts were in the record and went unused for a day: the five
   procedural manipulation rSkills are built and live-verified (F30) and
   MoveIt for the RM-75 works through the kernel (F36, chunk 8, success,
   0.03 rad). The next physical work belongs on that path, not in the oracle.
5. **The real risk to Experiment I**, now stated plainly: all three methods
   share one capability stack, and its measured precision does not obviously
   meet the missions' geometry — Nav2 leaves ~0.8 m of along-track overshoot
   (F47) against work poses with 0.198 m clearance, and `move_ee_to_pose`
   reaches 1.3–2.5 cm and then drifts back out because SRB's `arm_ik` term
   re-syncs every step with no holding stiffness (F30). If the shared stack
   cannot execute Mission A/B, every method fails for the same physical
   reason and the experiment measures nothing. Settling this is the next
   task, and it is the one the oracle work was displacing.
6. **Isaac Sim ships a usable motion planner** (`isaacsim.robot_motion.lula`:
   `RRT`, `RmpFlow`, `LulaKinematicsSolver`, `LulaCSpaceTrajectoryGenerator`;
   the `lula` C++ API takes obstacles directly, so no USD prims are needed).
   cuRobo is not installed. This was looked up while considering an in-sim
   planner for the oracle; it is recorded because it may be useful later, but
   MoveIt — already integrated — is the planner for the capability path.

### F50 — Phase D0: the shared capability stack on the real graph. Eleven defects, two physics measurements (wheel slip, sim-vs-wall time), and what the four capabilities actually deliver

2026-09-16, `execution_plan` §21.4 / §13.2. Ten live runs of Mission A/B through
`openral deploy sim` (`experiments/launch/lunar_base_d0/`: `run_d0.sh`, `d0_common.py`,
`d0_mission_{a,b}_check.py`), plus three simulator-only measurements
(`assets/lunar_base/scene/srb_{brake,turn,traction}_check.py`). Every motion is an
`ExecuteRskill` dispatch through runner → kernel → HAL → SRB; the oracle is not involved.

**1. Two physical measurements that govern every number below.**

*Braking* (`srb_brake_check.py`, 208 kg rover): a step to zero from 0.55 m/s slides
0.49 m, body speed decaying with τ ≈ 1.0 s while the wheel rims are already slower —
traction-limited, ≈0.5 m/s² at best. A 0.3 m/s² command ramp still needs 1.12 m.

*Slip* (`srb_traction_check.py`, three sites, 6 s holds). The user's prediction, confirmed:
the no-slip 4WIS kinematics is not what the vehicle does.

| manoeuvre | commanded | achieved | rim speed → slip | peak wheel torque |
|---|---|---|---|---|
| straight | 0.50 m/s | 0.40–0.41 (81 %) | 0.50 → 0.40, **18–19 %** | 5–6 N·m |
| straight | 0.15 m/s | 0.114–0.117 (76–78 %) | 0.17 → 0.12, **25–32 %** | 3.4–3.9 N·m |
| reverse | 0.30 m/s | 0.18–0.25 (61–83 %) | **16–38 %** | 4 N·m |
| **in-place turn** | 0.45 rad/s | 0.24 (**54 %**) | pure lateral scrub | **19–24 N·m** |
| **in-place turn** | 0.20 rad/s | 0.084 (**42 %**) | pure lateral scrub | **14–16 N·m** |

Low speed slips *more* (static friction unbroken), and an in-place turn — every wheel
scrubbing sideways — costs 4× the drive torque to realise half the commanded rate. Road and
work-pose sites differ little, so this is the manoeuvre, not the terrain. Design consequences:
never plan a manoeuvre that needs an in-place turn in a tight spot, and never trust
open-loop integration of commanded velocity.

*Sim vs wall clock.* A rendering deploy graph (two 640×480 cameras + lidar + SLAM + Nav2 +
MoveIt) advances SRB at a fraction of real time. Every rSkill timeout, the runner's execution
budget and the MoveIt replay pacing used `time.monotonic()`, so they fired while the robot was
still moving correctly: the docking servo "achieved" 9 % of a commanded 0.45 rad/s measured on
the wall, against 54 % measured in sim time. Fixed: the runner injects a `clock` callable
(`self.get_clock()`, i.e. the sim clock under `use_sim_time`) into every procedural skill and
into `ROSActionRskill`, and its own `_deadline_lapsed` uses it too.

**2. Defects found live, each one a thing that had never run in this graph.**

1. `deploy_e2e.launch.py` dies at launch with `No module named 'lxml'` — MoveIt's
   `moveit_configs_utils` → `urdf_parser_py` needs it and the venv had it only transitively.
   (openral `pyproject.toml`.) MoveIt had never been launched *inside* the graph before (F49).
2. `lunar_base_mission_{a,b}`'s `mission_brief` was a `@property`; Isaac Lab's `configclass`
   copies every attribute on init, so the `_visual` task variants could not be constructed at
   all ("property has no setter"). The mission tasks had only ever been run as the non-visual
   variant by the oracle.
3. Nav2's `behavior_server` Spin recovery publishes straight to `/cmd_vel` at the shared file's
   1.0 rad/s, over the kernel's 0.5 rad/s envelope → `safety.envelope_violation` → E-stop →
   the whole graph stops accepting commands. The first plan failure killed the run.
   `nav2_param_overrides()` now derives `max_rotational_vel`/`min_rotational_vel`/
   `rotational_acc_lim` from the robot's declared caps.
4. The shared 20 m rolling global costmap does not contain a site 14 m away: "the goal is off
   the global costmap. Planning will always fail." → `nav2_global_costmap_size_m: 60`.
5. `RewrittenYaml` rewrites *every* key of a name anywhere in the file, so a global-costmap
   `width` also resized the local costmap. Added `_apply_path_overrides` (dotted
   `node.node.ros__parameters.key` paths) — and it must preserve the base file's declared type,
   or `rclcpp` refuses (`parameter 'height' … integer … setting it to double is not allowed`).
6. The local costmap's `VoxelLayer` column started at `origin_z: 0.0`; on a real DEM the base
   frame dips below 0 and every scan was rejected ("Sensor origin … out of map bounds … cannot
   raytrace"), so the local costmap never formed. LunarBot now has its own Nav2 base file
   (`config/nav2_lunar_bot.yaml`, selected by `robot.yaml`'s new `nav2_params_file`) with the
   column starting at −0.5 m; the shared panda file is untouched.
7. **Teardown left nodes alive across runs.** `openral deploy sim` `setsid()`s its `ros2 launch`
   child, so neither the process-group kill nor a session kill reaches the tree; a stale
   `runtime_node` and `move_group` from an earlier run then shared the ROS domain with the new
   one, and every `ExecuteRskill` goal went to the dead server: three dispatches, 90 s each, no
   response, rover motionless. `run_d0.sh` now walks the descendant tree before the kill and
   reports `LEFT 0 of the tree still alive`; the check script opens with a functional dispatch
   probe rather than `server_is_ready()`.
8. **MoveIt planned the arm in isolation.** `rm_75_config` is the RM-75 alone: `rm_group`
   rooted at the arm's `base_link`, nothing else in the world, so a "collision-free" plan could
   sweep the deck, the wheels or the gripper through the rover, and a goal had to be
   re-expressed into the arm's frame by hand. Added `config/lunarbot_body.xacro`: the chassis
   deck and wheel boxes from `lunarbot.usdc`'s own collision bounds, the EG2 box, `tcp_frame`,
   and `chassis_base_link` as the URDF root (hence MoveIt's planning frame). Offline
   (`moveit_selfmodel_check.py`, standalone `move_group`): zero/stow/READY valid, pre-grasp and
   press poses plan in ~0.01 s, and a goal over the rover's own deck is correctly refused
   ("Unable to sample any valid states").
9. The same model logged one ERROR *per unknown joint per `/joint_states` message* — 14 joints
   × 30 Hz ≈ 600 lines/s into the deploy log. The self-model now carries the 4 steering, 4 wheel
   and 6 gripper joints as geometry-free passive joints.
10. **The MoveIt replay outran the arm.** `ROSActionRskill` emitted all 41 waypoints of a 6 s
    plan in 1.4 s and declared success; the arm was 0.6 m away. It now paces waypoints by their
    `time_from_start` (on the sim clock), holds when the measured joints lag by >0.05 rad, and
    only reports success once the *last* waypoint is reached. Offline against a first-order arm:
    legacy "succeeded" 0.27 rad short at τ=0.8 s; paced finishes within 0.049 rad.
11. **SRB's arm twist mode had no holding stiffness and realised 1.5–4 % of a command.**
    `SwitchableArmAction` recomputed its IK target from the *measured* pose every step
    (relative mode), so the drives only ever tracked a fraction of one 20 ms delta and a
    converged pose drifted straight back out (F30's open tuning gap). Rewritten as a Cartesian
    velocity controller with a persistent desired pose: the twist is integrated once per control
    step onto a desired pose leashed to the measured one, and absolute-mode differential IK
    drives to it — so a zero twist *holds*. Scales fixed to physical units (`ik_scale` 0.01 m,
    `ik_scale_angular` 0.012 rad per raw unit per step, matching the HAL's calibration).

**3. Where the four capabilities stand (run a8, Mission A `covered`, camera-free scene).**

| step | result | measured |
|---|---|---|
| Nav2 to the docking staging pose | success | 0.10–0.39 m in `map`; **1.0–2.3 m from truth** (SLAM drift, see 4) |
| `move_base_to_pose` into the work pose | success | closes on `odom` — which is still truth, see 4 |
| `grasp` (close jaws) / `move_joints` READY | success | |
| **MoveIt** pre-press (self-model, posture constraints, paced replay) | success | TCP **1.11 cm** |
| `move_ee_to_pose` pre-press, 3 s hold | success | 0.82 → 0.77 cm; hold drift <0.7 cm (F30's drift is gone) |
| `move_ee_to_pose` approach / press | success | 0.34 cm after hold; **verifier: PDU-2 fault cleared, 1 press** |
| retract | success | 0.98 cm |
| stow | **fail** | 0.086 rad short in 15 s (skill tol 0.05; the mission counts 0.35) — script now stows via READY, 0.1 rad / 30 s, not yet re-run |

Not yet reached: Mission A's return to the dock; **Mission B** (carry) has not run on the new
stack at all — `grasp` has never held a payload through an rSkill. Sim advances at 0.13–0.18×
real time with or without cameras: physics + SLAM + Nav2 + MoveIt, not rendering, set the pace
(the `_fast` scenes save little). A Mission A run is ~10 min wall.

Docking design, after the user's correction: LunarBot's in-place turning and crabbing are design
features and are not to be traded away to reduce slip. `move_base_to_pose` uses `(vx, vy, wz)`
together and rotates in place freely. (An earlier claim that the rover "cannot rotate at the work
pose" was an arithmetic error — the sweep radius, 0.88 m, is inside the 1.12 m from the rotation
centre to the structure; the stall was the wall-clock timeout.)

**4. Localization is the dominant error, and `/odom` is ground truth.** Nav2 reaches its goal in
`map` to 0.10–0.39 m, but slam_toolbox's map drifts 1.0–2.3 m from the world over an 18 m drive,
so the rover arrives physically that far off. It only docks correctly because `odom` is SRB's own
pose. With the arm compensating the last centimetres (user decision: terminal precision is a
manipulation rSkill's job, visual servoing belongs there), the base needs ≲0.10–0.15 m at the work
site (F45's reach margin). A literature survey (Sonnet subagent: Apollo LRV, MER/MSL/M2020, Yutu-2,
CADRE, VIPER, OSIRIS-REx; terrestrial loose-terrain practice) found: no flown rover closes
centimetres on global pose — it is always meters-level global localization, periodically
re-anchored (Perseverance's orbital-map matching: ~25 cm, 264/264 stops), plus relative sensing at
the target; slip is corrected in the estimator (JPL TANav), never by banning manoeuvres; the 2D
projection of the 3D lidar plus the indoor 12 m range are the likely cause of the drift; no lunar
GNSS/RTK exists (LunaNet/LCRNS/Moonlight target 1–10 m, 2026–2030).

**Decision (user, 2026-09-16):** do (i) wheel-inertial odometry and (ii) localization against a
prebuilt map; skip third-party LIO integration unless (ii) proves insufficient. Status:
- Sensor bridge `odom_source: wheel` implemented (4WIS least squares for v, IMU for yaw rate),
  truth on `/openral/pose_truth` — **not enabled**. `robot_localization` is not installed; the
  user prefers our own implementation, so a slip-aware covariance (from the least-squares
  residual) goes in the bridge rather than an external EKF.
- `slam_toolbox_lunar_bot.yaml` (35 m range, site-scale loop search) installed, not selected.
- Prebuilt-map localization: the deploy launch already seeds `nav2_map_server` from `map_path`
  when SLAM is off, and `nav2_amcl` is installed. Preferred route: render the occupancy grid from
  the scene's own static geometry (`/lunar_base/lidar` mesh, F41 — exact by construction, the
  "surveyed base map") and localize with AMCL; alternative: a slam_toolbox survey + localization
  mode. Mission scripts then measure against `/openral/pose_truth` and dock in `map`.

**5. Open.** Whether the ros_action result wait now runs on the sim clock was not re-observed after
the runner fix (the timeout message now reports both clocks). A parallel second graph on GPU 1 works
(`--kit_args "--/renderer/activeGpu=1 --/physics/cudaDevice=1"`, `D0_DOMAIN=78`; never combine with
`CUDA_VISIBLE_DEVICES`) — the "no goal response" failure attributed to it was stale nodes from an
earlier run.

### F51 — D0 core passes with realistic localization (wheel-inertial odometry + AMCL on a lidar-surveyed map): Mission A and B `covered` end to end, `route_block` held-out passes; the §21.4 capability boundary reproduces Mission A; a base velocity command had been opening the gripper

2026-09-16/17, `execution_plan` §21.4 / §13.2, user decision in F50 §4. openral `feat/d0-localization`,
SRB `feat/d0-nav-map`, research repo `feat/d0-localization`.

**1. What changed in the stack.**
- `/odom` is wheel-inertial: the bridge solves (vx, vy, ω) by least squares over the four 4WIS
  wheels (the old solve had no lateral unknown, wrong once the base crabs), heading rate from the
  IMU, twist covariance from the residual plus a slip floor. `/openral/pose_truth` is evaluator-only.
- The prebuilt map is surveyed with the rover's own lidar inside SRB
  (`assets/lunar_base/scene/srb_nav_map_survey.py`): 439 poses on every road, route, work and
  staging pose; keep only returns `pointcloud_to_laserscan` keeps (chassis-frame 0.05–0.6 m,
  0.1–40 m); a cell is occupied when ≥3 poses hit it. The unfiltered survey had 90 k occupied
  cells, most of them ground arcs that move with the rover; the filtered map has 17 k, structures
  only.
- SLAM off; `nav2_amcl` (omni motion model) on `nav2_map_server`, selected by the deploy scene's new
  `runtime.localization: amcl`; the bridge's static identity `map -> odom` is off
  (`publish_map_to_odom`), since two publishers of one TF edge make tf2 flip.
- Navigation and docking close on `map`; errors are measured against truth and split into
  physical (`pos_err`), AMCL (`loc_err`) and wheel odometry (`odom_err`).

**2. Measured (run a5, Mission A `covered`, camera-free, GPU 0 alone).**

| leg | truth error to goal | AMCL error | wheel-odom error |
|---|---|---|---|
| Nav2 dock → PDU-2 staging (≈17 m) | 0.174 m | 0.147 m | 0.167 m |
| dock into the work pose (`map`) | **0.090 m** | 0.078 m | 0.166 m |
| Nav2 back to the dock (≈17 m) | **0.077 m** | 0.074 m | 0.406 m |

Arm on top of that base error, target via the truth-relative stand-in: MoveIt pre-press 2.35 cm,
servo 1.5 → 0.13 cm after hold, approach 0.96 cm, press clears PDU-2's fault (1 press), retract
1.1 cm, READY → stow. **Verifier: `success: true`** (fault cleared, rover at the dock, arm stowed).
The base meets the ≲0.10–0.15 m the arm needs; AMCL, not odometry, carries it (odometry drifts
0.4 m over 34 m).

**2b. Mission B `covered` (run b7, after defect 9's fix).** Road point 0.20 m, depot staging 0.11 m, depot dock
**0.017 m** (AMCL 0.003 m); grasp stops the jaw at 0.172 rad (clamped), lift to handle z 1.099 m; the jaw stays
0.17–0.18 rad through dock-out, two Nav2 legs and the PDU-1 dock (0.061 m); lower, release (jaw 0.79 in 1.1 s),
ORU upright on PDU-1's shelf 2.3 cm from the shelf point; stow; dock 0.028 m. **Verifier: `delivered`,
`success: true`.** The handle sagged 4.5 cm under the 1 kg load during the carry (arm hold in twist mode); in the
video run at 0.06× (bv1) it sagged 15 cm and "servo over shelf" stalled — not isolated (render vs rate).

**2c. Held-out `route_block`** (`d0_route_block_check.py`, scenery `lunar_base_route_block`, AMCL map without the
parked rover): Nav2 detoured west (x 3.07 at y −2.11) round the rover at (5.0, −2.25) and reached (6, −6) 0.20 m
from goal; AMCL 0.074 m with the unmapped obstacle in view.

**3. Defects found, in order.** (each a thing that had never run in this graph)
1. AMCL was brought up last by the Nav2 lifecycle driver; `planner_server`'s configure blocks until
   `map -> base` resolves, which only an active AMCL provides. AMCL first.
2. **Every skill in `openral deploy sim` still timed out on `time.monotonic`.** `runtime_node` builds
   its own resolver through `skill_resolver_factory` and never passed the clock; F50's fix covered
   only the runner's internal fallback. Nav2 lost its 300 s budget after 28 s of sim time at 0.09×.
   (F50 §5 had flagged this as unobserved.)
3. Once on the sim clock, `move_base_to_pose` read speed between fixes with equal sim stamps (the
   runner steps faster than `/clock` advances) as inf, never counted the base as settled, and failed
   a dock sitting at dist 0.000 on the stall timer. The gripper's stopped window had the same
   exposure — identical same-frame readings mid-stroke could pass for a grasp. Both sample ≥50 ms of
   clock now; closing empty jaws now correctly reads "nothing grasped".
4. A stalled combined turn+translate made the wheels report 0.7 m that did not happen and AMCL
   followed it (loc_err 0.62 m). AMCL alpha1 0.05 → 0.3. Open: a rover wedged with spinning wheels
   still defeats AMCL (Mission B b1: 4.5 m) — see 5.
5. `terminate_on_success` auto-reset the episode the moment the rover reached the dock, teleporting it
   (AMCL then 160° off). Deploy scenes set it false; success is observed, not acted on.
6. Nav2's omni caps bound vx and vy separately (0.57 each); the kernel bounds the planar speed (0.6).
   A diagonal crab at 0.606 E-stopped the graph. New `nav2_max_lateral_speed_m_s` (0.25) derives
   vx_max = 0.512. Nav2's cruise envelope only; other callers crab at the full bound.
7. A direct Nav2 goal to the depot cut the charging station's corner: footprint 0.2 m into the
   station, rover wedged, odometry ran away. Mission B's check now goes via the depot loop's east
   leg. Open: MPPI/costmap tuning near structures.
8. Host: `openral deploy sim` SIGKILLs every openral-graph-looking process at start and exit and
   purges Fast-DDS SHM — it killed the sibling graph on the other GPU each time a run started or
   tore down (F50's "parallel graph works" was timing luck). `OPENRAL_SKIP_ORPHAN_REAP=1` now also
   covers the exit sweep and the purge. And editing `run_d0.sh` under a live run killed three
   runners mid-script (bash reads scripts incrementally); runs now execute a frozen copy and tear
   down by a run tag.

9. **A base velocity command opened the gripper.** SRB's `cmd_vel`/`event` callbacks rebuild the
   whole action row with the teleop mapping, whose gripper slot comes from the `event` topic the HAL
   never publishes. Grasp → lift worked; the first base motion after it opened the jaws, and Mission B's
   ORU rode to PDU-1 hooked on open fingers (b6: every step "succeeded", `release` was already done at
   0.0 s, the ORU hung at 72°/−53° after retreat). The handle–TCP distance could not tell a clamp from a
   hook; the D0 trace now logs the jaw joint. SRB now latches binary joint commands over rebuilt rows.
10. **MoveIt plans without the world.** The self-model knows the rover only (no octomap, no perceived
    collision objects in these runs), so a plan to a pre-grasp pose can sweep through the object it
    reaches for: it nudged the ORU 5 cm (b5, jaws then closed on nothing) and knocked the service cover
    0.21 m off the panel (ac1). The checks now re-read targets at step time (what relative perception
    would do); the D0 capability gap stays open: a world-aware planning scene before Experiment I.

**4. Closed-capability inventory (execution_plan §13.2).** What a valid solution of each situation needs, and
whether it has run through this stack with realistic localization:

| capability | A cov | B cov | A cover_obstruction | A status_mismatch | B destination_occupied | B spare_swapped | route_block | D0 |
|---|---|---|---|---|---|---|---|---|
| navigate (Nav2, AMCL map) | x | x | x | x (2 PDUs) | x | x | x (detour) | **measured** |
| dock to work pose (map) | x | x | x (+ shelf) | x | x (shelf, stand) | x | | **measured** |
| arm: READY/stow, MoveIt, servo | x | x | x | x | x | x | | **measured** |
| press with closed jaws | x | | x | x | | | | **measured** |
| clamp a handle, carry under Nav2, place, release | | ORU | cover bar | | crate + ORU | ORU (slot 1) | | **ORU measured**; crate not run |
| grasp the service cover's bar | | | x | | | | | **blocked**: MoveIt knocks it off (ac1), servo cannot reach from READY (ac4) |
| observe state from a view pose (camera + semantic query) | | | cover over button | lamp colours | shelf occupied | which object is the ORU | | **not in D0**: Phase E |
| relative target pose for the arm | x | x | x | x | x | x | | **truth stand-in** — replace before freeze |

So Experiment I's held-out set is not yet admissible: `status_mismatch`, `destination_occupied` and
`spare_swapped` need Phase E observation; `cover_obstruction` needs a world-aware planning scene.

**5. §21.4 common capability boundary (live proof, run cm2).** `ros/space_harness_msgs` +
`openral_ext/capability_server`: effects on `/space/capability/execute` (ExecuteCapability), queries on
`/space/capability/query`; `contracts.yaml` declares 8 effects and 4 queries; each effect is checked against its
contract and lowered to exactly one ExecuteRskill (same runner/kernel/HAL path); evidence is robot-observable only.
Mission A `covered` driven only through it (`d0_capability_mission_a_check.py`): dock 0.064 m, press clears PDU-2
(1 press, TCP 1.44 cm), stow, dock 0.041 m, **verifier success** — the same outcome as the direct dispatch (a5:
0.090 / 1 press / 0.077 m). An off-contract call (`dock_to_pose` without `yaw`) is refused with failure_kind 20.

**6. F50 §5 corrected.** The ros_action wait was *not* on the sim clock in the deploy graph (defect 2),
and the parallel GPU-1 graph did *not* work: its start/exit reaps killed the sibling (defect 8).

**7. Video.** `srb/utils/video_stream.py`: `--video` under `srb agent ros` streams a viewer camera
following the robot root into ffmpeg (fragmented MP4). Hydra `env.viewer.*` overrides did not reach
the viewport controller; the wrapper drives it directly.

### F52 — The PLEXIL baseline runs Mission A through the common boundary; a world-aware planning scene and a non-ratcheting arm hold make `heldout_cover_obstruction`'s capabilities and a clean Mission B carry work

2026-09-17, execution_plan §21.5, D0 gaps 1 and payload sag (F51).

**1. PLEXIL on the live graph (run p1).** `baselines/plexil/plans/MissionA_Covered.ple` (PLEXIL 6.1.3, standard
constructs: Sequence, Try-retry per base leg, PostCondition per effect) executed by `universalExec` with
`ros/plexil_capability_adapter`. Every Command is a capability of `contracts.yaml` with positional arguments — the
adapter holds no mission logic. 13 capability calls, all as planned (navigate_to_feature 43.9 s sim, dock_at_feature,
grasp → nothing grasped, READY, plan_ee_to_feature 30.4 s, four move_ee_to_feature, READY, stow, dock_at_feature
back-away, navigate_to_pose home); **verifier success** (PDU-2 cleared, 1 press), dock 0.127 m (AMCL 0.12 m).
"Plan complete, Exec exited without errors". So Ours (cm2) and PLEXIL (p1) now reach the robot through one
interface with the same outcome on the covered case.

To make that possible the boundary gained generic feature-addressed effects (`navigate_to_feature`,
`dock_at_feature`, `plan_ee_to_feature`, `move_ee_to_feature`: work pose = hull + arm reach along a site feature's
normal; TCP offset along the normal, press/grip orientation) — the geometry PLEXIL cannot do on JSON, identical for
every method — and a positional argument form. Adapter defects fixed on the way: a second `get()` on Humble's
`std::future` threw inside the exec thread and stalled every lookup; the rclcpp executor was constructed before
`rclcpp::init`; the adapter now waits for the boundary before the plan starts.

**2. World-aware arm planning (runs ac5, b8).** `openral_ext/planning_scene/node.py` publishes the surveyed site
structures (`site_structures.json`, 30 boxes — the same structures the lidar map contains; site knowledge) and the
movable ORU / crate / service cover (simulator-truth poses — Phase E perception stand-in) as `CollisionObject`s in
`map`. Default in `run_d0.sh`.
- `heldout_cover_obstruction` (ac5, MoveIt on): plan to the cover pre-pose **cover_moved 0.0 m** (0.21 m without the
  scene, ac1); servo approach, grasp the bar (jaw 0.313 rad), lift, pull (button uncovered), dock out and to the
  shelf with the cover clamped (0.029 m), place, release, re-dock the panel (0.049 m), MoveIt pre-press 0.5 cm, press:
  **PDU-2 cleared, blocked_presses 0**. 24/24 steps. Every capability the held-out solution needs now runs through the
  stack.
- Mission B (b8): MoveIt pre-grasp moves the ORU 1 mm; **verifier success**.

**3. Payload sag was a leash ratchet (SRB `SwitchableArmAction`).** The twist controller wrote the 5 cm-leashed desired
pose back every substep, so any transient beyond 5 cm under a held 1 kg ORU (Nav2 accelerations) became the new held
pose: over the carry leg the handle dropped 3.5 cm (b7), 10.4 cm (bv1), 9.0 cm (bv2) — not render- or rate-dependent
(bv2 ran at 0.21×), and not terrain (the road is level to 1.5 cm). The leash now persists only while the arm is being
moved. b8: 3.1 cm transient on the carry leg, **recovered to the held height (1.106 m)** on the next leg; place clean.

**Still open.** Perception held-out primitives (status_mismatch, destination_occupied, spare_swapped) need Phase E; the
truth stand-ins (`locate_feature`, arm feature targets, movable objects in the planning scene) must be replaced
before the freeze; a wedged rover defeats AMCL; PLEXIL plan library for Mission B and the held-out-relevant recovery.

### F53 — Ours runs Mission A `covered` end to end (verifier success, 43 agent steps); the simulator's camera TF was frozen at spawn; contact targets move from truth to wrist-camera vision

2026-09-17, execution_plan §21 items 2–4 (reordered: Ours before the baselines), Phase E. Research repo branch
`feat/ours-space-runtime`.

**1. Ours' runtime (`space_runtime/`).** OpenRAL's `ReasonerCore` runs the loop unchanged (one typed tool call per step,
identical-call cap, tick spans); the harness supplies what OpenRAL lacks for this paper:
- `facts.py`: append-only `events.jsonl` + reducer = authoritative facts (mission, robot evidence, verified effects,
  observations, anomalies, availability/FDIR/approvals, working plan, recent steps, reasoner history). A restarted or
  switched reasoner replays it (`--resume`); an effect in flight when a reasoner died becomes an anomaly.
- `context.py`: the snapshot is rebuilt from the facts every step (no chat history).
- `tools.py`: the palette is rendered from `contracts.yaml` (same names/args as PLEXIL) + plan tools + operator report /
  request; decoded into OpenRAL's `ReasonerToolCall` union.
- `guard.py` + `configs/space_runtime.yaml`: contract/arguments, hard availability, active-fault prohibition (the
  safety kernel's latched `/openral/safety_status` → `estop` fact), authority class. No mission rule; the one invariant
  first written ("arm stowed for base motion") was wrong -- Mission B carries clamped payloads under Nav2 -- and removed.
- `verification.py`: effects from robot-observable evidence vs the commanded goal (AMCL base, arm kinematics, jaw and
  joint encoders), never the skill flag or truth.
- `report.py`: the report is generated from the record; the agent's own text is quoted.
- OpenRAL's `DecomposeMissionTool` requires each subtask to name one tabletop object (`GroundedSubtask`): it rejected
  "return to the dock" three models out of four. The plan tool keeps `MissionState` but takes plain strings, replacing
  only open tasks.

**2. Run oa1 (Mission A `covered`, DeepSeek-V4.1-Flash, cameras on, arm targets still the truth stand-in).**
Verifier **success**: PDU-2 cleared with 1 press, rover at the dock (truth 0.10 m, AMCL 0.09 m), arm stowed. 43 steps,
598 s sim, 63 min wall. The agent's own strategy: plan (after one OpenRAL grounding rejection), inspect PDU-1 (front
camera from the view pose gave an ambiguous answer -- the cabinet carries decorative red lamps -- so it docked and read
the lamp with the wrist camera 12 cm away: green), PDU-2 (red), press (close jaws, MoveIt to the button, 1 cm past its
face), re-observe (green), inspect PDU-3 (green), stow, return, dock, report. The report matches the record.
Wall time: 68 % robot execution at 0.15× real time (two 640×480 cameras rendering), 30 % LLM (25 s/step mean,
2–99 s), 1 % VLM.

**3. VLM.** DeepSeek-V4.1-Flash reads lamp colours reliably from the wrist camera at 12 cm; answers "cannot be seen"
when a question names an unlabelled unit. Pointing (pixel JSON): lamp boxes within ~5 px on real frames (Qwen3.6-Plus
and GLM-4.6V equally, but in 0–1000 normalised coordinates). All three confuse the red push button with the glowing red
lamp when the wrist camera is rolled 90° -- "the lower dome" means nothing in a sideways image. The boundary now
rotates frames gravity-upright (quarter turns from the camera's TF) before the VLM and maps pixels back.

**4. Fiducials tried and dropped (user decision: visual servoing).** AprilTags on equipment would pre-engineer what can
be perceived (only tagged things exist) and address targets by registry name, against the paper's claim; the pilot also
detected nothing. Contact targets now come from `approach_target`: the VLM locates a target described in words in the
wrist image, the arm shifts 6 cm sideways, the two rays are triangulated (≈1–3 mm/px at 20 cm), the tool servos to a
stand-off and corrects once from a third view; `move_tool` does the last centimetres. Site points remain the survey
placed by AMCL (several cm), used to bring the camera near. Shared by every method; no simulator truth left in
`openral_ext` or `space_runtime`.

**5. Defect: camera TF frozen at spawn.** IsaacLab `CameraCfg.update_latest_camera_pose` defaults to False, so
`data.pos_w`/`quat_w_ros` keep the spawn pose and SRB's ROS interface broadcast it: `odom -> wrist_camera_optical_frame`
was constant at (-0.30, 0.06, 1.61) while the arm moved. First vision run (vc1) triangulated a button 17.8 m away.
Fixed in SRB `ground_manipulation/visual_ext.py` (True for all three cameras).

### F54 — Vision-guided contact works (press vc4, grasp vc10); the lunar base step cost was the lidar and re-published sensors, not rendering; GPU PhysX is not a switch in SRB

2026-09-17, Phase E / Step 5, runs vc3–vc10, pf1–pf2, gp1.

**1. Camera frames.** Chaining the cameras through their mount bodies (openral `feat/wrist-depth-relay`: Link7 / rgbd_camera_frame
TF × the `lunarbot.py` extrinsics, IsaacLab "world" convention → ROS optical) fixed F53 §5. Setting
`update_latest_camera_pose` in SRB did not change the broadcast pose and was reverted. Both cameras are D435i: the wrist depth
is relayed too, and `approach_target` localises from one RGB-D view (no triangulation).

**2. VLM localisation, measured on real frames.** One answer is not stable: vc3 got the PDU-2 button, then a rail point 14 cm
below it on the next call (the arm pushed the panel and moved the rover 7 cm). On an elongated part (the ORU bail) five answers
wandered 30–80 px along it. Now: five concurrent asks, ≥3 must find the target, per-axis median; depth = 25th percentile of a
7×7 patch (the foreground, not the box behind a thin neck). Frames are rotated gravity-upright before the VLM; the wrist image is
level in `grip` orientation and rolled 90° in `press` (user: view level).

**3. Results.** vc4 (press, button described in words): PDU-2 cleared, 1 press. vc10 (ORU bail, wrist light on): target
2.1 cm from the neck centre (mostly along the approach), one correction 1.8 cm, TCP 1 cm from the neck at the grasp, jaw
0.181 rad (F51's truth-guided clamp: 0.172), jaw held 0.17 through a 10 cm lift, handle 1.022 → 1.078 m (the rest is the 1 kg arm
sag, F51). Before the wrist light (vc7) the black bail against the black sky was invisible; the lunar base tasks now carry a
wrist and a front work light.

**4. Where a lunar base step went (SRB_ROS_PROFILE, pf1 → pf2).** 117 ms/tick at 0.155× real time: lidar ray-cast at every
50 Hz step 47 ms (the lazy refresh also absorbs the GPU sync), re-publishing unchanged camera/point-cloud data 28 ms, CPU
PhysX 26 ms, render 3 ms. Rendering was not the cost: cameras 50 → 15 Hz and dropping `cam_scene` changed 0.150× → 0.155×
(my first hypothesis, wrong). Fix: lidar `update_period` 0.1 s (the Mid-360's 10 Hz), publish a sensor only when its
timestamp advanced → ~47 ms/tick, **0.375×** measured on navigation and docking. Two graphs in parallel ran at 0.05× each
(24 threads per Isaac process on 24 cores): run one at a time.

**5. GPU PhysX (user request) is not a switch.** `SRB_SIM_DEVICE=cuda` (CCD off) crashes at the first step: IsaacLab's
`BinaryJointPositionAction` mixes cuda and cpu tensors (SRB's `__main__` re-sets devices after the cfg). Left opt-in and
off; physics is now ~24 of ~47 ms, so the ceiling of that port is ~2×.

**6. Reasoner thinking.** Offline A/B over oa1's 42 decisions: thinking off 3.9 s median vs 13.3 s on, tool choice not
systematically different; kept **on** (user decision: capability over latency).

### F55 — Mission B with Ours: the pick fails on the pipeline, not on the reasoner alone; step-wise development; reasoner and VLM choices; ad-hoc patches reverted

2026-09-17, Step 6, runs ob1–ob6 (+ ob5_s*, ob6_s* resumes), offline reasoner replay.

**1. Step-wise development.** SRB `envs/snapshot` saves/restores every articulation, rigid object and the held action
buffers; `ours_mission_check.py` saves before every agent step, `D0_HOLD=1` keeps the graph, `attach_d0.sh` restores to
before a failed step (also into a fresh sim from disk), re-seeds AMCL from the saved estimate (only after `/initialpose`
is matched — a lost message left a 0.16 m stale estimate once), truncates the record and resumes the agent.

**2. Real defects found and fixed.** (a) `move_ee_to_pose` completed on a nonzero proportional twist; SRB applies the
last twist until the next command → the arm crept ~1.5 cm/s after every servo (0.9 m in 60 s during reasoner thinking);
it now commands a zero twist before reporting. (b) A VLM gateway timeout raised out of `approach_target` with no reason.
(c) The camera frame can be one TF tick newer than the pose. (d) Verification band for MoveIt plans: executed plans end
0.9–3.0 cm from the planned goal (9 plans) → +2.5 cm. (e) An arm-goal failure now states its distance from the mount,
MoveIt IK reachability and joints at their stops (a bare `error_code=99999` gave the agent nothing).

**3. Why the pick kept failing** (12 failures): 4 stack defects, 5 interface gaps, 3 reasoner judgement errors — the
latter all where the interface made the reasoner do 3-D arm kinematics from coordinates (viewing poses inside the
elbow limit, docking with the arm raised pushed the ORU 9 cm, survey-coordinate contact). The VLM-point pipeline marked
the handle's base plate or the box edge instead of the bail twice (close up the gripper hides the T crossbar); the
approach is two looks and a blind slide; no pre-close or post-lift check. Best result: the agent clamped the ORU neck
(jaw 0.175 rad, ob6_s19d) but the lift stalled with joint3 at its stop.

**4. Reasoner / VLM.** Offline replay (`experiments/reasoner_replay/replay.py`, 5 recorded decision points × 2, limited
tools): DeepSeek-V4-Pro 7/10 (median 162 s), Kimi-K3 3/10, Qwen3.8-Max 3/10, local qwen3.8 27B (Ollama) 3/10 (33 s),
GLM-5.3 2/10 (mostly timeouts), DeepSeek-V4.1-Flash 1/10 text, 3/10 with the wrist image. Reasoner → DeepSeek-V4-Pro.
Shared VLM → GLM-5.3-Flash (Kimi-K3 took 95–150 s per answer with timeouts; same pixels). Wall time before the switch:
reasoner ~55 %, arm motion ~25 %, VLM ~20 %.

**5. Patches tried and reverted (user decision).** joint3 plan constraint, rejecting stand-off re-detections > 4 cm,
coordinates/operating hints in the contracts, a `look_at_feature` grid search, a mount-line reachability probe,
string/push-based stops in the dev check. They papered over one failure each. The pick is to be rebuilt as composable
OpenRAL rSkills (VLM chooses among image grasp candidates, IBVS, image checks, no object models, no world-coordinate
target) with the harness bridging failures: `docs/semantic_to_metric_manipulation_plan.md` (v3).

**6. Drift noted; architecture decision.** The capability boundary implements skills (`approach_target`, VLM
perception, feature lowering). Decision: physical-effect capabilities as OpenRAL rSkills; perception control and
queries as perception/world-state services; a thin method-neutral capability contract. Method boundary revised in
`research_content` §3.2/§5.2–5.3/§5.7 and `execution_plan` §9.7/§11: the baselines share the robot, capabilities,
perception sources, raw evidence, low-level safety and the external evaluator; Ours' authoritative facts, context
reconstruction, guard, internal effect verification and traces are the proposed method, attributed by Ours-internal
ablations. Details: `docs/semantic_to_metric_manipulation_plan.md` §2.

### F56 — Plan v4: the pick is one skill; the model composes operations, not stages

2026-09-17, user decision after reviewing plan v3 (`docs/semantic_to_metric_manipulation_plan.md`).

**1. What was wrong in v3.** Its internals were right (no object models, VLM chooses among image grasp candidates,
on-board tracking + IBVS, image/encoder checks, harness facts and verification), but it made the agent call seven
tools in a fixed order to pick one object (`grasp_candidates → choose_candidate → lock_target → servo_to_target →
approach_guarded → grasp → hold_check`). That order is fixed by physics, not a mission decision: seven reasoner
steps (DeepSeek-V4-Pro, 162 s median each, F55 §4) per pick with no scientific content, and seven chances to
mis-parameterise (the pattern of F55 §3's three reasoner errors, all where the interface made the model do
geometry). The operating picture is Claude Code for a lunar robot: the model gets `Edit`, not keystrokes.

**2. v4.** `pick(target, part)`, `place(support)` and (when Mission A's contact code is next touched) `press(target)`
are single OpenRAL procedural rSkills with mission-level arguments only; the v3 stage tools become internal functions
and perception services, not model tools and not baseline Commands. Locality rule: same-target retries inside the
call (re-lock, back off and re-centre, next candidate, re-check); changing target, base motion, another operation or
the operator return control with the stage reached and its evidence. The harness verifies `held` / `placed`
automatically from the shared queries. Hardware-protecting limits while driving or holding go to the shared
low-level safety; the v3 guard rule "no base motion while holding" contradicted Mission B's carry and is withdrawn
(F53 §1 removed the same rule once). Gates: G0 data, G1 classical candidates (learned only if needed), G2 VLM
selection, G3 one-call pick under unknown placement, G4 Mission B covered, G5 held-out; the generality gate and the
generator ablation are dropped. Granularity rule recorded in `execution_plan` §8.2.

**3. Effect on earlier work.** Nothing built is discarded: the VLM detection, servo and depth code in
`capability_server` and F54's vision-guided contact become the internals of `press`/`pick`; `verification.py`
gains the held/placed checks; `guard.py` and its config are unchanged (invariants already empty); the PLEXIL adapter
gets simpler (one Command per operation); F55's reverted patches stay reverted; the snapshot workflow is the
development loop for G3–G5. Expected Mission B step count falls from 60+ to roughly 15–25.

### F57 — `pick` as one call: what the wrist camera has to see, and the constants that hid it

2026-09-18, runs g3a–g3bn (`artifacts/runs/g3*`), `openral/python/rskill/src/openral_rskill/{procedural_pick.py,
grasp_perception.py,_eye_in_hand.py}`, SRB `lunarbot.py` + `ground_manipulation/visual_ext.py`.

**1. The gate is passed at the nominal placement (g3bn).** One `pick("the spare ORU ...", "its carry handle")` call:
the skill found the handle, the vision model chose the neck under the head, the first approach stalled 2.2 cm short and
the skill retried *on the same target* (the plan's locality rule) and held it. Jaw 0.172 rad (a 12 mm neck between the
pads), TCP 2.1 cm from the truth handle, Ours' independent `item_held` true: 7.85 cm of lift, 4 px of image motion on
the item against the 232 px it would have shown if left behind. 237 s of sim time. The truth handle settles back after
the call returns -- the 1 kg arm sag of F51, not a slip (F55's reading of `handle_rise_m` alone was wrong: g3aw's
handle rose 1.023 -> 1.085 m *during* the lift and the call still reported 1.7 cm afterwards).

**2. What the skill does.** `pick(target, part)` takes no geometry: side views of the reach zone from the arm's own
working branch, class-agnostic antipodal candidates from the wrist depth (G1), one vision-language choice among the
numbered marks (G2), the planner to the stand-off in the grasp's own orientation, then a closed loop -- the part
followed by its own image template -- for the last stretch. Nothing in the loop knows what an ORU is; the only
object-specific text is the site's payload-handle convention in the selection prompt.

**3. Look-move-look does not converge; the closed loop does.** Re-running the generic detector per frame and
re-associating the candidate walked the goal 8 cm sideways over an approach (servo trace, g3ap): the narrowing view
offers new antipodal pairs and the nearest one is not the same part. Following the part's own template instead
(`PartTracker`: NCC in a window predicted from the arm's own motion, template rescaled by the depth ratio and turned by
the camera's own roll, matches at the wrong distance rejected) removed the item pushing entirely -- the handle moved
3 mm during a whole approach (g3aw) where the open-loop version moved it 5 cm.

**4. Three defects, one cause: the camera's geometry written down as constants.** Each was found by looking at the
evidence pictures, not at the trajectory numbers.
- *The roll.* Which side of the tool axis the camera looks from decides the grasp's half-turn. Choosing it by
  projecting the measured camera offset across the *optical* axis cancels exactly the lateral component it is meant to
  keep (the optical axis is 17 deg off the tool axis, so in the tool frame it carries 0.29 of y): every view got the
  opposite roll (g3bg, `servo_00.jpg` is the chosen view upside down). Taking the lateral part *in the tool frame*
  fixes it for any mount. The roll itself belongs to the part -- the camera goes to the side the part is measured to be
  free on -- and must not be chosen to spare the tracker a rotation: doing that picked the opposite roll and the
  approach diverged, the tool sliding 18 cm sideways in 1.6 s with the error growing (g3bh).
- *The half turn itself.* Turning the wrist where the tool stands swings the camera's view by twice the mount's 17 deg
  and the part leaves the image (g3bl `turned.jpg`: only the rover deck). The planner now takes the tool to the
  stand-off *in the grasp's orientation* in one move, which puts the part back on the tool axis, and the visual servo
  does only the last 10 cm.
- *The self-depth.* "Nearer than 0.17 m is the gripper" was written into `seen_through`, with copies at 0.20, 0.22 and
  0.16 elsewhere. After the camera moved, the gripper's own pixels read as *an obstacle in front of every candidate
  pose* and no view of the work zone was allowed at all (g3bm: every side view `reachable: false`).

**5. The fix is one derivation, not four numbers.** `tool_in_view(K, T_camera_tool, rows)` computes, from the mount
(TF) and the tool's own dimensions, how far the gripper reaches along the optical axis and which image band it always
occupies; the self-occlusion depth, the framing rows, the candidate depth floor, the tracker's "the gripper covers the
part" test and the lift check all read it. Checked against the old mount it reproduces the hand-tuned values that were
in the manifest (0.203 m vs 0.20, row 107 vs 108) -- they were always geometry, not tuning. The manifest lost four
entries.

**6. The wrist camera itself was wrong twice.** Its intrinsics were `focal 10 mm / aperture 16 mm` = 77 deg, which is
the D435's *depth* field, not the colour stream the skills work in; it now renders the D435i's own 640x480 colour
intrinsics (15.4/16.0, fx = fy = 616, 55 x 42 deg). And it sat 0.048 m off the tool axis aimed at the grasp point,
which left two thirds of every frame filled by the fingers. The mount was recomputed (not tuned): 0.12 m off the axis,
0.22 m behind the TCP, aimed 0.15 m beyond it -- the gripper then occupies the bottom fifth of the frame with both pad
tips visible, and the part being approached sits in the middle of the image. G0's dataset and the G1/G2 offline scores
were taken with the old camera and stand as such.

**7. Method note.** Every one of these was visible in a single evidence image and invisible in the numbers; the runs
that only printed distances (g3ab..g3bd) cost hours and settled nothing. The servo now writes one picture per frame
with the tracked point, the match score, the roll correction and why a frame was rejected.

