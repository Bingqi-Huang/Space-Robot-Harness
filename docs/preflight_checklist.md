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
| B4 | Exp I secondary metric | Physical-layer failures logged per leg, attributable to a capability, not a method | rows.py field on real runs | PARTIAL: failure_kind/reason come from the shared boundary's log for every method; no failed call yet in step 9 to test on |

## C. Methods

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| C1 | Exp I baselines | PLEXIL: every covered case, retries, hold | `offline_check.py` in the run-farm image | DONE (51/51, 2026-09-24) |
| C2 | Exp I baselines | EUROPA: every §14 covered instance solved and dispatched | `run_offline_mission_{a,b}.sh` in the image | DONE (6/6, 2026-09-24) |
| C3 | Exp I held-out validity | On each §14 held-out state, both baselines end in "detected -> escalated", never solve it (a solve would make the case covered for that baseline) | plexiltest + sim_boundary with each held-out state | DONE 2026-09-24: 6 x 2 escalate -> hold at N=3; N=1,2,5 same outcome (representative cases); none solved. The offline stand-ins model occupancy only as a failed place and report every trip as OVERCURRENT (does not change either baseline's decisions) |
| C4 | Exp I L0/L1 | All three methods complete the seven covered instances live | step 9 | DONE 2026-09-24: 18/21; the three failures shared-layer, fixed (F115) |
| C5 | Exp I held-out | Ours solves the six held-out instances with generic changes only | step 10 | TODO |
| C6 | Exp I | Ours' step budget (`max_steps` 80) fits the longest held-out case | from the first L3 run | ESTIMATE 2026-09-24: step 9 used 2.2 steps per physical call (17-21 steps, 5-9 calls); L3/L4 ~17 calls -> ~40 steps; waiting for ground is one step. Kept at 80; confirm on the first L3 run |
| C7 | fairness | Same mission goal to all three (brief / formal goal equivalence per instance) | read the three inputs per §14 instance | DONE 2026-09-24: no method told the true unit; Mission B item/source/destination identical for all three |

## D. Operator protocol and space context

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| D1 | L4 | Flight-rule table grants PDU-3 -> PDU-1, denies other donors; HOLD for no-procedure; 300 s | console offline cases | DONE 2026-09-24: PDU-3 -> PDU-1 GRANT, ISRU power ORU -> PDU-1 GRANT (also non-critical), PDU-2 donor DENY, no procedure -> HOLD |
| D2 | L4, ALFUS | The Earth-set falls inside an L4 run as it will actually run (mission time at request) | compare the SPICE epoch with L4 run timing | FIXED 2026-09-24: 45 min fell after every run (covered 5-12 min of mission time, L4 ~25 est.); Earth-set now 925 s after the start (three request-answer cycles of the protocol), profile regenerated. Check on the first L4 run |
| D3 | ALFUS metrics | interaction_start/end, authority level, request/grant events logged for all three methods | `evaluation/interaction.py` on real runs | OPEN: covered runs raise no request, so the path is still exercised only on the synthetic L4; the first held-out run with a request (step 10) checks it; a queued escalation now counts as re-authoring required (console + interaction.py, offline-checked) |

## E. Evaluation and metrics (pre-registered before the campaign, §15)

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| E1 | Exp I | Scenario manifests + closed-capability certificates for all 13 §14 instances | `evaluation/scenario_schema.py` validates them | DONE 2026-09-24: 13 manifests + 6 certificates validate; no solution hint in Ours' artifacts; stale pre-§14 manifests removed; rows.py matched only on env.scenario (11/13 unresolved) -> now on every declared override (13/13 unique) |
| E2 | main table | rows.py -> tables.py end to end on real runs of all three methods | run on step 9 output | PARTIAL: rows -> tables run on the finished runs; all resolve to the right instance; baselines' rows after step 9 ends |
| E3 | H3 table | violations.py classes 1-5 give sane counts on real runs | step 9 output + one held-out run | FIXED 2026-09-24: class 2 read a carried item as dropped (held judged from the item's root, not its handle): 23 drops in a delivered run -> 0; a simulated drop still counts. Classes 1, 3-5: 0 on covered runs as expected |
| E4 | ALFUS | `preplanned_transition_fraction` definition final (a DRAFT hook today) | write + review | DONE 2026-09-24: decided per instance (docs/preregistration.md §1); computed from raw data at analysis time |
| E5 | failure analysis | Frozen failure taxonomy; exclusion rules (infrastructure failure -> fix and rerun) | write | DONE 2026-09-24: docs/preregistration.md §2-3 (user-approved) |
| E6 | §15 | Analysis scripts and statistics fixed before the campaign | write, run on step 9 rows | DONE 2026-09-24: docs/preregistration.md §4; run on step 9 rows after it ends |
| E7 | §14.6 | Trace completeness per consequential transition (Ours and baselines) | checker on step 9 runs | PARTIAL: `evaluation/trace_completeness_check.py` (new): Ours 27/27 calls carry proposal, guard, execution, evidence dir, verification; mission-state version = the event log's own sequence number (define in the checker); PLEXIL plan node <-> capability call has no join key (adapter to log the node id, after step 9) |

## F. Freeze and reproducibility (§13.1, §19)

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| F1 | every run | Run manifest (revisions, model config, capability registry, seeds) written by every run | `openral_ext/run_manifest` wired into run_d0? | DONE 2026-09-24: run_d0.sh writes run_manifest.yaml + capability_registry.json after teardown; step 9 backfilled; first live check in check1 |
| F2 | fairness | Freeze audit: no situation-specific hint in any Ours artifact; baselines match the lock | audit script + read | STARTED 2026-09-24: step 10's starting point read (playbook, tools, contracts, guard, config): no situation hint; observe's example "whether a place is occupied" (matches L2-B) removed. Step 10's changes are audited against this point at the freeze |
| F3 | reproducibility | Image, repos tagged; model id and decoding config recorded | tags + manifest | TODO (step 11) |

## G. Experiment II

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| G1 | Exp II | `scan_label` shared implementation, unregistered | build + decode on A1 renders | TODO |
| G2 | Exp II held-out | Hidden cases (spare recorded at the depot but in another PDU's tray/shelf; two ORUs with swapped records) boot and are physically solvable | configs + A2-style check + label decode at each candidate location | TODO |
| G3 | Exp II | Visible validation suite (build, wiring, one nominal case, trace completeness) | write | TODO |
| G4 | Exp II | Timer and artifact-delta tools | `engineering_worklog.py`, `artifact_delta.py` | DONE 2026-09-24: both work (scratch clone with dummy tags) |

## R. Raw data (user rule 2026-09-24: evaluation criteria will change while writing; never re-simulate for it)

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| R1 | any later metric | Every campaign run records the raw data any metric could need: simulator truth (rover, TCP, every object pose, unit states, contacts), joint states, telemetry / brief / inventory, front + wrist frames (low-rate JPEG), navigation (localization, plan, costmaps, cmd_vel), every capability call, Ours' full model input + output per step and every VLM question + answer, baseline plan-node traces and EUROPA solve in/out, operator exchanges, run manifest | list each item's source in a run dir; add what is missing (D0_BAG topics, the evaluator recorder, run manifest); measure data size and sim-speed cost on one run | DONE 2026-09-24 (default bag topics, 1 Hz JPEG frames, model_io.jsonl, per-body contact forces, run manifest; ~0.5 GB per sim hour, no measurable sim slowdown on check1); settle K + T_base_cam added to place's record |
| R2 | re-evaluation | A metric can be recomputed from R1 alone | recompute rows/violations/interaction from the raw record of one run, without the run's derived logs | TODO |

## H. Video and figures

| # | Needed by | Check | How | Status |
|---|---|---|---|---|
| H1 | demo video, trace figure | Every campaign run records what post-hoc video needs (poses, map + path, wrist/front frames at low rate, events); overlays render from it with no rerun | define topics; render one video from a step 9 run with `experiments/video/` | FAIL: no frame source without a live render (0.06x); bag lacks joint_states (jaw line blank), power telemetry, camera frames. Plan: the evaluator recorder saves front + wrist JPEG at 1 Hz (~0.2 GB/h); D0_BAG adds joint_states + power telemetry; live render only for a few showcase runs. Tool bugs: mission_video.py relative default paths drop the mini-map silently |
| H2 | §6.3 trace figure | The full chain intent -> observation -> decision -> call -> guard -> execution -> verification -> fact -> report is in the logs | read one Ours run's events | DONE 2026-09-24: full chain present in ours_a_bess (seq 42-56) |
| H3 | §8 swimlane | Timeline per method with the Earth-visibility window | tool exists? | FAIL: no figure renderer; `*_timeline_from_logs.py` produce the event lists but look for the old bag dir name `robot_motion` (now `bag`) |
