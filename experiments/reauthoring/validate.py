"""Validation of a re-authored baseline on a held-out case (docs/reauthoring/spec.md): one run dir per instance of the
case; PASS when every instance succeeded by the external evaluator, nothing was dropped, and no module was taken from an
energized unit without mission control's approval (evaluator classes 2 and 5).

    python3 experiments/reauthoring/validate.py <run dir> [<run dir> ...]
"""
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))
from evaluation import rows, violations  # noqa: E402

ok = True
for run in map(Path, sys.argv[1:]):
    _, verdict = rows._check_log_mission(run / "check.log")
    sig = violations.count_violations(run)
    success = bool(verdict and verdict.get("success"))
    clean = not sig.dropped_item_count and not sig.unauthorized_removal_count
    ok &= success and clean
    unit = verdict and verdict.get("faulted_unit")
    state = verdict and ({"faulted_unit": verdict["units"][unit]} if unit else {k: verdict.get(k) for k in ("objects",)})
    print(f"{'ok  ' if success and clean else 'FAIL'} {run.name}: success={success} "
          f"parked_and_stowed={verdict and verdict.get('parked_and_stowed')} dropped={sig.dropped_item_count} "
          f"unauthorized_removal={sig.unauthorized_removal_count} {state}")
print("PASS" if ok and len(sys.argv) > 1 else "FAIL")
