"""Freeze audit (checklist F2; execution_plan §13.1, docs/freeze_audit.md), as a Markdown report for a human to read.

(a) Ours' artifacts (`openral_ext.run_manifest.freeze.METHOD_ARTIFACTS["ours"]`, and the starting point's own list);
(b) their diff against step 10's starting point; (c) for each hunk, the findings (F116 on) that name its file and a
code word of the hunk, beside the commits that wrote its lines -- hunks no finding names are printed in full;
(d) every line of the artifacts that carries a word of a held-out situation (docs/heldout_design.md §14);
(e) the files the baselines' traceability tables name (docs/baselines/{plexil,europa}.md "Built to the lock"): present,
and what changed since the lock, with any table row that still states a value the change removed.
Git diffs and revisions only; the report decides nothing.

    python3 -m evaluation.freeze_audit [--out artifacts/eval/freeze_audit/<date>.md]
"""
from __future__ import annotations

import argparse
import ast
import datetime
import fnmatch
import re
import subprocess
from pathlib import Path

from openral_ext.run_manifest.freeze import METHOD_ARTIFACTS

REPO = Path(__file__).resolve().parents[1]
# Step 10's starting point, the state F116 audited: the research repo's HEAD when step10_r1 was launched (2026-09-24
# 23:24 +0800), the research_repo_revision of all six of its run manifests. Ours' artifacts there equal af1600d's, the
# commit F116 was recorded in (8361741 only queued the jobs).
START = "8361741"
FIRST_F = 116  # findings written from the starting point on: the only ones that can record a change made after it
# The baselines as built to the lock: the merge of feat/baseline-lock-build (2026-09-24), which brought the plans, the
# domain and the "Built to the lock" sections with their traceability tables to main.
LOCK = "1b6a40f"
BASELINE_DOCS = ["docs/baselines/plexil.md", "docs/baselines/europa.md"]
# Changed files outside the artifact list that still shape what Ours' reasoner reads or does (listed, not audited).
NEAR_ARTIFACTS = ["space_runtime", "configs", "prompts", "space_context", "experiments/operator_console"]
# Words of a held-out situation or its solution (docs/heldout_design.md §14's six held-out instances; §4 for what each
# scenario does). Every hit is printed: the generic guard rule names energized equipment and the contracts the site's
# units, so a hit is for the reader to judge.
HELDOUT_WORDS = {
    "any held-out case": [r"held[-_ ]?out", r"heldout_\w+"],
    "L2-A radiator shutter drawn (PDU-1, BESS)": [r"radiator", r"shutter", r"\bcover(s|ed)?\b", r"hvac", r"condenser",
                                                  r"overtemp", r"over-?temperature", r"\bblue\b"],
    "L2-B habitat stand occupied (consumables container -> habitat)": [r"occup\w*", r"return[-_ ]container",
                                                                       r"outbound", r"rtn-?\d+", r"consumables",
                                                                       r"habitat"],
    "L3 module fails self-test / filter clogged (BESS, ISRU)": [r"self[-_ ]?test", r"clog\w*", r"filter", r"cartridge",
                                                               r"bat_spare", r"slot_0", r"remove[- ]and[- ]replace",
                                                               r"\bspares?\b"],
    "L4 cannibalize (PDU-3's ORU -> PDU-1)": [r"cannibali[sz]\w*", r"donor", r"oru-?0258", r"transfer",
                                              r"energi[sz]ed", r"loss of signal"],
    "held-out faulted units": [r"\bpdu[-_ ]?[13]\b", r"\bbess\b", r"\bisru\b"],
}
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TOKEN = re.compile(r"\d+\.\d+|\w{3,}")  # a value or a name in a plan line or a table row
PATH = re.compile(r"[\w./-]+\.(?:py|md|yaml|json|ple|plx|nddl)\b|[\w.-]+/[\w./-]*")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def ours_paths(rev: str, patterns: list[str]) -> list[str]:
    return [p for p in git("ls-tree", "-r", "--name-only", rev).splitlines() if any(fnmatch.fnmatch(p, g) for g in patterns)]


def patterns_at(rev: str) -> list[str]:
    """`METHOD_ARTIFACTS["ours"]` as freeze.py stated it at `rev`."""
    tree = ast.parse(git("show", f"{rev}:openral_ext/run_manifest/freeze.py"))
    node = next(n for n in tree.body if isinstance(n, ast.AnnAssign) and n.target.id == "METHOD_ARTIFACTS")
    return ast.literal_eval(node.value)["ours"]


def findings() -> dict[int, str]:
    parts = re.split(r"^## F(\d+)\b", (REPO / "docs/research_findings.md").read_text(), flags=re.M)
    return {int(n): body for n, body in zip(parts[1::2], parts[2::2]) if int(n) >= FIRST_F}


def code_words(text: str) -> set[str]:
    """The identifiers an entry writes as code: inside backticks (paths left out), or joined by underscores."""
    ticked = PATH.sub(" ", " ".join(re.findall(r"`([^`]+)`", text)))
    return {w for w in WORD.findall(ticked) if len(w) >= 4} | {w for w in WORD.findall(text) if "_" in w.strip("_")}


def names_file(text: str, path: str) -> bool:
    folder, name = path.rsplit("/", 1)
    return name in text or re.search(re.escape(folder) + r"/(?![\w.-])", text) is not None


def parse_diff(diff: str) -> list[dict]:
    """`git diff` output -> [{path, status, hunks: [{header, lines, new_start, new_len}]}]."""
    files = []
    for block in re.split(r"^diff --git .*\n", diff, flags=re.M)[1:]:
        head, _, body = block.partition("\n@@")
        old = re.search(r"^--- (?:a/(.*)|/dev/null)$", head, flags=re.M)
        new = re.search(r"^\+\+\+ (?:b/(.*)|/dev/null)$", head, flags=re.M)
        status = "A" if "new file mode" in head else "D" if "deleted file mode" in head else "R" if "rename from" in head else "M"
        path = (new and new.group(1)) or (old and old.group(1)) or re.search(r"^rename to (.*)$", head, flags=re.M).group(1)
        hunks = []
        for h in re.split(r"^(?=@@ )", "@@" + body, flags=re.M)[1:] if body else []:
            header, _, rest = h.partition("\n")
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", header)
            hunks.append({"header": header, "lines": rest.rstrip("\n").splitlines(), "new_start": int(m.group(1)),
                          "new_len": int(m.group(2) if m.group(2) is not None else 1)})
        files.append({"path": path, "status": status, "hunks": hunks})
    return files


def commits_of(path: str, hunk: dict) -> list[str]:
    """The commits that wrote the hunk's lines at HEAD (git blame), each with the F-numbers its subject names."""
    if hunk["new_len"] == 0:
        return []
    blame = git("blame", "-s", "-l", "-L", f"{hunk['new_start']},+{hunk['new_len']}", "HEAD", "--", path)
    shas = dict.fromkeys(line.split()[0].lstrip("^") for line in blame.splitlines())
    out = []
    for sha in shas:
        if _is_ancestor(sha, START):
            continue  # an unchanged context line older than the starting point
        refs = re.findall(r"F\d+", git("log", "-1", "--format=%s", sha))
        out.append(f"{sha[:7]} ({', '.join(refs) or 'no F in subject'})")
    return out


def _is_ancestor(sha: str, rev: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, rev], cwd=REPO).returncode == 0  # noqa: S603, S607


def ours_section(entries: dict[int, str]) -> list[str]:
    start_patterns, patterns = patterns_at(START), METHOD_ARTIFACTS["ours"]
    now, then = ours_paths("HEAD", patterns), ours_paths(START, start_patterns)
    out = ["## (a) Ours' artifacts", "",
           f"`METHOD_ARTIFACTS[\"ours\"]` at HEAD: {', '.join(f'`{p}`' for p in patterns)}.", "",
           f"At the starting point `{START}` freeze.py listed: {', '.join(f'`{p}`' for p in start_patterns)}.", ""]
    out += [f"- `{p}`" + ("" if p in then else " (not in the starting point's list)") for p in now]
    out += [f"- `{p}` -- in the starting point's list, gone at HEAD" for p in then if p not in now]
    dirty = git("status", "--porcelain", "--", *now).splitlines()
    out += ["", "Uncommitted changes under these paths: " + (", ".join(f"`{d}`" for d in dirty) or "none"), ""]

    # one line of context: the reorganizations (F124) would otherwise merge every earlier change into one hunk
    files = parse_diff(git("diff", "-M", "-U1", "--no-color", START, "HEAD", "--", *sorted(set(now) | set(then))))
    out += [f"## (b, c) Changes since the starting point `{START}` (HEAD `{git('rev-parse', '--short', 'HEAD').strip()}`)", "",
            f"Per hunk: the findings (F{FIRST_F} on) that name the file and share a code word with the hunk's changed "
            "lines (the shared words in brackets); `file only` = a finding names the file but none of the hunk's code "
            "words; the commits that wrote the hunk's lines (git blame at HEAD) with the F-numbers of their subjects. "
            "Hunks no finding names, and hunks matched by file only, are printed in full below the table.", "",
            "| file | hunk | findings | commits |", "|---|---|---|---|"]
    unrecorded = []
    for f in files:
        whole = f["status"] in ("A", "D")
        for h in f["hunks"]:
            changed = [ln[1:] for ln in h["lines"] if ln[:1] in "+-"]
            words = {w for w in WORD.findall(" ".join(changed) + " " + h["header"].split("@@")[-1]) if len(w) >= 4}
            named = {n: sorted(words & code_words(t)) for n, t in entries.items() if names_file(t, f["path"])}
            matched = {n: w for n, w in named.items() if w or whole}
            file_only = sorted(set(named) - set(matched))
            label = "; ".join([*(f"F{n}" + (f" ({', '.join(w[:4])})" if w else " (whole file)") for n, w in sorted(matched.items())),
                               *(["file only: " + ", ".join(f"F{n}" for n in file_only)] if file_only else [])]) or "**none**"
            hunk_id = h["header"].split("@@")[1].strip()
            plus, minus = sum(ln[:1] == "+" for ln in h["lines"]), sum(ln[:1] == "-" for ln in h["lines"])
            out.append(f"| `{f['path']}` ({f['status']}) | `{hunk_id}` +{plus} -{minus} | {label} | "
                       f"{', '.join(commits_of(f['path'], h)) or '--'} |")
            if not matched:
                unrecorded.append((f["path"], label, h))
    out += ["", f"### Hunks no finding records by a shared code word ({len(unrecorded)})", ""]
    for path, label, h in unrecorded:
        out += [f"`{path}` -- {label}", "", "```diff", h["header"], *h["lines"], "```", ""]

    near = git("diff", "--name-status", "-M", START, "HEAD", "--", *NEAR_ARTIFACTS).splitlines()
    near = [ln for ln in near if ln.split("\t")[-1] not in set(now) | set(then)]
    out += ["## Changed since the starting point, outside the artifact list", "",
            "Not frozen as Ours' artifacts; listed because the reasoner's text or loop reads them.", ""]
    for ln in near:
        path = ln.split("\t")[-1]
        subjects = git("log", "--format=%h %s", f"{START}..HEAD", "--", path).splitlines()
        out.append(f"- `{ln.split(chr(9))[0]}` `{path}`: " + "; ".join(subjects))
    return out + [""]


def heldout_section(paths: list[str]) -> list[str]:
    out = ["## (d) Held-out words in Ours' artifacts (HEAD)", "",
           "Word list from docs/heldout_design.md §14 (scenario names, faulted units, cargo and destination, the fix "
           "sequences' nouns). Every hit, for a human to read; a hit is not a verdict.", ""]
    lines = {p: git("show", f"HEAD:{p}").splitlines() for p in paths}
    for case, words in HELDOUT_WORDS.items():
        out += [f"### {case}", ""]
        for w in words:
            hits = [f"  - `{p}:{i}` {ln.strip()[:220]}" for p, text in lines.items()
                    for i, ln in enumerate(text, 1) if re.search(w, ln, flags=re.I)]
            out += [f"- `{w}`: {len(hits)}", *hits]
        out.append("")
    return out


def traced_files(doc: str, tracked: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """{name a traceability table cites -> tracked files it resolves to}, and the tables' rows."""
    text = (REPO / doc).read_text().split("## Built to the lock", 1)[1]
    names, rows = {}, []
    for section in re.split(r"^### ", text, flags=re.M)[1:]:
        heading, _, body = section.partition("\n")
        if not heading.startswith("Traceability"):
            continue
        rows += [ln for ln in body.splitlines() if ln.startswith("|") and not ln.startswith("|---")]
        for name in re.findall(r"`([^`]+)`", heading) + [n for n in re.findall(r"`([^`]+)`", body) if n.startswith("baselines/")]:
            files = [f for f in tracked if name in f]
            names[name] = list(dict.fromkeys(files + [f[:-4] + ".plx" for f in files if f.endswith(".ple") and f[:-4] + ".plx" in tracked]))
    return names, rows


def baselines_section() -> list[str]:
    tracked = git("ls-files", "baselines").splitlines()
    out = [f"## (e) Baselines against the lock `{LOCK}`", "",
           "Files the traceability tables cite (docs/baselines/{plexil,europa}.md, \"Built to the lock\"; a .ple brings "
           "its compiled .plx), whether they exist at HEAD, and what changed since the lock with the commits that "
           "changed it. A table row is quoted when it states a value that the change removed and did not add back.", ""]
    named_all = set()
    for doc in BASELINE_DOCS:
        names, rows = traced_files(doc, tracked)
        out += [f"### {doc}", ""]
        for name, files in names.items():
            out.append(f"- `{name}` -> " + (", ".join(f"`{f}`" for f in files) or "**no tracked file**"))
        for f in sorted({f for files in names.values() for f in files}):
            named_all.add(f)
            log = git("log", "--format=%h %s", f"{LOCK}..HEAD", "--", f).splitlines()
            if not log:
                out.append(f"- `{f}`: unchanged since the lock")
                continue
            out.append(f"- `{f}`: changed by " + "; ".join(log))
            if f.endswith(".plx"):  # compiled from the .ple beside it; plexilc writes the source path it compiled from
                same = [re.sub(r' FileName="[^"]*"', "", git("show", f"{rev}:{f}")) for rev in (LOCK, "HEAD")]
                out[-1] += " -- only the compiler's FileName attribute" if same[0] == same[1] else " -- the plan itself"
                continue
            diff = git("diff", "--no-color", LOCK, "HEAD", "--", f)
            out += ["", "```diff", *[ln for ln in diff.splitlines() if ln[:1] in "@+-" and not ln.startswith(("+++", "---"))], "```", ""]
            lines = diff.splitlines()
            gone = ({t for ln in lines if ln.startswith("-") and not ln.startswith("---") for t in TOKEN.findall(ln)}
                    - {t for ln in lines if ln.startswith("+") and not ln.startswith("+++") for t in TOKEN.findall(ln)})
            out += [f"  - table row stating a removed value ({', '.join(sorted(gone & set(TOKEN.findall(r))))}): {r}"
                    for r in rows if gone & set(TOKEN.findall(r))]
        out.append("")
    rest = [f for m in ("plexil", "europa_plexil") for f in tracked if any(fnmatch.fnmatch(f, g) for g in METHOD_ARTIFACTS[m])
            and f not in named_all]
    out += ["### Frozen baseline files no table cites", ""]
    for f in sorted(set(rest)):
        log = git("log", "--format=%h %s", f"{LOCK}..HEAD", "--", f).splitlines()
        out.append(f"- `{f}`: " + ("changed by " + "; ".join(log) if log else "unchanged since the lock"))
    return out + [""]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / f"artifacts/eval/freeze_audit/{datetime.date.today()}.md")
    args = ap.parse_args()
    head = git("log", "-1", "--format=%h %ad %s", "--date=iso").strip()
    report = [f"# Freeze audit {datetime.date.today()}", "", f"HEAD: `{head}`; starting point `{START}`; baseline lock `{LOCK}`.", ""]
    report += ours_section(findings())
    report += heldout_section(ours_paths("HEAD", METHOD_ARTIFACTS["ours"]))
    report += baselines_section()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(report) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
