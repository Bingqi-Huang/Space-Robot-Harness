"""Offline logic smoke check for evaluation/ -- no ROS, no sim, no pytest (AGENT.md). Real fixtures
only: `experiments/scenarios/` manifests and a handful of `artifacts/runs/*` dev run directories.

Run: python3 evaluation/smoke_test_logic.py
"""
from pathlib import Path

from evaluation.artifact_delta import artifact_delta
from evaluation.baselines.plexil_normalize import normalize_capability_server_log, normalize_plexil_check_log
from evaluation.engineering_worklog import add_note, start_session, stop_session, total_active_seconds
from evaluation.rows import extract_row
from evaluation.scenario_schema import iter_manifests, load_certificate
from evaluation.tables import bootstrap_ci, success_rate_table, wilson_ci

_REPO_ROOT = Path("/mnt/SharedData/Research/Space_Robot_Harness")  # artifacts/runs/* dev fixtures live in the main checkout
_SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "experiments/scenarios"  # this worktree's own scenario manifests


def check(label, fn):
    try:
        fn()
        print(f"PASS {label}")
    except AssertionError as e:
        print(f"FAIL {label}: {e}")
        raise


# ── scenario_schema: every real manifest + certificate loads and carries required fields ──
def test_all_scenario_manifests_load():
    manifests = list(iter_manifests(_SCENARIOS_DIR))
    assert len(manifests) == 7, [p for p, _ in manifests]
    for path, m in manifests:
        if m.coverage == "held_out":
            cert = load_certificate(path.with_suffix("").with_suffix(".certificate.yaml"))
            assert cert.scenario_id == m.scenario_id
            assert cert.solution_sequence is None  # never filled in, even in a real fixture


# ── rows: extract_row on real dev runs (mixed outcomes: success, failure, infra crash) ──
def test_extract_row_success_run():
    row = extract_row(_REPO_ROOT / "artifacts/runs/oa1")
    assert row.autonomous_mission_success is True
    assert row.method == "ours"
    assert row.trace_complete is True
    assert row.guard_allowed_count > 0


def test_extract_row_failure_run():
    row = extract_row(_REPO_ROOT / "artifacts/runs/g9a")
    assert row.autonomous_mission_success is False
    assert row.false_completion_declaration_count == 0  # no operator_report was sent, so not a false claim


def test_extract_row_no_mission_verdict_is_honest():
    # pf1 has no ours/ subdir and its MISSION line has no matching family fields it can't parse into
    row = extract_row(_REPO_ROOT / "artifacts/runs/pf1")
    assert row.method == "generic_openral"
    assert row.preplanned_transition_fraction is None  # DRAFT hook, never filled in automatically
    assert row.human_intervention_ratio is None  # no operator/events.jsonl for this run


# ── tables: CI helpers and end-to-end table text on the extracted rows above ──
def test_wilson_ci_matches_known_values():
    p, lo, hi = wilson_ci(1, 2)
    assert abs(p - 0.5) < 1e-9
    assert 0.0 < lo < 0.5 < hi < 1.0
    assert wilson_ci(0, 0) == (0.0, 0.0, 1.0)  # no data -> full-width interval, not fabricated


def test_bootstrap_ci_is_centred_on_the_mean():
    point, lo, hi = bootstrap_ci([1.0, 2.0, 3.0], n_resamples=500)
    assert abs(point - 2.0) < 1e-9
    assert lo <= point <= hi
    assert bootstrap_ci([]) == (0.0, 0.0, 0.0)


def test_success_rate_table_end_to_end():
    rows = [extract_row(_REPO_ROOT / "artifacts/runs" / rid) for rid in ("g9a", "oa1", "oa2", "g8s")]
    table = success_rate_table(rows)
    assert "| ours | covered |" in table
    assert "4" in table  # 4 ours/covered rows go into one stratum


# ── baselines.plexil_normalize: real capability_server.log fixture (same boundary format PLEXIL uses) ──
def test_plexil_capability_log_normalizes_real_fixture():
    events = normalize_capability_server_log(_REPO_ROOT / "artifacts/runs/pf1/capability_server.log")
    assert len(events) >= 3
    assert all(e.method == "plexil" for e in events)
    assert all(e.kind == "execution_finished" for e in events)
    assert any(e.capability == "navigate_to_feature" for e in events)
    assert all(e.plan_node_id is None for e in events)  # honest -- no node-level data in this log format


def test_plexil_check_log_normalizes_synthetic_fixture(tmp_path=Path("/tmp/eval_smoke_plexil_fixture")):
    tmp_path.mkdir(exist_ok=True)
    log = tmp_path / "check.log"
    log.write_text(
        'PLAN {"t": 1.0, "executive": "PLEXIL universalExec 6.1.3", "plan": "MissionA_Covered.plx"}\n'
        'EXEC {"t": 45.9, "exit": 0, "wall_s": 44.9, "sim_s": 43.9, "tail": ["Plan complete."]}\n'
        'STEP {"t": 46.0, "n": 1, "name": "navigate_to_feature", "success": true, "failure_kind": 0, '
        '"failure_reason": "", "args": {"feature": "pdu_2_panel"}, "sim_s": 43.9}\n'
        'DOCK {"t": 46.5, "pos_err_m": 0.127}\n'
    )
    events = normalize_plexil_check_log(log)
    assert [e.kind for e in events] == ["plan_started", "plan_finished", "execution_finished"]
    assert events[2].capability == "navigate_to_feature" and events[2].success is True


# ── engineering_worklog: start/note/stop round-trips through a real log file ──
def test_engineering_worklog_round_trip(log=Path("/tmp/eval_smoke_worklog.jsonl")):
    log.unlink(missing_ok=True)
    sid = start_session(log, extension_id="vlm_scene_query", method="ours", engineer="smoke_test")
    add_note(log, "wired locate_in_view contract, testing offline")
    stopped = stop_session(log, reason="validation suite passed")
    assert sid == stopped
    assert total_active_seconds(log, extension_id="vlm_scene_query") >= 0.0
    log.unlink()


def test_engineering_worklog_rejects_double_start(log=Path("/tmp/eval_smoke_worklog2.jsonl")):
    log.unlink(missing_ok=True)
    start_session(log, extension_id="x", method="ours", engineer="smoke_test")
    try:
        start_session(log, extension_id="x", method="ours", engineer="smoke_test")
        raise AssertionError("expected RuntimeError: a session is already open")
    except RuntimeError:
        pass
    finally:
        stop_session(log)
        log.unlink()


# ── artifact_delta: a real commit range, grouped by ours' own frozen-artifact patterns ──
def test_artifact_delta_real_commit_range():
    delta = artifact_delta("ours", "main~15", "main", _REPO_ROOT)
    assert any("contracts.yaml" in k for k in delta.by_type), delta.by_type
    assert delta.other_files  # some changed files fall outside the frozen set -- must not be silently dropped


check("all_scenario_manifests_load", test_all_scenario_manifests_load)
check("extract_row_success_run", test_extract_row_success_run)
check("extract_row_failure_run", test_extract_row_failure_run)
check("extract_row_no_mission_verdict_is_honest", test_extract_row_no_mission_verdict_is_honest)
check("wilson_ci_matches_known_values", test_wilson_ci_matches_known_values)
check("bootstrap_ci_is_centred_on_the_mean", test_bootstrap_ci_is_centred_on_the_mean)
check("success_rate_table_end_to_end", test_success_rate_table_end_to_end)
check("plexil_capability_log_normalizes_real_fixture", test_plexil_capability_log_normalizes_real_fixture)
check("plexil_check_log_normalizes_synthetic_fixture", test_plexil_check_log_normalizes_synthetic_fixture)
check("engineering_worklog_round_trip", test_engineering_worklog_round_trip)
check("engineering_worklog_rejects_double_start", test_engineering_worklog_rejects_double_start)
check("artifact_delta_real_commit_range", test_artifact_delta_real_commit_range)
print("ALL SMOKE CHECKS PASSED")
