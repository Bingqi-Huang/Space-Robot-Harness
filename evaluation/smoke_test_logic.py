"""Offline logic smoke check for evaluation/ -- no ROS, no sim, no pytest (AGENT.md). Real fixtures
only: `experiments/scenarios/` manifests and a handful of `artifacts/runs/*` dev run directories.

Run: python3 evaluation/smoke_test_logic.py
"""
from pathlib import Path

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


check("all_scenario_manifests_load", test_all_scenario_manifests_load)
check("extract_row_success_run", test_extract_row_success_run)
check("extract_row_failure_run", test_extract_row_failure_run)
check("extract_row_no_mission_verdict_is_honest", test_extract_row_no_mission_verdict_is_honest)
check("wilson_ci_matches_known_values", test_wilson_ci_matches_known_values)
check("bootstrap_ci_is_centred_on_the_mean", test_bootstrap_ci_is_centred_on_the_mean)
check("success_rate_table_end_to_end", test_success_rate_table_end_to_end)
print("ALL SMOKE CHECKS PASSED")
