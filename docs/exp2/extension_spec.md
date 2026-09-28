# Experiment II extension specification: `exp2_scan_label`

Released to each method's extension engineer at the start of their timed session (execution_plan §13.3-13.4,
research_content §5.6, docs/heldout_design.md §6). Everything here is visible to every engineer. The held-out extension
cases are not: they are built and kept outside this repository by another session, and an engineer does not look for
them (see "Rules").

```yaml
extension_id: exp2_scan_label
new_shared_capability: scan_label          # the boundary carries it; no method is registered with it yet
new_mission_requirement: the delivered unit is the one the brief names by serial; the inventory record can be wrong
validation_cases: [V1]                     # experiments/exp2/g3_validate.py
held_out_cases: hidden                     # same mission form as V1, the record not matching the site
allowed_shared_changes: none by the engineer (a shared defect stops the timer and is fixed for every method)
base: tag exp2-base (research, openral, SRB)
```

## 1. What changed on the base

- **The inventory record can be wrong.** Mission control's record (the `manifest` query; the EUROPA host's facts)
  says what each tracked item is, where it is and its status. It is a record, not an observation: an item can stand
  somewhere other than its recorded place, and two items of the same kind can have each other's records. Items of one
  kind are physically identical; only the serial on their data plate tells them apart. The site now also holds a second
  ORU besides the depot spare: ORU-0272, recorded failed (removed from service, awaiting return shipment) and staged at
  `landing_stand/slot_1`; installed in a bay it fails its unit's self-test.
- **A label scanner is available**: `scan_label` (§3), identical for every method.

## 2. The new mission requirement

Mission B briefs can name the cargo by its serial (`env.name_serial=true`):

> Deliver the spare ORU ORU-0417 staged at the depot stand (slot 0 per the manifest) to the spares shelf of PDU-2,
> then return the rover to the dock with the arm stowed.

The mission succeeds only when **that unit** (by serial) stands on the destination, the rover is on its dock and the
arm stowed. Delivering an identical unit with another serial is a failed mission. The baselines' formal goal
(`MISSION_GOAL`, `experiments/launch/lunar_base_d0/d0_common.py mission_b_goal()`) then carries `serial` beside
`item`, `source` and `destination`. The brief's "staged at" is the record's word; §1 says what that is worth.

## 3. The shared capability (supplied, not timed)

`openral_ext/scan_label.py`, executed by the capability boundary (`openral_ext/capability_server/node.py`,
`CapabilityServer.scan_label`); zxing-cpp is in the openral venv.

- **Call**: effect `scan_label` with `{"support": <a site place frame, e.g. depot_stand/slot_0>, "item": <the
  equipment-catalogue kind expected there, e.g. "orbital replacement unit (ORU)">}`. The rover must be docked at the
  support (`dock_at_feature` with `standoff_m` 0 reaches the view at the depot stand, the landing stand and the PDU
  shelves) and the jaws empty (the boundary refuses it while the jaws hold something, like `stow`).
- **What it does**: the wrist camera goes to one view of the item's lid next to its handle (collision-checked IK, the
  posture skill's planned path), one frame is taken, every Data Matrix in it is decoded, the arm folds to its travel
  posture. About 6 s of mission time (the V1 physical check: every call of the V1 sequence succeeded at its first attempt).
- **Result**: `success` is false only when the view cannot be taken (the reason says why, e.g. no arm configuration
  from where the rover stands). Reading nothing is a success with no serials: an empty support, or a plate out of the
  frame. The result's evidence JSON (`evidence_json`; PLEXIL: `LastCapabilityResult`) carries
  `evidence["scan"] = {"serials": [...], "plates": [{"serial", "corners_px", "px_from_aim"}], "image", "raw_image",
  "support", "view_error_m", "folded"}`. A neighbouring item's plate can be in the frame too; `px_from_aim` is each
  plate's distance in the image from the point the view was aimed at (the item on the named support is the nearest).
- **Not registered**: `openral_ext/capability_server/contracts.yaml` has no `scan_label` entry, so the boundary
  refuses the call ("unknown capability"), Ours' palette does not offer it, no PLEXIL Command or EUROPA activity names
  it. Registering it and making it usable at mission level is the timed work.

## 4. What each engineer may change

Only the method's own artifacts (`openral_ext/run_manifest/freeze.py` `METHOD_ARTIFACTS`); `evaluation/artifact_delta.py`
reports the change against `exp2-base`, anything outside the method's set as "other files".

- **Ours**: the contract entry (a contract is also the shared interface: once it exists, the baselines use it and do
  not write their own) and whatever else of Ours' artifacts the validation needs. Every change is mission-generic and
  passes three tests: it names no situation, instance, site place or serial; it holds for every task Ours is given;
  it traces to this specification. No hint of how to handle a wrong record; each change is recorded with its reason.
- **PLEXIL, EUROPA -> PLEXIL**: `docs/baselines/authoring_spec.md` holds, with this specification added to the covered
  specification (rule (a)): what this document states may be encoded -- e.g. check the named serial by scanning,
  and look for the unit elsewhere when it is not where the record says. Knowledge beyond it (a particular wrong
  record, a particular place) may not. The shared adapter and HostLink bridge may be extended to carry the new call
  and its result; they still hold no mission logic. Tier 1 (3 attempts per call) is unchanged.
- **Not the engineer's**: skills, the boundary's implementation, SRB, the evaluator, this spec, the validation suite.
  A defect found there is shared infrastructure: note it, stop the timer, report it; it is fixed for every method
  and the timer resumes.

## 5. Protocol (timer, record, validation)

1. Branch `exp2/<method>` from `exp2-base` in this checkout (runs launch from it).
2. Start the timer: `python3 evaluation/engineering_worklog.py --log experiments/exp2/worklog/<method>.jsonl start
   --extension-id exp2_scan_label --method <ours|plexil|europa_plexil> --engineer <session id>`. Stop it for any pause
   (`stop --reason ...`), start it again to resume. Time is active work: reading, editing, building, offline checks,
   waiting on a validation run.
3. Record each validation failure and each modeling/logic error found (`note "..."`): these are §14.4's validation
   iterations and modeling errors.
4. Validate: one live run of the method on V1, then `python3 experiments/exp2/g3_validate.py --method <m> <run dir>`.
   The run (jobs file `experiments/exp2/jobs/<method>_v1.txt`, one line; see `experiments/exp2/jobs/README.md`):
   - Ours: `D0_CHECK=ours_mission_check.py`; PLEXIL: `D0_CHECK=d0_plexil_mission_b_check.py`; EUROPA:
     `D0_CHECK=d0_europa_mission_b_check.py`; all with `D0_CAPABILITY_SERVER=1
     D0_SCENE=scenes/deploy/srb_lunar_base_mission_b.yaml D0_SCENARIO=covered D0_ENV='env.cargo=spare_oru
     env.destination=pdu_2 env.name_serial=true'`.
   - Offline checks of the method's own (plexiltest, the EUROPA offline chain, a stand-in boundary) are the engineer's
     choice and count as work.
5. Stop the timer at the first `G3 PASS`. Commit the method's changes and the worklog on the branch; tag `exp2-<method>`.
6. Then, and not before, another session runs the hidden cases on `exp2-<method>`.

## 6. Rules for the extension session

- Do not look for the held-out extension cases: do not open `/mnt/SharedData/Research/exp2_hidden/`, other sessions'
  run directories under it, or anything outside this repository about Experiment II's held-out cases. Design for what
  §1-2 say, not for a guess about particular cases.
- The run farm's rules (AGENT/handoff.md "Run farm", "Running it"): one simulation per GPU, only your own containers,
  long runs watched with a Monitor on milestones rather than polling; the validation runs use GPUs 3-5.
- No change to shared code while any run is live (openral rskill modules, SRB assets, libraries a run loads).
