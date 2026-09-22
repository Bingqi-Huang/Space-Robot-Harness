# run_manifest

Run-manifest writer for reproducible experiment provenance
(execution_plan.md item 8 / §19 "Experiment artifacts and reproducibility").
Wraps `openral deploy sim`; does not reimplement its launch orchestration.

## Why this exists

Per §19, every run directory should contain (or honestly omit, with a
reason) the manifests, revisions, and trace/event data needed to
reproduce and audit a run without hand-editing anything afterward.
`docs/upstream_pins.md` has tracked `openral`/`space_robotics_bench`
revisions by hand after every merge — this makes that (and the rest of
§19's still-real fields) automatic per run instead.

## What it writes for real, and what it honestly omits

Written for real, from actual sources — never a placeholder value:

- `run_manifest.yaml` — run id, start/end time, exit code, the exact
  `openral deploy sim` invocation, robot id, scene config path, seed.
- `mission_config.yaml` — the resolved scene YAML content + its source path.
- `method_config.yaml` — `method: generic_openral` (the one real condition
  today — no baseline-comparison axis exists yet, see below).
- `openral_revision.txt` / `srb_revision.txt` — exact submodule commits,
  read from the superproject's own git metadata (`git ls-tree HEAD --
  <submodule>`) — works even if the submodule isn't checked out in the
  writer's own working tree.
- `capability_registry.json` — the robot's declared capabilities +
  every rSkill whose `embodiment_tags` resolves for it (same embodiment-tag
  intersection `openral check` uses, reimplemented independently against
  the public `openral_core.schemas` contracts rather than importing
  `openral_cli.check`'s private helpers across the submodule boundary).
- `events.jsonl` / `traces/<trace_id>.json` — real OTel spans, pulled from
  the dashboard's own read-only query API
  (`openral_observability.replay.trace_query.DashboardTraceClient`,
  `GET /api/traces` + `GET /api/spans/<id>`) while it's still reachable,
  at finalize time. If the dashboard is unreachable, `events.jsonl` says so
  in one line — it is never filled with fabricated data.
- `metrics.json` — run duration, exit code, trace count, whether rosbag
  was enabled. Deliberately thin: no evaluator/verifier-aggregated metrics
  exist yet beyond item 7's `VerifierEvent` stream, and this writer does
  not itself subscribe to that stream (a live rclpy subscriber inside the
  writer is a real, reasonable future addition — not built here to avoid
  adding a second live-subscription failure mode on top of the trace
  query, which is dashboard-based and doesn't need `rclpy` at all).
- `rosbag/` — opt-in (`--rosbag`), `ros2 bag record` scoped to a fixed,
  bounded topic list (`candidate_action`/`safe_action`/`safety_status`/
  `verifier_events`/`tf`/`tf_static`), not `-a` — §19: "large raw sensor
  data may be stored separately."

Honestly omitted (via `omitted_files.txt` in the run directory naming each
one and why — never silently missing, never a fabricated stand-in):

- `space_context_ref.yaml`, `network_profile_ref.yaml` — `space_context/`
  and `network/` are still empty placeholders (execution_plan.md §21.6-7:
  not built until Phase B hits a real failure calling for them).
- `model_config.json` — no reasoner LLM is in the loop yet for this robot
  (B3 has not been attempted); nothing real to record.
- `videos/` — not built; no obvious cheap real source for this yet.

## Layout

- `schemas.py` — `RunManifest` (Pydantic), the generic run header. Now also
  carries the method-comparison axis (`method`, `research_repo_revision`,
  `plexil_revision`, `europa_revision`, `operator_event_log_path`) -- §12/§19.
- `revisions.py` — `submodule_revisions()`, `research_repo_revision()`,
  `baseline_revision()` (PLEXIL/EUROPA, built outside this repo, best-effort).
  Pure, no ROS/sim.
- `capability_registry.py` — `resolve_capability_registry()`, pure, no ROS/sim.
- `writer.py` — `RunManifestWriter`, the orchestration (subprocess launch,
  rosbag, trace query, finalize). The only piece that needs a live process
  to exercise past the file-writing logic itself.
- `backfill.py` — `backfill_run_manifest()`: a post-hoc §19-layout dict for a
  run directory `RunManifestWriter` never wrapped (every dev run under
  `artifacts/runs/*/` so far, launched by `run_d0.sh` directly). Read-only,
  never launches anything -- this tool must not start or attach to a
  simulation. Returns a plain dict, not `RunManifest`: old runs cannot
  honestly satisfy that model's required fields (`command`/`cwd` are unknown).
- `freeze.py` — `list_method_artifacts()` / `plan_freeze()`, execution_plan.md
  §13.1 steps 5-6. `plan_freeze` is dry-run by default and has never been run
  with `dry_run=False` -- no freeze tag exists yet. See `docs/freeze_audit.md`
  for the checklist to run before it ever is.
- `__main__.py` — `python -m openral_ext.run_manifest --config <scene.yaml>`.

## Running it

```bash
cd <repo root>
python3 -m openral_ext.run_manifest \
    --config scenes/deploy/srb_panel_remount.yaml \
    --ros-domain-id 77 --discovery-range LOCALHOST
# Ctrl+C to end the run (graceful SIGINT, matches this project's own
# teardown convention) -- the run directory finalizes either way.
```

Needs `openral_core`, `openral_observability`, `pydantic`, and `PyYAML`
importable — i.e. run through the same environment `openral`'s own tools
use (`openral`'s `.venv`, with this repo's root also on `PYTHONPATH` so
`openral_ext` resolves).

Output lands in `experiments/manifests/<run_id>/` (§19's suggested
top-level location, already scaffolded with a `.gitkeep`), one directory
per run, `<UTC timestamp>-<robot_id>`.

## What it deliberately does NOT do

- Does not reimplement `deploy_sim.py`'s launch orchestration
  (`resolve_launch_invocation`/`run_launch_invocation`, 3300+ lines) — it
  shells out to the real `openral deploy sim` CLI and observes.
- Does not fabricate content for §19 fields with no real source yet
  (see "honestly omitted" above) — an empty/missing file with a reason
  beats a placeholder that looks real.
- Does not aggregate multiple runs into analysis tables — §19 also asks
  for that ("scripts that aggregate run artifacts... without hand-editing
  CSV files"), but that needs more than one real run's worth of data to
  design against sensibly; out of scope for this first version.
