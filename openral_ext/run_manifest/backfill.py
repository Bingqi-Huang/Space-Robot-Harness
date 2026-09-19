"""Post-hoc §19 manifest for a run directory `RunManifestWriter` never wrapped.

Every development run under `artifacts/runs/*/` so far was launched by
`experiments/launch/lunar_base_d0/run_d0.sh` directly (not through
`RunManifestWriter`), and this tool must never start or attach to a simulation
(hard rule) -- so it cannot backfill by re-running anything. It only reads what
the run directory already has on disk: `scene_run.yaml`, `check.log`'s
`CHECK_EXIT`/`RESULT` lines, file mtimes, and `ours/events.jsonl` when present.

Deliberately returns a plain dict, not a `RunManifest` -- old dev runs cannot
honestly satisfy that model's required fields (`command`, `cwd`,
`scene_config_path` are always known to the live writer; they are frequently
NOT recoverable after the fact). Every field here is `None` rather than guessed
when the source file does not have it. Revisions are the CURRENT checkout, not
what was checked out when the run executed (these dev runs were not frozen) --
`revision_caveat` says so explicitly in the output.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from openral_ext.run_manifest.revisions import baseline_revision, research_repo_revision, submodule_revisions

__all__ = ["backfill_run_manifest"]

_CHECK_EXIT_RE = re.compile(r"^CHECK_EXIT (-?\d+)\s*$")


def _mtime_range(run_dir: Path) -> tuple[str | None, str | None]:
    import datetime

    times = [p.stat().st_mtime for p in run_dir.rglob("*") if p.is_file()]
    if not times:
        return None, None
    tz = datetime.timezone.utc
    return (
        datetime.datetime.fromtimestamp(min(times), tz=tz).isoformat(),
        datetime.datetime.fromtimestamp(max(times), tz=tz).isoformat(),
    )


def _scene_run(run_dir: Path) -> dict[str, Any]:
    p = run_dir / "scene_run.yaml"
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _check_log_tail(run_dir: Path) -> tuple[int | None, dict[str, Any] | None]:
    """`(exit_code, last mission verdict dict)` from `check.log`, or `(None, None)` if absent."""
    p = run_dir / "check.log"
    if not p.is_file():
        return None, None
    exit_code, mission = None, None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _CHECK_EXIT_RE.match(line)
        if m:
            exit_code = int(m.group(1))
            continue
        if line.startswith("RESULT ") or line.startswith("MISSION "):
            try:
                body = json.loads(line.split(" ", 1)[1])
            except (json.JSONDecodeError, IndexError):
                continue
            mission = body.get("mission", body) if line.startswith("RESULT ") else body
    return exit_code, mission


def _detect_method(run_dir: Path) -> str:
    if (run_dir / "ours").is_dir():
        return "ours"
    check = run_dir / "check.log"
    if check.is_file() and '"executive": "PLEXIL' in check.read_text(encoding="utf-8", errors="replace"):
        return "plexil"
    return "generic_openral"  # a raw D0 capability check, neither method under comparison


def _operator_event_log(run_dir: Path) -> str | None:
    p = run_dir / "ours" / "events.jsonl"
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    return "ours/events.jsonl" if ('"kind": "operator_report"' in text or '"kind": "operator_request"' in text) else None


def backfill_run_manifest(run_dir: Path, *, repo_root: Path, method: str | None = None,
                           plexil_home: Path | None = None) -> dict[str, Any]:
    """Best-effort §19-layout dict for `run_dir` (e.g. `artifacts/runs/<id>`). Read-only."""
    scene = _scene_run(run_dir)
    started_at, ended_at = _mtime_range(run_dir)
    exit_code, mission_verdict = _check_log_tail(run_dir)
    resolved_method = method or _detect_method(run_dir)
    revisions = submodule_revisions(repo_root)

    return {
        "run_id": run_dir.name,
        "started_at": started_at,
        "ended_at": ended_at,
        "exit_code": exit_code,
        "command": None,  # not captured for ad hoc dev runs (run_d0.sh, not RunManifestWriter)
        "cwd": str((repo_root / "openral").resolve()) if (repo_root / "openral").exists() else None,
        "robot_id": scene.get("robot_id"),
        "scene_config_path": None,  # scene_run.yaml is a resolved copy, not the source path
        "seed": scene.get("seed"),
        "method": resolved_method,
        "research_repo_revision": research_repo_revision(repo_root),
        "openral_revision": revisions["openral"],
        "srb_revision": revisions["space_robotics_bench"],
        "plexil_revision": baseline_revision(plexil_home) if resolved_method == "plexil" else None,
        "europa_revision": None,  # EUROPA baseline not built yet (todo.md item 1)
        "operator_event_log_path": _operator_event_log(run_dir),
        "trace_locations": {
            "check_log": "check.log" if (run_dir / "check.log").is_file() else None,
            "capability_server_log": "capability_server.log" if (run_dir / "capability_server.log").is_file() else None,
            "ours_events": "ours/events.jsonl" if (run_dir / "ours" / "events.jsonl").is_file() else None,
        },
        "mission_verdict": mission_verdict,  # evaluator-only; this manifest is a post-run record, not method input
        "revision_caveat": (
            "openral/srb/research-repo revisions above are the CURRENT checkout, not what was "
            "checked out when this run executed -- these dev runs were not frozen (§13.1 step 6 "
            "has not happened yet)."
        ),
    }
