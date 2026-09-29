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

## Now (2026-09-29): Experiment II done (F144-F147)

- [x] Shared supply (F144), G2/G3, three timed extensions (tags `exp2-ours`, `exp2-plexil`, `exp2-europa_plexil`),
      pre-extension controls 0/6; shared fixes during the held-out runs: scan view (F145), on-support fact + Ours'
      step budget counts calls on the robot (F147); only the runs they decided rerun. After the extension: Ours 6/6,
      PLEXIL 2/2, EUROPA 2/2. Cases `experiments/exp2/heldout/`, runs `artifacts/runs/exp2/`, tables
      `python3 experiments/exp2/tables.py` -> `artifacts/eval/exp2/tables.md`.
- Not now (user): plan B (the user as engineer with Claude as assistant).
- Known limits (F141): localization ~5 cm at bess_stand, 0.3-1.3 m transients round the habitat row's east end.

## Next work (after Experiment II)

- [ ] §5.7 ablations, method B, from the `exp1b` tag.
- [ ] Re-authoring cost per held-out case for both baselines (heldout_design §8; feeds H2).
- [ ] Swimlane label overlap (press/press, place/stow) before the paper figure.
- [ ] Paper: results section from `tables.md` + `failures.md`; limitations (one engineer, category-level L2-B
      precedent, AMCL bias, fixed 300 s ground decision, Ours' post-mission inspection tours lengthen covered runs;
      Exp II: extension engineers are Claude sessions, the held-out categories were in heldout_design §6).

## Clean-up (user 2026-09-26: keep for now)

- `artifacts/runs/step10_final`, `.worktree/prefreeze` + branch.

## Rules (user)

- Simplified Chinese replies, plain words, conclusion first. Decide defaults yourself; ask only design questions.
- Only fix the current blocker; offline check first, one decisive live test; never rerun what already passed.
- No freeze ceremony (user 2026-09-27); shared-layer changes during a campaign: fix, record, rerun only the affected runs.
- Contacts from truth + layout; never navigate on truth; one simulation per GPU; kill only own containers.
