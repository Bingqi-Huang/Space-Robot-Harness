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

### F24 — RTX Lidar produces no data in headless mode on our pinned Isaac Sim build (confirmed upstream bug)

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
mechanisms tried (bare `simulation_app.update()`, `SimulationContext.
step()`, the async `next_render_simulation_async` matching Isaac Sim's own
official `isaacsim.sensors.rtx` test suite, and the synchronous
`rep.orchestrator.step()` purpose-built for standalone scripts), plus the
two documented headless workarounds from Isaac Sim's own Known Issues page
(`rt_subframes>=2`, `--/exts/isaacsim.core.throttling/enable_async=false`).
Matches a still-open upstream report,
[isaac-sim/IsaacSim#110](https://github.com/isaac-sim/IsaacSim/issues/110)
("Cannot retrieve RTX lidar data using headless Python script"), and an
[NVIDIA forum thread](https://forums.developer.nvidia.com/t/unable-to-reliably-produce-lidar-data-in-a-headless-simulation/337835)
reporting the identical symptom where a moderator stated (2025-09-24) the
issue was fixed in Isaac Sim 5.1.0 — but our pinned install
(`~/Programs/isaac-sim/VERSION`) is `5.1.0-rc.19`, a release-candidate
snapshot predating that GA fix, not the release it shipped in. **Not an
SRB or implementation defect** — do not re-attempt fixing this in SRB
code; re-verify after the Isaac Sim install moves off the RC build.
Consequence: `rtx_lidar.py` exists and is correct but is not wired into
`srb/core/env/mobile/env.py`'s active sensor path; RayCaster (F23) remains
the active `lidar_robot` implementation. Source: this session's six-way
reproduction (scratchpad, not committed) plus
`docs/rtx_lidar_integration_plan.md`'s Status section.
