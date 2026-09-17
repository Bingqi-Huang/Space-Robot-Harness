# Semantic-to-metric manipulation: design and validation plan

Status: plan (2026-09-17, user decision). Replaces the VLM-point + open-loop pick that failed repeatedly in Mission B
(runs ob1–ob6, `AGENT/handoff.md`). No code yet.

## 1. Why, and what is claimed

Every pick/place failure had one root: nothing in the pipeline knew the object's metric 6-DoF state, the motion was
open loop (two VLM looks, a blind slide), no physical result was checked, and geometry was left to the LLM.

Space heritage already has model-based pose estimation + visual servoing for pre-designated targets (ETS-VII capture,
Orbital Express ORU transfer, Dextre ORU swaps with targets, CAD-edge pose refinement for ORU insertion). **Not claimed:**
the servo law, the pose tracker, the detector. **Claimed (new contribution, alongside the harness):** a layered
*semantic-to-metric* manipulation architecture that lets a language-level mission agent act on targets designated
online, with the target's identity reconciled across records (manifest), semantics (VLM) and on-board measurement, and
with the physical result independently verified by the harness; recovery stays with the agent, not in the skill.

## 2. Layers

| Layer | Where | Role | Rate |
|---|---|---|---|
| Reasoner | ground/cloud | names the goal in words ("pick the spare ORU at slot 0 by its handle") | per step |
| Semantic selection (VLM) | cloud | picks which numbered on-board candidate is the named item/part | once per target |
| On-board perception | robot | candidates, CAD-model pose init, 6-DoF tracking, planning-scene sync | camera rate (15 Hz) |
| On-board control | robot | MoveIt coarse move, PBVS through the arm kinematics, pre-grasp / post-lift checks | 15 Hz |
| Harness (contribution) | robot | object facts, independent verification, reconciliation, invariants, evidence | per event |

Perception and control are decoupled by one message: `ObjectPose{item, T_base_obj, quality, stamp, source}`.

## 3. Components

### 3.1 Part catalog (design data, not truth)
`configs/part_catalog.yaml`, one entry per standard item (spare ORU, cargo crate; later tools):
mesh (OBJ exported from the SRB USD asset), size, mass, appearance text for the VLM, grasp interfaces (frame in the
object frame, approach axis, expected jaw angle range from the neck thickness, pre-grasp distance), place interface
(bottom frame). Source values: `interaction.json` `objects.*.handle` (ORU neck 12 mm, width 0.16 m, depth 0.028 m) and
the asset geometry. A new item = a new entry (Experiment II's extension unit).

### 3.2 On-board perception (shared capability stack, `openral_ext/perception/`)
- **Candidates:** open-vocabulary detector, boxes numbered on the image. OpenRAL already runs OmDet-Turbo as a
  `zeroshot_hf` detector engine; Grounding DINO / OWLv2 as alternatives.
- **Semantic selection:** set-of-mark prompt to the shared VLM (GLM-5.3-Flash): "which number is <catalog appearance>?".
- **Pose init + tracking behind one `PoseTracker` interface:**
  - FoundationPose (primary): CAD mesh + RGB-D, register from the box (depth-cropped mask, no separate segmenter),
    then track. Runs as a sidecar process in its own CUDA environment (host torch 2.9.1+cu128, nvcc 13.0).
  - ViSP model-based tracker (classical comparator; edges + KLT + depth, CPU; `ros-humble-visp` 3.7.0 in apt).
  Track the whole box; the handle frame follows from the CAD model (a large textured body tracks far better than a
  12 mm neck).
- **Planning-scene sync:** the tracked item's mesh as a MoveIt collision object (attached to the gripper once held).

### 3.3 On-board control rSkills (shared capability stack)
- **`grasp_object(item, interface)`**, one attempt, honest report:
  1. view: OpenRAL `LookAtRskill` (MoveGroup gaze) if the item is not tracked;
  2. feasibility: pre-grasp → grasp → lift checked together (IK, collisions, joint margins);
  3. coarse: MoveIt to the pre-grasp;
  4. PBVS: `e = log(T_tcp⁻¹ · T_grasp)` from the live track, `v = -λ e` saturated, through the existing Cartesian twist
     path; stop on track quality drop or stall;
  5. pre-grasp visual check: finger volumes (arm FK + camera extrinsics) and the handle mesh projected into the wrist
     image and depth; handle centred between the fingers within margin, else report `misaligned`;
  6. close; jaw angle within the catalog range for that interface;
  7. lift; the tracked item moves with the TCP (Δpose agreement).
  Outcomes: `ok | not_visible | not_identified | unreachable(detail) | track_lost | misaligned | not_clamped | slipped`,
  with the evidence bundle (annotated candidates, overlay, pose track).
- **`place_object(item, place_point)`**: symmetric; support surface from depth; lower under PBVS; release; item at rest
  on the support.

### 3.4 Common capability boundary
Effects `grasp_object`, `place_object`; queries `locate_object` (pose + identity evidence), `object_state`. Same
contracts for Ours, PLEXIL and EUROPA→PLEXIL.

### 3.5 Harness (contribution, `space_runtime/`)
- **Authoritative object facts:** item location `on:<support> | in_gripper | unknown`, changed only by verified evidence.
- **Independent verifiers** (not the skill's success flag): `object_in_gripper` (jaw range + co-moving track),
  `object_on_support` (track at rest within the support footprint, jaws open), `object_released`.
- **Reconciliation with provenance:** manifest record vs VLM identity vs on-board geometric fit (catalog mesh
  residual/size); disagreement → anomaly naming the sources (drives `spare_swapped`, `destination_occupied`).
- **Invariants (guard):** no base motion while holding an item or with the arm outside the hull; track lost during
  an arm effect → FDIR fact that blocks further contact effects until re-observed.
- **Evidence and traces:** every outcome links its frames/overlays/tracks for ground reconstruction.

## 4. Validation gates (in order; each gate before the next)

| Gate | Test | Pass |
|---|---|---|
| G0 data | record RGB-D + wrist pose + truth item pose (evaluator only) at ~30 viewpoints around the depot slot, ORU and crate | dataset saved |
| G1 perception (offline) | FoundationPose vs ViSP: init success, translation / rotation error of the handle frame | init ≥ 90 %, < 1 cm, < 3° |
| G2 identity (offline) | candidates + set-of-mark selection on the recorded frames; swapped items | correct item ≥ 95 %, swap detected |
| G3 grasp (live, snapshot at the depot dock) | 10 trials, base pose perturbed ±5 cm / ±5° | ≥ 9/10 clamped and lifted |
| G4 place (live) | 10 trials onto PDU-1's shelf | ≥ 9/10 at rest on the shelf |
| G5 ablation | VLM point + open loop / tracking without semantic reconciliation / full: grasp success; swapped-item trial | reported |
| G6 missions | Mission B covered with the agent, then `destination_occupied`, `spare_swapped` | verifier success |

## 5. Risks

- FoundationPose build (CUDA extensions vs host CUDA 13 / torch cu128) → sidecar env; ViSP needs `sudo apt install`.
- Mesh export from USD (textures irrelevant for depth; edges need the true geometry).
- Arm sag under the 1 kg item (F51: 4.5 cm) is within PBVS's job while tracking, but the lift check must allow it.
- Truth is used only in G0/G1 labels and evaluation, never by the skills or the harness.

## 6. Work order

1. Catalog + mesh export; G0 recording check (`experiments/perception/record_rgbd.py`).
2. G1: FoundationPose sidecar and ViSP tracker on the dataset.
3. G2: candidate detector + set-of-mark selection.
4. rSkills `grasp_object` / `place_object` (PBVS, checks, outcomes) + boundary contracts.
5. Harness: object facts, verifiers, reconciliation, invariants.
6. G3–G6 on the held-graph snapshot workflow.
