"""Table generation from normalized rows -- execution_plan.md §13.2 "The main result table is
generated directly from these rows", §15 (Wilson CI for rates, bootstrap for ratios, pairing by
scenario seed). No hand-edited CSV: `main()` reads a directory of row JSON files (as written by
`evaluation/rows.py::extract_row`) and prints the Markdown tables.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from evaluation.rows import NormalizedRunRow

__all__ = ["wilson_ci", "bootstrap_ci", "success_rate_table", "instance_table", "violation_table", "interaction_table",
           "physical_failure_table", "load_rows"]

LEVELS = ("L0", "L1", "L2-A", "L2-B", "L3", "L4")  # docs/heldout_design.md §2, the order of the success-versus-level curve


def wilson_ci(successes: int, n: int, *, z: float = 1.96) -> tuple[float, float, float]:
    """§15 "confidence intervals for autonomous success rates". `(point, low, high)`, all in [0, 1].
    `n == 0` returns `(0.0, 0.0, 1.0)` -- no data, not a fabricated interval."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0.0, (centre - spread) / denom), min(1.0, (centre + spread) / denom)


def bootstrap_ci(values: list[float], *, statistic=lambda xs: sum(xs) / len(xs), n_resamples: int = 2000,
                  alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    """§15 "bootstrap ... confidence intervals for HIR and continuous timing measures". `(point, low, high)`.
    Empty `values` returns `(0.0, 0.0, 0.0)` -- no data, not a fabricated interval."""
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    point = statistic(values)
    n = len(values)
    resamples = sorted(statistic([values[rng.randrange(n)] for _ in range(n)]) for _ in range(n_resamples))
    lo_idx, hi_idx = int(n_resamples * alpha / 2), int(n_resamples * (1 - alpha / 2)) - 1
    return point, resamples[max(lo_idx, 0)], resamples[min(hi_idx, n_resamples - 1)]


def load_rows(rows_dir: Path) -> list[NormalizedRunRow]:
    return [NormalizedRunRow.model_validate_json(p.read_text()) for p in sorted(rows_dir.glob("*.json"))]


def success_rate_table(rows: list[NormalizedRunRow]) -> str:
    """Markdown table, the main result: one line per (method, level), the success-versus-level curve of preregistration
    §4 (docs/heldout_design.md §14: L0/L1 covered, L2-L4 held-out). Rows with `autonomous_mission_success is None` (no
    verdict -- an infrastructure failure, preregistration §3, not scored) are excluded from the denominator and listed."""
    groups: dict[tuple[str, str | None], list[NormalizedRunRow]] = {}
    excluded = []
    for r in rows:
        if r.autonomous_mission_success is None:
            excluded.append(r.run_id)
            continue
        groups.setdefault((r.method, r.level), []).append(r)
    lines = ["| method | level | coverage | n | successes | rate | 95% Wilson CI |", "|---|---|---|---|---|---|---|"]
    for (method, level), grp in sorted(groups.items(), key=lambda kv: (kv[0][0], LEVELS.index(kv[0][1]))):
        n = len(grp)
        succ = sum(1 for r in grp if r.autonomous_mission_success)
        p, lo, hi = wilson_ci(succ, n)
        lines.append(f"| {method} | {level} | {grp[0].coverage} | {n} | {succ} | {p:.2f} | [{lo:.2f}, {hi:.2f}] |")
    if excluded:
        lines.append("")
        lines.append(f"({len(excluded)} run(s) excluded, no verdict -- infrastructure failure, not scored: {', '.join(excluded)})")
    return "\n".join(lines)


def instance_table(rows: list[NormalizedRunRow]) -> str:
    """Markdown table: successes k of n per §14 instance and method (preregistration §4, paired by instance); `-` where a
    method has no scored run of that instance."""
    methods = sorted({r.method for r in rows})
    scored = [r for r in rows if r.autonomous_mission_success is not None]
    instances = sorted({(r.level, r.scenario_id) for r in scored}, key=lambda k: (LEVELS.index(k[0]), k[1]))
    lines = ["| level | instance | " + " | ".join(methods) + " |", "|---|---|" + "---|" * len(methods)]
    for level, sid in instances:
        cells = []
        for m in methods:
            grp = [r for r in scored if r.method == m and r.scenario_id == sid]
            cells.append(f"{sum(r.autonomous_mission_success for r in grp)}/{len(grp)}" if grp else "-")
        lines.append(f"| {level} | {sid} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def violation_table(rows: list[NormalizedRunRow]) -> str:
    """Markdown table: the external evaluator's five violation classes (§14.3/§5.5 metric 6,
    docs/evaluator_violations.md), summed per (method, coverage). `evaluator-covered` is how many of
    that group's runs had `evaluation/evaluator_recorder` attached (`evaluator_*_count is not None`) --
    a run without it contributes nothing to the sums, not a zero, so the sums are only comparable
    against that coverage count, not against `n`."""
    groups: dict[tuple[str, str | None], list[NormalizedRunRow]] = {}
    for r in rows:
        groups.setdefault((r.method, r.coverage), []).append(r)
    lines = [
        "| method | coverage | n | evaluator-covered | unintended contact | dropped item | collateral change | execution during fault | removal without approval |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for (method, coverage), grp in sorted(groups.items(), key=lambda kv: kv[0]):
        covered = [r for r in grp if r.evaluator_unintended_contact_count is not None]

        def total(attr: str) -> int:
            return sum(getattr(r, attr) or 0 for r in covered)

        lines.append(
            f"| {method} | {coverage or '?'} | {len(grp)} | {len(covered)} | "
            f"{total('evaluator_unintended_contact_count')} | {total('evaluator_dropped_item_count')} | "
            f"{total('evaluator_collateral_change_count')} | {total('evaluator_estop_fault_execution_count')} | "
            f"{total('evaluator_unauthorized_removal_count')} |"
        )
    return "\n".join(lines)


def interaction_table(rows: list[NormalizedRunRow]) -> str:
    """Markdown table: human involvement per (method, coverage) -- research repo docs/heldout_design.md §8, ALFUS
    (NIST SP 1011-II-1.0). Means over the group's runs with a recorded mission time; counts are sums; the ALFUS level
    is the most human-directed one used in any run of the group; re-authoring is how many runs needed it."""
    from evaluation.interaction import ALFUS_ORDER

    groups: dict[tuple[str, str | None], list[NormalizedRunRow]] = {}
    for r in rows:
        groups.setdefault((r.method, r.coverage), []).append(r)
    lines = [
        "| method | coverage | n | human intervention ratio | requests: authorization / authority check / new procedure / information | grants/denials | highest ALFUS level | ground re-authoring | idle waiting | longest autonomous stretch (s) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (method, coverage), grp in sorted(groups.items(), key=lambda kv: kv[0]):
        timed = [r for r in grp if r.mission_elapsed_s]

        def mean(attr: str) -> str:
            v = [getattr(r, attr) for r in timed if getattr(r, attr) is not None]
            return f"{sum(v) / len(v):.3f}" if v else "-"

        levels = [r.highest_interaction_level for r in grp if r.highest_interaction_level]
        kinds = " / ".join(str(sum(getattr(r, f"requests_{k}") for r in grp))
                           for k in ("authorization", "authority_check", "new_procedure", "information"))
        lines.append(
            f"| {method} | {coverage or '?'} | {len(grp)} | {mean('human_intervention_ratio')} | {kinds} | "
            f"{sum(r.grants for r in grp)}/{sum(r.denials for r in grp)} | "
            f"{max(levels, key=ALFUS_ORDER.index) if levels else '-'} | {sum(r.ground_reauthoring_required for r in grp)} | "
            f"{mean('idle_waiting_fraction')} | {mean('longest_autonomous_stretch_s')} |"
        )
    return "\n".join(lines)


def physical_failure_table(rows: list[NormalizedRunRow]) -> str:
    """Markdown tables, the physical layer per leg (docs/heldout_design.md §9, preregistration §2 category 4): per
    capability, the calls the shared boundary completed over all runs and how many failed, by failed stage; then every
    failed call with its run, the skill's own failure_kind, stage and reason. Attributed to the capability, whichever
    method made the call."""
    calls: dict[str, int] = {}
    for r in rows:
        for c, n in r.capability_calls.items():
            calls[c] = calls.get(c, 0) + n
    failed = [(r, f) for r in rows for f in r.failed_calls]
    lines = ["| capability | calls | failed | failed at stage |", "|---|---|---|---|"]
    for c in sorted(calls):
        stages: dict[str, int] = {}
        for _, f in failed:
            if f["capability"] == c:
                stages[f["failed_stage"] or "-"] = stages.get(f["failed_stage"] or "-", 0) + 1
        lines.append(f"| {c} | {calls[c]} | {sum(stages.values())} | "
                     f"{', '.join(f'{k} {v}' for k, v in sorted(stages.items())) or '-'} |")
    lines += ["", "| run | method | level | capability | mission time (s) | failure_kind | failed stage | reason |",
              "|---|---|---|---|---|---|---|---|"]
    for r, f in failed:
        reason = f["failure_reason"].replace("|", "\\|")
        lines.append(f"| {r.run_id} | {r.method} | {r.level} | {f['capability']} | {f['sim_t_start']:.1f}-{f['sim_t_end']:.1f} | "
                     f"{f['failure_kind']} | {f['failed_stage'] or '-'} | {reason} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows-dir", type=Path, required=True, help="Directory of *.json files written by rows.extract_row")
    args = ap.parse_args()
    rows = load_rows(args.rows_dir)
    print(success_rate_table(rows))
    print()
    print(instance_table(rows))
    print()
    print(violation_table(rows))
    print()
    print(interaction_table(rows))
    print()
    print(physical_failure_table(rows))


if __name__ == "__main__":
    main()
