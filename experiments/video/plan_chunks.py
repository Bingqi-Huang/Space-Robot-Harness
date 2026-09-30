"""Split the 1x replay renders into chunks that run in parallel (several renders share one GPU: a replay uses ~1.6
cores and a quarter of a GPU). For each run: the frame times replay_render.py would render (the bag's full-/tf span on
the 1/fps grid), minus the frames already in <video dir>/replay/<run>/ (the newest one is re-rendered: its writer may
have been stopped mid-file); the missing times go out as chunks "<run> <a> <b>" (a <= t < b, cut between grid points), each within one
contiguous stretch of missing frames and of at most --size frames, longest run first.

    python3 experiments/video/plan_chunks.py <video dir> <run> [<run> ...] > <video dir>/chunks.txt
"""
import argparse
import glob
import math
import sqlite3
from pathlib import Path

R = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser()
ap.add_argument("video_dir", type=Path)
ap.add_argument("runs", nargs="+")
ap.add_argument("--fps", type=float, default=10.0)
ap.add_argument("--size", type=int, default=1000)
a = ap.parse_args()

plan = []
for run in a.runs:
    db = sqlite3.connect(glob.glob(str(R / "artifacts/runs/exp1b" / run / "bag" / "*.db3"))[0])
    tid = db.execute("select id from topics where name='/tf'").fetchone()[0]
    t0, t1 = (v / 1e9 for v in db.execute("select min(timestamp), max(timestamp) from messages where topic_id=? and length(data)>2000", (tid,)).fetchone())
    db.close()
    lo = math.ceil(max(0.0, t0) * a.fps) / a.fps  # replay_render.py's grid
    times = [round(lo + i / a.fps, 2) for i in range(int((t1 - lo) * a.fps) + 1)]
    have = sorted(float(Path(p).stem) for p in glob.glob(str(a.video_dir / "replay" / run / "*.png")))
    done = set(have[:-1])
    todo = [t for t in times if t not in done]
    half = 0.5 / a.fps
    runs, i = [], 0  # contiguous stretches of missing frames, then chunks of at most --size
    for j in range(1, len(todo) + 1):
        if j == len(todo) or todo[j] - todo[j - 1] > 1.5 / a.fps:
            runs.append(todo[i:j]); i = j
    for seg in runs:
        for k in range(0, len(seg), a.size):
            c = seg[k:k + a.size]
            plan.append((len(times), run, round(c[0] - half, 3), round(c[-1] + half, 3), len(c)))
    print(f"# {run}: {len(times)} frames, {len(done)} kept, {len(todo)} to render", flush=True)
for n, run, lo, hi, k in sorted(plan, key=lambda p: (-p[0], p[2])):
    print(run, lo, hi)
