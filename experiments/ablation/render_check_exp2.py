"""After merging the ablation switches into main (2026-09-30): with no variant set, main's harness must re-render every
recorded step of the final Experiment II Ours run (post_ours_h1_r2_f147, run on main's final code) exactly as it was
sent (render_check.py's rule and its one expected difference, the link line's rounding; the STEP line's number is the
agent's budget count, F147)."""
import re
import sys

from record import before, events, model_io, render
from space_runtime.agent import PLAN_TOOLS

LINK = re.compile(r'"earth_sets_in_s":[-0-9.]+')
bad = total = 0
for run in sys.argv[1:] or ["exp2/post/post_ours_h1_r2_f147"]:
    evs = events(run)
    for row in model_io(run):
        sent_sys, sent = row["request"]["messages"][0]["content"], row["request"]["messages"][1]["content"]
        cut, t = before(evs, row["step"])
        # the STEP line shows the budget count since F147: calls on the robot and failed steps, not plan bookkeeping
        shown = 1 + sum(e["kind"] == "reasoner_step_failed" or (e["kind"] == "tool_proposed" and e["tool"] not in PLAN_TOOLS) for e in cut)
        system, user = render(None, cut, shown, t)
        total += 1
        if system != sent_sys or LINK.sub("", user) != LINK.sub("", sent):
            bad += 1
            a, b = LINK.sub("", user).splitlines(), LINK.sub("", sent).splitlines()
            first = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
            print(run, row["step"], "system" if system != sent_sys else f"line {first}: {a[first:first+1]} vs {b[first:first+1]}"[:400])
print(f"{total - bad}/{total} steps identical")
sys.exit(bad > 0)
