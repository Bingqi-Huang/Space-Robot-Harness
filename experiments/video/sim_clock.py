"""Wall-clock -> simulation-clock lookup from a run's own evaluator record (`<run>/evaluator/events.jsonl`). Shared by
`plexil_timeline_from_logs.py`, `europa_timeline_from_logs.py` and `swimlane.py`: both baselines log on the wall
clock (PLEXIL's node trace and EUROPA host's `events.jsonl` are plain `time.time()`), but videos and figures play
mission time -- the simulator clock (`space_context/link.py`), which Ours' `events.jsonl` and the operator console
already carry. The evaluator recorder stamps every pose it records with both clocks, which makes the table.

The run's bag cannot give this: the recorder runs on the simulator clock, so a message's receive time in the bag is
itself simulation time (every step-9/10 bag starts at 0.02 s since the epoch).

Also here, because it is the other half of reading mission time: the Earth link profile a run ran under.
"""
import bisect
import json
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


def manifest(run: Path) -> dict:
    """The run's manifest (`run_manifest.yaml`, or the step-9 `run_manifest.backfilled.yaml`)."""
    return yaml.safe_load(next(run.glob("run_manifest*.yaml")).read_text())


def earth_profile(run: Path) -> dict:
    """The Earth link profile the run ran under: `space_context/profiles/earth_link.json` at the research-repo revision
    its manifest names (Earth set 2700 s after the start until F116, 925 s since)."""
    rev = manifest(run)["research_repo_revision"]
    return json.loads(subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:space_context/profiles/earth_link.json"],
                                     capture_output=True, text=True, check=True).stdout)


def wall_to_sim(run: Path):
    """A monotone (wall_s, sim_s) table from the evaluator's own stamps, for linear lookup without numpy."""
    pairs = [(e["wall_t"], e["sim_t"]) for e in map(json.loads, (run / "evaluator" / "events.jsonl").read_text().splitlines())
             if e["sim_t"] is not None]
    wall, sim = [w for w, _ in pairs], [s for _, s in pairs]

    def convert(w: float) -> float:
        i = bisect.bisect_left(wall, w)
        if i <= 0:
            return sim[0]
        if i >= len(wall):
            return sim[-1]
        w0, w1, s0, s1 = wall[i - 1], wall[i], sim[i - 1], sim[i]
        return s0 if w1 <= w0 else s0 + (s1 - s0) * (w - w0) / (w1 - w0)
    return convert
