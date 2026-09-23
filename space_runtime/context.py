"""Dynamic context construction (execution_plan §4.5, §9.5): the snapshot the agent reads each step.

Selects and formats facts from the authoritative record -- mission intent, site knowledge, robot state, verified
effects, observations, unresolved anomalies, availability/FDIR/authority, the agent's own working plan, the recent
tool steps and any operator request/answer exchange. It never chooses or suggests the next action. Rebuilt from the
record every step, so a restarted or switched reasoner sees exactly what the previous one would have.
"""
import json

from openral_reasoner.context import ContextRenderer

from openral_ext.capability_server.contracts import CONTRACTS


def _j(v) -> str:
    return json.dumps(v, separators=(",", ":"))


def render(facts: dict, step: int, max_steps: int, events: list[dict] | None = None, authority_rules: list[dict] | None = None) -> str:
    f = facts
    out = [f"## MISSION (from mission control)\n{f['mission']['text']}",
           f"## STEP\n{step} of the mission step budget {max_steps}"]
    site = f["site"]
    lines = [f"frame {site['frame']}; point types: " + "; ".join(f"{k} = {v}" for k, v in site["point_types"].items())]
    lines += [f"- {name}: {p['type']} on {p['equipment']} at {_j(p['xyz'])}, normal {_j(p['normal'])}" for name, p in site["points"].items()]
    lines += [f"- view pose {name}: x={v['x']} y={v['y']} yaw={v['yaw']} (looks at {_j(v['looks_at'])})" for name, v in site["view_poses"].items()]
    lines.append(f"- rover dock: {_j(site['dock'])}")
    out.append("## SITE (surveyed, fixed infrastructure)\n" + "\n".join(lines))
    if site.get("equipment_catalogue"):
        out.append("## EQUIPMENT CATALOGUE (documented prior knowledge; not current observations)\n"
                   + _j(site["equipment_catalogue"]))
    r = f["robot"]
    out.append("## ROBOT STATE (latest robot-observable evidence)\n"
               f"base estimate: {_j(r['base']) if r['base'] else 'not yet read'}\n"
               f"tool centre point: {_j(r['tcp']) if r['tcp'] else 'not yet read'}\n"
               f"arm: {_j(r['arm']) if r['arm'] else 'not yet read'}")
    eff = [f"- [{e['seq']}] after {e['capability']}: {e['effect']} {'HOLDS' if e['holds'] else 'DOES NOT HOLD'} "
           f"({_j({k: v for k, v in e.items() if k not in ('seq', 'capability', 'effect', 'holds')})})" for e in f["verified_effects"][-12:]]
    out.append("## VERIFIED EFFECTS (independent verification of what physically happened; latest last)\n" + ("\n".join(eff) or "(none yet)"))
    obs = [f"- [{o['seq']}] {o['query']}{_j(o['args']) if o['args'] else ''} -> {_j(o['value'])}" for o in f["observations"][-8:] if o["query"] != "site_map"]
    out.append("## OBSERVATIONS (query answers; latest last)\n" + ("\n".join(obs) or "(none yet)"))
    objs = [f"- {name}: {o['state']} (record #{o['seq']}, {o['by']})" for name, o in f["objects"].items()]
    out.append("## MOVABLE ITEMS (changed only by verified effects)\n" + ("\n".join(objs) or "(no verified manipulation yet)"))
    tries = [f"- [{a['seq']}] {a['operation']}{_j(a['args'])} -> {'success' if a['success'] else 'failed'} at stage {a['stage']}"
             + (f": {a['why']}" if a["why"] else "") + (f"; tries {_j(a['tries'])}" if a.get("tries") else "")
             + (f"; base estimate {_j(a['base_pose'])}" if a.get("base_pose") else "")
             + (f"; skill measurements {_j(a['measurements'])}" if a.get("measurements") else "")
             + (f"; RECONCILIATION interface fit vs equipment catalogue {_j(a['reconciliation'])}" if a.get("reconciliation") else "")
             + (f"; execution conditions {_j(a['execution_conditions'])}" if a.get("execution_conditions") else "")
             + (f"; the vision model saw {_j(a['vision_model_saw'])}" if a.get("vision_model_saw") else "") for a in f["attempts"][-10:]]
    out.append("## MANIPULATION ATTEMPTS (operations on items, latest last)\n" + ("\n".join(tries) or "(none yet)"))
    anomalies = [f"- [{a['seq']}] {a['capability']}: {a['reason']}" for a in f["anomalies"]]
    out.append("## UNRESOLVED ANOMALIES\n" + ("\n".join(anomalies) or "(none)"))
    # request_operator's requests and mission control's asynchronous answers, read straight off the record (no decision
    # logic here about what an answer means); a request with no answer yet is still open
    ops = [e for e in (events or []) if e["kind"] in ("operator_request_sent", "operator_answered")]
    if ops:
        lines = [f"- [{e['seq']}] you asked mission control: {e['text']}" if e["kind"] == "operator_request_sent"
                 else f"- [{e['seq']}] mission control answered ({e.get('outcome') or e.get('link_status')}): {e['text']}"
                 for e in ops[-8:]]
        out.append("## OPERATOR EXCHANGES (your requests and mission control's answers, latest last)\n" + "\n".join(lines))
    if len(f["reasoner_history"]) > 1:
        out.append("## REASONER CONTINUITY\nthis record was continued by another reasoner session: "
                   + " -> ".join(f"{r['model']} (from record #{r['seq']})" for r in f["reasoner_history"]))
    status = [f"unavailable capabilities: {_j(f['unavailable']) if f['unavailable'] else 'none'}",
              f"active faults: {_j({k: v for k, v in f['fdir'].items() if v['active']}) or 'none'}",
              "authority: " + ", ".join(sorted({c['authority_class'] for c in CONTRACTS['effects'].values()})) + " operations are autonomous"
              + "".join(f"; except {r['name']}: {', '.join(r['applies_to'])} on a {r['target_role']} whose unit reports "
                        f"{_j(r['when_unit'])} is {r['outcome']} ({r['why']})" for r in authority_rules or [])
              + (f"; operator approvals on record: {_j(f['approvals'])}" if f["approvals"] else "")
              + (f"; held for mission control's approval (send request_operator; the request carries these): "
                 f"{_j([{k: p[k] for k in ('capability', 'target')} for p in f['pending_approvals']])}" if f["pending_approvals"] else "")]
    out.append("## OPERATING STATUS\n" + "\n".join(status))
    ledger = f["ledger"]
    if ledger:
        plan = [f"- {t['task_id']} [{t['status']}] {t['text']}" + (f" -- {t['last_verdict']}" if t["last_verdict"] else "") for t in ledger["tasks"]]
        out.append("## YOUR WORKING PLAN (yours to revise; not a record of what happened)\n" + "\n".join(plan))
    else:
        out.append("## YOUR WORKING PLAN\n(no plan written yet)")
    steps = []
    for s in f["recent"]:
        line = f"- [{s['seq']}] {s['tool']}{_j(s['args'])}"
        if "guard" in s and s["guard"]["outcome"] != "allow":
            line += f" -> GUARD {s['guard']['outcome'].upper()}: {s['guard']['reason']}"
        if "result" in s:
            line += f" -> {_j(s['result'])}"
        steps.append(line)
    out.append("## RECENT STEPS (oldest first)\n" + ("\n".join(steps) or "(none yet)"))
    return "\n\n".join(out)


class HarnessRenderer(ContextRenderer):
    """OpenRAL's renderer slot filled with the harness context (ReasonerCore calls `render` each tick)."""

    def __init__(self, store, max_steps: int, authority_rules: list[dict]):
        super().__init__()
        self.store, self.max_steps, self.step, self.authority_rules = store, max_steps, 0, authority_rules

    def render(self, *, world_state=None) -> str:
        return render(self.store.facts, self.step, self.max_steps, self.store.events, self.authority_rules)
