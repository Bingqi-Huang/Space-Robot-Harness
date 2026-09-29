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
        "anomalies": [],  # unresolved failures/denials: {"seq", "capability", "kind", ...its own fields}
        "unavailable": {},  # capability -> reason
        "fdir": {},  # fault name -> {"active", "detail"}
        "approvals": [],  # operator approvals on record: {"capability", "target"} (target None = the whole capability)
        "pending_approvals": [],  # calls the guard held for approval: {"seq", "capability", "target", "reason"}
        "power": None,  # the units' own telemetry as last read by the harness for a guard check (power_status)
        "ledger": None,  # agent working plan (MissionState state dict) -- NOT mission truth
        "recent": [],  # last RECENT tool steps: proposal, guard outcome, result
        "reasoner": None,  # {"model", "endpoint"} currently attached
        "reasoner_history": [],  # every attach: {"seq", "model", "endpoint"}
        "objects": {},  # movable item (as the mission agent named it) -> {"state": in_gripper|on <support>|unknown, + the verified effect that set it}
        "labels": {},  # support -> the latest frame read there: {"seq", "from_scan_view", "something_on_support", "plates_read", "plates": [{"serial", "px_from_aim"}], "frame_px"}
        "attempts": [],  # manipulation operations and their outcomes: {"seq", "operation", "args", "success", "stage", "why", "saw"}
        "active_execution": None,  # {"seq", "capability", "args"} between execution_started and _finished
        "reports": [],  # operator-facing reports/requests the agent emitted
        "terminal": None,  # {"kind": report|request|budget, "seq"}
    }


def attempt_summary(ev: dict) -> dict:
    sk = ev["evidence"]["skill"]
    out = {"seq": ev["seq"], "operation": ev["capability"], "args": ev["args"], "success": ev["success"],
           "stage": sk.get("failed_stage") or sk.get("stage"), "why": sk.get("why", ""), "sim_s": sk.get("sim_s")}
    tries = [{k: a[k] for k in ("attempt", "outcome", "fit") if k in a} for a in sk.get("attempts", [])]
    if tries:
        out["tries"] = tries
    # Reconciliation (method mechanism, not a skill filter): how much of the catalogue's declared interface the
    # wrist depth image agreed with where the skill took hold -- the picture against the record, in two numbers.
    for a in sk.get("attempts", []):
        if a.get("fit"):
            out.setdefault("reconciliation", []).append({
                "interface_agreement": a["fit"]["agreement"], "residual_m": a["fit"]["residual_m"],
                "points": a["fit"]["points"]})
    find = sk.get("find") or {}
    views = [v.get("vlm", {}) for v in find.get("views", [])] + [find.get("locate", {})]
    saw = sorted({v["what_is_visible"] for v in views if v.get("what_is_visible")})
    if saw:
        out["vision_model_saw"] = saw[:3]
    out["measurements"] = {k: {name: value for name, value in sk[k].items()
                               if name not in ("before", "after", "before_depth", "gripper_mask")}
                           for k in ("hold_check", "bring_in") if k in sk}
    out["base_pose"] = ev["evidence"].get("base_pose")
    # Preserve the physical execution conditions across reasoner restarts. These
    # are evidence, not held facts or a prescribed recovery sequence.
    out["execution_conditions"] = {
        key: sk[key] for key in ("contact_scene", "target_lock", "last_ik", "last_state_validity",
                                "contact_path_observation", "closure_precondition", "decision_required")
        if key in sk
    }
    return out


def apply(f: dict, ev: dict) -> None:
    """Fold one event into the facts (the reducer)."""
    k = ev["kind"]
    if k == "mission_received":
        f["mission"] = {"text": ev["text"], "received_wall_t": ev["wall_t"]}
    elif k == "site_knowledge":
        f["site"] = ev["site"]
    elif k == "reasoner_attached":
        f["reasoner"] = {"model": ev["model"], "endpoint": ev["endpoint"]}
        f["reasoner_history"].append({"seq": ev["seq"], "model": ev["model"], "endpoint": ev["endpoint"]})
        if f["active_execution"] is not None:  # the previous reasoner stopped while an effect was running
            a = f["active_execution"]
            f["anomalies"].append({"seq": ev["seq"], "capability": a["capability"], "kind": "outcome_unrecorded", "started_seq": a["seq"]})
            f["active_execution"] = None
    elif k == "tool_proposed":
        f["recent"].append({"seq": ev["seq"], "tool": ev["tool"], "args": ev["args"], "rationale": ev["rationale"]})
    elif k == "guard_decision":
        f["recent"][-1]["guard"] = {"outcome": ev["outcome"], "reason": ev["reason"]}
        if ev["outcome"] != "allow":
            f["anomalies"].append({"seq": ev["seq"], "capability": ev["tool"], "kind": f"guard_{ev['outcome']}", "reason": ev["reason"]})
    elif k == "execution_started":
        f["active_execution"] = {"seq": ev["seq"], "capability": ev["capability"], "args": ev["args"]}
    elif k == "execution_finished":
        f["active_execution"] = None
        evd = ev["evidence"]
        f["recent"][-1]["result"] = {"success": ev["success"], "failure_reason": ev["failure_reason"],
                                     "sim_s": evd.get("sim_s"), "goal": evd.get("goal")}
        if "skill" in evd:  # an operation's own record: the stage it reached and what its camera / vision model saw
            f["attempts"].append(attempt_summary(ev))
            # A disagreement between sources is an anomaly naming them (plan v4 §5), not a detail inside the attempt
            for r in f["attempts"][-1].get("reconciliation", []):
                if r["interface_agreement"] < 0.5:
                    f["anomalies"].append({"seq": ev["seq"], "capability": ev["capability"], "kind": "source_disagreement", **r})
        f["robot"].update({key: evd[src] for key, src in (("base", "base_pose"), ("tcp", "tcp_pose"), ("arm", "arm")) if isinstance(evd.get(src), dict)})
        # a capability that now succeeds resolves its own earlier failures
        f["anomalies"] = [a for a in f["anomalies"] if not (ev["success"] and a["capability"] == ev["capability"])]
        if not ev["success"]:
            # a remote service that did not answer is an outage of the stack, not an outcome of the robot's work: the
            # anomaly says so, so the record separates "the method failed here" from "the gateway was down"
            dep = (evd.get("skill") or {}).get("dependency_unavailable")
            f["anomalies"].append({"seq": ev["seq"], "capability": ev["capability"], "kind": "failed", "reason": ev["failure_reason"],
                                   **({"service_outage": dep} if dep else {})})
    elif k == "effect_verified":
        f["verified_effects"].append({key: ev[key] for key in ev if key not in ("kind", "wall_t")})
        # object facts change only on verified evidence
        basis = {"seq": ev["seq"], "effect": ev["effect"], "holds": ev["holds"], "after": ev["capability"]}
        if ev["effect"] == "item_held":
            if ev["holds"]:
                f["objects"][ev["target"]] = {"state": "in_gripper", **basis}
            elif f["objects"].get(ev["target"], {}).get("state") == "in_gripper" or ev["jaw"] == "holding_object":
                f["objects"][ev["target"]] = {"state": "unknown", **basis}
        if ev["effect"] == "item_still_held" and not ev["holds"]:
            # Failed confirmation invalidates the held fact; it does not prove the item fell or the jaws are empty.
            # What the camera showed and how it was read stay with the item so the agent can resolve the uncertainty.
            for name in ev["items"]:
                f["objects"][name] = {"state": "unknown", **basis, "camera_saw": ev.get("seen"), "jaw_rad": ev["jaw_rad"],
                                      "read_twice_record_and_jaw_say_held": ev.get("record_and_jaw_expect_held")}
        if ev["effect"] == "labels_read" and ev.get("image"):
            # what one frame read at a support, kept past the recent window (a scan that took no frame read nothing there)
            f["labels"][ev["support"]] = {"seq": ev["seq"], "from_scan_view": ev["holds"], "something_on_support": ev["something_on_support"],
                                          "plates_read": ev["plates_read"], "plates": ev["plates"], "frame_px": ev["frame_px"]}
        if ev["effect"] == "item_placed":
            # not established (holds None): let go at the support, not seen resting there -- the item is out of the jaws
            # and its place is unknown until something shows it
            held = [name for name, o in f["objects"].items() if o["state"] == "in_gripper"]
            for name in held:
                f["objects"][name] = ({"state": f"on {ev['support']}", **basis} if ev["holds"] else
                                      {"state": "unknown", **basis, "let_go_above_expected_m": ev.get("let_go_above_expected_m"),
                                       "skill_stopped_at": ev.get("skill_stopped_at")})
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
    elif k == "equipment_telemetry":
        f["power"] = ev["value"]
    elif k == "approval_pending":
        f["pending_approvals"] = [p for p in f["pending_approvals"] if (p["capability"], p["target"]) != (ev["capability"], ev["target"])]
        f["pending_approvals"].append({key: ev[key] for key in ("seq", "capability", "target", "reason")})
    elif k == "approval_granted":
        f["approvals"].append({"capability": ev["capability"], "target": ev["target"]})
        f["pending_approvals"] = [p for p in f["pending_approvals"] if (p["capability"], p["target"]) != (ev["capability"], ev["target"])]
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
