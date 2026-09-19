# Manipulation capabilities: design and validation plan

**2026-09-19 execution notice:** The user approved the narrowed
[r3 success-reference plan](manipulation_contracts_proposal.md): reproduce compatible successful grasp/carry
conditions, then complete Mission B; diagnose the first divergence if reproduction fails.
Full C1/C3 construction is deferred. This historical v4 text does not authorize restoring hidden scan/retry loops.

Status: plan v4 (2026-09-17, user decision). Supersedes v3, which kept the right internals (no object models, VLM
chooses among image grasp candidates, on-board tracking + visual servo, image/encoder checks, harness facts and
verification) but put the *composition* at the wrong level: it made the agent call seven tools in a fixed order to
pick one object. v4 moves that work procedure into one skill. v1 (CAD-model tracking) and v2 (a grasp skill without a
stated locality rule) remain superseded. No v4 code exists yet; the analysis behind it is `docs/research_findings.md`
F55.

## 0. The operating picture

The system is "Claude Code for a lunar robot". The model owns the mission the way a coding agent owns a bug fix; the
harness runs tools, keeps the record, checks results and holds the boundaries; OpenRAL is the tool runner and skill
format we borrowed so we did not have to write one.

| Claude Code | Lunar mission agent |
|---|---|
| "fix this bug" | "restore the PDU" / "deliver the spare to PDU-1" |
| the model decides what to read, what to edit, whether to test, what to try after a failure | the model decides what to observe, where to go, what to pick, what to try after a failure |
| tools: `Read`, `Edit`, `Bash` -- one meaningful operation each, never keystrokes | tools: `observe`, `navigate_to_pose`, `pick`, `place`, `press` -- one physical operation each, never servo stages |
| harness: tool registry, approvals, transcript, context, test output returned verbatim, traces | harness: capability registry, authority guard, authoritative facts, context rebuilt every step, independent effect verification, traces |
| a post-edit hook runs lint automatically | after `pick`, the harness checks "is it really in the gripper" automatically |
| the harness never decides how to fix the bug | the harness never decides how to do the mission |

## 1. Principles

1. **No object models.** Nothing about an object is known in advance except what a mission record says in words (and
   perhaps a rough size). Grasp geometry comes from the current wrist RGB-D view.
2. **Semantics from the VLM, geometry from vision.** The VLM never outputs coordinates; it chooses among
   geometry-derived candidates drawn on the image, for the stated intent ("by its carry handle").
3. **No target localisation in world or rover coordinates for movable objects.** The target lives in the eye-in-hand
   image (pixels + local depth) and is servoed there; the only geometry used is the robot's own.
4. **Closed loop at camera rate; checks from images and encoders.**
5. **Tools at the granularity of one physical operation.** A model-facing tool is something an operator would name as
   one action: navigate, dock, pick, place, press, observe, look at, stow. Its internal stages (candidates, selection,
   tracking, servo, close-in, jaw, hold check) are the skill's procedure, not tools. The model chooses *which*
   operation on *what*, and what to do when it fails; it never runs a procedure step by step and never fills in
   mechanical parameters. Independent verification is the harness's job, done automatically.

## 2. Architecture

Physical-effect capabilities are OpenRAL rSkills; stateful perception control and read-only queries are perception /
world-state services; the shared capability contract stays thin and method-neutral. Method boundary
(`research_content` §3.2, §5.2–5.3, §5.7): the baselines share the problem and the robot, not Ours' mechanisms.

```text
Ours                                        PLEXIL / EUROPA→PLEXIL
LLM/VLM agent                               classical mission model
        |                                             |
==================== METHOD-SPECIFIC ====================
Ours harness:                               their own plan / domain,
 authoritative facts                        execution and recovery semantics,
 dynamic context reconstruction             mission/authority constraints
 thin authority / invariant guard           encoded in their artifacts
 independent effect verification (automatic)
 evidence-linked trace / reconciliation
        |                                             |
================= SHARED ROBOT SUBSTRATE =================
typed capability contract (names, mission-level arguments, availability incl. requires_remote_service)
  physical operation   → OpenRAL rSkill (pick, place, press, navigate, dock, stow, ...)
  perception control   → perception module (used inside skills; not a model-facing tool)
  read-only query      → perception / world-state service (observe, arm_state, base_pose, manifest, ...)
raw robot-observable results and signals (the same evidence for every method)
Nav2 / MoveIt / controllers · low-level hardware safety (limits, e-stop, collision-critical kernel,
                              posture and speed limits while driving or holding) · robot / environment
================= EXTERNAL EVALUATOR =================
same success criteria for all methods; counts constraint violations and false success declarations
```

Rules:

- **Granularity rule (new).** The model-facing palette contains operations, not stages. The stage tools of v3
  (`grasp_candidates`, `choose_candidate`, `lock_target`, `target_status`, `servo_to_target`, `approach_guarded`,
  `hold_check`) exist as functions and perception services inside the skills; they are not rendered as tools and not
  exposed to the baselines. The same holds for Mission A's contact: `approach_target` + `move_tool` + `grasp` fold
  into one `press` skill when that code is next touched.
- **Skill locality rule (revised).** Inside one call a skill may retry on the *same target*: re-lock a lost track,
  back off to the pre-grasp pose and re-centre, try the next grasp candidate of the same target, re-run the hold
  check. It may not change the target, move the base, need a viewpoint that requires base motion, choose a different
  operation, or ask the operator. On any of those it stops and returns the stage it reached with its evidence.
  Recovery across those lines is the model's.
- **Mission-level arguments only.** A contract exposes what the mission decides (which target, which part, where to
  put it); stand-off distances, speeds, tolerances, retry counts and time budgets are defaults inside the skill,
  recorded in its result. No coordinates for movable objects.
- **Automatic verification.** After `pick` the harness establishes `held` (jaw range + image hold check + short
  lift); after `place`, `placed` (jaws open, item at rest on the support, tool clear). These use the shared query
  services; the skill's own success flag is never the evidence.
- **Constraints split.** Hardware-protecting limits -- joint and speed limits, the arm outside the hull while
  driving, base speed and acceleration while holding a payload -- live in the shared low-level safety (kernel
  envelope, Nav2 parameters), identical for every method. Mission and authority constraints (operator approval for a
  class of operation, contact blocked after an uncertain hold until re-observed) are method-specific: Ours' guard,
  the baselines' plans; the evaluator counts violations for all. The v3 rule "no base motion while holding" is
  withdrawn: Mission B carries the spare under Nav2 (F53 removed the same rule once before).
- **Fixed infrastructure vs movable objects.** `*_to_named_location` capabilities (navigate, dock, arm
  pre-position) use surveyed fixed-infrastructure places loaded into OpenRAL's world state; movable objects (ORU,
  crate, cover, handles) only through current perception → tracking → visual servo inside the skill.
- **No decision-workflow (playbook) rSkills.** Search → alternative → ask-human sequences are mission strategy.
- **Availability metadata, not rules.** A cloud-dependent skill carries `requires_remote_service`; when unavailable
  every method sees it unavailable; what to do is each method's own mission logic.
- **Migration without a big refactor.** New skills follow these rules from the start; `approach_target`, the VLM
  perception calls and the feature-pose lowering leave `capability_server` when the new work touches them; Mission A
  `covered` is the regression after each move.
- **Attribution by Ours-internal ablations**, not by giving components to the baselines.

## 3. Model-facing tools

New or changed (through the shared boundary; PLEXIL sees each as one Command, EUROPA as one activity):

| Tool | Arguments (mission-level) | Returns |
|---|---|---|
| `pick(target, part)` | what to pick, described in words; which part to hold (e.g. "the carry handle") | `held` / failed at stage `find | select | approach | grasp | hold` + evidence: annotated candidate image, chosen candidate and VLM reason, track quality, final servo errors, jaw angle, hold-check frames, candidates tried, time used |
| `place(support)` | where to set the held item down, described in words (a surveyed place name or "the empty slot on the PDU-1 shelf") | `placed` / failed at stage + evidence: support view, contact/settle result, jaw, tool clearance |
| `press(target)` (folds Mission A's contact; when touched) | what to press, described in words | `pressed` / failed at stage + evidence: target view, contact depth, retreat |
| `observe(camera, question)` (exists) | as now | answer + frame |
| `look_at(target)` (OpenRAL `rskill-moveit-look-at`, retagged) | bring the wrist camera to view a described or named target | reached / blocked + frame |

Kept as they are: `navigate_to_pose`, `navigate_to_feature`, `dock_to_pose`, `dock_at_feature`, `arm_ready`, `stow`,
`release` (opens the jaws without placement semantics), the read-only queries. `approach_target`, `move_tool`,
`plan_ee_*`, `move_ee_*`, `move_joints`, `grasp` stay in the palette until `press` lands, then leave it (they remain
skills for engineering use and for Experiment II authoring, not model tools).

A Mission B run the model may compose: navigate → dock → observe → pick → navigate → dock → observe → place → stow →
return. The order is the model's; a failed `pick` comes back with its stage and the model decides between re-observe,
another part, another viewpoint, another base pose, or the operator.

## 4. Inside `pick` (the procedure, from v3)

Stages, each with a measured end condition and its own evidence; parameters are skill defaults:

1. **find** -- class-agnostic grasp candidates on the current wrist RGB-D view: classical first (depth-discontinuity
   edges, thin elongated structures by line fitting, antipodal pairs across depth edges within the jaw opening,
   support-plane removal); a learned single-view generator (Contact-GraspNet PyTorch port, GraspNet-1Billion
   baseline) only if the classical one fails G1. Output: numbered annotated image; per candidate pixel, image axis
   angle, depth, approach direction, jaw width, score.
2. **select** -- VLM set-of-mark choice for `target` + `part`; returns id, reason, runner-up, and a flag when the view
   does not contain the described item (feeds the harness's reconciliation, §5).
3. **approach** -- lock the candidate (KLT points + depth patch), IBVS `v_cam = -λ L⁺ (s - s*)` on centre pixel,
   axis angle and depth to a stand-off with the target in the jaw gap (jaw gap measured once from the robot's own
   wrist images), then a guarded straight close-in along the tool axis (stop on contact or depth limit). Camera
   twist → tool frame by the fixed mount → the existing Cartesian twist path through the kernel.
4. **grasp** -- close the jaws; jaw angle within the holding band.
5. **hold** -- short image test while the tool moves (target static in the image, background moving) plus a small
   lift; jaw still in band.

Local retries (locality rule): track lost → re-acquire from the last patch, else back to pre-grasp and re-run
approach; hold failed → release, back to pre-grasp, next candidate of the same target; budgets per call (candidates
tried, time) are defaults, recorded. Anything else returns to the model with the stage.

`place` mirrors it: view the support, choose the put-down point (VLM among free-space candidates), servo above, lower
on contact, open, retreat, settle check. `press`: locate the described target in the wrist view, servo to a stand-off,
guarded close-in past the face by a default depth, retreat.

Not used: Isaac ROS FoundationPose (needs the object mesh, targets ROS 2 Jazzy). Related work (not claimed): VLM
visual prompting over grasp candidates (OWG, ThinkGrasp), task-oriented grasping (GraspGPT family), iterative visual
prompting (PIVOT); space heritage of pre-designated-target visual servoing (ETS-VII, Orbital Express, Dextre).

## 5. Ours' harness for manipulation (`space_runtime/`)

- **Object facts** (`on:<place> | in_gripper | unknown`), changed only by verified evidence.
- **Automatic effect verification** after `pick` / `place` / `press` on the shared query services (jaw, hold check,
  support view, arm kinematics) -- never a skill's own success flag.
- **Reconciliation with provenance:** manifest record vs VLM identity vs on-board measurement (extent of the
  point-cloud segment at the chosen candidate) → an anomaly naming the sources (`spare_swapped`,
  `destination_occupied`). The harness names the disagreement; the model decides what it means for the mission.
- **Guard (mission/authority constraints only):** approval classes; contact blocked after an uncertain hold until
  re-observed. No posture or payload rules (those are shared low-level safety).
- **Attempt record in the context**, per target: operations called, stage reached, candidates tried, viewpoints, base
  poses, outcomes. The model reads it and decides; the harness does not pre-fill exclusions or choose retries.
- **Provider failover** (VLM, reasoner) as recorded facts. **Latency layering:** cloud reasoning never inside the
  15 Hz loop; the VLM is called once per `select`, not per frame.
- Measured: recovered-failure rate, attempts per success, operator requests, reasoner steps per mission.

## 6. Baselines

`pick`, `place`, `press` are one Command / one activity each, with the same arguments and the same raw result. PLEXIL's
Mission B plan sequences them with its own recovery branches; EUROPA's domain declares them as activities with
pre/post-states. Neither sees the stage tools.

## 7. Validation gates

| Gate | Test | Target |
|---|---|---|
| G0 data | wrist RGB-D at ~30 arm viewpoints of the ORU and crate on the depot stand (truth only for scoring) | saved |
| G1 candidates (offline) | a correct handle grasp among the top-K, classical (learned only if this fails) | most views |
| G2 selection (offline) | VLM picks a correct candidate for "by its carry handle"; wrong item flagged | most views; flagged |
| G3 pick (live, one call) | `pick("the spare ORU", "its carry handle")` with the item moved ±10 cm / rotated ±30° and the dock perturbed | held and lifted in most trials; every failure returns a stage |
| G4 Mission B covered (agent) | snapshot workflow; the agent composes navigate / dock / observe / pick / place | verifier success |
| G5 held-out | `destination_occupied`, `spare_swapped`, then `cover_obstruction`, `status_mismatch`, `route_block` | verifier success; failures → mission-generic changes only |

Numbers are development targets, not thresholds (execution_plan §0.11). The v3 generality gate and the generator
ablation are dropped from the plan; they may return as supplementary material if time allows.

## 8. Work order

1. G0 recorder (`experiments/perception/record_rgbd.py`) on a held graph (snapshot workflow, `AGENT/handoff.md`).
2. G1 classical generator; G2 candidate rendering + set-of-mark prompt (both offline on the G0 data).
3. `pick` as an OpenRAL procedural rSkill in the fork (stages as internal functions; tracking as a perception
   service), one contract line in the boundary; `place` the same way. `press` when Mission A's contact code is next
   touched.
4. Harness pieces of §5 (object facts, automatic verification, reconciliation, attempt record).
5. G3, G4, G5.

Risks: learned generators are trained on tabletop objects (G1 decides whether they are needed); their CUDA ops vs
host CUDA 13 / torch cu128 (separate env if needed); fingers occlude the handle close in (servo to stand-off, then
guarded straight close-in); arm sag under the 1 kg item (F51: 4.5 cm) is within the servo while tracking; the EG2
cannot pinch the 1 kg spare, so the handle stays a bail (F46).
