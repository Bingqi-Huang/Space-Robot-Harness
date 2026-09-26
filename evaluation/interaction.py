"""Human-interaction measures of one run -- research repo docs/heldout_design.md §8; NIST SP 1011-II-1.0 (ALFUS Human
Independence), Steinfeld et al. HRI 2006 (intervention response time), Olsen & Goodrich PerMIS 2003 (neglect time).

Identical for every method: read from mission control's own log (`<run_dir>/operator/events.jsonl`,
experiments/operator_console/console.py) and the shared capability boundary's call windows (`capability_server.log`,
mission time `sim_t_start`/`sim_t_end`). Mission time is the simulator clock throughout; the mission spans the first
capability call's start to the later of the last one's end and the last exchange of a request with mission control: a
method that stops and asks the ground after its last call is still in its mission while it waits (the baselines' escalations; ending the mission
at the last call gave a ratio of 2.2 and no waiting at all, F132).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: ALFUS level of human interaction, most autonomous first (NIST SP 1011-II-1.0 §4)
ALFUS_ORDER = ("mission", "strategic_goal", "tactical_goal", "mission_task", "route", "autopilot", "servo")
_CAPABILITY_LOG_RE = re.compile(r"\[space_capability_server\]: CAPABILITY (?P<json>\{.*\})\s*$")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []


def call_windows(run_dir: Path) -> list[tuple[float, float]]:
    """[start, end] mission time of every completed capability call."""
    path = run_dir / "capability_server.log"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(errors="replace").splitlines():
        m = _CAPABILITY_LOG_RE.search(line)
        if m:
            c = json.loads(m.group("json"))
            out.append((c["sim_t_start"], c["sim_t_end"]))
    return out


def _merge(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The union of intervals as disjoint, sorted intervals."""
    out: list[list[float]] = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _covered(intervals: list[tuple[float, float]], lo: float, hi: float) -> float:
    """Length of [lo, hi] covered by the union of `intervals`."""
    return sum(max(0.0, min(b, hi) - max(a, lo)) for a, b in _merge(intervals))


def measures(run_dir: Path) -> dict[str, Any]:
    ev = _read_jsonl(run_dir / "operator" / "events.jsonl")
    calls = call_windows(run_dir)
    starts = {e["interaction_id"]: e for e in ev if e["kind"] == "interaction_start"}
    ends = {e["interaction_id"]: e for e in ev if e["kind"] == "interaction_end"}
    delivered = {e["interaction_id"]: e["mission_t"] for e in ev if e["kind"] == "reply_delivered"}
    # requests whose message or answer the link held (not the final report, which is no request); one never delivered to
    # the ground has no interaction_start and is open from its queuing on
    queued = [e for e in ev if e["kind"] == "link_queued" and e["type"] == "request_operator"]
    requests = [i for i, s in starts.items() if s["type"] == "request_operator"]
    unsent = [q for q in queued if q["request_id"] not in {starts[i]["request_id"] for i in requests}]
    exchanges = [e["mission_t"] for e in ev if e.get("interaction_id") in requests] + [q["mission_t"] for q in queued]
    mission = (min(a for a, _ in calls), max([b for _, b in calls] + exchanges)) if calls else None
    elapsed = mission[1] - mission[0] if mission else None

    # each request's segments (Steinfeld et al. 2006): delivery to the ground, ground decision (notice + planning,
    # scripted as one), delivery back; execution after the answer is the method's own and shows in its trace
    segments = [dict(interaction_id=i, kind=starts[i].get("request_kind") or ("authorization" if starts[i]["pending_approvals"] else "new_procedure"),
                     sent=starts[i]["sent_mission_t"], uplink_s=round(starts[i]["mission_t"] - starts[i]["sent_mission_t"], 2),
                     decision_s=round(ends[i]["mission_t"] - starts[i]["mission_t"], 2) if i in ends else None,
                     downlink_s=round(delivered[i] - ends[i]["mission_t"], 2) if i in delivered and i in ends else None,
                     outcome=ends[i]["outcome"] if i in ends else None)
                for i in requests]
    # time with a request open: from sending it to its answer arriving (or the run's end when none arrived)
    end_t = mission[1] if mission else None
    open_windows = [(s["sent"], delivered.get(s["interaction_id"], end_t)) for s in segments if end_t is not None]
    open_windows += [(q["mission_t"], end_t) for q in unsent if end_t is not None]
    open_union = _merge([(max(a, mission[0]), min(b, mission[1])) for a, b in open_windows]) if mission else []
    open_s = sum(b - a for a, b in open_union) if mission else None
    # waiting idle: a request open and no capability executing
    idle_s = sum((b - a) - _covered(calls, a, b) for a, b in open_union) if mission else None
    # neglect time (Olsen & Goodrich): the longest stretch of the mission with no request open
    edges = [mission[0], *(t for w in open_union for t in w), mission[1]] if mission else []
    free = [edges[k + 1] - edges[k] for k in range(0, len(edges) - 1, 2)]
    levels = [ends[i]["authority_level"] for i in requests if i in ends and ends[i]["authority_level"]]

    return dict(
        mission_elapsed_s=round(elapsed, 1) if elapsed else None,
        requests_authorization=sum(s["kind"] == "authorization" for s in segments),
        requests_authority_check=sum(s["kind"] == "authority_check" for s in segments),
        requests_new_procedure=sum(s["kind"] == "new_procedure" for s in segments),
        requests_information=sum(s["kind"] == "information" for s in segments),
        requests_queued_by_link=len(queued),
        grants=sum(s["outcome"] == "grant" for s in segments),
        denials=sum(s["outcome"] == "deny" for s in segments),
        ground_reauthoring_required=any(e.get("ground_reauthoring_required") for e in (*ends.values(), *queued)),
        # ALFUS: ratio of human intervention time (ground decision time) to mission time
        human_intervention_ratio=round(sum(s["decision_s"] or 0.0 for s in segments) / elapsed, 4) if elapsed else None,
        # the most human-directed level mission control acted at (ALFUS order runs from mission to servo)
        highest_interaction_level=max(levels, key=ALFUS_ORDER.index) if levels else None,
        interaction_levels=sorted(set(levels), key=ALFUS_ORDER.index),
        request_segments=segments,
        open_request_fraction=round(open_s / elapsed, 4) if elapsed else None,
        idle_waiting_fraction=round(idle_s / elapsed, 4) if elapsed else None,
        longest_autonomous_stretch_s=round(max(free), 1) if mission else None,
    )
