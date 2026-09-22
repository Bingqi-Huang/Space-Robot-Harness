"""Mission report from the structured record (execution_plan §9.6, §4.13).

The agent's own operator report is quoted, but the body is generated from the events: what was executed, what the
guard decided, which effects the independent verification established, what stayed unresolved. Where prose and
evidence disagree, the evidence sections are the record.
"""
import json


def write_report(store, path) -> None:
    f, ev = store.facts, store.events
    calls = [e for e in ev if e["kind"] == "execution_finished"]
    guard = [e for e in ev if e["kind"] == "guard_decision" and e["outcome"] != "allow"]
    failed = [e for e in ev if e["kind"] == "reasoner_step_failed"]
    queries = [e for e in ev if e["kind"] == "query_answered" and e["query"] != "site_map"]
    lines = ["# Mission report", "", "## Mission", f["mission"]["text"], "",
             f"## Outcome of the autonomous run\n{f['terminal']['kind'] if f['terminal'] else 'in progress'}", ""]
    for r in f["reports"]:
        lines += [f"## Agent {'report' if r['kind'] == 'operator_report' else 'request to mission control'} (record #{r['seq']})", r["text"], ""]
    lines += ["## Executed capabilities (boundary results)", "| # | sim t | capability | args | success | failure |", "|---|---|---|---|---|---|"]
    lines += [f"| {e['seq']} | {e['sim_t']} | {e['capability']} | `{json.dumps(e['args'])}` | {e['success']} | {e['failure_reason'][:80]} |" for e in calls]
    lines += ["", "## Verified effects (independent verification)", "| # | after | effect | holds | measure |", "|---|---|---|---|---|"]
    lines += [f"| {e['seq']} | {e['capability']} | {e['effect']} | {e['holds']} | "
              f"`{json.dumps({k: v for k, v in e.items() if k not in ('seq', 'kind', 'wall_t', 'sim_t', 'capability', 'effect', 'holds', 'source')})}` |"
              for e in ev if e["kind"] == "effect_verified"]
    lines += ["", "## Movable items (verified)", *([f"- {n}: {o['state']} (#{o['seq']}, {o['by']})" for n, o in f["objects"].items()] or ["(none)"])]
    lines += ["", "## Manipulation attempts", *([f"- #{a['seq']} {a['operation']} {json.dumps(a['args'])}: {'success' if a['success'] else 'failed'} at {a['stage']} {a['why']}" for a in f["attempts"]] or ["(none)"])]
    lines += ["", "## Observations", *[f"- #{e['seq']} {e['query']} {json.dumps(e['args'])} -> {json.dumps(e['value'])[:300]}" for e in queries]]
    lines += ["", "## Guard decisions other than allow", *([f"- #{e['seq']} {e['tool']}: {e['outcome']} ({e['reason']})" for e in guard] or ["(none)"])]
    lines += ["", "## Steps without an executable call", *([f"- #{e['seq']} {e['tool']}: {e['detail'][:200]}" for e in failed] or ["(none)"])]
    # an outage of a service the stack depends on is not an outcome of the method: the evaluation counts them apart
    outages = [a for a in f["anomalies"] if a.get("service_outage")]
    lines += ["", "## Unresolved at the end", *([f"- #{a['seq']} {a['capability']}: {a['reason']}" for a in f["anomalies"]] or ["(none)"])]
    lines += ["", "## Service outages (not the robot's doing)",
              *([f"- #{a['seq']} {a['capability']}: {a['service_outage']['service']} "
                 f"({a['service_outage']['model']}) {a['service_outage']['error']} at stage {a['service_outage']['stage']}"
                 for a in outages] or ["(none)"])]
    if f["ledger"]:
        lines += ["", "## Agent working plan at the end", *[f"- {t['task_id']} [{t['status']}] {t['text']}" for t in f["ledger"]["tasks"]]]
    path.write_text("\n".join(lines) + "\n")
