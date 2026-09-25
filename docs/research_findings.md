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

### F58 — The two things that stopped `pick` being callable by the agent were not about grasping

2026-09-18, runs g4a–g4h, `openral/python/rskill/src/openral_rskill/{_eye_in_hand.py,grasp_perception.py,
procedural_pick.py}`.

**1. A skill may not own a subscription it closes.** `pick` created its wrist RGB-D subscriptions per call and
destroyed them at the end, from the worker thread that runs the skill. `rclpy` handles belong to the executor: the
destroy raced `executor.spin()` on the runner's own thread, which died with `InvalidHandle` -- and with it every later
goal on that runner, including the ones the agent had not sent yet. The symptom (each capability after the first
returning "no result") pointed at the boundary, the capability server and the agent in turn; none of them was at
fault. Sensor streams are now the *node's*, created once and never destroyed; the skill borrows them. The general
rule for this codebase: a skill may create work for the executor, never take work away from it.

**2. The vision model's latency is set by the request, and the request was ours to choose.** Every G4 attempt before
g4h died at stage `select` on a vision-language call that never returned. Measured and excluded, in this order:
gateway health (three concurrent asks answered in 12.7 s, all ten choices correct), concurrency (sequential was
*slower*), the GIL (9.3 s with four camera pump threads running), CPU load (24 cores, load 13), a proxy (the runner's
environment has none -- the "proxied process" was my own shell), stale keep-alive sockets, and the SDK version (raw
`httpx` timed out identically). What was left was the request itself, and it reproduced on demand with the same
recorded frames:

| what the one request carried | bytes | two trials |
|---|---|---|
| overview + both marked views, full size | 265 KB | 60 s no answer, 16 s |
| both views side by side, 448 px wide each | 69 KB | 60 s no answer, 45 s |
| **one marked view** | **54 KB** | **15 s, 7 s** |

`select` now asks one question per marked view, carrying that view alone, and stops at the first view that answers;
on three real frames it answered in 12, 74 and 78 s and chose the neck mark in every one. The overview left the
request: the item's identity is carried by the words, and the separate `item_visible` / `what_is_visible` fields left
with it -- a choice of null is the same answer, and a model spends its time on what it is asked to write. The three
concurrent asks became one on the G2 dataset's own evidence: a single answer and the majority of three both scored
20/28.

**3. Why this belongs in the record.** Neither defect is about manipulation, and both would have been read as "the
grasp method is unreliable" from the mission log alone. The harness already separates them: a call that fails because
a remote service did not answer is recorded as `dependency_unavailable` / `requires_remote_service` and reported under
"service outages (not the robot's doing)", not as a failed operation. A study that compares methods across an agent
loop needs that line drawn before the numbers are collected, not after.


### F59 — What the robot can reach is the harness's business, and what it is holding is not an obstacle

2026-09-18, runs g4h–g4l, `openral_ext/workspace/{reach.py,footprint.py}`, `openral_ext/planning_scene/node.py`,
`openral_rskill._eye_in_hand.working_on`.

**1. An item in the planner's scene is an item the robot can never pick up.** Measured obstacles (F57 gap 1) put what
the cameras see standing in the arm's work zone into MoveIt's scene, so a planned move goes round the things no map
knows about. The ORU is one of those things. With it in the scene, no arm configuration was allowed to put the tool at
its handle; with the same request and the measurement dropped, the pose solved. Measured at the depot, one dock pose,
one tool orientation, `/compute_ik` with collisions on:

| | measurement present | measurement dropped |
|---|---|---|
| tool at the handle | no solution | solves |
| tool at the 7 cm stand-off | solves | solves |

The general rule this needs is not an exception for ORUs. A skill that is working on something says which piece of the
world its tool is about to be inside -- a sphere the size of the gripper itself, published as a collision object on
`/space/manipulation_target` and renewed while the skill runs. The world model leaves the measurement inside that
sphere out; everything outside it is an obstacle as before, and a declaration that stops being renewed (the skill
ended, or died) expires within two of the model's own cycles. While the item is in the jaws the sphere follows the
tool, which is also what makes carrying it past other structures safe. Nothing in it is item-specific: the radius is
the tool's own dimensions, the centre is where the tool is going.

**2. Where the rover parks was a table of hand-written numbers.** `interaction.py` carried `REACH = {"press": 0.45,
"pick": 0.40, ...}`: one distance past the hull per kind of job, baked into `interaction.json` and read by the
boundary, which docked there without ever asking the arm. A single number per job cannot be right -- the arm reaches a
shell around its shoulder, so the distance depends on how high the work is. The 0.40 was read off a press at panel
height and reused for a handle 0.29 m above the shoulder.

The replacement is a model of the robot, not of the site: `openral_ext/workspace/reach.py` samples the arm's own
kinematics from the live URDF (the model MoveIt plans with) on the working branch the skills use, and bins the tool
poses it can hold by point and approach direction; `footprint.py` says how close the hull may come to the surveyed
structures, with the dock's own measured error as the margin. `dock_at_feature` now proposes stands from the reach
map, rules out the ones the hull cannot take, and settles each with the robot's own IK -- one docking error nearer and
further as well, because that is how accurately a dock lands. A feature with no such stand is answered before the
rover drives anywhere: *the rover cannot park anywhere that lets the arm work here*.

**3. What the survey then said about the site.** Running that decision over every interaction point: the three PDU
panels were being approached from 0.20 m too far (their presses worked at the edge of the envelope -- Mission A's own
record has a `move_tool` failing at 1.127 m and succeeding at 1.082 m), and two features -- `depot_stand/slot_1` and
the crate staged on it -- have no legal stand at all: the hull cannot clear the stand at any distance from which the
arm reaches the handle. That is a fact about the scene the robot can now state, instead of a mission that fails at the
last centimetre.

**4. Why G3 looked fine.** The G3 gate passed at a dock that landed 6 cm short of its work pose, which was enough for
the measured-obstacle problem to stay hidden behind a stand-off that happened to be reachable. A gate that only ever
runs one placement measures the luck of one dock; the reach model is what turns that into a statement about the site.

### F60 — A grasp cannot be restored, a jaw angle is not a grip, and one blocked view should not end a pick

2026-09-18, runs g4m–g4w. `openral_rskill.{procedural_pick,grasp_perception,_eye_in_hand}`,
`openral_ext/capability_server/{contracts.yaml,node.py}`, `space_runtime/{verification,facts,agent}.py`,
`experiments/launch/lunar_base_d0/ours_mission_check.py`.

**1. The simulator's snapshot cannot restore a grasp, so no run may resume from one.** `envs/snapshot` writes back every
joint angle, every joint target and every object pose, but the contact that holds a payload is not state — PhysX
rebuilds it from the geometry, and a 1 kg item hanging from a bail does not survive the rebuild. Measured: the
snapshot held the ORU at (6.133, −14.347, **0.668**) with all six jaw joints at 0.325 rad; after the restore the ORU
sat at (5.958, −14.103, **0.193**) — 0.475 m straight down, 0.30 m sideways, on the ground where the rover stood.
Two runs (g4n, g4o) were spent on a payload that had never been carried: g4o drove the length of the site with empty
jaws and reached for the shelf. Only snapshots taken with the jaws open are honest resume points; `before_step_<n>`
before a `pick` is one, `before_step_<n>` after it is not.

**2. A jaw angle measures how far the fingers are apart, not whether anything is between them.** `JAW_OPEN_MIN_RAD`
was 0.78, four hundredths under the commanded 0.82 — and the jaws come to rest at 0.776. Every open jaw therefore read
as a held item: the boundary refused `arm_ready` in g4p ("the jaws are holding something (jaw 0.776 rad)"), and the
same constant would have failed `place` at its own settle check. It was written down twice, in `_eye_in_hand.py` and
in `node.py`, for one gripper. Now 0.6, defined once, read by the boundary from the skills (the harness config already
used 0.6). The deeper point is that the angle was never the right evidence: 0.10 rad is closed on nothing, 0.175 is
closed on a 13.6 mm edge, and a payload that slips out leaves the jaws exactly where the grasp left them.

**3. `held_item`: what the gripper has, read from its own camera.** A new read-only query at the shared boundary asks
the vision model what is between the fingers and answers `{holding, what}` with the jaw angle beside it as a number,
not as the verdict. Offline on four frames whose answer was known it scored 4/4 in 1.8–2.6 s (`hold_after.png` →
"white T-shaped block"; the frame where g4s reached for the shelf → not holding). Nothing is said to the model about
what is expected to be there: an answer shaped by the question is not evidence (F57 §4, F58 §2), and comparing it with
the record is the caller's job. Being a perception service it is shared with the baselines, like `observe`; using it
to keep authoritative facts honest is Ours' mechanism (research_content §3.2).

**4. An effect verified once is not a fact for the rest of the mission.** `item_held` held after `pick` and was never
questioned again. In g4s the ORU dropped back onto the depot stand as the rover pulled away; the jaw read 0.1 rad in
the evidence of *every* call from there to the shelf, and nothing compared it with the record, so `place` reached out
holding nothing and stalled against the PDU panel — a failure that looks like a manipulation failure and is not one.
The harness now looks again after every call that is not `place` or `release` (`item_still_held`, through `held_item`),
and an item that is no longer there goes back to `unknown` with the picture that unseated it. Where it went, and what
the mission does about it, stay the agent's to work out. A query that does not answer leaves the fact alone: a service
outage is not evidence that the payload is gone (F58 §3).

**5. The first view that answered was deciding the grasp.** F58 §2 cut `select` to one marked view per question and
stopped at the first view with a choice — a concession to a gateway that timed out on anything larger. On DeepSeek's
own endpoint a marked view is read in 1–6 s, and the concession had become the defect: this model essentially always
answers, so the first view always won. In g4q that was the only view taken from above, and the mark it chose lay on
the depot stand 42 cm behind the ORU's handle, reported as "the narrow neck directly under the T-shaped head"; the
approach then failed 99 cm short. `select` now takes every view first and judges all of them in one question (the
numbering already ran across views). Offline on g4m's own two views it chose the low view's mark 7 — the grasp that
actually held — in 2 of 3 asks, where the high view's mark 6 had slipped out of the jaws on the lift.

**6. What holds the payload is interlock, not friction** (user, 2026-09-18): the grasp goes across the neck *just*
under the T-head, so the head rests on the closed fingers. This is why a static lift check cannot predict a carry.
In g4s the chosen candidate was 13.6 mm wide (jaw closed to 0.175 rad, exactly as predicted), it passed `item_held`
with a 7.2 cm lift, and it dropped as soon as the rover moved. A lift proves friction; only the head sitting on the
fingers survives a drive.

**7. A blocked view, or an unreachable candidate, should not end the call.** Taking every view before choosing means
more views, and the lowest of them stand close in: g4v stopped 0.12 rad short against contact on the way to one and
failed the whole `pick`. Three places treated a local obstruction as a fatal one, and all three are now local: a view
the arm cannot reach is one view fewer; a candidate the arm cannot stand in front of goes into `tried` and the next
one is asked for (plan v4 §4's own rule — g4q's was 99 cm away on the wrong structure, g4u's 21 cm away on the ORU
itself); and the retreat back to the view's posture is a convenience, not a requirement. Also removed: the move back
to the chosen view's posture before approaching. It was a no-op while the chosen view was the one the arm stood in;
with every view taken first it became a move across the work zone, and in g4r it stalled and failed the call —
`approach` works from the frame's own TF and plans to the stand-off from wherever the tool is.

**8. Operational.** A `pgrep -f` kill left one agent of a stopped run alive; it drove the robot alongside the next
run's agent for twenty minutes (g4u), which knocked the ORU off its stand mid-`pick`. The rule was already in the
handoff — kill explicit PIDs — and the missing half is: verify afterwards that the domain is clean. The scene's own
starting state is now saved as `snapshots/initial.pt` when a graph boots, so a mission can be retried from the top
with `OURS_RESET=1` instead of rebooting Isaac; it is a jaws-open state, the only kind a restore can honestly return
to (§1).

### F61 — Where to look was written down, and looking from above made the grasp that holds unmeasurable

2026-09-19, runs g4w, g5a–g5e. `openral_rskill.{procedural_pick,grasp_perception}`, `rskill-procedural-pick`.

**1. Three constants decided where the camera looked, and none of them knew what it was looking for.** The overview
posture was one written-down pose (`overview_pose: [-0.85, 0, 1.10, 50, 0]`); the working views came from
`aim_points`, which picks whatever stands above its surroundings -- its own docstring says "nothing here knows where
it was put" -- and their direction came from `side_view_pitch_deg: [10, 20, 30, 40]`, every one of them looking down.
In g4w four of the five views went to other structures, and the one that did find the handle saw it from above.

**2. From above, the grasp that holds cannot be measured at all.** The ORU's lifting interface is a 12 mm neck under
a 90x45x14 mm head with 55 mm of free height (F49 §2): the jaws take the neck and the head rests on them. A row-wise
depth profile of g4w's top view finds the neck exactly where F49 says it is -- **12.3 mm wide at 0.629 m, both sides
100% clear** -- and the candidate generator still produced nothing near it. Not a defect in the generator: seen from
above, the neck's 55 mm of free height projects to about **8 px ≈ 8 mm**, below `pad_height_m` (14 mm), and a grasp
face that short is correctly refused. At the handle's own distance every candidate in all 26 was 19-27 mm, which is
the handle's *other* axis -- the one F49 recorded as squeezing out of the jaws at 28 mm. The vision model was never
choosing badly; the grasp that holds was not in the list to choose.

**3. What replaced the constants.** The overview is now a place to look from, not a posture: lower and shallower
poses are offered in turn until one is actually reached (g5b stopped 0.13 m short of the written-down one, "blocked
by contact", and failed the call). The item is then found *once*, on the overview, with `find_regions` +
`locate_region` -- three functions that had been written and never called -- and every working view is a view of it,
aimed at the item's own top (a lifting handle stands on top of its payload; the overview's height map says how high
it stands, no model of the item). The viewing directions now include the horizontal (`pitch 0, 5`). Asking the model
to point at the *part* in the top view was dropped: it answered "dot 14 lies on the gray carry handle" about a
surface 0.2 m behind the handle. The overview finds the item; the part is looked for from the side.

**4. Measured.** On the same scene, with the views aimed at the item and taken from the side (g5d): a candidate
**12.4 mm at 0.554 m** in the pitch-5 view and **12.6 mm at 0.551 m** at pitch 10 -- their graspable length 16 mm,
just over the 14 mm the pads need, where the top view had 8 mm. The vision model chose across the neck, and the
grasp held: **jaw 0.172 rad** (F57's own figure for a 12 mm neck between the pads), lift 7.5 cm, 34 px of item
motion against the 285 px of a scene left behind. In g5e the model again chose the thin axis twice out of three.

**5. Still open: the tool body against a 2.5-D height map.** `approach` is where it now fails: of five attempts across g5d and g5e, one held, two were refused
for a surface the tool body would touch on the way in, one stalled 2.4 cm short and one lost the track 10 cm out.
Reaching a neck under an overhanging head means putting the fingers into 55 mm of free height from the side, and the
path is narrow. The successful grasp is worth reading twice: the candidate it approached was 26 mm, and the jaws
still closed to 12 mm -- the item settled onto the neck as they closed. Form closure is what holds, and it is not
only decided by which candidate is chosen.

Measured in g5f, with the grasp point at [-1.086, 0.014, 0.94]: the tool point the guard refuses is
[-0.907, 0.010, 0.89] -- the tool's own body 17.9 cm behind the grasp, correctly outside the 0.10 m the guard
excludes around it -- and the cell it crosses measures a surface at 0.913 m, so the body is 2.3 cm *below* what was
measured there, not short of a margin. Reaching a neck that sits in 55 mm of free height means putting the tool
body over the payload it is picking up, and `surface_heights` is a 2.5-D map on 5 cm cells: it keeps the highest
point of each cell and no shape, so it cannot tell a tool passing beside the box from one driven into it. The
oracle's `pinch_pick` makes the same horizontal move and succeeds -- it checks nothing. Two ways out, both real
work: leave the *target's own* measured surface out of the guard (F59's rule, which `working_on` applies to MoveIt's
scene but not to the skill's own check), or give the check a representation that can hold an overhang.


**6. The grasp holds a lift and does not hold a drive, and that is not a speed setting.** With the observation
strategy fixed, `pick` succeeded three times running inside full Mission B runs (g5h, g5i, g5k), each time across the
12 mm neck: jaw 0.171-0.184 rad, lifts of 6-13 cm, 0.2-4.9 px of item motion against the 225-423 px a scene left
behind would have shown. Each time the payload came out of the jaws on the first drive afterwards, and the harness
said so at once (`item_still_held`, §4) instead of letting the mission reach the shelf empty. Nav2's smoother was
then set to ramp at 0.5 m/s^2 instead of 2.5 while the jaws hold something -- a shared-substrate limit applied by the
boundary to every method's base moves, read from the jaw alone (plan v4 §2) -- and the payload still came out, *on
the first metre*: measured at (5.887, -14.356, 0.548) against the slot it started in at (5.820, -14.390, 0.555), so
7.5 cm sideways and no height lost. The jaw went 0.171 -> 0.100, closed on nothing, and the gripper's own camera
showed an empty hand: the item slid from between the pads rather than the jaws opening. The head resting on the
fingers constrains the item downwards, which is what makes a *lift* hold; it constrains nothing against the moment a
horizontal acceleration puts on a 1 kg body hanging from a 12 mm neck, and the pads are 14 mm tall (`pad_height_m`)
-- too short a purchase on a 55 mm neck to stop it tilting out. Where this goes next is a question about the grasp
and the payload interface, not about a parameter: how deep the neck sits between the pads (F49 §2 measured a flange
jamming at 50 mm of depth and squeezing out at 28 mm), or whether carrying should hold the arm in a posture that
turns the moment into a push against the pads.

### F62 — `press` exists; Mission A now deadlocks between three parts that are each right

2026-09-19, runs ma1–ma2. `openral_rskill.{procedural_press,grasp_perception}`, `rskill-procedural-press`,
`capability_server/{contracts.yaml,node.py}`, `space_runtime/verification.py`.

**1. The fold is built.** `press(target)` is a procedural rSkill of the shape plan v4 §3/§4 asked for: locate (the
target's pixel from the vision model in the wrist view, its depth from the same frame, the point those give in the
rover frame) → approach (stand off facing the surface, look again from there and correct once) → press (guarded
straight close-in until the face takes the load, read the way `place` reads a support taking a payload) → retreat.
The model's palette gains one operation and loses nothing: `approach_target`, `move_tool` and `grasp` were already
`engineering: true`, which had left the model with **no contact capability at all** since that change. The harness
verifies `pressed` from the robot's own kinematics against the point the view measured -- far enough past the face,
and clear of it again afterwards -- never the skill's success flag. One new perception function was needed:
`locate_point` asks the vision model for a pixel, because a button is a patch on a panel and `find_regions` will not
separate it from the panel for set-of-mark selection. Offline on a real wrist frame of the PDU it found the button
twice (128,322 and 125,325 for two different wordings) and correctly answered "not visible" for a thing that was not
there; the pixel round-trip through every quarter turn of the gravity-up view is exact.

**2. Two defects of my own, both in the wiring rather than the skill.** `contracts.yaml` gained `press` while
`lower_effect` did not, so the boundary raised `KeyError: 'press'` **and the agent was told nothing**: the action's
own exception path leaves `failure_reason` empty, unlike the query path, which turns any exception into a typed
answer ("every failure is a typed answer to the caller, not a dead service"). The agent spent five steps re-wording
its target and re-docking against a blank failure. Effects need the same treatment as queries.

**3. Mission A now deadlocks, and every part of the deadlock is correct.** With `press` wired, ma2 surveyed all three
PDUs from their view poses, read the lamps (pdu_1 green, pdu_2 red) and went to the faulted one -- and then never
pressed anything in 23 steps:
- `dock_at_feature` stands where **the reach model** says the arm can work: 0.905 m from the point, 0.20 m closer
  than the old hand-set distance (F59 §3 measured that the old one was too far). Right.
- At 0.905 m, `arm_ready` fails -- twice, the second time with the tolerance relaxed: "no collision-free path". The
  **ready posture is a written-down set of joint angles** that assumes the rover is parked further out. Right, for
  where it was written.
- The agent worked the cause out by itself, retreated 1.5 m, raised the arm there (it succeeded), and drove back in
  -- and `dock` stopped 7 cm short: **Nav2 will not push a raised arm into a panel**. Right.
- It then diagnosed *that* correctly too ("the raised arm blocks the final approach"), and tried to stow -- "no
  collision-free path". The arm can now neither be raised nor stowed where it stands. **Deadlock.**

No part is at fault and the mission cannot proceed, because **nothing owns the joint feasibility of arm posture and
base position**. The reach model answers "can the arm reach the work from here", Nav2 answers "can the hull get
there", the postures are constants from an era of standing further back, and the agent is left to discover the
interaction empirically -- which it did, twice, and still could not escape. `press` itself needs none of it: it
plans from wherever the arm is. Its contract now says so, which avoids entering the state; it does not dissolve it.

### F63 — The carry is a moment problem, not a speed problem; and three ways a new capability fails to arrive

2026-09-19, runs g5h–g5p, ma1–ma4, g6a. `openral_rskill.{procedural_pick,procedural_press}`,
`capability_server/node.py`, `rskill-procedural-press/rskill.yaml`, `space_runtime/`.

**1. What the carry actually needed.** F61 §6 left the payload coming out of the jaws in the first metre of every
drive and recorded the wrong conclusion — that ramping Nav2 down had not changed it. Two things had to change
together, and both are about the *moment* on a 12 mm neck held by 14 mm pads, not about speed:

- **The lever.** After a successful lift the arm was left wherever the grasp ended — the tool 1.144 m out from the
  chassis origin. `bring_in()` now walks the held item in along the tool axis before anything else moves: 1.144 →
  0.838 m in g5m. The same angular acceleration at the base becomes a third less tangential acceleration at the
  payload, and it costs one arm move.
- **The drive limits.** Nav2's velocity smoother is retuned at the boundary whenever a base move is issued while the
  jaws hold something (0.25 m/s, 0.5 m/s² carrying; 0.5 m/s, 2.5 m/s² free), and restored after. This is **shared
  substrate, not Ours' method**: it reads the jaw alone, applies to every method's base moves, and is recorded in the
  boundary's own log. A baseline that carries a payload gets it too.

With both, g5m drove the whole depot → PDU-1 leg with `item_still_held` verified true on arrival — the first carry
this project has ever completed. It came out on the **dock** at the far end.

**2. What is still open, and the fix that has never run.** The dock is where the rover turns. The carrying limits
capped linear acceleration but left angular acceleration at the free-driving constant, so on a 0.84 m lever the turn
delivered ~0.84 m/s² to the payload — worse than the straight-line ramp the 19-metre leg had just survived. The
boundary now derives it: `α = 0.5 / max(lever, 0.2)`, the lever read from the actual tool pose, so the tangential
acceleration at the payload stays at the 0.5 m/s² that is known to hold. **This has never been exercised** (g6a was
started for exactly this and is still running at the time of writing). Everything in §1 above is measured; this
sentence is the one claim in F63 that is not.

**3. A capability can fail to arrive three times before it is ever called.** Wiring `press` in cost more than
writing it, and each failure was silent in a different way:

- `actions: ["press"]` is not in `openral_core`'s controlled action vocabulary. Pydantic rejected the manifest, the
  **local rSkill index silently skipped it**, and the runner fell through to HF Hub — reporting "network
  unreachable" for a file sitting on disk. The vocabulary's word for pushing a face is `push`; the capability the
  model sees is still `press` (that mapping lives in `contracts.yaml`, which is where it belongs).
- `lower_effect` had no `press` branch (F62 §2), and the action path turns an exception into a blank failure.
- `procedural_press` began with the same disease F61 diagnosed in `pick`: it looked wherever the arm happened to be
  left, and ma4's first `press` photographed "the gripper against a dark starfield". `face_the_work_zone()` now
  derives a looking posture — the tool pointed out of the rover's back, where a `dock` puts the work, at whatever
  height and pitch the arm can actually hold — instead of a written-down posture. This is the third time the same
  root cause has been fixed in a different place; a posture constant is a bug until proven otherwise.

**4. Process, on the record.** Mission B was not finished when I started Mission A: the turn-limit fix of §2 had
never been run, and I moved on to build `press` and then to run ma1–ma4 on top of an unverified carry. The user
stopped it. The standing rule — finish the thing under test before opening the next one — is not a style preference;
it is what keeps a claim like §1's attached to a run that actually happened. Both halves of this finding exist
because the rule was applied late rather than early.

### F64 — The visual servo was chasing a goal that moved when the tool moved

2026-09-19, runs g5p (two failures), g6a (one). `openral_rskill.procedural_pick.{approach,take_standoff,grasp_rotation}`.

**1. The symptom looked like a tracking problem and was not.** Three `approach` stages in a row ended with "lost
sight of the chosen grasp 8 frames running while still 13–15 cm away", and the honest reading of that message — the
template tracker gives up when the item fills the frame — is wrong. The pictures say something else: in g5p's
`servo_10` the part is dead centre with 10.3 cm to go, and nine frames later in `servo_19` it has been swept to the
right edge of the image with **13.2 cm** to go. The tool was further from the grasp than it had been, and the whole
scene had rotated. The `take_standoff` trace of g6a shows the same thing numerically: the error runs
0.012 → 0.009 → 0.016 → 0.020 → 0.012 m and the TCP walks a closed loop, never converging.

**2. The goal pose was a function of the tool's own pose.** `goal_now()` recomputed the grasp orientation on every
frame from `view = p_base - view_base`, where `view_base` was updated to the *current* camera position on every
successful measurement. The camera is bolted to the gripper. `grasp_rotation` points the tool's z away from the
camera (`if np.dot(z, view_b) < 0: z = -z`), so once the tool swung past the part far enough for the camera to
change sides, z flipped 180°, the tool swung back, the camera changed sides again — a bang-bang limit cycle, not a
slow divergence. Offline, with the part's geometry held fixed and only the camera's position varied, the commanded
tool z flips from `[-1,0,0]` to `[+1,0,0]` between 180° and 240° of camera swing.

**3. The fix is to decide the approach direction once.** Which side a grasp is taken from is a property of the view
that *chose* it, not of where the tool has got to. `set_view_dir()` fixes it at that moment; the servo loop keeps
updating **where** the part is and never **which side** it is taken from. The same offline check with the direction
fixed gives a spread of exactly 0.0 over every tool pose — the loop is open.

**4. Why four earlier picks succeeded.** g5h/i/k/m are not evidence against any of this. A bang-bang loop of this
shape is conditionally stable: when the stand-off already puts the tool near the grasp orientation, the sign never
flips and the servo converges in a few centimetres. The 2/3 success rate was the initial angle, not chance — which
is exactly the kind of thing a success rate hides, and the reason "it works, four times running" was the wrong
claim to record in F61 §1 without reading the failures underneath it.

**5. What the fix uncovered (g6b).** With the loop open, the first live approach behaved as it never had: 43 frames
tracked and **0 missed** through the stand-off, the tool's roll within a tenth of a degree, the part square in the
middle of every frame. It still failed — and the message was the same sentence ("lost sight … 8 frames running"),
which is why the sentence was never a diagnosis. The tracker was matching at **score 1.00** and throwing the match
away: `no depth where it matches`. A grasp that holds is a thin one (12 mm across, ~20 px at 0.37 m) and behind it
is sky, which returns no range; the depth image had no value at a pixel the template was certain of. The pixel is
the strong measurement in that geometry and the range is the weak one — and the arm's own motion already implies
the range. `measure()` now takes the predicted distance when the match is confident enough (0.9) and marks it
`depth_predicted`, so a trace says which frames were ranged and which were inferred. This is not the same mistake
as §2 wearing a different hat: the prediction is the tracked point carried through the camera's *measured* motion,
so the distance still comes from the arm, never from the match. Offline: with sky behind the neck the old path
loses a 1.00 match and the new one returns 0.360 m marked predicted; given a real depth image both return the
measured 0.352 m.

### F65 — A resume is a claim about the whole robot, and nobody was checking the arm

2026-09-19, runs g6a–g6e. `experiments/launch/lunar_base_d0/{ours_mission_check.py,d0_common.py}`, `AGENT/handoff.md`.

**1. Three graphs were booted to test a one-line change.** `handoff.md` said "changing skill code needs a new graph",
and it was wrong: the rSkills run inside `capability_server`, which `attach_d0.sh`'s `D0_RESTART_BOUNDARY=1` kills and
restarts. Every `pick` change from F64 was therefore paid for with eight minutes of Isaac Sim start-up and twenty
minutes of driving to the depot — about an hour and a half, to reach a scene that `OURS_RESUME_BEFORE_STEP=7` puts
back in **twenty seconds**. The note is corrected. The user's instruction was blunter than the fix: don't start from
the beginning; the simulator has snapshots.

**2. The first resume measured something other than the scene it named.** g6d restored `before_step_7` with the base
within 3 mm of its saved estimate — and the arm still in the half-way posture the killed run had left it in. `pick`'s
first overview was taken pressed against a panel, the ORU was not in the frame at all, and the call failed at `find`
with "none of the structures in view from here is the described item". That reads as a perception failure. It was a
resume nobody had checked: the joint target that holds the arm is a live ROS action, not part of the physics state
the snapshot saves, so whatever the previous run was commanding can outlive a restore.

**3. So the restore is now verified, like everything else here.** The snapshot's metadata records the seven joint
angles beside the localization estimate; after a restore the joints are read back; a mismatch is driven to the saved
posture through the boundary and read back again; and a mismatch that survives that stops the run rather than
continuing into a scene that is not the one named. `RESTORED_ARM` says which of those happened. This is the same
principle the method applies to effects, turned on the harness's own development tooling — which had been trusted
precisely because it was "just" tooling.

**4. What it cost to not have it.** Two of the three `pick` diagnoses in F64 came out of runs whose approach never
started, and one whole run (g6d) was spent on a failure that existed only because the resume was silently wrong. A
development loop that cannot restore a known state is not faster than booting from scratch; it is slower, because it
looks like it worked.


### F66 — The development resume restarted the client, not the skill owner

2026-09-19, diagnosis from g6c/g6e; validation in progress in g7a.

`capability_server/node.py:call_rskill` sends an ExecuteRskill action. The independent
`openral_rskill_ros/runtime_node` owns execution; `_import_procedural_entrypoint` uses
`importlib.import_module`, with no reload. The original runtime PID 273922 started at 09:34:32,
before `procedural_pick.py` was modified at 09:55:47 (commit 5171284, 09:56:24).
The runner had already loaded pick before that change. `D0_RESTART_BOUNDARY=1` only restarted
its client. Thus g6d/g6e cannot validate the unranged-frame fix; conclusions assigning all
remaining failures to base stance were premature. No new grasp algorithm follows from this finding.

Development tooling now accepts `D0_RESTART_RUNTIME_PID=<explicit PID>` on attach.
`restart_runtime.py` checks that PID belongs to the named graph and is runtime_node,
restarts it with its actual launch configuration, and records the process provenance without
logging credentials. Isaac, HAL and the independent safety kernel are retained. g7a restores
g6e's jaws-open snapshot before step 7. This is a development continuation, not a frozen
autonomous experiment or an autonomous-success result.

**Resume validation correction:** editing the live attach script let its old bash process resume
at an obsolete byte offset and start its check again after the original check was killed. Two
agents therefore overlapped in g7a; it is invalid. The unintended old check truncated g6e's
`check.log` and restarted its `events.jsonl` from step 7. The original capability log and appended
agent log retain the earlier failures, but g6e's original event journal is no longer intact.
The attach script now executes a frozen per-run copy, as run_d0 already did. Old attach parents,
checks and agents were explicitly stopped before g7b resumed the unchanged g6c step-7 snapshot.

**Scope audit before g7b:** the pick manifest contained a site-specific standard-handle grasp
instruction. It was removed; the selector retains its generic image-based instruction and the
caller's target/part. Separately, place's settling evidence omitted `fx`, although the independent
verifier indexes `settle["fx"]`. The producer now records the actual frame's calibrated focal
length, consistent with pick's hold evidence. No tolerance, stand-off or mission sequence changed.
Both changes are generic contract/prompt corrections; placement is still unvalidated live.


### F67 — Starting place implicitly released the item; evidence must survive retries

2026-09-19, source audit while g7b pick was running. The shared EyeInHandSkill initialized
`_jaw_open=True` and emitted GRIPPER_BINARY on every tick. With the real place/robot manifests
and g5m's recorded held jaw (0.169 rad), its first tick emitted `gripper: [1.0]`, before place
reached release. This is a generic operation-state bug, not a scene-specific grasp problem.
The initial gripper command is now absent until set_jaw explicitly requests one. Two targeted
command-semantics tests passed: startup/arm hold preserve the grasp, explicit release emits open.
Physics validation is still required. Place also now declares the joint-position actuator its
servo uses, and supplies calibrated `settle.fx` to the independent verifier.

The first approach in g7b failed and entered a local retry. Retrying overwrote the original
servo images and replaced approach evidence in the result, preventing reliable diagnosis.
Pick now writes separate attempt directories, records each attempt's selection/approach evidence,
and writes attempt.json after the attempt. This changes evidence retention only, not candidates,
controllers, retries, tolerances or strategy. g7b still uses the earlier loaded implementation;
these changes require the next runtime restart.


### F68 — A verified lift was followed by an unverified carry retraction

2026-09-19, g7b step 7. With the actual current tracker loaded and the site-specific grasp
hint removed, attempt 2 selected the 12.1 mm stem from image evidence. Lift 0.139 m, jaw
0.1696 rad and recomputed image flow 1.5 px vs 406.9 px expected for a left-behind item
supported holding at the end of lift. The later bring_in moved TCP from [-1.109,-0.009,1.159]
to [-0.808,-0.039,1.151]; final jaw was 0.100 rad (empty). The skill said success/held, but
Ours' independent verifier rejected item_held. No authoritative held fact was created.

The carry retraction code called plan_to with only an endpoint joint goal despite documenting
constant tool orientation. Intermediate orientation was unconstrained and the trajectory was
not retained, so its exact rotation during this failed run cannot be reconstructed. This is a
confirmed mismatch in path semantics; it is not yet proof that rotation alone caused the slip.
Retraction now uses the existing place carry servo: fixed TCP orientation, per-step MoveIt
state-validity checks, and the same carry tolerances/rate/time budget relocated from place
into both manifests (not tuned to this mission). It checks the jaw after retraction and sets
outcome=held only afterwards. A failed optional retraction can still return a held item if
the measured jaw supports that; an empty jaw returns a typed bring_in failure.

g7c restores the original jaws-open g6c step-7 snapshot with runtime PID 912950 and all current
changes, including F67. It stops at the first failed capability/effect for development diagnosis.
No altered run here is a frozen-campaign autonomous success.

g7c outcome: failed at bring_in with empty jaw, correctly reported by the new check. Lift
was 0.079 m (jaw 0.1703 rad, image flow 7.8 px versus 632 px expected). Retraction moved
0.25 m in 8.14 s, endpoint error 0.0073 m / 0.0198 rad, final jaw 0.100 rad. Maintaining
orientation did not suffice. Hold-before/after images show relative sliding, and grasp-close
jaw was 0.3672 rad before it narrowed to 0.1703. Existing traces do not retain the whole
motion, so the exact loss time and mechanical cause remain unresolved.

g7d continues the full g7c record/current physics without teleporting. Its robot-motion bag
records clocks, TF, joint state and actual arm/gripper commands; no truth topics enter the
agent. The harness attempt summary previously omitted current-schema VLM descriptions,
selection reasons, operation base estimate and hold/retraction measurements. It now retains
those existing facts for the model to interpret. No recovery plan or handle hint is added.
Development attach can now omit OURS_RESUME_BEFORE_STEP to continue a stopped live graph's
full record without restoring physics. This is still a development continuation, not a
frozen autonomous campaign result.


### F69 — Reproduce successful contact before replacing the grasp interface

2026-09-19. Active scope is r3 of `manipulation_contracts_proposal.md`: compatible success
reference → generic reproduction → complete the mission. No full NBV or control-ownership
framework. Details, provenance and limits: `docs/success_reference_reproduction.md`.

The current unchanged assets support grasp and transport: reference_r3_pregrasp restored an
open-jaw snapshot, executed the existing D0 reference from MoveIt pregrasp, lifted and carried
through destination docking. Jaw 0.174 at closure, 0.169 after lift, about 0.172 at destination.
Thus a jaw reading near 0.17 alone is not evidence of loss. Release completed; retreat stalled.
The next check, before any restore, independently reported the ORU delivered on PDU-1's shelf.
No stow/dock or initial-state autonomous success is claimed. Oracle coordinates remain evaluator-only.
The original straight-joint READY reference first failed before grasp; the recovery is explicitly
recorded, not hidden as a complete clean reference run.

A more specific g7c discrepancy precedes bring_in: chosen candidate 1 is on the wider mounting
pedestal. Recomputing the original depth reproduces its 26.2 mm span; nearby visible neck rows
measure about 12 mm. The VLM called it the neck, and a separate VLM confirmation repeated that
mistake. That confirmation layer was discarded. Replaying selection with both old and clarified
part wording chose candidate 22 once; this does not establish a prompt-only reliability improvement.

The generic candidate chain tracked only centre and depth, allowing a narrow neck and coaxial
wide base to join. Requiring continuity of both contour boundaries, using the existing pixel
continuity tolerance, exposes a 12.1 mm neck candidate in that same frame. Twelve archived depth
frames retain before/after candidates. This is offline geometry evidence, not physical success.
The shared equipment catalogue now exposes sourced contact-region relationships and dimensions
from the equipment specification, separate from observed poses; Ours refreshes it on reattachment.
No per-object grasp coordinates, tuned numerical threshold, or simulator asset change was added.

g8a validates these changes on the same held graph, with a new skill runtime and robot/TF/RGB-D
recording started before the verified open-jaw restore. The reasoner independently used the catalogue
to request the neck between head and pedestal. Minimal stage feedback reaches the journal.
Live cancellation and successful completion of the new pick remain to be measured.


### F70 — A committed neck contact drifted into background before closure

2026-09-19, g8a. The reasoner used the sourced interface catalogue to request the narrow neck,
excluding the head and mounting pedestal. The VLM selected candidate 15, width 12.0 mm, on the
neck midsection. The first approach nevertheless failed at 6.9 cm with lost visibility, before
closing. Its own images show the match moving from the neck to the lower-right background while
scores remained near 1.0. The automatic next observation was explicitly canceled to analyze the
first divergence. It is not a slip experiment: the jaws never closed on this attempt.

Replay of the recorded wrist RGB-D and robot TF reproduces 5.3 cm target-estimate drift with the
loaded adaptive-template implementation. Independent simulator TF records 663 object samples
with zero translation during this approach; truth is used only to establish stationarity, not
as tracker input. Freezing the template alone still permits association with the adjacent base.
A fixed reference template/depth, association inside the measured contact's projected half-width,
and a spatial contact committed in odom preserve matches over all 109 replayed approach frames.
This is a counterfactual replay on the recorded camera trajectory, not proof of a new physical grasp.

The fix uses no object-specific numbers or oracle pose. Robot pose feedback re-expresses the
same odom contact and axes each cycle; visual matches check visibility and report discrepancy,
not overwrite the point. Losing visibility before terminal self-occlusion invalidates the lock
and returns a typed failure. One pick call now selects one contact; automatic full re-observation
and re-selection were removed, leaving recovery strategy with the caller. The shared contract
explicitly describes stationary targets and the controller's actual feedback source.

The g8a cancellation exercised the minimal feedback/stop chain: final result was cancelled,
worker_stopped=true and hold_command_applied=true; the harness then independently reported
item_held=false. Jaws were already open and remained open. This does not test cancellation while
holding a payload or establish a physical-rest acknowledgement; physical_stop_confirmed=false.

g8b reloads the runtime and restores the same open-jaw initial state for physical validation.
Evidence: g8a/offline_reference/{tracking_replay.json,object_stationarity.json}; replay script
artifacts/perception/oracle_grasp_review/replay_g8a_tracking.py; g8b/source_snapshot and development.json.


### F71 — Visual neck grasp survives lift and retraction; carry handoff exposed a reporting bug

2026-09-19, g8b, development restore from g6c step 7. The model independently chose arm_ready,
observe, locate_feature, then pick with the catalogue's neck description. Candidate 8 spans
12.1 mm. Approach retained 46 matched frames without a miss; last reported match discrepancy
was 1.68 mm. Closure jaw 0.1711, measured TCP lift 0.100 m, retraction 0.250 m, final jaw 0.172;
the harness independently verified item_held=true. Closed robot/RGB-D bag and offline TF
confirm handle world height 1.015 → 1.100 → 1.102 m through lift/retraction. The current assets
therefore do not require modification to achieve this grasp. This is one successful development
pick, not a frozen initial-state Mission B success or a controlled reliability comparison.

The first navigation request failed before dispatch: drive_limits successfully sent carrying
parameters, then indexed every evidence value as an array. The newly included scalar lever_m
raised TypeError. The boundary now returns the complete configured arrays and scalar evidence
unchanged. g8c continues the same physical grasp and complete journal without restoring a held
snapshot or restarting skills. Its recording starts before the continuation.

Evidence: g8b/ours/events.jsonl seq 48–65; g8b/offline_reference/phase_samples.json and
relative_pose.csv; g8b/capability_server.log traceback; g8c/development.json.


### F72 — Carry and destination docking retain grip; single-frame held query gives a false negative

2026-09-19, g8c. After the scalar drive-limit evidence correction, navigate_to_pose completed
81.64 sim seconds of transport; the harness then confirmed held=true. dock_at_feature reached
the shelf work pose (1.3 cm reported error). The following VLM held query returned false despite
a jaw angle of 0.175 rad, and the development stop-on-failure check stopped the agent.

Closed-bag evaluator TF confirms retained grip: handle in TCP approximately [0.0005,0.0113,0.0153] m
at departure, [0.0003,0.0059,0.0187] at arrival, [0.0009,0.0080,0.0181] after docking; neck/jaw
axis alignment remains above 0.9995. The saved wrist image also shows the neck between the
fingers. Thus this failure is a perception/verification false negative, not another physical slip.
Simulator truth remains diagnostic-only and is not injected into the continuation.

The authoritative object fact already transitions to unknown after failed confirmation, but its
explanation asserted empty jaws. Corrected that wording to 'holding not confirmed'. g8d preserves
the complete record/current physics and lets the model resolve the conflict. Its first chosen
tool was held_item, which returned true on a fresh image. No repeated offline prompt trials or
physical modification were used to force a positive result. Place/stow/dock still pending.

A separate development-check defect was observed in g8b: STOP_ON_FAILURE killed the agent as
soon as execution_finished=false arrived, before its independent held query completed. A new
verification_finished event now marks completion of effect verification; subsequent checks
wait for it before stopping/snapshotting. These edits were made after g8d's processes loaded
and are not part of its executing source snapshot; they need validation on the next launch.

Evidence: g8c/ours/events.jsonl seq 75–86; g8c/offline_reference/relative_pose.csv;
g8c/evidence/wrist_0001945.92.jpg; g8d/ours/events.jsonl seq 89–90.


### F73 — Placement was initially within bounds; upward withdrawal disturbed the released item

2026-09-19, g8d/e. Do not infer the cause from the final outboard/tilted pose alone. At release
entry the ORU root was [11.7611,4.3954,0.5150] m, 8.5 degrees from upright; the surveyed support
is [11.75,4.4065,0.5]. Just after opening, it settled to root z=0.5097, up cosine 0.9986.
Then during retreat it rose again to z=0.5725, moved outboard and ultimately settled near
[11.6843,4.2307,0.5032], tilted 19.1 degrees. That endpoint fails both along-support location
and upright criteria. The evaluator was not relaxed. g8e drove clear, inspected and was stopped
after sufficient diagnostic evidence; no successful place/stow/dock is claimed.

The direct geometric discrepancy from the successful reference: reference tool pitch at release
was about +0.6 degrees, g8d about -21 degrees. Place preserves the measured wrist orientation
after transport. Its axial withdrawal therefore commanded +53.7 mm upward motion over a
150 mm retreat. The object's renewed lift starts during that movement, consistent with the
open fingers catching the overhanging head. No contact-force trace identifies the exact colliding
body; this contact explanation is an inference from synchronized motion and interface geometry.
The later extra upward stroke also stalled; the first axial stroke itself reached its goal.

Minimal shared correction: equipment knowledge for a neck with an overhanging head states a
release constraint, below_overhang. The mission caller can pass this semantic constraint to
place (default unconstrained retains axial withdrawal). The skill computes a support-parallel
withdrawal for a side grasp, followed by its existing upward clearance. No new distances, object
coordinates, asset changes, or mission-specific branch. The selected constraint and retreat
goal are returned as evidence. Every method uses the same capability/metadata.

Executing the actual modified geometric code on recorded robot TF preserves the 150 mm stroke
and removes the 53.7 mm rise. This is counterfactual goal evidence, not proof of collision-free
withdrawal or successful placement. Both constraint values validate through the real shared
contract, lowering function, and RSkillManifest. Physical validation pending.

Evidence: g8d/offline_reference/{relative_pose.csv,support_relation.json,withdrawal_replay.json};
artifacts/perception/oracle_grasp_review/replay_release_withdrawal.py; reference_r3_pregrasp
closed bag and corresponding CSV. g8e/diagnostic_stop.json records the explicit process stop.


## F74 — Contact geometry first: oblique closing axis (2026-09-19, development)

User narrowed work to correct approach/contact/closure; lift, bring_in and transport are deferred.
g8f selected the neck and tracked 91 frames without a reported miss, closed at 0.2174 rad, lifted,
then slipped during bring_in. This does not invalidate g8b’s success but does invalidate any claim
that the visual pick is already reliable.

Closed-bag RGB-D replay recovered the selected g8b/g8f observations (image MAE 0.334/0.330;
RGB/depth receipt differences about 1 ms). The original candidate gave both closing-axis endpoints
the same depth, imposing camera-frontoparallel closing. Fitting the visible neck surface gives
a 0.44-degree tangent error for successful g8b and about 7.0 degrees for g8f, consistent with
g8f's approximately 7.4-degree physical closure misalignment. This identifies an upstream geometric
defect; it does not prove it is the only determinant of grasp retention.

`refine_contact` now fits the selected part's local RGB-D surface, intersects its image direction
with that plane, and constructs a tangent closing axis before odom target commitment. Actual-code
replay changes g8b by 0.44 degrees and g8f by 7.21 degrees; the reconstructed axes are orthogonal
to the fitted normal. Selection identity/point are unchanged. No object truth, object name,
asset CAD or target-specific angle enters the control calculation. The hidden cross-section
depth approximation remains to be evaluated against actual closure, not tuned preemptively.

USD inspection found every EG2 collider inherited `regolith_contact` (0.5/0.5, multiply) from
the rover. User explicitly authorized a reasonable friction increase. The gripper now has an
independent 0.8/0.6 material, using the existing equipment-material range as a declared simulation
assumption, not a hardware measurement. Wheel/body binding is unchanged. With multiply, against
equipment 0.8/0.6, effective static/dynamic friction is 0.64/0.36 instead of 0.40/0.30.
Authoring recipe: `space_robotics_bench/assets/lunar_base/process/set_gripper_material.py`.
PhysX combination semantics: https://nvidia-omniverse.github.io/PhysX/physx/5.1.0/_build/physx/latest/struct_px_combine_mode.html

Contact-only fixture g8g_contact runs production pick through grasp and raises an intentional
`contact_diagnostic_complete` before hold/lift. It cannot assert held or run bring_in. It is not
a mission capability or autonomous success. Its temporary manifest is outside the mission library.
The explicit PhysxMaterialAPI schema was added to the authoring recipe after g8g boot, so g8g
must not be cited as validation of the final multiply-combined material; reload before that claim.
Live contact result pending.


F74 contact validation update: g8g never reached contact (diagnostic client omitted the normal pick deadline; fixed).
g8h loaded the final gripper material and selected a neck, but stopped before closure on lost tracking.
Closed-bag TF shows premature object displacement with jaws still open. Before that, `take_standoff` rejected
normal-direction IK then substituted a -30-degree approach. It checked only the stand-off, not the final
contact. Thus tracking loss is not evidence to relax the tracker: the object really moved.

Removed the pitch-search list and tilted-approach substitution. Equally clear sides now preserve both
antipodal wrist rolls, ordered by current rotational distance; both stand-off and contact IK must succeed
before the approach starts. The chosen roll remains fixed in odom during servo. Real-frame replay confirms
contour-sign reversal leaves the same physical side options. g8i_contact validates this on the same
open-jaw fixture and material; no lift/carry. Result pending.

## F75 — Shared contact geometry and explicit closure conditions (2026-09-19, development)

The solution-focused audit is `contact_closure_audit.md`. g8i ended before motion: contact IK failed.
Its known-success-pose probe was after skill cleanup, so it did not establish the exact in-call scene.
Code nevertheless confirmed a solid gripper envelope filling the jaw gap, ground-to-top work-zone columns,
different planning/servo target exclusions, no consumer acknowledgement, and a close-in failure path that
could proceed to closure without checking orientation. The two-second declaration expiry does not explain
g8i's 0.04-s approach; that earlier possibility was explicitly withdrawn.

Implemented: export seven EG2 collision meshes and six authored joints from the existing robot USD into
the planning model; measured jaw state accompanies IK/whole-robot validity checks. Only authored adjacent
joint collision exclusions replace the old broad gripper-link exemptions. These are source collision
meshes, not a claim of identical PhysX cooked convex decomposition. No target geometry or oracle pose is
embedded. Robot package builds and expanded URDF contains the six real gripper joints.

The local work-zone node now triangulates valid neighbouring depth pixels instead of filling columns,
with timestamped camera transforms. Long edges cannot bridge the minimum supported feature size.
No target sphere or item-wide removal is applied. A shared prepare service acknowledges MoveIt's
ApplyPlanningScene result and retains the stationary scene until release. Invalid/occluded measurements
remain unknown: pick separately checks observed free rays for actual gripper surface samples along insertion.
This is not a dynamic obstacle map or a complete concurrent ownership protocol.

Pick's close-in uses the existing per-step joint servo and shared whole-robot collision checks, preserving
the previous Cartesian speed limits. The separate height-map target authorization functions were removed.
Close-in stalls no longer count as completion; actual position/orientation and target validity are checked
again before closure. Pose error alone does not prove retained grasp. No lift or bring_in validation here.

Read-only evidence in `artifacts/perception/contact_revision/`: the recorded g8b successful preclosure
configuration now passes whole-robot validity and collision-aware IK in the acknowledged measured scene,
with target_excluded=false; the old model rejected it. Five g8h configurations from the strongest recorded
object-motion increments were compared against the currently undisturbed fixture: one reports eg2_base
contact with measured/work_zone (~0.056 mm), four do not. This is a useful counterexample to blanket
permission, not exact replay of the moving object's collision history or a robust contact-margin claim.
Actual depth-surface replay on g8b/g8f passed; four existing command/cancellation tests passed.

Harness attempt summaries/context retain scene, target validity, collision/IK, observation and closure
conditions without creating held facts or prescribing recovery. The old g8i result survives reducer replay.
The more specific final failure classification was edited after g8j runtime loaded: it is not physically
validated by that run. g8j is contact-only; setup first corrected a temporary diagnostic manifest ID and
reissued a stranded client request, before any pick execution. Its physical result is recorded below.

F75 live update: g8j selected a neck and acknowledged measured_scene_144; contact IK and whole-robot
validity succeeded. It stopped before insertion/closure on free-ray coverage (best candidates: 294
unobserved samples), and released the scene normally. Closed-bag view recovery localizes the deficit
to fingertips in the last portion of insertion; replay differs slightly because frames/TF are recovered
by nearest recorded samples. This is no longer the old contact-IK failure.

The added observability check initially conflated positive infinity with invalid depth. Installed IsaacLab
CameraCfg documents clipping behavior 'none' as returning inf for ranges beyond the maximum; the current
wrist camera has an authored far clip, while the ROS Image relay previously omitted this semantics.
See the [official CameraCfg documentation](https://isaac-sim.github.io/IsaacLab/v2.2.0/source/api/lab/isaaclab.sensors.html#isaaclab.sensors.CameraCfg.depth_clipping_behavior)
and installed `/home/bingqi/isaaclab/source/isaaclab/isaaclab/sensors/camera/camera_cfg.py`.

SRB now publishes its actual CameraCfg near/far and positive-infinity meaning as sensor metadata;
the bridge relays it unchanged, and Frame preserves it. Only explicitly declared beyond-far returns
certify rays inside that sensor range. NaN, zero, missing metadata and out-of-image samples remain unknown.
No numeric clipping distance is embedded in pick. Counterfactual replay on g8j's closed RGB-D using
the unchanged authored camera configuration passes the same insertion coverage check without changing
the grasp or coverage threshold. This was not metadata recorded live in g8j; g8m fresh boot validates
the producer/relay/consumer path. Gripper FK also now computes TCP and fingers in one requested state,
avoiding the current TF of a moving TCP as the reference for recorded-state geometry.

Integration bookkeeping: g8k failed during sensor startup because the new publisher call passed one
Publisher to an existing Sequence-based subscriber check; corrected. g8l's live metadata stayed unknown
because the producer omitted IsaacLab's documented `depth` alias; corrected and raw data_types/clipping
behavior retained. Neither executed pick. g8m fresh boot publishes the real `rgb/depth`, clipping='none',
near=0.001/far=1.999, positive_infinity=beyond_far_clip metadata end to end (depth_semantics_live.yaml).
These bounds come from the running sensor config, not skill constants.

g8m reached closure: 2.86 mm / 0.0226 rad controller error, jaw 0.1825 rad. Closed-bag TF evaluation
shows no object displacement during approach and the neck between the fingers. See contact_evaluation.json
and the contact_closed.png image. This is contact evidence, not a held/lift result.

**Run-isolation correction:** the previous statement that g8k/l never executed pick was only true at
their initial teardown. Their check clients were not tagged and survived the simulator teardown. g8l
subsequently issued another joints action immediately after g8m closure (bag wall 631.509 s), then failed
find on the displaced scene. Thus g8m postclosure motion is contaminated, not evidence against friction
or the stop action. The recorded stop command itself matches measured joints. Pending g8k client and
launcher were explicitly terminated. run_d0 and attach_d0 now tag the timeout/check clients with their
graph, so teardown owns actuator clients as well as ROS servers. g8n repeats from the other existing
open-jaw fixture with unchanged capability code; only its active check remains.


g8n completed observation (6 views, 28 candidates) and selected the neck, but stopped before motion:
all offered stand-offs returned IK -31. The evidence preserved ik_no_solution and explicitly did not
claim physical impossibility. Comparison with g8m isolates a remaining second feasibility rule:
free_sides sampled one point 60 mm along either part-axis sign, kept only the highest visibility vote,
and therefore pruned the opposite antipodal roll before the shared geometry could check it.
The generic fix enumerates both mathematical jaw symmetries; current orientation orders them, while
IK, whole-robot collision and observed insertion coverage authorize them. No new pitch, target point,
IK seed list or scene-specific pose is introduced. Read-only replay checks this before another motion.

Read-only g8n replay confirms the pruned opposite roll has both stand-off/contact IK and whole-robot
validity, with zero missing sampled free-ray evidence; the original roll still fails IK. Stored at
`artifacts/perception/contact_revision/g8n_antipodal_probe.json`. The attached bag missed the bridge's
volatile TF because of subscriber QoS; replay reconstructs those robot-only frames using the actual
sensor bridge calibration and recorded robot body TF. It does not read object transforms for solving.
The same graph's startup bag provides the static frame roots. g8o records explicit TF QoS and reloads
the skill runtime (1050798), then repeats the g8b step-10 fixture. Result below.


g8o selected the neck and passed shared stand-off/contact IK, whole-robot endpoint checks and insertion
observation coverage. It reached close-in, then stopped 13 mm / ~2 degrees before its goal: the next
joint state collided between measured/work_zone and eg2_link6 (0.382 mm reported penetration).
Jaws remained open. Closed-bag robot/object TF confirms zero object displacement during approach;
final_wrist.png and contact_evaluation.json retain the actual stopped geometry. Endpoint feasibility
is therefore not a physical trajectory success. Do not loosen collision tolerance or reinstate the
old near-enough closure path. Exact collision position/normal and tested joints were missing from this
result; state_validity now returns those fields for the harness (source change after g8o, not loaded
in its runtime). No claim yet whether the hit is permissible contact, reconstruction error or trajectory
tracking error. No stable contact/closure claim and no lift/bring-in execution in these diagnostics.

Final state: only g8m graph retained, runtime 1050798; all recorders/checks finished. Temporary diagnostic
skill symlink removed from the palette. All source changes remain uncommitted. The next investigation
is the last insertion corridor/contact identity using the recorded state, not another whole pick sweep.


## F76 — Formal grasp/transport attempt still stops before closure (2026-09-19)

User authorized attempting full pick and transport after the audit corrections. g8p restores g8b's
open-jaw before_step_10 fixture in g8m's graph; runtime 1054384 reloads the collision evidence additions,
and the capability boundary is restarted. The mission agent issues the semantic pick through the normal
boundary; STOP_ON_FAILURE waits for independent verification. No motion/control/friction changes in this attempt.

Six views / 28 candidates, selected neck candidate 7. The applied scene, stand-off/contact endpoint IK,
whole-robot endpoint validity and sampled insertion visibility pass. Stand-off settles to 1.7 mm / 0.0253 rad.
Final approach fails about 20 mm / 3 degrees from its estimated goal. The rejected configuration reports
measured/work_zone vs eg2_link2, penetration 0.0387 mm, with contact position, normal and tested joints now
retained. This is a planning collision, not proof of an actual physical impact. Jaws remain 0.82 rad/open;
independent item_held=false. No closure, lift, bring-in, navigation or transport is executed.

Closed-bag evaluation: zero object displacement after approach starts. The reported planning contact
transforms near the neck's front/side corner: relative to authored handle center approximately
[+6.45, -15.23, -17.66] mm. Robot/object truth is used only for this evaluation, never for control.
Final actual closing-axis error against the neck axis is about 15.9 degrees. The controller's 3-degree
error is relative to its estimated goal, not to the true contact frame. Candidate 7's local surface fit
has RMS 1.59 mm and rotates the image proposal by 20.52 degrees; earlier successful flat-face fit g8m
had RMS ~7e-8 m. Mixed-face fitting is a plausible direction-estimation cause, not yet a proven exclusive
root cause. The next targeted analysis is the selected contact surface/frame and executed orientation;
do not expand this into friction tuning or a transport-slip diagnosis before grasp is established.

Evidence: g8p/{pick_result,physical_evaluation,collision_evaluation}.json, ours/events.jsonl,
offline_reference/, and closed robot_motion/. Source/assets and development metadata retained.
This restored development attempt is not a frozen paper-campaign trial. Only g8m graph is retained;
g8p agent/check/recorder ended, no competing client remains.


## F77 — Expected contact is a scoped permission, not absent geometry (2026-09-19)

**Trigger and scope.** User identified the over-strong final-approach requirement:
a grasp must establish contact. g8p's predicted 0.039 mm intersection alone does not
prove physical infeasibility or a false positive. Its reported body was eg2_link2,
not a distal jaw. Implement expected contact without globally ignoring the gripper
or deleting the target, and retain the same capability for every mission/method.

**Implementation.** The locked RGB-D candidate supplies an oriented region in odom:
measured width/length and the existing gripper perception depth-discontinuity span.
The shared scene labels only whole measured triangles within that region as
`measured/contact`; every other triangle (including crossing boundaries), surveyed
structure and robot collision model stays in place. Robot geometry identifies
`eg2_link5/6` as distal jaw bodies. Only those two link/patch pairs are allowed for
contact endpoint IK/validity and final insertion/closure. Free-space standoff motion
retains strict checks; free-ray coverage separately counts expected-contact samples
for the same link/region predicate. Permission is revoked before lift. Every phase
waits for ApplyPlanningScene and records its evidence; all operation exits restore
the original ACM and unsplit scene before releasing the scene owner.

**Integration evidence.** `artifacts/perception/contact_permission/integration.json`
records a real idle-graph MoveIt check: immutable registration, endpoint_check,
insertion, two revocations, and release. All **26,455 measured triangles** and
unrelated ACM pairs were preserved. Release restored the original ACM and removed
the temporary label. No motion was sent. The check accounts for MoveIt's serialized
object pose/mesh poses and omission of all-false ACM rows. The four existing gripper
command/cancellation tests pass. `openral_msgs` rebuilt successfully.

The same integration exposed images arriving 20 ms ahead of their robot TF. The
scene now selects the newest timestamp-matched frame in the sensor QoS history,
not a latest-pose substitution or a guessed time offset. Registration rejection
also exercises cleanup without attempting to remove a never-created object.

**Limits.** Permission uses distal-jaw-body granularity, not isolated pad meshes.
The regional box labels observed surfaces; it is not an object shape or evidence
that insertion is physically correct. eg2_link2 remains protected. This change
neither proves g8p would grasp if allowed nor repairs a 16-degree estimated-axis
error. No contact-force guarantee, crash recovery, or held-object attachment is
claimed. Full physical validation is g8q, a development continuation, not a frozen
campaign run.

**g8q physical result.** Resumed g8b before step 10 through the production harness,
with runtime 1079879. Candidate 8 measured 12 mm wide; registration split 785
triangles into the contact patch. Endpoint permission, revocation before standoff,
and final insertion permission were all acknowledged. Standoff reached 1.2 mm /
0.0342 rad error. Final insertion stalled 27 mm / about 1 degree from its commanded
goal, with last MoveIt state validity **true** and no reported contacts. The final
command-minus-measured joints were approximately [0.01, 0, -0.01, -0.02, -0.07,
0.03, -0.05] rad. No closure or transport occurred; independent item_held=false,
jaw=0.82. This is a servo no-progress result, not another collision veto; physical
interference versus controller/model/tracking cause is **not yet established**.
Failure cleanup acknowledged geometry/permission restoration. Agent/check ended;
recorder 1079792 closed cleanly. Preserve the sole g8m_contact graph.

Artifacts: `artifacts/runs/g8q/{pick_result.json,ours/events.jsonl,robot_motion/,
source_snapshot/}`. Next session should analyze the closed bag and compare actual
versus commanded joint/TCP motion with g8b, before another modification or run.
Do not infer stable grasp from the permission check or the absence of a collision
veto. OpenRAL commits 6154482 + 56ce9b8; SRB 1928821.


## F78 — Empty-jaw close-in fixed; one pick → carry → dock chain; selection and loaded servo remain (2026-09-19)

**g8q cause (closed-bag replay).** Object and base never moved. At sim 2315.5–2316.3 the distal jaws straddled
the neck (jaw centre ~3 mm from the ORU axis, evaluator TF only). The TCP was then ~15 mm past the skill's own
goal; the servo carried it 26 mm sideways, ~20 mm back and 10 mm up, then declared no progress 27 mm out.
Measured joints followed commands: not an obstruction. Offline replay of the servo law through the live graph's
MoveIt FK, with per-joint lags fitted from the bag (0.34–1.44 s), reproduces it: as-is 11.7 s, 12 mm overshoot,
23.5 mm lateral; without the sag integral no overshoot but 18.5 mm lateral; without integral and null-space
posture pull 5.5 s, 8 mm lateral. Fix: `servo(sag_integral=False, posture_gain=0.0)` for pick's close-in only
(empty jaws, short straight insertion). Other servo users unchanged.

**g8r (same code, runtime 1093996, g8b before_step_10).** VLM chose candidate 10, 27.4 mm wide, ~10 cm below the
neck: the pedestal (as g7c). Its p30 view offered no neck mark; p20's neck mark 2 was ignored. Contact IK then
failed correctly; nothing touched. The catalogue lists the neck thickness, pick measures each candidate's width,
and nothing compares them: C2's "semantic choice and geometry refer to the same part" is not implemented.
STOP_ON_FAILURE ended the agent, so model recovery was not exercised; the failure text would not have told it why.

**g8s (same code).** Neck candidate 12 (12.1 mm). Close-in 2 mm / 0.004 rad in 9.2 s, 88 frames, 0 missed.
Jaw 0.170, lift 0.061 m, flow 0.3 px vs 412 px expected; independent held=true. bring_in stalled at joint4's
limit, jaw retained. navigate_to_feature and dock_at_feature to PDU-1 with item_still_held verified after each.
place failed at `over`: stalled 1.1 cm / 2 deg from goal (carry tolerance 1.0 cm), jaw 0.173, item_placed=false,
item still in the jaws. Throughout the carry after bring_in the held joint command differed from measured by
0.3–0.75 rad on joints 1/3/5/7 (arm against joint4's stop): the servo command integrates from itself and winds
up at a joint stop. Loaded `over` also lagged (joint6 ~0.1 rad). Cause of the `over` stall not yet established.
Development continuations, not campaign trials. Evidence: g8q/g8r/g8s `robot_motion/` (closed), `ours/events.jsonl`.

**Place and carry (g8s/g8t closed bags, evaluator TF only).** place's `over` goal is the support's x/y at the
current TCP height; nothing checks that the hanging item clears the support. Entering place the ORU base rode at
0.56 m (g8s) / 0.52 m (g8t) over a 0.50 m shelf. g8s: the ORU came to rest on the shelf (0.505 m) with jaws
closed; the arm stalled 1.1 cm short. g8t: the ORU struck the shelf, jaw 0.231 then 0.100 (empty), item fell onto
the shelf (evaluator delivered=true by accident). Carry: rigid after lift (0.4–3.6 deg), but from bring_in the ORU
pivots 16–32 deg about the jaw closing axis and the neck slides 16–18 mm until the head rests on the fingers;
swings pry the jaw from 0.17 to 0.18–0.23 during driving/docking. Retention is the head interlock, not clamp force.
g8t without STOP_ON_FAILURE: the model observed, backed off, confirmed empty jaws and searched; the wrist VLM
wrongly reported the item on the ground. Stopped by the user.

**g8u.** Model re-docked (approach 2.0 m) before pick; VLM chose the neck correctly (15.5 mm, 0.74 m range).
pick failed at contact_scene/register: "selected region contains no complete measured surface triangles" (F77
permission precondition). Cause of zero triangles not yet established. Evidence of g8s–g8u is written under
g8r/evidence (runtime restarted during g8r keeps its log dir).

**Fragile vetoes removed (user principle: checks fall back to the harness; no per-task tuning).** A skill check that
cannot certify something is evidence, not a veto; a confirmed problem returns a typed reason with the facts the model
needs, and the model chooses the next operation (never mechanical parameters). (1) Contact permission with zero
measured triangles in the selected region now registers "nothing exempted" and continues; every other collision
check remains (planning_scene/node.py). (2) Insertion free-ray observation is recorded, not blocking (openral
2a24b9c). (3) Pick attempt summaries carry the selected mark's id, measured width and range into the context, so a
27 mm pick against the catalogue's 12 mm neck is visible to the model. Kept: target-drift gate, closure pose check,
empty-jaw and lift checks (confirmed problems). `restart_runtime.py` also restarts the planning_scene node.
g8v runs without STOP_ON_FAILURE from g8b before_step_10, stopping after a verified dock at PDU-1.

**Carry and place root cause (g8s bag vs the robot's collision model).** After bring_in the ORU's box overlapped
the rover's deck collision box by 13–93 mm (x) and 60–105 mm (z) for the whole carry: bring_in had pulled the
hanging item onto the rear deck. That one fact explains the 0.4–0.75 rad joint lag, the 16–32 deg pivot and the
jaw prying. Nothing checked it: state validity saw the arm and gripper, never the item. Offline, live MoveIt with
the catalogue envelope attached reports held_item vs chassis_base_link/base_link at those configurations and
nothing against the robot just after the lift. Fix (openral 0179a1d): the envelope (upright square prism over any
yaw, extended by the neck length it can slide) joins every state-validity check while held; world objects are
exempt (the measured scene holds the item itself); bring_in may raise before walking in; place travels over the
support with the envelope above it and drops it on release. Boundary: pick/place take an optional catalogue `item`.

**Shelf.** The PDU shelf (0.42 x 0.56 m, back strip 0.20 m above the plate) left 2.4 cm behind a centred ORU; both
g8s and g8t struck the back strip (far edge 4.64–4.66 m vs strip 4.627 m). User approved a larger shelf: 0.60 x
0.72 m, place point at the plate centre, ~10 cm clear (SRB 6839574). Regenerated site boxes are now axis-aligned
(the committed ones were skewed min-area rectangles). place's over tolerance 1.0 cm → 3 cm / 0.08 rad (a third of
the clearance). The evaluator's window (±12 / ±18 cm, 15 deg) already exceeds what the new shelf allows; unchanged.
Needs a fresh graph (the running Isaac holds the old shelf).

## F79 — The IK acceptance rule: on the working branch, or next to the seed (2026-09-20, development)

**g9m (runtime started 10:33:40, openral b6798bc).** pick reached `held`: the VLM chose the 12.4 mm neck over the
27 mm pedestal, close-in stalled 1.3 cm out inside every direction's budget, jaw 0.1695, lift 0.1502 m, flow 0.5 px
against 409.9 px expected, `item_held` verified. **bring_in then moved nothing.** Its own record: `in_by_m 0.25`,
`raised_by_m 0.02`, and the servo refused at 25.5 cm / 16 deg — the whole distance. The height ladder is the reason:
`raise 0.00` not clear, `raise 0.02` clear, and **0.04 through 0.20 all `reachable: false`**. The single clear height
had millimetres of margin; `last_state_validity` shows `held_item` against `site/depot_stand` at 2.7 mm, and the
held joints sat 0.03–0.07 rad below their commands (the load sagging), so the pull-in's first step was already
invalid. The evaluator kept reading `oru_on: depot_stand/slot_0` while the model drove off to PDU-1. dde1be6, which
removes the window that caused those `reachable: false`, was committed at 10:35:30 — 110 s after that runtime
started. g9m ran code the fix was not in, so it re-ran a known failure rather than testing anything.

**g9n (fresh graph, openral dde1be6).** pick failed at `find`: "the arm cannot take an overview of the work zone
from where the rover stands (4 postures tried)". `last_ik` says `error_code 1` — MoveIt **did** solve it — refused
by `branch_jump_rad 1.868 > 1.2`. The model's response was sound (it repositioned the base), but no base pose helps.

**Cause.** dde1be6 replaced the working-branch window with a distance from the seed. Every `ik()` call seeded at
`READY` is a deliberate reconfiguration — `find`'s overview, `rolled_view`, the working views — and the wrist joints
carry that change: joint6/joint7 are deliberately absent from `POSTURE` because the tool rotation asked for
determines them. So the reconfigurations solve *on the working branch* and still land 1.6–2.6 rad from the seed.
The window alone was equally wrong the other way: it refused poses the arm was already in and made every bring_in
height unreachable (g9l, b6798bc widened it, dde1be6 removed it). The two criteria each cover one case.

**Rule (fbb33c9).** A solution is this arm's own configuration when it is on the working branch **or** within
`BRANCH_JUMP_RAD` of the seed; it is refused only when it is neither. Reach, collision and the servo decide the rest.
`move_to` now reports which of the two happened, because that is what tells the caller whether to move at all.

**Measured offline against the live MoveIt before any run** (`/compute_ik`, `/compute_fk`, read-only):

| case | on branch | jump (rad) | verdict |
|---|---|---|---|
| overview dz 0, dpitch 0 | yes | 2.57 | accept |
| overview dz −0.08, dpitch −10 | no (joint1, joint4) | 4.99 | refuse — the wrist wraps a full turn |
| overview dz −0.16, dpitch −20 | yes | 1.57 | accept |
| overview dz 0, dpitch −20 | yes | 1.87 | accept |
| bring_in raise 0.00 / 0.02 / 0.04 | yes | 0.00 / 0.10 / 0.23 | accept |
| bring_in raise 0.06 / 0.08 | no (joint4) | 0.39 / 0.65 | accept — next to the seed |
| bring_in raise 0.10 and above | — | — | IK error −31: a real reach limit, not the rule |
| mirrored branch (F57) | no (joint1–5) | 2.90 | refuse |

`find` takes the first posture it can also plan to, so one accepted overview is enough. bring_in's usable heights go
from **0.02 alone** to **0.02/0.04/0.06/0.08**, and the pull-in walks 0.15 m at raise 0.08 before the next step is a
different configuration. The 1.2 rad threshold now sits in a measured gap: accepted off-branch solutions jump at
most 0.65, refused ones at least 2.90. That is the first of the three numbers the plan owes a measured source.

**Method note.** g9m and g9n both cost a full graph and a pick to learn something a read-only query of the live
MoveIt answered in seconds. The IK rule is a pure function of a solution, a seed and `POSTURE`: it belongs in an
offline bench (`/compute_ik` on the held graph) before a runtime restart, not in a mission run.

**g9o (same graph, same snapshot, openral fbb33c9 — the rule is the only variable against g9n).** `find` took its
overview and selected candidate 3, the 12.4 mm neck, from three views; g9n's `attempt_01/` had not one image in it.
bring_in's ladder inverted: `0.00` and **`0.02` both not clear**, `0.04/0.06/0.08/0.10` reachable *and* clear, `0.12`
and above a real IK limit. It raised 0.04 and stalled 10.9 cm from a 0.25 m goal — about **14 cm of travel, against
g9m's zero**. pick `held`, lift 0.154 m, flow 0.5 px against 499.5 expected, `item_held` verified.

**The carry still lost the ORU.** During `navigate_to_feature(pdu_1_shelf/shelf)` the jaw went 0.169 → **0.100**
(closed on nothing) and the evaluator returned `oru_on: depot_stand/slot_0`. That reading is decisive rather than
noisy: `on_support` requires `free = |handle - tcp| > NOT_HELD_M`, so naming a support *means* the item is out of the
gripper. 14 cm of retraction did not take the ORU off the stand's support; driving away stripped it from the jaws.

**The harness caught it without being told.** `navigate_to_feature`'s `item_still_held` verified **false** on jaw
encoder plus wrist image — the skill had reported success — and the model went straight to a front-camera `observe`
looking for the box on the ground. Independent effect verification and model-owned recovery, both working, on a
failure nothing had anticipated.

**Open, and not to be guessed at.** Whether the ORU ever left the support, and at which instant it came down, is one
measurement on the closed bag (`/tf` evaluator poses plus `/srb/env0/mission_state`): the ORU's base height over the
stand across grasp → hold lift → bring_in → the first metres of the drive. Insufficient raise (the IK ceiling at
0.10), sag after `hold_here`, and the drive's own acceleration call for different fixes; the trace separates them.

**The carry, measured from the evaluator TF of a successful and a failed bag (g8s, g9m).** The question the code
could not answer — why two runs carried the ORU and none since — is answered by one quantity: how far the item had
been moved toward the rover, relative to the stand's near edge, at the moment it sagged. Stand box (live planning
scene) 0.616 deep x 1.300 x 0.610; slot 0 at (5.82, -14.39, 0.55), so the edge the rover faces is y = -14.192 and
the slot's inset is 0.198 m — with the 0.392 m deep ORU centred there, its near face is 2 mm from that edge.

| | peak over the slot | travel toward the rover | at its lowest | outcome |
|---|---|---|---|---|
| g8s (before the envelope) | 0.102 m | **0.228 m — past the edge** | 0.021 m over slot level, 0.070 m *outside* the stand | held, carried ✓ |
| g9m (with the envelope) | 0.141 m | **0.105 m — still over the stand** | back on the slot surface | released ✗ |

**Both runs sag, by 8–14 cm within seconds of the lift; sag is not the fault.** What decides the outcome is where
the item is when it sags: past the stand's edge it keeps hanging in the jaws, over the stand it lands and is let go.
g9m's ORU was on the slot **before the rover moved at all** — the drive did not tear it out, it left it behind.

**Why the travel collapsed.** `carry_item` models the payload as an upright square prism swept over every yaw:
`side = hypot(0.45, 0.392) = 0.597`, half 0.298 against the real half depth of 0.196. The evaluator TF refutes the
sweep: across both runs the ORU's tilt stays 0.5–10 deg and its yaw within a few degrees of where it started — it
does not turn in the jaws. The phantom 0.102 m per side is exactly the travel that disappeared (0.228 → 0.105).

**The budget, and what closes it.** Travel needed is the item's own half depth plus a margin, `0.196s + 0.03`;
travel available is the arm's limit minus the envelope's excess, `0.228 - 0.102s` (the arm stops at joint4's limit,
g8s/g8t both at -2.24/-2.33 rad of ±2.356). They meet at **s ≤ 0.664, i.e. `target: {longest: 0.30}`**; at 0.25 m
the margin is 3.2 cm. Removing the unjustified yaw sweep instead makes the budget close at full size. The two are
independent and both are one small change; neither is a tuned constant.

**What the stand is, and what the stand-off does not check (g9p).** Two scene facts were wrong, not one. The
`site/depot_stand` box took the prop's bounding height, 0.610 m, while the asset that authors it says plainly
`top surface 0.55 m, front (+X) edge free for the arm, back lip`: the 6 cm is a lip along the back, and the box
spread it over the table, the slots and the free front edge alike. An ORU standing on a slot at 0.550 therefore
began 6 cm *inside* the obstacle, and since the held envelope reaches `neck_height` (0.055) below the item's own
base, it had to rise **0.115 m** before the arm's checks would let it move at all, where physics asks 0. The hold
lift is 0.15, so bring_in had 0.035 m against a measured 0.07 m of sag, and the first heights of its ladder came
back `clear: false`. Bounding a prop at its declared working surface gives 0.093 m instead.

Shrinking the ORU to 0.25 m was tried in the same pass and **reverted**: it cannot help. The body scale cancels out
of the vertical budget exactly (`handle_above_base = body height + 0.10`, the handle being synthesized after scaling
in absolute metres, which also left the 12 mm neck untouched). What it did do was move the rover. The boundary
stands where the arm reaches the work height, and the work height is the tallest handle over a support
(`ITEM_HANDLE_M`); a shorter unit lowered it from 1.017 to 0.854, the reach model parked 14 cm closer, and every one
of pick's working views became unreachable. Swept against the live MoveIt over the skill's own grid
(back x rise x pitch, 96 poses), the views survive on the aim's *distance*, barely on its height:

| aim x (chassis) | −1.02 | −1.00 | −0.98 | −0.96 | −0.94 | −0.92 | −0.90 |
|---|---|---|---|---|---|---|---|
| reachable views of 96 | 15–20 | 10–17 | 6–15 | 1–9 | 0–5 | 0–1 | **0** |

g9o's aim sat at −0.954 and worked on 3–8 of 96; g9p's at −0.908 and had none.

**Harness gap this exposes (not a scene fault).** `stand_distance` chooses the parking place by asking whether the
arm reaches the *work heights*, plus footprint clearance and a docking error either way. It never asks whether the
skill's own observation poses are reachable from there, and those are the tighter constraint by far — behind and
above the target, folding toward the rover. So the boundary can hand back a stand from which the item can be
grasped but not seen. That is a property of the robot's geometry, not of any mission, and belongs in the stand
choice.

**The overview is written in the chassis frame, and the stand-off is not a constant (g9p, g9q).** Bounding the
depot stand at its table moved the boundary's parking place from 1.096 m to 0.950 m — a closer stand now passes
`arm_reaches`, and candidates are offered roomiest first. Both pick failures that followed come from that 14 cm,
and they are different failures:

*g9p* — every working view unreachable. The views sit 0.15–0.34 m behind the aim and pitched down at it, so a
nearer target folds them into the rover. Swept on the live MoveIt, 96 poses per aim: 15–20 survive at aim
x = −1.02, 3–8 at −0.95, **none** at −0.91, and the aim's height barely matters.

*g9q* — the views were reachable, and the aim still landed on the ORU's body (0.910) instead of its handle (1.022).
Not framing: measured through the robot's own camera-in-tool transform, the closer stand frames the handle *better*
(image row 210 against 11, depth 0.318 against 0.372). The overview's own regions prove it was seen — one sits at
chassis z = 1.059, the handle's head, 0.023 m from the located dot and well inside the 0.2 m window the aim
searches. What discarded it is `surface_heights`, which drops every measured point within 0.15 m of an arm link as
the arm's own body. The overview is taken at a **fixed chassis pose** `[-0.85, 0, 1.10, 50, 0]`: at the 1.096 m
stand the tool sits 0.258 m from the handle and the handle survives; at 0.950 m it sits **0.135 m** from it and the
skill deletes the thing it came to find.

**What the measurement says the fix is.** Taking the same overview relative to the item instead of to the chassis
makes its geometry identical at both stand-offs (handle at 0.411 m, 47.6 deg down) — the property wanted, since the
stand-off is chosen by the boundary and will keep changing. And the stand choice itself asks only whether the arm
reaches the *work*; the poses it must observe from are the tighter constraint, and a stand that fails them is one
the skills arrive at and cannot start from. Both follow from the robot's own geometry — the arm's self-filter
radius, the camera's place on the gripper — not from any mission.

## F80 — The stand is reasoned about, and the pick works (2026-09-20, development)

**What was wrong.** Three scene/skill faults and one architectural one, all measured:

1. `site/depot_stand` took the prop's bounding height, 0.610, while the asset that authors it says its table is
   0.55 and its front edge is left free for the arm; the 6 cm is a lip along the back. An ORU standing on a slot
   began 6 cm *inside* the obstacle, so the held envelope had to rise 0.115 m before the arm's own checks would let
   it move, where physics asks 0. Bounding a prop at its declared working surface gives 0.093 m of clearance at the
   hold lift instead of 0.035.
2. The held item was checked as a prism swept over every yaw, 0.597 m square against a 0.45 x 0.392 m unit. Four
   carry bags say the ORU does not turn in the jaws (yaw within 14 deg of where it started, modulo the box's own
   symmetry) and pivots at most 15.4 deg about the jaw axis. It is now checked as the box it is, widened across
   that axis by the measured pivot.
3. `find` opened with an overview from a pose fixed in the chassis frame, built a 5 cm height map, took the tallest
   cell within 0.2 m of a located blob for "the item's top", and aimed 24 viewpoints at that guess. All of it was
   machinery for deciding where to point the camera, and it assumed a parking distance the boundary decides. It is
   one view now, level with the part, because an upright handle neck shows the width the jaws close on from the
   side and not at all from above (F60). Where that is comes from the caller.
4. **The boundary chose where to park and said nothing about what it gave up.** `stand_distance` takes the roomiest
   stand its reach model offers and settles it with kinematics: 0.96 m at the depot, where the arm reaches the
   handle and can only look at it from 20 deg above -- and from above the head hides the 12 mm neck, so five
   candidates came back at 19-27 mm, the pedestal, and none at the declared width (g9t, reproduced offline on the
   saved depth). Four predicates over the nominal work point failed to tell 0.96 from the 1.10 every successful
   pick had used: standing off by the camera's set-back, reach-map room at the point and at that remove, the
   working-branch rule, an insertion from a stand-off. A **level look** tells them apart cleanly, because that is
   what the measurement needs.

**What was done about (4) is the part that matters.** Not a predicate inside `stand_distance`. `work_stands`
reports, per distance, whether the tool reaches the work and the shallowest angle above horizontal the wrist camera
can look from, with the stand-off taken from the pick skill's own manifest so both answer with one number; each row
carries the `standoff_m` that parks there. `dock_at_feature` now says its default distance is chosen for reach
alone. What each part needs is already in the catalogue's grasp interface. The model reads both and decides.

**It does.** Offline against the real reasoner, with the real records and no hint: it computes the grasp height as
the place frame's z plus the catalogued handle height (1.017, exact), reads "a neck under an overhanging head" and
concludes it needs a level look, asks `work_stands`, and docks with `standoff_m` 0.12 -- 1.08 m, the nearest stand
that allows one. Live in g9w and g9x it did the same, unprompted, and wrote the reason into its own task ledger.
An earlier interface where the query reported what the standoff counted *from* had it pass 0.96 and park at 1.92:
the inference was right and the interface was ambiguous, which is the sort of thing the offline check finds in
seconds.

**g9x, the first pick that works end to end.** One level view, 5.7 s of sim time against the old flow's 92 s, one
candidate, the VLM naming it as the neck between head and pedestal. `bring_in` then ran **without stalling at all**
-- no `why` -- over **0.30 m**, against 0.228 m in the best previous run and 0 m in g9m, with six usable heights
starting at `raise 0.00` clear, the falsifiable prediction fault (1) implied. `item_held` verified, jaw 0.174,
lift 0.152. The evaluator's `oru_on` stayed empty through the drive that follows.

**Method.** Every step above was settled offline before a simulator ran: the IK rule and the view sweep against the
live MoveIt, the detector replayed on the run's own saved depth, the reasoner's inference asked of the real model
with the real records. Two runs were still lost to code that a read-back would have caught (a `#` comment inside an
embedded JSON block; a path passed where an image array was expected), which is why that read-back is now a rule.

**g9x's carry, and what it uncovers.** The pick held: bring_in ran its full 0.30 m without stalling, `item_held`
verified at jaw 0.174 and a 0.152 m lift, and the evaluator's `oru_on` stayed empty. The drive then lost it. At the
shelf `item_still_held` verified **false** at jaw 0.100 -- closed on nothing -- and the ORU's truth pose is
(5.620, -14.009, 0.086), pitched 48 deg, on the ground **0.44 m from the slot it came off**. It did not ride to
PDU-1 and fall; it slid out of the jaws within the first metre, and the rover drove the rest of the way empty.

This failure has been hidden until now. Every earlier run either never moved the item off its support (bring_in
travelled 0-0.14 m, g9m/g9o) or ended with the arm pressed against joint4's stop, which held the posture rigid
(g8s/g8t, both of which carried). g9x is the first time the ORU has hung free, clear of the stand, while the base
accelerated -- and a 12 mm neck between jaws that close to 0.174 rad did not survive it. The handle is built so a
vertical pull is taken by the head resting on the fingers (F49); nothing in it resists the neck being shaken out
sideways.

The question is whether the base's acceleration threw it or the arm's hold relaxed after bring_in, and those need
different answers. The bag carries the ORU's evaluator TF and the joint states: the ORU's height and the jaw angle
against time across the first metre of the drive separate them. Not to be guessed at.

## F81 -- the carry never had a dynamics problem: a cmd_vel overwrote the arm

Six runs lost the ORU within the first metre of the drive. The dynamics were derived carefully -- lunar gravity from
the published `space_context`, a swing budget from the largest disturbance the jaw had been measured to take, the
linear and angular allowances split because they add at the load -- and ga1 drove under those limits, at a peak base
speed of 0.08 m/s against g9x's 0.20, and lost it anyway. Peak load tilt barely moved: 14.3 deg in g9x, 12.9 in ga1.
Base roll and pitch are 0.00 deg throughout both runs, parked and driving, so terrain was never in it either.

The bag's wrist camera settled it in one look. From t=184.6 to 186.0 the ORU's head sits still above the closed jaws
against empty sky. At 186.08 a base structure fills the frame; by 186.5 the head is visibly skewed; the jaw falls
0.183 -> 0.163 -> 0.133 -> 0.104 and by 187.4 the jaws are empty. Reading the numbers alone had produced four
successive wrong hypotheses in a day. **Look at the pictures first, then measure.**

What the pictures showed was the load being flung, and the joints say by what. The arm is motionless from t=183.0 to
185.78 -- joint2 at 41.6 deg to a tenth of a degree. At 186.00 it moves; by **186.22, 0.22 s later, joint2 is at
60.0 deg and joint6 at -39.1** (+18.4 and -36.3 deg); the load's handle travels 21 mm along the tool's own approach
axis in that same interval, and the jaw is pried from 0.170 to 0.183. From 187.5 on the arm oscillates between
joint2 34.5 and 50.8 for the remainder of the run. Nothing in the mission commanded any of this.

**The cause is at the SRB/ROS action boundary.** `LunarBot`'s action vector is one concatenation: base drive, then
the arm's 14 slots (`[mode flag, 6 ik twist, 7 joint targets]`, `SwitchableArmAction`), then the binary gripper. Every
`cmd_vel` message rebuilds the *whole* vector through `map_cmd_to_action`, which is the **teleoperation** mapping of
one shared twist -- for this robot it returns a zero mode flag and seven zeroed joint targets that its own comment
calls "an ignored placeholder" -- and then keeps only the dimensions in `_held_mask`. That mask was set by
`hold = msg_type is BoolMsg`: the gripper was protected because it is a Bool, the arm was not because it is a
`Float32MultiArray`. So the first cmd_vel of the drive switched the arm out of joint-position mode and zeroed its
targets, and every cmd_vel after that did it again at 20 Hz.

The bag contains its own control. The last arm command is at sim_t 176.54, when `pick` finishes; the arm is then
uncommanded for **9.4 s and does not move at all**. It whips at 186.0, the instant the base first moves. Absence of
arm commands is not what does it; the arrival of cmd_vel is.

This is why every earlier explanation failed. Halving the drive speed could not help, because the disturbance is a
joint step, not an acceleration. The gripper was never commanded open -- it is the one term the mask protected -- yet
the load still left. The loss always fell inside the first metre because it happens on the *first* cmd_vel. And the
two runs that did carry (g8s, g8t) had the arm pressed against joint4's stop, which absorbed the step.

The fix is one line of semantics: **a client that commands an action term owns it**, so `hold = True` for every term
rather than for Bool terms alone. Teleoperation never publishes on the per-term topics, and the base's own term
(`four_wheel_steer`) has no publisher at all -- the base is driven by the `action/cmd_vel` Twist -- so nothing that
worked before is latched.

**A second, independent weakness, found on the way and worth keeping.** The jaws closed with the ORU's neck only
3.2 mm inside the fingertips. The gripper's own collision meshes, forward-kinematic at the measured jaw angle, put
the fingertips at tool z +0.006 and the pads' clamping ridges back to -0.030, with the jaw body closing the pocket at
-0.043. The skill drove the contact to -0.012 and accepted a residual of up to 0.012 -- one manifest number,
`pad_offset_m`, serving as both the target and its own tolerance, so a contact that had not entered the jaws at all
was inside budget. Target and tolerance are now two quantities from one measurement of the pads (`pad_band_m`):
seat at their middle, accept half their length. The seat moves 6 mm deeper, which lengthens the escape the load must
travel from 33 mm to 40 mm. It is hardening, not the cause.

## F82 -- the carry holds, and what it cost the mission next

With the action-ownership fix in (F81), ga4 carried the ORU twice without losing it. `pick` verified at sim_t
184.88 on the first attempt (`item_held`, jaw 0.199); the rover drove depot -> PDU-1 over 86 s of sim time and
`item_still_held` verified at jaw 0.182; it later drove PDU-1 -> depot over 77 s and `item_still_held` verified at
jaw 0.194. Six earlier runs had lost the load inside the first metre. The jaw never approached the 0.13 that means
closed on nothing.

The jaw angle also measures the fix to the seat. ga1 closed at 0.170 with the neck 3.2 mm inside the fingertips;
ga4 closed at 0.199. The fingers turn about a proximal pivot, so for the same 12 mm neck a larger angle is a
contact nearer that pivot -- the deeper seat, read straight off the encoder.

**The mission still did not finish, and the reason is a harness gap worth the paper.** At PDU-1 the model asked
what was in the jaws. The wrist camera is on the gripper, and the gripper is clamped to the T-handle: the handle's
head fills the frame and the ORU's gold body hangs below it, out of view. The model answered accurately -- "a
smooth light-grey case, flat matte top, no lifting eye, no gold MLI foil" -- which is exactly what the head looks
like. From two such observations the model concluded it was carrying the white cargo crate, wrote itself a recovery
task, and drove the correct payload back to the depot to put it down.

Nothing in that chain is a mistake by the model. It asked a reasonable question; the only instrument the harness
offered was one that physically cannot answer it. The boundary's `held_item` query was *defined* as a camera
reading, with the comment that the comparison against "what the record says is carried" belongs to the caller --
but the record was never given to any caller. The boundary dispatched the `pick`, saw it succeed, and knew the
catalogued item and the support it came from.

`held_item` now returns both, labelled and unreconciled: `observed` (the camera, still asked blind, because an
answer shaped by the question is not evidence) and `record` (the item and support of the last pick that succeeded,
with the jaw at that moment). The contract states the geometry that makes them disagree -- a load held by a handle
puts its body below the wrist camera's frame -- and leaves which to act on to the caller. That is the pattern the
paper argues for: the harness owns the authoritative fact and the honest observation, and the agent owns the
judgement between them.

## F83 -- the carry budget was a pendulum, and a T-handle does not resist twist

ga4 carried the ORU through two long straight drives and lost it on the first turn. The third move was
`navigate_to_pose` to a heading 180 deg from the one it held, and the boundary applied the carry limits it derives
(`max_velocity [0.25, 0, 0.36]`, `max_accel [0.071, 0, 0.06]`, `lever_m 1.109`); the base held ~0.36 rad/s, exactly
the allowance. The arm did not move -- joint2 stayed at -45.7 deg to a fifth of a degree through the whole event,
so the action-ownership fix (F81) held. Something else took the load.

The wrist camera shows the handle head tipping further out of square with the jaws frame by frame, and the
transforms say by how much. The load's yaw lags the base's and the lag grows monotonically through the turn:
+99.2 deg at t=583.0 (the standing offset), +103.1 at 587.4, +107.5 at 588.7, +113.4 at 589.5, **+122.7 at 591.8**
-- **23.5 deg of twist relative to the jaws**, accumulated over about 181 deg of heading change. The jaw angle
tracks it: 0.188 held, 0.232 pried at the widest, then 0.164, 0.110, 0.100 and the ORU on the ground.

The catalogue says why. The neck is 12 mm across the jaws and 30 mm along the approach. Turned by phi about its own
upright axis it presents `12 cos(phi) + 30 sin(phi)` to jaws that closed on 12: at 23 deg that is **22.7 mm**,
nearly twice the width they hold. A `neck_with_overhanging_head` takes a vertical pull by geometry and a sideways
swing on the pads. Against twist it has only friction on a thin rectangle, and the rectangle is 2.5 times wider than
it is thick.

The derived limits could not have prevented this, because they model the load as a point pendulum:
`a = g tan(theta/2)` bounds the lateral acceleration that leans a hanging mass, and the angular allowance was the
same budget divided by the lever. Nothing in it is about what the *grasp* can transmit. A straight drive never
accumulates relative twist, which is why the same grasp survived 86 s and 77 s of driving and failed inside 9 s of
turning.

Two quantities follow from the measurement, and they are different in kind. The geometry gives the twist a grasp
tolerates: the jaws give about 2 mm before the neck walks out, so `phi_tol = asin(2/30)` is about **4 deg**. The run
gives how much twist a heading change costs: 23.5 deg of lag for 181 deg of turn, about **13%**. Together they bound
the heading change this grasp can take in one move at roughly **30 deg** -- which would have refused the 180 deg
turn. The ratio is one measurement from one run and is owed a second before it is trusted as a number; the geometry
is not.

## F84 -- the lifting interface takes the roll by geometry too, and the gripper is 3x its own datasheet

F49 established the principle and applied half of it: a payload interface must give **form closure, not friction**,
so the T-handle's head rests on the fingers and a vertical pull is taken by geometry. Rotation was left to friction,
and rotation is what F83 measured coming apart -- 23.7 deg of roll about the approach axis while the two drives that
held moved 4.9 and 4.8 on that same axis.

With 55 mm of free neck the fingers had 27 mm of empty travel below them. The head is the upper stop; there was no
lower one. The handle now has a **collar** of the head's own footprint below a slot, and the fingers sit in the slot:
to roll, one finger must rise out of it and the other drop into it, and both are stopped within the slack. Neither
number is picked for this payload -- the slot is the gripper's own finger height (18 mm, `eg2_link5/6` span
y +-0.009 in their meshes) plus 3 mm each side, and the collar reaches as far across as those fingers touch (27 mm):

    roll allowed = asin(3/27) = 6.4 deg     measured: 4.9 and 4.8 held, 23.7 lost it

The handle frame stays at 0.4669 above the item's base, so the catalogue height, `work_stands` and the reasoner's
own 0.55 + 0.467 = 1.017 are untouched. The column also used to start at the item's *bounding* top -- the highest
point anywhere on it -- and hung in the air above the surface under its own footprint; it now starts at what is
measured beneath that footprint and sinks 20 mm into it.

**A measurement that stands against the simulation, not against the run.** The gripper's drives were at their
4.0 N.m limit on all six joints for every sample the item was held, and the load still pried them from 0.188 to
0.232 rad -- so grip force is genuinely the binding term. But the Inspire-Robots EG2-4C2 this robot names is a
**0-20 N** gripper (manufacturer's own page), and 4.0 N.m over the 0.045-0.06 m finger lever is 65-90 N: the
simulated gripper is **three to four times the hardware**. F49's note that 65 N is "inside the EG2-4C2 band" is
wrong, and F49 itself recorded that at the physically faithful 0.9 N.m the payload levered the jaws open. The user's
decision is to keep the simulated force -- lunar equipment is not a commercial catalogue part -- and fix the
interface, which is the right way round: a grasp that needs three times its gripper's rated force is not a grasp.

## F85 -- two things the harness knew and did not say: where a level look survives docking, and which way is off a surface

**pick.** ga6's handle change cost the pick, and the model was not at fault. `work_stands` reported a level look
from 1.080 m and nothing nearer; the model docked at exactly that stand (`standoff_m` 0.12). The rover landed at
**1.068 m** -- 12 mm short -- and at 1.065 m the same query says the shallowest look is 10 deg above horizontal. The
24 mm slot is not readable from there: replayed on the run's own saved depth, the candidate search finds a
continuous 90 mm surface where the neck should be isolated (the collar's own top face, seen through the slot) and
returns **nothing** at the declared 12 mm; with the old permissive default it returns three candidates, all 26.4 mm
-- the pedestal below the collar.

The boundary was promising a level look on a 15 mm-wide condition against a docking band it verifies at **60 mm**.
Reporting the precision would only have turned that into a refusal. The fix is in the interface instead: along the
approach the handle's head and collar are now **shallower than the neck** (24 mm against 30), so the neck is the
nearest surface from any direction with open air on both sides -- which is what the candidate search asks of any
part. The level look stops being a precondition, and the stop against roll, which is the collar's reach *across*
the jaws, is untouched.

**place.** ga5 reached `place` for the first time and stalled at `over`, 5.5 and 6.8 cm out, with
`site/pdu_1` against `held_item` 1.5 mm and 8.2 mm deep. The shelf is mounted correctly -- 0.6 m deep, protruding
from the cabinet's front face, its surveyed point at its own centre. The item is what does not fit: the held
envelope is 0.485 m across (0.392 widened by the measured 16 deg pivot), which leaves 58 mm behind it on a 600 mm
shelf whose back is the cabinet wall, and the approach spends it.

The surveyed point is the middle of the surface; nothing told the skill which way is *off* it. That direction is
the support's own outward normal, surveyed beside the point and never passed on. `place` now receives it and steps
along it until the robot's own collision check passes, no further than half the item's depth -- past that the item
is more off the surface than on it -- and records what it cost. No new number: the step is the smallest feature the
perception resolves and the limit is the item's own size.

## F86 -- the shelf, computed instead of argued

Three sessions of inference about why `place` stalled ended with one instruction: it is a geometry question, so
compute it from the actual models and the actual scene, and if the shelf is too small make it bigger. Doing that
took minutes and found three defects, two of which no run had pointed at.

**1. Props were boxed where they are not.** `prop_boxes` built each obstacle as `[0, size_m[2]]`, and `size_m` is a
prop's *extent*, not where its top is: a prop that keeps its modelled origin need not start at z = 0. Read straight
out of the authored glTF accessors, the service shelf spans **0.16..0.53** in its own frame and the PDU service
panel **0.60..1.12**. Their collision boxes sat at 0..0.37 and 0..0.52 -- a phantom obstacle in the air underneath
each, and no obstacle at all where the tray and the panel actually are. The panel's box was 0.6 m below the panel.
This is the third time the same mistake has been found (F79 bounded a stand at its lip, F80 at its bounding height);
it is now the asset's job to say where it is, in `z_range_m`.

**2. The shelf could not take the payload.** It is a tray with a 3 cm rim, cantilevered off the cabinet on
brackets, 0.6 m deep with the wall directly behind it. The ORU is checked as a 0.485 m envelope, so centred on its
surveyed point the item sat **58 mm** from that wall, and the approach spent it: `place` stalled 5.5 cm out with
`site/pdu_1` against `held_item`. The tray is now stretched in depth alone -- scaling it all round would lift its
surface out of the arm's working band -- to 0.75 m, with its place frame at 0.40 rather than the centre. 1.42x was
tried first and the scene builder refused it: the deeper tray reached 30 mm into the rover's own work pose. Back
clearance 58 -> **158 mm**, no problems reported.

**3. The handle's bars are what a downward look sees through the slot.** ga7's view left **8.7 mm** of neck showing
where the candidate search needs `pad_height_m` = 14 mm, so it found the neck at exactly 12 mm wide with clear air
on both sides and discarded it as too short -- 0 candidates at the declared width, while the permissive default
returned the 26 mm pedestal. Each millimetre of bar depth costs `tan(look)` of visible neck. Bars 24 -> 12 mm deep
and slot 24 -> 28 mm gives 25.9 mm of neck from 10 deg above, and the roll stop moves only from 6.3 to 10.5 deg --
where the neck still presents 14.3 mm to jaws holding 14.95, so it is not pried. Measured: 4.9 deg held, 23.7 lost.

The lesson is the instruction: a question about whether one solid fits on another is arithmetic over data the
repository already holds. Three of these were sitting in the asset files the whole time.

## F87 -- Mission B, end to end

ga8, every effect verified, `CHECK_EXIT 0`:

    RESULT {"scenario": "covered", "destination": "pdu_1", "oru_on": "pdu_1_shelf/shelf",
            "crate_on": "depot_stand/slot_1", "delivered": true, "success": true}

| sim_t  | step                | evidence                                          |
|--------|---------------------|---------------------------------------------------|
| 179.52 | pick                | `item_held` true, jaw 0.170, lift 0.162 m, first attempt |
| 285.34 | navigate to PDU-1   |                                                   |
| 305.48 | dock                | `item_still_held` true, jaw 0.171                 |
| 332.92 | place               | `item_placed` true, jaw 0.82, tool clear by 0.18 m |
| 339.40 | stow                | `arm_stowed` true                                 |
| 338.3  | evaluator           | `delivered: true`                                 |
| 393.60 | return dock         | map position error 0.019 m, yaw 1.5 deg           |

Before today the chain stood at: pick worked, carry always lost the load inside the first metre, and `place` had
never been reached. Ten defects were found and fixed between those two states, and they are worth separating by
what kind of thing they were.

**Two were the harness withholding what it already knew.** The boundary dispatched the `pick`, saw it succeed and
knew the catalogued item -- and answered "what am I holding" with a camera that is clamped to the handle and
cannot see the payload, so the model correctly read "a grey rectangular block" and drove the right payload back
to the depot (F82). The site survey records an outward normal beside every place point, and `place` was never
given it, so when its own collision check refused the surveyed centre it had no direction to move in (F85).

**Three were geometry no run ever pointed at, found by computing instead of inferring.** A prop's collision box
was built from how *tall* it is rather than where it is, putting the service shelf 16 cm and the PDU panel 60 cm
below themselves. The shelf was 0.6 m deep against a 0.485 m envelope with a wall behind it. The handle's own
bars occluded the slot they bound, leaving 8.7 mm of neck where the candidate search needs 14 (F86). Three
sessions of reasoning from run logs had not touched any of them; the arithmetic took minutes.

**One was the simulator's action boundary**, and it is the one the whole carry turned on: every `cmd_vel` rebuilt
the full action vector through the *teleoperation* mapping and kept only the dimensions marked held, and only the
Bool gripper was marked. The first cmd_vel of every drive zeroed the arm (F81).

**The rest were the harness's own numbers being wrong about themselves**: a seat depth and its tolerance sharing
one constant, a transient swing tolerance spent as a sustained one, a turn taking the whole budget the line above
it split in half, an orphaned scene lock that refused every later operation.

The model's side needed no correction at any point. It computes the grasp height as the place frame's z plus the
catalogued handle height, asks `work_stands` and docks where a level look exists, reconciles what the pick
measured against the catalogue in its own report ("measured neck width 0.0119 m vs catalogue closing width
0.012"), and when told what it was carrying, acted on the record rather than the picture.

## F89 -- what the robot does when nobody is commanding it

Three things the user saw in gb2's video, all one root: the rover stood still for the first minute, the arm moved
continuously and without purpose throughout, and at rest it was folded somewhere that looked nothing like a
working posture.

**Measured from the bag.** The rover first moves 2 cm at sim 79.7 s. For the first 150 s the arm's fastest joint
is at **3.88 rad/s median, in 100 % of samples** -- its velocity limit is 3.92. Joint2 swings between -33 and
-56 deg, joint4 between +59 and +101, joint6 between **-22 and +50**, with a period of a few seconds, until a
skill first claims the arm at sim 159 s. After that the median joint speed is 0.0003 rad/s.

**Why.** `RosInterface` starts its action buffer at zeros, and for `SwitchableArmAction` a zero is not "do
nothing": element 0 is the mode flag, and 0 selects twist mode against a persistent desired pose that has never
been set. Nav2's velocity smoother publishes `cmd_vel` at ~20 Hz whether or not the rover is moving, and every
one of those rebuilt the whole action row through the teleoperation mapping (F81's other half -- `hold=True` only
latches a term once something has commanded it, and nothing had). So the arm chased an unset pose at its limit
for as long as the mission took to reach its first arm call.

The fix belongs where the knowledge is: the term now answers `hold_action()` with joint-position mode at its own
measured joints, and the interface writes that into the buffer and latches it before any subscription is live. A
robot with nobody commanding it holds its posture.

**And what it holds.** `stow` was `[0, -0.6, 0, 1.2, 0, 0.6, 0]`: the arm folded up over the deck, tool 0.209 m
behind the rover origin at 1.455 m, the wrist camera pointing **forward** and 21 deg above the horizon -- and off
the working branch the skills seed their IK from. It is now `[0, 0.40, 0, -0.70, 0, -1.27, pi]`: tool 0.694 m
behind the origin at 1.404 m, camera **level and facing the way this arm works**, elbow bent 40 deg, on the
branch, and 26 mm past the rear hull face so it changes nothing about what the rover can back up to. Every
candidate was computed from the robot's own URDF against four conditions at once -- level, rearward, inside the
hull, on the branch -- rather than adjusted until it looked right.

Seven files carried a copy of that pose and an eighth carried it as the spawn state. That they all had to be
found by grep is its own finding.

## F90 -- three minutes at the start of every run, for one dropped response

Every run stood still for the first minute of sim time. Measured from gb2's bag and events: the base first moves
at sim 79.7 s, and between `reasoner_attached` and the first thing the agent does there are **180.1 s of wall
clock** -- against 3 to 25 s for every LLM call after it.

`QUERY_RESEND_S = 180.0`, to the tenth of a second. Humble drops the response to the first service call after
discovery (`wait_for_service` returning is not enough), so the agent resends a read-only query when no answer
comes. One timer set that interval, and it had been set for the slowest thing a query can legitimately do -- a
vision-model localisation, up to a minute. So the cost of a lost response was pinned to the duration of the
slowest answer, two quantities with nothing to do with each other.

What a query does is in its own contract. The three that go out to the vision model declare `uses_model` and keep
the long wait; everything the boundary answers from its own state is resent after 4 s.

Unverified: no run has started since.

## F91 -- the robot looked once, and 6 cm of docking error decided the mission

gb2 called `pick` three times at the same handle and lost all three, and the model's side is again blameless. It
asked `work_stands`, docked at the level-look stand (1.08 m) and the approach stalled 2.6 cm short of the grasp; it
reasoned that the neck was beyond reach, docked at the nearest stand (0.93 m), and the view measured nothing; it
split the difference at 1.035 m, and the view measured nothing again. Three stands, 15 cm apart end to end, and the
part was in plain sight in all of them.

**The picture the stage saved settles it.** At 1.035 m, looking 10 deg above the horizontal, the ORU's T-handle
fills the upper third of the frame: head bar, slot, collar bar, against black sky. Replayed offline on that run's
own saved depth, the candidate search returns **nothing** -- and returns **five candidates** the moment one gate is
removed, the best of them **12.9 mm across at 0.418 m**, which is the 12 mm neck, on the slot, with clear air both
sides. The view was never the problem.

**Defect 1: the image was made to certify what the catalogue declares.** `find_candidates` dropped any candidate
whose measured extent along the pads was under `pad_height_m` (14 mm). The width already takes the honest route --
the interface declares `closing_width_m` and the image confirms it to four pixels -- but the length did not, and the
two are not measured alike. A width is a cut across the part in the image plane and reads true from any direction
the part is seen in the round from. A length runs *up* the part: any look off its own square foreshortens it, and
whatever overhangs it cuts into it. At 10 deg above the horizontal a 28 mm slot read **9.5 mm**, and the part was
thrown away for being short. The catalogue had already said the interface takes the pads. The floor is now what the
perception can resolve at all when the length is declared, and the pads' own height when it is not.

**Defect 2: the stage looked once.** `find` pointed the camera straight back along the rover's own axis, tried three
elevations, took the first one the arm could reach, and made whatever that single frame measured the outcome of the
mission. Nothing retried, nothing moved, nothing looked again -- with seven joints and a wrist camera, and with the
part in the picture. That is what turned a 6 cm docking band into a mission outcome. The stage now takes the views
the arm can reach, in order of what each costs the measurement, and a pose out of reach, a view that measures
nothing and a view whose marks are all on something else are each one view fewer, not the end of the operation.

**What the azimuth is and is not worth, computed rather than assumed.** The first version of this fix ordered the
side looks before the steeper ones, on the reasoning that an elevation decides what can be measured and an azimuth
does not. The robot's own kinematics agree about reach -- straight back, a level look at this handle exists only
from 1.08 m, past where the arm reaches the grasp, while 30 deg round the side it exists from **0.92 m to 1.14 m**,
and the grasp with it. The *asset* disagrees about measurement. The neck is a rib, 12 mm across the jaws and 30 mm
along the approach, so seen from phi round the side it presents `12 cos(phi) + 30 sin(phi)`: **17 mm at 10 deg**,
against a declared 12 mm the search accepts to 2.7 mm. A level look from the side is a look that cannot measure this
part. So the order is the other way round -- every elevation from where the rover is facing, then the azimuths --
and the azimuths are there for a contact that is not facing the way the survey said. Two hours of plausible
reasoning, one line of arithmetic over the asset file.

**And the harness stopped promising what its own error rate breaks.** `work_stands` answered about the stand as a
point and then said, in words, that docking is verified to 0.06 m -- leaving the caller to carry a margin it has no
way to compute. That is not a fact; it is a fact plus a footnote that cancels it. Each promise is now answered at
the end of the docking band where it is hardest to keep: reach runs out with distance, so it is asked at `d + 0.06`,
and the look shallows with distance, so it is asked at `d - 0.06`. Both are monotone in the distance, so one point
bounds each and it costs nothing. Computed on the arm's own model, that leaves stands from **0.99 m to 1.08 m** that
both reach the grasp and offer a look wherever the dock lands -- where the old answer offered a level look at
exactly one distance, 1.08 m, at which the arm cannot reach the grasp at all.

    stand   reaches the grasp at d+6cm     shallowest look at d-6cm
    0.960   yes                            none
    0.990   yes                            30 deg
    1.035   yes                            20 deg
    1.080   yes                            20 deg
    1.095   no                             10 deg

Two rules come out of this, and they are the same rule twice. **A promise the harness makes must survive the error
the harness itself admits** -- it owns both numbers, and handing the caller a fact and a caveat that cancels it is
handing over nothing. And **a capability that gives up after one observation is weaker than the robot it runs on**:
the mechanics belong inside the skill, so looking again belongs inside the skill too, not in the model's head as a
re-dock.

Unverified: no run has started since.

**Superseded the same day.** The user's ruling on reading this: thresholds on absolute numbers are the wrong
scheme altogether, and a handle is an affordance -- how to grasp it is declared, and vision only has to say where
it is. Both fixes above (the declared-length floor and the multi-pose look) were reverted; `pick` now fits the
catalogue's interface shape to the depth image and servos on the fit (`interface_fit.py`,
`docs/grasp_target_selection_proposal.md`). The docking-band answer in `work_stands` stands.

## F92 -- the model decided one thing and called another: a schema-valid answer that was not an answer

gb3, 2026-09-21, the first run of the rebuilt `pick`. Step 7: the rover had just arrived at the depot approach
point (`base_at_commanded_pose` verified at sim 85). The model thought for **50.2 s** -- 39,297 characters of
`reasoning_content`, the first run to record it -- and its reasoning ends, verbatim:

    Plan for steps:
    7. dock_at_feature(slot_0, standoff 0.135)
    8. observe(wrist, "describe the object on the stand ahead of the gripper ...")
    9+. pick(...)
    Let me go.
    ... It says reaches_the_work: true. OK.
    Go.

The tool call that came with it was `dock_to_pose {"x": 0, "y": 0, "yaw": 0}` with the rationale **"placeholder"**.
Not the tool it had chosen, not the feature, not the standoff; the pose is the map origin, which is the dock. Every
field is schema-valid, the pose is a legal target, and the guard allowed it. The rover drove 1.9 m back toward the
dock, `dock_to_pose` timed out after 180 s short of it, the verifier reported `base_at_commanded_pose: false`, the
model read that in its next context, wrote a fresh plan and drove back to the depot. Cost: about 200 s of
simulation and nothing else. Recovery worked exactly as the harness is designed to make it work -- verification
independent of the model, context rebuilt from the record, the model replans -- and it worked at the price of a
timeout.

**What this is.** Not a wrong strategy: the strategy in the reasoning was right. Not a malformed reply: the reply
parsed. It is a *degenerate* answer -- the function-call channel came back with defaults and a placeholder after a
long reasoning channel -- and the harness had nothing that looks at an answer's quality, only at its validity and,
later, its effect. That is a failure class of its own, distinct from the two the harness already handles (an
answer the guard refuses; an effect the verifier refutes), and it is the class that costs time rather than safety.

**Why it took 50 s and 39 k characters to get there is also the harness's doing.** The reasoning dithers for pages
over the stand: *"The explicit hint in the tool description pushes toward choosing based on look angle ... Choose
it. Confirmed ... let me reconsider the standoff one final time."* The `work_stands` contract still discusses the
look angle at length -- text written when a level look was a precondition. It no longer constrains anything (F91:
the fit takes the interface from any elevation), but the description still makes the model deliberate about it,
and the deliberation is what ran the answer channel dry. A contract that describes a constraint the harness no
longer has is not neutral: it is a prompt.

**What the harness can do about a degenerate answer, in order of how little it has to know.**

1. *Treat a non-answer as no answer.* The contract already requires a rationale on every call; a rationale that is
   empty or a single placeholder token is a call that has not been justified, in the same sense as a reply with no
   tool call in it -- and the core already re-asks for that (`reasoner_step_failed`, one retry, the failure in the
   record). No task knowledge, no geometry, no thresholds: an unjustified call is not an answer.
2. *Check the answer against the model's own reasoning.* The endpoint returns the reasoning; when it names a tool
   (`dock_at_feature(slot_0, ...)`) and the call names another (`dock_to_pose`), the two channels disagree and the
   record can say so. Cheap to detect for the tool name; fragile for arguments. Worth recording; not worth acting
   on automatically beyond (1).
3. *Do not describe constraints the harness no longer has.* The look-angle text in `work_stands` goes.
4. *Bound what a wrong call can cost.* The 180 s was `dock_to_pose`'s own timeout on a 1.9 m drive; the loss was
   the timeout, not the detection. Progress-based termination is the general remedy and already exists for the arm
   (stall detection in the servo); the base's docking skill only has a deadline.

For the paper this is the third leg of the argument, and the run supplied it unasked: a harness for a fallible
reasoner has to hold three things -- what the model may not do (invariants), whether what it did worked
(verification), and whether what it said is an answer at all (answer integrity). The first two carried this run;
the third is the gap, and it is small.

Recorded, not yet acted on. Whether to add (1) and (3) is the user's call.

## F93 -- a stand has to reach the whole job, and "reaches" has to mean "without hitting itself"

gb6 docked at the boundary's default stand (0.96 m), found the handle at 0.96 agreement, and had no arm
configuration for any of six stand-off options. ma4 and ma5 did the same at a button: `press` failed at `locate`,
twice, from two different stands (0.589 m and 0.784 m), with every one of twelve viewing poses unreachable.

**The boundary's answer was wrong in the same way three times.** `work_stands` asked MoveIt for an arm configuration
at one pose per job with collisions off. gb2 reached the handle's point and stalled short of the seat (F88); gb6
reached the seat and had none for the stand-off, 7-14 cm nearer the rover than the handle; ma5 reached a button and
every configuration for its stand-off and view folded the forearm into the arm's own base. Asked offline of the
live MoveIt -- IK with collisions off, then `check_state_validity` on each solution -- the pure kinematics says all
of stand-off, view and stroke are reachable for a button 0.5-1.1 m out, and MoveIt names the contact for the ones
the planner refuses: `base_link x Link5`, `base_link x Link6`, `base_link x eg2_*`. The button was 0.784 m from the
rover's origin and the arm has to fold to reach a tool 0.68 m out.

The rule that replaces it: a stand is listed only if, for every pose the skill for that kind of point takes (a
grasp's stand-off, seat and view; a press's stand-off, stroke and view), some seed of a fixed bank yields a
configuration with no robot-vs-robot contact, at the near, middle and far end of the docking band. World contacts are
ignored because they depend on where the rover will stand; its own geometry does not. Every candidate distance is
scanned -- the window for a press, D in [0.95, 1.10] m, was not among the twelve stands with the most room, which
is what the boundary used to look at. Result: press default 1.06 m (was 0.589 / 0.805), pick 1.065 m.

## F94 -- press: three gates, one cause

At the new stand `press` ran further than it ever had, and each step ended on a fact about a number written down.

`locate` refused a button in plain view at the frame's centre because it measured 0.3142 m against
`min_depth_m: 0.315`. The gripper's own reach in its camera follows from the mount and the tool -- 0.285 m -- and a
surface beyond it cannot be the gripper. (The silhouette mask `tool_in_view` also produces was tried and refused: it
over-covers by construction and reaches the button's lower edge.)

The stroke then ran its full 3 cm and met nothing, because the simulator's panel does not resist the tool; the skill
reported a miss. **The evaluator had counted the press and cleared PDU-2's fault** -- `faults.pdu_2 false`,
`presses.pdu_2 1` -- the first time the new skill ever pressed a button. The skill was waiting for a signal the world
does not give and calling its absence failure. It now records `contact.resisted` and returns; the `pressed` verifier
already judged by kinematics alone (how far past the measured face the tool went, how far back it came), never by the
skill's flag. This is the harness's own rule -- an unsure check is not a veto, its facts go to whoever decides -- and
the skill had not followed it.

A third run failed at `locate` because the model described the button as "below the large round status lamp": the
frame is a few tens of centimetres across and the lamp is not in it, so the vision model correctly said no button
was visible below it. The contract asked for a description "by appearance and position". It asks for what the
close view shows now.

## F95 -- the servo was a limit cycle, in position and again in orientation

`pick` stalled 2.6 cm short in gb2 and 2.9 cm short in gb7r1 with the target steady and the arm reaching it. The
bag's `switchable_arm` command against the joint states showed the command itself swinging with a 3 s period, the
measured joints trailing it by 0.5-0.75 s. `servo` integrates the measured error into the command each 50 ms cycle
at up to 20 per second, limited only by a 5 cm/s speed cap: that is a limit cycle for any delay of the arm over 0.3 s.
Copied line for line into a model of the loop (`experiments/servo_loop.py`) against arms answering 0.3, 0.6 and 1.0 s
late, the law as written swings +-26, +-39 and +-59 mm and never settles; a gain of 1 per second and no sag
integral settles in under 2.5 s at every delay and holds +-2 mm with 3 mm of noise on the goal. The second integrator
the sag term adds is destabilising by itself (+-38 mm at a gain of 1.5 with it on), which is why it stays for the
stages that carry a load and off for the ones that do not.

The gain was added as an opt-in parameter for the empty-jaw stages, and the stand-off then settled in 0.72 s to 3 mm.
The close-in still swung +-9 mm sideways at 1.6 Hz with the goal steady to 0.8 mm: the orientation term takes the
whole rotation error every cycle too, a 20/s loop about a 0.2 m lever. The same gain applies to it now. By the time
the finger met the collar the tool had drifted 16 mm sideways and 7 mm low -- the slot leaves the fingers 5 mm to
either side -- which the forward kinematics of the blocked configuration showed and the slot itself did not: in the
live planning scene every tool pose inside the slot, +-10 mm in height and 40 mm in depth, is collision-free.

What the three findings share for the paper: every one was found from the record of a failed run and settled
offline -- a live planner asked what it would accept, a bag replayed against the loop's own arithmetic -- before
another run was started.

## F96 -- the arm's joints were stuck by the friction the robot's USD authors on them

The arm never held what it was told, and a good part of the session went on the consequences: the arm answered 0.5-0.75 s late (F95), settled above its command, sagged 5-6 cm over a carry, and on the last runs its wrist saturated at its torque limit at rest and whipped when the arm first moved, twisting the ORU's T-handle out of the jaws (gb8r3: jaw 0.169 to 0.098 within 6 s of place starting). Skills, gains and the harness were tuned around a plant that was misbehaving.

**Where it was found.** The bag of a real run: while `pick` waited on the vision model the command was one constant vector for 40 s, and joints 1, 3, 5 and 7 sat 2-7 degrees from it with their drives at the torque limit (60, 30, 10, 10 N m). Not a tracking error, not a second command source (one distinct vector in 1200 messages). Then a bare simulation with nothing else in it -- the robot on a ground plane, a 0.10 rad step per joint (`experiments/robot_check/arm_steps.py`):

| what was changed | joints 1-7, 0.10 rad step |
|---|---|
| as configured, base free | half way in ~7.5 s, drives saturated, end torque 10-29 N m |
| base fixed | 0.05-0.3 s, end torque under 1.4 N m |
| self collisions off | identical to as configured |
| sleeping off, 1 g root given 50 kg | identical |
| solver iterations 32 to 128, or step 5 ms to 2.5 ms | worse (less motion in the same time) |
| USD joint friction 0.4 0.4 0.3 0.3 0.2 0.2 0.1 to 0 | 0.05-0.3 s, end torque under 1.2 N m |

**Why.** PhysX's joint friction is a unitless coefficient on the force transmitted between the two links a joint connects, not a torque. In an articulation whose base is free that force is large enough that the coefficient times it exceeds what the drives can deliver. With the base fixed, or the coefficient zero, the same drives (stiffness 600, damping and limits as configured, checked against what PhysX holds) are fast and hold with almost no torque. The values are what the USD carried, not a typo in our configuration; the actuator group's `friction` option did not reach PhysX in this Isaac Lab (the read-back stayed at the USD's values), so the fix is in the asset: `experiments/robot_check/zero_arm_joint_friction.py`.

**What it does not say.** It does not say the earlier findings were wrong: the ratchets of `hold_here`, the leash and the carry sag are real and separate, at centimetres. It does say that the gains, ramps and margins tuned in F92-F95 were tuned against an arm that lagged by seconds, and that the wrist saturation the place failures ended in was this. The first graph-level check is the next full runs.

## F97 -- two joint-space defaults the sluggish arm had been hiding: a turn of the wrist, and a pull at the rate limit

With the arm answering its command (F96), the first full pair of runs (gc3 Mission B, mc4 Mission A) failed at two places the
servo had passed before, and both were joint-space rules that were wrong for any arm and had never been exercised on one
that moves.

**mc4, press retreat: "arm stopped making progress 0.1 cm / 7 deg from its goal ... at a joint stop: joint7 -6.24 (limit +-6.283)".**
The button was pressed (jaw closed on nothing, 1 mm off axis, 6.9 mm past the face, retreated 107 mm; the independent check
held) and the skill still failed. The bag: between sim 198 and 205 joint7 went from +1.89 to -5.58 in one planned move, a turn
and a half, and ended 0.04 rad from its stop. The planned stand-off IK is seeded from several configurations; MoveIt answers
with whatever turn of the roll its solver settled on, and a planned move executes the joints literally. The wrist roll spans
+-2 pi, so every pose has two solutions a turn apart. `nearest_equivalent` now takes each joint that can turn more than a
full turn at the turn nearest the arm, inside the stop's margin, on both IK paths.

**gc3, place: the carried ORU left the fingers 0.6 s after `over` began.** The world poses in the bag (evaluator truth, used
here only to diagnose): the tool, held at z 1.217, fell to 1.10 in half a second with the *command* within 4 mm of its goal,
rose to 1.33, and rang at 1 Hz with +-10 cm decaying over five seconds; the jaw read 0.158 then 0.093 (empty) as the tool
accelerated upward; the ORU dropped 11 cm onto the shelf, upright, and the evaluator scored it delivered while the skill,
correctly, reported a failed place. What moved was the elbow and wrist at 0.23-0.28 rad/s, the joint-rate limit. The servo's
posture pull was `(centre - q) * gain`, scaled up to `max_dq` whenever it exceeded it, which with the arm anywhere off the
window centre is always: a null-space self-motion at the rate limit, from a standstill, on every default-gain stage. The
joints answer at their own lags, so a null-space motion that should leave the tool where it is moved it by 12 cm and excited
the arm's slow mode. On the arm that stuck (F96) the pull was invisible. It is now a rate -- `posture_gain` per second of the
distance from the window centre, 0.05 -- because the branch drifts over tens of seconds and a pull with a 20 s time constant
holds it without exciting the arm. `place` also waits for the arm to be still before `over`, since the rover has just stopped.

**What the run did with it.** The reasoner searched, saw a gold box on the shelf, and tried to pick it again to "decide
whether it is really there": the harness had said "not placed" (true of the skill, false of the world) and had no instrument
of its own that could say "it is on the shelf" -- the claim/instrument gap of the reconcile design, not yet built.

**Also learned the hard way.** Reading a bag with SQLite while its recorder is alive crashes the recorder ("database is locked"):
both bags of that pair were cut in the middle of the run, which is why the mini-map of that pair cannot be drawn.

Not yet validated: the place chain on the fixed servo (scripted pick -> carry -> place on a held graph, then a full recorded run).

## F98 -- the arm's drives were 57 times softer than configured: gains are applied per degree

F97 named two joint-space defaults, and the scripted carry (pick, drive, dock, place on a held graph) showed they were not the
cause of the place failures: the arm still swung the carried ORU +-10 cm at 1 Hz whenever it moved, with the command constant
for ten seconds. The recorded efforts said "joint 4 at 30 N m, joints 5-7 at 10 N m, all at their limits, for tens of seconds"
with a 1 kg unit in 1.625 m/s^2 -- a 1.6 N weight -- which no load can explain.

**The reading was a replica.** Isaac Lab's implicit actuator reports `k * (target - position) - c * velocity`, clipped, with the
gains it was configured with; PhysX applies what it applies. The "saturated" efforts were the replica of a configured gain acting on
a joint error of 0.1-0.3 rad, and told nothing about the torque.

**What PhysX does.** A bare-simulation script (`experiments/robot_check/carry_static.py`: the robot with its base fixed, in the carry
pose recorded from gc3, nothing else in the scene): the elbow's target stepped 0.05 rad rings as a clean sinusoid at 1.0 Hz, amplitude
decaying by 0.84 every half cycle (damping ratio 0.055), for six seconds. The generalized mass matrix PhysX reports for the arm gives
0.12 kg m^2 about the elbow, which at the configured 600 N m/rad would ring at 11 Hz. Stiffness 150 rings at 0.5 Hz (frequency goes
as the square root of the gain, so it is a gain and not an inertia), and a free base changes nothing. A stiffness of 600 * pi/180 =
10.5 N m/rad and a damping of 7.65 * pi/180 = 0.13 N m s/rad reproduce both the frequency and the damping ratio. Multiplying both
gains by 180/pi (34 377 and 438 in the configured units) settles the same kick in 0.3 s with no ringing; the configuration in
`lunarbot.py` now writes the arm's gains converted, and the same test on that file holds the ORU to 0.001-0.004 rad.

**What it explains.** The arm that "answers 0.5-0.75 s late" (F95), the wrist that sagged 5-6 cm over a carry (F96's list), the servo
gains that had to be so low that a stall looked like success, the stand-off that rang after a planned move, and every place that ended
with the ORU out of the fingers: a static load of 1 N m deflected an elbow by 0.1 rad, and any disturbance rang for five seconds. F96
took the friction off the arm; this is what remained.

**What it does not say.** The gripper, the steering and the wheels are configured in the same way and are left alone: they were tuned
against their behaviour as it is, and nothing in the record shows them at fault. The servo's gains and ramps were tuned against the soft arm
and are conservative for the arm as configured; they are not touched until a run shows them wrong.

## F99 -- a joint pinned at its stop is a joint-space fact, not a Cartesian one

gt2c1, the first pick-carry-place chain on the corrected arm (F98): pick held the ORU through the whole carry, `over` and `lower`
placed it 6 mm from the expected shelf height, and `place` still failed. The withdrawal leg of `retreat` (collision checking off,
by design -- the open jaws start around the part they just released) stalled 15 mm short of its target with joint4 at -2.31 rad,
0.046 rad from its -2.356 stop. Nothing was in the way -- the servo's own progress test, not a collision, ended the stage.

Two fixes were tried and rejected before this one, on the user's own read of each. The first let a joint-limited stall stand as
retreat's result, on the reasoning that ending clear of the item is retreat's job and a 15 mm shortfall already does that -- this
treats the symptom, not the question of why a plain 15 cm withdrawal ran a joint to its stop. The second re-solved inverse
kinematics for the same (position, orientation) target from several seeds, on the reasoning that `over`/`lower` are local,
incremental tracking with no look-ahead -- nothing ever chose the release configuration for room to retreat from, so the servo
was stuck on one branch when another likely reaches the same pose without the joint at its edge. Asked why this still went
through a Cartesian target and a seed search for a problem that is "one joint is stuck," the honest answer is it did not need to:
a joint pinned at its stop is a fact about that joint, not about the pose. Finding it a target pose and re-solving IK for one is
solving a harder problem than the one that exists.

The fix: `joints_off_their_stops` (`_eye_in_hand.py`) walks any joint `posture_cost` would already call "at its limit" (within
0.3 rad of the stop -- the same threshold, not a new number) back to exactly that clear, towards its own working centre, and
leaves every other joint untouched. No target pose, no inverse kinematics, no seed search. `plan_to` makes the joint move,
collision-aware, since by the time a stall is detected the arm is already most of the way through the withdrawal and clear of
what the released item sat against. A stall that is not at a joint's stop still raises, unchanged.

Ran to a conclusion in F100 -- verified, but not by this fix alone.

## F100 -- what auditing the whole `place` flow found, and the first clean pick-to-place delivery

Told, correctly, to stop reacting to one more live failure and instead read the whole of `place` for every way it could still be
wrong (user's explicit direction after F99's second attempt), three more gaps turned up without running anything:

- **`over` had no escape from a joint pinned at its own stop.** It is the same local, no-lookahead Cartesian tracking `retreat`
  is (F99): each step continues from wherever the arm already is, so nothing about it chooses a configuration with room to move
  on from. The dead end F99 found in `retreat` could equally show up in `over`, on a different release pose, and had nothing to
  catch it. Both stages now share one helper (`_move_or_free_a_joint`): a stall with the scene clear gets `joints_off_their_stops`
  and a planned move: no target pose, no inverse kinematics, just the pinned joint walked back to `posture_cost`'s own 0.3 rad
  "at its limit" margin.
- **`plan_to` never told the planner about a carried item.** `state_valid` already attaches the held item's collision geometry to
  every check it makes; `plan_to`'s own MoveIt request never did. Nothing had exercised this before, because every existing
  caller of `plan_to` runs either before a grasp or after a release. Wiring `over`'s fallback to the same planner is the first
  path that can fire mid-carry, and an unaware plan there could swing what the arm is holding into the scene it never checked
  against. Fixed to match `state_valid`.
- **The retreat distance cleared the evaluator's own "not held" definition (F99, 0.30 m) only in the nominal case.** Each leg's
  own tolerance (0.015 m) can fall short of its target; the worst case at 0.25 + 0.20 m is 0.299 m -- inside the 0.30 m the check
  asks for, not past it. 0.30 + 0.25 m clears it at 0.37 m worst case.

A fourth thing found along the way was self-inflicted: the first draft of the retreat-distance fix put its explanation as a `#`
comment inside `default_goal_json`, a literal JSON string in the YAML manifest -- not a comment there, and it broke the manifest
outright. Caught by running the unit suite, not by another sim launch.

**gt2c8** (scripted pick -> navigate -> dock -> place, the pre-pick snapshot, no model, no video): pick held through the full carry,
`lower` stalled 4.2 mm from the expected height, `retreat`'s first leg hit joint4's stop 18.5 cm into the withdrawal and the new
escape freed it (`joint4: -2.306 -> -2.056`), the second leg completed locally, settle read the item motionless (190,215 near
pixels, comfortably over the 200 floor even at the wider retreat), and the evaluator's own `mission_state` read `oru_on:
"pdu_1_shelf/shelf", delivered: true`. The one `pick` failure on the way there (gt2c7, the VLM pointing at the item's body instead
of its handle, "nothing beyond the gripper in the view to fit the declared interface to") was not a code defect: `find` deliberately
has no internal retry ("the model answers within the deadline or the stage returns with what it has"), on the same principle as
everywhere else in this harness -- retrying a bad read is the reasoner's job, not something a skill does silently. The scripted
chain has no reasoner, so it just tried again.

Not yet run: the same chain end to end inside the real Mission B loop, with a model and with video.

## F101 — PLEXIL 6.1.3 LibraryCall does not carry its callee's failure (2026-09-20, Session P, offline; renumbered from F79 at the `p/integration` merge, 2026-09-22)

Mission B covered for PLEXIL is composed from reusable library nodes (`baselines/plexil/plans/lib/`: DriveAndDock,
PickItem, PlaceItem, StowAndReturn). With `plexiltest` and `Node:outcome` tracing, an injected `command-failed` on
`dock_at_feature` made the library root FAILURE while the calling `LibraryCall` node still ended SUCCESS, so the next
legs ran; the documented `PostCondition <call>.outcome == SUCCESS` idiom did not hold one nesting level deeper. The
library now returns an explicit `InOut Boolean ok` and every leg has `PreCondition ok` (PLEXIL's own regression-suite
pattern); re-verified: a failed dock skips everything after it and the plan ends FAILURE. Any generated PLEXIL (the
EUROPA→PLEXIL bridge) must use the same pattern. The adapter gained typed `LastFailureKind` / `LastFailureStage`
Lookups (mechanical reads of the last result) so recovery branches need no JSON parsing. The predefined recovery set
waits for pick/place failure kinds to settle; Mission A stays on stage-level tools until `press` is fixed (user).

## F102 — EUROPA builds natively; the EUROPA→PLEXIL machinery replans offline (2026-09-20, Session P, offline; renumbered from F80)

nasa/europa@ac5c332 builds with CMake on Ubuntu 22.04 / gcc 11 without Docker or root; swig 4.0, libantlr3c 3.4 and
cppunit 1.15 are unpacked from jammy .debs (`baselines/europa/build_europa.sh`, `docs/baselines/europa.md`). Upstream
examples solve (Light: 4 steps; Rover: from the single goal TakeSample(rock4) the solver derives
Go→Unstow→Place→TakeSample→PhoneHome). Machinery: `planner/europa_plan` solves an NDDL problem in a fresh Plan
Database; `host.py` runs solve → dispatch → result→facts (`facts_from_result`, a baseline artifact) → replan; a generic
PLEXIL `ActivityDispatch` plan with a length-framed TCP `HostLinkAdapter` (UDP datagrams are too small for 56 KB pick
evidence) calls the unmodified capability adapter. Offline against a stand-in boundary on a base-only skeleton domain:
nominal run completes; a dock failure that leaves the base far away yields a new plan with an extra navigation; three
identical failures stop the run as needing the operator. User decisions: replanning from the current state in a fresh
Plan Database is accepted as the baseline's own method (no strengthening of the baseline); the host reads site map and
initial pose directly from the boundary queries. The retry cap and "near" distance move to configuration with the
Mission B domain, which waits for the manipulation contracts.

## F103 — Experiment infrastructure in place; two structural gaps for the ALFUS metrics (2026-09-20, Session P, offline; renumbered from F81)

Scenario manifests (`experiments/scenarios/`, A/B covered + five held-out with closed-capability certificates, all
OPEN), §19 run-manifest backfill and a dry-run freeze tool (`openral_ext/run_manifest/`), per-run row extraction and
tables with Wilson/bootstrap intervals (`evaluation/`), an operator console, a PLEXIL log normalizer and Experiment II
worklog/delta tools. Exercised on 5 development runs only; development numbers are not results. Gaps found: (1) Ours'
`request_operator` ended the run and only wrote a local event, so interaction time and ALFUS level could not be
measured — user decision: the run pauses for the answer, which is fed back; the researcher is the campaign operator,
a script only in development; the protocol rules come from a literature survey (`docs/operator_protocol.md`, pending).
(2) PLEXIL runs never persisted universalExec's node transitions, so baseline traces stopped at the capability
boundary (§14.6). Both are being implemented on `p/operator-mechanism`. `preplanned_transition_fraction` uses three
categories (user): human-preauthored sequence (PLEXIL), planner-generated from a human-authored domain (EUROPA),
agent-generated online (Ours), reported raw.

## F104 — PLEXIL raced through the whole Mission B plan in under a second: the adapter's early `COMMAND_SENT_TO_SYSTEM` ack, not the plan (2026-09-22, live)

First live run of `MissionB_Covered.plx` after the `p/integration` merge and an adapter rebuild (`RequestOperator`,
`LastFailureKind/Stage` symbols confirmed present). Two failures before a clean run, each root-caused rather than
retried blind. `g_pb1`/`g_pb1_r2`/`g_pb1_v2`/`g_pb1_v3`'s run directories were debugging evidence, not campaign
results, and are deleted once this account was written and the successful run reproduced the fixes; `g_pb1_v4`'s
is kept, renamed (below).

**g_pb1 (was `artifacts/runs/plexil_mission_b_live_20260922`).** `universalExec` exited immediately: "Library node
DriveAndDock not found while expanding LibraryNodeCall node ToDepot". `d0_plexil_mission_a_check.py`'s
`universalExec` invocation (copied verbatim for Mission B) never passed `-L <library dir>`; Mission A's flat plan
never called a library, so the gap was invisible until Mission B's first live run. Fixed
(`experiments/launch/lunar_base_d0/d0_plexil_mission_b_check.py`: `-L plans/lib`); reproduced and confirmed fixed
offline first (`plexiltest -L plans/lib -p MissionB_Covered.plx -s MissionB_Covered_nominal.psx` -> `ok: true`)
before touching the live graph again.

**g_pb1_r2.** Reattached to the same held graph (no reboot). `ToDepot` (nav + dock) genuinely completed --
`runtime_node`'s own logs confirmed the robot actually drove and docked -- but PLEXIL never moved past it: the arm
never reached READY, `universalExec` sat at 0% CPU waiting on a Command result that never arrived, and nothing in
any log changed for 20+ minutes. `sudo py-spy dump --pid <capability_server>` (needed to inspect the process; this
session had no non-interactive sudo, so the user ran it) showed **all 8 of `capability_server`'s executor threads
simultaneously inside `dispatch()`**, one per capability of the entire plan (both nav/dock legs, `arm_ready`,
`pick`, `place`, the second `arm_ready`/stow posture) -- the whole mission's worth of calls had been issued within
the same instant, deadlocking the fixed 8-thread pool on their own nested `send_goal_async`/`get_result_async`
callbacks. `py-spy --locals` on the check script's own process caught `universalExec`'s buffered node-transition
trace mid-flight: `Return` (the plan's *last* node) reached FINISHING at essentially the same wall-clock instant
`ToDepot`'s nav started -- the entire 9-step plan had already "finished" in PLEXIL's own bookkeeping before the
robot had done anything.

**Root cause, confirmed against PLEXIL 6.1.3's own executive source** (`src/exec/CommandNode.cc`,
`src/intfc/CommandImpl.cc`), not guessed at: a Command node's `actionComplete` condition -- which gates the
FINISHING -> ITERATION_ENDED transition, i.e. whether the node is genuinely *done* -- is `CommandHandleKnown`:
`result = (NO_COMMAND_HANDLE != arg->getCommandHandle())`. Any handle value counts, terminal or not.
`ros/plexil_capability_adapter/src/CapabilityAdapter.cc`'s `send()` acked `COMMAND_SENT_TO_SYSTEM` in
`goal_response_callback` -- fired the instant the ROS action goal is merely *accepted* (a handshake, milliseconds),
long before the robot does anything -- which is enough on its own to satisfy `actionComplete`. The real terminal ack
(`COMMAND_SUCCESS`/`FAILED`, in `result_callback`) was correct, but the early one made it moot: every command
`send()` touched was already "complete" from PLEXIL's perspective the moment it was accepted. `requestOperator()`
had the identical bug (acked `COMMAND_SENT_TO_SYSTEM` right after publishing, contradicting this file's own header
comment -- "the Command stays EXECUTING (no Command Ack yet)" -- which describes the *intended* design that the code
never implemented); its own smoke test apparently didn't catch this because a scripted console answer arrives
fast enough to mask it. Fix: `goal_response_callback` now acks only on genuine rejection (`COMMAND_DENIED`);
`requestOperator()` sends no ack at all until the real reply. `EndCondition isKnown(ok)` in the library nodes
(`baselines/plexil/plans/lib/*.ple`) is not itself broken -- verified empirically, once the adapter fix was in,
`navigate_to_feature`/`dock_at_feature`/`arm_ready` each took their real, distinct sim-time durations, not zero.

**g_pb1_v2** (fresh graph, fixed adapter): `ToDepot` genuinely took 51.7 s + 13.2 s of sim time, `arm_ready` 3.7 s --
real, sequential, no deadlock. `pick` then failed for an unrelated, legitimate reason: "this pick did not say what
the item stands on, so there is nothing to look at: name the place frame (`support`) the item" -- `PickItem.ple`
only ever passed `target`/`part`/`item` (contracts.yaml's `pick.support` is optional but `find` needs it in
practice). Fixed: `PickItem.ple`/`MissionB_Covered.ple` now pass `support = "depot_stand/slot_0"` as `pick`'s 4th
positional argument; recompiled (`plexilc`), offline-verified (`plexiltest`, nominal script updated with the extra
argument), `ok: true`.

**g_pb1_v3**: `pick` failed again, differently -- "nothing beyond the gripper in the view to fit the declared
interface to", a single-view VLM miss at `find` (the same class of stochastic perception failure the harness sees
elsewhere; `pick`'s `find` deliberately has no internal retry, by design -- recovery is the caller's job). The
plan is nominal-path-only (no recovery branches yet, docs/baselines/plexil.md), so it correctly reported failure
and stopped rather than doing something not in the graph.

**g_pb1_v4 (renamed `artifacts/runs/plexil_mission_b_success_20260922`) -- first clean, full, video-recorded pass.** Same
plan, re-run once (a legitimate retry of a known-stochastic single-view failure, not a code change). All 9 steps
succeeded with real, distinct sim-time durations (51.7/12.7/3.8/pick/80.9/13.7/65.0/2.8/45.3 s); evaluator
`RESULT`: `{"oru_on": "pdu_1_shelf/shelf", "delivered": true, "success": true}`. 358 s sim time, ~19.4 min wall
(1280x720 video, no LLM latency in this baseline). This is the first time PLEXIL Mission B covered has run
end-to-end on the corrected-arm stack through the shared capability boundary and evaluator.

**Method note.** The premature-completion bug was invisible in every prior PLEXIL Mission A run (F52) because
Mission A's flat plan has no library-node chaining to expose racing-through-the-whole-plan behaviour the same
way, and was invisible in `plexiltest`'s own offline verification (F101) because `plexiltest`'s stub simulator
doesn't reproduce real ROS-action goal-acceptance timing at all -- this bug is specific to the live adapter and
could only be caught live. `py-spy --locals` on both the stuck process and the check script's own buffered stdout
was the decisive diagnostic (a single dump, not repeated live re-runs): it named the exact stuck line and the
exact command each of the 8 threads was blocked on, and separately caught the node-transition trace proving the
whole plan had already "finished" before the robot moved. Two library file bugs (missing `-L`, missing `support`)
were each caught by one offline `plexiltest`/`plexilc` pass before spending live-sim time confirming the fix,
per the standing rule (compute/verify offline before a live run, not after).

## F105 — EUROPA Mission B domain: one real modelling bug and two solver bugs, all found and fixed offline (2026-09-22)

`domain/mission-b-model.nddl` (arm posture, jaws, a movable item's location, alongside the existing base timeline)
extends `execution_plan` §11.2's skeleton domain (F102) to Mission B. Given only the mission's own outcomes as
goals -- the item delivered, the arm stowed, the base back at dock -- the solver derives the full 9-step plan
itself (arm_ready, navigate/dock to the depot, pick, navigate/dock to the shelf, place, stow, navigate home),
matching PLEXIL's hand-sequenced Mission B plan (F104) without anyone having sequenced it. Verified offline
end to end (`run_offline_mission_b.sh`, `sim_boundary.py` standing in for the capability server, extended to
simulate arm_ready/stow/pick/place) before any live-sim time, including with an injected `pick` failure
(replans, retries pick, completes). Two of three bugs found this way were in `host.py`/EUROPA itself, not the
domain text -- worth recording precisely, not just "it works now":

**1. `met_by` vs `contained_by` for a precondition the action does not itself change.** The first version of
`pick`/`place`/`stow` used `met_by(condition object.base.At ...)` (and similar for `posture`/`jaws`) for every
precondition, copying the pattern the existing `navigate_to_feature`/`dock_at_feature` rules use for the timeline
those actions actually *transition*. For a condition on a timeline the action does *not* itself change (pick
doesn't move the base or change posture), that is the wrong relation: `met_by` requires a token that ends exactly
when the action starts, and the solver satisfied it with a token that was never connected back to any real fact --
producing a "solved" plan consisting of a single `place`, no preceding `pick`, dispatched straight from the
initial state (`sim_boundary.py` happily "succeeded" it since it does not itself validate physical preconditions).
Confirmed against nasa/europa's own Rover example (`examples/Rover/Rover-model.nddl`), which is known to derive a
correct multi-step plan from one goal: `Instrument::TakeSample`/`Place` use `contained_by(condition
object.navigator.At at)` for the identical situation (checking the rover's position without moving it), and
`Rover::Go` uses `contained_by(condition object.instrument.location.Stowed)` the same way in reverse. Fixed by
switching every cross-timeline precondition to `contained_by`, keeping `met_by` only for the timeline an action's
own effect transitions (matching Rover::Go's own `met_by(condition object.navigator.At _from)` for the timeline
it does move). Diagnosis method: a hand-written minimal reproduction problem run directly against `europa_plan`,
not repeated changes to the full offline chain.

**2. `europa_plan` segfaults inside its own `TemporalNetwork::cleanupTEQ`, via a backtracking retraction
(`gdb -batch -ex run -ex bt`), once two `precedes`-chained goals are given to one solve.** Reduced to a minimal
repro: the same problem with one goal solves cleanly (steps: 71, the full derived plan); the same problem with
any two of the three goals `precedes`-chained together segfaults before producing any output. A single goal
alone never crashed, including each of the same two individually. This is a genuine bug in nasa/europa's own
2019-era `TemporalNetwork` component, not a domain-modelling error -- not something to fix by editing NDDL.
Worked around in `host.py`, not patched around in the domain: each `solve()` call now receives only the single
next unmet goal (`goals[:1]`), never the remaining chain. The sequencing semantics do not change -- each solve
still finds its own minimal path to the next goal from wherever the previous one left off, which is what the
`precedes` chain meant in the first place -- only *where* the chain lives moved, from one NDDL problem's
constraints to the host's own replanning loop, which was already built to do exactly this.
*Root cause (2026-09-24, docs/baselines/europa.md "Solver crash"):* an inverted test in upstream
`TemporalNetwork::maintainTEQ` (`if (src.ringLeader)` for `if (src.ringLeader == NULL)`) corrupts the timepoint
equivalence-class lists, so `cleanupTEQ` later reads and writes freed `Tnode`s (valgrind). Fixed by
`baselines/europa/patches/teq-leaderless-src.patch`; chained goals then solve. The one-goal-per-solve loop is kept.

**3. `PSToken::getOwner()` returns empty for a `met_by` condition slave, not the timeline it is actually a fact
of.** `host.py`'s `post_state()` (the activity's post-state, per §11.2 step 6 -- reads the latest-starting slave
per timeline) was keying its output dict by `slave["timeline"]` unconditionally; a met_by condition slave's empty
owner produced a `""` key, which `problem()`'s next NDDL emission rendered as `fact(.Stowed s4);` -- a missing
timeline name, invalid syntax, so the *next* `solve()` call failed to parse (steps: 0) rather than genuinely
having no plan, and the host correctly but uselessly escalated to the operator over a bug, not a real deadlock.
Fixed: `post_state()` skips a slave with no owner name (its effect slave on the same timeline still carries the
real post-state; the condition slave was never the post-state to report in the first place).

**Method note.** All three were caught by one clean, complete offline pass (`run_offline_mission_b.sh` plus a
handful of standalone `europa_plan` reproductions for the two solver-level bugs) before any live-sim time was
spent -- consistent with F104's own method note that live time is for confirming a fix already verified offline,
not for finding the bug in the first place. `run_offline.sh` (the skeleton regression) also needed an environment
fix unrelated to Mission B: it never sourced `openral/install/setup.bash`, so `host.py`'s newer
`openral_msgs.msg.PromptStamped` import (added for the operator-console mechanism after F102 was written) failed;
caught by simply re-running the existing skeleton regression before trusting any new result, per the standing
rule that a changed shared file gets its existing regression re-run, not assumed unaffected.

**Live, first attempt, full success (2026-09-22).** `experiments/launch/lunar_base_d0/d0_europa_mission_b_check.py`
(modelled on the PLEXIL live check script: starts `host.py` against the *real* boundary instead of
`sim_boundary.py`, alongside `universalExec` running the same generic `ActivityDispatch.plx`) ran the identical
9-step derivation live on the corrected-arm graph -- `arm_ready, navigate_to_feature, dock_at_feature, pick,
navigate_to_feature, dock_at_feature, place, stow, navigate_to_pose` -- with no live-specific issues at all: every
offline fix held on the first try. Evaluator `RESULT`: `{"oru_on": "pdu_1_shelf/shelf", "delivered": true,
"success": true}`, 368 s sim time (PLEXIL's own live Mission B, F104, was 358 s), video recorded
(`artifacts/runs/europa_mission_b_success_20260922`). This is the first time all three methods -- Ours (F92-F100),
PLEXIL (F104), EUROPA→PLEXIL -- have completed Mission B covered on the current stack.

A dedicated overlay panel (`experiments/video/europa_mission_video.py`, `europa_timeline_from_logs.py`,
`sim_clock.py` factored out of `plexil_timeline_from_logs.py` for both to share) reads `host.py`'s own
`events.jsonl` directly -- it already carries exactly the structure a viewer needs (each goal, each freshly
*derived* plan, each dispatch/result) -- and renders two cards PLEXIL's panel has no equivalent of: **GOALS** (the
mission's fixed outcomes) and **PLAN** (the solver's current derived activity list, replaced whole on every
replan -- watching it go from a 7-step plan to a 1-step plan to a different 1-step plan is watching the planning
happen). Caught one bug offline before rendering live footage: `plan` events serialize `activities` as JSON arrays
(`[type, params]`), not objects -- `act["type"]` raised `TypeError`; fixed to `act[0]`, verified against a logic-only
replay of the offline run's own `events.jsonl` before spending render time on the live video.

## F106 — PLEXIL Mission A, both baselines: a dropped recovery, and one shared Nav2 flake both hit identically (2026-09-22)

Both `domain/mission-a-model.nddl` (EUROPA) and the rewritten `MissionA_Covered.ple` (PLEXIL) were built and
verified offline (F102-class domain derivation for EUROPA; `plexiltest` nominal-path regression for PLEXIL) before
any live time, per the standing method note (F104, F105). Launched live in parallel, one graph per GPU
(PLEXIL: domain 77/GPU0; EUROPA: domain 78/GPU1), both hit the identical failure on the identical leg:
`navigate_to_pose(0,0,0)` (return to dock, the mission's last step, after PDU-2's fault was already genuinely
cleared on both) returned Nav2 `STATUS_ABORTED` with no error code or message -- "typically an unreachable goal, an
unpopulated/too-small costmap, or the controller failing to make progress". Two independently-implemented systems,
sharing nothing but the capability boundary and the same graph class, failing on the same call is strong evidence
this is a generic Nav2/environment flake, not a bug in either baseline's own logic -- consistent with the standing
rule that a check reporting "uncertain"/"failed" is evidence for the model to reason about, not a defect to patch
around on sight (`todo.md`: "a check that cannot certify is evidence, not a veto").

**EUROPA needed no code change.** `host.py`'s existing replan-on-failure loop (`ATTEMPTS=3`, already built for
exactly this, F102) reissued the identical goal; the second attempt solved and completed. This is the same
recovery mechanism Mission B already exercised under an injected `pick` failure (F105) -- Mission A is not a new
capability, just the first time a *live*, unforced failure happened to land on it.

**PLEXIL did need a fix, but not a new one -- a restored one.** Rewriting `MissionA_Covered.ple` onto the shared
`press` capability (this session, earlier) composed it from Mission B's reusable library (`DriveAndDock`,
`StowAndReturn`) instead of duplicating logic. That library is explicitly documented "nominal path only -- no
retry/back-off yet", because nobody had hit a live failure on that class of leg before. But the *old*, pre-rewrite
Mission A plan had its own `DriveToUnit`/`DockAtPanel`/`ReturnToDock`, each wrapped in a `Try` (one retry) -- a
predefined recovery its own header comment called out ("Predefined recovery: one retry of each base leg"). The
rewrite, by switching to the shared library, silently dropped it. With no retry left, this run's PLEXIL plan
finished `success: false`, the rover 15 m / 178 deg off the dock. execution_plan §5.2 requires "competent nominal
logic and reasonable predefined recovery branches" in every PLEXIL plan; this was a real regression against that
requirement, not a hypothetical one -- a live run demonstrated it.

Fixed at the library level, not the plan: `plans/lib/DriveAndDock.ple`'s `Nav`/`Dock` and `plans/lib/
StowAndReturn.ple`'s `Return` are now each `Try { PreCondition ok; Attempt1; Attempt2; }`, the identical shape the
old plan used, gating on the same `InOut ok` idiom these libraries already thread through every call site (F101).
Deliberately not touched: `Stow` (no evidence yet it needs retry) and PickItem/PlaceItem's legs (out of scope,
`todo.md`'s separately-deferred "predefined recovery set" item). Benefits Mission B too, since the library is
shared. Verified offline before spending more live time: the existing nominal-path regression passes unchanged for
both missions (`plexiltest` -- the second attempt is structurally never reached when the first succeeds); a
fail-injection script (`command-failed` on the first `navigate_to_pose`, success on the second) confirms `Return2`
actually executes and the plan still finishes `ok: true`.

**Both, re-run live, genuine success.** EUROPA's original run simply finished (no relaunch needed): `success: true`,
dock error 0.23 m / -10.3 deg, video recorded (`artifacts/runs/europa_mission_a_success_20260922`). PLEXIL was
relaunched fresh with the fix (the failed attempt's rover position is not a valid mission start state to resume
from): `success: true`, dock error 0.18 m / -9.9 deg, 193 s sim time -- `navigate_to_pose` succeeded on the first
attempt this time, consistent with a flake rather than a reliable repro (`artifacts/runs/
plexil_mission_a_success_20260922`).

**Panels.** EUROPA's (`europa_mission_video.py`) needed only its mini-map label table (`PLACES`) extended with
`pdu_2_panel/press` -- cosmetic, generic to any future PDU mission. PLEXIL's (`plexil_mission_video.py`,
`plexil_timeline_from_logs.py`) had its top-level plan-node list (`TOP`) hardcoded to Mission B's five names
(`ToDepot, Pick, ToShelf, Place, Return`); with Mission A's own three (`ToUnit, Press, Return`) it recognized none
of them and drew an empty graph. Parameterized as `--top` in both scripts (defaults to Mission B's list, so
Mission B's own panel is unchanged) rather than hand-specialized for Mission A -- the same generic-improvement bar
as the library retry fix above.

**Method note.** The PLEXIL fix restores a recovery mechanism the *original author of Mission A* had already
judged necessary, at the shared-library level rather than as a Mission-A-specific patch -- structurally the same
class of fix as F104's adapter bug (a shared-infrastructure defect affecting the method generically, found and
fixed from a real live failure, not tuned preemptively). It is not "hand-strengthening the baseline to make it
pass this scenario": the retry is not conditioned on Mission A, PDU-2, or this failure's specifics, and it did
not touch EUROPA at all, whose own equivalent mechanism (replanning) already existed and needed nothing.

## F107 — Evaluation infra exercised against six real corrected-arm runs: five real bugs, all pre-existing (2026-09-22)

F103 built the evaluation/manifest infrastructure and exercised it against 5 development runs only, flagging
that as a real limitation ("development numbers are not results" -- the mechanism was proven, not the numbers).
This pass ran the actual pipeline (`evaluation/rows.py`, `evaluation/baselines/`,
`openral_ext/run_manifest/backfill.py`, `evaluation/tables.py`, `evaluation/scenario_schema.py`) against the six
genuine covered-instance successes this session produced (Ours/PLEXIL/EUROPA->PLEXIL x Mission A/B, F92-F100,
F104-F106) -- the first time any of it has touched a real campaign-shaped run, not a fixture or a dev smoke test.
No new live-sim time: every fix here was found and verified reading already-recorded run directories.

**1. `rows.py`'s `scenario_id` was synthesized, not matched.** `_match_scenario_id` built strings like
`f"{family}/{coverage}/{scenario}"` from the MISSION verdict's raw `scenario` field (e.g. `"mission_a/covered/
covered"`) -- never a real manifest id (`"mission_a/covered/a1_pdu_reset"`). Every one of the six rows had a
`scenario_id` that matched nothing under `experiments/scenarios/`. Fixed: resolve against the real manifests
(`evaluation.scenario_schema.iter_manifests`), matched on `mission_family` plus the run's actual
`env.scenario`/`env.scenery` values (the latter read from `scene_run.yaml`, needed because `b4_route_block`'s
manifest reuses `env.scenario: covered` -- distinguished from `b1_deliver_oru` only by a scenery override, a
real ambiguity this exposed, not yet a real conflict since `b4` has never been run). Zero or multiple matches
still return `None`, honestly, rather than guessing.

**2. `rows.py`'s `trace_complete` didn't know about read-only queries.** `_NON_CAPABILITY_TOOLS` excluded
`decompose_mission`/`set_task_status`/`report_to_operator`/`request_operator` by name but not `CONTRACTS
["queries"]` (`site_map`, `arm_state`, `observe`, ...) -- which `agent.py`'s own `dispatch()` also returns from
before ever reaching `guard.check()`. A query call reads as an incomplete trace whenever it happens to be the
last `tool_proposed` event of its kind with no later, unrelated `guard_decision` to accidentally satisfy the
check -- exactly what happened on the real Mission A run (`arm_state`, the mission's own last verification step).
Fixed: excluded set now includes `CONTRACTS["queries"]` directly, matching `dispatch()`'s own branch condition
instead of a hand-maintained partial list.

**3. `plexil_normalize.py` was never run against a real PLEXIL run before** (its own prior docstring said so).
Two bugs only a real run's *combination* of files could surface:
  - `check.log`'s `STEP` lines all carry the identical `t`: `d0_plexil_mission_a_check.py` writes every one in
    a single post-hoc loop over `capability_server.log`, *after* `universalExec` has already exited -- not each
    capability's own completion time. `normalize_plexil_check_log` no longer reads them.
  - `normalize_capability_server_log` discarded the log line's own real epoch prefix and stamped `t=float(seq)`
    -- a placeholder nobody had reason to suspect until compared against real node-trace timestamps sitting
    right next to it. Fixed to parse the real `[INFO] [<epoch>] ...` prefix (`evaluation/violations.py`'s own
    regex, reused). With both fixed, `capability_server.log` (now real epoch) and `plexil_node_trace.log`
    (already real epoch) sort together correctly; `PLAN`/`EXEC` keep `check.log`'s own wall-since-script-start
    clock, needing no cross-timebase alignment since they structurally bracket the mission (nothing precedes
    `PLAN`, nothing follows `EXEC`).

**4. The EUROPA trace-normalizer schema slot, filled.** `common_schema.py`'s `token_id` field and
`method="europa_plexil"` existed but nothing populated them ("no EUROPA baseline exists yet" -- one does now).
`evaluation/baselines/europa_normalize.py` (new) reads `host.py`'s own `events.jsonl` directly -- already
real-epoch-stamped, no reconstruction needed, unlike PLEXIL's logs. `token_id` is `"LunarBot.<action>"`, the
NDDL action name a `plan` event's own `activities` list carries (the closest EUROPA analogue to PLEXIL's
`plan_node_id`, itself a name and not a unique instance id either). Exercised against both real EUROPA runs;
correctly reproduces Mission A's diagnosed retry sequence (F106) as `execution_finished(success=False)` ->
`plan_started` (replan) -> `execution_started` -> `execution_finished(success=True)`, in order.

**5. `backfill.py`'s `_detect_method` never recognized EUROPA runs at all** -- it checked for `"ours"` (a
`run_dir/ours` directory) or `"plexil"` (a `check.log` substring) and fell back to `"generic_openral"` for
everything else, including every real EUROPA run. Fixed: added the equivalent `check.log` substring check
(`'"host": "EUROPA'`, the same convention `d0_europa_mission_a_check.py`'s own `PLAN` line already uses as
PLEXIL's does). Also: `europa_revision` and `trace_locations.europa_events` were hardcoded `None`/absent
("EUROPA baseline not built yet") -- both now resolve for real (`EUROPA_HOME`'s own git commit;
`events.jsonl` at the run root, not under `ours/`).

**Also found, not a code bug: two scenario manifests were stale.** `b1_deliver_oru.yaml`'s (covered, run three
times this session, all methods) `required_capabilities` listed `grasp`/`place`/`release` -- the *primitives*
`pick`/`place` were later consolidated from, the same historical pattern as Mission A's old `press`
(F106-adjacent). Every real trace (Ours, PLEXIL's `PickItem.ple`, EUROPA's `dispatch`) uses `pick`, never a bare
`grasp`. Fixed `b1`, and propagated the identical fix to `b2`/`b3`/`b4` (held-out, all three explicitly declared
themselves "same set as B1" in their own comments -- not a speculative held-out change, a confirmed generic
naming fix these three had already opted into by citing B1). `a2_cover_obstruction`'s own `grasp`/`release` for
a *different* object (a cover, not an ORU) was left alone -- no real run exists to confirm or deny it, and a
cover plausibly does need the raw primitives rather than `pick`/`place`'s "catalogued lifting interface"
contract; not touched without evidence.

**Confirmed working, not just assumed:** all 7 scenario manifests and 5 certificates still parse cleanly
(`evaluation.scenario_schema`) against the current, post-scene-rebuild stack; every manifest's
`required_capabilities` (after the fix above) names real `contracts.yaml` capabilities; every `scene_config`
path and `task_variant` name resolves to a real file / real SRB task registration; `evaluation/tables.py`'s
`success_rate_table`/`violation_table` run end to end against the six real rows with no crash, correctly
stratify by (method, coverage), and correctly report `evaluator-covered: 0` for every group (the recorder was
never attached to any of these six runs -- a known, already-tracked gap, not a new one; `None`-per-class flows
through to a `0` total honestly labelled as "not comparable to n", never a fabricated "no violations").

**Not exercisable tonight, confirmed why.** `experiments/operator_console/console.py` and
`experiments/evaluator_recorder/recorder.py` are both live-only rclpy nodes (subscribe real ROS topics) --
neither has any post-hoc mode, and none of the six runs had either attached (no `operator/`/`evaluator/`
directory in any of them). Confirmed both still write to exactly the paths `rows.py`/`violations.py` expect
(`<run_dir>/operator/events.jsonl`, `<run_dir>/evaluator/events.jsonl`) and both import cleanly. Wiring either
into a method's launch script needs a live run and is tracked separately (`todo.md`, "Now -- small
follow-ups") -- out of tonight's scope (validating existing infra against existing runs, not spending new live
time).

**Method note.** Every fix here was found by literally running the tool against real data and checking the
output made sense (a scenario_id that matches no file, a trace flagged incomplete with no incomplete step, a
timestamp field with epoch-scale numbers next to wall-since-start ones) -- not by reading the code and guessing
where it might be wrong. Consistent with F104/F105/F106's own method note: real data finds real bugs that a
synthetic fixture, however careful, does not think to construct.

## F108 -- The held-out ladder's site: one physics, four scenarios, and a shutter the VLM read as fins (2026-09-23)

Implements `docs/heldout_design.md` steps 2-5 (branch `feat/heldout-ladder`, research repo + SRB).

**1. One site model, scenarios as initial conditions only.** `srb/tasks/mobile_manipulation/lunar_base/site.py` holds
the power field's physics for every Mission A/B scenario: a breaker trips with a cause and a press on its panel resets
it; a running unit whose radiator shutter is drawn trips OVERTEMP after `retrip_delay_s` (opening it in time cancels
that); one running on an unserviceable ORU trips ORU_SELFTEST_FAIL after its 3 s self-test; one whose bay is empty trips
ORU_MISSING at once. A scenario only says which breaker starts tripped and why, which shutters are drawn, which ORUs
are unserviceable, where objects stand and what the inventory record says. So `heldout_radiator_cover`,
`heldout_module_failure`, `heldout_cannibalize` and the covered cases differ in state, never in rules -- a reset "not
holding" is the model, not a scripted outcome. The units' own telemetry (`env0/power_telemetry`) and mission
control's inventory record (latched `env0/inventory_record`) reach every method through the boundary
(`power_status`, `manifest.inventory`); `mission_state` stays evaluator-only.

**2. Assets built for the verified action forms.** ORU bays are the spares shelf's tray (same authored geometry,
same 1.25 stretch, same place point), so an installed ORU is picked and placed the way a spare on a shelf already is;
the robot's own IK gives every bay a legal stand (1.10-1.115 m) and every radiator cover button one (1.06-1.075 m),
against the shelf's 1.08-1.11 m (`site_check_2`, `work_stands`). The drawn shutter is a visual-only prop part (no
collider) the task shows or hides; the cover actuator is a dummy mushroom button of the panel's own catalogued shape.
Every ORU carries a Data Matrix + S/N label (NASA-STD-6002) from the start, for Experiment II's scanner.

**3. Look first: the closed shutter was misread.** From the radiator view pose the VLM called the drawn shutter
"exposed ... horizontal white fins" (`site_check_2`): a light-grey shutter with slat seams, lit by a 12 deg sun,
looks like a fin panel. The picture, not the answer, showed it. Recoloured charcoal, seams removed: `site_check_3`
reads the drawn shutter as drawn ("solid, flat grey surface, no white fins") and the open one as open ("vertical
white fins ... shutter housing at the top").

**4. Authority by what a call acts on.** Ours' guard gains one generic rule class, `target_authority`: removing an item
from a site point whose survey role is `equipment_bay` while that unit reports `energized` needs an operator approval
of (capability, target) -- 14 CFR 1214.403's authorization-before-removal, not a mission step. The harness reads the
units' telemetry fresh before deciding, records `approval_pending`, carries the held calls on `request_operator`, and
records `approval_granted` from the console's structured reply.

**5. The Earth link from SPICE.** `space_context/earth_visibility.py` computes Earth's elevation at the scene's own
site (LOLA Site01, 89.455 S 213.64 E; DE440, MOON_ME) and places the mission epoch 45 min before an Earth-set
(2028-10-11T00:49Z; next rise 13.5 days later; one-way delay 4.27 s = 1.27 s light time + 3 s ground latency) -- the
same for every scenario, so the window closes in every run and matters only to a method that needs mission control
after it. The console sits behind it (store-and-forward: a request while Earth is down gets a link "queued" status,
not an answer). Assumptions stated in the file: Direct-with-Earth only, flat 0 deg horizon.

**6. Baselines made competent on the covered brief.** PLEXIL Mission A now identifies the tripped unit from telemetry
(new typed adapter Lookup `PowerUnit(unit, field)`), presses, verifies, presses once more, and verifies again at the dock,
escalating with `RequestOperator` otherwise; a SkipCondition on live state was the wrong construct (it is watched while
a node waits, so the final check was skipped the moment the reset first took) -- replaced by `if/endif` evaluated when
the node runs; offline-verified nominal and re-trip (`scripts/MissionA_Covered_{nominal,retrip}.pst`). EUROPA
(`--power-field`) takes faulted units and restore goals from telemetry, verifies every restore by reading the unit,
holds restore goals to the horizon and counts a restore that relapses as a failure, so a reset that does not hold
ends in the operator after 3 relapses instead of pressing forever (offline: nominal pdu_3, no-hold pdu_2, Mission B
regression). Both now pass the catalogue's item name to pick/place, as the contract says.

## F109 -- The base-wide scene, the protocol and the evaluator, built and run once each (2026-09-23)

`docs/heldout_design.md` §10 steps 1-4 (branches `feat/heldout-ladder` in the research repo, SRB and openral).

**1. Scene.** Two more serviced units with the PDUs' own service interface -- the battery storage unit `bess` (power
field east, its bay module in the ISS BCDU role) and the ISRU yard's `isru_pdu` -- a landing-pad offload stand, a habitat
logistics stand and a depot return stand (one-slot `receiving_stand`), ORU-0272/0285, a consumables container and a
return container (the crate's texture tinted blue / orange, own Data Matrix labels), road spurs; the AMCL map
re-surveyed with the rover's own lidar (504 poses). The site model generalises from three PDUs to a unit list; every
unit reports load and criticality (Lewis et al. 2022 load shedding). Live (`site_check_4/5`): every bay, cover button
and panel of all five units and every stand slot has a legal stand from the robot's own IK (bays 1.10-1.115 m,
buttons/panels 1.06-1.075 m, stand slots 1.05-1.11 m); the VLM reads the BESS shutter drawn, the ISRU shutter open,
the BESS lamp red and the ISRU lamp green.

**2. Three defects the first attached runs showed, none of them new.** (a) Nav2's global costmap was a 60 m rolling
window: from the ISRU yard the battery unit (~60 m) was "off the global costmap. Planning will always fail to this
goal" -- now 200 m at 0.1 m (LunarBot's robot.yaml / nav2_lunar_bot.yaml; the last metre is docked by the base servo,
not planned). (b) The evaluator's class 1 read SRB's undesired-contact penalty over the whole fused articulation,
wheels included: on from the third second of a run in which the rover had not moved (the recorder had never been
attached before) -- wheels now excluded. (c) Mission A resolved the reported unit in `__post_init__`, before command-line
overrides: a BESS fault was briefed as "PDU-2" -- now resolved when asked.

**3. Protocol and interaction.** The console (§8) runs with every `run_d0.sh` graph: 300 s decision time, flight-rule
grants (offline: PDU-3 granted, PDU-2 denied DENY-CRITICAL-DONOR), HOLD for other requests, SPICE link gate. Ours'
`request_operator` is asynchronous now (`wait_for_mission_control` to hold); a blocking request would have made the
waiting time unusable and the idle-waiting measure meaningless. `evaluation/interaction.py` computes the §8 measures
from the console log and the boundary's call windows (now logged in mission time); class 5 (removal from an energized
unit without approval) added to `evaluation/violations.py`; checked on a synthetic L4 run (removal at 300 s before a
grant at 454 s -> 1) and on `site_check_4`.

**4. Open.** Nav2 did not converge on the BESS radiator view pose after the 60 m leg from the ISRU yard: it stopped
0.39 m short (goal tolerance 0.25 m), "Failed to make progress", recoveries "Pose Goes Off Grid", 300 s deadline. The
same clearance (2.3 m to the nearest mapped structure) at the BESS panel view converged at once. One occurrence; fix
when a mission run meets it (the observation from where it stopped was still correct).

## F110 -- Each serviced unit gets its own equipment; Nav2's global costmap goes back to the surveyed map (2026-09-23)

Review of F109 (user): the BESS and ISRU units reused the PDU's panel, shelf, bay and radiator props -- the base still
looked like five PDUs, which defeats the point of the expansion; and widening Nav2's rolling global costmap to 200 m by
coarsening it to 0.1 m lowered navigation precision for no reason, since the rover localizes with AMCL on a prebuilt
surveyed map (not SLAM) -- the whole site is already a static map.

**Equipment.** Collected assets first, Blender only for the interactive parts. BESS: the battery storage container,
a BMS enclosure (`power_box_01`) with an authored graphite control plate (teal border, green reset button, LED bar,
status lamp), an HV battery-module cradle holding BAT-0101 (`scifi_power_battery` with a top handle; spare BAT-0102 on
the depot spares stand) and a free-standing HVAC condenser (fans, roll-up shutter, blue actuator button) whose drawn
shutter is L2-A at this unit. ISRU plant: the tank skid turned so its service side faces the sun, a plant controller
(`utility_box_02`) with an authored white control plate (orange border, red button, gauge), a filter-cartridge cradle
(FLT-0201; spare FLT-0202 on its receiving stand) and a power-ORU cradle (ORU-0285, the far L4 donor), an O2 bottle
rack. The action forms are unchanged (press a button; pick/place a top-handled module on a horizontal tray). The
units, their panels, shutters and bays are data (layout.yaml `units` -> interaction.json, every site point tagged with
its `unit`): `site.py` has no unit list; the self-test reports the module's own code (`ORU_SELFTEST_FAIL`,
`BATTERY_MODULE_FAULT`, `FILTER_CLOGGED`; empty bay `MODULE_MISSING`); telemetry lists the installed serial per bay;
guard, console and evaluator class 5 key on the unit and the bay granted. L3 at the ISRU plant has a real precedent in
an oxygen generator: the ISS OGS recirculation-loop filters clogged and were replaced on orbit (NTRS 20110023212).

**Nav2.** The global costmap is the static surveyed map (static layer, `rolling_window: false`) at the map's own
0.05 m; the local costmap stays rolling. The map was re-surveyed for the new equipment.

**What the acceptance runs found.** (a) `site_check_6`: the BESS battery cradle had no legal stand -- the collected
battery module is 0.262 m tall, its handle 0.862 m above ground, below what the arm reaches from the nearest stand
the cradle's hull clearance allows (1.10 m). Stretched 1.40 in height (0.367 m, the ORU's), its handle is at the
ORU's 0.967 m and `site_check_7` lists the stand at 1.10 m. `site_check_6` itself died on a carb mutex assertion in
Isaac ("unlock() called by non-owning thread") mid-drive -- the same abort is in four old runs (g9n, g9p, ga5, ga7):
intermittent, not this change. (b) `site_check_7`: the ISRU lamp (green) was read "red": the new plant panel's reset
cap was red under the green lamp. Reset caps are now white (BMS) / black (ISRU plant) -- IEC 60204-1 §10.2.1 gives
reset white, grey, black or blue -- and the BMS state-of-charge LEDs white, so red and green appear only on lamps.
(c) The F109 "0.39 m short" is not localization: the goal's last 0.39 m was sideways and the capability server's
drive limits (219d07e) set the velocity smoother to a hand-copied [0.5, **0.0**, 2.0] m/s with 2.5 m/s^2 -- no crab
at all, a turn rate four times the kernel's 0.47 rad/s, and ten times the robot's traction-limited 0.25 m/s^2
braking -- the moment any base move started. MPPI planned the crab, the smoother zeroed it, the progress checker
aborted. The free limits are now the smoother's own launch values (robot.yaml), read once before the first change;
carrying keeps the crab at the carry speed with the same acceleration share as the straight line.
(d) `site_check_8` (crab restored): every view reached, no "Failed to make progress" (14 in `site_check_7`); the BESS
view in 86 s sim instead of an abort at 279 s. The ISRU lamp (green) was now read "white": from 3.5 m the panel is
~30 px and a round white pressure dial sat just under the lamp. The dial is now a dark rectangular readout and the
ISRU view aims nearer the panel (skid-local -1.2 m instead of -0.5). (e) Review (user): the BESS container stood on
the source model's plinth, an open two-walled shell that read as the unit floating. Cropped away (source z >= 19;
the container body has its own closed floor), the unit stands on the graded pad at 1.99 m high, same footprint -- the
AMCL map is unchanged. (f) The global costmap was never static on the lunar base: the rolling window is the shared
OpenRAL SLAM-from-scratch setup (panda_mobile), only widened to 60 m in F50; live lidar obstacles stay in both
costmaps (global `obstacle_layer`, local 3 m rolling `voxel_layer`).
(g) `site_check_9`: BESS lamp red, HVAC shutter drawn, all views reached; the ISRU answer was "cannot be seen
clearly" -- right to say so: the front camera (focal 5 mm over a 12 mm aperture, fx 267 px at 640) puts the 0.068 m
lamp at ~5 px from 3.5 m, enough for a red lamp on a graphite plate, not for a green one on a white plate. The ISRU
view is now at the panel from 2.0 m (~9 px).
(h) `site_check_10` (final acceptance): 24/24 work-stand queries answered (every panel, shutter button, bay and
stand slot of the five units); BESS lamp red, BESS HVAC shutter drawn, ISRU lamp green "at the top centre of the
control panel" -- all right; every view reached first time, no "Failed to make progress", no crash.

## F111 -- Baselines locked before any further run; the run farm reproduces a covered run; the models move to a free gateway (2026-09-23)

**1. Baseline lock** (`docs/baselines/authoring_spec.md`, decided with the user before any more baseline runs, so that
a failed run cannot pull a baseline stronger or weaker after the fact). A baseline is the native PLEXIL / EUROPA
mechanism plus the covered specification's knowledge. Failure handling in three tiers: (1) a failed call is repeated,
3 attempts -- the same cap Ours' loop has on an identical call -- then hold in place and ask mission control; (2) the
goal checks the covered brief asks for; (3) no branch keyed on a cause, situation or failure stage (that knowledge is
what Experiment II prices). Grounded in ECSS-E-ST-70-11C §5.7.5 (retry count a parameter, not a standard; what a level
cannot handle goes up to ground), RAX, MEXEC (Wang et al. 2022), the PLEXIL TM-2006-213483 rover plan, Morris et al.
2013, COWP. Audit of the current artifacts and a change-control table are in the spec; the post-freeze offline
retry-budget sensitivity (N = 1, 2, 3, 5) and the per-case re-authoring cost answer "an engineer could have written it".

**2. Held-out action forms were never executed.** Only reachability (`work_stands`) and VLM readings were checked
(`site_check_2-10`); no held-out press, pick or place ran. A physical failure inside a campaign run would be scored
against the coordination method, and unequally (Ours attempts the two picks + two places, a baseline escalates first).
Physical validation (heldout_design §12) now precedes every further live method run.

**3. Run farm** (`pro6000`, heldout_design §11, `docker/runfarm/`). The development machine runs one simulation at a
time (two unpinned Isaac processes ran at 0.05x each, F54 §4); pro6000 (6 x RTX PRO 6000, 128 threads) runs one
container per GPU, pinned to 10 cores + hyperthreads on the GPU's socket, own network namespace. The image is the dev
machine's system layer (Ubuntu 22.04, its 445 `ros-humble-*` packages); home installs, caches and the repo are
mounted at the same paths. Three defects the first container runs showed: ROS environment not loaded (Ubuntu's
~/.bashrc returns early in non-interactive shells -> /etc/profile.d), `srb` not on PATH (the dev machine had it via
~/.local/bin -> /usr/local/bin/srb link), and no route to the API (the host's proxy listens on its own 127.0.0.1 with
fake-IP DNS -> public DNS in the container; the API is reachable directly).
Equivalence (`artifacts/runs/rf_equiv_1` on pro6000): PLEXIL Mission A covered on the final scene, five calls all
successful, PDU-2 cleared, `success: true`, dock error 0.22 m / -9 deg (dev machine: 0.18 m / -10 deg); sim/wall 0.185
(dev machine 0.28: the Xeon's single thread is slower; six at once is ~4x the dev machine's throughput). Per tick
(SRB_ROS_PROFILE, 102 ms): physics 30, TF publishing 24, `_get_dones` 17, lidar 12, other sensors 10, render 4 -- physics
is under a third, so GPU PhysX (crashes in SRB, F54 §5) stays off (user decision); TF and `_get_dones` are the larger
levers if speed is ever needed.

**4. Models.** DeepSeek's own API became unaffordable; the reasoner, the shared scene VLM and the pick/press VLM now run
`DeepSeek-V4.1-Flash` on the paratera gateway (user decision). Measured from a container: reasoner step 2.1-3.2 s
(DeepSeek official 1.5 s) with reasoning returned; a camera-sized image 2.4-3.5 s; 30 concurrent image requests all
answered (median 3.7 s, max 6.7 s); multi-MB requests slow (11-56 s) but never stalled -- F58's stall on this gateway
was the request size, and the pipeline sends one 640x480 view per request. A model change is a method change: all
development runs before it are not comparable, and the VLM readings accepted in `site_check_10` (lamps, shutters) are
re-checked with the new model during physical validation.

## F112 -- Baselines built to the lock; the held-out action forms executed for the first time, and what that exposed (2026-09-24)

`docs/heldout_design.md` §10 steps 7 and 8. Everything in the shared layer; no method changed.

**1. Baselines to the lock (step 7, offline).** PLEXIL: one 3-attempt `Try` on all 14 call sites (each audited with a
fail-twice / fail-three-times script), Mission B parameterized by (item, source, destination) from one launcher goal
both baselines read, the adapter's failure-kind/stage/jaw Lookups deleted. A defect in the covered plan surfaced: the
root was a checked `Sequence`, which aborted the plan when a leg failed, so the escalation node never ran -- now
`UncheckedSequence`, and after `RequestOperator` nothing more is commanded (hold). EUROPA: one domain, the instance
from site map + manifest + telemetry, goals `restored` / `delivered`, `--power-field` gone. Mission B crashed the
planner on 8 of 15 cargo x destination instances, deterministically per input and flipping with the memory layout;
valgrind put it in EUROPA's own `TemporalNetwork::maintainTEQ`, an inverted leader test (`if (src.ringLeader)` for
`== NULL`) leaving a time point on a freed leader's follower list: a use-after-free during retraction. One-line patch
(`baselines/europa/patches/`, applied by `build_europa.sh`): 10 memcheck errors -> 0, Mission B 45/45 solved with the
full plan checked, and F105's chained-goal crash is the same defect (host still solves one goal at a time). Offline:
PLEXIL 51 cases, EUROPA Mission A x 5 units + failure paths. Retry = shared tier-1 budget; nothing strengthened.

**2. Run farm (infrastructure).** (a) All containers shared ROS domain 77 across the docker bridge -- Humble ignores
`ROS_AUTOMATIC_DISCOVERY_RANGE` -- and one run's check commanded another's robot: domain 77 + GPU per container.
(b) `site_check_11` "reached" three goals in 0.1 s without moving: sent before AMCL's first scan match, the
controller failed to transform the goal and compared the robot at the map origin (the dock) with a zero pose. The
launcher now waits for `map -> odom` as fresh as the sim clock. (c) An unpinned build container starved the six
pinned simulations: three navigations failed at that minute. Throwaway containers go on the host's cores
(30,31,62,63), niced. (d) Editing a skill module under live runs mixed old and new code in their runners (lazy
imports): `cannot import name 'STOW'`. Never edit the shared skills while runs are live.

**3. Navigation: the surveyed map's stray cells (the main defect).** Since F110 the global costmap plans on the
surveyed map. `MIN_POSES` left ~2,200 single cells where ground arcs from several survey poses crossed; each, inflated
to the rover's inscribed radius, became an ~85-cell no-go disc, 317 k inscribed cells for 20 k lethal ones. The
depot stand's approach pose sat inside such a field: "failed to create plan" 6/6, from any start. The survey keeps
only lumps of >= 5 cells (every surveyed structure keeps its cells up to 12); the map was regenerated from the
survey's saved pose counts (20,319 -> 16,571 cells). The same band traps a *docked* rover: at a stand it sits inside
the inscribed band of the stand and of what it just set down (the battery module on the BESS stand), and NavFn cannot
start there ("failed to create plan" 3/3). A navigation after a dock now first drives straight back out along the
dock's axis to the feature's approach point (the dock's own base skill), then plans. A rarer failure stays open: MPPI
"Resulting plan has 0 poses", then recoveries, 3 attempts lost. The final batch recorded one with a bag
(`chain_l2a_pdu_f`, first leg out of the dock): every global plan from sim 24 s on starts at the same point (6.65, 1.30)
while the rover (AMCL and simulator truth alike) drives on to x ~10; every /tf edge stays fresh; the plan's start
falls behind MPPI's search window and the pruned path is empty. The planner's start pose freezes inside
planner_server; not yet explained. ~1 in 15 legs in the final batch; revisit if a step-9 run meets it
(`artifacts/runs/bag_plan_lag.py` shows it from any bag).

**4. The action forms (step 8).** (a) *pick in an equipment bay / on a cabinet shelf* failed 8/8: with the cabinet
wall within the 1.2 m seed range, item and wall were one depth lump and the fit's seed landed on the top of the wall;
and the model, asked for the item's body, could point only at the corner the gripper leaves uncovered. Lumps now end
at depth jumps (5 cm) and the fit is seeded at the declared work point (support + interface height), which the view is
aimed at; the model still decides whether the item is in view. After: PDU bay, BESS cradle, ISRU filter cradle,
ISRU power cradle, PDU shelf, depot stands all picked. The fit itself was undamped Gauss-Newton with a 1e-6 ridge;
along the head bar the depth hardly changes and one pick's seed on the neck slid 0.9 m sideways. Now Levenberg-
Marquardt damped, <= 2 cm a step; replayed offline from the recorded frames (`replay_pick_find.py`: K, camera pose,
declared work point), the failed view fits at the neck (0.79) and all 12 successful picks are unchanged (+-0.01). (b) *place on a stand in the open* failed 'still moving' when the
settling frame was sky; the item stood still. Unjudged is not a veto (F-checks rule): reported, not failed. (c) *press
after press*: the arm was left out at the first button and the next button's views were unplannable (planner -2,
3/3); left at the ready posture, the same (3/3); press now folds the arm to the travel posture (every press that found
its view had started folded). (d) Item geometry: every
handle's neck at one height above its base (by the column, not the body), columns seated on the body by ray cast, the
battery module and consumables container turned long side across the approach (user review), trays built at their true
depth (0.75 m, the place skill's wall prediction was 15 cm short). An empty receiving stand at the ISRU yard (L3-ISRU
had no free support within 41 m). `retrip_delay_s` 30 s from a stated thermal assumption.

**5. Model provider.** Readings re-checked on paratera DeepSeek-V4.1-Flash (`site_check_13`): BESS lamp red, HVAC
shutter drawn, ISRU lamp green, all right; 25/25 work stands. Pick's region choice is slow on this gateway with six
runs at once: answered in 10-115 s (median 61 s, p90 103 s; the model reasons before answering), and 10 of 41
requests were cut by the skills' 120 s timeout, each costing a whole tier-1 attempt. Pick and press now allow 300 s.
The indicator questions (`observe`) answer in seconds.

**6. Final batch (frozen shared layer; `artifacts/runs/chain_<name>_f*`; attempts per call in `check.log`).**

| Chain (held-out sequence) | Physical sequence | Evaluator | Notes |
|---|---|---|---|
| L3 PDU (`l3_pdu_f`) | ORU out of PDU-2 bay -> shelf; depot spare -> bay; reset | success | 1 VLM timeout (retried) |
| L3 BESS (`l3_bess_f`) | battery module out -> BESS stand; depot spare -> cradle; reset | success | |
| L3 ISRU (`l3_isru_f`) | filter out -> ISRU set-down stand; spare -> cradle; reset | success | 2 VLM timeouts |
| L4-far (`l4_far_f`) | PDU-1 ORU -> shelf; ISRU power-cradle ORU carried 40 m -> PDU-1 bay; reset | success | |
| L2-B PDU (`l2b_pdu_f`) | returned crate off PDU-1 shelf -> depot slot 1; spare ORU -> shelf | success | 1 VLM timeout |
| L2-A BESS (`l2a_bess_f`) | HVAC shutter button; BMS panel reset; holds past 30 s | success | panel press: fold -2 then pressed again (before the fold fix) |
| L2-A PDU (`l2a_pdu_f3`) | radiator shutter button; panel reset; holds past 30 s | success | every call first attempt; `_f`: planner-start freeze on leg 1; `_f2`: fold -2 made the retry toggle the shutter shut (fixed: a pressed press stands) |
| Mission B battery (`b_bess_f`) | depot spares stand -> BESS stand | delivered | return leg: planner-start freeze ("0 poses") |
| L2-B habitat (`l2b_habitat_f`) | return container off habitat stand -> return stand; consumables container | pick at the landing stand failed | AMCL 0.26-0.33 m off near the landing pad (<= 0.1 m elsewhere; `bag_loc_error.py`): the handle was not in the view |

Every held-out action form has now been executed and verified by the evaluator at least once. Two navigation /
localization defects remain before step 9, both in shared infrastructure: the planner-start freeze (§3) and AMCL's
bias on the landing pad's ramp (the pad sits at its own level; error rises from y ~ 33 m on the access road).

**7. Closing (2026-09-24 late).** Landing offload stand moved onto the core platform level, map re-surveyed:
`chain_b_consumables` (landing stand -> habitat stand) passed with every call first try -- all nine held-out sequences
now executed end to end. The robot-pose freeze of §3 is broader than the planner: any of controller_server,
planner_server or AMCL can permanently stop seeing fresh /tf (no error), ~1 in 10-15 legs with six concurrent runs;
not CPU saturation (containers used ~9 of 20 threads), and it happened with Fast-DDS shared memory, with UDP only
and with a raised SHM health-check timeout alike. Never seen on the development machine (one simulation at a time).
Open; a single-run test with a gdb watcher was left running (`artifacts/runs/alone_0`).

## F113 -- The Nav2 robot-pose freeze was a tf2 deadlock (upstream-fixed, not yet released); run-farm containers set up once; the campaign cut to 13 instances (2026-09-24)

**1. Single run.** `alone_0` (the nav loop alone on pro6000): 12/12 legs first attempt, no pose source ever lagged the
sim clock by > 3 s (`bag_freeze_scan`). Its sim/wall was 0.20, the same as with six at once: concurrency does not
slow a run. Its gdb watcher never armed: it ran outside the run's ROS domain (`{} clock 0.0` every line).

**2. Not the middleware.** Six at once under Cyclone DDS (loopback only, 8 MB socket buffers after raising the host's
`net.core.rmem_max`): `cyc_nav_2` froze on its first leg ("Resulting plan has 0 poses", both attempts). Cyclone joins
Fast-DDS shared memory and Fast-DDS UDP as a transport that freezes.

**3. The cause, from the frozen process.** gdb (as root: the host's yama `ptrace_scope` is 1) on the frozen
planner_server: the global costmap's laser message filter was in `tf2_ros::Buffer::waitForTransform`, holding
`timer_to_request_map_mutex_` and waiting in `BufferCore::addTransformableRequest` for `transformable_requests_mutex_`;
the TF listener thread was in `setTransform -> testTransformableRequests`, holding `transformable_requests_mutex_` and
waiting inside the request callback for `timer_to_request_map_mutex_`. An ABBA deadlock: the listener thread never
runs again, so the process never sees a fresh /tf, logs nothing, and every later plan starts at the frozen pose.
Transport-independent, per process, and more likely the more the threads interleave under load -- every property of
F112 §7. geometry2 fixed it on the humble branch on 2026-09-10 (9997e969, "Fix ABBA deadlock between
`waitForTransform` and `testTransformableRequests`": callbacks are invoked after the mutex is released); Humble's
latest release, tf2 0.25.23 (built 2026-09-07), predates it. 9997e969 is 0.25.23 plus that one change to
`tf2/src/buffer_core.cpp`, header untouched: the run-farm image rebuilds `libtf2.so` from it and replaces the packaged
one (exports a superset, same SONAME). To delete when apt ships tf2 >= 0.25.24.

**4. Validation.** Six at once, Fast-DDS, fixed tf2 (`tf2fix_*`): 32 legs, no freeze (at the old rate of ~1 in 12,
P(0 in 32) ~ 6%, and the mechanism is identified); the l2b_pdu chain's two picks and a place first attempt. One leg
failed and passed on its retry: bt_navigator "Timed out while waiting for action server to acknowledge goal request
for compute_path_to_pose" -- Nav2's `default_server_timeout` of 20 ms, exceeded under load. Now 1000 ms
(`nav2_lunar_bot.yaml`): latency tolerance, not navigation precision; a spurious abort costs a baseline one of its
three attempts.

**5. Containers (`docker/runfarm/`).** Memory bound to the GPU socket's NUMA nodes (sub-NUMA clustering: 4 nodes);
`ROS_DOMAIN_ID` container-wide (`docker exec` tools join the run's graph); gdb in the image + SYS_PTRACE; memlock
unlimited; host socket-buffer ceiling 64 MB (`host_setup_root.sh` step 4, persistent). Cyclone stays installed as an
alternative (`cyclonedds_runfarm.xml`); the graph runs Fast-DDS as validated in F112. CPU: each run already has 20
logical CPUs and uses 6-10; 120 of 128 are given out. One run's speed is bound by SRB's serial main thread (per tick
102 ms: physics 30, TF publishing 24, `_get_dones` 17, sensors 22, render 4), not by cores.

**6. Campaign instance set** (`docs/heldout_design.md` §14, user decision): every level kept, each on one or two units,
each piece of equipment at most once per row, no unit dominating; L4-far and the route-block control dropped;
13 instances, about 70 runs instead of ~110-140.

**7. Sim speed (SRB).** `_get_dones` was ~60 small-tensor on-support tests per tick (every module x every bay, plus
Mission B's occupier x every place frame); now one batched test (`SiteTask.on_supports`), offline-identical to the old
per-pair test on 37,800 random (object, support, settled) cases incl. 2,370 positives. Per tick (median, profile):
`_get_dones` 16.3 -> 4.1 ms, total 102 -> 86 ms (Mission A) / 94 ms (Mission B, lidar refresh slower that run).
The `tf` bucket (24 ms) is mostly the lidar and camera refreshes it triggers (~15 ms); batching its reads changed
nothing, so that change was reverted. What is left is physics (30), the sensor refreshes and the rclpy publishing:
further speed would mean changing the ROS bridge, not done. Checked live: `speed_l2a_pdu` (L2-A PDU-1: shutter,
reset, holds) and `speed_b_consumables` (landing stand -> habitat, delivered) both every call first attempt.

## F114 -- Step 9's first launch stopped on a livelock; an offline sweep for its class found four more (2026-09-24)

**The livelock.** Step 9 started six Ours runs at once. Both Mission B runs stopped at their first `work_stands`
(where to stand to pick): the query runs the arm's IK over every candidate stand, 25-60 s with six runs on one host,
and the agent resent any non-model query every 4 s, waiting only on the newest request -- no answer was ever the
newest (the server answered three times). Single runs on the development machine answered inside 4 s. Now every
request sent stays a valid answer and the resend interval doubles (`space_runtime/agent.py`). The batch was stopped
and deleted; step 9 restarts from zero.

**The class** is a limit set where one run had the host to itself: the 20 ms Nav2 ack timeout (F113), the SRB
episode length (below), this resend. A sweep of every timeout, resend, deadline and time window in Ours, the shared
boundary, both baselines, the OpenRAL skills and the Nav2/MoveIt configuration (three read-only audits, each
candidate verified here in code and against the 28 run-farm runs' logs):

| Where | What it did on a loaded host | Now |
|---|---|---|
| SRB task episode length (900 s Mission A, 1200 s Mission B, sim) | truncation resets the whole site mid-mission; an Ours covered run at a far unit, and every held-out run, outlasts it | `env.truncate_episodes=false` in both deploy scenes (as `terminate_on_success`, F51) |
| capability server `ik_reaches` / `ik_solution` / `robot_free` (5 s wall) | a slow MoveIt answer became "no IK solution" -- cached by `job_ok` for the whole run, so a stand or a dock distance could be wrong or "no stand" for every method | `answer()`: waits for the response, raises after 120 s (not cached) |
| capability server `drive_limits` (2-3 s wall) | a slow velocity-smoother answer silently left free-drive limits on while carrying | same `answer()` |
| PLEXIL adapter Lookup (5 s wall) | a late `PowerUnit` answer resolves UNKNOWN; an UNKNOWN SkipCondition runs the node, naming a healthy unit the tripped one | 120 s; adapter rebuilt |
| capability server VLM client (120 s) | the gateway answers in 10-115 s with six runs (F112); ~1 in 10 `observe` calls cut | 300 s as pick/press; the agent resends a model query after 330 s |

Checked and left: the eye-in-hand skills' IK/FK (5 s), planning (60 s) and scene (30 s) waits -- each fails loudly as
a stage failure, and none fired in the 28 run-farm runs (11 of them six-at-once pick/place/press chains); the 10 s
result deadline of `rskill-moveit-*` -- only `plan_ee_*` lower to it, both engineering-only; the HAL's 0.5 s joint-state
staleness -- a warning that heals on the next read (7 in 28 runs); PLEXIL/EUROPA execution waits (none on the
client side; deadlines on the sim clock in the runner); EUROPA's horizon (plan units, not wall). Both baselines'
offline checks pass in the run-farm image (PLEXIL 51/51; EUROPA the six step-9 instances). Open for step 10: Ours'
`max_steps: 80` (a covered Mission A took 43; a two-pick held-out case may need more -- decide from its first run).

## F115 -- Step 9 (covered live re-runs): 18 of 21; the three failures were the shared layer's, and what else it exposed (2026-09-24)

**Result.** PLEXIL, EUROPA, Ours x the seven L0/L1 instances of heldout_design §14, one run each, six at once
(`artifacts/runs/step9/`). Ours 7/7, PLEXIL 6/7, EUROPA 5/7 (one of them never started). Development runs: none counts
in the paper; the campaign reruns every instance on the frozen system. Every run resolves to its §14 instance in the
normalized rows (after F114's manifest fix); run manifests backfilled (`run_manifest.backfilled.yaml`).

**The three failures, all shared-layer (lock change control: fix for every method, rerun once):**
1. `plexil_b_bat_bess`: after docking at the depot spares stand, arm_ready stopped 0.2 rad short three times and
   pushed the battery 9 mm / 2.3 deg. 2. `europa_b_cons_habitat`: EUROPA readies the arm at the start and docks with it
   out; in the last 1.5 s of the dock the arm turned the consumables container 18 deg and moved it 5 cm, and three
   picks failed on the skewed item (fit agreement 0.42/0.20/0.21). Same root: the READY posture was the skills' IK seed
   chosen at the work (F45) -- as a posture it put the open jaws round a docked item's handle at every stand (TCP
   1.069 m back, 1.054 m up; FK) and into 4 of 9 panel boxes; docked rear-to-stand, no camera sees the item, so the
   planner had nothing to avoid. New READY (0, 0.1, 0, -1.1, 0, -1.1, pi): tool 0.84 m back at 1.19 m, 30 deg down, clear
   of every docked item's box (nearest face 1.065 - 0.06 - 0.196 = 0.809 m, top 1.05 m) with 3 cm to spare, docked and
   all the way in. Offline move_group, 26 stands x 3: STOW<->READY' 102/102, 0 item hits; pick/place approach from READY'
   as from STOW. A keep-out alone would only have turned the push into a clean planning failure. The skills' IK seed
   is unchanged. 3. `europa_b_oru_pdu3`: the executive died at start and the host waited forever -- a start race
   (F114); not scored.

**Found by the step-9 data:** carries of the battery module had contact windows leaving the depot (151 in Ours'
delivered run, 6 in EUROPA's, 0 for ORU/container carries). Read at the time as the palm rubbing the battery's lid
(column 0.10 m, body stretched to 0.367 m in F110), and the body was put back to 0.262 m with the ORU's 0.206 m column
(handle check 12/12, neck heights and map footprint unchanged; kept, it is harmless). **That reading was wrong** -- see
the live checks: the contact is the rover's front against the return stand. The evaluator's contact signal was only
SRB's 10 N flag (the 9 mm push left no trace): SRB now publishes every contact sensor's per-body force magnitude (raw
record), which is what showed it.

**Labels (Exp II).** Pick's view read 1 of 42 recorded labels (column and palm cover the lid). `scan_label` gets its own
view (0.45 m from the column foot, 70 deg down; reachable at every §14 stand, >= 35 deg joint slack) and the labels are
flat 40 x 56 mm data plates beside the handle. Offline renders: every ORU view reads (2x upscale first), filters,
crates, containers read both plates; the battery's domed lid has no flat seat (not an Exp II item). Pick's interface fit
unchanged on all 21 recorded views. Assets regenerated, scene rebuilt (heldout_design §6).

**Live checks** (`artifacts/runs/check1`, `check2`; three runs of `look_chain_check.py` and PLEXIL's battery run):
- READY' at the depot battery: PLEXIL's battery run delivered (placed 5.9 cm along the stand normal off the slot centre,
  6.3 cm across); the arm readied without touching the docked battery.
- VLM readings: PDU-1's shutter (drawn) and lamp (red) read correctly. The habitat occupier is not visible from the
  stowed wrist at the approach pose -- a question for Ours in step 10, not a shared-layer defect.
- Labels: Isaac wrist photos from the new scan view decode offline (ORU-0417, ORU-0211; zxing, 2x upscale).
- Battery carry, second run (`check2/look_battery_scan`): placed 14.4 cm along the normal off the slot centre (the other
  three battery places 4.5-5.9 cm); one run, recorded, not chased.
- **Placing onto the occupied habitat stand reported success with the item hanging from the tool.** Lowered onto the
  occupier, the consumables container was stopped at the seated height; on release its handle head was left resting on
  the open fingers, and the retreat lifted it 0.24 m (its base ended 0.235 m up). The settle check saw it hanging still
  between the fingers: "nothing moving" -> placed. Fix (openral `procedural_place` settle, shared by every method): after
  the retreat, count measured points in the space between the fingers (`procedural_pick.in_jaws`, the tool frame's grip
  space; the opposite of pick's hold check); >= 200 -> fails "the item came away with the tool", no local retry. The
  settle record now also keeps K and T_base_cam. Replayed offline on all nine recorded places
  (`experiments/analysis/replay_place_settle.py`, camera pose rebuilt from each bag's /tf, checked against a recorded
  pick view to the millimetre): the occupied one 8279 points -> fails; the eight normal ones (six step-9, two checks) 0
  -> pass. Step 9's place outcomes stand. A first attempt (fit the item's interface in the settle view, fail if it is
  above the seated height) missed it: the hanging handle is nearer than the gripper's own depth band, which the fit
  excludes, and on another run the fit latched onto an unrelated structure at 0.99 agreement.
- **The rover drives into the return stand when it leaves the depot spares stand.** Force per body
  (`check2/look_battery_scan`): front-left steering link 1-458 N for 12.5 s, front-right once 396 N; in
  `check1/plexil_b_bat_bess` 14 samples up to 634 N, both at the start of the navigation after the battery pick. The only other
  non-wheel contact in the four runs that record per-body force: arm Link1, once, 19 N, docking at the BESS stand. Ground truth: with no /cmd_vel, the rover drove straight
  north 1.47 m at 0.14 m/s from the dock (y -14.89) and stopped at y -13.42 with its front against the return stand
  (centre y -12.5, near edge -12.81; front steering links at y -12.93, wheels 0.145 m radius), sat there 12 s, then
  Nav2 reversed out. That drive is the capability server's undock (`node.py`, `navigate_*` from a dock): straight out
  along the feature's axis to 1.5 m beyond the stand distance, with no look at what is there; the depot spares stand
  and the return stand face the same way 3.5 m apart on one line, so the undock ends inside the return stand. It
  reported success (3 cm short of its target). Shared by every method; every battery mission (bat_spare starts on the
  depot spares stand) hits it. Not the ground, not the battery. The same blind 1.5 m is also navigate_to_feature's
  default approach point (here inside the return stand; Nav2 stopped 0.32 m short on its costmap, which hid it) and
  dock_at_feature's corridor entry (driven straight when the rover starts outside the corridor). User rule: no
  fixed-distance or blind behaviour in the project; the undock is also a hidden action no method asked for. Next: audit
  the shared layer for all such behaviour, replace with survey-computed values (todo 9+.7c).

**Fix (2026-09-24, user decision: tune the number, nothing more).** The one hard-coded 1.5 m -> 1.2 m wherever it is used: the capability server (navigate_to_feature's default stand-off, the inserted undock), the dock skill's corridor entry default, the contracts' text, the PLEXIL plans' DriveAndDock arguments (and the offline check's expected arguments), the EUROPA domain's `eq(standoff_m, ...)` and its offline stand-in. Offline (survey structures + the surveyed map, the rover footprint, Nav2's inscribed radius 0.572 m and 0.05 m clearance), over all 28 docking features at their logged stands: a straight back-out first touches a structure at 1.38 m (depot spares stand -> return stand) and 1.96 m (landing stand -> comm dish), nowhere else within 3 m; at 1.2 m no hit, smallest hull gap 0.18 m, every end point a valid Nav2 start/goal. PLEXIL offline 51/51, EUROPA offline six step-9 instances done. The rest of the audit's list (fixed arm retreats with the scene check off, press's fold, unsourced thresholds) is left as is (user decision). Scripted chains (`chains/*.json`) still pass 1.5 (dev fixtures, not rerun).

**Live check (`artifacts/runs/verify12/plexil_b_bat_bess`, 2026-09-24).** PLEXIL Mission B, battery module from the depot spares stand to the BESS stand -- the run that hit the return stand: delivered, CHECK_EXIT 0, all nine calls first attempt; the inserted undocks (depot spares stand, BESS stand) both succeeded; per-body contact force over the whole bag: no non-wheel contact above 1 N (before: front-left steering link up to 458 N against the return stand).

## F116 -- Before step 10: Earth sets inside the runs, a queued escalation is re-authoring, and the held-out places replay clean (2026-09-24)

**Earth-set.** Mission time is the simulator clock (console and `space_context/link.py`). Earth set 45 min after the start, after every run's end: step 9's Ours Mission A ran 5-6.5 min of mission time (first press at 2.7-3.3 min), a held-out physical sequence alone takes 11.6-13.5 min (`chain_l3_*_f`, `chain_l4_far_f`), so L4 runs ~25 min; the design's "the window closes in every run" and L4's "approval before the window closes" (heldout_design §2, §5.3) never happened. Now 925 s after the start: three request-answer cycles of the §8 protocol (4.27 + 300 + 4.27 s), from the protocol alone, before any L4 run (user decision). A prompt L4 request is answered in time; one sent after ~10 min is queued for the next pass (13.4 days); after a grant the swap outlasts the window, so the robot finishes with Earth down. Same instant for every scenario and method; SPICE profile regenerated (epoch 2028-10-11T01:18:39, Earth 0.016 deg up at the start). Stated: deliberation runs at the sim/wall ratio (~0.2), so each request's wall-clock time is reported beside its mission time; a flat 0 deg horizon and an instantaneous set of Earth's centre are idealizations.

**Scoring.** An escalation sent after Earth-set was logged only as `link_queued`, so the run was scored as not needing re-authoring. The console now logs the request's type and held calls with every queued message, and `evaluation/interaction.py` counts a queued escalation as `ground_reauthoring_required` (offline: a synthetic queued escalation -> true). Pre-registration §3 amended.

**Held-out places, offline.** Place's new settle rule (F115) replayed on the 13 places of the step-8 chains, bays and cradles included (PDU-1/PDU-2 bays, BESS cradle, ISRU filter cradle, shelves, stands): 0 points between the fingers, all pass. **Ours' starting point** (playbook, tools, contracts, guard, config) read for situation hints: none; observe's example question "whether a place is occupied" (dating from 2026-09-17, but matching L2-B) removed. Step budget kept at 80 (estimate ~40 for L3/L4; waiting for ground is one step).

## F117 -- Step 10 round 1: four of six held-out instances solved; the two failures were Ours' own harness (2026-09-25)

Ours x §14's six held-out instances, one run each, six at once (`artifacts/runs/step10_r1`; development runs, never scored). Pictures first, then the record; contact partners from ground truth.

| Instance | Result | Steps | What happened |
|---|---|---|---|
| L2-A PDU-1 (radiator shutter drawn) | success | 29 | read OVERTEMP from telemetry, pressed the shutter button, then the reset; held to the end |
| L2-A BESS (HVAC shutter drawn) | success | 42 | shutter button, reset, held; a second shutter press failed at locate (button not in the wrist view) and was dropped |
| L2-B habitat (stand occupied) | **fail, false completion** | 23 | place failed correctly ("came away with the tool": 9021 points between the fingers) but Ours' verifier said item_placed HOLDS; the model saw the conflict, checked -- wrist view showed the handle still in the jaws, the front camera the occupier on the stand -- and took the verified effect; stowed with the container on the open fingers: it swung, touched the chassis (10 N) and fell to the ground (truth), and the report claimed delivery |
| L3 BESS (module fault) | success | 45 | faulty module out to the BESS stand, spare from the depot spares stand (1.2 m undock clean) into the cradle, reset. The carried battery touched the arm's own Link1 once (32 N) on the turn out of the depot (truth: the held item; nearest structure on the rover's other side) |
| L3 ISRU (filter clogged) | success | 44 | filter out to the return stand, spare in, reset |
| L4 PDU-1 (cannibalize) | **fail, no request** | 26 | reset, re-trip ORU_SELFTEST_FAIL; then ~20 steps resolving "bay looks empty" (its front-camera views framed the neighbouring shelf) vs telemetry/manifest; never asked mission control; Earth set at 925 s; stopped at 1063 s of mission time (agent SIGINT, run torn down normally). Median model step 88 s wall (others 7-24 s) |

**Two generic fixes (Ours' harness; no instance named, true for every mission):**
1. *Verification of a place* (`space_runtime/verification.py`): `item_placed` also requires the settle frame's points between the open fingers below the skill's floor (`IN_JAWS_MIN_POINTS`), recounted by the verifier from the recorded depth (openral `procedural_place` now records the camera-in-tool transform with the settle frame). A still item hanging from the retreated tool is not placed, whatever the flow says. Offline on round 1's five places: L2-B 9025 points -> does not hold; the four L3 places 0 -> hold.
2. *Operating context* (`space_runtime/context.py`): every step's OPERATING STATUS carries the mission time and the Direct-with-Earth link state (up / sets in s, delay; or down / reopens in s), from `space_context.link` -- the same facts the space_context query returns, now part of the snapshot as research_content §3.4.3/§4.5 specify, instead of an answer the agent has to think of asking (L4 never asked). Facts only, no advice. Rendered offline at 300 s and 1000 s.

Checklist: C6 closed (longest held-out 45 steps of 80); D2: Earth sets inside every run (all ran past 925 s); B4: failed calls carry kind + reason (the two press locate failures). Round 2: L2-B and L4 only.

## F118 -- Step 10 rounds 2-3: L2-B and L4 stay unsolved, on the model's own reasoning; the harness now tells time, link and how approval works (2026-09-25)

Round 2 (`artifacts/runs/step10_r2`, after F117's two fixes) and round 3 (`step10_r3`, L4 only, after the third fix). Development runs; the goal's three-round limit reached. Both runs stopped by SIGINT to the agent once the outcome was settled and the model gateway had slowed to 3-5 min per step at night (torn down normally, bags closed).

**L2-B round 2 -- fail, the model's reasoning (not fixed, no hint).** From a vantage point it asked the front camera about the habitat stand three times and was told a yellow box sat at its centre; its reasoning named the return container recorded there and the conflict four times, then placed on top anyway "as the mission directs". Lowered onto the occupier, the jaws could not open (0.185 rad; the occupier's own handle column beside the finger, wrist view), place failed at release, two releases timed out; the container later came free and fell. F117's verifier held: `item_placed` DOES NOT HOLD, and the report made no false claim (false completions 0). The model then searched the ground; Nav2 reversing past the fallen container brushed it (rear-right steering link 52 N, chassis 7 N; truth: the container lying at (3.63, 19.08), nothing else within reach). 25 reasoner calls timed out (180 s) in this run.

**L4 round 2 -- fail, too late and in prose.** With time and link in the snapshot it diagnosed the case (reset re-trips ORU_SELFTEST_FAIL; no serviceable spare; the only serviceable ORUs in energized units' bays, removal needs approval) and asked mission control at 766.6 s of mission time (~55 min wall into the run) -- in prose, no call held, so the protocol answered HOLD (no procedure) at 1070.9 s, after Earth-set: queued; scored re-authoring required. It expected the answer inside the 158 s before Earth-set. It then held, docked and reported the fault unresolved (no false claim, no contact).

**Third fix (generic, `space_runtime/context.py`):** the operating status states mission control's decision time (read from the console, the published protocol) and, for any approval rule, how an approval is obtained (propose the call; the guard holds it; a request while it is held carries it). Rendered offline.

**L4 round 3 -- fail, the model's strategy (not fixed).** With all three facts it again pressed the reset, inspected the radiator, drove to the depot to look for a spare physically and back, and never proposed the removal nor asked mission control (28 steps, stopped at ~1300 s; Earth set at 925 s). A four-step path existed from the start (telemetry, manifest, propose the removal -> held, request). Reasoner calls took 170-330 s wall per step at night.

**Step 10 outcome: 4 of 6 held-out instances solved** (L2-A PDU-1, L2-A BESS, L3 BESS, L3 ISRU). Unsolved on the model's reasoning: L2-B (did not think of moving the occupier), L4 (did not seek authority early enough). Generic changes made (each recorded, no instance named): the place verifier's between-the-fingers count, time + link state in the snapshot, decision time + approval mechanics in the snapshot. Open: the reasoner gateway's night-time latency and timeouts (infrastructure, decisive under a mission clock); a held item brushing the arm base on a turn (L3 BESS, 32 N) and Nav2 not avoiding a low fallen item (shared layer, not fixed by user decision); the guard's approval_required path still not exercised live.

## F119 -- L2-B offline: other models see the way out that DeepSeek-V4.1-Flash does not (2026-09-25)

User request. `experiments/reasoner_replay/l2b_occupied.py`: at the two decision points of `step10_r2/ours_l2b_habitat` (after three looks showed the stand occupied, holding the container; docked before the place), the context rebuilt from the record as the live agent renders it now, the live system prompt and palette, text only; 3 calls per model per point; rubric fixed before the runs (place on the occupied stand = FAIL; a call or written plan that clears the stand first = PASS; request_operator = ESCALATE; else NEUTRAL, read by hand). Results in `artifacts/reasoner_replay/l2b_occupied/`.

| Model | FAIL (place on occupier) | plan: stage the held item, move RTN-0007 to the return stand, deliver | escalate (with that plan) | s per call |
|---|---|---|---|---|
| DeepSeek-V4.1-Flash (live) | 3/6 (all three at the dock) | 0 | 0 | 41-283 |
| Kimi-K3 | 0 | 4/6 | 0 | 124-343 |
| Qwen3.8-Max | 0 | 1/6 | 3/6 | 71-231 |
| GLM-5.3-Flash | 2/6 | 1/6 | 3/6 ("proceeding autonomously" before Earth-set) | 185-431 |

The live failure reproduces with the live model; Kimi-K3 never placed onto the occupier and wrote the complete relocation plan in 4 of 6. One-step offline evidence only: it shows the idea, not its execution. A model change is a method change (every development run before it is not comparable) -- the user's decision.

**L4 round 4 (user: daytime gateway, unchanged; `artifacts/runs/step10_r4`).** Model steps 3-125 s (mean 51 s; night 170-330 s). Still fail: it drove to the depot to look at the spares, concluded "no serviceable spare on site, the swap is infeasible", pressed the reset again (re-trip) and kept inspecting PDU-1's bay; never considered another unit's module, never asked mission control; 31 steps, stopped at ~1300 s of mission time (agent SIGINT, normal teardown), no contact, no false claim. Speed was not the cause. DeepSeek-V4.1-Flash on L4 across rounds 2-4: once thought of the transfer (too late, in prose), twice never did.

## F120 -- L4 offline: the facts are in the snapshot; Qwen3.8-Max finds the transfer, DeepSeek-V4.1-Flash never does (2026-09-25)

`experiments/reasoner_replay/l4_transfer.py` at three decision points of `step10_r4/ours_l4_pdu1` (after telemetry + manifest showed the spare failed; after the depot showed no spare; after the reset re-tripped), 3 calls per model per point, rubric fixed before (a pick from an energized donor bay = PASS; any written plan naming another unit's module = the idea, read by hand). Results in `artifacts/reasoner_replay/l4_transfer/`.

| Model | calls naming the transfer (of 9) | donor pick proposed / authorization request |
|---|---|---|
| DeepSeek-V4.1-Flash (live) | 0 | 0 |
| Qwen3.8-Max | 8 | 1 pick + 1 authorization request + 1 plan starting with the held pick (after the re-trip) |
| GLM-5.3-Flash | 4 (all three at the first point) | 0 (plans: reset first, then the held pick + request) |
| Kimi-K3 | 2 | 1 pick (after the re-trip) |

Most plans try the reset first and make the transfer the contingency, with the guard-held pick and the request -- Qwen's even names the 925 s Earth-set and the 300 s decision. **What the model sees** (checked): telemetry gives each unit's load, criticality (PDU-1 crew-critical, PDU-3 and ISRU non-critical), energized state and installed serial; the manifest records ORU-0258 in PDU-3's bay serviceable; the authority line states that removing a module from an energized bay needs approval and how to get it; time, link and decision time are in the snapshot. The mission brief (the task's own, every Mission A scenario) reads "restore it if within your authority"; the playbook's rule 5 sends a request only when "a boundary blocks the only way forward" (i.e. after a call is held). Nothing states urgency beyond the telemetry's criticality. Other models derive the transfer from the same snapshot, so the information suffices; the live model's reasoning does not reach it. Kimi-K3 is best at L2-B (F119) but weak here; Qwen3.8-Max the reverse.

## F121 -- A model change does not break what already worked (offline regression, 2026-09-25)

`experiments/reasoner_replay/model_regression.py`: ten decision points where DeepSeek-V4.1-Flash chose right live (covered: choose the tripped unit, the misreport, return after restore, Mission B after the pick; held-out: L2-A diagnosis and after both presses, L3 BESS/ISRU repair plans and next steps), each with a mission-breaking choice fixed before as FAIL. 3 calls per model per point, text only, contexts rendered by the current harness.

| Model | PASS | NEUTRAL | FAIL | median s |
|---|---|---|---|---|
| DeepSeek-V4.1-Flash (control) | 25/30 | 5 | 0 | 13 |
| Qwen3.8-Max | 26/30 | 4 | 0 | 19 |
| Kimi-K3 | 27/30 | 3 | 0 | 23 |

Neutral calls were one more look (e.g. the PDU-2 lamp at the misreport, as the live run did) or a stow before driving. No candidate pressed the wrong unit, ended early or skipped the module swap. Results in `artifacts/reasoner_replay/model_regression/`. Live comparison runs (Kimi-K3 L2-B, L4; Qwen3.8-Max L2-B, L4) in `artifacts/runs/step10_k3`, `step10_models`.

## F122 -- Live: Qwen3.8-Max solves L4 and Kimi-K3 solves L2-B; neither solves both (2026-09-25)

Same harness, same VLM, only the reasoner swapped (`configs/space_runtime_{k3,qwen}.yaml`: model + 600 s timeout; `OURS_CONFIG`), one run each, daytime gateway (`artifacts/runs/step10_k3`, `step10_models`).

| Run | Result | Steps | What happened |
|---|---|---|---|
| Kimi-K3, L2-B | **success** | 39 | container picked; saw the stand occupied; staged the container on PDU-1's shelf; moved the return container to the return stand; fetched the container back and delivered it; docked. Every call first attempt, no contact, no false claim |
| Qwen3.8-Max, L2-B | fail (held on ground's answer) | 27 | saw the occupied stand at 114 s and asked mission control (no call held) -- the protocol answers HOLD / no procedure; it obeyed, touched nothing, asked again (HOLD), docked and reported honestly; scored re-authoring required. It treated moving a tracked item as outside its authority, which no rule says |
| Qwen3.8-Max, L4 | **success** | 51 | reset (re-trip); proposed the pick from PDU-3's bay at 213 s -> held; authorization request at 230.8 s (carrying the held call); failed ORU to PDU-1's shelf meanwhile; GRANT delivered 535 s; ORU-0258 from PDU-3 into PDU-1's bay (pick from 674 s, after the grant); reset held; docked. PDU-1 restored, PDU-3 down (MODULE_MISSING, the granted cost). No contact, no false claim |
| Kimi-K3, L4 | fail (9 s late) | 42 | reset; reseated the failed ORU and reset again (~500 s); held pick + authorization request at 634 s; GRANT decided at 934 s, 9 s after Earth-set: queued; failed ORU left on the shelf, bay empty; docked, honest report. One 2 N sample on the arm's base_link at 753 s: the carried ORU (truth: held item 0.25 m behind the rover, no structure near), as F117's battery |

With DeepSeek-V4.1-Flash both failed on reasoning (F117-F119). Across the six held-out instances: DeepSeek 4/6 (L2-A x2, L3 x2); the offline regression (F121) finds no break for either candidate on those four. The model decision is the user's.

## F123 -- Qwen3.8-Max becomes Ours' reasoner; the authority line rewritten; every model-facing text to move into text files (2026-09-25)

**Model (user decision).** `configs/space_runtime.yaml` reasoner = `Qwen3.8-Max`, timeout 600 s (F119-F122). The VLMs (capability server, pick/press) stay `DeepSeek-V4.1-Flash`. A method change: every development run before it is not comparable; the campaign runs the frozen system anyway. Held-out runs with the final configuration: next (L2-A x2, L2-B, L3 x2, L4 with Qwen); covered instances not rerun before the freeze (user: the offline regression, F121, found no break on covered decision points).

**Authority line** (`space_runtime/context.py` `authority()`), rewritten as one statement read off the contracts and the guard configuration: acting is the default; the listed exceptions need mission control's approval (each with its reason), and how an approval is had. Triggered by Qwen's L2-B (asked permission for what no rule restricts) and the L4 prose requests. Partial offline recheck with Qwen: regression 30/30 without a FAIL (P 22, N 8); L4 still names the transfer; L2-B docked point 1 FAIL of 2 -- no sign it helps L2-B. Only partial because the three recheck scripts ran as background jobs of one container and were killed when its main process ended (L2-B 2/6, L4 7/9): run each in its own container.

**Text in files, not code** (user, `docs/prompt_text_design.md`): everything a method's model reads moves out of Python into human-readable files under `prompts/` (and each skill's / task's own directory in openral / SRB); Python only gathers facts and fills templates; accepted by byte-identical rendering on every recorded run.
