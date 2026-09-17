# Composable manipulation capabilities: design and validation plan

Status: plan v3 (2026-09-17, user decisions). Supersedes v1 (CAD-model 6-DoF tracking: needs the part's 3-D model, no
generality) and v2 (one grasp skill with internal outcomes). Replaces the VLM-point + open-loop pick that failed
repeatedly in Mission B (runs ob1–ob6, `docs/research_findings.md` F55). No code yet.

## 1. Principles (user decisions)

1. **No object models.** Nothing about an object is known in advance except what a mission record says in words (and
   perhaps a rough size). Grasp candidates come from the current RGB-D view.
2. **Semantics from the VLM, geometry from vision.** The VLM never outputs coordinates; it chooses among
   geometry-derived candidates drawn on the image, for the mission's intent ("by its carry handle").
3. **No target localisation in world or rover coordinates.** Placement is unknown and absolute poses are not trusted.
   The target lives in the eye-in-hand image (pixels + local depth) and is servoed there. The only geometry used is the
   robot's own (fixed camera-to-tool mount, the arm's Cartesian velocity interface).
4. **Closed loop at camera rate; checks from images and encoders.**
5. **Small tools, composed by the agent.** Each capability does one job and reports what it measured, like
   `navigate_to_pose`; none contains a recovery path. The agent composes them; when a step fails it re-composes with a
   different tool or parameters. Ours supplies authoritative facts, the attempt record and budgets; physical
   verification and hard constraints are the shared substrate (§2).

## 2. Architecture decision (user, 2026-09-17)

Physical-effect capabilities are implemented as OpenRAL rSkills; stateful perception control and read-only
perception/state queries are provided by perception/world-state services. The shared boundary remains thin and
method-neutral. Shared physical verification, low-level safety, externally imposed hard constraints and observable
evidence remain identical across methods (`research_content` §5.2–5.3); Ours' contribution is the authoritative mission
state, dynamic context reconstruction and agent-owned mission strategy above that common substrate.

```text
Ours                                   PLEXIL / EUROPA→PLEXIL
agent                                  plan / planner
facts + context + mission reasoning    baseline execution semantics
      |                                        |
------------- each method's mission-level operating model -------------
                           |
======== shared capability / evidence boundary (thin, method-neutral) ========
  contracts · argument checks · availability (incl. requires_remote_service) · external hard constraints
                           |
   physical effect      → OpenRAL rSkill (runner + safety kernel)
   perception control   → perception module (start/stop tracking, set current target)
   read-only query      → perception / world-state service
                           |
        shared verifier · FDIR signals · low-level safety
                           |
               Nav2 / MoveIt / controllers / HAL
```

Rules:

- **Three interface classes**, used identically by all methods: physical effect, perception control, read-only query.
- **Fixed infrastructure vs movable objects.** `*_to_named_location` capabilities (navigate, dock, arm pre-position)
  use surveyed fixed-infrastructure places loaded into OpenRAL's world state (named places); rSkills do not parse the
  lunar-base files. Movable objects (ORU, crate, cover, handles) never go through fixed geometry: only current
  perception → tracking → visual servo.
- **rSkill locality rule.** An rSkill may adapt execution locally while preserving the selected target and task
  intent; any change of target, task strategy, information source or recovery mode returns control to the agent
  (local re-acquisition or backing off to the pre-grasp and re-centring: yes; another candidate, another viewpoint,
  moving the base, asking the operator: no).
- **No decision-workflow (playbook) rSkills** in the method: search → alternative → ask-human sequences are mission
  strategy.
- **Availability metadata, not rules.** A cloud-dependent service carries `requires_remote_service`; when unavailable,
  every method sees the capability unavailable; what to do is each method's own mission logic.
- **Migration without a big refactor.** New capabilities follow these rules from the start; `approach_target`, the VLM
  perception calls and the feature-pose lowering move out of `capability_server` when the new work touches them;
  Mission A `covered` is the regression after each move.
- **Consequence to schedule:** effect verification now lives in `space_runtime/verification.py` (Ours only) and the
  guard's hard constraints (e.g. FDIR estop) are enforced there too; per §5.2–5.3 both belong to the shared substrate
  (PLEXIL reads them as Lookups). Ours keeps authoritative facts, context and agent-facing authority reasoning.

## 3. Tools (exposed through the shared boundary)

Perception (perception control: `lock_target`; the rest read-only queries):

| Capability → implementation | Does | Returns |
|---|---|---|
| `observe(camera, question)` | VLM question on the current frame | answer + frame |
| `grasp_candidates(camera, generator, max_n, exclude)` | class-agnostic grasp candidates on the current view (§4) | numbered annotated image; per candidate: pixel, image axis angle, depth, approach direction and jaw width in the camera frame, score |
| `choose_candidate(candidates, intent, exclude)` | VLM set-of-mark choice | candidate id, reason, runner-up |
| `lock_target(candidates, id)` | starts the on-board track (KLT points + depth patch) | track id, quality |
| `target_status(track)` | live track | pixel error to the jaw gap, axis error, depth, quality |
| `hold_check(track)` | short image test while the tool moves: target static, background moving | held yes/no + frames |

Motion:

| Capability → rSkill | Does | Stops and reports |
|---|---|---|
| `servo_to_target(track, standoff_m, max_speed)` | IBVS to the stand-off with the target in the jaw gap | converged / track_lost / stalled + last errors |
| `approach_guarded(distance_m, max_speed)` | straight move along the tool axis | reached / contact / depth limit |
| `look_at` (OpenRAL `rskill-moveit-look-at`) / relative camera move (rSkills) | change the viewpoint | reached / blocked |
| `move_tool`, `grasp`, `release`, `stow`, navigation, docking (exist) | as now | as now |

A typical pick the agent may compose: observe → grasp_candidates → choose_candidate → lock_target → servo_to_target →
approach_guarded → grasp → hold_check (+ small lift). The order is the agent's, not encoded anywhere.

## 4. Inside the tools

- **Candidate generators** (compare offline, keep the better or both; also a paper ablation):
  - classical (OpenCV + depth): depth-discontinuity edges, thin elongated structures by line fitting (handles, bars),
    antipodal pairs across depth edges within the jaw opening, support-plane removal;
  - learned, class-agnostic from a single-view point cloud: Contact-GraspNet (PyTorch port), GraspNet-1Billion
    baseline; AnyGrasp only if the open ones fail (per-machine licence).
- **IBVS:** `v_cam = -λ L⁺ (s - s*)` on the grasp centre pixel, image axis angle and depth; `s*` = centre in the jaw
  gap, axis on the jaw axis, depth = stand-off; `v_cam` → tool frame by the fixed mount → existing Cartesian twist path.
- **Jaw gap in the image:** measured once from the robot's own wrist images.
- **Not used:** Isaac ROS FoundationPose (Isaac ROS 4.6, 2026-08): needs the object mesh, current packages target ROS 2
  Jazzy (our stack: Humble / Ubuntu 22.04), 0.5–6 fps estimation.

Related work (not claimed): VLM visual prompting over grasp candidates (OWG, ThinkGrasp), task-oriented grasping
(GraspGPT family), iterative visual prompting (PIVOT); space heritage of pre-designated-target visual servoing
(ETS-VII, Orbital Express ORU transfer, Dextre).

## 5. Ours above the shared substrate (contribution, `space_runtime/`)

- **Object facts** (`on:<place> | in_gripper | unknown`), changed only by verified evidence.
- **Verified facts from the shared verifier** (held = jaw range + `hold_check`; placed = jaws open + item at rest on
  the support) folded into authoritative mission state. Never a skill's own success flag.
- **Reconciliation with provenance:** manifest record vs VLM identity vs on-board measurement (extent of the point-cloud
  segment at the chosen candidate) → anomaly naming the sources (`spare_swapped`, `destination_occupied`).
- **Hard constraints (shared substrate, same for all methods):** no base motion while holding or with the arm outside
  the hull; stop on a lost track during a contact move; contact blocked after an uncertain hold until re-observed.
- **Attempt record in the context** per target: tools, parameters, candidates, viewpoints, base poses, outcomes; failed
  candidates handed back as `exclude`. Attempt/time budgets → operator request with the evidence.
- **Provider failover** (VLM, reasoner) as recorded facts. **Latency layering:** cloud reasoning never inside a 15 Hz loop.
- Measured: recovered-failure rate, attempts per success, operator requests.

## 6. Validation gates

| Gate | Test | Pass |
|---|---|---|
| G0 data | wrist RGB-D at ~30 arm viewpoints of the ORU and crate on the depot stand (truth only for scoring) | saved |
| G1 candidates (offline) | a correct handle grasp among the top-K, classical vs learned | ≥ 90 % of views |
| G2 selection (offline) | VLM picks a correct candidate for "by its carry handle"; swapped item flagged | ≥ 90 %; flagged |
| G3 servo (live) | `servo_to_target` converges from depot views | ≥ 9/10 |
| G4 pick, unknown placement (live, agent composing) | item moved ±10 cm / rotated ±30° on the stand, rover dock perturbed | ≥ 8/10 held and lifted |
| G5 generality (live) | crate and one new item, no code change | held and lifted |
| G6 ablation | VLM point + open loop / classical / learned candidates | reported |
| G7 missions | Mission B covered with the agent, then `destination_occupied`, `spare_swapped` | verifier success |

## 7. Work order

1. G0 recorder (`experiments/perception/record_rgbd.py`) on a held graph (snapshot workflow, `AGENT/handoff.md`).
2. G1 classical generator first (no build risk), then Contact-GraspNet / GraspNet baseline.
3. G2 candidate rendering + set-of-mark prompt.
4. §3 tools per §2 (effects as rSkills in the OpenRAL fork, perception control/queries as perception services);
   boundary contracts as a thin mapping; move `approach_target` / VLM perception / feature lowering out when touched.
5. Harness pieces of §5.
6. G3–G7.

Risks: learned generators are trained on tabletop objects (G1 decides); their CUDA ops vs host CUDA 13 / torch cu128
(separate env if needed); fingers occlude the handle close in (servo to stand-off, then guarded straight close-in);
arm sag under the 1 kg item (F51: 4.5 cm) is within the servo while tracking.
