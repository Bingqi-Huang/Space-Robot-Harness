"""`RunManifestWriter` — wraps `openral deploy sim`, produces the §19 run directory.

Does NOT reimplement `deploy_sim.py`'s launch orchestration (3300+ lines of
robot/manifest/feature resolution in `resolve_launch_invocation` /
`run_launch_invocation`) — it shells out to the real `openral deploy sim`
CLI, exactly as a human or `just` recipe would, and observes: writes what
is known before launch, watches the process, and finalizes what is only
knowable after teardown (duration, exit code, OTel traces).

Usage::

    with RunManifestWriter(
        config=Path("scenes/deploy/srb_panel_remount.yaml"),
        openral_root=Path("openral"),
        repo_root=Path("."),
    ) as run:
        run.wait()  # blocks until `openral deploy sim` exits (Ctrl+C, timeout, or the
                    # process's own teardown) and finalizes the run directory

Or attach to a process this script did not start (e.g. a shell-launched
`openral deploy sim` you want to bracket with manifest writing)::

    with RunManifestWriter(..., attach_pid=1234) as run:
        ...
        run.finalize(exit_code=0)  # caller knows when/why it ended
"""

from __future__ import annotations

import contextlib
import datetime
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from openral_ext.run_manifest.capability_registry import resolve_capability_registry
from openral_ext.run_manifest.revisions import submodule_revisions
from openral_ext.run_manifest.schemas import RunManifest

__all__ = ["RunManifestWriter"]

# §19 fields with no real source yet at Phase B2 (no baseline-comparison axis,
# no space_context/network_profile content) — written to `omitted_files.txt`
# instead of being fabricated. See RunManifest.method's docstring for why.
_OMITTED_WITH_REASON = {
    "space_context_ref.yaml": (
        "space_context/ is an empty placeholder — not built until Phase B "
        "observes a real failure calling for it (execution_plan.md §21.6-7)."
    ),
    "network_profile_ref.yaml": (
        "network/ is an empty placeholder — same status as space_context/."
    ),
    "model_config.json": (
        "No reasoner LLM is in the loop yet for this robot (B3, "
        "reasoner-in-the-loop, has not been attempted) — nothing real to "
        "record here yet."
    ),
}


class RunManifestWriter:
    """Creates `experiments/manifests/<run_id>/`, wraps one `openral deploy sim` run."""

    def __init__(
        self,
        *,
        config: Path,
        openral_root: Path,
        repo_root: Path,
        manifests_dir: Path | None = None,
        ros_setup: str = "/opt/ros/humble/setup.bash",
        ros_domain_id: str | None = None,
        discovery_range: str | None = None,
        dashboard_port: int = 4318,
        rosbag: bool = False,
        rosbag_topics: list[str] | None = None,
        extra_deploy_args: list[str] | None = None,
        attach_pid: int | None = None,
    ) -> None:
        """Args mirror `openral deploy sim`'s own knobs; see the module docstring."""
        self._config = config
        self._openral_root = openral_root.resolve()
        self._repo_root = repo_root.resolve()
        self._manifests_dir = (manifests_dir or self._repo_root / "experiments" / "manifests").resolve()
        self._ros_setup = ros_setup
        self._ros_domain_id = ros_domain_id or os.environ.get("ROS_DOMAIN_ID", "")
        self._discovery_range = discovery_range or os.environ.get(
            "ROS_AUTOMATIC_DISCOVERY_RANGE", ""
        )
        self._dashboard_port = dashboard_port
        self._rosbag = rosbag
        self._rosbag_topics = rosbag_topics or [
            "/openral/candidate_action",
            "/openral/safe_action",
            "/openral/safety_status",
            "/space_harness/verifier_events",
            "/tf",
            "/tf_static",
        ]
        self._extra_deploy_args = extra_deploy_args or []
        self._attach_pid = attach_pid

        self.run_id: str
        self.run_dir: Path
        self._manifest: RunManifest
        self._proc: subprocess.Popen[bytes] | None = None
        self._bag_proc: subprocess.Popen[bytes] | None = None
        self._started_monotonic: float

    # ── Context manager ─────────────────────────────────────────────────

    def __enter__(self) -> RunManifestWriter:
        self._start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        exit_code = self._proc.poll() if self._proc is not None else None
        self.finalize(exit_code=exit_code)

    # ── Start: everything knowable before/at launch ────────────────────

    def _start(self) -> None:
        scene = self._load_scene()
        robot_id = scene.get("robot_id")
        seed = int(scene.get("seed", 0))

        started_at = datetime.datetime.now(tz=datetime.timezone.utc)
        self.run_id = f"{started_at.strftime('%Y%m%dT%H%M%SZ')}-{robot_id or 'unknown'}"
        self.run_dir = self._manifests_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        (self.run_dir / "traces").mkdir()

        command = self._build_command()
        self._manifest = RunManifest(
            run_id=self.run_id,
            started_at=started_at.isoformat(),
            command=command,
            cwd=str(self._openral_root),
            robot_id=robot_id,
            scene_config_path=str(self._config),
            seed=seed,
            dashboard_port=self._dashboard_port,
            rosbag_enabled=self._rosbag,
        )
        self._write_yaml("run_manifest.yaml", self._manifest.model_dump())
        self._write_yaml(
            "mission_config.yaml", {"source_path": str(self._config), "scene": scene}
        )
        self._write_yaml(
            "method_config.yaml", {"method": self._manifest.method, "note": RunManifest.model_fields["method"].description}
        )
        self._write_revisions()
        self._write_capability_registry(robot_id)
        self._write_omitted_files_note()

        self._started_monotonic = time.monotonic()
        if self._attach_pid is None:
            self._proc = self._launch()
        if self._rosbag:
            self._bag_proc = self._launch_rosbag()

    def _load_scene(self) -> dict[str, Any]:
        config_path = self._config if self._config.is_absolute() else self._openral_root / self._config
        text = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}

    def _build_command(self) -> list[str]:
        venv_openral = self._openral_root / ".venv" / "bin" / "openral"
        return [
            str(venv_openral),
            "deploy",
            "sim",
            "--config",
            str(self._config),
            *self._extra_deploy_args,
        ]

    def _launch(self) -> subprocess.Popen[bytes]:
        env_lines = [f"source {self._ros_setup}", "source install/setup.bash"]
        if self._ros_domain_id:
            env_lines.append(f"export ROS_DOMAIN_ID={self._ros_domain_id}")
        if self._discovery_range:
            env_lines.append(f"export ROS_AUTOMATIC_DISCOVERY_RANGE={self._discovery_range}")
        cmd = " && ".join([*env_lines, f"exec {' '.join(self._manifest.command)}"])
        return subprocess.Popen(  # noqa: S603  # reason: fixed shell prelude, no user-controlled interpolation beyond a path
            ["bash", "-c", cmd],
            cwd=self._openral_root,
            stdout=(self.run_dir / "deploy_sim.log").open("wb"),  # noqa: SIM115  # reason: lives as long as self._proc
            stderr=subprocess.STDOUT,
        )

    def _launch_rosbag(self) -> subprocess.Popen[bytes]:
        env_lines = [f"source {self._ros_setup}"]
        if self._ros_domain_id:
            env_lines.append(f"export ROS_DOMAIN_ID={self._ros_domain_id}")
        if self._discovery_range:
            env_lines.append(f"export ROS_AUTOMATIC_DISCOVERY_RANGE={self._discovery_range}")
        bag_dir = self.run_dir / "rosbag"
        argv = ["ros2", "bag", "record", "-o", str(bag_dir), *self._rosbag_topics]
        cmd = " && ".join([*env_lines, f"exec {' '.join(argv)}"])
        return subprocess.Popen(  # noqa: S603  # reason: fixed shell prelude
            ["bash", "-c", cmd],
            cwd=self._openral_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _write_revisions(self) -> None:
        revisions = submodule_revisions(self._repo_root)
        (self.run_dir / "openral_revision.txt").write_text(
            (revisions["openral"] or "") + "\n", encoding="utf-8"
        )
        (self.run_dir / "srb_revision.txt").write_text(
            (revisions["space_robotics_bench"] or "") + "\n", encoding="utf-8"
        )

    def _write_capability_registry(self, robot_id: str | None) -> None:
        if not robot_id:
            self._write_json(
                "capability_registry.json",
                {"error": "scene declares no robot_id; nothing to resolve"},
            )
            return
        robot_yaml = self._openral_root / "robots" / robot_id / "robot.yaml"
        try:
            registry = resolve_capability_registry(
                robot_yaml=robot_yaml, rskills_dir=self._openral_root / "rskills"
            )
        except FileNotFoundError as exc:
            registry = {"error": str(exc)}
        self._write_json("capability_registry.json", registry)

    def _write_omitted_files_note(self) -> None:
        lines = [
            f"{name}: {reason}" for name, reason in _OMITTED_WITH_REASON.items()
        ]
        (self.run_dir / "omitted_files.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ── Wait / finalize: everything only knowable after teardown ───────

    def wait(self, timeout: float | None = None) -> int | None:
        """Block until the wrapped `openral deploy sim` process exits, then finalize.

        Returns:
            The process exit code, or `None` if this writer attached to an
            externally-managed PID (nothing to wait on — call `finalize`
            explicitly once the caller knows the run ended).
        """
        if self._proc is None:
            return None
        try:
            exit_code = self._proc.wait(timeout=timeout)
        except KeyboardInterrupt:
            self._proc.send_signal(2)  # SIGINT — graceful teardown, matches this project's own convention
            exit_code = self._proc.wait(timeout=60)
        self.finalize(exit_code=exit_code)
        return exit_code

    def finalize(self, *, exit_code: int | None) -> None:
        """Write everything only knowable after the run ended. Idempotent."""
        if self._bag_proc is not None and self._bag_proc.poll() is None:
            self._bag_proc.send_signal(2)
            with contextlib.suppress(subprocess.TimeoutExpired):
                self._bag_proc.wait(timeout=30)

        duration_s = time.monotonic() - self._started_monotonic
        trace_count = self._write_traces_and_events()

        self._manifest.ended_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        self._manifest.exit_code = exit_code
        self._write_yaml("run_manifest.yaml", self._manifest.model_dump())
        self._write_json(
            "metrics.json",
            {
                "duration_s": round(duration_s, 3),
                "exit_code": exit_code,
                "trace_count": trace_count,
                "rosbag_enabled": self._rosbag,
            },
        )

    def _write_traces_and_events(self) -> int:
        """Pull every trace from the dashboard's `/api/traces` while it's still up.

        Real OTel spans (`DashboardTraceClient`, the same read-only client
        the dashboard's own correlator uses) — not fabricated. If the
        dashboard is unreachable (already torn down, never came up), writes
        an honestly-empty `events.jsonl` with a one-line reason, not fake data.
        """
        from openral_observability.replay.trace_query import (
            DashboardTraceClient,
            TraceQueryError,
        )

        events_path = self.run_dir / "events.jsonl"
        client = DashboardTraceClient(base_url=f"http://127.0.0.1:{self._dashboard_port}")
        try:
            traces = client.list_traces()
        except TraceQueryError as exc:
            events_path.write_text(f"# dashboard unreachable, no events captured: {exc}\n", encoding="utf-8")
            return 0

        with events_path.open("w", encoding="utf-8") as events_f:
            for trace in traces:
                trace_id = trace.get("trace_id")
                if not isinstance(trace_id, str):
                    continue
                spans = client.get_spans(trace_id)
                (self.run_dir / "traces" / f"{trace_id}.json").write_text(
                    json.dumps(spans, indent=2), encoding="utf-8"
                )
                for span in spans:
                    events_f.write(json.dumps({"trace_id": trace_id, **span}) + "\n")
        return len(traces)

    # ── Small YAML/JSON helpers ─────────────────────────────────────────

    def _write_yaml(self, name: str, data: dict[str, Any]) -> None:
        (self.run_dir / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def _write_json(self, name: str, data: dict[str, Any]) -> None:
        (self.run_dir / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
