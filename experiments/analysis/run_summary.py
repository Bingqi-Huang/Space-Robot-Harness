"""One-page summary of a finished Ours run: verdict, steps, calls, operator exchanges (mission + wall time), rows."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.rows import extract_row  # noqa: E402
from evaluation.interaction import measures  # noqa: E402

run = Path(sys.argv[1])
row = extract_row(run)
print(f"== {run.name}: success={row.autonomous_mission_success} reason={row.failure_reason} "
      f"false_completion={row.false_completion_declaration_count}")
ev = [json.loads(l) for l in open(run / "ours/events.jsonl")]
steps = [e for e in ev if e["kind"] == "reasoner_step_started"]
print(f"steps {len(steps)}; guard non-allow {sum(1 for e in ev if e['kind'] == 'guard_decision' and e.get('outcome') != 'allow')}")
for l in open(run / "capability_server.log"):
    if "CAPABILITY {" in l:
        c = json.loads(l[l.index("{"):])
        a = {k: v for k, v in c["args"].items() if k in ("feature", "support", "item", "camera", "x", "y", "question", "target")}
        print(f"  {c.get('sim_t_start', 0):7.0f}-{c.get('sim_t_end', 0):7.0f} {c['capability']:20s} {'ok ' if c['success'] else 'FAIL'} "
              f"{json.dumps(a)[:110]} {c['failure_reason'][:120]}")
op = run / "operator/events.jsonl"
if op.exists():
    t0 = None
    for l in open(op):
        e = json.loads(l)
        t0 = t0 or e["wall_t"]
        if e["kind"] in ("interaction_start", "interaction_end", "link_queued", "reply_delivered"):
            print(f"  OP {e['kind']:18s} mission_t {e['mission_t']:7.1f} wall+{e['wall_t'] - t0:7.0f}s "
                  f"{str(e.get('text') or e.get('why') or e.get('outcome') or '')[:150]}")
m = measures(run)
print("  interaction:", {k: m[k] for k in ("requests_authorization", "requests_escalation", "requests_queued_by_link",
                                            "grants", "ground_reauthoring_required")})
rep = run / "ours/report.md"
if rep.exists():
    print("  REPORT:", rep.read_text()[:600].replace("\n", " | "))
