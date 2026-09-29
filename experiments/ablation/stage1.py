"""Stage 1 of the §5.7 ablations (research repo F148): what each variant would have recorded and shown on the 25
Experiment I Ours runs as they happened -- offline, no model called. Writes <out>/stage1.md.

  no_verification  every call whose flag-based effect disagrees with the verifier's, and the looks at a carried item
                   the variant never takes
  no_guard         the calls the guard held, which nothing would have held
  no_facts         the steps at which the full record held an item location or an unresolved anomaly set more than the
                   12 recent steps back -- what the variant's model would have had only in its own plan notes
  no_context       the accumulated conversation against the rebuilt message, in characters (from points/N__*)
"""
import json
import sys
from collections import Counter
from pathlib import Path

from accidents import EXP1B, as_recorded_by
from record import STEP_KINDS, events, fold

out = Path(sys.argv[1])
lines = ["# Stage 1: the ablation variants on the Experiment I runs as they happened (offline, no model)", ""]

# ---- no_verification ----------------------------------------------------------------------------------------------------
dis, looks, calls = Counter(), Counter(), 0
for run in EXP1B:
    evs = events(run)
    rep = {e["seq"] - (e["seq"] % 1): e for e in as_recorded_by("no_verification", evs) if e["kind"] == "effect_verified"}
    for i, e in enumerate(evs):
        if e["kind"] == "execution_finished":
            calls += 1
        if e["kind"] != "effect_verified":
            continue
        if e["effect"] == "item_still_held":
            looks[e["holds"]] += 1
            continue
        call = next(x for x in reversed(evs[:i]) if x["kind"] == "execution_finished")
        flag = bool(call["success"])
        if e["holds"] != flag:
            dis[(e["capability"], e["effect"], str(e["holds"]), f"flag {flag}")] += 1
lines += ["## no_verification", "", f"{calls} calls. Effects where the verifier and the skill's flag disagree:", "",
          "| capability | effect | verifier | flag | n |", "|---|---|---|---|---|",
          *[f"| {c} | {eff} | {v} | {fl} | {n} |" for (c, eff, v, fl), n in sorted(dis.items())], "",
          f"Looks at a carried item the variant never takes: {sum(looks.values())} ({looks[True]} held, {looks[False]} not held).", ""]

# ---- no_guard -----------------------------------------------------------------------------------------------------------
held = [(run, e["tool"], e["reason"][:60]) for run in EXP1B for e in events(run) if e["kind"] == "guard_decision" and e["outcome"] != "allow"]
lines += ["## no_guard", "", f"Calls the guard held ({len(held)}); without it each would have run at once:", "",
          *[f"- {r}: {t} ({why}...)" for r, t, why in held], ""]

# ---- no_facts -----------------------------------------------------------------------------------------------------------
steps = outside = 0
per_run = []
for run in EXP1B:
    evs = events(run)
    k_steps = k_out = 0
    for i, e in enumerate(evs):
        if e["kind"] != "reasoner_step_started":
            continue
        f = fold(evs[:i + 1])
        window = min((r["seq"] for r in f["recent"]), default=0)
        old = [o for o in f["objects"].values() if o["seq"] < window] + [a for a in f["anomalies"] if a["seq"] < window]
        k_steps += 1
        k_out += bool(old)
    steps, outside = steps + k_steps, outside + k_out
    per_run.append(f"{run.split('/')[1]} {k_out}/{k_steps}")
lines += ["## no_facts", "",
          f"Steps at which the full record held an item location or an unresolved anomaly older than the 12 recent steps: "
          f"{outside} of {steps}.", "", "Per run: " + ", ".join(per_run), ""]

# ---- no_context ---------------------------------------------------------------------------------------------------------
pts = sorted(Path(sys.argv[2]).glob("N__*.json"))
size = lambda a: len(a["system"]) + sum(len(m.get("content") or "") + len(json.dumps(m.get("tool_calls", ""))) for m in a["messages"])
rows = [(json.loads(p.read_text())) for p in pts]
lines += ["## no_context", "", "Two thirds through each run: the rebuilt message (system + step) against the accumulated "
          "conversation (system + every message so far), characters (~2.5 per token on these records).", "",
          "| run | step | rebuilt | accumulated | messages |", "|---|---|---|---|---|",
          *[f"| {r['run'].split('/')[1]} | {r['step']} | {size(r['arms']['full'])} | {size(r['arms']['no_context'])} | "
            f"{len(r['arms']['no_context']['messages'])} |" for r in rows], ""]
(out / "stage1.md").write_text("\n".join(lines))
print("\n".join(lines))
