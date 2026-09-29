"""With no variant set, the switches must leave the full method as it ran: re-render every recorded step of every
Experiment I Ours run (exp1b) and compare with what was actually sent (`ours/model_io.jsonl`), character for character.
The one expected difference is the link line's `earth_sets_in_s` (rounded to 0.1 s from a clock read a few milliseconds
after the step's event)."""
import re
import sys

from record import RUNS, before, events, model_io, render

LINK = re.compile(r'"earth_sets_in_s":[-0-9.]+')
bad = total = 0
for run in sorted(p.parent.name for p in RUNS.glob("exp1b/ours_*/ours")):
    run = f"exp1b/{run}"
    evs = events(run)
    for row in model_io(run):
        sent_sys, sent = row["request"]["messages"][0]["content"], row["request"]["messages"][1]["content"]
        system, user = render(None, *before(evs, row["step"])[:1], row["step"], before(evs, row["step"])[1])
        total += 1
        if system != sent_sys or LINK.sub("", user) != LINK.sub("", sent):
            bad += 1
            a, b = LINK.sub("", user).splitlines(), LINK.sub("", sent).splitlines()
            first = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
            print(run, row["step"], "system" if system != sent_sys else f"line {first}: {a[first:first+1]} vs {b[first:first+1]}"[:400])
print(f"{total - bad}/{total} steps identical")
sys.exit(bad > 0)
