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
