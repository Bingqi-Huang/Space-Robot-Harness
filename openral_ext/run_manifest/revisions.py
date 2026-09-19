"""Exact submodule commits for `openral_revision.txt` / `srb_revision.txt`.

`docs/upstream_pins.md` has tracked these by hand after every merge; this
makes it automatic per-run instead. Reads the superproject's recorded
gitlink (`git ls-tree HEAD -- <submodule>`) rather than requiring the
submodule to be checked out in the caller's worktree — a run-manifest
writer running from an isolated worktree must not assume the submodule
is populated there.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["submodule_revisions", "research_repo_revision", "baseline_revision"]


def submodule_revisions(repo_root: Path) -> dict[str, str | None]:
    """Return `{"openral": <sha>, "space_robotics_bench": <sha>}`.

    A value is `None` (not a fabricated placeholder) when the superproject's
    git metadata is unavailable at all (e.g. `repo_root` is not a git
    checkout) — callers must write that absence honestly, not guess.

    Args:
        repo_root: The outer research repo's root (holds `.gitmodules`).
    """
    revisions: dict[str, str | None] = {"openral": None, "space_robotics_bench": None}
    for name in revisions:
        try:
            out = subprocess.run(  # noqa: S603  # reason: fixed argv, no shell, trusted local git
                ["git", "ls-tree", "HEAD", "--", name],  # noqa: S607  # reason: git on PATH, dev host
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            continue
        # A gitlink line: "160000 commit <sha>\t<path>"
        line = out.stdout.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) >= 3 and fields[1] == "commit":  # noqa: PLR2004  # reason: git ls-tree's fixed column count
            revisions[name] = fields[2]
    return revisions


def research_repo_revision(repo_root: Path) -> str | None:
    """This outer repo's own HEAD commit -- `None` (not fabricated) off a non-git `repo_root`."""
    try:
        out = subprocess.run(  # noqa: S603  # reason: fixed argv, no shell, trusted local git
            ["git", "rev-parse", "HEAD"],  # noqa: S607  # reason: git on PATH, dev host
            cwd=repo_root, capture_output=True, text=True, check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return out.stdout.strip() or None


def baseline_revision(home: Path | None) -> str | None:
    """`git -C <home> rev-parse HEAD` for a baseline built outside this repo (PLEXIL_HOME,
    EUROPA_HOME -- neither is a submodule). `None` when `home` is unset, missing, or not a git
    checkout -- best-effort, never fabricated."""
    if home is None or not home.is_dir():
        return None
    try:
        out = subprocess.run(  # noqa: S603  # reason: fixed argv, no shell, trusted local git
            ["git", "rev-parse", "HEAD"],  # noqa: S607  # reason: git on PATH, dev host
            cwd=home, capture_output=True, text=True, check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return out.stdout.strip() or None
