"""PLEXIL as it ran: the same follow-camera-plus-cards layout `mission_video.py` uses for Ours, content adapted to
what PLEXIL actually has instead of copied from it.

    openral/.venv/bin/python experiments/video/plexil_mission_video.py <follow.mp4> <run>/plexil_timeline.json <out.mp4> \
        [--times <follow.mp4.times>] [--track <track.json>] [--title "..."] [--mission "..."] [--from-sim 0 --to-sim 1e9]

`<run>/plexil_timeline.json` comes from `plexil_timeline_from_logs.py` (needs the ROS-sourced Python for
`rosbag2_py`; this script needs only `cv2`/`PIL`/`numpy`, same split as `track_from_bag.py` / `mission_video.py`).

What stays identical to Ours' video, on purpose -- these are properties of the robot/run, not of the method: the
header clock and motion line, the mini-map (same `Map` class, same evaluator track), the colour rule (one accent
for what is happening now, green/red for verdicts, grey otherwise), and the RECORD card, because both methods'
capability calls cross the same boundary and report the same shape of result.

What is different, because PLEXIL is a different thing, not a worse-decorated version of the same thing:
- No MODEL card. There is no model here; a card for "what the model is thinking" would be decoration over nothing.
- PLAN is not an agent's own working ledger that grows online -- it is the plan `MissionB_Covered.ple` declares,
  fixed before the mission starts. What is live is only each step's *state* (pending / running / done / failed),
  read off `universalExec`'s own node-transition trace. The card draws a graph that does not change and a cursor
  that moves through it, which is the honest picture of what PLEXIL is doing.
- NOW has no rationale line -- PLEXIL does not have one. In its place, which reusable library call the running
  step is inside (`DriveAndDock` / `PickItem` / `PlaceItem` / `StowAndReturn`), which is what PLEXIL substitutes
  for judgment: composed procedure, not a reason.
"""
import argparse
import bisect
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mission_video import (AMBER, DIM, FAINT, FONT, FONT_B, FONT_M, GREEN, INK, MAP_W, OUT_W, PAD, PANEL_W, RED,
                            LEDGER, Map, elide, moving, plain, wrap)

TOP = ["ToDepot", "Pick", "ToShelf", "Place", "Return"]
DEFAULT_MISSION = ("Deliver the spare ORU staged on the depot stand to the spares shelf of PDU-1, then return the "
                    "rover to the dock with the arm stowed.")


def plexil_timeline(events: list[dict], mission: str) -> tuple[list[float], list[dict]]:
    """The state of the mission after every node-status/capability event, keyed to the sim clock the video plays
    at (`plexil_timeline_from_logs.py` already resolved PLEXIL's wall-clock logs to it). Mirrors
    `mission_video.py`'s `timeline()` in shape (a (times, states) pair a frame loop can `bisect` into), not in
    content -- see the module docstring for what differs and why."""
    top_status = {n: "pending" for n in TOP}
    top_active, lib_active, cap_now, log = None, None, None, []
    times, states = [], []

    def note(text: str, kind: str, detail: str = "") -> None:
        nonlocal log
        log = (log[-7:] if len(log) >= 8 else log) + [{"t": t, "text": text, "kind": kind, "detail": detail}]

    pts = []
    for e in events:
        if e["kind"] == "node_status":
            pts.append((e["sim_t"], 0, e))
        else:
            pts.append((e["sim_t_start"], 1, {"edge": "start", **e}))
            pts.append((e["sim_t_end"], 2, {"edge": "end", **e}))
    pts.sort(key=lambda p: (p[0], p[1]))

    for t, _, e in pts:
        if "edge" not in e:
            name, level, state = e["name"], e["level"], e["state"]
            if level == "top":
                if state == "EXECUTING":
                    top_active, top_status[name] = name, "active"
                elif state == "FAILING":
                    top_status[name] = "abandoned"
                elif state == "FINISHED" and top_status[name] != "abandoned":
                    top_status[name] = "done"
            else:
                lib_active = name if state == "EXECUTING" else (None if state == "FINISHED" else lib_active)
        elif e["edge"] == "start":
            cap_now = e["capability"]
        else:
            ok = e["success"]
            note(f"{plain(e['capability'])} {'finished' if ok else 'failed'}", "good" if ok else "bad",
                 "" if ok else str(e.get("failure_reason") or ""))
            cap_now = None
        times.append(t)
        states.append({"plan": [(top_status[n], n) for n in TOP], "top_active": top_active, "lib_active": lib_active,
                       "now": cap_now, "log": list(log), "mission": mission})
    return times, states


def panel(state: dict, sim_t: float, title: str, fonts, moving_now: str = "") -> Image.Image:
    """Same card shape and reading order as `mission_video.py`'s `panel()` -- clock, mission, plan, now, record --
    with MODEL dropped and PLAN/NOW's content specific to PLEXIL (see module docstring)."""
    small, body, head, mono, capf = fonts
    x0, inner = 20, PANEL_W - 40
    ops: list[tuple] = []
    y = 18

    def text(t, font, colour, dx=0, gap=5):
        nonlocal y
        ops.append(("text", y, x0 + dx, t, font, colour))
        y += font.size + gap

    def caption(t):
        nonlocal y
        y += 4
        ops.append(("text", y, x0, t.upper(), capf, DIM))
        y += capf.size + 7

    ops.append(("text", y - 2, x0, f"{sim_t:.0f}", head, INK))
    ops.append(("text", y + head.size - small.size - 4, x0 + head.getlength(f"{sim_t:.0f}") + 6, "s", small, FAINT))
    if moving_now:
        w = body.getlength(moving_now)
        ops.append(("text", y + head.size - body.size - 3, x0 + inner - w, moving_now, body, DIM))
    y += head.size + 10
    ops.append(("rule", y))
    y += 12

    caption("mission")
    said = wrap(state["mission"], 54)
    for i, t in enumerate(said[:2]):
        text(t + ("…" if i == 1 and len(said) > 2 else ""), body, DIM, gap=4)
    y += 10

    caption("plan")  # the fixed graph MissionB_Covered.ple declares; only each step's state is live
    for status, step in state["plan"]:
        glyph, here = LEDGER.get(status, ("·", False))
        colour = INK if here else (FAINT if status == "done" else DIM)
        ops.append(("text", y, x0, glyph, body, colour))
        ops.append(("text", y, x0 + 24, plain(step), body, colour))
        y += body.size + 6
    y += 10

    caption("now")
    top = y
    text(plain(state["now"]) if state["now"] else "—", head, AMBER if state["now"] else FAINT, dx=12, gap=3)
    inside = " · ".join(x for x in (state.get("top_active"), state.get("lib_active")) if x)
    text(elide(inside, body, inner - 12) if inside else "", body, DIM, dx=12, gap=5)
    ops.append(("bar", top, y - 2))
    y += 12

    caption("record")
    for m in state["log"][-4:]:
        colour = {"good": GREEN, "bad": RED}.get(m["kind"], INK)
        ops.append(("text", y + body.size - mono.size, x0, f"{m['t']:5.0f}", mono, FAINT))
        text(elide(m["text"], body, inner - 48), body, colour, dx=48, gap=3 if m.get("detail") else 7)
        if m.get("detail"):
            text(elide(m["detail"], small, inner - 48), small, FAINT, dx=48, gap=7)
    y += 6
    ops.append(("rule", y))
    y += 9
    text(elide(title, small, inner), small, FAINT, gap=0)
    height = y + small.size + 16

    img = Image.new("RGBA", (PANEL_W, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, PANEL_W - 1, height - 1], radius=14, fill=(13, 15, 19, 222))
    for op in ops:
        if op[0] == "text":
            _, yy, xx, t, font, colour = op
            d.text((xx, yy), t, font=font, fill=colour)
        elif op[0] == "rule":
            d.line([(x0, op[1]), (x0 + inner, op[1])], fill=(255, 255, 255, 28), width=1)
        else:
            d.rounded_rectangle([x0, op[1], x0 + 3, op[2]], radius=2, fill=(*AMBER, 255))
    return img


PLACES = {"depot_stand/slot_0": "depot", "pdu_1_shelf/shelf": "PDU-1 shelf"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("timeline", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--times", type=Path, default=None)
    ap.add_argument("--track", type=Path, default=None)
    ap.add_argument("--points", type=Path,
                    default=Path("space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json"))
    ap.add_argument("--structures", type=Path,
                    default=Path("space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/site_structures.json"))
    ap.add_argument("--title", default="PLEXIL Baseline — Mission B")
    ap.add_argument("--mission", default=DEFAULT_MISSION)
    ap.add_argument("--from-sim", type=float, default=-1e9)
    ap.add_argument("--to-sim", type=float, default=1e9)
    ap.add_argument("--width", type=int, default=OUT_W)
    a = ap.parse_args()

    cap = cv2.VideoCapture(str(a.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    times_path = a.times or Path(f"{a.video}.times")
    times = [float(x) for x in times_path.read_text().split()] if times_path.exists() else []
    events = json.loads(a.timeline.read_text())["events"]
    if len(times) < n:
        t0 = min(e.get("sim_t", e.get("sim_t_start", 0.0)) for e in events)
        t1 = max(e.get("sim_t", e.get("sim_t_end", 0.0)) for e in events)
        times = [t0 + (t1 - t0) * i / max(n - 1, 1) for i in range(n)]
        print(f"no {times_path.name}: assuming the video spans sim {t0:.0f}-{t1:.0f} s")

    stamps, states = plexil_timeline(events, a.mission)
    track = json.loads(a.track.read_text())["track"] if a.track else []
    places = {}
    if a.points.exists():
        ix = json.loads(a.points.read_text())["points"]
        places = {k: {**ix[k], "label": PLACES[k]} for k in PLACES if k in ix}
    track_t = [s["t"] for s in track]
    fonts = (ImageFont.truetype(FONT, 12), ImageFont.truetype(FONT, 14), ImageFont.truetype(FONT_B, 26),
             ImageFont.truetype(FONT_M, 13), ImageFont.truetype(FONT_B, 14))
    site = Map(a.structures, MAP_W, track, places, font=fonts[0]) if track and a.structures.exists() else None

    scale = a.width / w
    out_w, out_h = a.width, int(round(h * scale / 2) * 2)
    tmp = a.out.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))
    written = 0
    for i in range(n):
        ok, frame = cap.read()
        if not ok:
            break
        sim_t = times[min(i, len(times) - 1)]
        if not (a.from_sim <= sim_t <= a.to_sim):
            continue
        canvas = Image.fromarray(cv2.cvtColor(cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_CUBIC),
                                              cv2.COLOR_BGR2RGB)).convert("RGBA")
        j = max(bisect.bisect_right(stamps, sim_t) - 1, 0)
        canvas.alpha_composite(panel(states[j], sim_t, a.title, fonts, moving(track, track_t, sim_t)), (PAD, PAD))
        if site is not None:
            canvas.alpha_composite(site.frame(sim_t), (out_w - MAP_W - PAD, out_h - MAP_W - PAD))
        writer.write(cv2.cvtColor(np.array(canvas.convert("RGB")), cv2.COLOR_RGB2BGR))
        written += 1
    cap.release()
    writer.release()
    import subprocess
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-c:v", "libx264", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(a.out)], check=True)
    tmp.unlink()
    print(f"wrote {a.out}: {written} frames, {written / fps:.0f} s, {len(states)} states, mini-map: {site is not None}")


if __name__ == "__main__":
    main()
