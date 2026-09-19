"""PLEXIL universalExec output -> `CommonEvent` (§14.6 trace completeness).

Parses the check.log format `experiments/launch/lunar_base_d0/d0_plexil_mission_a_check.py`
writes (read directly, not guessed): `PLAN`/`EXEC`/`STEP`/`DOCK`/`RESULT` lines, each
`"KIND {json}"`, the same `d0_common.log()` convention every D0 evaluator script uses.
`STEP` lines are themselves reconstructed by that script from `capability_server.log`'s
`"CAPABILITY {...}"` lines (the common boundary's own call trace -- `capability, args,
success, failure_kind, failure_reason, evidence`), so this normalizer can also read
`capability_server.log` directly when `check.log`'s `STEP` lines are absent.

**Node-level trace (§13.2/§14.6)**: `d0_plexil_mission_a_check.py` and
`d0_plexil_operator_check.py` both persist universalExec's full stdout to
`<log_dir>/plexil_node_trace.log` (the `EXEC` line itself keeps only a 4-line tail) --
`baselines/plexil/Debug.cfg` turns on universalExec's own `Node:transition` debug flag, so
that file carries one line per PLEXIL node state transition. When it sits next to
`check_log`, `normalize_plexil_node_trace` turns it into its own `execution_started`
`CommonEvent`s, one per node entering `EXECUTING`, each carrying `plan_node_id` -- a
mechanical read of the trace (node id, timestamp), no attempt to match a node to the
capability it dispatches (that pairing is not represented in `check.log`'s own format
and no per-capability interpretation belongs in a normalizer).

**No real PLEXIL run exists on disk right now** (F52's run "p1" was cleaned up per
AGENT.md's debug-artifact-cleanup rule). This module was verified against a REAL
`capability_server.log` fixture from a non-PLEXIL D0 run (`artifacts/runs/pf1`, same
boundary, same log format) for `STEP`/`CAPABILITY`-line parsing, and against a small
synthetic fixture built to the documented format (clearly labeled synthetic, not a
captured run) for `PLAN`/`EXEC`-line parsing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from evaluation.baselines.common_schema import CommonEvent

__all__ = ["normalize_plexil_check_log", "normalize_plexil_node_trace"]

_LINE_RE = re.compile(r"^([A-Z_]+) (\{.*\})\s*$")
_TRANSITION_RE = re.compile(r"Transitioning (\S+) \S+ from (\S+) to (\S+) at ([\d.]+)")


def normalize_plexil_node_trace(trace_log: Path) -> list[CommonEvent]:
    """One `execution_started` `CommonEvent` per `Node:transition` line landing on `EXECUTING`
    (see module docstring). `t` is universalExec's own plan-relative clock, as the trace line
    carries it -- not resynchronised to `check_log`'s wall/sim clocks."""
    events: list[CommonEvent] = []
    seq = 0
    for line in trace_log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _TRANSITION_RE.search(line)
        if not m or m.group(3) != "EXECUTING":
            continue
        events.append(CommonEvent(kind="execution_started", seq=seq, t=float(m.group(4)), method="plexil",
                                   plan_node_id=m.group(1)))
        seq += 1
    return events


def normalize_plexil_check_log(check_log: Path) -> list[CommonEvent]:
    """One `CommonEvent` per `PLAN`/`EXEC`/`STEP` line in `check_log`, plus every node
    transition in a sibling `plexil_node_trace.log` when one is on disk (see module
    docstring). `DOCK`/`RESULT`/`READY`/`TF`/`PROBE`/`MISSION` lines are evaluator
    bookkeeping, not trace events, and are skipped (same convention `evaluation/rows.py`
    uses for `check.log`)."""
    events: list[CommonEvent] = []
    seq = 0
    for line in check_log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        tag, body = m.group(1), m.group(2)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        t = data.get("t", 0.0)
        if tag == "PLAN":
            events.append(CommonEvent(kind="plan_started", seq=seq, t=t, method="plexil",
                                       args={"executive": data.get("executive"), "plan": data.get("plan")}))
        elif tag == "EXEC":
            events.append(CommonEvent(kind="plan_finished", seq=seq, t=t, method="plexil",
                                       success=(data.get("exit") == 0),
                                       evidence={"wall_s": data.get("wall_s"), "sim_s": data.get("sim_s"), "tail": data.get("tail")}))
        elif tag == "STEP":
            events.append(CommonEvent(kind="execution_finished", seq=seq, t=t, method="plexil",
                                       capability=data.get("name"), success=data.get("success"),
                                       failure_reason=data.get("failure_reason"), args=data.get("args"),
                                       evidence={"n": data.get("n"), "sim_s": data.get("sim_s"), "failure_kind": data.get("failure_kind")}))
        else:
            continue
        seq += 1
    trace_log = check_log.parent / "plexil_node_trace.log"
    if trace_log.exists():
        for e in normalize_plexil_node_trace(trace_log):
            events.append(e.model_copy(update={"seq": seq}))
            seq += 1
    return events


def normalize_capability_server_log(log: Path, *, method: str = "plexil") -> list[CommonEvent]:
    """One `execution_finished` `CommonEvent` per `"CAPABILITY {...}"` line -- the common
    boundary's own trace (`openral_ext/capability_server/node.py`), shared by every
    method that dispatches through it. Usable directly when `check.log`'s reconstructed
    `STEP` lines are not available."""
    events: list[CommonEvent] = []
    seq = 0
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "CAPABILITY " not in line:
            continue
        try:
            data = json.loads(line.split("CAPABILITY ", 1)[1])
        except (json.JSONDecodeError, IndexError):
            continue
        events.append(CommonEvent(kind="execution_finished", seq=seq, t=float(seq), method=method,
                                   capability=data.get("capability"), success=data.get("success"),
                                   failure_reason=data.get("failure_reason"), args=data.get("args"),
                                   evidence=data.get("evidence")))
        seq += 1
    return events
