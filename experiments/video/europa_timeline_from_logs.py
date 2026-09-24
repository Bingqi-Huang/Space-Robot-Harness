"""EUROPA host run -> a sim-time-stamped event list for `europa_mission_video.py` (a video-specific reading of
`host.py`'s own `events.jsonl`, same split as `plexil_timeline_from_logs.py` -- see its module docstring).

    /usr/bin/python3.10 experiments/video/europa_timeline_from_logs.py <run dir> <out.json>

`host.py`'s `events.jsonl` already carries exactly the structure a viewer needs (`mission`'s goals, each `plan`'s
freshly *derived* activity list, `dispatch`/`result` per call, `done`) -- nothing here reinterprets it, only adds
`sim_t` (host.py logs on the wall clock, `sim_clock.wall_to_sim` resolves it from the run's own closed bag).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_clock import wall_to_sim


def main(run_dir: str, out: str) -> None:
    run = Path(run_dir)
    to_sim = wall_to_sim(run / "bag")
    events = []
    for line in (run / "events.jsonl").read_text().splitlines():
        e = json.loads(line)
        e["sim_t"] = to_sim(e["wall_t"])
        events.append(e)
    Path(out).write_text(json.dumps({"run": run_dir, "events": events}))
    print(f"{len(events)} events -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
