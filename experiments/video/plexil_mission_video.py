"""PLEXIL as it ran: the same layout `mission_video.py` composes for Ours (`compose()`: the replayed third-person view,
the robot's front and wrist cameras, the site plan), with a card adapted to what PLEXIL actually has instead of copied
from it.

    openral/.venv/bin/python experiments/video/plexil_mission_video.py <replay dir | follow.mp4> <run>/plexil_timeline.json \
        <out.mp4> [--run <run>] [--track <track.json>] [--title "..."] [--mission "..."] [--top A,B,...] [--from-sim 0 --to-sim 1e9]

`<run>/plexil_timeline.json` comes from `plexil_timeline_from_logs.py` (needs the ROS-sourced Python for
`rosbag2_py`; this script needs only `cv2`/`PIL`/`numpy`, same split as `track_from_bag.py` / `mission_video.py`).

The mission is the brief the simulator published (`mission_brief`, from the run's bag) unless `--mission` says
otherwise; `--top` names the plan's top-level steps when it is not Mission B's (Mission A's `MissionA_Covered.ple`:
Identify,ToUnit,Reset,Return,FinalCheck), the same list `plexil_timeline_from_logs.py` was given.

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

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mission_video import (AMBER, DIM, FAINT, GREEN, INK, PANEL_W, RED, LEDGER, compose, elide, load_fonts,
                            mission_brief, places_from_calls, plain, video_args, wrap)

TOP = ["ToSource", "Pick", "ToDestination", "Place", "Return"]


def plexil_timeline(events: list[dict], mission: str, top: list[str] = TOP) -> tuple[list[float], list[dict]]:
    """The state of the mission after every node-status/capability event, keyed to the sim clock the video plays
    at (`plexil_timeline_from_logs.py` already resolved PLEXIL's wall-clock logs to it). Mirrors
    `mission_video.py`'s `timeline()` in shape (a (times, states) pair a frame loop can `bisect` into), not in
    content -- see the module docstring for what differs and why."""
    top_status = {n: "pending" for n in top}
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
        states.append({"plan": [(top_status[n], n) for n in top], "top_active": top_active, "lib_active": lib_active,
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


def main() -> None:
    ap = argparse.ArgumentParser()
    video_args(ap, "<run>/plexil_timeline.json (plexil_timeline_from_logs.py)", "PLEXIL Baseline")
    ap.add_argument("--mission", default=None, help="default: the brief the simulator published (the run's bag)")
    ap.add_argument("--top", default=",".join(TOP), help="comma-separated top-level node names, for a plan shape other than Mission B's")
    a = ap.parse_args()
    a.run = a.run or a.record.parent
    events = json.loads(a.record.read_text())["events"]
    stamps, states = plexil_timeline(events, a.mission or mission_brief(a.run), a.top.split(","))
    places = places_from_calls([e["args"] for e in events if e["kind"] == "capability"], json.loads(a.points.read_text())["points"])
    fonts = load_fonts()

    def panel_at(sim_t: float, moving_now: str, pace: float) -> Image.Image:
        return panel(states[max(bisect.bisect_right(stamps, sim_t) - 1, 0)], sim_t, a.title, fonts, moving_now)

    compose(a, panel_at, places)


if __name__ == "__main__":
    main()
