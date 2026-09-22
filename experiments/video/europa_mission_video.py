"""EUROPA as it ran: the same follow-camera-plus-cards layout `mission_video.py`/`plexil_mission_video.py` use,
content adapted to what EUROPA actually does.

    openral/.venv/bin/python experiments/video/europa_mission_video.py <follow.mp4> <run>/europa_timeline.json <out.mp4> \\
        [--times <follow.mp4.times>] [--track <track.json>] [--title "..."] [--mission "..."] [--from-sim 0 --to-sim 1e9]

`<run>/europa_timeline.json` comes from `europa_timeline_from_logs.py`.

Shared with Ours'/PLEXIL's videos, unchanged, because these are properties of the run, not of the method: the
header clock/motion line, the mini-map, the colour rule, the RECORD card.

What is different, and is the point of this file: EUROPA has no fixed plan graph to draw a cursor through (PLEXIL's
card). Given the mission's own goals, it re-derives a fresh activity sequence every time it starts toward the next
one -- so the video shows two things PLEXIL's never has to: **GOALS**, the few outcomes the mission actually asks
for (fixed, like PLEXIL's steps, but these are the mission's own objectives, not an authored procedure), and
**PLAN**, the activity list the solver *derived* toward whichever goal is active right now, replaced whole the
next time it replans. Watching PLAN change -- appear, execute step by step, get replaced by a new one -- is
watching the planning happen, which is the whole reason to use EUROPA over a hand-sequenced plan. NOW's second
line names which goal the current step serves, in place of PLEXIL's library call (EUROPA has no library, only a
goal it is working toward).
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

DEFAULT_MISSION = ("Deliver the spare ORU staged on the depot stand to the spares shelf of PDU-1, then return the "
                    "rover to the dock with the arm stowed. EUROPA is given only this outcome, not a procedure.")


def goal_label(g) -> str:
    """A goal tuple (`timeline, predicate, params, final`) in words, not NDDL identifiers."""
    tl, pred, params = g[0], g[1], g[2]
    if tl.endswith(".loc") and pred == "On":
        return f"{plain(tl[:-4])} on {plain(params.get('support', '?'))}"
    if tl == "rover.posture":
        return f"arm {pred.lower()}"
    if tl == "rover.base" and pred == "At":
        return f"base at {plain(params.get('loc', '?'))}"
    return f"{plain(tl)} {plain(pred)}"


def goal_met(state: dict, g) -> bool:
    return state.get(g[0]) == [g[1], g[2]]


def europa_timeline(events: list[dict], mission: str) -> tuple[list[float], list[dict]]:
    """The state of the mission after every host event, keyed to sim time. Mirrors `mission_video.py`'s
    `timeline()` in shape; see the module docstring for what the content means and why it differs from PLEXIL's."""
    goals, state = [], {}
    plan_n, plan_solved, plan_steps, activities, plan_idx = 0, None, 0, [], 0
    now_cap, log = None, []
    times, states = [], []

    def note(text: str, kind: str, detail: str = "") -> None:
        nonlocal log
        log = (log[-7:] if len(log) >= 8 else log) + [{"t": t, "text": text, "kind": kind, "detail": detail}]

    for e in events:
        t, k = e["sim_t"], e["kind"]
        if k == "mission":
            goals, state = e["goals"], dict(e["state"])
        elif k == "plan":
            plan_n, plan_solved, plan_steps, activities, plan_idx = e["n"], e.get("solved"), e.get("steps", 0), e.get("activities", []), 0
        elif k == "dispatch":
            now_cap = e["capability"]
        elif k == "result":
            state, now_cap = dict(e["state"]), None
            plan_idx += 1
            ok = e["success"]
            note(f"{plain(e['capability'])} {'finished' if ok else 'failed'}", "good" if ok else "bad",
                 "" if ok else str(e.get("failure_reason") or ""))
        elif k == "done":
            state = dict(e["state"])
        elif k == "no_plan":
            note("no plan found -- escalated to the operator", "bad", "")
        else:
            continue
        goal_rows, marked_active = [], False
        for g in goals:
            if goal_met(state, g):
                goal_rows.append(("done", goal_label(g)))
            elif not marked_active:
                goal_rows.append(("active", goal_label(g)))
                marked_active = True
            else:
                goal_rows.append(("pending", goal_label(g)))
        plan_rows = [("done" if i < plan_idx else "active" if i == plan_idx and now_cap else "pending",
                     plain(act[0].split(".", 1)[1])) for i, act in enumerate(activities)]  # act: [type, params]
        active_goal = next((goal_label(g) for g in goals if not goal_met(state, g)), "")
        times.append(t)
        states.append({"mission": mission, "goals": goal_rows, "plan_n": plan_n, "plan_solved": plan_solved,
                       "plan_steps": plan_steps, "plan": plan_rows, "now": now_cap, "active_goal": active_goal,
                       "log": list(log)})
    return times, states


def panel(state: dict, sim_t: float, title: str, fonts, moving_now: str = "") -> Image.Image:
    """Same card shape as `mission_video.py`'s -- clock, mission, goals, plan, now, record. GOALS/PLAN replace
    Ours' single PLAN card; see the module docstring for what each means for EUROPA."""
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

    def rows(items, cap_width):
        nonlocal y
        for status, label in items[:cap_width]:
            glyph, here = LEDGER.get(status, ("·", False))
            colour = INK if here else (FAINT if status == "done" else DIM)
            ops.append(("text", y, x0, glyph, body, colour))
            ops.append(("text", y, x0 + 24, elide(label, body, inner - 24), body, colour))
            y += body.size + 6

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

    caption("goals")  # the mission's own outcomes, fixed -- not a method-authored procedure
    rows(state["goals"], 6)
    y += 10

    caption(f"plan  ·  #{state['plan_n']}, {state['plan_steps']} solver steps" if state["plan_n"] else "plan")
    if state["plan"]:
        rows(state["plan"], 8)
    else:
        text("(not yet solved)", small, FAINT, gap=3)
    y += 10

    caption("now")
    top = y
    text(plain(state["now"]) if state["now"] else "—", head, AMBER if state["now"] else FAINT, dx=12, gap=3)
    if state.get("active_goal"):
        text(elide(f"toward: {state['active_goal']}", body, inner - 12), body, DIM, dx=12, gap=5)
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
    ap.add_argument("--title", default="EUROPA→PLEXIL Baseline — Mission B")
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
        t0, t1 = events[0]["sim_t"], events[-1]["sim_t"]
        times = [t0 + (t1 - t0) * i / max(n - 1, 1) for i in range(n)]
        print(f"no {times_path.name}: assuming the video spans sim {t0:.0f}-{t1:.0f} s")

    stamps, states = europa_timeline(events, a.mission)
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
