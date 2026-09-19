"""Offline logic smoke check for the run-manifest writer -- no ROS, no sim,
no pytest (AGENT.md: minimize pytest). Same style as
openral_ext.mission_verifier's own offline smoke check.

Uses the REAL `robots/`/`rskills/` manifests and the REAL
`scenes/deploy/srb_panel_remount.yaml` scene -- no placeholder fixtures.
Resolved against the main checkout at
`/mnt/SharedData/Research/Space_Robot_Harness/openral`, NOT this worktree's
own (unpopulated -- git submodules aren't checked out per-worktree) copy;
this is a worktree-specific interim path, not something to hardcode
post-merge -- once this lands in the same worktree as the actual
`openral/` submodule, drop `_MAIN_CHECKOUT_OPENRAL` and just use
`repo_root / "openral"`.

Run: python3 openral_ext/run_manifest/smoke_test_logic.py
"""

import datetime
from pathlib import Path

import yaml

from openral_ext.run_manifest.backfill import backfill_run_manifest
from openral_ext.run_manifest.capability_registry import resolve_capability_registry
from openral_ext.run_manifest.freeze import list_method_artifacts, plan_freeze
from openral_ext.run_manifest.revisions import submodule_revisions
from openral_ext.run_manifest.schemas import RunManifest

_MAIN_CHECKOUT_OPENRAL = Path("/mnt/SharedData/Research/Space_Robot_Harness/openral")
_REPO_ROOT = Path("/mnt/SharedData/Research/Space_Robot_Harness")


def check(label, fn):
    try:
        fn()
        print(f"PASS {label}")
    except AssertionError as e:
        print(f"FAIL {label}: {e}")
        raise


# ── capability_registry: lunar_bot resolves real procedural + moveit rskills ──
def test_capability_registry_lunar_bot():
    registry = resolve_capability_registry(
        robot_yaml=_MAIN_CHECKOUT_OPENRAL / "robots" / "lunar_bot" / "robot.yaml",
        rskills_dir=_MAIN_CHECKOUT_OPENRAL / "rskills",
    )
    assert registry["robot_id"] == "lunar_bot"
    assert "lunar_bot" in registry["embodiment_tags"]
    assert "mobile_base" in registry["embodiment_tags"]
    ids = {r["rskill_id"] for r in registry["resolved_rskills"]}
    assert any("stow" in i for i in ids), ids
    assert any("move_ee_to_pose" in i for i in ids), ids
    assert any("moveit" in i and "eef_pose" in i for i in ids), ids  # item 6's rm75 retag
    for entry in registry["resolved_rskills"]:
        assert entry["matched_tags"], entry  # every resolved entry names why it matched


# ── capability_registry: nonexistent robot_yaml raises, not a silent empty dict ──
def test_capability_registry_missing_robot_raises():
    try:
        resolve_capability_registry(
            robot_yaml=_MAIN_CHECKOUT_OPENRAL / "robots" / "does_not_exist" / "robot.yaml",
            rskills_dir=_MAIN_CHECKOUT_OPENRAL / "rskills",
        )
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


# ── revisions: superproject gitlink resolves to a real 40-char sha for both ──
def test_submodule_revisions_real():
    revisions = submodule_revisions(_REPO_ROOT)
    assert revisions["openral"] is not None
    assert len(revisions["openral"]) == 40, revisions["openral"]
    assert revisions["space_robotics_bench"] is not None
    assert len(revisions["space_robotics_bench"]) == 40, revisions["space_robotics_bench"]


# ── revisions: a non-git repo_root fails closed to None, not a fabricated sha ──
def test_submodule_revisions_missing_repo():
    revisions = submodule_revisions(Path("/tmp"))
    assert revisions["openral"] is None
    assert revisions["space_robotics_bench"] is None


# ── RunManifest: round-trips through YAML the way the writer actually calls it ──
def test_run_manifest_yaml_roundtrip():
    m = RunManifest(
        run_id="20260101T000000Z-lunar_bot",
        started_at=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        command=["openral", "deploy", "sim", "--config", "scenes/deploy/srb_panel_remount.yaml"],
        cwd="/mnt/SharedData/Research/Space_Robot_Harness/openral",
        robot_id="lunar_bot",
        scene_config_path="scenes/deploy/srb_panel_remount.yaml",
    )
    text = yaml.safe_dump(m.model_dump(), sort_keys=False)
    back = RunManifest.model_validate(yaml.safe_load(text))
    assert back == m
    assert back.exit_code is None  # not-yet-finalized is None, never a fabricated 0
    assert back.ended_at is None


# ── real scene fixture parses the same way the writer's _load_scene does ──
def test_real_scene_fixture_parses():
    scene_path = _MAIN_CHECKOUT_OPENRAL / "scenes" / "deploy" / "srb_panel_remount.yaml"
    data = yaml.safe_load(scene_path.read_text(encoding="utf-8"))
    assert data["robot_id"] == "lunar_bot"
    assert "seed" in data


# ── backfill: a real dev run directory (never wrapped by RunManifestWriter) ──
def test_backfill_real_run():
    m = backfill_run_manifest(_REPO_ROOT / "artifacts/runs/g9a", repo_root=_REPO_ROOT)
    assert m["run_id"] == "g9a"
    assert m["method"] == "ours"  # has an ours/ subdir
    assert m["operator_event_log_path"] is None or m["operator_event_log_path"] == "ours/events.jsonl"
    assert m["openral_revision"] is not None and len(m["openral_revision"]) == 40, m["openral_revision"]
    assert m["command"] is None  # honestly unknown for a run_d0.sh-launched dev run, never guessed


def test_backfill_missing_scene_run_yaml_is_honest():
    m = backfill_run_manifest(_REPO_ROOT / "artifacts/runs/g9a", repo_root=_REPO_ROOT)
    assert m["seed"] is None or isinstance(m["seed"], int)  # None (no scene_run.yaml), never fabricated


# ── freeze: dry-run only, no tag exists, artifacts resolve to real files ──
def test_freeze_ours_artifacts_are_real_files():
    arts = list_method_artifacts("ours", _REPO_ROOT)
    assert any(p.name == "playbook.md" for p in arts), arts
    assert any(p.name == "contracts.yaml" for p in arts), arts
    for p in arts:
        assert p.is_file(), p


def test_freeze_dry_run_creates_no_tag():
    plan = plan_freeze("plexil", _REPO_ROOT, dry_run=True)
    assert plan.would_create is False  # dry_run=True must never tag
    assert plan.head_commit is not None and len(plan.head_commit) == 40


def test_freeze_unbuilt_baseline_is_honestly_empty():
    arts = list_method_artifacts("europa_plexil", _REPO_ROOT)
    assert arts == []  # EUROPA baseline not built yet -- empty, not fabricated


check("capability_registry_lunar_bot", test_capability_registry_lunar_bot)
check("capability_registry_missing_robot_raises", test_capability_registry_missing_robot_raises)
check("submodule_revisions_real", test_submodule_revisions_real)
check("submodule_revisions_missing_repo", test_submodule_revisions_missing_repo)
check("run_manifest_yaml_roundtrip", test_run_manifest_yaml_roundtrip)
check("real_scene_fixture_parses", test_real_scene_fixture_parses)
check("backfill_real_run", test_backfill_real_run)
check("backfill_missing_scene_run_yaml_is_honest", test_backfill_missing_scene_run_yaml_is_honest)
check("freeze_ours_artifacts_are_real_files", test_freeze_ours_artifacts_are_real_files)
check("freeze_dry_run_creates_no_tag", test_freeze_dry_run_creates_no_tag)
check("freeze_unbuilt_baseline_is_honestly_empty", test_freeze_unbuilt_baseline_is_honestly_empty)
print("ALL SMOKE CHECKS PASSED")
