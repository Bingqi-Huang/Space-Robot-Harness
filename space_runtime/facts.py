"""Authoritative mission facts (execution_plan §4.1): an append-only event log and the reducer that folds it.

Mission truth is whatever the typed events establish -- the operator's intent, execution results with their
robot-observable evidence, verified effects, observations, guard decisions, FDIR/availability changes. It lives in
`events.jsonl`, never in a model conversation, so any reasoner (restarted, or a different endpoint) resumes from the
same record: `FactStore(path)` replays the log. The agent's working plan is stored here too, but as working state
(`ledger`), never as a fact.
"""
import json
import time
from pathlib import Path

RECENT = 12  # tool results kept verbatim in the facts for the context window


def empty_facts() -> dict:
    return {
        "mission": None,  # {"text", "received_wall_t"}
        "site": None,  # surveyed site knowledge (site_map query at mission start)
        "robot": {"base": None, "tcp": None, "arm": None},  # latest robot-observable state
        "verified_effects": [],  # {"seq", "capability", "effect", "holds", ...}
        "observations": [],  # {"seq", "query", "args", "value"}
        "anomalies": [],  # unresolved failures/denials: {"seq", "capability", "reason"}
        "unavailable": {},  # capability -> reason
        "fdir": {},  # fault name -> {"active", "detail"}
        "approvals": [],  # capabilities approved by the operator
        "ledger": None,  # agent working plan (MissionState state dict) -- NOT mission truth
        "recent": [],  # last RECENT tool steps: proposal, guard outcome, result
        "reasoner": None,  # {"model", "endpoint"} currently attached
        "reports": [],  # operator-facing reports/requests the agent emitted
        "terminal": None,  # {"kind": report|request|budget, "seq"}
    }


def apply(f: dict, ev: dict) -> None:
    """Fold one event into the facts (the reducer)."""
    k = ev["kind"]
    if k == "mission_received":
        f["mission"] = {"text": ev["text"], "received_wall_t": ev["wall_t"]}
    elif k == "site_knowledge":
        f["site"] = ev["site"]
    elif k == "reasoner_attached":
        f["reasoner"] = {"model": ev["model"], "endpoint": ev["endpoint"]}
    elif k == "tool_proposed":
        f["recent"].append({"seq": ev["seq"], "tool": ev["tool"], "args": ev["args"], "rationale": ev["rationale"]})
    elif k == "guard_decision":
        f["recent"][-1]["guard"] = {"outcome": ev["outcome"], "reason": ev["reason"]}
        if ev["outcome"] != "allow":
            f["anomalies"].append({"seq": ev["seq"], "capability": ev["tool"], "reason": f"guard {ev['outcome']}: {ev['reason']}"})
    elif k == "execution_finished":
        evd = ev["evidence"]
        f["recent"][-1]["result"] = {"success": ev["success"], "failure_reason": ev["failure_reason"],
                                     "sim_s": evd.get("sim_s"), "goal": evd.get("goal")}
        f["robot"].update({key: evd[src] for key, src in (("base", "base_pose"), ("tcp", "tcp_pose"), ("arm", "arm")) if isinstance(evd.get(src), dict)})
        # a capability that now succeeds resolves its own earlier failures
        f["anomalies"] = [a for a in f["anomalies"] if not (ev["success"] and a["capability"] == ev["capability"])]
        if not ev["success"]:
            f["anomalies"].append({"seq": ev["seq"], "capability": ev["capability"], "reason": ev["failure_reason"]})
    elif k == "effect_verified":
        f["verified_effects"].append({key: ev[key] for key in ev if key not in ("kind", "wall_t")})
    elif k == "query_answered":
        f["recent"][-1]["result"] = {"success": ev["success"], "value": ev["value"], "failure_reason": ev["failure_reason"]}
        if ev["success"]:
            f["observations"].append({"seq": ev["seq"], "query": ev["query"], "args": ev["args"], "value": ev["value"]})
            if ev["query"] == "arm_state":
                f["robot"]["arm"] = ev["value"]
            elif ev["query"] == "base_pose":
                f["robot"]["base"] = ev["value"]
    elif k == "reasoner_step_failed":
        # a step that produced no executable call (invalid tool call, identical-call cap): the agent sees why
        f["recent"].append({"seq": ev["seq"], "tool": ev["tool"], "args": ev["args"], "result": {"error": ev["detail"]}})
    elif k == "local_tool":
        f["recent"][-1]["result"] = {"success": ev["success"], "detail": ev["detail"]}
    elif k == "ledger_changed":
        f["ledger"] = ev["ledger"]
    elif k == "fdir_changed":
        f["fdir"][ev["fault"]] = {"active": ev["active"], "detail": ev["detail"]}
    elif k == "availability_changed":
        if ev["available"]:
            f["unavailable"].pop(ev["capability"], None)
        else:
            f["unavailable"][ev["capability"]] = ev["reason"]
    elif k == "approval_granted":
        f["approvals"].append(ev["capability"])
    elif k in ("operator_report", "operator_request"):
        f["reports"].append({"seq": ev["seq"], "kind": k, "text": ev["text"]})
        f["terminal"] = {"kind": k, "seq": ev["seq"]}
    elif k == "budget_exhausted":
        f["terminal"] = {"kind": k, "seq": ev["seq"]}
    del f["recent"][:-RECENT]


class FactStore:
    """The persistent event log plus its folded facts. Opening an existing log replays it (resume)."""

    def __init__(self, path: Path):
        self.path = path
        self.events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        self.facts = empty_facts()
        for ev in self.events:
            apply(self.facts, ev)

    def append(self, kind: str, **data) -> dict:
        ev = {"seq": len(self.events), "kind": kind, "wall_t": round(time.time(), 3), **data}
        self.events.append(ev)
        with self.path.open("a") as fh:
            fh.write(json.dumps(ev) + "\n")
        apply(self.facts, ev)
        return ev
