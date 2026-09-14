"""`run_manifest.yaml`'s content model — the generic, task-agnostic run header.

Mirrors `openral_ext.mission_verifier.schemas`'s pattern (item 7): a small
Pydantic model, no mission-specific fields, JSON/YAML-serialisable.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["RunManifest"]


class RunManifest(BaseModel):
    """The §19 `run_manifest.yaml` header — what was run, when, how.

    Attributes:
        run_id: `<UTC timestamp>-<robot_id>`, also the directory name under
            `experiments/manifests/`.
        started_at: ISO-8601 UTC.
        ended_at: ISO-8601 UTC; `None` until `RunManifestWriter` finalizes.
        exit_code: `openral deploy sim`'s process exit code; `None` until
            finalized (or if the writer was torn down without ever waiting
            on the process — still `None`, not a fabricated `0`).
        command: The exact subprocess argv (post `bash -c` wrapping),
            for exact reproduction.
        cwd: Working directory the command ran from (the `openral`
            submodule root).
        robot_id: From the deploy scene's `robot_id`, when the scene
            declares one.
        scene_config_path: Path to the `--config` scene YAML, relative to
            `cwd`.
        seed: The deploy scene's `seed` field (`DeployScene.seed`,
            defaults to 0 upstream).
        dashboard_port: The OTel dashboard port this run's traces were
            queried from, when trace export succeeded.
        rosbag_enabled: Whether `ros2 bag record` was started alongside.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: str
    ended_at: str | None = None
    exit_code: int | None = None
    command: list[str]
    cwd: str
    robot_id: str | None = None
    scene_config_path: str
    seed: int = 0
    dashboard_port: int | None = None
    rosbag_enabled: bool = False
    method: str = Field(
        default="generic_openral",
        description=(
            "The only real condition today — Phase B2 has no baseline-comparison "
            "axis yet (execution_plan.md §21 items 5-6, PLEXIL/EUROPA, not "
            "started). `method_config.yaml` is written with this same value; "
            "there is nothing else real to put in a fuller method_config yet."
        ),
    )
