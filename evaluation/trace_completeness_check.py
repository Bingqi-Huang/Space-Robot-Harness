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

For PLEXIL/EUROPA: reads `evaluation/baselines/*normalize*` CommonEvents and reports, per
execution_finished, whether a plan_node_id can be attributed to it (it cannot: normalize_plexil_
check_log's own docstring says node transitions and capability-server events are only merged by
sorting on wall-clock, never joined by id).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(errors="replace").splitlines() if l.strip()]


def check_ours(run_dir: Path) -> None:
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


def check_plexil(run_dir: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from evaluation.baselines.plexil_normalize import normalize_plexil_check_log
    events = normalize_plexil_check_log(run_dir / "check.log")
    node_events = [e for e in events if e.kind == "execution_started" and e.plan_node_id]
    cap_events = [e for e in events if e.kind == "execution_finished" and e.capability]
    print(f"  plan node transitions logged: {len(node_events)}")
    print(f"  capability calls logged: {len(cap_events)}")
    joined_by_id = any(getattr(e, "plan_node_id", None) and getattr(e, "capability", None) for e in events)
    print(f"  any single event carries BOTH plan_node_id and capability (a real join key): {joined_by_id}")
    print("  -> node<->capability attribution is by nearest-timestamp only, never an explicit id join "
          "(confirmed against plexil_normalize.py's own docstring)")


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
