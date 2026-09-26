# Pre-campaign checklist (created 2026-09-24, after the label defect)

Why this exists: step 9 (covered live re-runs) was treated as if it were acceptance, but it only exercises covered
missions; the user found by eye that no Data Matrix label is readable from the pick view (1 of 42 recorded wrist
views decodes), a defect that would have sunk Experiment II and that heldout_design §4 already asked to check. Rule
from now on: **every check is derived from what a paper output needs** (Exp I, Exp II, ablations, figures, metrics),
and each line says what it can and cannot catch. Nothing is frozen (step 11) while a line is open. Offline first; a
live run only where no offline check can answer.

Status: DONE (evidence) / FAIL / TODO / VERIFY (exists, not yet checked against the §14 instances).

## A. Scene and assets (both experiments)

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| A1 | Exp II scan_label, demo video | Every labelled item's Data Matrix decodes from the wrist view `pick` takes, at every support it is picked from; S/N text upright from the rover | render the pick view pose per item x support, decode with zxing-cpp (the capability's own decoder); look at every image | DONE 2026-09-24: flat lid plates + scan_label's own view; offline renders read every ORU view (2x upscale), all non-battery items; Isaac photos from check2 decode (ORU-0417, ORU-0211) (F115) |
| A2 | Exp I all levels | Every §14 instance boots into the intended initial state (tripped unit + cause, shutters, unserviceable modules, occupier, inventory record, reported unit) | instantiate each §14 config offline through the site model's own initial-state functions; compare with §14 | DONE 2026-09-24: all 13 as §14 says (L4 needs `faulted_unit=pdu_1`, now in §14) |
| A3 | Exp I L0-L4 (VLM observations) | The VLM reads every indicator a §14 instance needs (lamp colour per unit, shutter drawn/open at PDU-1 and BESS, occupier on the habitat stand) from the view poses | still renders at the surveyed view poses, one VLM call each (paratera, as runs use) | DONE 2026-09-24 (check1): PDU-1 shutter drawn + lamp red read correctly; the habitat occupier is not visible from the stowed wrist at the approach pose (Ours' concern in step 10, F115) |
| A4 | all figures and video | Scene and items look right from several angles after any asset change | multi-angle stills, looked at | DONE 2026-09-24: item previews after the rebuild looked at (labels flat plates, battery at its own height) |
| A5 | Exp I physical layer | Handle graspable, item-on-support clearance for every item x support used by §14 | `process/check_handles.py`, work_stands for every §14 support | DONE (F112) |
| A6 | Nav / localization | Surveyed map matches the structures | re-survey after footprint changes | DONE (F112, landing stand) |

## B. Shared capabilities and run farm

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| B1 | Exp I | Every action form of every §14 instance executed once | scripted chains | DONE (F112); L4-near's own chain (PDU-3 bay -> PDU-1 bay) not run, its forms are |
| B2 | all runs | No limit set on a single-run host misfires with six at once | sweep of every timeout/resend/window + run-log evidence | DONE (F113, F114) |
| B3 | all runs | Nothing resets or truncates a run (episode length, auto-reset) | config read-back | DONE (F114) |
| B5 | Exp I L2-B baselines | Placing onto an occupied support fails cleanly (no stacking, the occupier not knocked off): the path both baselines take at L2-B, never executed | FIXED 2026-09-24: the place reported success with the container hanging on the open fingers (lifted 0.24 m by the retreat); settle now fails when points remain between the fingers; replayed offline on all 9 recorded places, 1 fails / 8 pass (F115) |
| B6 | Exp I unintended contact | No shared motion drives the rover into a structure: every method's contact count is its own | per-body contact force on the recorded runs; offline sweep of the rover hull along every docking feature's axis | DONE 2026-09-24: the shared 1.5 m (approach point, dock corridor entry, inserted undock; also in the PLEXIL plans and the EUROPA domain) -> 1.2 m everywhere. Offline over all 28 docking features: at 1.5 m 1 hit (depot spares stand -> return stand at 1.38 m), at 1.2 m 0; smallest hull gap 0.18 m; every end point a valid Nav2 pose. PLEXIL 51/51, EUROPA 6/6 offline; live `verify12` (PLEXIL battery run): delivered, no non-wheel contact > 1 N (F115) |
| B4 | Exp I secondary metric | Physical-layer failures logged per leg, attributable to a capability, not a method | rows.py field on real runs | DONE 2026-09-26 (F132): rows.py records every boundary call and each failed one (failure_kind, the skill's failed_stage, reason, mission-time window); tables.physical_failure_table: 334 calls, 13 failed (arm_ready move 3, pick find 3, press locate 3, place settle 1 / release 1, release timeout 2). Every failure_kind is 3; the stage tells them apart. Boundary refusals are not logged |

## C. Methods

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| C1 | Exp I baselines | PLEXIL: every covered case, retries, hold | `offline_check.py` in the run-farm image | DONE (51/51, 2026-09-24) |
| C2 | Exp I baselines | EUROPA: every §14 covered instance solved and dispatched | `run_offline_mission_{a,b}.sh` in the image | DONE (6/6, 2026-09-24) |
| C3 | Exp I held-out validity | On each §14 held-out state, both baselines end in "detected -> escalated", never solve it (a solve would make the case covered for that baseline) | plexiltest + sim_boundary with each held-out state | DONE 2026-09-24: 6 x 2 escalate -> hold at N=3; N=1,2,5 same outcome (representative cases); none solved. The offline stand-ins model occupancy only as a failed place and report every trip as OVERCURRENT (does not change either baseline's decisions) |
| C4 | Exp I L0/L1 | All three methods complete the seven covered instances live | step 9 | DONE 2026-09-24: 18/21; the three failures shared-layer, fixed (F115) |
| C5 | Exp I held-out | Ours solves the six held-out instances with generic changes only | step 10 | DONE 2026-09-26 (F138): 6/6 solved live with Qwen3.8-Max (L2-A x2, L3 x2, L4, L2-B r3 + resume43d from its own snapshot); generic changes only (F117, F118, F123-F125, F138), each recorded. Earlier DeepSeek rounds stopped at 4/6 (F117, F118) |
| C6 | Exp I | Ours' step budget (`max_steps` 80) fits the longest held-out case | from the first L3 run | DONE 2026-09-25: L3 BESS 45, L3 ISRU 44, L2-A 29/42 steps (F117) |
| C7 | fairness | Same mission goal to all three (brief / formal goal equivalence per instance) | read the three inputs per §14 instance | DONE 2026-09-24: no method told the true unit; Mission B item/source/destination identical for all three |
| C8 | §5.7 ablation table (H3) | Ours' four ablation variants exist as frozen configuration switches: without authoritative facts (the agent's own claims advance state), without internal effect verification (skill success flags trusted), without the invariant/authority guard, without dynamic context reconstruction (plain accumulated history); no variant adds or removes mission knowledge | switches in space_runtime + config; offline check per variant on a recorded run; one live smoke per variant | DEFERRED 2026-09-26 (user): how §5.7 is measured is decided when the ablations are due (after Experiment I); F130's reading stands. Not part of Experiment I's freeze |

## D. Operator protocol and space context

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| D1 | L4 | Flight-rule table grants PDU-3 -> PDU-1, denies other donors; HOLD for no-procedure; 300 s | console offline cases | DONE 2026-09-24: PDU-3 -> PDU-1 GRANT, ISRU power ORU -> PDU-1 GRANT (also non-critical), PDU-2 donor DENY, no procedure -> HOLD |
| D2 | L4, ALFUS | The Earth-set falls inside an L4 run as it will actually run (mission time at request) | compare the SPICE epoch with L4 run timing | DONE 2026-09-25: Earth set at 925 s inside every step-10 run; L4 r2 asked at 766.6 s (answer due 1075 s, queued), r3 never asked (F118) |
| D3 | ALFUS metrics | interaction_start/end, authority level, request/grant events logged for all three methods | `evaluation/interaction.py` on real runs | DONE 2026-09-26: both paths exercised live and logged for the interaction measures. Approval: `step10_models/ours_qwen_l4_pdu1` -- guard hold at 213 s (approval_pending), request carrying it at 226 s, interaction_start 230.8 s, GRANT decided 530.8 s (300 s), delivered 535.1 s, approval_granted, the held pick executed after it (F122). Queued escalation after Earth-set: `step10_r2/ours_l4_pdu1` (link_queued, scored re-authoring required, F118) |

## E. Evaluation and metrics (pre-registered before the campaign, §15)

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| E1 | Exp I | Scenario manifests + closed-capability certificates for all 13 §14 instances | `evaluation/scenario_schema.py` validates them | DONE 2026-09-24: 13 manifests + 6 certificates validate; no solution hint in Ours' artifacts; stale pre-§14 manifests removed; rows.py matched only on env.scenario (11/13 unresolved) -> now on every declared override (13/13 unique) |
| E2 | main table | rows.py -> tables.py end to end on real runs of all three methods | run on step 9 output | DONE 2026-09-26 (F132): rows -> tables on all 35 finished runs (step 9: 21; step 10 r1-r4/k3/models: 14): 35/35 resolve to their §14 instance and level; step9/europa_b_oru_pdu3 has no verdict, excluded. Main table method x level with Wilson CI, per-instance k/n, violation, interaction and physical-failure tables render (artifacts/eval/step9_10/tables.md). Fixed on the way: verdict from RESULT only, method from the run manifest, run id with batch, level in the manifests, class 2/3 false positives, interaction mission window |
| E3 | H3 table | violations.py classes 1-5 give sane counts on real runs | step 9 output + one held-out run | FIXED 2026-09-24 (class 2 held from the item's root) and 2026-09-26 (F132): class 2 judged on-support from the site's geometry on the recorded pose (12 -> 2 drops over 35 runs, both real falls); class 3 broken when the item leaves every support (a reseat is not collateral; 4 -> 3). Classes 1, 4, 5 unchanged |
| E4 | ALFUS | `preplanned_transition_fraction` definition final (a DRAFT hook today) | write + review | DONE 2026-09-24: decided per instance (docs/preregistration.md §1); computed from raw data at analysis time |
| E5 | failure analysis | Frozen failure taxonomy; exclusion rules (infrastructure failure -> fix and rerun) | write | DONE 2026-09-24: docs/preregistration.md §2-3 (user-approved) |
| E6 | §15 | Analysis scripts and statistics fixed before the campaign | write, run on step 9 rows | DONE 2026-09-24: docs/preregistration.md §4; run on step 9 rows after it ends |
| E7 | §14.6 | Trace completeness per consequential transition (Ours and baselines) | checker on step 9 runs | DONE 2026-09-26 (F133, offline): Ours 27/27 calls carry proposal, guard, execution, evidence dir, verification; mission-state version = the event log's own sequence number. PLEXIL: the adapter prints the issuing plan node id on every capability call (from CommandImpl's command-handle name); `--method plexil` joins each boundary call to its node instance by that id (scratch run 5/5; offline check 51/51). Lookups have no issuing node (shared state cache). Live `ros/install` rebuilt after the step10_qwen runs; runs before it carry no id |

## F. Freeze and reproducibility (§13.1, §19)

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| F1 | every run | Run manifest (revisions, model config, capability registry, seeds) written by every run | `openral_ext/run_manifest` wired into run_d0? | DONE 2026-09-24: run_d0.sh writes run_manifest.yaml + capability_registry.json after teardown; step 9 backfilled; first live check in check1 |
| F2 | fairness | Freeze audit: no situation-specific hint in any Ours artifact; baselines match the lock | audit script + read | TOOL READY 2026-09-26 (F137): `evaluation/freeze_audit.py` -> `artifacts/eval/freeze_audit/<date>.md`. Against step 10's start (8361741): 34 hunks, all traced to F117/F118/F123/F124 (tools.py's reorganization recorded in F137); no held-out word in model-facing text (one code comment in verification.py names a held-out run: user decides); baselines: only shared fixes since the lock 1b6a40f (F114, F115); plexil.md's stale 1.5 m row corrected. Rerun at the freeze commit |
| F3 | reproducibility | Image, repos tagged; model id and decoding config recorded | tags + manifest | TOOL READY 2026-09-26 (F137): `evaluation/freeze_tag.py` (dry run by default; `--tag` refuses a dirty repo) records the 3 HEADs, the runfarm:22.04 digest, openral/.venv (py3.10) packages, artifact lists, reasoner/VLM models and request arguments into artifacts/freeze/<tag>.yaml. Tag at step 11 |

## G. Experiment II

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| G1 | Exp II | `scan_label` shared implementation, unregistered | build + decode on A1 renders | DONE 2026-09-25 (F131): `openral_ext/scan_label.py`, in no method's artifacts; offline both F115 Isaac photos decode; live (`pf/scan_label_2`, six supports): view reached 6/6, every plate in the frame decoded (3/3), no false reading, empty bay empty; the two no-reads were the rover's docked pose estimate 5-7 cm off sideways (bag truth), plate out of the frame |
| G2 | Exp II held-out | Hidden cases (spare recorded at the depot but in another PDU's tray/shelf; two ORUs with swapped records) boot and are physically solvable | configs + A2-style check + label decode at each candidate location | DEFERRED 2026-09-26: built before Experiment II starts (after Experiment I), hidden from the extension author; not part of Experiment I's freeze |
| G3 | Exp II | Visible validation suite (build, wiring, one nominal case, trace completeness) | write | DEFERRED 2026-09-26: with G2, before Experiment II |
| G4 | Exp II | Timer and artifact-delta tools | `engineering_worklog.py`, `artifact_delta.py` | DONE 2026-09-24: both work (scratch clone with dummy tags) |

## R. Raw data (user rule 2026-09-24: evaluation criteria will change while writing; never re-simulate for it)

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| R1 | any later metric | Every campaign run records the raw data any metric could need: simulator truth (rover, TCP, every object pose, unit states, contacts), joint states, telemetry / brief / inventory, front + wrist frames (low-rate JPEG), navigation (localization, plan, costmaps, cmd_vel), every capability call, Ours' full model input + output per step and every VLM question + answer, baseline plan-node traces and EUROPA solve in/out, operator exchanges, run manifest | list each item's source in a run dir; add what is missing (D0_BAG topics, the evaluator recorder, run manifest); measure data size and sim-speed cost on one run | DONE 2026-09-24 (default bag topics, 1 Hz JPEG frames, model_io.jsonl, per-body contact forces, run manifest; ~0.5 GB per sim hour, no measurable sim slowdown on check1); settle K + T_base_cam added to place's record |
| R2 | re-evaluation | A metric can be recomputed from R1 alone | recompute rows/violations/interaction from the raw record of one run, without the run's derived logs | PARTIAL 2026-09-26 (F132): step10_models/ours_qwen_l4_pdu1 recomputed without check.log / capability_server.log / report.md / scene_run.yaml: 36 of 37 row fields equal (idle waiting 0.0918 vs 0.0919), all violation classes and interaction measures; the bag alone gives the verdict. Baselines: the per-call record is only in capability_server.log (no capability topic in the bag); the reasoner model is in no manifest |

## H. Video and figures

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| H1 | demo video, trace figure | Every campaign run records what post-hoc video needs (poses, map + path, wrist/front frames at low rate, events); overlays render from it with no rerun | define topics; render one video from a step 9 run with `experiments/video/` | DONE 2026-09-26 (F135): `mission_video.py` renders from a run's raw record alone (1 Hz front + wrist frames, bag track + Nav2 plan, events with the model's own rationale/reply, Earth link); ours_qwen_l4_pdu1 -> artifacts/figures/video/ours_qwen_l4_pdu1.mp4 (186 s), looked at. Silent mini-map drop fixed: absolute default paths, a missing file raises |
| H2 | §6.3 trace figure | The full chain intent -> observation -> decision -> call -> guard -> execution -> verification -> fact -> report is in the logs | read one Ours run's events | DONE 2026-09-24: full chain present in ours_a_bess (seq 42-56) |
| H3 | §8 swimlane | Timeline per method with the Earth-visibility window | tool exists? | DONE 2026-09-26 (F135): `experiments/video/swimlane.py` renders one swimlane per run with the Earth window from the link profile at the manifest's revision -> artifacts/figures/swimlane/*.{pdf,png}, looked at. The timeline scripts' real defect was the clock (the bag is recorded on sim time); wall->sim now from the evaluator record. Step-9 baselines ran under Earth-set 2700 s: the like-for-like figure comes from the campaign's held-out baseline runs |
