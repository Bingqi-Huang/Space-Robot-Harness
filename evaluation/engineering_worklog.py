"""Experiment II engineering timer -- execution_plan.md §13.4 Timer policy.

"record session start/stop explicitly in `engineering_worklog.jsonl`... do not
reconstruct timing from git commit timestamps." A start/stop/note CLI, stateless
across invocations (each subcommand is a separate process): `stop`/`note` act on the
most recent `session_start` in the log that has no matching `session_stop` yet --
there is deliberately no separate lock/state file to go stale.

ETVS (§14.4) = sum of active session durations from extension-spec release until the
common validation suite first passes -- `total_active_seconds()` computes that from
whatever sessions are in the log; it does not itself know when the suite passed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import uuid
from pathlib import Path
from typing import Any

__all__ = ["start_session", "stop_session", "add_note", "read_log", "total_active_seconds"]


def _now() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()


def _append(log_path: Path, event: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def read_log(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _open_session_id(log_path: Path) -> str | None:
    """The most recent `session_start` with no `session_stop` naming its id yet, or `None`."""
    events = read_log(log_path)
    stopped = {e["session_id"] for e in events if e["kind"] == "session_stop"}
    for e in reversed(events):
        if e["kind"] == "session_start" and e["session_id"] not in stopped:
            return e["session_id"]
    return None


def start_session(log_path: Path, *, extension_id: str, method: str, engineer: str) -> str:
    if _open_session_id(log_path) is not None:
        msg = "a session is already open -- stop it before starting another (one timer at a time, §13.4)"
        raise RuntimeError(msg)
    session_id = uuid.uuid4().hex[:12]
    _append(log_path, {"kind": "session_start", "session_id": session_id, "t": _now(),
                        "extension_id": extension_id, "method": method, "engineer": engineer})
    return session_id


def stop_session(log_path: Path, *, reason: str = "") -> str:
    session_id = _open_session_id(log_path)
    if session_id is None:
        msg = "no open session to stop"
        raise RuntimeError(msg)
    _append(log_path, {"kind": "session_stop", "session_id": session_id, "t": _now(), "reason": reason})
    return session_id


def add_note(log_path: Path, text: str) -> None:
    session_id = _open_session_id(log_path)  # notes attach to the open session when there is one, else stand alone
    _append(log_path, {"kind": "note", "session_id": session_id, "t": _now(), "text": text})


def total_active_seconds(log_path: Path, *, extension_id: str | None = None) -> float:
    """§14.4 ETVS building block: sum of every closed (`session_start`, `session_stop`) pair's
    duration, optionally filtered to one `extension_id`. An still-open session (no matching
    `session_stop`) is not counted -- it has not been closed yet, its duration is not yet known."""
    events = read_log(log_path)
    starts = {e["session_id"]: e for e in events if e["kind"] == "session_start"}
    total = 0.0
    for e in events:
        if e["kind"] != "session_stop":
            continue
        start = starts.get(e["session_id"])
        if start is None or (extension_id is not None and start.get("extension_id") != extension_id):
            continue
        t0 = datetime.datetime.fromisoformat(start["t"])
        t1 = datetime.datetime.fromisoformat(e["t"])
        total += (t1 - t0).total_seconds()
    return round(total, 3)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", type=Path, default=Path("engineering_worklog.jsonl"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("--extension-id", required=True)
    p_start.add_argument("--method", required=True, choices=("ours", "plexil", "europa_plexil"))
    p_start.add_argument("--engineer", required=True)

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("--reason", default="")

    p_note = sub.add_parser("note")
    p_note.add_argument("text")

    p_total = sub.add_parser("total")
    p_total.add_argument("--extension-id", default=None)

    args = ap.parse_args()
    if args.cmd == "start":
        print(start_session(args.log, extension_id=args.extension_id, method=args.method, engineer=args.engineer))
    elif args.cmd == "stop":
        print(stop_session(args.log, reason=args.reason))
    elif args.cmd == "note":
        add_note(args.log, args.text)
    elif args.cmd == "total":
        print(total_active_seconds(args.log, extension_id=args.extension_id))


if __name__ == "__main__":
    main()
