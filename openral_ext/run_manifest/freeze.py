"""Pre-campaign artifact freeze -- execution_plan.md §13.1 steps 5-6.

Step 5 names, per method, exactly which artifacts get frozen:
  Ours:           generic capability contracts, generic prompts/playbooks, hard
                   invariant/authority configuration, effect-verifier mappings.
  PLEXIL:         plan libraries.
  EUROPA→PLEXIL:  domain/solver configuration.
Step 6: "freeze all method-specific artifacts by recording and tagging their git commits."

`list_method_artifacts` is the first half (what gets frozen). `plan_freeze` is the
second half, dry-run by default: it reports the tag(s) it WOULD create and never
calls `git tag` unless `dry_run=False` is passed explicitly -- no tag has been
created by this module; freezing is a user decision, not something to run now.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = ["METHOD_ARTIFACTS", "list_method_artifacts", "plan_freeze", "FreezeTagPlan"]

# Paths are relative to repo_root; a bare filename glob matches only that file.
METHOD_ARTIFACTS: dict[str, list[str]] = {
    "ours": [
        "prompts/ours/*",  # every text the reasoner reads: standing text, step template, local tool texts
        "space_runtime/context.py",  # fills them from the record
        "configs/space_runtime.yaml",  # hard invariant/authority guard configuration
        "space_runtime/guard.py",  # the guard mechanism itself
        "space_runtime/verification.py",  # effect-verifier mapping
        "space_runtime/facts.py",  # what the record keeps of each event (the fields the step text shows)
        "space_runtime/tools.py",  # renders the contracts + prompts/ours/tools.yaml into the tool schemas
        "openral_ext/capability_server/contracts.yaml",  # generic capability contracts (shared boundary, but
        # this is the artifact PLEXIL/EUROPA also read through the same file -- listed once, not duplicated below)
    ],
    "plexil": [
        "baselines/plexil/plans/*.ple",
        "baselines/plexil/plans/*.plx",
        "baselines/plexil/plans/lib/*.ple",  # the library both missions call (docs/baselines/plexil.md traceability)
        "baselines/plexil/plans/lib/*.plx",
        "baselines/plexil/interface-config.xml",
        "baselines/item_descriptions.json",  # the item table both baselines read (named in interface-config.xml)
    ],
    "europa_plexil": [
        "baselines/europa/**",
        "baselines/item_descriptions.json",
    ],
}


def list_method_artifacts(method: str, repo_root: Path) -> list[Path]:
    """Every real file matching `METHOD_ARTIFACTS[method]` under `repo_root`, sorted.

    A pattern that matches nothing (e.g. EUROPA today) is silently absent from the
    result -- the caller decides whether an empty list means "not ready to freeze".
    """
    if method not in METHOD_ARTIFACTS:
        msg = f"unknown method {method!r}; choices: {sorted(METHOD_ARTIFACTS)}"
        raise ValueError(msg)
    found: list[Path] = []
    for pattern in METHOD_ARTIFACTS[method]:
        if any(ch in pattern for ch in "*?["):
            found.extend(sorted(repo_root.glob(pattern)))
        else:
            p = repo_root / pattern
            if p.is_file():
                found.append(p)
    return sorted(set(found))


@dataclass
class FreezeTagPlan:
    method: str
    tag_name: str
    head_commit: str | None
    artifacts: list[Path]
    dirty_artifacts: list[Path]  # artifacts with uncommitted changes -- freezing now would tag an untracked state
    would_create: bool  # False if dry_run, or if head_commit is None, or if dirty_artifacts is non-empty


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603  # reason: fixed argv, no shell, trusted local git
            ["git", *args], cwd=repo_root, capture_output=True, text=True, check=True, timeout=10,  # noqa: S607
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return out.stdout.strip()


def plan_freeze(method: str, repo_root: Path, *, tag_prefix: str = "freeze", dry_run: bool = True) -> FreezeTagPlan:
    """List `method`'s artifacts and report the tag this WOULD create. Never runs `git tag`
    when `dry_run=True` (the default, and the only mode exercised so far -- no tag exists yet)."""
    artifacts = list_method_artifacts(method, repo_root)
    head = _git(repo_root, "rev-parse", "HEAD")
    # an empty `--` pathspec means "no restriction" to git (whole-repo status), not "nothing" -- guard it
    status = (_git(repo_root, "status", "--porcelain", "--", *(str(p.relative_to(repo_root)) for p in artifacts))
              if artifacts else "") or ""
    dirty = [repo_root / line[3:] for line in status.splitlines() if line.strip()]
    tag_name = f"{tag_prefix}/{method}/{head[:12]}" if head else f"{tag_prefix}/{method}/unknown"
    would_create = bool(head) and not dirty and not dry_run
    if would_create:
        # Not exercised by this session -- do NOT create tags now (task instruction). Left here so the
        # mechanism is complete, gated behind an explicit, never-yet-passed dry_run=False.
        _git(repo_root, "tag", "-a", tag_name, "-m", f"freeze: {method} artifacts at {head}")
    return FreezeTagPlan(method=method, tag_name=tag_name, head_commit=head, artifacts=artifacts,
                         dirty_artifacts=dirty, would_create=would_create)
