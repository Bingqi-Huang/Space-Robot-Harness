# Handoff

Updated 2026-09-19 after scoped contact permission implementation (F77). First read `AGENT/research_content.md` and `AGENT/execution_plan.md`.
The goal is the Acta Astronautica paper: model-owned mission strategy; a thin harness owns facts, evidence,
verification and hard boundaries. No Mission B-specific skill/tool, hidden solution hint, numeric tuning or recovery graph.
Shared capability defects may be corrected generically; other failures are addressed through the harness.
Current order: **finish Mission B → press live → Mission A → baselines/freeze/experiments**.

## Current user instruction: reproduce success before diagnosing every failure

- User approved implementation/simulation: success reference → generic reproduction → Mission B.
- Active plan is r3 at the top of `docs/manipulation_contracts_proposal.md`; full r2 C1/C3 construction is deferred.
- First compare compatible successful oracle/autonomous records. Diagnose failure only at the first divergence from success.
- Minimal contracts: stable target, factual outcomes on all exits, stage evidence, cancel stops worker without opening jaws.
- In-progress C3 code: feedback IDL/forwarding, cooperative worker stop and final hold commands. Both action interfaces built; open-jaw cancellation validated in g8a.
- Four command-semantics tests pass; g8a live cancellation joined the worker and applied hold; physical_stop_confirmed remains false.
- Current physical reference: `artifacts/runs/reference_r3`, existing D0 script on unchanged assets, robot/wrist recording (see comparison document for the interrupted first bag).
- This run uses truth-assisted manipulation as a reference only, not an autonomous success. No asset modification.

## Current work and live processes

- Latest instruction: allow declared final grasp contact, validate, commit all related work and update handoff/todo.
- F77: measured patch + distal-jaw-only permission; endpoint and insertion use it, standoff remains strict.
- Real MoveIt integration passed: 26,455 triangles preserved, other ACM pairs unchanged, release restores original.
- g8q finished: 785 patch triangles, permission applied, last MoveIt validity=true; servo stalled 27 mm out.
- No closure/transport; independent held=false. Next: offline bag comparison of commanded/measured motion and g8b success.
- EG2 now has independent static/dynamic 0.8/0.6 material; wheels retain 0.5/0.5. Fresh graph required.

- Research branch `feat/manipulation-contracts`, continuing prior uncommitted `fix/mission-operation-evidence` work.
- OpenRAL branch `feat/manipulation-contracts`, 6154482 (manipulation fixes) + 56ce9b8 (method documentation).
- SRB `feat/lunar-base-scene`: 1928821 commits shared gripper friction and sensor depth-return semantics.
- GUI Isaac had already exited; stale agent/check/launch and tagged graph processes were torn down explicitly.
- F78: close-in fix (openral f925430); fragile vetoes → evidence (2a24b9c + planning_scene); g8v tests recovery.
  place `over` stalled 1.1 cm, item still in jaws. g8r: VLM chose 27 mm pedestal; no width-vs-catalogue check yet.
- Only graph g8m_contact retained; runtime 1505904, scene 1504068 (restarted for g8v). Recheck PIDs before control.
- g8p/g8q bags closed; no diagnostic skill. g8q cleanup restored geometry/ACM. Recheck PIDs before control.
- g8p: eg2_link2 collision near neck, ~16-degree axis error, no closure/push. Link2 remains protected by F77.
- Original reference stopped before grasp at obsolete straight-joint READY; restored g6c step 7 in the same graph.
- Reference retained through destination dock; release executed, retreat stalled at step 18.
- Before g8a restore, evaluator later confirmed delivered=true on PDU-1 shelf; no stow/dock completion.
- Offline TF/frames saved under reference_r3_pregrasp/offline_reference. Current assets support grasp/carry.
- g7c candidate 1 spans the wide pedestal (raw depth confirmed); VLM reconfirmation also accepted it, so discarded.
- Generic contour chaining now follows both edges; old g7c depth gains a 12.1 mm neck candidate.
- Shared equipment catalogue includes sourced interface/contact descriptions; Ours refreshes it on attach.
- g8a ended: correct 12 mm neck selected, then template drift/lost lock at 6.9 cm before grasp.
- Canceled automatic re-observation; worker stopped, no implicit jaw change, effect verified not held. Recorder closed.
- Offline RGB-D/TF replay reproduces 5.3 cm adaptive-template drift; actual object stayed still.
- Fixed template/reference depth + contact-width association + odom contact lock retain all 109 replay frames.
- No full re-observation/re-selection inside pick; failures return to caller. See F70.
- g8b pick succeeded: 12.1 mm neck, 0.10 m lift, 0.25 m retraction; independently held, jaw 0.172. Bag closed.
- Offline truth confirms object lifted and retained through retraction; no truth entered control.
- First carry call crashed in drive_limits evidence (scalar lever indexed as array), before navigation. Fixed.
- g8c carried and docked at PDU-1; VLM held check false, but closed-bag TF confirms retained grip (F72).
- g8d model re-queried held=true, placed/released; retreat stalled, so item_placed remains unverified. Bag closed.
- g8e moved clear/inspected; stopped after sufficient evidence. All g8b–g8e recorders closed.
- F73: placement initially in bounds, then axial withdrawal of tilted wrist lifted/dragged released ORU.
- Shared below_overhang release constraint now enables support-parallel withdrawal; no tuned numbers/assets.
- Actual-code replay removes 53.7 mm rise from the same 150 mm stroke; both enum values validate, 4 tests pass.
- g8f ended: correct neck selected, lifted, then lost during bring_in; recorder closed. Place fix not reached.
- g8f also loads verification_finished; development stopping/snapshots wait for independent verification.
- Do not read active SQLite bags; close recorder before offline analysis.
- g6c and gui_verified artifacts/snapshots remain available. Comparison: `docs/success_reference_reproduction.md`.
- Recheck process identities with `ps -eo pid,ppid,args` before stopping anything. Kill explicit PIDs only.

## The important correction: restarting the boundary does not reload skills (F66)

`capability_server` is an action client. Skills run in **openral_rskill_ros/runtime_node**, which caches Python
imports. g6c's original runtime PID 273922 started at 09:34, before the 09:55 unranged-frame tracker correction.
g6d/g6e restarted only the client; they did not validate that correction. Their blanket stand-position diagnosis
was premature. See `docs/research_findings.md` F66–F68 and the actual run records.

Development loop without rebooting Isaac:

1. Stop the old attach parent, check and agent by explicit PID; no stale agent may resume later.
2. Find the current graph's runtime_node PID.
3. Launch with absolute paths:
   `D0_RESTART_RUNTIME_PID=<pid> D0_RESTART_BOUNDARY=1 OURS_MISSION=b OURS_STOP_ON_FAILURE=1`
   `OURS_RESUME_FROM=<log> OURS_RESUME_BEFORE_STEP=<n> setsid nohup <repo>/experiments/launch/lunar_base_d0/attach_d0.sh <graph> <newlog>`.
4. Check `runtime_restart.json`, `runtime.log`, and `RESTORED_ARM` in `check.log`.
5. Only jaws-open snapshots are valid restore points: a physics restore cannot rebuild a grasp.

`restart_runtime.py` preserves actual runtime argv/environment/cwd, checks the explicit PID's graph identity,
and records old/new PID without credentials. Isaac, HAL and the independent safety kernel remain running.
Attach now executes a frozen copy in the run directory, like run_d0.sh. **Do not edit scripts executing in place.**
While fixing attach during this session, the old g6e shell resumed at the wrong byte offset and launched its
check again; g7a had overlapping agents and is invalid. That check truncated g6e's original check/event journal.
Its capability log and appended agent log still contain the earlier failures. This data loss is recorded in F66.
All those old parents/checks/agents were explicitly stopped before g7b.

## What g7b actually measured (F68)

The original step-7 stand was usable for a grasp. Without the site's standard-handle hint, the model's second
local attempt selected the 12.1 mm neck from images. Lift: **0.139 m**, jaw **0.1696 rad**, image flow **1.5 px**
versus **406.9 px** expected if the item stayed behind. Then `bring_in` moved the TCP about 0.30 m inward;
final jaw was **0.100 rad**, empty. The skill said held, but independent `item_held` was **false**.
The agent was paused after verification and then stopped; g7b never carried to the destination.

The retraction used a joint-goal plan, which constrains endpoint orientation but not the path. Its intermediate
rotations were not recorded, so rotation is a plausible cause, not a measured exclusive cause of this drop.
Current fix: reuse place's existing fixed-orientation servo and per-step MoveIt state-validity check for
retraction. Carry settings were moved from place code to both manifests unchanged. Check the jaw afterwards;
only then set outcome=held. A loss returns a typed bring_in failure.

g7c also lost the item: lift 0.079 m, jaw 0.1703, then retraction 0.25 m in 8.14 s, final jaw 0.100.
Endpoint rotation error 0.0198 rad. Orientation preservation alone did not solve the loss. Hold images show
relative sliding during lift. Existing servo traces cover only their beginning; the exact slip time is unknown.
g7d records `/clock`, `/tf`, `/tf_static`, robot joints and arm/gripper commands in `robot_motion/` for diagnosis.
Harness now exposes real VLM selection, operation base estimate and lift/retraction measurements in context.
g7d continues the full failed record and current physical state, without restore or skill edits. To do this,
set `OURS_RESUME_FROM=<log>` and omit `OURS_RESUME_BEFORE_STEP`; keep the same held graph and stop prior agents.

## Other current generic corrections (F67)

- EyeInHandSkill used to initialize `_jaw_open=True`, so **place immediately opened the jaws before release**.
  Reproduced offline with real manifests and g5m's recorded held joints. Now no gripper command is emitted until
  the operation explicitly calls set_jaw. Two targeted command tests pass; physical placement still pending.
- Place now returns actual calibrated `settle.fx`, required by the independent verifier, and declares the
  joint-position actuator its servo uses. Manifest schema validation passes.
- Removed pick's site-specific `handle_convention` default. The generic selector uses images and caller intent.
- Pick retries now have `attempt_01/`, etc., plus `attempt.json`, retaining selection and approach evidence.
  Previously files and trace fields were overwritten on retries; g7b's first approach was copied manually to
  `evidence/observed_first_approach` (its overview already belongs to attempt 2, stated in note.txt).
- Source snapshots/development metadata accompany g7b/g7c. These are development continuations, not frozen
  autonomous-success results. Do not count edited/resumed runs in paper campaign metrics.

## Established context and remaining sequence

- Ours completed Mission A covered before the new manipulation stack (oa2); record-based restart worked (rs1).
- g5m previously completed a depot→PDU-1 carry, lost the payload at destination dock (F63).
  Angular carrying acceleration now derives from measured lever; it still needs successful live verification.
- Place with a held payload, final stow and return dock remain unvalidated.
- Press is built but never pressed a button live; Mission A's prior ready/stand deadlock remains unresolved.
- Do not switch to Mission A before Mission B is complete.

## Operational rules and locations

- One simulation only. All paths absolute. No `pgrep -f` / `pkill -f` process killing.
- Never navigate on simulator truth. `/odom` is wheel-inertial; AMCL uses the lidar-surveyed map; Nav2 goals are map-frame.
- Simulator truth is evaluator-only. No hidden solution sequence in skills, contracts, prompts, guards or verifiers.
- Whole-operation tools only; mechanics stay inside skills. A skill retries the same target, never moves the base.
- Model-facing services use DeepSeek's own endpoint; keys in `AGENT/VLM_provider.md` must not enter logs/output.
- Wrist intrinsics/extrinsics come from CameraInfo/TF, never hardcoded. Jaw bands are shared from `_eye_in_hand`.
- Manipulation uses wrist RGB-D, image candidates and VLM selection; no movable-object CAD model or truth target.
- Boundary: `openral_ext/capability_server/{contracts.yaml,node.py}`. Ours: `space_runtime/`.
- Logs: `<log>/ours/events.jsonl`, `capability_server.log`, `runtime.log`, `evidence/`, `check.log`, `snapshots/`.
- Teardown: `<repo>/experiments/launch/lunar_base_d0/teardown_d0.sh <absolute graph log>`.
- Existing unresolved gaps: effect exceptions can return blank failure; item_cells undersegments the held payload;
  guard has no substantive hard-invariant exercise yet. Fix only when relevant to measured runs.
- Keep this file and todo.md under 150 lines; update at milestones. No hashes, defensive corner-case coding,
  broad test campaigns or unrelated refactors. Replies in concise Simplified Chinese.
