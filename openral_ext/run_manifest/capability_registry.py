"""Resolve which rSkills target a robot — the real content of `capability_registry.json`.

Pure reuse of `openral_core`'s public schema contracts
(`RobotDescription.from_yaml` / `RSkillManifest.from_yaml`), the same
embodiment-tag intersection `openral_cli.check._check_rskills` already
does — reimplemented independently here (not imported: `check.py`'s
helpers are underscore-private, and this module needs to keep working
even if that CLI's internals change) rather than against a private API
across the `openral` submodule boundary. No ROS, no simulator — offline,
testable against the real manifest files on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["resolve_capability_registry"]


def resolve_capability_registry(*, robot_yaml: Path, rskills_dir: Path) -> dict[str, Any]:
    """Return the robot's declared capabilities + every rSkill that resolves for it.

    Args:
        robot_yaml: Path to `robots/<id>/robot.yaml`.
        rskills_dir: Path to the `rskills/` directory (each `*/rskill.yaml`
            is a candidate).

    Returns:
        A JSON-serialisable dict: `robot_id`, `embodiment_kind`,
        `embodiment_tags`, `supported_control_modes`, and
        `resolved_rskills` (one entry per rSkill whose `embodiment_tags`
        intersects the robot's, or declares the `"any"` wildcard) with
        `rskill_id`, `version`, `kind`, `role`, `matched_tags`.

    Raises:
        FileNotFoundError: `robot_yaml` does not exist.
    """
    from openral_core.schemas import RobotDescription, RSkillManifest

    if not robot_yaml.is_file():
        msg = f"robot_yaml not found: {robot_yaml}"
        raise FileNotFoundError(msg)

    robot = RobotDescription.from_yaml(str(robot_yaml))
    robot_tags = set(robot.capabilities.embodiment_tags)

    resolved: list[dict[str, Any]] = []
    for path in sorted(rskills_dir.glob("*/rskill.yaml")) if rskills_dir.is_dir() else []:
        try:
            manifest = RSkillManifest.from_yaml(str(path))
        except Exception:  # noqa: BLE001  # reason: a broken sibling manifest must not blank the registry
            continue
        tags = set(manifest.embodiment_tags)
        matched = tags & robot_tags
        if not (matched or "any" in tags):
            continue
        resolved.append(
            {
                "rskill_id": manifest.name,
                "version": manifest.version,
                "kind": manifest.kind,
                "role": manifest.role,
                "matched_tags": sorted(matched) if matched else ["any"],
            }
        )

    return {
        "robot_id": robot_yaml.parent.name,
        "embodiment_kind": robot.embodiment_kind,
        "embodiment_tags": sorted(robot_tags),
        "supported_control_modes": sorted(
            m.value for m in robot.capabilities.supported_control_modes
        ),
        "resolved_rskills": sorted(resolved, key=lambda r: r["rskill_id"]),
    }
