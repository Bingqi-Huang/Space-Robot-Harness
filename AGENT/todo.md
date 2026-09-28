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

- **F141/F142: shared layer fixed, Experiment I rerun (exp1b) done** (`artifacts/runs/exp1b`, 51 scored runs): Ours
  covered 7/7, held-out 18/18; PLEXIL 7/7, 0/6; EUROPA 7/7, 0/6; no physical-layer failure. Two runs invalidated by
  defects found in the batch (place turn regression; adapter lost goal response), fixed and rerun (F142). Tables,
  failures, place offsets, trace completeness in `artifacts/eval/exp1b/`; swimlanes and six textured third-person
  videos (L4, L2-B x 3 methods) in `artifacts/figures/exp1b/`. Evaluator call-window fix recomputed exp1 (unchanged).
  exp1b supersedes exp1 for the paper; exp1 kept.

## Now (2026-09-28): decisions before the next stage

- Done 2026-09-28 (F143): PLEXIL N=1/2/5 on derived plans (outcome never changes); class 2 = a fall (recomputed).
- For the user: §5.7 ablation method (proposed: fault injection + counterfactual replay, F130); whether to start
  Experiment II before the ablations (tag `exp1b` for them), and who plays the extension engineer.
- Known limits (F141): localization ~5 cm at bess_stand (map precision), 0.3-1.3 m transients round the habitat row's
  east end; carried items swing +-7 cm while lowered (touchdown phase decides the set-down point).

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
- No freeze ceremony (user 2026-09-27); shared-layer changes during a campaign: fix, record, rerun only the affected runs.
- Contacts from truth + layout; never navigate on truth; one simulation per GPU; kill only own containers.
