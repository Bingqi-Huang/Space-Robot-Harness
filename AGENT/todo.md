# TODO

Goal: the Acta Astronautica paper. `docs/heldout_design.md` is the plan (§10 work order, §14 instances).
`docs/preregistration.md` fixes metrics, failure taxonomy, exclusion and statistics.

## Done (see docs/research_findings.md)

- F108-F125: site, scenarios, protocol, evaluator, baseline lock, run farm, steps 7-10, Qwen3.8-Max, prompts/ours,
  request kinds. F130-F137: ablations deferred, scan_label, rows->tables, PLEXIL node id, video/swimlane, retry
  budget, freeze tools. F138: step 10 6/6. F139: freeze `freeze-1` (pushed).
- **F140: Experiment I done** (`artifacts/runs/exp1`, 51 scored runs): Ours covered 7/7, held-out 17/18; PLEXIL 6/7,
  0/6; EUROPA 7/7, 0/6. Tables `artifacts/eval/exp1/tables.md`, failures + categories `failures.md`, place offsets,
  trace completeness; swimlanes (L4, L2-B x 3 methods) and Ours videos (L4, L2-B) in `artifacts/figures/exp1/`.

## Decisions for the user (from F140)

- [ ] Shared-layer issues found in the campaign (not fixed; a post-freeze shared fix reruns the affected campaign):
      bess_stand set-down bias (+8-10 cm along, all methods); base-withdrawal drag (2-65 mm); Nav2 in-place reversals
      shaking a carried item loose (Ours L2-B r2); dock_to_pose ignoring the costmap (Ours drove into the habitat);
      the PLEXIL adapter losing a first command result (2/27 baseline runs, category 8).
- [ ] Class-2 definition: one drop counted twice after a push; an upright item off the scored footprint read as a
      drop. Keep as computed or redefine (recompute from raw data, no rerun).
- [ ] §5.7 ablations: how to measure (F130: natural runs likely null; fault injection + replay proposed).
- [ ] PLEXIL retry budget N=1,2,5: argument only, or a derived plan variant (F136).

## Next work (after the decisions)

- [ ] Experiment II (H2): G2 hidden cases + G3 validation suite (built hidden from the extension author), register
      `scan_label`, extension timing (`engineering_worklog.py`, `artifact_delta.py`).
- [ ] Re-authoring cost per held-out case for both baselines (heldout_design §8; feeds H2).
- [ ] Baseline videos: `plexil_mission_video.py` / `europa_mission_video.py` need a frames mode like Ours' (F135).
- [ ] Swimlane label overlap (press/press, place/stow) before the paper figure.
- [ ] Paper: results section from `tables.md` + `failures.md`; limitations (one engineer, category-level L2-B
      precedent, AMCL bias, fixed 300 s ground decision, Ours' post-mission inspection tours lengthen covered runs).

## Clean-up (user 2026-09-26: keep for now)

- `artifacts/runs/step10_final`, `.worktree/prefreeze` + branch.

## Rules (user)

- Simplified Chinese replies, plain words, conclusion first. Decide defaults yourself; ask only design questions.
- Only fix the current blocker; offline check first, one decisive live test; never rerun what already passed.
- Frozen at `freeze-1`: no change to a method artifact or shared skill without the user; campaign runs are scored.
- Contacts from truth + layout; never navigate on truth; one simulation per GPU; kill only own containers.
