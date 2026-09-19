# evaluation

Execution_plan.md §12-§15 metrics and table generation. No framework, no hand-edited
CSV: every table is produced by a script reading normalized rows.

- `scenario_schema.py` -- loads/validates `experiments/scenarios/**/*.yaml` manifests
  and `*.certificate.yaml` certificates (§12, §13.2).
- `rows.py` -- `extract_row(run_dir)`: one `NormalizedRunRow` per run, read from
  `check.log` + `ours/events.jsonl` (+ `operator/events.jsonl` when present). Two
  fields are explicit DRAFT hooks, not final rules: `preplanned_transition_fraction`
  (see `PREPLANNED_TRANSITION_CATEGORIES`) and the constraint-violation signals
  behind the trust counts (`docs/evaluator_violations_draft.md`).
- `tables.py` -- `wilson_ci`/`bootstrap_ci` (§15) and `success_rate_table()`,
  stratified by method x coverage. `python3 -m evaluation.tables --rows-dir <dir>`.
- `engineering_worklog.py` -- Experiment II timer CLI (§13.4).
- `artifact_delta.py` -- diff summarizer between two freeze tags (§14.4).
- `baselines/` -- PLEXIL log normalization into the common event schema (§14.6); the
  EUROPA token schema slot.
- `smoke_test_logic.py` -- offline checks (no ROS/sim/pytest) against real
  `experiments/scenarios/` manifests and `artifacts/runs/*` dev runs:
  `PYTHONPATH=. python3 evaluation/smoke_test_logic.py`.

## What this does NOT do

- Does not score development runs as campaign results (AGENT.md: development numbers
  are not findings about methods) -- `extract_row` is exercised against dev runs only
  to prove the mechanism works, never to report a method's success rate.
- Does not fill in `preplanned_transition_fraction` or the evaluator's
  constraint-violation list -- both are pending user decisions (see the two files
  above); `rows.py` exposes only the raw counts either would be built from.
- Does not implement HIR/interaction-level metrics beyond what `operator/events.jsonl`
  (written by `experiments/operator_console/`) can supply -- `None` when that file is
  absent, never a fabricated 0.
