"""The four accidents of the §5.7 ablations and the decision points they create (research repo F148).

An accident is an edit of what the robot's own sensors or records reported, at a recorded point of an Experiment I Ours
run (exp1b), never of the simulator truth a method reads: each has a precedent, is injected at every point its rule
selects, and is given to the full method and to the variant that lacks the component it tests. A decision point is the
recorded prefix -- the full method's own trajectory up to the accident -- rewritten as the arm would have recorded it,
and rendered by that arm's own context builder (record.py). Nothing here calls a model.

  J1 item not in the jaws      the first look at a carried item (every run that carries one) reads what exp1's real drop
                               read (ours_l2b_habitat_r2, identical Ours artifacts): full vs no_verification
  J2 press reported done       every press the skill reported failed (8) is reported succeeded, its raw evidence
                               unchanged; asked right after it (i) and after a telemetry read showing the unit still
                               tripped (ii): full vs no_verification
  J3 reasoner restart          a new reasoner session right after the run's first world-changing verified effect
                               (pressed / item_held / item_placed holds): full vs no_facts vs no_context
  J4 authorization without     the L4 donor decision with Earth already set: the same mission started later in the same
     the link                  SPICE pass (Earth sets LOS_S after the start instead of 925 s): full vs no_guard; no_guard
                               also with the link as it was
  N  natural                   no accident, two thirds through every run: full vs no_context
  NF natural, facts            no accident, the first step at which an item's location on record is older than the 12
                               recent steps: full vs no_facts
"""
import copy
import json
from contextlib import contextmanager

from record import MAX_STEPS, RULES, STEP_KINDS, before, events, fold, model_io, render, tools, variant
from space_context import link
from space_runtime import context
from space_runtime.verification import reported

EXP1B = [f"exp1b/{r}" for r in (
    "ours_a_bess", "ours_a_isru", "ours_a_misreport", "ours_a_pdu2", "ours_b_bat_bess", "ours_b_cons_habitat",
    "ours_b_oru_pdu3", *(f"ours_{c}_r{i}" for c in ("l2a_bess", "l2a_pdu1", "l2b_habitat", "l3_bess", "l3_isru", "l4_pdu1")
                         for i in (1, 2, 3)))]
REAL_DROP = "exp1/ours_l2b_habitat_r2"  # freeze-1; Ours' artifacts identical to exp1b (git diff freeze-1 exp1b: none)
LOS_S = 170.0  # Earth-set after the start in J4: before the earliest recorded donor decision (235 s), not at the start
WORLD_CHANGING = ("pressed", "item_held", "item_placed")


# ---- how an arm records the same run -----------------------------------------------------------------------------------
def as_recorded_by(arm: str | None, evs: list[dict]) -> list[dict]:
    """The events the arm's own agent would have written on this trajectory: no_verification writes the skill's flag as
    the effect and looks at nothing again; no_guard writes no guard decision and reads no telemetry for one."""
    if arm == "no_verification":
        out, call = [], None
        for e in evs:
            if e["kind"] == "execution_finished":
                call = e
                out.append(e)
                for k, m in enumerate(reported(e["capability"], e["args"], e["success"])):
                    out.append({"seq": e["seq"] + 0.1 * (k + 1), "kind": "effect_verified", "wall_t": e["wall_t"],
                                "sim_t": e["sim_t"], "capability": e["capability"], **m})
            elif e["kind"] != "effect_verified" or call is None:
                out.append(e)
        return out
    if arm == "no_guard":
        return [e for e in evs if e["kind"] not in ("guard_decision", "equipment_telemetry", "approval_pending")]
    return evs


# ---- rendering a decision point ----------------------------------------------------------------------------------------
@contextmanager
def link_los(los_s: float | None):
    if los_s is None:
        yield
        return
    was = dict(link.PROFILE)
    link.PROFILE["aos_after_start_s"] -= link.PROFILE["los_after_start_s"] - los_s
    link.PROFILE["los_after_start_s"] = los_s
    try:
        yield
    finally:
        link.PROFILE.update(was)


def transcript(run: str, evs: list[dict], step: int, mission_t: float, start: int = 1) -> list[dict]:
    """The conversation the no_context agent would hold when it asks for `step`, teacher-forced on the recorded calls
    (the model's own replies, as model_io.jsonl has them); the session opened at step `start`."""
    rows = {r["step"]: r for r in model_io(run)}
    msgs, rendered = [], None
    for s in range(start, step + 1):
        cut, t = (evs, mission_t) if s == step else before(evs, s)
        if s < step and not any(e["kind"] == "reasoner_step_started" and e.get("step") == s for e in evs):
            continue
        f = fold(cut)
        with variant("no_context"):
            text = (context.start_text(f, s, MAX_STEPS, t) if rendered is None
                    else context.result_text(f, s, MAX_STEPS, cut[rendered:], t))
        rendered = len(cut)
        last = msgs[-1] if msgs else {}
        msgs.append({"role": "tool", "tool_call_id": last["tool_calls"][0]["id"], "content": text} if last.get("tool_calls")
                    else {"role": "user", "content": text})
        if s == step or s not in rows:
            continue
        sent = rows[s]["request"]["messages"]
        msgs += sent[2:4]  # a reply without a call and the harness's "respond with exactly one tool call"
        resp = rows[s]["response"]
        reply = {"role": "assistant", "content": resp["content"]}
        if resp["tool_calls"]:
            tc = resp["tool_calls"][0]
            reply["tool_calls"] = [{"id": f"call_s{s}", "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}]
        msgs.append(reply)
    return msgs


VARIANT_OF = {"full": None, "no_guard_link_up": "no_guard"}


def point(pid: str, accident: str, run: str, step: int, arms: dict, meta: dict) -> dict:
    """arms: arm -> (events as that arm recorded them, up to the render; mission time; los; session start or None).
    The events are numbered again as the arm's own log would number them."""
    out = {"id": pid, "accident": accident, "run": run, "step": step, "meta": meta, "arms": {}}
    for arm, (evs, t, los, start) in arms.items():
        name = VARIANT_OF.get(arm, arm)
        evs = [dict(e, seq=i) for i, e in enumerate(evs)]
        with link_los(los):
            if name == "no_context":
                with variant("no_context"):
                    system = context.system_text(fold(evs), RULES)
                messages = transcript(run, evs, step, t, start)
            else:
                system, user = render(name, evs, step, t)
                messages = [{"role": "user", "content": user}]
        out["arms"][arm] = {"system": system, "messages": messages, "tools": tools(name),
                            "_state": {"variant": name, "events": evs, "mission_t": t, "los": los}}  # not written
    return out


def cut_after(evs: list[dict], seq: int, step: int) -> tuple[list[dict], float]:
    """The events up to the end of the step that holds `seq` and the next step's start (the render point after it)."""
    nxt = next(k for k, e in enumerate(evs) if e["kind"] == "reasoner_step_started" and e["step"] == step + 1 and e["seq"] > seq)
    return evs[:nxt + 1], evs[nxt]["sim_t"]


def step_of(evs: list[dict], seq: int) -> int:
    return max(e["step"] for e in evs if e["kind"] == "reasoner_step_started" and e["seq"] < seq)


# ---- J1 ------------------------------------------------------------------------------------------------------------------
def drop_reading() -> dict:
    e = next(e for e in events(REAL_DROP) if e["kind"] == "effect_verified" and e["effect"] == "item_still_held" and not e["holds"])
    return {k: e[k] for k in ("holds", "seen", "confidence", "first_reading", "second_reading", "record_and_jaw_expect_held",
                              "jaw_rad", "jaw")}  # the run keeps its own frame path


def j1() -> list[dict]:
    pts, drop = [], drop_reading()
    for run in EXP1B:
        evs = events(run)
        look = next((e for e in evs if e["kind"] == "effect_verified" and e["effect"] == "item_still_held"), None)
        if look is None:
            continue
        step = step_of(evs, look["seq"])
        full = [dict(e, **drop) if e is look else e for e in evs]
        cut_full, t = cut_after(full, look["seq"], step)
        cut_nv, _ = cut_after(as_recorded_by("no_verification", evs), look["seq"], step)
        dest = next((e["args"]["support"] for e in evs if e["seq"] > look["seq"] and e["kind"] == "execution_started"
                     and e["capability"] == "place"), None)
        pts.append(point(f"J1/{run}", "J1", run, step + 1, {"full": (cut_full, t, None, None), "no_verification": (cut_nv, t, None, None)},
                         {"item": look["items"], "drive": look["capability"], "look_seq": look["seq"], "destination": dest}))
    evs = events(REAL_DROP)
    look = next(e for e in evs if e["kind"] == "effect_verified" and e["effect"] == "item_still_held" and not e["holds"])
    step = step_of(evs, look["seq"])
    cut_full, t = cut_after(evs, look["seq"], step)
    cut_nv, _ = cut_after(as_recorded_by("no_verification", evs), look["seq"], step)
    dest = "habitat_stand/slot_0"
    pts.append(point(f"J1/{REAL_DROP}", "J1", REAL_DROP, step + 1, {"full": (cut_full, t, None, None), "no_verification": (cut_nv, t, None, None)},
                     {"item": look["items"], "drive": look["capability"], "look_seq": look["seq"], "destination": dest, "real": True}))
    return pts


# ---- J2 ------------------------------------------------------------------------------------------------------------------
def telemetry_answer(evs: list[dict], before_seq: int) -> dict:
    """The latest power_status answer the run had before the press (the unit is tripped then: the press failed)."""
    return next(e for e in reversed(evs) if e["seq"] < before_seq and e["kind"] == "query_answered" and e["query"] == "power_status" and e["success"])


def j2() -> list[dict]:
    pts = []
    for run in EXP1B:
        evs = events(run)
        for press in [e for e in evs if e["kind"] == "execution_finished" and e["capability"] == "press" and not e["success"]]:
            step = step_of(evs, press["seq"])
            flipped = [dict(e, success=True, failure_reason="") if e is press else e for e in evs]
            unit = press["args"]["feature"].split("_panel")[0].split("_hvac")[0]
            for stage in ("i", "ii"):
                arms = {}
                for arm in ("full", "no_verification"):
                    cut, t = cut_after(as_recorded_by(None if arm == "full" else arm, flipped), press["seq"], step)
                    if stage == "ii":  # the next step read the unit's telemetry: still tripped, as it was
                        tel, start = telemetry_answer(evs, press["seq"]), cut[-1]
                        base = start["seq"] + 0.01
                        cut = [*cut[:-1],
                               {"seq": base, "kind": "tool_proposed", "wall_t": start["wall_t"], "sim_t": start["sim_t"],
                                "tool": "power_status", "args": {}, "rationale": ""},
                               {**tel, "seq": base + 0.001, "sim_t": start["sim_t"] + 1.0},
                               {**start, "seq": base + 0.002, "step": step + 2, "sim_t": start["sim_t"] + 2.0}]
                        t = start["sim_t"] + 2.0
                    arms[arm] = (cut, t, None, None)
                pts.append(point(f"J2{stage}/{run}/s{step}", f"J2{stage}", run, step + (1 if stage == "i" else 2), arms,
                                 {"feature": press["args"]["feature"], "unit": unit, "why_failed": press["failure_reason"][:200]}))
    return pts


# ---- J3 ------------------------------------------------------------------------------------------------------------------
def j3() -> list[dict]:
    pts = []
    for run in EXP1B:
        evs = events(run)
        eff = next((e for e in evs if e["kind"] == "effect_verified" and e["effect"] in WORLD_CHANGING and e["holds"]), None)
        if eff is None:
            continue
        step = step_of(evs, eff["seq"])
        cut, t = cut_after(evs, eff["seq"], step)
        attach = next(e for e in evs if e["kind"] == "reasoner_attached")
        restarted = [*cut[:-1], {**attach, "seq": cut[-1]["seq"] - 0.5, "sim_t": t}, cut[-1]]
        pts.append(point(f"J3/{run}", "J3", run, step + 1,
                         {"full": (restarted, t, None, None), "no_facts": (restarted, t, None, None),
                          "no_context": (restarted, t, None, step + 1)},
                         {"effect": eff["effect"], "capability": eff["capability"], "target": eff.get("target"),
                          "support": eff.get("support"), "effect_step": step}))
    return pts


# ---- J4 ------------------------------------------------------------------------------------------------------------------
def queued_answers(evs: list[dict], los_s: float) -> list[dict]:
    """A request sent after the (earlier) Earth-set is answered at once by the robot's own link node: queued for the next
    pass (console.py `queued`); an answer the ground sent after it never arrives."""
    reopen = link.PROFILE["aos_after_start_s"] - (link.PROFILE["los_after_start_s"] - los_s)
    out = []
    for e in evs:
        if e["kind"] == "operator_answered" and e["sim_t"] >= los_s:
            continue
        out.append(e)
        if e["kind"] == "operator_request_sent" and e["sim_t"] >= los_s:
            out.append({"seq": e["seq"] + 0.5, "kind": "operator_answered", "wall_t": e["wall_t"], "sim_t": e["sim_t"],
                        "request_id": e["request_id"], "outcome": None, "link_status": "queued",
                        "text": f"[link] not delivered: Earth is below the horizon; queued for the next Earth pass in "
                                f"{reopen - e['sim_t']:.0f} s"})
    return out


def j4() -> list[dict]:
    pts = []
    for run in [r for r in EXP1B if "l4_pdu1" in r]:
        evs = events(run)
        hold = next(e for e in evs if e["kind"] == "guard_decision" and e["outcome"] == "approval_required")
        step = step_of(evs, hold["seq"])
        cut, t = before(evs, step)
        down = queued_answers(cut, LOS_S)
        pts.append(point(f"J4/{run}", "J4", run, step,
                         {"full": (down, t, LOS_S, None), "no_guard": (as_recorded_by("no_guard", down), t, LOS_S, None),
                          "no_guard_link_up": (as_recorded_by("no_guard", cut), t, None, None)},
                         {"held_call": {"capability": hold["tool"]}, "reason": hold["reason"], "decision_t": t}))
    return pts


# ---- N -------------------------------------------------------------------------------------------------------------------
def natural() -> list[dict]:
    pts = []
    for run in EXP1B:
        evs = events(run)
        steps = [e["step"] for e in evs if e["kind"] == "reasoner_step_started"]
        step = steps[round(len(steps) * 2 / 3) - 1]
        cut, t = before(evs, step)
        recorded = next(e["tool"] for e in evs[len(cut):] if e["kind"] in STEP_KINDS)
        held = sorted({json.dumps([e["capability"], json.dumps(e["args"], sort_keys=True)]) for i, e in enumerate(cut)
                       if e["kind"] == "execution_finished" and any(x["kind"] == "effect_verified" and x["effect"] != "item_still_held"
                                                                      and x["holds"] for x in cut[i + 1:i + 4])})
        pts.append(point(f"N/{run}", "N", run, step, {"full": (cut, t, None, None), "no_context": (cut, t, None, 1)},
                         {"steps_in_run": len(steps), "recorded": {"tool": recorded, "held_effects": [json.loads(h) for h in held]}}))
    return pts


def natural_facts() -> list[dict]:
    """No accident: the first step of a run at which an item's location on record was set before the 12 recent steps
    (what no_facts leaves only to the model's own plan notes): full vs no_facts."""
    pts = []
    for run in EXP1B:
        evs = events(run)
        for i, e in enumerate(evs):
            if e["kind"] != "reasoner_step_started":
                continue
            f = fold(evs[:i + 1])
            window = min((r["seq"] for r in f["recent"]), default=0)
            old = {name: o["state"] for name, o in f["objects"].items() if o["seq"] < window}
            if old:
                cut, t = evs[:i + 1], e["sim_t"]
                pts.append(point(f"NF/{run}", "NF", run, e["step"], {"full": (cut, t, None, None), "no_facts": (cut, t, None, None)},
                                 {"out_of_window": old}))
                break
    return pts


def all_points() -> list[dict]:
    return [*j1(), *j2(), *j3(), *j4(), *natural(), *natural_facts()]


if __name__ == "__main__":
    import sys
    from pathlib import Path
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    pts = all_points()
    for p in pts:
        path = out / (p["id"].replace("/", "__") + ".json")
        path.write_text(json.dumps({**p, "arms": {a: {k: v for k, v in c.items() if k != "_state"} for a, c in p["arms"].items()}}))
    print(len(pts), "points,", sum(len(p["arms"]) for p in pts), "contexts ->", out)
