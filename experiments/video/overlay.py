"""Mission video with the agent's live state beside it, at 1x sim time.

Input: the SRB robot-following video (`D0_VIDEO=<mp4>` with SRB_VIDEO_SPEEDUP=1, which writes `<mp4>.times`: the sim
time of every frame) and Ours' record (`<log>/ours/events.jsonl`, every event stamped with the same sim clock).
Output: the video padded with a side panel showing, at each moment, the mission, the agent's working plan, the
current step (tool, arguments, rationale), what the guard decided, what the capability boundary returned, the
independent verification, and the latest camera observation -- how OpenRAL + the harness run the mission.

    python3 experiments/video/overlay.py <video.mp4> <events.jsonl> <out.mp4> [--title "..."]
"""
import argparse
import bisect
import json
import subprocess
import textwrap
from pathlib import Path

W_PANEL = 760
WRAP = 58


def esc(t: str) -> str:
    return t.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def wrap(t: str, width=WRAP, lines=3) -> list[str]:
    out = textwrap.wrap(t, width) or [""]
    return out[:lines - 1] + [textwrap.shorten(" ".join(out[lines - 1:]), width, placeholder=" ...")] if len(out) > lines else out


def ts(sec: float) -> str:
    h, rem = divmod(max(sec, 0.0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def states(events: list[dict], title: str):
    """(sim_t, panel lines) at every event that changes what the panel shows."""
    s = dict(plan=[], step="", guard="", result="", verify=[], observe="", phase="waiting for the mission", report="")
    step_no = 0
    out = []
    mission = ""
    for e in events:
        k = e["kind"]
        if k == "mission_received":
            mission, s["phase"] = e["text"], "mission received"
        elif k == "reasoner_attached":
            s["phase"] = f"reasoner attached: {e['model']}"
        elif k == "tool_proposed":
            step_no += 1
            s.update(step=f"#{step_no} {e['tool']} {json.dumps(e['args'], separators=(',', ':'))}", guard="", result="", verify=[],
                     phase="LLM chose a tool", rationale=e.get("rationale", ""))
        elif k == "reasoner_step_failed":
            step_no += 1
            s.update(step=f"#{step_no} (no executable call) {e['tool']}", result=e["detail"][:160], phase="LLM output rejected -> fed back")
        elif k == "guard_decision":
            s["guard"], s["phase"] = f"{e['outcome'].upper()} {e['reason']}", "invariant / authority guard"
        elif k == "execution_started":
            s["phase"] = "executing: capability boundary -> OpenRAL rSkill -> safety kernel -> robot"
        elif k == "execution_finished":
            s["result"] = "success" if e["success"] else f"FAILED: {e['failure_reason'][:120]}"
            s["phase"] = f"capability finished in {e['evidence'].get('sim_s')} s sim"
        elif k == "effect_verified":
            s["verify"] = s["verify"] + [f"{e['effect']}: {'HOLDS' if e['holds'] else 'DOES NOT HOLD'}"]
            s["phase"] = "independent effect verification"
        elif k == "query_answered":
            v = e["value"]
            if e["query"] == "observe" and v:
                s["observe"] = f"[{v['camera']} camera, {v['model']}] {v['answer']}"
                s["result"] = "observation recorded"
            else:
                s["result"] = json.dumps(v, separators=(",", ":"))[:160] if e["success"] else f"FAILED: {e['failure_reason'][:120]}"
            s["phase"] = f"query answered: {e['query']}"
        elif k == "local_tool":
            s["result"], s["phase"] = e["detail"], "working plan updated" if e["success"] else "plan tool refused"
        elif k == "ledger_changed":
            mark = {"done": "[x]", "abandoned": "[-]", "active": "[>]", "pending": "[ ]", "verifying": "[?]"}
            s["plan"] = [f"{mark[t['status']]} {t['text']}" for t in e["ledger"]["tasks"]]
        elif k == "operator_report":
            s["report"], s["phase"] = e["text"], "final report to mission control"
        elif k == "operator_request":
            s["report"], s["phase"] = e["text"], "request to mission control"
        else:
            continue
        lines = [r"{\b1\fs30}" + esc(title) + r"{\b0\fs22}", ""]
        lines += [r"{\b1}MISSION{\b0}"] + [esc(x) for x in wrap(mission, lines=3)] + [""]
        lines += [r"{\b1}PHASE{\b0}  " + esc(s["phase"]), ""]
        lines += [r"{\b1}WORKING PLAN (agent-owned){\b0}"] + [esc(textwrap.shorten(p, WRAP)) for p in s["plan"][-9:]] + [""]
        lines += [r"{\b1}CURRENT STEP{\b0}"] + [esc(x) for x in wrap(s["step"], lines=2)]
        if s.get("rationale"):
            lines += [r"{\i1}" + esc(x) + r"{\i0}" for x in wrap("why: " + s["rationale"], lines=2)]
        if s["guard"]:
            lines += ["guard: " + esc(textwrap.shorten(s["guard"], WRAP - 7))]
        if s["result"]:
            lines += [esc(x) for x in wrap("result: " + s["result"], lines=2)]
        for v in s["verify"][-2:]:
            lines += ["verified: " + esc(v)]
        lines += [""]
        if s["observe"]:
            lines += [r"{\b1}LATEST CAMERA OBSERVATION (VLM){\b0}"] + [esc(x) for x in wrap(s["observe"], lines=4)] + [""]
        if s["report"]:
            lines += [r"{\b1}REPORT TO MISSION CONTROL{\b0}"] + [esc(x) for x in wrap(s["report"], lines=6)]
        out.append((e["sim_t"], lines))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("events", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--title", default="OpenRAL + space-native harness (Ours)")
    a = ap.parse_args()
    times = [float(x) for x in Path(f"{a.video}.times").read_text().split()]
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                                       "-of", "json", str(a.video)], capture_output=True, text=True).stdout)["streams"][0]
    num, den = map(int, probe["r_frame_rate"].split("/"))
    fps, w, h = num / den, probe["width"], probe["height"]
    events = [json.loads(line) for line in a.events.read_text().splitlines()]
    panel = states(events, a.title)
    ass = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w + W_PANEL}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
        f"Style: Panel,DejaVu Sans,22,&H00F0F0F0,&H00000000,&H00000000,0,0,1,0,0,7,{w + 18},10,14",
        "Style: Clock,DejaVu Sans Mono,24,&H0000FFFF,&H00000000,&H80000000,1,0,3,6,0,9,10,10,10", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def vt(sim_t):  # video time of the first frame at or after a sim time
        return bisect.bisect_left(times, sim_t) / fps

    end = len(times) / fps
    for i, (t, lines) in enumerate(panel):
        t1 = vt(panel[i + 1][0]) if i + 1 < len(panel) else end
        if t1 > vt(t):
            text = "\\N".join(lines)
            ass.append(f"Dialogue: 0,{ts(vt(t))},{ts(t1)},Panel,,0,0,0,,{text}")
    step = max(1, int(round(fps)))
    for i in range(0, len(times), step):
        ass.append(f"Dialogue: 1,{ts(i / fps)},{ts((i + step) / fps)},Clock,,0,0,0,,sim t = {times[i]:7.1f} s  (1x sim time)")
    sub = a.out.with_suffix(".ass")
    sub.write_text("\n".join(ass) + "\n")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(a.video), "-vf",
                    f"pad={w + W_PANEL}:{h}:0:0:0x14171c,ass={sub}", "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", str(a.out)], check=True)
    print(f"wrote {a.out} ({end:.0f} s, {len(panel)} panel states)")


if __name__ == "__main__":
    main()
