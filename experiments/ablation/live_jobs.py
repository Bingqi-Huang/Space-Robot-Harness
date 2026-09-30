"""Stage 3 of the §5.7 ablations (research repo F148): a farm jobs file for the live cells stage 2 selected.

Each live run resumes a recorded Experiment I run (exp1b) from its own snapshot and record (ours_mission_check.py
OURS_RESUME_FROM / OURS_RESUME_BEFORE_STEP) with the arm's variant switched on. The record it resumes is the one the
arm's own agent would have written on that trajectory (accidents.as_recorded_by), prepared under
<out>/src/<name>/ours/events.jsonl beside a link to the run's snapshots. The accident happens live:
  J1  resumed before the carrying drive from a copy of the saved state in which the carried item lies on the ground
      beside the rover, the jaws left at their grasp angle: a slip the record does not know of. (F60 expected the
      restore itself to drop the item; with the top-handle grasp it does not, research repo F154.)
  J3  resumed at the point, which restarts the reasoner (no_context: a new session from the mission and the robot)
  J4  resumed at the donor decision with Earth already set (SPACE_LINK_LOS_S=0)

    python3 live_jobs.py <out dir> <cell> [<cell> ...]     cell = <accident>:<run>:<arm>[:<name>]
e.g. J1:exp1b/ours_l3_bess_r1:no_verification
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

from accidents import as_recorded_by, step_of
from record import RUNS, events

JOBS = Path(__file__).resolve().parents[1] / "launch/lunar_base_d0/jobs"
MAP = Path(__file__).resolve().parents[2] / "space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/nav_map"
DROP_R = 1.4  # m from the rover's centre: clear of its hull
CLEAR = 0.45  # m of surveyed free ground round the spot
APART = 0.9  # m from every other object
DROP_Z = 0.45  # m: the item is let go this high and settles on the ground


def base_line(run: str) -> str:
    """The run's own launch line in the Experiment I job files (the fix batch's where it was rerun)."""
    name = run.split("/")[1]
    for f in ("exp1b_fix.txt", "exp1b_campaign.txt"):
        for line in (JOBS / f).read_text().splitlines():
            if line.split(" ", 1)[0] == name:
                return line.split(" ", 1)[1]
    raise KeyError(run)


def resume_step(accident: str, run: str) -> int:
    evs = events(run)
    if accident == "J1":
        look = next(e for e in evs if e["kind"] == "effect_verified" and e["effect"] == "item_still_held")
        return step_of(evs, look["seq"])  # before the drive
    if accident == "J3":
        eff = next(e for e in evs if e["kind"] == "effect_verified" and e["effect"] in ("pressed", "item_held", "item_placed") and e["holds"])
        assert eff["effect"] != "item_held", f"{run}: J3 live needs a point with nothing held (a restore drops it)"
        return step_of(evs, eff["seq"]) + 1
    if accident == "J4":
        hold = next(e for e in evs if e["kind"] == "guard_decision" and e["outcome"] == "approval_required")
        return step_of(evs, hold["seq"])
    raise ValueError(accident)


def drop_carried(src: Path, snaps: Path, step: int) -> dict:
    """Write src/snapshots: links to the run's snapshots, and before_step_<step> with the carried item on the ground."""
    (src / "snapshots").mkdir()
    for f in snaps.iterdir():
        (src / "snapshots" / f.name).symlink_to(f)
    pt = src / f"snapshots/before_step_{step}.pt"
    pt.unlink()
    snap = torch.load(snaps / pt.name, map_location="cpu")
    rover = json.loads((snaps / f"before_step_{step}.json").read_text())
    objs = {k: v[0] for k, v in snap["rigid_objects"].items()}
    near = [k for k, s in objs.items() if s[2] > 0.65 and math.dist(s[:2].tolist(), (rover["x"], rover["y"])) < 1.2]
    assert len(near) == 1, near
    item = near[0]
    head = (MAP / "map.pgm").read_bytes()
    w, h = map(int, head.split(b"\n")[1].split())
    grid = np.frombuffer(head, np.uint8)[-w * h:].reshape(h, w)
    meta = yaml.safe_load((MAP / "map.yaml").read_text())
    res, (ox, oy, _) = meta["resolution"], meta["origin"]

    def free(x, y):
        r = int(CLEAR / res)
        c, row = int((x - ox) / res), h - 1 - int((y - oy) / res)
        yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
        return bool((grid[row - r:row + r + 1, c - r:c + r + 1][yy ** 2 + xx ** 2 <= r * r] == 254).all())

    for turn in (90, -90, 135, -135, 45, -45, 180, 0):
        a = rover["yaw"] + math.radians(turn)
        x, y = rover["x"] + DROP_R * math.cos(a), rover["y"] + DROP_R * math.sin(a)
        if free(x, y) and all(math.dist((x, y), s[:2].tolist()) >= APART for k, s in objs.items() if k != item):
            break
    else:
        raise RuntimeError(f"no free spot beside the rover for {item}")
    was = objs[item][:3].tolist()
    objs[item][:] = torch.tensor([x, y, DROP_Z, math.cos(rover["yaw"] / 2), 0, 0, math.sin(rover["yaw"] / 2), 0, 0, 0, 0, 0, 0])
    torch.save(snap, pt)
    injected = dict(item=item, held_at=[round(v, 3) for v in was], dropped_at=[round(x, 3), round(y, 3)],
                    beside_rover_deg=turn, rover=[rover["x"], rover["y"], rover["yaw"]])
    (src / "injected.json").write_text(json.dumps(injected, indent=1) + "\n")
    return injected


def main() -> None:
    out, cells = Path(sys.argv[1]), sys.argv[2:]
    lines = []
    for cell in cells:
        accident, run, arm, *name = cell.split(":")
        name = name[0] if name else f"{accident.lower()}_{run.split('/')[1]}_{arm}"
        variant = {"full": None, "no_guard_link_up": "no_guard"}.get(arm, arm)
        src = out / "src" / name
        (src / "ours").mkdir(parents=True, exist_ok=True)
        record = [dict(e, seq=i) for i, e in enumerate(as_recorded_by(variant, events(run)))]  # numbered as its own log
        (src / "ours/events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in record))
        step = resume_step(accident, run)
        if accident == "J1":
            print(name, drop_carried(src, RUNS / run / "snapshots", step), file=sys.stderr)
        else:
            (src / "snapshots").symlink_to(RUNS / run / "snapshots")
        env = [base_line(run), f"OURS_RESUME_FROM={src}", f"OURS_RESUME_BEFORE_STEP={step}"]
        if variant:
            env.append(f"OURS_ABLATION={variant}")
        if accident == "J4" and arm != "no_guard_link_up":
            env.append("SPACE_LINK_LOS_S=0")
        lines.append(f"{name} {' '.join(env)}")
    (out / "jobs.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
