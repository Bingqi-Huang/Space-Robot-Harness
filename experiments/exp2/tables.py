"""Experiment II's tables from the raw records (research_findings F146; execution_plan §14.4; research_content §5.6).

    python3 experiments/exp2/tables.py   ->   artifacts/eval/exp2/tables.md

1. Engineering, per method: active time from the worklog (`evaluation/engineering_worklog.py`), the part of it spent
   waiting on the method's own validation runs (their queue.log start/end), the rest; pauses; notes (validation
   failures and modeling errors the engineer recorded); validation runs to the first G3 PASS; the artifact delta
   between the method's base and extension tags (the method's own artifact set, and other files it changed).
2. Held-out extension cases, per method: before the extension (exp2-base) and after it, success k/n per case, false
   completion declarations, and why each failed run failed. rows.py's ledger rule never fires here (the report is the
   plan's last task and still active while it is sent) and cannot tell a claim from an honest failure report without
   the text, so a failed run's report is read (preregistration §2, one engineer): `CLAIMS`. The baselines send no
   report.
3. Every run: the evaluator's verdict, false completions, reasoner steps (Ours), capability calls, scans, failed calls.

Runs are found by name under artifacts/runs/exp2/{pre,post}: `<pre|post>_<method>_<h1|h2>[_r<n>][_f<finding>]`, the
suffix naming the fix a rerun came after (F145, F147); the run it replaced is in post_superseded/, listed in table 3.
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))
from evaluation import rows  # noqa: E402
from evaluation.artifact_delta import artifact_delta  # noqa: E402

RUNS = R / "artifacts/runs/exp2"
OUT = R / "artifacts/eval/exp2/tables.md"
METHODS = {"ours": ("ours", "exp2-base", "exp2-ours"), "plexil": ("plexil", "exp2-base-plexil", "exp2-plexil"),
           "europa": ("europa_plexil", "exp2-base-europa", "exp2-europa_plexil")}
CASES = {"h1": "H1 mislocated", "h2": "H2 swapped"}
#: why each superseded or failed post-extension run failed (preregistration §2, assigned from the logs: the first failure
#: on the causal path) and what replaced it
WHY = {
    "post_ours_h1_r2": "3 -- step budget (75 of 80) spent re-scanning a support whose item has no readable plate and on "
                       "plan bookkeeping; reported the delivery not done; rerun as post_ours_h1_r2_f147 after F147",
    "post_europa_h1": "1/4 -- the shared scan read nothing where the unit stood (plate cut by the frame edge); rerun as "
                      "post_europa_h1_f145 after F145",
}


#: failed runs whose final report claims the mission complete (read from the report text)
CLAIMS = {"pre_ours_h1": "MISSION COMPLETE -- ORU-0417 delivered from depot_stand/slot_0 to pdu_3_shelf/shelf",
          "pre_ours_h2": "MISSION COMPLETE -- spare ORU ORU-0417 delivered to the PDU-1 spares shelf"}


def worklog(method: str) -> dict:
    ev = [json.loads(line) for line in (R / f"experiments/exp2/worklog/{method}.jsonl").read_text().splitlines() if line.strip()]
    starts = {e["session_id"]: datetime.fromisoformat(e["t"]) for e in ev if e["kind"] == "session_start"}
    sessions = [(starts[e["session_id"]], datetime.fromisoformat(e["t"])) for e in ev if e["kind"] == "session_stop"]
    return {"active_s": sum((b - a).total_seconds() for a, b in sessions), "sessions": len(sessions),
            "notes": [e["text"] for e in ev if e["kind"] == "note"]}


def validation(method: str) -> tuple[int, float]:
    """(validation runs, their wall time in s) from each run root's queue.log (local time stamps)."""
    n, wall = 0, 0.0
    for q in sorted((RUNS / "validation").glob(f"{method}_*/queue.log")):
        lines = [line.split() for line in q.read_text().splitlines()]
        t = {k: datetime.fromisoformat(f"{d}T{h}") for d, h, _, k, *_ in lines if k in ("start", "end")}
        n, wall = n + 1, wall + (t["end"] - t["start"]).total_seconds()
    return n, wall


def delta(method: str, base: str, tag: str) -> dict:
    d = artifact_delta(method, base, tag, R)
    other = [f for f in d.other_files if "worklog" not in f]
    numstat = subprocess.run(["git", "diff", "--numstat", f"{base}..{tag}", "--", *other], cwd=R, capture_output=True,
                             text=True, check=True).stdout.split("\n") if other else []
    add = sum(int(x.split("\t")[0]) for x in numstat if x.strip())
    rem = sum(int(x.split("\t")[1]) for x in numstat if x.strip())
    return {"files": sorted({f for fs in d.by_type.values() for f in fs}), "plus": d.insertions, "minus": d.deletions,
            "other": other, "other_plus": add, "other_minus": rem}


def run_facts(run: Path) -> dict:
    row = rows.extract_row(run)
    calls = row.capability_calls
    return {"run": run.name, "success": row.autonomous_mission_success, "false_completion": int(run.name in CLAIMS),
            "steps": row.step_count, "calls": sum(calls.values()), "scans": calls.get("scan_label", 0),
            "failed": [f"{c['capability']}: {c['failure_reason'][:70]}" for c in row.failed_calls],
            "elapsed_s": row.mission_elapsed_s}


def main() -> None:
    out = ["# Experiment II results (generated by experiments/exp2/tables.py from the raw records)", ""]
    out += ["## 1. Engineering (engineer: one autonomous Claude session per method, order Ours -> PLEXIL -> EUROPA)", "",
            "| method | active (min) | waiting on own validation runs (min) | other work (min) | sessions | notes | "
            "validation runs to G3 PASS | method artifacts changed | lines (+/-) | other files changed | lines (+/-) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, (method, base, tag) in METHODS.items():
        w, (n, wall), d = worklog(method), validation(method), delta(method, base, tag)
        out.append(f"| {method} | {w['active_s'] / 60:.1f} | {wall / 60:.1f} | {(w['active_s'] - wall) / 60:.1f} | "
                   f"{w['sessions']} | {len(w['notes'])} | {n} | {', '.join(d['files'])} | +{d['plus']}/-{d['minus']} | "
                   f"{', '.join(d['other']) or '-'} | +{d['other_plus']}/-{d['other_minus']} |")
    runs = {p.name: run_facts(p) for phase in ("pre", "post") for p in sorted((RUNS / phase).iterdir()) if p.is_dir()}
    out += ["", "## 2. Held-out extension cases", "",
            "| method | case | before the extension | after the extension | false completions (before / after) | failed runs after |",
            "|---|---|---|---|---|---|"]
    for key, (method, _, _) in METHODS.items():
        for case, name in CASES.items():
            pre = [f for r, f in runs.items() if re.fullmatch(f"pre_{key}_{case}", r)]
            post = [f for r, f in runs.items() if re.fullmatch(f"post_{key}_{case}(_r\\d)?(_f\\d+)?", r)]
            k = lambda fs: f"{sum(bool(f['success']) for f in fs)}/{len(fs)}"  # noqa: E731
            fails = "; ".join(f"{f['run']}: {WHY[f['run']]}" for f in post if not f["success"]) or "-"
            claims = (f"{sum(f['false_completion'] for f in pre)} / {sum(f['false_completion'] for f in post)}" if key == "ours"
                      else "no report (before: the plan ended normally with the wrong unit delivered)")
            out.append(f"| {method} | {name} | {k(pre)} | {k(post)} | {claims} | {fails} |")
    superseded = [run_facts(p) for p in sorted((RUNS / "post_superseded").iterdir()) if p.is_dir()]
    out += ["", "## 3. Every run", "", "| phase | run | success | false completion | reasoner turns (all proposals) | capability calls | "
            "scans | mission time (s) | failed calls |", "|---|---|---|---|---|---|---|---|---|"]
    for phase, facts in [("pre" if r.startswith("pre") else "post", f) for r, f in runs.items()] + [("superseded", f) for f in superseded]:
        out.append(f"| {phase} | {facts['run']} | {facts['success']} | {facts['false_completion']} | "
                   f"{facts['steps'] if facts['run'].startswith(('pre_ours', 'post_ours')) else '-'} | {facts['calls']} | "
                   f"{facts['scans']} | {facts['elapsed_s']} | {'; '.join(facts['failed']) or '-'} |")
    out += ["", "Superseded: " + "; ".join(f"{f['run']}: {WHY[f['run']]}" for f in superseded)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n")
    print(OUT.read_text())


if __name__ == "__main__":
    main()
