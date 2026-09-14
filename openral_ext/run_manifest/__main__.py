"""CLI: `python -m openral_ext.run_manifest --config <scene.yaml> [--rosbag]`.

Thin argument parsing over `RunManifestWriter` — see that module's
docstring for what this does and does not do. Run from the outer research
repo root (so `openral/` resolves as a sibling); pass `--openral-root` /
`--repo-root` to override.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openral_ext.run_manifest.writer import RunManifestWriter


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Scene YAML, relative to --openral-root.")
    parser.add_argument("--openral-root", type=Path, default=Path("openral"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--manifests-dir", type=Path, default=None)
    parser.add_argument("--ros-domain-id", type=str, default=None)
    parser.add_argument("--discovery-range", type=str, default=None)
    parser.add_argument("--dashboard-port", type=int, default=4318)
    parser.add_argument("--rosbag", action="store_true")
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=None,
        help="Give up waiting on `openral deploy sim` after this long (still finalizes).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    with RunManifestWriter(
        config=args.config,
        openral_root=args.openral_root,
        repo_root=args.repo_root,
        manifests_dir=args.manifests_dir,
        ros_domain_id=args.ros_domain_id,
        discovery_range=args.discovery_range,
        dashboard_port=args.dashboard_port,
        rosbag=args.rosbag,
    ) as run:
        print(f"run_manifest: writing to {run.run_dir}", file=sys.stderr)
        exit_code = run.wait(timeout=args.timeout_s)
    return exit_code if exit_code is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
