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
import re
import subprocess
import textwrap
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
PANEL_W, PAD, MAP_W, OUT_W = 440, 24, 300, 1600  # OUT_W is the default; --width overrides it
#: The panel and the map are fixed pixel sizes, so a wider output gives them proportionally less of the frame
#: and the follow camera proportionally more. Record the follow camera at the width you compose at: scaling it
#: up is the only thing here that costs picture quality, and rendering it larger costs almost nothing -- the
#: sim ran at 0.324x real time with a 960x540 stream against 0.353x with none at all (gb1 against ga8).

#: One accent, two verdicts, three greys. A panel that colours nine kinds of line has told the eye that nothing
#: in particular is happening; the amber is the robot's own now, and green and red are the harness's verdict on
#: what it did. Everything else is text.
INK = (236, 238, 242)
DIM = (152, 160, 174)
FAINT = (106, 114, 128)
AMBER = (255, 196, 90)
GREEN = (126, 214, 150)
RED = (236, 124, 124)


def wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for para in str(text).splitlines() or [""]:
        out += textwrap.wrap(para, width) or [""]
    return out


def timeline(events: list[dict]) -> tuple[list[float], list[dict]]:
    """The state of the mission after every event, and the simulation time it took effect.

    Two channels, and the split is the point. **What the robot is doing now** carries the operation and the model's
    own reason for it -- that sentence is the whole claim of the method, so it is read where the eye already is,
    under the operation, and not as one more line scrolling past. **What has happened** carries outcomes only:
    finished, failed, verified, refused. Nothing appears in both, which is what made the old log twice as long as
    it needed to be, every call once as a call and again as a result.

    Deliberately absent: the raw arguments of every call, the stage feedback of every skill, the guard's assent,
    and the queries the boundary answers from its own state. Those are in `events.jsonl` for anyone reading the
    record; on a video they crowd out the four things a viewer needs.
    """
    state = {"mission": "", "plan": [], "log": [], "now": "", "why": "", "stage": "", "held": "nothing"}
    times, states = [], []

    def note(text: str, kind: str = "plain", detail: str = "") -> None:
        state["log"] = state["log"][-8:] + [{"t": e["sim_t"], "text": str(text), "kind": kind, "detail": detail}]

    for e in events:
        k = e["kind"]
        if k == "mission_received":
            state["mission"] = e["text"]
        elif k == "tool_proposed":
            state.update(now=str(e["tool"]), why=str(e.get("rationale") or ""), stage="")
        elif k == "reasoner_step_failed":
            note("the model's answer was not a usable call", "bad")
        elif k == "guard_decision" and e.get("outcome") != "allow":
            note(f"refused — {e.get('reason', '')}", "bad")
        elif k == "execution_feedback":
            phase = e.get("phase") or ""
            if phase not in ("dispatched", "executing"):
                state["stage"] = phase
        elif k == "execution_finished":
            state["stage"] = ""
            if e.get("success"):
                note(f"{e.get('capability')} finished", "good")
            else:
                # the whole reason is the failure's own sentence, which is the one thing a viewer wants when
                # something goes wrong; the error class and the skill's package name in front of it are not
                why = str(e.get("failure_reason", ""))
                m = re.search(r"failed at stage (\w+): (.*)", why, re.S)
                note(f"{e.get('capability')} failed", "bad", f"{m[1]} — {m[2]}" if m else why)
        elif k == "effect_verified":
            holds = e.get("holds")
            note(f"{e['effect']} {'verified' if holds else 'not verified'}", "good" if holds else "bad")
            if e["effect"] in ("item_held", "item_still_held"):
                state["held"] = (e.get("target") or "the item") if holds else "nothing"
            if e["effect"] == "item_placed" and holds:
                state["held"] = "nothing"
        elif k == "ledger_changed":
            state["plan"] = [(t["status"], t["text"]) for t in e["ledger"]["tasks"]]
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

    def __init__(self, structures: Path, size: int, track: list[dict], points: dict | None = None, font=None):
        self.size = size
        self.boxes = json.loads(structures.read_text())["structures"]
        # Fit the map to what the mission uses -- everywhere the rover goes and everywhere it works -- rather than
        # to every surveyed structure on the site. Drawn to the whole site the route was a thumbnail in one corner.
        xs = [t["robot"][0] for t in track] + [p["xyz"][0] for p in (points or {}).values()]
        ys = [t["robot"][1] for t in track] + [p["xyz"][1] for p in (points or {}).values()]
        pad = 8.0  # enough of the base around the route to place it, without shrinking the route to a thumbnail
        self.lo = np.array([min(xs) - pad, min(ys) - pad])
        self.hi = np.array([max(xs) + pad, max(ys) + pad])
        span = float(max(self.hi - self.lo))
        self.lo -= (span - (self.hi - self.lo)) / 2  # square, so a metre is a metre in both directions
        self.hi = self.lo + span
        self.base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.base)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=16, fill=(13, 15, 19, 224),
                            outline=(255, 255, 255, 30), width=1)
        for b in self.boxes:
            c, (sx, sy), yaw = np.array(b["center"]), b["size_xy"], b["yaw"]
            r = np.array([[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]])
            pts = [tuple(self.px(c + r @ np.array([dx * sx / 2, dy * sy / 2]))) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            tall = min(120, 46 + int(b.get("z1", 1.0) * 26))  # taller structures read lighter
            d.polygon(pts, fill=(tall, tall + 4, tall + 12, 255), outline=(150, 160, 176, 200))
        def marked(q, label, colour):
            """A surveyed place: a ring, and its name on a plate of its own so it reads over a structure or the
            route rather than through them."""
            d.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], outline=(*colour, 255), width=2)
            wide = font.getlength(label) if font else 6 * len(label)
            x = q[0] + 10 if q[0] + 12 + wide < size - 10 else q[0] - 10 - wide  # one that would run off goes left
            y = q[1] - 8
            d.rounded_rectangle([x - 4, y - 2, x + wide + 4, y + 14], radius=4, fill=(13, 15, 19, 210))
            d.text((x, y), label, font=font, fill=(*colour, 255))

        for key, p in (points or {}).items():
            marked(self.px(np.array(p["xyz"][:2])), p.get("label", key), (150, 200, 250))
        marked(self.px([0, 0]), "dock", AMBER)
        d.text((16, 14), " ".join("SITE"), font=font, fill=FAINT)
        metres = next(m for m in (20, 10, 5) if m * size / span <= size * 0.42)  # the picture carries its own scale
        bar = int(metres * size / span)
        d.line([(16, size - 20), (16 + bar, size - 20)], fill=(190, 198, 210, 210), width=2)
        for x in (16, 16 + bar):
            d.line([(x, size - 24), (x, size - 16)], fill=(190, 198, 210, 210), width=2)
        d.text((24 + bar, size - 27), f"{metres} m", font=font, fill=(190, 198, 210, 210))
        #: the structures are drawn to their own corners, so the card's are cut back to shape when it is composed
        self.mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(self.mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=16, fill=255)
        self.track = track
        self.t = [s["t"] for s in track]

    def px(self, xy) -> np.ndarray:
        rel = (np.array(xy) - self.lo) / (self.hi - self.lo)
        return np.array([rel[0] * self.size, (1 - rel[1]) * self.size])  # +y up, like the site map

    def frame(self, sim_t: float) -> Image.Image:
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        i = min(bisect.bisect_left(self.t, sim_t), len(self.track) - 1)
        path = [tuple(self.px(s["robot"][:2])) for s in self.track[:i + 1]]
        if len(path) > 1:
            d.line(path, fill=(110, 170, 245, 230), width=2)
        s = self.track[i]
        p, yaw = self.px(s["robot"][:2]), s["robot"][2]
        nose = np.array([math.cos(yaw), math.sin(yaw)]) * 12
        side = np.array([-nose[1], nose[0]]) * 0.6
        d.polygon([tuple(p + np.array([nose[0], -nose[1]])), tuple(p - np.array([nose[0], -nose[1]]) + np.array([side[0], -side[1]])),
                   tuple(p - np.array([nose[0], -nose[1]]) - np.array([side[0], -side[1]]))], fill=(*AMBER, 255))
        if s.get("item"):
            q = self.px(s["item"][:2])
            held = float(np.linalg.norm(np.array(s["item"][:2]) - np.array(s["robot"][:2]))) < 1.2  # riding with the rover
            d.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(*GREEN, 255) if held else (*RED, 255))
        img.putalpha(ImageChops.multiply(img.getchannel("A"), self.mask))
        return img


def moving(track: list[dict], stamps: list[float], sim_t: float) -> str:
    """One line of the robot's own state: how fast it is going and what the jaws are doing. Where it is, the plan
    view says better than six decimals can."""
    if not track:
        return ""
    i = min(bisect.bisect_left(stamps, sim_t), len(track) - 1)
    s = track[i]
    j = max(i - 5, 0)
    dt = max(s["t"] - track[j]["t"], 1e-3)
    speed = float(np.linalg.norm(np.array(s["robot"][:2]) - np.array(track[j]["robot"][:2])) / dt)
    jaw = s.get("jaw")
    grip = "" if jaw is None else ("jaws open" if jaw > 0.6 else "jaws empty" if jaw < 0.13 else "jaws holding")
    return "  ·  ".join(x for x in (f"{speed:.2f} m/s" if speed > 0.01 else "stopped", grip) if x)


#: how a task in the agent's own ledger is drawn: a glyph and whether it is the line being worked on
LEDGER = {"done": ("✓", False), "active": ("▸", True), "verifying": ("▸", True), "abandoned": ("✕", False)}


def elide(text: str, font, width: int) -> str:
    """One line, cut at the last word that fits rather than at a character count -- the panel knows its own width
    and the font knows its own metrics, so nothing needs a guess at how many characters fit."""
    text = " ".join(str(text).split())
    if font.getlength(text) <= width:
        return text
    out = ""
    for word in text.split(" "):
        if font.getlength(f"{out} {word}…".strip()) > width:
            break
        out = f"{out} {word}".strip()
    return (out + "…") if out else text[:1] + "…"


def panel(state: dict, sim_t: float, title: str, fonts, moving_now: str = "") -> Image.Image:
    """Four things, in the order a viewer needs them: what the robot is doing and why, where that sits in its own
    plan, what the harness has just ruled on, and -- once, quietly at the top -- the mission it was given.

    The card is as tall as what it has to say. The full-height slab this replaced held forty log lines at one
    size in five colours, wrapped and cut with `[...]` mid-sentence, and the one thing a viewer actually needs --
    the operation running right now -- was a small green line in the middle of it.
    """
    small, body, head, mono = fonts
    inner = PANEL_W - 2 * 18
    rows: list[tuple] = []  # (font, colour, text, indent, gap after, an optional (text, font, colour) at the margin)

    def row(font, colour, text, dx=0, gap=6, lead=None):
        rows.append((font, colour, text, dx, gap, lead))

    def caption(text):
        row(small, FAINT, " ".join(text.upper()), gap=8)  # letter-spaced: a label, read as a label, not as a line

    row(small, FAINT, elide(title, small, inner), gap=6)
    row(mono, AMBER, f"{sim_t:.0f} s" + (f"   {moving_now}" if moving_now else ""), gap=20)

    caption("mission")
    said = wrap(state["mission"], 56)
    for i, t in enumerate(said[:2]):
        row(body, DIM, t + ("…" if i == 1 and len(said) > 2 else ""), gap=4)
    rows[-1] = (*rows[-1][:4], 22, None)

    if state["plan"]:
        caption("plan")
        for status, text in state["plan"][:6]:
            glyph, here = LEDGER.get(status, ("·", False))
            row(body, INK if here else FAINT, f"{glyph}  {elide(text, body, inner - 22)}", gap=7)
        rows[-1] = (*rows[-1][:4], 22, None)

    caption("now")
    # the agent's own bookkeeping calls are named for the tool table they live in; on a video that prefix is noise
    row(head, AMBER, (state["now"] or "thinking").split("/")[-1], gap=4)
    under = "  ·  ".join(x for x in (state["stage"], f"holding {state['held']}") if x)
    row(body, DIM, elide(under, body, inner), gap=6)
    if state["why"]:
        said = wrap(state["why"], 58)
        for i, t in enumerate(said[:2]):
            row(small, FAINT, t + ("…" if i == 1 and len(said) > 2 else ""), gap=3)
    rows[-1] = (*rows[-1][:4], 22, None)

    caption("what happened")
    for m in state["log"][-4:]:
        colour = {"good": GREEN, "bad": RED}.get(m["kind"], INK)
        row(body, colour, elide(m["text"], body, inner - 46), dx=46, gap=7 if not m.get("detail") else 3,
            lead=(f"{m['t']:5.0f}", mono, FAINT))
        if m.get("detail"):
            row(small, FAINT, elide(m["detail"], small, inner - 46), dx=46, gap=7)

    height = 18 + sum(font.size + gap for font, _, _, _, gap, _ in rows) + 12
    img = Image.new("RGBA", (PANEL_W, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, PANEL_W - 1, height - 1], radius=16, fill=(15, 17, 22, 194),
                        outline=(255, 255, 255, 30), width=1)
    y = 18
    for font, colour, text, dx, gap, lead in rows:
        if lead is not None:
            d.text((18, y + font.size - lead[1].size), lead[0], font=lead[1], fill=lead[2])
        d.text((18 + dx, y), text, font=font, fill=colour)
        y += font.size + gap
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
    # one scale: a caption, a line of text, the thing happening now, and the clock
    fonts = (ImageFont.truetype(FONT, 12), ImageFont.truetype(FONT, 15), ImageFont.truetype(FONT_B, 27),
             ImageFont.truetype(FONT_M, 14))
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
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-c:v", "libx264", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(a.out)], check=True)
    tmp.unlink()
    print(f"wrote {a.out}: {written} frames, {written / fps:.0f} s, {len(states)} states, mini-map: {site is not None}")


if __name__ == "__main__":
    main()
