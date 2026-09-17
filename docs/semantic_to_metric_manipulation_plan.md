# Manipulation as composable OpenRAL rSkills: design and validation plan

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
   different tool or parameters. The harness supplies facts, the attempt record, independent verification,
   invariants and budgets.

## 2. Layering (where each thing lives)

| Layer | Lives in | Role |
|---|---|---|
| Robot skills | **OpenRAL rSkills** (the fork: `openral/rskills/<name>/rskill.yaml` + entrypoints in `openral/python/rskill`), run by OpenRAL's runner under its safety kernel | navigation, arm motion, gripper (exist); perception and servo tools of §3 (new) |
| Common capability boundary | `openral_ext/capability_server` (`contracts.yaml`) | a **thin** 1:1 mapping of capability names/arguments to rSkills + robot-observable evidence, identical for Ours, PLEXIL and EUROPA→PLEXIL |
| Harness (contribution) | `space_runtime/` | the agent loop: context, facts, verification, guard/invariants, attempt record, budgets, traces |

**Correction to the current code (drift):** the boundary today also *implements* skills — `approach_target`
(camera-in-the-loop controller), `locate_in_view` / `observe` (VLM calls), feature-geometry lowering. Those belong in
rSkills. OpenRAL already has the right kinds: `procedural` (closed-loop controllers, e.g.
`rskill-procedural-move_ee_to_pose`), detector/locator (`omdet-turbo-locator`, `find-object`), MoveIt
(`rskill-moveit-look-at`). Part of this work is moving that logic down and leaving the boundary a mapping.

## 3. Tools (new rSkills, exposed 1:1 as capabilities)

Perception (read-only):

| Capability → rSkill | Does | Returns |
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
| `look_at` (OpenRAL `rskill-moveit-look-at`) / relative camera move | change the viewpoint | reached / blocked |
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

## 5. Harness (contribution, `space_runtime/`)

- **Object facts** (`on:<place> | in_gripper | unknown`), changed only by verified evidence.
- **Independent verifiers** on the query tools: held = jaw range + `hold_check`; placed = jaws open + item at rest on
  the support in view. Never a skill's own success flag.
- **Reconciliation with provenance:** manifest record vs VLM identity vs on-board measurement (extent of the point-cloud
  segment at the chosen candidate) → anomaly naming the sources (`spare_swapped`, `destination_occupied`).
- **Invariants:** no base motion while holding or with the arm outside the hull; stop on a lost track during a contact
  move; contact blocked after an uncertain hold until re-observed.
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
4. rSkills of §3 in the OpenRAL fork; boundary contracts as a thin mapping; move `approach_target` / `locate_in_view` /
   `observe` logic out of the boundary.
5. Harness pieces of §5.
6. G3–G7.

Risks: learned generators are trained on tabletop objects (G1 decides); their CUDA ops vs host CUDA 13 / torch cu128
(separate env if needed); fingers occlude the handle close in (servo to stand-off, then guarded straight close-in);
arm sag under the 1 kg item (F51: 4.5 cm) is within the servo while tracking.
