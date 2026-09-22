"""Artifact-delta summarizer between two freeze tags -- execution_plan.md §14.4
"Mission-specific artifact delta". Groups `git diff --stat`'s file list by artifact
type per `openral_ext.run_manifest.freeze.METHOD_ARTIFACTS`'s own path patterns, so a
method's frozen-artifact set and its delta report agree on what counts as what.

Records only what §14.4 asks for: files added/modified, artifact types changed, line
delta as *supplemental* descriptive data (never a cross-language complexity claim --
"Do not compare raw line counts across PLEXIL/NDDL/Python as a universal complexity
metric"). It does not count semantic constructs, validation iterations, or modeling
errors -- those need engineer judgment §14.4 does not ask a script to automate.
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from openral_ext.run_manifest.freeze import METHOD_ARTIFACTS

__all__ = ["ArtifactDelta", "artifact_delta"]


@dataclass
class ArtifactDelta:
    method: str
    from_tag: str
    to_tag: str
    by_type: dict[str, list[str]] = field(default_factory=dict)  # artifact-type label -> changed paths
    other_files: list[str] = field(default_factory=list)  # changed under repo, but outside this method's artifact set
    insertions: int = 0
    deletions: int = 0


def _artifact_type(path: str, patterns: list[str]) -> str | None:
    """Which of `METHOD_ARTIFACTS[method]`'s glob patterns `path` matches, or `None`."""
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern) or path == pattern:
            return pattern
    return None


def artifact_delta(method: str, from_tag: str, to_tag: str, repo_root: Path) -> ArtifactDelta:
    if method not in METHOD_ARTIFACTS:
        msg = f"unknown method {method!r}; choices: {sorted(METHOD_ARTIFACTS)}"
        raise ValueError(msg)
    patterns = METHOD_ARTIFACTS[method]
    out = subprocess.run(  # noqa: S603  # reason: fixed argv, no shell, trusted local git
        ["git", "diff", "--numstat", f"{from_tag}..{to_tag}"],  # noqa: S607  # reason: git on PATH, dev host
        cwd=repo_root, capture_output=True, text=True, check=True, timeout=15,
    ).stdout

    delta = ArtifactDelta(method=method, from_tag=from_tag, to_tag=to_tag)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:  # noqa: PLR2004  # reason: git numstat's fixed column count (added, deleted, path)
            continue
        added, deleted, path = parts
        artifact_type = _artifact_type(path, patterns)
        if artifact_type is None:
            delta.other_files.append(path)
            continue
        delta.by_type.setdefault(artifact_type, []).append(path)
        delta.insertions += int(added) if added.isdigit() else 0
        delta.deletions += int(deleted) if deleted.isdigit() else 0
    return delta


def format_markdown(delta: ArtifactDelta) -> str:
    lines = [f"# Artifact delta: {delta.method} {delta.from_tag}..{delta.to_tag}", "",
              f"+{delta.insertions} -{delta.deletions} lines across {sum(len(v) for v in delta.by_type.values())} artifact file(s) "
              "(supplemental only -- not a cross-method complexity comparison, §14.4)", ""]
    for artifact_type, paths in sorted(delta.by_type.items()):
        lines.append(f"## {artifact_type} ({len(paths)} file(s))")
        lines.extend(f"- {p}" for p in paths)
        lines.append("")
    if delta.other_files:
        lines.append(f"## Changed outside this method's frozen artifact set ({len(delta.other_files)} file(s), not counted above)")
        lines.extend(f"- {p}" for p in delta.other_files)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", required=True, choices=sorted(METHOD_ARTIFACTS))
    ap.add_argument("--from-tag", required=True)
    ap.add_argument("--to-tag", required=True)
    ap.add_argument("--repo-root", type=Path, default=Path("."))
    args = ap.parse_args()
    print(format_markdown(artifact_delta(args.method, args.from_tag, args.to_tag, args.repo_root)))


if __name__ == "__main__":
    main()
