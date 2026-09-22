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

**Exercised against two real PLEXIL runs (2026-09-22, F107)**: `plexil_mission_a_success_20260922`,
`plexil_mission_b_success_20260922`. Found and fixed two real bugs neither the original
`capability_server.log` fixture nor the synthetic `PLAN`/`EXEC` fixture could have caught, since both
need a real run's *combination* of files:
  - `check.log`'s `STEP` lines all carry the *same* `t`: `d0_plexil_mission_a_check.py` writes every one
    in a single post-hoc loop over `capability_server.log`, run *after* `universalExec` has already
    exited -- not each capability's own completion time. `normalize_plexil_check_log` no longer reads
    them; `capability_server.log` (real per-call epoch, `normalize_capability_server_log`) is the one
    source of per-capability timing.
  - `normalize_capability_server_log` itself discarded the log line's own epoch prefix and stamped
    `t=float(seq)` -- a placeholder, not a bug anyone had reason to suspect until it was compared against
    real node-trace timestamps. Fixed to parse the real `[INFO] [<epoch>] ...` prefix (same regex
    `evaluation/violations.py` already uses for the identical log line shape).
  - With both fixed, `capability_server.log` (now real epoch) and `plexil_node_trace.log` (already real
    epoch) are sorted together by that shared clock -- not appended as two separate un-interleaved runs
    the way this file first merged them (silently wrong order between calls and node transitions, only
    visible once real events from both files existed side by side). `PLAN`/`EXEC` keep `check.log`'s own
    wall-since-script-start `t`: they bracket the mission structurally (nothing precedes `PLAN`, nothing
    follows `EXEC`), so no cross-timebase alignment is needed for those two to sort correctly regardless.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from evaluation.baselines.common_schema import CommonEvent

__all__ = ["normalize_plexil_check_log", "normalize_plexil_node_trace", "normalize_capability_server_log"]

_LINE_RE = re.compile(r"^([A-Z_]+) (\{.*\})\s*$")
_TRANSITION_RE = re.compile(r"Transitioning (\S+) \S+ from (\S+) to (\S+) at ([\d.]+)")
_CAP_LOG_RE = re.compile(r"^\[INFO\] \[(?P<t>\d+\.\d+)\] \[space_capability_server\]: CAPABILITY (?P<json>\{.*\})\s*$")


def normalize_plexil_node_trace(trace_log: Path) -> list[CommonEvent]:
    """One `execution_started` `CommonEvent` per `Node:transition` line landing on `EXECUTING`
    (see module docstring). `t` is the real wall-clock epoch the trace line itself carries
    (universalExec's own `Node:transition` debug output, not resynchronised to anything) --
    directly comparable to `normalize_capability_server_log`'s `t` (the same kind of epoch,
    read from the same machine during the same run), which is what `normalize_plexil_check_log`
    sorts them together by. NOT comparable to `check_log`'s own `PLAN`/`EXEC` `t` (wall-since-
    script-start, a different origin)."""
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


def normalize_capability_server_log(log: Path, *, method: str = "plexil") -> list[CommonEvent]:
    """One `execution_finished` `CommonEvent` per `"CAPABILITY {...}"` line -- the common
    boundary's own trace (`openral_ext/capability_server/node.py`), shared by every
    method that dispatches through it. `t` is the log line's own real wall-clock epoch
    prefix (`[INFO] [<epoch>] [space_capability_server]: CAPABILITY {...}`, the same shape
    `evaluation/violations.py`'s `_CAPABILITY_LOG_RE` reads) -- the one source of genuine
    per-capability timing (`check_log`'s own `STEP` lines, reconstructed from this same log
    by a post-hoc dump loop that runs after `universalExec` has already exited, all carry
    that loop's *one* moment, not each call's -- confirmed against two real runs, F107)."""
    events: list[CommonEvent] = []
    seq = 0
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _CAP_LOG_RE.match(line)
        if not m:
            continue
        data = json.loads(m.group("json"))
        events.append(CommonEvent(kind="execution_finished", seq=seq, t=float(m.group("t")), method=method,
                                   capability=data.get("capability"), success=data.get("success"),
                                   failure_reason=data.get("failure_reason"), args=data.get("args"),
                                   evidence=data.get("evidence")))
        seq += 1
    return events


def normalize_plexil_check_log(check_log: Path) -> list[CommonEvent]:
    """`PLAN`/`EXEC` bookkeeping from `check_log` (its own wall-since-script-start `t` --
    kept only for these two, which bracket the mission structurally: nothing precedes
    `PLAN`, nothing follows `EXEC`, so no cross-timebase alignment is needed for them to
    sort correctly), interleaved with the actual execution trace -- every capability call
    (`capability_server.log`, real epoch) and, when a sibling `plexil_node_trace.log` is on
    disk, every node transition (also real epoch) -- sorted by that shared real clock.
    `check_log`'s own `STEP`/`DOCK`/`RESULT`/`READY`/`TF`/`PROBE`/`MISSION` lines are not
    read: `STEP` carries no real per-call timing (see `normalize_capability_server_log`),
    the rest are evaluator bookkeeping, not trace events (same convention
    `evaluation/rows.py` uses for `check.log`)."""
    plan_event, exec_event = None, None
    for line in check_log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line)
        if not m or m.group(1) not in ("PLAN", "EXEC"):
            continue
        try:
            data = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        t = data.get("t", 0.0)
        if m.group(1) == "PLAN":
            plan_event = CommonEvent(kind="plan_started", seq=0, t=t, method="plexil",
                                      args={"executive": data.get("executive"), "plan": data.get("plan")})
        else:
            exec_event = CommonEvent(kind="plan_finished", seq=0, t=t, method="plexil",
                                      success=(data.get("exit") == 0),
                                      evidence={"wall_s": data.get("wall_s"), "sim_s": data.get("sim_s"), "tail": data.get("tail")})

    cap_log = check_log.parent / "capability_server.log"
    trace_log = check_log.parent / "plexil_node_trace.log"
    trace_events = (normalize_capability_server_log(cap_log) if cap_log.exists() else []) + \
                   (normalize_plexil_node_trace(trace_log) if trace_log.exists() else [])
    trace_events.sort(key=lambda e: e.t)

    events: list[CommonEvent] = []
    seq = 0
    for e in ([plan_event] if plan_event else []) + trace_events + ([exec_event] if exec_event else []):
        events.append(e.model_copy(update={"seq": seq}))
        seq += 1
    return events
