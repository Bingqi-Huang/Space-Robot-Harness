"""What the proposed runtime's reasoning would cost in mission time on a real robot (Experiment I, tag exp1b).

The simulation runs slower than real time, so a model call that takes W s of wall clock advances mission (simulator)
time by only the simulated time that passes meanwhile. Per Ours run: the reasoning calls inside the evaluator's mission
window (evaluation/interaction.py: from the first capability call's start, `mission_elapsed_s` long; a call counts when
its middle falls inside), each call from its `reasoner_step_started` to its `tool_proposed` / `reasoner_step_failed` in
ours/events.jsonl, which stamps both clocks; then the mission time with that latency in full,
`mission_elapsed_s - sim time during the calls + wall time during the calls`.

    python3 experiments/analysis/reasoning_latency.py > artifacts/eval/exp1b/reasoning_latency.md
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from evaluation.interaction import call_windows  # noqa: E402

RUNS = REPO / "artifacts/runs/exp1b"
ROWS = REPO / "artifacts/eval/exp1b/rows"


def reasoning_calls(run: Path) -> list[tuple[dict, dict]]:
    """(start event, end event) of every reasoning call of the run."""
    out, start = [], None
    for line in (run / "ours/events.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e["kind"] == "reasoner_step_started":
            start = e
        elif e["kind"] in ("tool_proposed", "reasoner_step_failed"):
            out.append((start, e))
    return out


def main() -> None:
    per_run = []
    print("| run | coverage | reasoning calls (in mission / all) | wall clock in calls (s) | mission time in calls (s) | "
          "mission time, recorded (s) | mission time, latency in full (s) |")
    print("|---|---|---|---|---|---|---|")
    for run in sorted(RUNS.glob("ours_*")):
        row = json.loads((ROWS / f"exp1b__{run.name}.json").read_text())
        m0 = min(a for a, _ in call_windows(run))
        m1 = m0 + row["mission_elapsed_s"]
        calls = reasoning_calls(run)
        inside = [(a, b) for a, b in calls if m0 <= (a["sim_t"] + b["sim_t"]) / 2 <= m1]
        wall = [b["wall_t"] - a["wall_t"] for a, b in inside]
        sim = sum(b["sim_t"] - a["sim_t"] for a, b in inside)
        real = row["mission_elapsed_s"] - sim + sum(wall)
        per_run.append(dict(coverage=row["coverage"], calls=len(inside), wall=sum(wall), sim=sim,
                            recorded=row["mission_elapsed_s"], real=real, latencies=wall,
                            hir=row["human_intervention_ratio"],
                            hir_real=row["human_intervention_ratio"] * row["mission_elapsed_s"] / real))
        print(f"| {run.name} | {row['coverage']} | {len(inside)} / {len(calls)} | {sum(wall):.0f} | {sim:.0f} | "
              f"{row['mission_elapsed_s']:.0f} | {real:.0f} |")

    print()
    print("| coverage | runs | reasoning calls | wall clock in calls (s) | mission time in calls (s) | mission time, recorded (s) | "
          "mission time, latency in full (s) | per-call wall latency (s), median [IQR] | mission time per wall second in calls | "
          "HIR, recorded | HIR, latency in full |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for cov in ("covered", "held_out", "all"):
        g = [r for r in per_run if cov in ("all", r["coverage"])]
        med = {k: np.median([r[k] for r in g]) for k in ("calls", "wall", "sim", "recorded", "real", "hir", "hir_real")}
        lat = np.concatenate([r["latencies"] for r in g])
        q1, q2, q3 = np.percentile(lat, [25, 50, 75])
        print(f"| {cov} | {len(g)} | {med['calls']:.0f} | {med['wall']:.0f} | {med['sim']:.0f} | {med['recorded']:.0f} | "
              f"{med['real']:.0f} | {q2:.1f} [{q1:.1f}, {q3:.1f}] | {sum(r['sim'] for r in g) / sum(r['wall'] for r in g):.3f} | "
              f"{med['hir']:.3f} | {med['hir_real']:.3f} |")
    print()
    print("Medians over runs, except the per-call latency (median and interquartile range over the calls of those runs) "
          "and the mission time per wall second (pooled over those calls). A call's wall time includes the harness's "
          "context rendering, at most 0.15 s above the model's own latency in ours/model_io.jsonl. Calls before the "
          "first capability call (reading telemetry, writing the plan) and after the mission's end fall outside the "
          "mission window and are not counted, as the mission time does not count them. HIR's numerator is mission "
          "control's decision time on the mission clock, so HIR with the latency in full is the recorded HIR times "
          "recorded / latency-in-full mission time. The runtime keeps reasoning while a request is open; with the "
          "latency in full those calls would overlap mission control's decision time, so the increase over the recorded "
          "mission time is an upper bound on the cost of reasoning for a model served at this latency. Model calls "
          "inside the shared skills (the VLM that locates a press target) run on the same compressed clock for every "
          "method and are not corrected here.")


if __name__ == "__main__":
    main()
