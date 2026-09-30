"""Re-authoring study: engineering time per baseline x held-out case (user 2026-09-30: engineering time = active time
minus waiting on the simulation). Active time = the worklog's timer intervals (session_start -> session_stop, UTC);
waiting on the simulation = the part of them during which one of the case's own live validation runs was running
(queue.log start -> end lines, CST). A stalled run counts only while the timer ran (it was stopped 15 min after the
run's last progress, F154). Also: the case's validation runs and the baseline's own files changed on its branch.

    python3 experiments/reauthoring/cost_table.py
"""
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[2]
CST = timezone(timedelta(hours=8))
CASES = [(b, c) for b in ("plexil", "europa_plexil") for c in ("l2a", "l2b", "l3", "l4")]


def timer(case):
    spans, start = [], None
    for line in (R / "experiments/reauthoring/worklog" / f"{case}.jsonl").read_text().splitlines():
        e = json.loads(line)
        t = datetime.fromisoformat(e["t"])
        if e["kind"] == "session_start":
            start = t
        elif e["kind"] == "session_stop" and start:
            spans.append((start, t))
            start = None
    return spans


def runs(case):
    out = []
    for q in sorted((R / "artifacts/runs/reauth" / case).glob("*/queue.log")):
        began = {}
        for line in q.read_text().splitlines():
            d, h, _, what, *rest = line.split() + [""]
            t = datetime.fromisoformat(f"{d}T{h}").replace(tzinfo=CST)
            if what in ("start", "end") and rest[0]:
                if what == "start":
                    began[rest[0]] = t
                else:
                    out.append((q.parent.name, rest[0], began.pop(rest[0]), t))
        out += [(q.parent.name, name, t, None) for name, t in began.items()]  # still running
    return out


def overlap(spans, a, b):
    b = b or datetime.now(timezone.utc)
    return sum(max(0.0, (min(e, b) - max(s, a)).total_seconds()) for s, e in spans)


def diff(case):
    b, c = case.split("_")[0], case.split("_")[-1]
    out = subprocess.run(["git", "-C", str(R), "diff", "--numstat", "exp1b", f"reauth/{'europa' if b == 'europa' else b}-{c}",
                          "--", "baselines", "ros"], capture_output=True, text=True).stdout.split("\n")
    rows = [l.split("\t") for l in out if l]
    return len(rows), sum(int(r[0]) for r in rows), sum(int(r[1]) for r in rows)


print("| baseline | case | active (min) | waiting on own validation runs (min) | engineering time (min) | validation runs | files +/- (baselines/, ros/) |")
print("|---|---|---|---|---|---|---|")
for b, c in CASES:
    case = f"{b}_{c}"
    spans = timer(case)
    active = sum((e - s).total_seconds() for s, e in spans)
    rs = runs(case)
    wait = sum(overlap(spans, a, e) for _, _, a, e in rs)
    n, add, rm = diff(case)
    vr = ", ".join(f"{v}/{name}" + ("" if e else " (running)") for v, name, _, e in rs)
    print(f"| {'PLEXIL' if b == 'plexil' else 'EUROPA->PLEXIL'} | {c.upper()} | {active / 60:.1f} | {wait / 60:.1f} | "
          f"{(active - wait) / 60:.1f} | {vr} | {n} files +{add}/-{rm} |")
