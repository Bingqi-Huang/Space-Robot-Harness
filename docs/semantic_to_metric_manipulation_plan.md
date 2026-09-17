# Semantic grasp selection with image-based closed-loop execution: design and validation plan

Status: plan v2 (2026-09-17, user decision). v1 (CAD-model 6-DoF tracking) is dropped: it needs the part's 3-D model,
which removes generality. Replaces the VLM-point + open-loop pick that failed repeatedly in Mission B (runs ob1–ob6).
No code yet.

## 1. Principles (user decisions)

1. **No object models.** Nothing about the object is known in advance except what a mission record says in words
   (and, where available, rough size). Candidates come from the current RGB-D view only.
2. **Semantics from the VLM, geometry from vision.** The VLM never outputs coordinates; it chooses among
   geometry-derived grasp candidates drawn on the image, or ranks them for the mission's intent ("by its carry handle").
3. **No target localisation in world or rover coordinates.** Object placement is unknown and absolute poses are not
   trusted. The target lives in the eye-in-hand camera image (pixels + local depth) and is servoed there. The only
   geometry used is the robot's own: the fixed camera-to-tool mount and the arm's Cartesian velocity interface.
4. **Closed loop at camera rate; verification from images and encoders.** Every contact step is guarded and checked.
5. **Manipulation is a set of tools, not one skill.** Like `navigate_to_pose`, each tool does one job and reports what
   it measured; none contains a recovery path. The agent in the harness composes them and, when a step fails,
   chooses a different tool or different parameters (another candidate, generator, viewpoint, stand-off, speed, base
   pose). The harness supplies the facts, the attempt record, independent verification, invariants and budgets (§5a).

## 2. A typical composition (chosen by the agent, not encoded anywhere)

| Stage | What | Where / rate |
|---|---|---|
| Reasoner | goal in words: "pick the spare ORU at the depot by its carry handle" | cloud, per step |
| Candidates | class-agnostic grasp candidates from the wrist RGB-D view (learned and/or classical, §3) | robot, per view |
| Semantic selection | candidates drawn and numbered on the image; VLM picks / ranks for the intent | cloud, per view |
| Track | the selected grasp's image features tracked frame to frame (KLT points + depth patch) | robot, 15 Hz |
| Servo | IBVS: image error → camera twist → tool twist → arm Cartesian velocity | robot, 15 Hz |
| Coarse-to-fine | re-generate candidates at closer range; re-select only by feature match to the track (VLM again only if lost) | robot |
| Guarded close-in | move along the grasp approach while keeping the features centred; stop on depth or contact | robot |
| Checks | pre-close (grasp point between the fingers in the image, depth consistent); post-lift (object moves with the camera) | robot |
| Harness | object facts, independent verification, reconciliation, invariants, evidence (§5) | robot, per event |

## 3. Candidate generators (compare offline, keep the better or both)

- **Learned, class-agnostic 6-DoF grasps from a single-view point cloud:** Contact-GraspNet (PyTorch port) and
  GraspNet-1Billion baseline (open code, PyTorch; CUDA ops to build). AnyGrasp (strongest reported) needs a per-machine
  licence — consider only if the open ones fail. Output reprojected to the image as gripper glyphs with the approach
  direction.
- **Classical (OpenCV + depth, no learning):** depth-discontinuity edges; elongated thin structures by line fitting
  (handles, bars, rails); antipodal pairs across depth edges within the jaw opening; planar support removal. Output: the
  same glyph format.
- The two generators are also a paper ablation (learned vs classical candidates under the same selection and servo).

Related work to position against (not claimed): open-world grasping with VLM visual prompting over candidates (e.g.
OWG, ThinkGrasp), task-oriented grasping (GraspGPT family), iterative visual prompting (PIVOT). The contribution is the
space-mission layer below.

## 4. Servo and checks (no absolute coordinates)

- **Features:** the selected grasp's centre pixel, its image axis angle, and depth at the centre; a KLT point set in the
  surrounding patch keeps the track through scale change and partial occlusion by the fingers.
- **Law:** classic point-feature IBVS with the depth estimate: `v_cam = -λ L⁺ (s - s*)`, `s*` = grasp centre at the
  image point that lies between the fingers, axis aligned with the jaw axis, depth = pre-grasp distance. `v_cam` is
  mapped to the tool frame by the fixed mount transform and sent through the existing Cartesian twist path.
- **Finger region:** where the finger gap appears in the wrist image, measured once from the robot's own images (no
  model of the object, no arm kinematics chain).
- **Pre-close check:** grasp centre inside the finger-gap region, depth within the jaw's reach, feature track healthy.
- **Post-close / lift:** jaw encoder stops in a plausible range for a clamp (not fully closed); on a short lift the
  tracked features stay put in the image while the scene behind moves → object held.
- Each check is its own query (`target_status`, `hold_check`) so the agent and the harness verifiers can use it.

## 5. Harness (contribution, `space_runtime/`)

- **Authoritative object facts:** item location `on:<place> | in_gripper | unknown`, changed only by verified evidence.
- **Independent verifiers:** held = jaw range + post-lift image check (not the skill's flag); placed = jaws open, item
  at rest in the view on the support.
- **Reconciliation with provenance:** manifest record (what should be where, rough size) vs VLM identity judgement vs
  on-board measurement (object extent from the point cloud segment around the grasp); disagreement → anomaly naming the
  sources (`spare_swapped`, `destination_occupied`).
- **Invariants:** no base motion while holding or with the arm outside the hull; track lost during a contact effect →
  FDIR fact blocking contact until re-observed.
- **Latency layering:** cloud reasoning (tens of seconds) never sits inside the 15 Hz loop.
- **Evidence:** every outcome links its frames and tracks.

## 5a. Tools and composition

Perception queries (no motion):

| Tool | Does | Returns |
|---|---|---|
| `observe(camera, question)` (exists) | VLM question on the current frame | answer + frame |
| `grasp_candidates(camera, generator, max_n, exclude)` | class-agnostic candidates on the current view (§3) | annotated numbered image; per candidate: pixel, image axis angle, depth, approach direction and jaw width in the camera frame, score |
| `choose_candidate(candidates_id, intent, exclude)` | VLM set-of-mark choice for the intent | candidate id, reason, runner-up |
| `lock_target(candidates_id, candidate)` | starts the on-board KLT + depth track of that candidate | track id, quality |
| `target_status(track)` | reads the live track | pixel error to the jaw gap, axis error, depth, quality |
| `hold_check(track)` | short image test while the tool moves: target static in the image, background moving | held yes/no + frames |

Motion effects:

| Tool | Does | Stops and reports |
|---|---|---|
| `servo_to_target(track, standoff_m, max_speed)` | IBVS to the stand-off with the target in the jaw gap | converged / track_lost / stalled (with the last errors) |
| `approach_guarded(distance_m, max_speed)` | straight move along the tool axis | reached / contact / depth limit |
| `move_camera(...)` / OpenRAL `LookAtRskill` | change the viewpoint relative to the current view | reached / blocked |
| `move_tool`, `grasp`, `release`, `stow`, base navigation (exist) | as now | as now |

The harness's part (contribution): object facts updated only by verified evidence; verifiers built on these queries
(held = jaw range + `hold_check`, not a skill flag); automatic invariants (stop on a lost track during a contact move,
no base motion while holding or with the arm out, contact blocked after an uncertain hold until re-observed); an
attempt record in the context per target (tools, parameters, candidates, viewpoints, outcomes, failed candidates
passed as `exclude`); attempt/time budgets with an operator request on exhaustion; provider failover for VLM and
reasoner. The agent reads this and composes the next attempt differently. No recovery graph in tools or harness.
Measured as recovered-failure rate, attempts per success, operator requests.

## 6. Capability boundary

The §5a tools as contracts (effects and queries), exactly like navigation today. Same contracts for Ours, PLEXIL and
EUROPA→PLEXIL; PLEXIL composes them in authored plans and branches, Ours composes them online.

## 7. Validation gates

| Gate | Test | Pass |
|---|---|---|
| G0 data | wrist RGB-D at ~30 arm viewpoints of the ORU and crate on the depot stand (truth only for scoring) | saved |
| G1 candidates (offline) | a correct handle grasp among the top-K, learned vs classical | ≥ 90 % of views |
| G2 selection (offline) | VLM picks a correct candidate for "by its carry handle"; swapped item flagged | ≥ 90 %; swap flagged |
| G3 servo (live) | IBVS converges to the pre-grasp from the depot views | ≥ 9/10 |
| G4 grasp, unknown placement (live) | item moved ±10 cm and rotated ±30° on the stand, rover dock perturbed | ≥ 8/10 held and lifted |
| G5 generality (live) | crate and one new item with no code change | held and lifted |
| G6 ablation | VLM point + open loop / classical candidates / learned candidates | reported |
| G7 missions | Mission B covered with the agent, then `destination_occupied`, `spare_swapped` | verifier success |

## 8. Risks

- Isaac ROS FoundationPose (Isaac ROS 4.6, 2026-08) is not a drop-in: it requires the object mesh (against principle
  1), current packages target ROS 2 Jazzy (our stack is Humble, Ubuntu 22.04), and estimation runs at 0.5–6 fps. Kept
  only as a possible comparator (e.g. with a mesh reconstructed on the fly from wrist RGB-D), not in the pipeline.
- Learned generators are trained on tabletop objects; a handle on a large box should be graspable, the crate's lid
  handle likewise — G1 decides. Build of their CUDA ops against host CUDA 13 / torch cu128 → separate env if needed.
- Fingers occlude the handle close in → KLT patch + stop the servo at pre-grasp, then a guarded straight close-in.
- Arm sag under load (F51: 4.5 cm) is inside the servo's job while tracking; the lift check is image-relative.

## 9. Work order

1. G0 recorder (`experiments/perception/record_rgbd.py`) on the held graph.
2. G1: classical generator (OpenCV/depth) first (no build risk), then Contact-GraspNet / GraspNet baseline.
3. G2: candidate rendering + set-of-mark selection prompt.
4. Tools of §5a (candidates, choose, lock/track, servo, guarded approach, checks) as rSkills + boundary contracts.
5. Harness: object facts, verifiers, reconciliation, invariants.
6. G3–G7 with the snapshot workflow.
