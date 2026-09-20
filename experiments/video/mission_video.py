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
PANEL_W, PAD, MAP_W, OUT_W = 560, 22, 360, 1600
INK = (238, 240, 244)
DIM = (168, 176, 188)
ROLE = {"reasoner": (128, 196, 255), "vlm": (196, 160, 255), "tool": (150, 230, 170),
        "skill": (240, 206, 120), "harness": (150, 230, 170), "operator": (255, 176, 120)}


def wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for para in str(text).splitlines() or [""]:
        out += textwrap.wrap(para, width) or [""]
    return out


def timeline(events: list[dict]) -> tuple[list[float], list[dict]]:
    """The state of the mission after every event, and the simulation time it took effect."""
    state = {"mission": "", "phase": "waiting for the mission", "plan": [], "chat": [], "reasoner": "", "vlm": "",
             "call": "", "guard": "", "result": "", "verified": [], "held": "none", "stage": "", "report": ""}
    times, states, step = [], [], 0

    def say(role: str, text: str, detail: str = "") -> None:
        state["chat"] = state["chat"][-40:] + [{"role": role, "text": str(text), "detail": str(detail)}]

    for e in events:
        k = e["kind"]
        if k == "mission_received":
            state.update(mission=e["text"], phase="mission received")
            say("operator", "mission control", e["text"])
        elif k == "reasoner_attached":
            state["reasoner"] = e["model"]
            state["phase"] = f"reasoner attached ({e['model']})"
        elif k == "tool_proposed":
            step += 1
            args = json.dumps(e.get("args", {}), separators=(",", ":"))
            state.update(call=f"#{step} {e['tool']} {args}", guard="", result="", verified=[], stage="",
                         phase="the model chose the next operation")
            if e.get("rationale"):
                say("reasoner", f"step {step}", e["rationale"])
            say("tool", f"{e['tool']}", args)
        elif k == "reasoner_step_failed":
            step += 1
            say("reasoner", "output rejected, fed back", e.get("detail", "")[:300])
            state["phase"] = "the model's output was not an executable call"
        elif k == "guard_decision":
            state.update(guard=f"{e['outcome'].upper()}: {e['reason']}", phase="invariant / authority guard")
            say("harness", f"guard {e['outcome']}", e["reason"])
        elif k == "execution_started":
            state["phase"] = "executing through the capability boundary"
        elif k == "execution_feedback":
            phase = e.get("phase") or ""
            if phase not in ("dispatched", "executing") and phase != state["stage"]:
                state["stage"] = phase
                say("skill", f"{e.get('capability')} · {phase}", "")
        elif k == "execution_finished":
            ok = e.get("success")
            state["result"] = "success" if ok else f"FAILED {e.get('failure_reason','')[:200]}"
            state["phase"] = "the capability returned"
            say("skill" if ok else "harness", f"{e.get('capability')} {'completed' if ok else 'failed'}",
                "" if ok else e.get("failure_reason", "")[:300])
        elif k == "effect_verified":
            holds = e.get("holds")
            state["verified"] = state["verified"][-3:] + [f"{e['effect']}: {'HOLDS' if holds else 'does not hold'}"]
            state["phase"] = "independent effect verification"
            if e["effect"] in ("item_held", "item_still_held"):
                state["held"] = e.get("target", "the item") if holds else "none (not confirmed)"
            say("harness", f"verified {e['effect']}", "holds" if holds else "does not hold")
        elif k == "query_answered":
            value = e.get("value") or {}
            if e.get("query") == "observe" and value:
                say("vlm", f"observe · {value.get('camera','')} camera ({value.get('model','')})", value.get("answer", ""))
            elif e.get("query") == "held_item" and value:
                say("vlm", "held_item", f"holding={value.get('holding')} what={value.get('what','')}")
            else:
                say("tool", f"{e.get('query')} answered", json.dumps(value, separators=(",", ":"))[:220])
            state["phase"] = f"query answered: {e.get('query')}"
        elif k == "local_tool":
            say("tool", e.get("tool", "working plan"), str(e.get("detail", ""))[:220])
        elif k == "ledger_changed":
            mark = {"done": "[x]", "abandoned": "[-]", "active": "[>]", "pending": "[ ]", "verifying": "[?]"}
            state["plan"] = [f"{mark.get(t['status'], '[ ]')} {t['text']}" for t in e["ledger"]["tasks"]]
        elif k in ("operator_report", "operator_request"):
            state["report"] = e["text"]
            state["phase"] = "report to mission control"
            say("operator", "report to mission control", e["text"])
        else:
            continue
        times.append(e["sim_t"])
        states.append({**state, "plan": list(state["plan"]), "chat": list(state["chat"]),
                       "verified": list(state["verified"])})
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
    f, fb, fm = fonts
    img = Image.new("RGBA", (PANEL_W, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, PANEL_W - 1, height - 1], radius=14, fill=(22, 25, 31, 168), outline=(120, 130, 150, 120))
    y = 14

    def line(text, font=f, fill=INK, dx=0, gap=4):
        nonlocal y
        d.text((14 + dx, y), text, font=font, fill=fill)
        y += font.size + gap

    line(title, fb, (255, 255, 255), gap=8)
    line(f"sim t {sim_t:8.1f} s", fm, (255, 214, 102), gap=10)
    line("MISSION", fb, DIM)
    for t in wrap(state["mission"], 66)[:3]:
        line(t, f)
    y += 6
    line("DEVICES", fb, DIM)
    for t in (dev or ["(no telemetry track)"]):
        line(t, fm, INK)
    y += 6
    line("STATE", fb, DIM)
    line(f"phase   {textwrap.shorten(state['phase'], 58)}", fm, INK)
    line(f"held    {textwrap.shorten(str(state['held']), 58)}", fm, INK)
    if state["call"]:
        for i, t in enumerate(wrap(f"call    {state['call']}", 62)[:2]):
            line(t, fm, (150, 230, 170))
    if state["guard"]:
        line(textwrap.shorten(f"guard   {state['guard']}", 62), fm, (255, 176, 120))
    if state["result"]:
        for t in wrap(f"result  {state['result']}", 62)[:2]:
            line(t, fm, INK if state["result"] == "success" else (240, 140, 140))
    for v in state["verified"][-3:]:
        line(textwrap.shorten(f"verify  {v}", 62), fm, (150, 230, 170) if "HOLDS" in v else (240, 140, 140))
    y += 6
    if state["plan"]:
        line("WORKING PLAN (the agent's own)", fb, DIM)
        for t in state["plan"][-6:]:
            line(textwrap.shorten(t, 64), fm, INK if t.startswith("[>") else DIM)
        y += 6
    line("REASONER / VISION MODEL / CALLS", fb, DIM)
    top = y
    entries = []
    for m in state["chat"]:
        head = f"{m['role']}: {m['text']}"
        block = [(ROLE.get(m["role"], INK), t, fb if i == 0 else f) for i, t in enumerate(wrap(head, 60)[:2])]
        block += [(DIM, "    " + t, f) for t in wrap(m["detail"], 62)[:4]] if m["detail"] else []
        entries.append(block)
    lines = [ln for block in entries for ln in block + [(None, "", f)]]
    room = (height - top - 14) // (f.size + 4)
    for colour, text, font in lines[-room:]:
        if colour is not None:
            d.text((14, y), text, font=font, fill=colour)
        y += f.size + 4
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

    scale = OUT_W / w
    out_w, out_h = OUT_W, int(round(h * scale / 2) * 2)
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
