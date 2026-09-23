"""EUROPA->PLEXIL `host.py` output -> `CommonEvent` (§14.6 trace completeness) -- the schema slot
`common_schema.py`'s `token_id` field and `method="europa_plexil"` already anticipated but nothing
populated (`plexil_normalize.py`'s own module docstring: "no EUROPA baseline exists yet"). One now
exists (F105, F106); this reads its `events.jsonl` directly.

Unlike PLEXIL's logs (`plexil_normalize.py`'s own module docstring), `host.py` already stamps every
line with a real wall-clock epoch (`wall_t`, plain `time.time()`) -- no reconstruction needed, and every
event this module emits sorts correctly by `t` with no separate log to interleave.

EUROPA has no fixed node graph the way PLEXIL's `.plx` does (`europa_mission_video.py`'s own docstring:
"EUROPA has no fixed plan graph to draw a cursor through"): every unmet goal gets a fresh `solve()`, and
the solver's own derived activity sequence *is* the closest thing to PLEXIL's per-node `plan_node_id` --
so `token_id` here is `"LunarBot.<action>"`, the activity name a `plan` event's own `activities` list
carries (`host.py`'s own NDDL action names, `domain/mission-{a,b}-model.nddl`), not a per-instance id
(matching PLEXIL's `plan_node_id`, itself a name, not a unique instance id either).

Mapping (`host.py`'s own event kinds, read directly, not guessed -- `europa_mission_video.py`'s
`europa_timeline()` reads the identical five):
  - `mission`  -> `plan_started`  (once per run; `args={goals}`, the mission's own fixed outcomes)
  - `plan`     -> `plan_started`  (once per replan -- a genuinely fresh derivation, not an update to the
                  previous one; `args={n, solved, steps, activities}`, the solver's own output whole)
  - `dispatch` -> `execution_started`  (`token_id` = `"LunarBot.<capability>"` from the *current* plan's
                  activity list, matched by capability name -- best-effort: `host.py` dispatches activities
                  in the order the plan lists them, so the first not-yet-dispatched match is correct for
                  every real run inspected, F107; ambiguous only if a plan repeats one capability twice with
                  no way to tell dispatch order apart, not observed)
  - `result`   -> `execution_finished`  (`evidence={state, as_planned}` -- `state` is EUROPA's own post-call
                  fact dict, `as_planned` whether the capability's own after-state matched what the plan
                  expected, both genuine, not derived)
  - `done`     -> `plan_finished`  (`success=True` -- `host.py` only ever emits `done` on a genuinely met
                  mission; `evidence={state}`)
  - `no_plan`  -> `plan_finished`  (`success=False` -- the solver could not find one and `host.py` escalated
                  to the operator instead of dispatching anything; no evidence beyond the fact itself)
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.baselines.common_schema import CommonEvent

__all__ = ["normalize_europa_events"]


def _token_for(capability: str, activities: list) -> str | None:
    """`"LunarBot.<capability>"` if `capability` names one of `activities`' own action types
    (`[["LunarBot.navigate_to_feature", {...}], ...]`, `host.py`'s own `plan` event shape), else `None`
    (a dispatch this normalizer cannot place against a plan it has seen -- never guessed)."""
    for act, _params in activities:
        if act.rsplit(".", 1)[-1] == capability:
            return act
    return None


def normalize_europa_events(events_jsonl: Path) -> list[CommonEvent]:
    """One `CommonEvent` per line of `host.py`'s own `events.jsonl` (see module docstring for the
    mapping). Lines this normalizer does not recognize (there are none as of F105/F106's five kinds,
    but a future host.py addition is not silently dropped) raise, matching `evaluation/violations.py`'s
    own rule: this is the evaluator's own file, a line it cannot place is a bug worth raising on."""
    events: list[CommonEvent] = []
    activities: list = []  # the most recent `plan` event's own activity list, for `dispatch` -> token_id
    seq = 0
    for line in events_jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        kind, t = data["kind"], data["wall_t"]
        if kind == "mission":
            events.append(CommonEvent(kind="plan_started", seq=seq, t=t, method="europa_plexil",
                                       args={"goals": data.get("goals")}))
        elif kind == "plan":
            activities = data.get("activities") or []
            events.append(CommonEvent(kind="plan_started", seq=seq, t=t, method="europa_plexil",
                                       args={"n": data.get("n"), "solved": data.get("solved"), "steps": data.get("steps"),
                                             "activities": activities}))
        elif kind == "dispatch":
            cap = data.get("capability")
            events.append(CommonEvent(kind="execution_started", seq=seq, t=t, method="europa_plexil",
                                       capability=cap, args=data.get("args"), token_id=_token_for(cap, activities)))
        elif kind == "result":
            events.append(CommonEvent(kind="execution_finished", seq=seq, t=t, method="europa_plexil",
                                       capability=data.get("capability"), success=data.get("success"),
                                       failure_reason=data.get("failure_reason"),
                                       evidence={"state": data.get("state"), "as_planned": data.get("as_planned")}))
        elif kind == "done":
            events.append(CommonEvent(kind="plan_finished", seq=seq, t=t, method="europa_plexil",
                                       success=True, evidence={"state": data.get("state")}))
        elif kind == "no_plan":
            events.append(CommonEvent(kind="plan_finished", seq=seq, t=t, method="europa_plexil", success=False))
        else:
            msg = f"{events_jsonl}: unrecognized host.py event kind {kind!r} -- host.py added something this normalizer does not know about"
            raise ValueError(msg)
        seq += 1
    return events
