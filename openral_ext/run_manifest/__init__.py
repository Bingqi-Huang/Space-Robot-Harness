"""Run-manifest writer — execution_plan.md item 8 / §19.

Wraps `openral deploy sim` and produces the §19 run directory
(`run_manifest.yaml`, `mission_config.yaml`, `capability_registry.json`,
`openral_revision.txt`, `srb_revision.txt`, `events.jsonl`, `traces/`,
`metrics.json`, optional `rosbag/`) without reimplementing any of
`deploy_sim.py`'s launch orchestration — see `writer.RunManifestWriter`.
"""

from __future__ import annotations

from openral_ext.run_manifest.writer import RunManifestWriter

__all__ = ["RunManifestWriter"]
