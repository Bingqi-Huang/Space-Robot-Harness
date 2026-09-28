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

## Now (2026-09-28): Experiment II (H2), heldout_design §6, execution_plan §13.4

User decisions 2026-09-28: Exp II before the ablations (Exp I state tagged `exp1b`, 3 repos); §5.7 ablations by
method B (fault injection + offline counterfactual replay, live only where offline differs), later, from `exp1b`;
extension engineer = Claude, one fresh session per method, Ours -> PLEXIL -> EUROPA; the hidden cases (G2) are built
by the orchestrating session outside the repo and never shown to an extension session.

- [x] Shared supply (F144, tag `exp2-base`): scan_label behind the boundary with no contract; zxing-cpp in the venv;
      a second identical ORU (ORU-0272, recorded failed, landing_stand/slot_1); Mission B knobs name_serial /
      placement / records; spec `docs/exp2/extension_spec.md`; G3 `experiments/exp2/g3_validate.py`; engineer
      checkouts `experiments/exp2/make_worktree.sh`. V1 physical check passed.
- [ ] G2 (hidden, orchestrating session only): built and physically checked; not described here.
- [ ] Ours extension (fresh session, `.worktree/exp2-ours`, timer, G3 PASS, tag `exp2-ours`) -> merge -> hidden runs.
- [ ] PLEXIL extension from the merged Ours state -> hidden runs; then EUROPA -> hidden runs.
- [ ] Exp II table: ETVS, artifact delta (`artifact_delta.py`), validation iterations, modeling errors, hidden success.
- Known limits (F141): localization ~5 cm at bess_stand (map precision), 0.3-1.3 m transients round the habitat row's
  east end; carried items swing +-7 cm while lowered (touchdown phase decides the set-down point).

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
