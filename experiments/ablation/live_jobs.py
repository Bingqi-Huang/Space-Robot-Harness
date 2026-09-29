"""Stage 3 of the §5.7 ablations (research repo F148): a farm jobs file for the live cells stage 2 selected.

Each live run resumes a recorded Experiment I run (exp1b) from its own snapshot and record (ours_mission_check.py
OURS_RESUME_FROM / OURS_RESUME_BEFORE_STEP) with the arm's variant switched on. The record it resumes is the one the
arm's own agent would have written on that trajectory (accidents.as_recorded_by), prepared under
<out>/src/<name>/ours/events.jsonl beside a link to the run's snapshots. The accident happens live:
  J1  resumed before the carrying drive: the restore leaves the carried item out of the jaws (a held item's contact is
      not in the saved state, research repo F60), then the drive runs
  J3  resumed at the point, which restarts the reasoner (no_context: a new session from the mission and the robot)
  J4  resumed at the donor decision with Earth already set (SPACE_LINK_LOS_S=0)

    python3 live_jobs.py <out dir> <cell> [<cell> ...]     cell = <accident>:<run>:<arm>[:<name>]
e.g. J1:exp1b/ours_l3_bess_r1:no_verification
"""
import json
import sys
from pathlib import Path

from accidents import as_recorded_by, step_of
from record import RUNS, events

JOBS = Path(__file__).resolve().parents[1] / "launch/lunar_base_d0/jobs"


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
        if not (src / "snapshots").exists():
            (src / "snapshots").symlink_to(RUNS / run / "snapshots")
        env = [base_line(run), f"OURS_RESUME_FROM={src}", f"OURS_RESUME_BEFORE_STEP={resume_step(accident, run)}"]
        if variant:
            env.append(f"OURS_ABLATION={variant}")
        if accident == "J4" and arm != "no_guard_link_up":
            env.append("SPACE_LINK_LOS_S=0")
        lines.append(f"{name} {' '.join(env)}")
    (out / "jobs.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
