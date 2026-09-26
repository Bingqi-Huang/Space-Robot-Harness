"""Where every place of a batch left its item, from the evaluator's truth (no bag, no rerun).

For each successful `place` call in capability_server.log: the carried item is the tracked object that moved most during
the call; its offset from the support's surveyed point along the support's outward normal and across it, (1) when it
first came to rest at the support's height (the set-down, before the release and the base withdrawal) and (2) at the
call's end (after the withdrawal and the lift); the difference is what the withdrawal dragged. The site's on-support
test allows 0.12 m along and 0.18 m across (SRB site.py ON_SUPPORT_XY_M).

    python3 experiments/analysis/place_offsets.py artifacts/runs/exp1 > artifacts/eval/exp1/place_offsets.md
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POINTS = json.loads((REPO / "space_robotics_bench/assets/lunar_base/scene/generated/interaction.json").read_text())["points"]
ALONG_MAX, ACROSS_MAX = 0.12, 0.18


def calls(run: Path):
    for line in (run / "capability_server.log").read_text().splitlines():
        if "CAPABILITY {" in line:
            yield json.loads(line.split("CAPABILITY ", 1)[1])


def poses(run: Path, t0: float, t1: float) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for line in (run / "evaluator/events.jsonl").open():
        if '"kind": "pose"' not in line:
            continue
        d = json.loads(line)
        if t0 <= d["sim_t"] <= t1 and "/lb_" in d["frame"]:
            out.setdefault(d["frame"].rsplit("/lb_", 1)[1], []).append(d)
    return out


def offset(p: dict, point: dict) -> tuple[float, float]:
    (sx, sy, _), (nx, ny, _) = point["xyz"], point["normal"]
    rx, ry = p["x"] - sx, p["y"] - sy
    return rx * nx + ry * ny, rx * ny - ry * nx


def main() -> None:
    print("| run | support | item | set-down along / across (m) | end along / across (m) | dragged by the withdrawal (m) | inside the scored footprint |")
    print("|---|---|---|---|---|---|---|")
    for run in sorted(p for p in Path(sys.argv[1]).iterdir() if (p / "capability_server.log").exists()):
        for c in calls(run):
            if c["capability"] != "place" or not c["success"]:
                continue
            support = c["args"]["support"]
            point = POINTS[support]
            tracks = poses(run, c["sim_t_start"], c["sim_t_end"] + 2.0)
            item = max(tracks, key=lambda k: abs(tracks[k][-1]["x"] - tracks[k][0]["x"]) + abs(tracks[k][-1]["y"] - tracks[k][0]["y"])
                       + abs(tracks[k][-1]["z"] - tracks[k][0]["z"]))
            tr = tracks[item]
            down = next((p for p in tr if abs(p["z"] - point["xyz"][2]) < 0.03), tr[-1])
            a0, c0 = offset(down, point)
            a1, c1 = offset(tr[-1], point)
            inside = abs(a1) < ALONG_MAX and abs(c1) < ACROSS_MAX
            print(f"| {run.name} | {support} | {item} | {a0:+.3f} / {c0:+.3f} | {a1:+.3f} / {c1:+.3f} | "
                  f"{((a1 - a0) ** 2 + (c1 - c0) ** 2) ** 0.5:.3f} | {'yes' if inside else '**no**'} |")


if __name__ == "__main__":
    main()
