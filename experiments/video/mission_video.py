"""The mission as it ran: the robot-following view, the harness's state, and what the remote models said.

    openral/.venv/bin/python experiments/video/mission_video.py <follow.mp4> <run>/ours/events.jsonl <out.mp4> \
        [--times <follow.mp4.times>] [--track <track.json>] [--title "..."] [--from-sim 0 --to-sim 1e9]

Layout: the follow camera fills the frame; a translucent panel down the left carries the mission, the state of the
robot and its services, the agent's working plan, and beneath them a chat of the remote reasoner and vision model
with every tool and rSkill call between them; a corner holds a plan view of the site with the rover on it.

Every panel line is read from the run's own record (`events.jsonl`, the same simulation clock as the video's
`.times`), so the video states what the run states. The mini-map's poses come from the evaluator track
(`track_from_bag.py`), for drawing only.
"""
import argparse
import bisect
import json
import math
import subprocess
import textwrap
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
PANEL_W, PAD, MAP_W, OUT_W = 560, 22, 360, 1600  # OUT_W is the default; --width overrides it
#: The panel and the map are fixed pixel sizes, so a wider output gives them proportionally less of the frame
#: and the follow camera proportionally more. Record the follow camera at the width you compose at: scaling it
#: up is the only thing here that costs picture quality, and rendering it larger costs almost nothing -- the
#: sim ran at 0.324x real time with a 960x540 stream against 0.353x with none at all (gb1 against ga8).
INK = (238, 240, 244)
DIM = (168, 176, 188)
# (the log colours its own lines; see panel())


def wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for para in str(text).splitlines() or [""]:
        out += textwrap.wrap(para, width) or [""]
    return out


def timeline(events: list[dict]) -> tuple[list[float], list[dict]]:
    """The state of the mission after every event, and the simulation time it took effect.

    One plain line per thing that happened, in the words the run itself used. What is deliberately not here: the
    raw arguments of every call, the stage feedback of every skill, the guard's assent, and the queries the
    boundary answers from its own state. Those are in `events.jsonl` for anyone reading the record; on a video
    they crowd out the four things a viewer needs -- the mission, the plan, what is happening now, and what has
    happened.
    """
    state = {"mission": "", "plan": [], "log": [], "now": "", "stage": "", "held": "nothing"}
    times, states, step = [], [], 0

    def note(text: str, kind: str = "plain") -> None:
        state["log"] = state["log"][-40:] + [{"t": e["sim_t"], "text": str(text), "kind": kind}]

    for e in events:
        k = e["kind"]
        if k == "mission_received":
            state["mission"] = e["text"]
        elif k == "tool_proposed":
            step += 1
            state.update(now=f"{e['tool']}", stage="")
            note(f"{e['tool']} — {textwrap.shorten(e.get('rationale') or 'no reason given', 90)}", "call")
        elif k == "reasoner_step_failed":
            note("the model's answer was not a usable call; fed back to it", "bad")
        elif k == "guard_decision" and e.get("outcome") != "allow":
            note(f"refused: {e.get('reason', '')}", "bad")
        elif k == "execution_feedback":
            phase = e.get("phase") or ""
            if phase not in ("dispatched", "executing"):
                state["stage"] = phase
        elif k == "execution_finished":
            state["stage"] = ""
            if e.get("success"):
                note(f"{e.get('capability')} finished", "good")
            else:
                note(f"{e.get('capability')} failed — {textwrap.shorten(e.get('failure_reason', ''), 120)}", "bad")
        elif k == "effect_verified":
            holds = e.get("holds")
            note(f"{e['effect']}: {'verified' if holds else 'NOT verified'}", "good" if holds else "bad")
            if e["effect"] in ("item_held", "item_still_held"):
                state["held"] = (e.get("target") or "the item") if holds else "nothing"
            if e["effect"] == "item_placed" and holds:
                state["held"] = "nothing"
        elif k == "query_answered":
            v = e.get("value") or {}
            if e.get("query") == "observe":
                note(f"camera: {textwrap.shorten(v.get('answer', ''), 110)}", "look")
            elif e.get("query") == "held_item":
                o = v.get("observed") or {}
                note(f"camera on the jaws: {textwrap.shorten(o.get('what') or 'nothing', 70)}", "look")
            else:
                continue
        elif k == "ledger_changed":
            mark = {"done": "done", "abandoned": "left", "active": "now", "verifying": "check"}
            state["plan"] = [(mark.get(t["status"], ""), t["text"]) for t in e["ledger"]["tasks"]]
        elif k in ("operator_report", "operator_request"):
            note("reported to mission control", "good")
        else:
            continue
        times.append(e["sim_t"])
        states.append({**state, "plan": list(state["plan"]), "log": list(state["log"])})
    return times, states


PLACES = {"depot_stand/slot_0": "depot", "pdu_1_shelf/shelf": "PDU-1 shelf"}


class Map:
    """A plan view of the site: surveyed structures, the rover's path, where it is now, and the carried item."""

    def __init__(self, structures: Path, size: int, track: list[dict], points: dict | None = None):
        self.size = size
        self.boxes = json.loads(structures.read_text())["structures"]
        xs = [b["center"][0] for b in self.boxes] + [t["robot"][0] for t in track]
        ys = [b["center"][1] for b in self.boxes] + [t["robot"][1] for t in track]
        pad = 6.0
        self.lo = np.array([min(xs) - pad, min(ys) - pad])
        self.hi = np.array([max(xs) + pad, max(ys) + pad])
        self.scale = size / max(self.hi - self.lo)
        self.base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.base)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=12, fill=(14, 17, 22, 168))
        for b in self.boxes:
            c, (sx, sy), yaw = np.array(b["center"]), b["size_xy"], b["yaw"]
            r = np.array([[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]])
            pts = [tuple(self.px(c + r @ np.array([dx * sx / 2, dy * sy / 2]))) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            tall = min(255, 90 + int(b.get("z1", 1.0) * 60))
            d.polygon(pts, fill=(tall // 3, tall // 3, tall // 2, 230), outline=(120, 130, 150, 255))
        for key, label in (points or {}).items():
            q = self.px(np.array(points[key]["xyz"][:2]))
            d.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3], fill=(120, 190, 255, 255))
            d.text((q[0] + 6, q[1] - 7), points[key].get("label", key), fill=(190, 210, 235, 255))
        d.ellipse([self.px([0, 0])[0] - 4, self.px([0, 0])[1] - 4, self.px([0, 0])[0] + 4, self.px([0, 0])[1] + 4],
                  outline=(255, 214, 102, 255), width=2)
        d.text((self.px([0, 0])[0] + 7, self.px([0, 0])[1] - 7), "dock", fill=(255, 214, 102, 255))
        self.track = track
        self.t = [s["t"] for s in track]

    def px(self, xy) -> np.ndarray:
        rel = (np.array(xy) - self.lo) / (self.hi - self.lo)
        return np.array([rel[0] * self.size, (1 - rel[1]) * self.size])  # +y up, like the site map

    def frame(self, sim_t: float) -> Image.Image:
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        i = min(bisect.bisect_left(self.t, sim_t), len(self.track) - 1)
        path = [tuple(self.px(s["robot"][:2])) for s in self.track[max(0, i - 3000):i + 1]]
        if len(path) > 1:
            d.line(path, fill=(90, 160, 240, 200), width=2)
        s = self.track[i]
        p, yaw = self.px(s["robot"][:2]), s["robot"][2]
        nose = np.array([math.cos(yaw), math.sin(yaw)]) * 14
        side = np.array([-nose[1], nose[0]]) * 0.55
        d.polygon([tuple(p + np.array([nose[0], -nose[1]])), tuple(p - np.array([nose[0], -nose[1]]) + np.array([side[0], -side[1]])),
                   tuple(p - np.array([nose[0], -nose[1]]) - np.array([side[0], -side[1]]))], fill=(255, 214, 102, 255))
        if s.get("item"):
            q = self.px(s["item"][:2])
            held = float(np.linalg.norm(np.array(s["item"][:2]) - np.array(s["robot"][:2]))) < 1.2  # riding with the rover
            d.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], fill=(120, 230, 140, 255) if held else (240, 120, 120, 255))
        return img


def devices(track: list[dict], stamps: list[float], sim_t: float) -> list[str]:
    """The robot's own state around this moment: where it is, how fast, what the jaws read."""
    if not track:
        return []
    i = min(bisect.bisect_left(stamps, sim_t), len(track) - 1)
    s = track[i]
    j = max(i - 5, 0)
    dt = max(s["t"] - track[j]["t"], 1e-3)
    speed = float(np.linalg.norm(np.array(s["robot"][:2]) - np.array(track[j]["robot"][:2])) / dt)
    jaw = s.get("jaw")
    grip = "" if jaw is None else ("open" if jaw > 0.6 else "closed, empty" if jaw < 0.13 else "closed on something")
    return [f"base    x {s['robot'][0]:6.2f}  y {s['robot'][1]:6.2f}  yaw {math.degrees(s['robot'][2]):6.1f} deg",
            f"drive   {speed:4.2f} m/s",
            f"gripper {jaw:5.3f} rad  {grip}" if jaw is not None else "gripper  -"]


def panel(state: dict, sim_t: float, title: str, height: int, fonts, dev: list[str] | None = None) -> Image.Image:
    """Four things: the mission, the plan, what is happening now, and what has happened."""
    f, fb, fm = fonts
    img = Image.new("RGBA", (PANEL_W, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, PANEL_W - 1, height - 1], radius=14, fill=(22, 25, 31, 178), outline=(120, 130, 150, 110))
    y = 16

    def line(text, font=f, fill=INK, dx=0, gap=5):
        nonlocal y
        d.text((16 + dx, y), text, font=font, fill=fill)
        y += font.size + gap

    line(title, fb, (255, 255, 255), gap=4)
    line(f"{sim_t:.0f} s", fm, (255, 214, 102), gap=14)

    line("MISSION", fb, DIM)
    for t in wrap(state["mission"], 62)[:3]:
        line(t)
    y += 12

    if state["plan"]:
        line("PLAN", fb, DIM)
        for mark, text in state["plan"][:6]:
            here = mark == "now"
            line(f"{mark:5s} {textwrap.shorten(text, 56)}", fm, INK if here else DIM)
        y += 12

    line("NOW", fb, DIM)
    doing = state["now"] or "thinking"
    if state["stage"]:
        doing += f"  ·  {state['stage']}"
    line(doing, fb, (150, 230, 170))
    line(f"holding {textwrap.shorten(state['held'], 52)}", fm, DIM)
    for t in (dev or [])[:1]:
        line(t, fm, DIM)
    y += 12

    line("WHAT HAPPENED", fb, DIM)
    top = y
    colours = {"good": (150, 230, 170), "bad": (240, 140, 140), "call": (128, 196, 255),
               "look": (196, 160, 255), "plain": INK}
    rows = []
    for m in state["log"]:
        body = wrap(m["text"], 52)
        rows.append((colours[m["kind"]], f"{m['t']:6.0f}  {body[0]}"))
        rows += [(DIM, "        " + t) for t in body[1:2]]
    room = max(1, (height - top - 16) // (f.size + 5))
    for colour, text in rows[-room:]:
        line(text, f, colour, gap=5)
    return img

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("events", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--times", type=Path, default=None)
    ap.add_argument("--track", type=Path, default=None)
    ap.add_argument("--points", type=Path,
                    default=Path("space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json"))
    ap.add_argument("--structures", type=Path,
                    default=Path("space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/site_structures.json"))
    ap.add_argument("--title", default="Space Robotics Agent Harness — Mission B")
    ap.add_argument("--from-sim", type=float, default=-1e9)
    ap.add_argument("--to-sim", type=float, default=1e9)
    ap.add_argument("--width", type=int, default=OUT_W, help="composed output width; record the follow camera at it")
    a = ap.parse_args()

    cap = cv2.VideoCapture(str(a.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    times_path = a.times or Path(f"{a.video}.times")
    times = [float(x) for x in times_path.read_text().split()] if times_path.exists() else []
    if len(times) < n:  # a video without its own clock: the mission's own span, spread over the frames
        events0 = [json.loads(line) for line in a.events.read_text().splitlines()]
        t0, t1 = events0[0]["sim_t"], events0[-1]["sim_t"]
        times = [t0 + (t1 - t0) * i / max(n - 1, 1) for i in range(n)]
        print(f"no {times_path.name}: assuming the video spans sim {t0:.0f}-{t1:.0f} s")

    events = [json.loads(line) for line in a.events.read_text().splitlines()]
    stamps, states = timeline(events)
    track = json.loads(a.track.read_text())["track"] if a.track else []
    places = {}
    if a.points.exists():
        ix = json.loads(a.points.read_text())["points"]
        places = {k: ix[k] for k, _ in PLACES.items() if k in ix}
        places = {k: {**v, "label": PLACES[k]} for k, v in places.items()}
    track_t = [s["t"] for s in track]
    site = Map(a.structures, MAP_W, track, {k: v for k, v in places.items()}) if track and a.structures.exists() else None
    fonts = (ImageFont.truetype(FONT, 15), ImageFont.truetype(FONT_B, 16), ImageFont.truetype(FONT_M, 14))

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
        canvas.alpha_composite(panel(states[j], sim_t, a.title, out_h - 2 * PAD, fonts,
                                     devices(track, track_t, sim_t)), (PAD, PAD))
        if site is not None:
            m = site.frame(sim_t)
            canvas.alpha_composite(m, (out_w - MAP_W - PAD, out_h - MAP_W - PAD))
            d = ImageDraw.Draw(canvas)
            d.rounded_rectangle([out_w - MAP_W - PAD, out_h - MAP_W - PAD, out_w - PAD, out_h - PAD], radius=12,
                                outline=(120, 130, 150, 160))
            d.text((out_w - MAP_W - PAD + 12, out_h - MAP_W - PAD + 10), "site plan view", font=fonts[1], fill=(235, 238, 244))
        writer.write(cv2.cvtColor(np.array(canvas.convert("RGB")), cv2.COLOR_RGB2BGR))
        written += 1
    cap.release()
    writer.release()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-c:v", "libx264", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(a.out)], check=True)
    tmp.unlink()
    print(f"wrote {a.out}: {written} frames, {written / fps:.0f} s, {len(states)} states, mini-map: {site is not None}")


if __name__ == "__main__":
    main()
