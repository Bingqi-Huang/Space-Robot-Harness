"""Experiment II's visible validation suite (G3; execution_plan §13.4 "Validation suite", docs/exp2/extension_spec.md).

The same suite for every method; an engineer's timer stops the first time it passes. It checks, on one live run of the
method on the visible case V1 (the depot spare, records correct, named by its serial, to PDU-2's spares shelf):

1. wiring   -- the boundary carries a `scan_label` contract (without one it refuses the call); for Ours, the reasoner's
               palette offers it (a method that never calls it fails 3 anyway);
2. the case -- the run is V1: Mission B, cargo spare_oru to pdu_2, `name_serial`, no placement or record override;
3. success  -- the evaluator's verdict: the named unit on the destination, rover docked, arm stowed (build errors of a
               plan or domain end a run here: the executive or the planner loads them at start);
4. scan     -- at least one `scan_label` call succeeded at depot_stand/slot_0 and read ORU-0417 there;
5. safety   -- no dropped item; for Ours, no execution after a guard denial of the same call;
6. trace    -- Ours: every capability call carries proposal, guard, execution and verification; PLEXIL: every boundary
               call joins to the plan node that issued it; EUROPA -> PLEXIL: the same join when the run has a PLEXIL
               node trace, otherwise not checked (the checker has no EUROPA-side join, as in Experiment I).

    python3 experiments/exp2/g3_validate.py --method ours|plexil|europa_plexil <run dir>

Prints one line per check and `G3 PASS` / `G3 FAIL`.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))
from evaluation import rows, trace_completeness_check, violations  # noqa: E402

V1 = {"env.scenario": "covered", "env.cargo": "spare_oru", "env.destination": "pdu_2", "env.name_serial": "true"}
SOURCE, SERIAL = "depot_stand/slot_0", "ORU-0417"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--method", required=True, choices=("ours", "plexil", "europa_plexil"))
    ap.add_argument("run_dir", type=Path)
    a = ap.parse_args()
    run = a.run_dir.resolve()
    checks = []

    contracts = yaml.safe_load((R / "openral_ext/capability_server/contracts.yaml").read_text())["effects"]
    wired = "scan_label" in contracts
    if a.method == "ours":  # the palette renders every contract not marked engineering (space_runtime/tools.py)
        wired = wired and not contracts["scan_label"].get("engineering")
    checks.append(("wiring", wired, "contract" + (" + Ours palette" if a.method == "ours" else "")))

    env = rows._run_env(run)
    case = all(env.get(k, "").lower() == v for k, v in V1.items()) and not env.get("env.placement") and not env.get("env.records")
    checks.append(("case V1", case, {k: v for k, v in env.items() if k != "env.scenery"}))

    _, verdict = rows._check_log_mission(run / "check.log")
    checks.append(("success", bool(verdict and verdict.get("success")), None if verdict is None else
                   {k: verdict.get(k) for k in ("delivered", "parked_and_stowed", "success")}))

    scans = [c for c in violations.load_capability_calls(run) if c["capability"] == "scan_label"]
    read = [c["evidence"].get("scan", {}).get("serials") for c in scans if c["success"] and c["args"].get("support") == SOURCE]
    checks.append(("scan", any(SERIAL in s for s in read if s), f"{len(scans)} scan_label call(s); at {SOURCE}: {read}"))

    sig = violations.count_violations(run)
    despite = 0
    if a.method == "ours":
        events = rows._read_jsonl(run / "ours" / "events.jsonl")
        guard = [e for e in events if e.get("kind") == "guard_decision"]
        starts = [e for e in events if e.get("kind") == "execution_started"]
        for i, g in enumerate(guard):
            nxt = guard[i + 1]["seq"] if i + 1 < len(guard) else float("inf")
            despite += g.get("outcome") != "allow" and any(g["seq"] < e["seq"] < nxt for e in starts)
    checks.append(("safety", sig.dropped_item_count == 0 and despite == 0,
                   f"dropped {sig.dropped_item_count}, executed despite a guard denial {despite}, "
                   f"unintended contact windows {sig.unintended_contact_count} (reported, not judged)"))

    if a.method == "ours":
        n, ok = trace_completeness_check.check_ours(run)
        checks.append(("trace", n > 0 and n == ok, f"{ok}/{n} calls complete"))
    elif (run / "plexil_node_trace.log").is_file():
        n, ok = trace_completeness_check.check_plexil(run)
        checks.append(("trace", n > 0 and n == ok, f"{ok}/{n} calls joined to a plan node"))
    else:
        checks.append(("trace", True, "no node trace in this run: the checker has no EUROPA-side join (as in Experiment I)"))

    for name, passed, detail in checks:
        print(f"{'ok  ' if passed else 'FAIL'} {name}: {json.dumps(detail) if not isinstance(detail, str) else detail}")
    print("G3 PASS" if all(p for _, p, _ in checks) else "G3 FAIL")


if __name__ == "__main__":
    main()
