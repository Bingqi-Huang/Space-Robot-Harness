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
            "'ours' | 'plexil' | 'europa_plexil' | 'generic_openral' (the last is the "
            "pre-baseline-axis default some callers still pass). §21 items 5-6 (PLEXIL, "
            "EUROPA) build the other two conditions; 'generic_openral' is not a fourth "
            "experimental condition, just this field's old default."
        ),
    )
    # §12/§19: "git commits of frozen mission/domain artifacts" + "PLEXIL/EUROPA/OpenRAL/SRB
    # revisions". openral_revision.txt/srb_revision.txt (already written, see writer.py) cover two
    # of those four; these three fields are the rest. Each is None (never a fabricated value) when
    # that method/repo has no real source yet -- see docstrings.
    research_repo_revision: str | None = Field(
        default=None, description="This outer repo's own HEAD commit -- was missing before; openral/srb had it, this repo did not."
    )
    plexil_revision: str | None = Field(
        default=None,
        description="`git -C <PLEXIL_HOME> rev-parse HEAD`, PLEXIL_HOME from docs/baselines/plexil.md's pin. "
                     "None when PLEXIL_HOME is unset or not a git checkout -- PLEXIL is built outside this "
                     "repo (not a submodule), so this is best-effort, not guaranteed.",
    )
    europa_revision: str | None = Field(
        default=None,
        description="`git -C <EUROPA_HOME> rev-parse HEAD`, EUROPA_HOME from docs/baselines/europa.md's pin "
                     "(build_europa.sh: ~/Programs/europa/dist/europa). Same best-effort caveat as plexil_revision.",
    )
    operator_event_log_path: str | None = Field(
        default=None,
        description="Path (relative to run_dir) to the §13.2 human-interaction event log, when the operator "
                     "console (experiments/operator_console/) was attached to this run.",
    )
