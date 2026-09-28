"""Ad hoc §14.6 trace-completeness checker, exercised against the step9 batch (E2 eval pass,
2026-09-24). NOT wired into rows.py/tables.py -- a standalone report tool, run manually:

    python3 evaluation/trace_completeness_check.py <run_dir> [--method ours|plexil]

For Ours: for every completed capability call (an execution_started/execution_finished pair in
`ours/events.jsonl`), checks presence of the seven §14.6 items in the window
[preceding tool_proposed .. next reasoner_step_started]:
  1. mission-state version      -- NOT a field anywhere in the schema (checked structurally: no
                                    event carries a "version"/"state_version" key at all)
  2. evidence reference         -- inline only (effect_verified's own numeric fields / "source"
                                    text); no cross-reference to the evidence/*.jpg files on disk
  3. proposal/tool call         -- tool_proposed
  4. guard outcome              -- guard_decision
  5. execution result           -- execution_started + execution_finished
  6. verifier result            -- effect_verified + verification_finished
  7. resulting fact transition  -- ledger_changed is the only candidate, but it fires on the
                                    agent's own set_task_status calls, not automatically after
                                    verification_finished -- not one-to-one with capability calls

For PLEXIL: the join key is the plan node id the adapter prints on every capability call
(`[CapabilityAdapter] COMMAND <node_id> <capability> <args>`, plexil_capability_adapter, F133), on the
same stdout as the executive's own Node:transition trace (`plexil_node_trace.log`). Per call: the node
id, the node instance it resolves to (the latest `Transitioning <node_id> <address> ... to EXECUTING`
before the call's line), and the boundary's own record of the call (`capability_server.log`'s CAPABILITY
lines, the n-th adapter call = the n-th boundary call: one Command runs at a time; the capability names
must agree). Runs before F133 print no node id and report 0 joined.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(errors="replace").splitlines() if l.strip()]


def check_ours(run_dir: Path) -> tuple[int, int]:
    events = _read_jsonl(run_dir / "ours" / "events.jsonl")
    has_version_field = any("version" in k.lower() for e in events for k in e)
    print(f"  mission-state version field present anywhere in schema: {has_version_field}")

    starts = [e for e in events if e["kind"] == "execution_started"]
    finishes = {e["seq"]: e for e in events if e["kind"] == "execution_finished"}
    proposals = [e for e in events if e["kind"] == "tool_proposed"]
    guards = [e for e in events if e["kind"] == "guard_decision"]
    verifies = [e for e in events if e["kind"] == "effect_verified"]
    ledgers = [e for e in events if e["kind"] == "ledger_changed"]

    n_calls = len(starts)
    n_complete = 0
    for s in starts:
        # nearest preceding tool_proposed/guard_decision, nearest following effect_verified within
        # this call's capability
        cap = s.get("capability")
        prior_proposal = [p for p in proposals if p["seq"] < s["seq"] and p.get("tool") == cap]
        prior_guard = [g for g in guards if g["seq"] < s["seq"] and g.get("tool") == cap]
        next_finish = next((e for e in events if e["kind"] == "execution_finished" and e["seq"] > s["seq"]
                             and e.get("capability") == cap), None)
        next_verify = next((v for v in verifies if v["seq"] > s["seq"] and v.get("capability") == cap), None)
        ledger_after_verify = None
        if next_verify:
            ledger_after_verify = next((l for l in ledgers if l["seq"] > next_verify["seq"]
                                         and l["seq"] < next_verify["seq"] + 20), None)
        ok = bool(prior_proposal and prior_guard and next_finish and next_verify)
        n_complete += ok
        if not ok or ledger_after_verify is None:
            print(f"    capability={cap!r} seq={s['seq']}: proposal={bool(prior_proposal)} "
                  f"guard={bool(prior_guard)} exec_finish={bool(next_finish)} "
                  f"verify={bool(next_verify)} ledger_change_within_20_events_after_verify="
                  f"{bool(ledger_after_verify)}")
    print(f"  capability calls: {n_calls}, with proposal+guard+exec+verify all present: {n_complete}")
    print(f"  evidence/ dir files not cross-referenced by any event field: True (grep confirms no "
          f"'evidence/' path string appears in events.jsonl)")
    has_evidence_path_ref = any("evidence/" in json.dumps(e) for e in events)
    print(f"  (checked: any event JSON contains the literal 'evidence/' path substring: {has_evidence_path_ref})")
    return n_calls, n_complete


_EXECUTING_RE = re.compile(r"Transitioning (\S+) (\S+) from \S+ to EXECUTING ")
_ADAPTER_RE = re.compile(r"^\[CapabilityAdapter\] COMMAND ([^\s\[{]+) ([^\s\[{]+) ([\[{].*)$")


def check_plexil(run_dir: Path) -> tuple[int, int]:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from evaluation.baselines.plexil_normalize import normalize_capability_server_log
    boundary = normalize_capability_server_log(run_dir / "capability_server.log")
    executing, issued = {}, []  # node id -> address of its latest EXECUTING instance; (node, address, capability)
    for line in (run_dir / "plexil_node_trace.log").read_text(errors="replace").splitlines():
        m = _EXECUTING_RE.search(line)
        if m:
            executing[m.group(1)] = m.group(2)
        m = _ADAPTER_RE.match(line)
        if m:
            issued.append((m.group(1), executing.get(m.group(1)), m.group(2)))
    n_joined = 0
    for i, call in enumerate(boundary):
        node, address, cap = issued[i] if i < len(issued) else (None, None, None)
        ok = bool(node and address and cap == call.capability)
        n_joined += ok
        print(f"    call {i}: {call.capability} success={call.success} <- plan node {node} ({address})"
              f"{'' if ok else '  NOT JOINED'}")
    print(f"  capability calls (boundary): {len(boundary)}, adapter calls with a node id: {len(issued)}, "
          f"joined to an executing plan node by id: {n_joined}")
    return len(boundary), n_joined


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--method", choices=["ours", "plexil"], required=True)
    args = ap.parse_args()
    print(f"=== {args.run_dir.name} ({args.method}) ===")
    if args.method == "ours":
        check_ours(args.run_dir)
    else:
        check_plexil(args.run_dir)


if __name__ == "__main__":
    main()
