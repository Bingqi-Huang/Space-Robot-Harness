"""Dynamic context construction (execution_plan §4.5, §9.5): what the reasoner reads, filled from the record.

Every word the model reads is in `prompts/ours/` (the standing text `system.md`, the per-step template `step.md`);
this module only selects facts from the authoritative record and fills the templates, one JSON record per line. The
standing text is filled once per reasoner session (the authority exceptions from the contracts and the guard
configuration, the link's constants, the surveyed site); the step message is rebuilt from the record every step, so a
restarted or switched reasoner sees exactly what the previous one would have. Nothing here chooses or suggests the
next action.
"""
import json

from openral_reasoner.context import ContextRenderer

from openral_ext.capability_server.contracts import CONTRACTS
from experiments.operator_console.console import DECISION_TIME_S
from space_context import link
from space_runtime import ablation


def _j(v) -> str:
    return json.dumps(v, separators=(",", ":"))


def _lines(records: list[dict], empty: str = "(none)") -> str:
    # empty fields are left out, except a verdict: `holds` null (not established) is a fact of its own
    return "\n".join(_j({k: v for k, v in r.items() if v not in (None, "", [], {}) or k == "holds"}) for r in records) or empty


def system_text(facts: dict, rules: list[dict]) -> str:
    """The standing text of a reasoner session: rules, the authority model read off the contracts and the guard
    configuration (never written per mission), the link's constants, the surveyed site."""
    exceptions = [f"- {k} ({c['authority_class'].replace('_', ' ')})" for k, c in sorted(CONTRACTS["effects"].items())
                  if c["authority_class"] != "routine"]
    exceptions += [f"- {', '.join(r['applies_to'])} on a {r['target_role']} whose unit reports {_j(r['when_unit'])}: "
                   f"{r['outcome'].replace('_', ' ')} -- {r['why']}" for r in rules]
    site, ls = facts["site"], link.state(0.0)
    return ablation.prompt("system.md").read_text().format(
        authority_exceptions="\n".join(exceptions) or "(none)",
        link=ls["link"], one_way_delay_s=ls["one_way_delay_s"], decision_time_s=f"{DECISION_TIME_S:.0f}",
        site_frame=site["frame"], site_point_types=_j(site["point_types"]),
        site_points=_lines([{"point": name, **p} for name, p in site["points"].items()]),
        site_view_poses=_lines([{"view_pose": name, **v} for name, v in site["view_poses"].items()]),
        site_dock=_j(site["dock"]), equipment_catalogue=_j(site.get("equipment_catalogue")))


def _now(mission_t: float) -> dict:
    ls = link.state(mission_t)
    return {"mission_time_s": round(mission_t), "link": "up" if ls["earth_visible"] else "down (Earth below the horizon)",
            "earth_sets_in_s": ls["closes_in_s"], "link_reopens_in_s": ls["reopens_in_s"]}


def _exchange(e: dict) -> dict:
    return ({"seq": e["seq"], "asked": e["text"], "kind": e.get("request_kind")} if e["kind"] == "operator_request_sent"
            else {"seq": e["seq"], "answered": e["text"], "outcome": e.get("outcome") or e.get("link_status")})


def _recent(s: dict) -> dict:
    return {"seq": s["seq"], "tool": s["tool"], "args": s["args"],
            "guard": s["guard"] if "guard" in s and s["guard"]["outcome"] != "allow" else None, "result": s.get("result")}


def _effect(e: dict) -> dict:
    return {k: v for k, v in e.items() if k not in ("kind", "wall_t", "seq", "sim_t", "capability")}


def _own_records(facts: dict, events: list[dict]) -> tuple[dict, dict]:
    """Each step's own verified effects and manipulation record, by the seq of the step's proposal."""
    verified, attempts, step_of, step_seq = {}, {}, {}, None
    for e in events:
        if e["kind"] in ("tool_proposed", "reasoner_step_failed"):
            step_seq = e["seq"]
        step_of[e["seq"]] = step_seq
        if e["kind"] == "effect_verified":
            verified.setdefault(step_seq, []).append(_effect(e))
    for a in facts["attempts"]:
        attempts[step_of[a["seq"]]] = a
    return verified, attempts


def step_text(facts: dict, step: int, max_steps: int, events: list[dict], mission_t: float) -> str:
    f = facts
    now = _now(mission_t)
    exchanges = [_exchange(e) for e in events if e["kind"] in ("operator_request_sent", "operator_answered")][-8:]
    approvals = {"approvals_on_record": f["approvals"],
                 "held_for_approval": [{k: p[k] for k in ("capability", "target")} for p in f["pending_approvals"]]}
    step_line = [{"step": step, "of_budget": max_steps}]
    if len(f["reasoner_history"]) > 1:
        step_line.append({"continued_by_another_reasoner": f["reasoner_history"]})
    recent = [_recent(s) for s in f["recent"]]
    if ablation.VARIANT == "no_facts":  # a result carries its own manipulation record and verification; nothing accumulates them
        verified, attempts = _own_records(f, events)
        for r in recent:
            r["attempt"], r["verified"] = attempts.get(r["seq"]), verified.get(r["seq"])
    return ablation.prompt("step.md").read_text().format(
        mission=f["mission"]["text"], step=_lines(step_line), robot=_j(f["robot"]),
        verified_effects=_lines(f["verified_effects"][-12:]),
        observations=_lines([o for o in f["observations"] if o["query"] != "site_map"][-8:]),
        objects=_lines([{"item": name, **o} for name, o in f["objects"].items()], "(no verified manipulation yet)"),
        attempts=_lines(f["attempts"][-10:]), anomalies=_lines(f["anomalies"]),
        mission_control=_lines([now, *exchanges, approvals]),
        status=_j({"unavailable_capabilities": f["unavailable"], "active_faults": {k: v for k, v in f["fdir"].items() if v["active"]}}),
        plan=_lines([{k: t[k] for k in ("task_id", "status", "text", "last_verdict")} for t in f["ledger"]["tasks"]] if f["ledger"] else [],
                    "(no plan written yet)"),
        recent=_lines(recent))


# ---- ablation no_context: one accumulating conversation instead of a record rebuilt every step -----------------------
NEWS = ("operator_answered", "approval_granted", "fdir_changed", "availability_changed")


def start_text(facts: dict, step: int, max_steps: int, mission_t: float) -> str:
    """The first message of a reasoner session: the mission and what the robot reports now -- nothing from the record."""
    return ablation.prompt("start.md").read_text().format(
        mission=facts["mission"]["text"], step=_lines([{"step": step, "of_budget": max_steps}]), robot=_j(facts["robot"]),
        mission_control=_lines([_now(mission_t)]))


def result_text(facts: dict, step: int, max_steps: int, new: list[dict], mission_t: float) -> str:
    """The answer to the previous call, from the events since it was made: its result (as RECENT STEPS gives it), the
    verification of its effect, its manipulation record, the robot's state after it, and whatever arrived meanwhile."""
    seqs = {e["seq"] for e in new}
    last = facts["recent"][-1]
    return ablation.prompt("result.md").read_text().format(
        result=_lines([_recent(last)]),
        verified=_lines([_effect(e) for e in new if e["kind"] == "effect_verified"]),
        attempt=_lines([a for a in facts["attempts"] if a["seq"] in seqs]), robot=_j(facts["robot"]),
        news=_lines([_exchange(e) if e["kind"] == "operator_answered" else {k: v for k, v in e.items() if k != "wall_t"}
                     for e in new if e["kind"] in NEWS]),
        step=_lines([{"step": step, "of_budget": max_steps}, _now(mission_t)]))


class HarnessRenderer(ContextRenderer):
    """OpenRAL's renderer slot filled with the harness context (ReasonerCore calls `render` each tick)."""

    def __init__(self, store, max_steps: int, clock):
        super().__init__()
        self.store, self.max_steps, self.step, self.clock = store, max_steps, 0, clock
        self.rendered = None  # no_context: how many events the conversation has seen; None = a new session

    def render(self, *, world_state=None) -> str:
        if ablation.VARIANT == "no_context":
            f, events, first = self.store.facts, self.store.events, self.rendered is None
            text = (start_text(f, self.step, self.max_steps, self.clock()) if first
                    else result_text(f, self.step, self.max_steps, events[self.rendered:], self.clock()))
            self.rendered = len(events)
            return text
        return step_text(self.store.facts, self.step, self.max_steps, self.store.events, self.clock())
