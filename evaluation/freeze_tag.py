"""Freeze tag (checklist F3; execution_plan §13.1 step 6, §19): what the campaign runs, in one manifest, and the git
tag that names it in all three repos.

Recorded: HEAD of the research repo, openral/ and space_robotics_bench/, each with its uncommitted paths; the run-farm
image (`docker image inspect runfarm:22.04`); the packages of openral/.venv as the run farm's interpreter sees them
(the venv's own Python version, pyvenv.cfg); each method's frozen artifacts (`METHOD_ARTIFACTS`); the reasoner's model
and call configuration (configs/space_runtime.yaml `reasoner`) and the VLMs' (the capability server's scene VLM,
openral's pick and press skills), with the arguments each model request sends, read from the calling code.

Dry run by default: prints the manifest and writes artifacts/freeze/<tag>.dry_run.yaml, creates nothing.
`--tag` writes artifacts/freeze/<tag>.yaml and creates the annotated tag <tag> in all three repos -- refused when any
of them has an uncommitted change.

    python3 -m evaluation.freeze_tag <tag> [--tag]
"""
from __future__ import annotations

import argparse
import ast
import datetime
import json
import subprocess
import sys
from pathlib import Path

import yaml

from openral_ext.run_manifest.freeze import METHOD_ARTIFACTS, list_method_artifacts

REPO = Path(__file__).resolve().parents[1]
REPOS = {"research": REPO, "openral": REPO / "openral", "space_robotics_bench": REPO / "space_robotics_bench"}
IMAGE = "runfarm:22.04"
VENV = REPO / "openral/.venv"
# where each model is called: Ours' reasoner, the capability server's scene VLM (every method), pick/press's VLM
CALLERS = ["space_runtime/tools.py", "openral_ext/capability_server/node.py",
           "openral/python/rskill/src/openral_rskill/grasp_perception.py"]
SKILLS = ["openral/rskills/rskill-procedural-pick/rskill.yaml", "openral/rskills/rskill-procedural-press/rskill.yaml"]


def run(*argv: str, cwd: Path = REPO) -> str:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=True).stdout  # noqa: S603


def repo_state(path: Path) -> dict:
    return {"head": run("git", "rev-parse", "HEAD", cwd=path).strip(),
            "branch": run("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=path).strip(),
            "uncommitted": run("git", "status", "--porcelain", cwd=path).splitlines()}


def image() -> dict:
    info = json.loads(run("docker", "image", "inspect", IMAGE))[0]
    return {"name": IMAGE, "id": info["Id"], "repo_digests": info["RepoDigests"], "created": info["Created"]}


def venv_packages() -> dict:
    """`uv pip freeze` over the venv's own site-packages: the host's python3 is not the venv's (3.10, the image's)."""
    version = dict(ln.split(" = ") for ln in (VENV / "pyvenv.cfg").read_text().splitlines())["version_info"]
    site = VENV / f"lib/python{'.'.join(version.split('.')[:2])}/site-packages"
    return {"python": version, "site_packages": str(site.relative_to(REPO)),
            "packages": run("uv", "pip", "freeze", "--color", "never", "--target", str(site)).splitlines()}


def _arg(k: ast.keyword) -> str:
    return f"**{ast.unparse(k.value)}" if k.arg is None else k.arg + (f"={k.value.value!r}" if isinstance(k.value, ast.Constant) else "")


def requests_in(path: str) -> list[list[str]]:
    """The arguments of every model client and request in a source file: each `OpenAI(...)` and
    `...completions.create(...)` call's keywords (a literal value with it), and the keys of each dict assigned to `body`
    (a request posted by hand). A sampling parameter, if any were sent, would appear here."""
    out = []
    for n in ast.walk(ast.parse((REPO / path).read_text())):
        if isinstance(n, ast.Call) and ast.unparse(n.func).endswith(("completions.create", "OpenAI")):
            out.append([ast.unparse(n.func).rsplit(".", 1)[-1] + ":", *(_arg(k) for k in n.keywords)])
        if isinstance(n, ast.Assign) and [ast.unparse(t) for t in n.targets] == ["body"] and isinstance(n.value, ast.Dict):
            out.append(["body:", *(k.value for k in n.value.keys)])
    return [list(r) for r in dict.fromkeys(tuple(r) for r in out)]


def constants(path: str, names: set[str]) -> dict:
    """Module-level assignments of `names` in a source file, as written (e.g. an environment default)."""
    tree = ast.parse((REPO / path).read_text())
    return {n.targets[0].id: ast.unparse(n.value) for n in tree.body
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names}


def models() -> dict:
    skills = {Path(p).parent.name: {k: v for k, v in json.loads(yaml.safe_load((REPO / p).read_text())["procedural"]["default_goal_json"]).items()
                                    if k.startswith("vlm_")} for p in SKILLS}
    return {
        "reasoner": {**yaml.safe_load((REPO / "configs/space_runtime.yaml").read_text())["reasoner"],
                     "requests": requests_in(CALLERS[0])},
        "scene_vlm": {**constants(CALLERS[1], {"VLM_MODEL", "VLM_ENDPOINT"}), "requests": requests_in(CALLERS[1])},
        "skill_vlm": {**skills, **constants("openral/python/rskill/src/openral_rskill/procedural_pick.py", {"VLM_TIMEOUT_S"}),
                      "requests": requests_in(CALLERS[2])},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="the tag, e.g. freeze-1")
    ap.add_argument("--tag", action="store_true", help="write the manifest and create the tags (default: dry run)")
    args = ap.parse_args()
    repos = {k: repo_state(p) for k, p in REPOS.items()}
    tracked = set(run("git", "ls-files").splitlines())
    manifest = {
        "tag": args.name, "dry_run": not args.tag, "recorded_at": datetime.datetime.now().astimezone().isoformat(),
        "repos": repos, "image": image(), "openral_venv": venv_packages(),
        "artifacts": {m: [p for p in (str(f.relative_to(REPO)) for f in list_method_artifacts(m, REPO)) if p in tracked]
                      for m in METHOD_ARTIFACTS},  # committed files only: the europa glob also finds build output
        "models": models(),
    }
    dirty = [k for k, r in repos.items() if r["uncommitted"]]
    out = REPO / "artifacts/freeze" / f"{args.name}{'' if args.tag else '.dry_run'}.yaml"
    if args.tag and dirty:
        print(f"refused: uncommitted changes in {', '.join(dirty)}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(manifest, sort_keys=False, width=120))
    print(out)
    for k, path in REPOS.items():
        if args.tag:
            run("git", "tag", "-a", args.name, "-m", f"freeze {args.name}: artifacts/freeze/{args.name}.yaml", cwd=path)
        print(f"{'tagged' if args.tag else 'would tag'} {k} {repos[k]['head'][:12]} as {args.name}"
              + (f" -- refused at --tag: {len(repos[k]['uncommitted'])} uncommitted path(s)" if repos[k]["uncommitted"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
