# evaluation

Execution_plan.md §12-§15 metrics and table generation. No framework, no hand-edited
CSV: every table is produced by a script reading normalized rows.

- `scenario_schema.py` -- loads/validates `experiments/scenarios/**/*.yaml` manifests
  and `*.certificate.yaml` certificates (§12, §13.2).
- `rows.py` -- `extract_row(run_dir, method=...)`: one `NormalizedRunRow` per run, read
  from `check.log` + `ours/events.jsonl` (+ `operator/events.jsonl` when present) plus,
  for the four `evaluator_*_count` fields, `violations.py`. `scenario_id`/`coverage`
  resolve against the *real* manifests under `experiments/scenarios/` (matched on the
  run's raw `env.scenario`/`env.scenery` values, read from `scene_run.yaml`), not
  synthesized. One field is still an explicit DRAFT hook, not a final rule:
  `preplanned_transition_fraction` (see `PREPLANNED_TRANSITION_CATEGORIES`).
- `violations.py` -- the external evaluator's four physical constraint-violation
  classes (`docs/evaluator_violations.md`, the decided definition): unintended
  robot contact, carried-item drop, collateral change, execution during an active
  e-stop/fault. Reads `<run_dir>/evaluator/events.jsonl`
  (`experiments/evaluator_recorder/recorder.py`'s own output, including the poses
  it records itself from `/tf` -- no rosbag dependency) and `capability_server.log`.
  `None` per class when the recorder was not attached, or a needed pose never
  resolved; a mission that structurally has nothing of a class (e.g. Mission A has
  no carried item) is a genuine `0`.
- `tables.py` -- `wilson_ci`/`bootstrap_ci` (§15), `success_rate_table()` and
  `violation_table()` (the four evaluator classes, summed per method x coverage),
  stratified by method x coverage. `python3 -m evaluation.tables --rows-dir <dir>`.
- `engineering_worklog.py` -- Experiment II timer CLI (§13.4).
- `artifact_delta.py` -- diff summarizer between two freeze tags (§14.4).
- `baselines/` -- both methods' logs normalized into the common event schema (§14.6):
  `plexil_normalize.py` (`normalize_plexil_check_log`/`normalize_capability_server_log`/
  `normalize_plexil_node_trace`) and `europa_normalize.py`
  (`normalize_europa_events`, reading `host.py`'s own `events.jsonl` directly -- real
  wall-clock epoch already, no reconstruction needed). Both exercised against real runs
  (F107, 2026-09-22), not just fixtures.

## What this does NOT do

- Does not score development runs as campaign results (AGENT.md: development numbers
  are not findings about methods) -- `extract_row` is exercised against dev runs only
  to prove the mechanism works, never to report a method's success rate.
- Does not fill in `preplanned_transition_fraction` -- still a pending user decision;
  `rows.py` exposes only the raw counts it would be built from.
- Does not implement HIR/interaction-level metrics beyond what `operator/events.jsonl`
  (written by `experiments/operator_console/`) can supply -- `None` when that file is
  absent, never a fabricated 0.
