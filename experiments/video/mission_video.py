"""The mission as it ran: the robot's cameras, the harness's state, and what the remote models said.

    openral/.venv/bin/python experiments/video/mission_video.py <follow.mp4 | run/frames> <run>/ours/events.jsonl <out.mp4> \
        [--times <follow.mp4.times>] [--track <track.json>] [--title "..."] [--fps 6] [--from-sim 0 --to-sim 1e9]

Two sources. A live-rendered follow video (`D0_VIDEO`, with its `.times`) fills the frame. Or, from the raw record of
any finished run with no rerun, the run's own 1 Hz camera frames (`<run>/frames/{front,wrist}/<sim_t>.jpg`, the
evaluator recorder's): the front camera fills the right of the frame with the wrist camera inset, one recorded frame
per video frame at `--fps`. Either way a card on the left carries the clock and the Earth link, the mission, the
agent's plan with the current step marked, what it is doing now and why, the model's own words, and the harness's
last verdicts; a plan view of the site bottom-right has the rover, its path, the route Nav2 is following and the
item in its jaws.

Every panel line is read from the run's own record (`events.jsonl`, the same simulation clock as the video's `.times`
and the frames' names), so the video states what the run states. The mini-map's poses and plans come from the bag
(`track_from_bag.py`), for drawing only; its labelled places are the units the run's own calls went to. The Earth
link is the profile the run ran under (`sim_clock.earth_profile`).
"""
import argparse
import bisect
import json
import math
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_clock import earth_profile  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
PANEL_W, PAD, MAP_W, OUT_W, WRIST_W, INSET = 420, 24, 300, 1600, 400, 14  # OUT_W is the default; --width overrides it
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
    state = {"mission": "", "plan": [], "log": [], "now": "", "why": "", "stage": "", "held": "nothing",
             "thinking": None, "reply": "", "reasoning": "", "llm_s": None, "plan_since": 0.0}
    times, states = [], []
    # wall seconds per simulated second over the run: the model thinks in wall time and the video plays sim time
    span_w, span_s = events[-1]["wall_t"] - events[0]["wall_t"], events[-1]["sim_t"] - events[0]["sim_t"]
    state["wall_per_sim"] = span_w / span_s if span_s > 0 else 1.0

    def note(text: str, kind: str = "plain", detail: str = "") -> None:
        state["log"] = state["log"][-8:] + [{"t": e["sim_t"], "text": str(text), "kind": kind, "detail": detail}]

    for e in events:
        k = e["kind"]
        if k == "mission_received":
            state["mission"] = e["text"]
        elif k == "reasoner_step_started":
            state.update(thinking=e["sim_t"], reply="", reasoning="", llm_s=None)
        elif k == "tool_proposed":
            state.update(now=str(e["tool"]), why=str(e.get("rationale") or ""), stage="", thinking=None,
                         reply=str(e.get("content") or ""), reasoning=str(e.get("reasoning") or ""), llm_s=e.get("llm_s"))
        elif k == "reasoner_step_failed":
            state["thinking"] = None
            note("the model's answer was not a usable call", "bad")
        elif k == "guard_decision" and e.get("outcome") == "approval_required":
            note(f"{e['tool']} held for mission control's approval", "plain", e.get("reason", ""))
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
            state["plan_since"] = e["sim_t"]  # a long line rests when it first appears, then scrolls
        elif k in ("operator_report", "operator_request"):
            note("reported to mission control", "good")
        elif k == "operator_request_sent":
            note("asked mission control", "plain", e["text"])
        elif k == "operator_answered":
            note(f"mission control: {e['outcome']}", "good" if e["outcome"] == "grant" else "bad", e["text"])
        else:
            continue
        times.append(e["sim_t"])
        states.append({**state, "plan": list(state["plan"]), "log": list(state["log"])})
    return times, states


class Map:
    """A plan view of the site: surveyed structures, the rover's path, the route Nav2 is following, where the rover is
    now, and the item in its jaws."""

    def __init__(self, structures: Path, size: int, track: list[dict], points: dict | None = None, font=None,
                 plans: list[dict] | None = None):
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
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=14, fill=(13, 15, 19, 222))
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
        self.plans = plans or []
        self.plan_t = [p["t"] for p in self.plans]

    def px(self, xy) -> np.ndarray:
        rel = (np.array(xy) - self.lo) / (self.hi - self.lo)
        return np.array([rel[0] * self.size, (1 - rel[1]) * self.size])  # +y up, like the site map

    def frame(self, sim_t: float) -> Image.Image:
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        k = bisect.bisect_right(self.plan_t, sim_t) - 1
        if k >= 0 and sim_t - self.plan_t[k] < 2.0:  # Nav2 replans ~2.4 times a second while it drives; older is done
            d.line([tuple(self.px(xy)) for xy in self.plans[k]["xy"]], fill=(236, 238, 242, 170), width=1)
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
        if s.get("held"):
            q = self.px(s["held"]["xyz"][:2])
            d.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(*GREEN, 255))
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


def plain(text: str) -> str:
    """Identifiers as words: `dock_at_feature` reads as "dock at feature" on a screen meant for people."""
    return str(text).replace("_", " ")


def marquee(text: str, font, width: int, height: int, colour, t: float, hold_s: float = 3.0, speed_px_s: float = 30.0) -> Image.Image:
    """A line too long for its box, shown whole: it rests, scrolls left at a reading pace until its end is in
    view, rests again, and starts over -- keyed to the simulation clock the video plays at."""
    full = int(font.getlength(text)) + 1
    over = max(0, full - width)
    if over:
        period = 2 * hold_s + over / speed_px_s
        phase = t % period
        off = 0 if phase < hold_s else (over if phase > hold_s + over / speed_px_s else (phase - hold_s) * speed_px_s)
    else:
        off = 0
    strip = Image.new("RGBA", (max(full, width), height), (0, 0, 0, 0))
    ImageDraw.Draw(strip).text((0, 0), text, font=font, fill=colour)
    return strip.crop((int(off), 0, int(off) + width, height))


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


def panel(state: dict, sim_t: float, title: str, fonts, moving_now: str = "", link: str = "", pace: float = 1.0) -> Image.Image:
    """One card, read top to bottom in the order a viewer needs it: the clock and the robot's state, the mission
    it was given, its own plan with the current step marked, what it is doing now and why, and the harness's
    last four verdicts. One accent (amber) for now, green and red for verdicts, three greys for everything else.
    The card is as tall as its content; nothing wraps past two lines and nothing is cut mid-word. `pace` is simulated
    seconds per video second: scrolling and the thinking dots run on the video's clock, not the mission's."""
    small, body, head, mono, capf = fonts
    x0, inner = 20, PANEL_W - 40
    ops: list[tuple] = []  # ("text", y, x, text, font, colour) | ("strip", y, x, image) | ("rule", y) | ("bar", y0, y1)
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

    # header: the clock, and the robot's own state beside it
    ops.append(("text", y - 2, x0, f"{sim_t:.0f}", head, INK))
    ops.append(("text", y + head.size - small.size - 4, x0 + head.getlength(f"{sim_t:.0f}") + 6, "s", small, FAINT))
    if moving_now:
        w = body.getlength(moving_now)
        ops.append(("text", y + head.size - body.size - 3, x0 + inner - w, moving_now, body, DIM))
    y += head.size + 10
    if link:
        text(link, small, FAINT, gap=6)
    ops.append(("rule", y))
    y += 12

    caption("mission")
    said = wrap(state["mission"], 54)
    for i, t in enumerate(said[:2]):
        text(t + ("…" if i == 1 and len(said) > 2 else ""), body, DIM, gap=4)
    y += 10

    if state["plan"]:
        caption("plan")
        for status, task in state["plan"][:6]:
            glyph, here = LEDGER.get(status, ("·", False))
            colour = INK if here else (FAINT if status == "done" else DIM)
            ops.append(("text", y, x0, glyph, body, colour))
            ops.append(("strip", y, x0 + 24, marquee(plain(task), body, inner - 24, body.size + 6, colour, (sim_t - state.get("plan_since", 0.0)) / pace)))
            y += body.size + 6
        y += 10

    caption("now")
    top = y
    if state.get("thinking") is not None:
        text("deciding", head, DIM, dx=12, gap=3)
    else:
        text(plain((state["now"] or "thinking").split("/")[-1]), head, AMBER, dx=12, gap=3)
    under = "  ·  ".join(x for x in (plain(state["stage"]), f"holding {plain(state['held'])}") if x)
    text(elide(under, body, inner - 12), body, DIM, dx=12, gap=5)
    if state["why"]:
        said = wrap(state["why"], 56)
        for i, t in enumerate(said[:2]):
            text(t + ("…" if i == 1 and len(said) > 2 else ""), small, FAINT, dx=12, gap=3)
    ops.append(("bar", top, y - 2))
    y += 12

    # the remote model, in its own words: while it thinks, that it is thinking and for how long; after, what it
    # said beside the call and the opening of its reasoning. A robot that stands still while a model thinks is not
    # stuck, and the record can say so.
    caption("model")
    if state.get("thinking") is not None:
        waited = (sim_t - state["thinking"]) * state.get("wall_per_sim", 1.0)
        dots = "·" * (1 + int(sim_t / pace * 3) % 3)
        text(f"thinking {dots:<3}", body, AMBER, gap=3)
        text(f"{max(waited, 0):.0f} s waiting on the model", small, FAINT, gap=3)
    elif state.get("reply") or state.get("reasoning"):
        if state.get("reply"):
            said = wrap(state["reply"], 48)  # body size: 56 characters ran past the card
            for i, t in enumerate(said[:2]):
                text(t + ("…" if i == 1 and len(said) > 2 else ""), body, DIM, gap=4)
        if state.get("reasoning"):
            said = wrap(state["reasoning"].replace("\n", " "), 60)
            for i, t in enumerate(said[:3]):
                text(t + ("…" if i == 2 and len(said) > 3 else ""), small, FAINT, gap=3)
        if state.get("llm_s"):
            text(f"answered in {state['llm_s']:.0f} s", small, FAINT, gap=3)
    else:
        text("no reply recorded", small, FAINT, gap=3)
    y += 12

    caption("record")
    for m in state["log"][-4:]:
        colour = {"good": GREEN, "bad": RED}.get(m["kind"], INK)
        ops.append(("text", y + body.size - mono.size, x0, f"{m['t']:5.0f}", mono, FAINT))
        text(elide(plain(m["text"]), body, inner - 48), body, colour, dx=48, gap=3 if m.get("detail") else 7)
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
        elif op[0] == "strip":
            img.alpha_composite(op[3], (op[2], op[1]))
        elif op[0] == "rule":
            d.line([(x0, op[1]), (x0 + inner, op[1])], fill=(255, 255, 255, 28), width=1)
        else:
            d.rounded_rectangle([x0, op[1], x0 + 3, op[2]], radius=2, fill=(*AMBER, 255))
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path, help="a follow-camera video, or a run's frames/ directory")
    ap.add_argument("events", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--times", type=Path, default=None)
    ap.add_argument("--track", type=Path, default=None)
    ap.add_argument("--points", type=Path,
                    default=Path(__file__).resolve().parents[2] / "space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json")
    ap.add_argument("--structures", type=Path,
                    default=Path(__file__).resolve().parents[2] / "space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/site_structures.json")
    ap.add_argument("--title", default="Space Robotics Agent Harness — Mission B")
    ap.add_argument("--from-sim", type=float, default=-1e9)
    ap.add_argument("--to-sim", type=float, default=1e9)
    ap.add_argument("--fps", type=float, default=6.0, help="frames mode: recorded frames per video second")
    ap.add_argument("--width", type=int, default=OUT_W, help="composed output width; record the follow camera at it")
    a = ap.parse_args()

    events = [json.loads(line) for line in a.events.read_text().splitlines()]
    stamps, states = timeline(events)
    track_json = json.loads(a.track.read_text()) if a.track else {"track": [], "plans": []}
    track = track_json["track"]
    # the places the run's own calls went to, one label per unit (a unit's panel, bay and shelf sit a metre apart)
    ix = json.loads(a.points.read_text())["points"]
    groups: dict[str, list] = {}
    for e in events:
        if e["kind"] == "execution_started" and (f := e["args"].get("feature") or e["args"].get("support")):
            groups.setdefault(ix[f]["asset"], []).append(ix[f]["xyz"])
    places = {k: {"xyz": list(np.mean(v, axis=0)), "label": plain(k).upper()} for k, v in groups.items()}
    los = earth_profile(a.events.parent.parent)["los_after_start_s"]
    track_t = [s["t"] for s in track]
    # one scale: a caption, a line of text, the thing happening now, and the clock
    fonts = (ImageFont.truetype(FONT, 12), ImageFont.truetype(FONT, 14), ImageFont.truetype(FONT_B, 26),
             ImageFont.truetype(FONT_M, 13), ImageFont.truetype(FONT_B, 14))
    site = Map(a.structures, MAP_W, track, places, font=fonts[0], plans=track_json["plans"]) if track else None

    if a.video.is_dir():  # the run's own 1 Hz frames, named by simulation time
        names = sorted(p.name for p in (a.video / "front").iterdir())
        times = [float(n.removesuffix(".jpg")) for n in names]
        fps, pace = a.fps, (times[-1] - times[0]) / (len(times) - 1) * a.fps
        cam_x = PANEL_W + 2 * PAD
        cam_w = a.width - cam_x - PAD
        cam_h = cam_w * 3 // 4
        out_w, out_h = a.width, cam_h + 2 * PAD
        wrist_h = WRIST_W * 3 // 4
        map_xy = (out_w - PAD - INSET - MAP_W, out_h - PAD - INSET - MAP_W)

        def plate(img: Image.Image, xy: tuple[int, int], label: str) -> None:
            d = ImageDraw.Draw(img)
            wide = fonts[4].getlength(label)
            d.rounded_rectangle([xy[0], xy[1], xy[0] + wide + 16, xy[1] + 24], radius=6, fill=(13, 15, 19, 210))
            d.text((xy[0] + 8, xy[1] + 4), label, font=fonts[4], fill=DIM)

        def frames():
            for n, t in zip(names, times):
                canvas = Image.new("RGBA", (out_w, out_h), (8, 9, 12, 255))
                canvas.paste(Image.open(a.video / "front" / n).convert("RGB").resize((cam_w, cam_h), Image.BICUBIC), (cam_x, PAD))
                wx, wy = cam_x + INSET, out_h - PAD - INSET - wrist_h
                wrist = Image.open(a.video / "wrist" / n).convert("RGB").resize((WRIST_W, wrist_h), Image.BICUBIC)
                ImageDraw.Draw(canvas).rectangle([wx - 2, wy - 2, wx + WRIST_W + 1, wy + wrist_h + 1], fill=(13, 15, 19, 255))
                canvas.paste(wrist, (wx, wy))
                plate(canvas, (cam_x + INSET, PAD + INSET), "FRONT CAMERA  ·  1 Hz")
                plate(canvas, (wx + 8, wy + 8), "WRIST CAMERA")
                yield t, canvas
    else:
        cap = cv2.VideoCapture(str(a.video))
        fps, pace = cap.get(cv2.CAP_PROP_FPS), 1.0
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        times_path = a.times or Path(f"{a.video}.times")
        times = [float(x) for x in times_path.read_text().split()] if times_path.exists() else []
        if len(times) < n:  # a video without its own clock: the mission's own span, spread over the frames
            t0, t1 = events[0]["sim_t"], events[-1]["sim_t"]
            times = [t0 + (t1 - t0) * i / max(n - 1, 1) for i in range(n)]
            print(f"no {times_path.name}: assuming the video spans sim {t0:.0f}-{t1:.0f} s")
        out_w, out_h = a.width, int(round(h * a.width / w / 2) * 2)
        map_xy = (out_w - MAP_W - PAD, out_h - MAP_W - PAD)

        def frames():
            for i in range(n):
                ok, frame = cap.read()
                if not ok:
                    break
                yield times[min(i, len(times) - 1)], Image.fromarray(cv2.cvtColor(
                    cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)).convert("RGBA")

    tmp = a.out.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))
    written = 0
    for sim_t, canvas in frames():
        if not (a.from_sim <= sim_t <= a.to_sim):
            continue
        j = max(bisect.bisect_right(stamps, sim_t) - 1, 0)
        link = f"Earth up  ·  sets in {los - sim_t:.0f} s" if sim_t < los else "Earth below the horizon  ·  link down"
        canvas.alpha_composite(panel(states[j], sim_t, a.title, fonts, moving(track, track_t, sim_t), link, pace), (PAD, PAD))
        if site is not None:
            canvas.alpha_composite(site.frame(sim_t), map_xy)
        writer.write(cv2.cvtColor(np.array(canvas.convert("RGB")), cv2.COLOR_RGB2BGR))
        written += 1
    writer.release()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-c:v", "libx264", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(a.out)], check=True)
    tmp.unlink()
    print(f"wrote {a.out}: {written} frames, {written / fps:.0f} s, {len(states)} states, mini-map: {site is not None}")


if __name__ == "__main__":
    main()
