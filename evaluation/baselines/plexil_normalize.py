"""PLEXIL universalExec output -> `CommonEvent` (§14.6 trace completeness).

Parses the check.log format `experiments/launch/lunar_base_d0/d0_plexil_mission_a_check.py`
writes (read directly, not guessed): `PLAN`/`EXEC`/`STEP`/`DOCK`/`RESULT` lines, each
`"KIND {json}"`, the same `d0_common.log()` convention every D0 evaluator script uses.
`STEP` lines are themselves reconstructed by that script from `capability_server.log`'s
`"CAPABILITY {...}"` lines (the common boundary's own call trace -- `capability, args,
success, failure_kind, failure_reason, evidence`), so this normalizer can also read
`capability_server.log` directly when `check.log`'s `STEP` lines are absent.

**Known limitation, stated honestly**: `d0_plexil_mission_a_check.py` captures
universalExec's own stdout (`exec_out`) but only logs `tail=[...][-4:]` -- the last
4 lines -- in the `EXEC` line. Full PLEXIL node-transition output (State:
WAITING/EXECUTING/... per plan node) is never persisted to disk by that script today,
so `plan_node_id` is `None` on every event this normalizer produces -- there is no
node-level PLEXIL data anywhere on disk to recover it from. Capability-level
Command/Lookup traffic (what `STEP`/`CAPABILITY` lines carry) IS recovered.

**No real PLEXIL run exists on disk right now** (F52's run "p1" was cleaned up per
AGENT.md's debug-artifact-cleanup rule) -- `smoke_test_logic.py` tests the
`STEP`/`CAPABILITY`-line parsing against a REAL `capability_server.log` fixture from a
non-PLEXIL D0 run (`artifacts/runs/pf1`, same boundary, same log format) and the
`PLAN`/`EXEC`-line parsing against a small synthetic fixture built to the documented
format, clearly labeled synthetic, not presented as a captured run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from evaluation.baselines.common_schema import CommonEvent

__all__ = ["normalize_plexil_check_log"]

_LINE_RE = re.compile(r"^([A-Z_]+) (\{.*\})\s*$")


def normalize_plexil_check_log(check_log: Path) -> list[CommonEvent]:
    """One `CommonEvent` per `PLAN`/`EXEC`/`STEP` line in `check_log`. `DOCK`/`RESULT`/
    `READY`/`TF`/`PROBE`/`MISSION` lines are evaluator bookkeeping, not trace events, and
    are skipped (same convention `evaluation/rows.py` uses for `check.log`)."""
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
