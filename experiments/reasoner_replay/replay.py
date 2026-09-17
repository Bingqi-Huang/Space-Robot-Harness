"""Offline reasoner comparison on recorded Mission B decision points (no simulator).

Each decision point is an agent record cut before one step: the harness context is rebuilt from the record exactly as
the live agent would render it, and every candidate model chooses one tool call from the same palette. Models that take
images also get the latest wrist-camera frame on record. A rubric fixed before the runs scores the call.

    python3 experiments/reasoner_replay/replay.py [--models A,B] [--repeats N]   (writes <out>/results.jsonl)
"""
import argparse
import base64
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from openai import OpenAI  # noqa: E402

from space_runtime.context import render  # noqa: E402
from space_runtime.facts import apply, empty_facts  # noqa: E402
from space_runtime.tools import capability_tools, local_tools  # noqa: E402

RUNS = REPO / "artifacts/runs"
GATEWAY = "https://llmapi.paratera.com/v1"
OLLAMA = "http://localhost:11434/v1"
MOUNT = (-0.448, 0.727)  # arm mount (x, z) in chassis_base_link
BASE_MOTION = {"navigate_to_pose", "dock_to_pose", "navigate_to_feature", "dock_at_feature"}
ARM_FEATURE = {"plan_ee_to_feature", "move_ee_to_feature"}

# model id -> (endpoint, sees images)
MODELS = {
    "DeepSeek-V4.1-Flash": (GATEWAY, True),
    "Kimi-K3": (GATEWAY, True),
    "GLM-5.3": (GATEWAY, True),
    "Qwen3.8-Max": (GATEWAY, True),
    "qwen3.8:latest": (OLLAMA, True),
}


def tcp_from_feature(args, slot_xz):
    return slot_xz[0] + args.get("offset_m", 0.0), slot_xz[1] + args.get("lift_m", 0.0)


def grip_reachable(xz):
    """Measured on the live arm (vc10, ob5, ob6): a level grip TCP about 0.52-0.68 m from the mount reaches; closer
    runs the elbow into its limit."""
    return 0.52 <= math.dist(xz, MOUNT) <= 0.68


def frame_the_oru(tool, args, slot_xz):
    """Arm at ready, wrist camera sees sky: bring the camera to a reachable pose that views the ORU."""
    if tool in ARM_FEATURE:
        xz = tcp_from_feature(args, slot_xz)
        ok = args.get("orientation") == "grip" and grip_reachable(xz) and args.get("offset_m", 0) >= 0.10
        return ok, f"TCP (x,z)=({xz[0]:.2f},{xz[1]:.2f}) d={math.dist(xz, MOUNT):.2f} {args.get('orientation', 'press')}"
    if tool in BASE_MOTION:
        return False, "moves the base with the arm raised"
    return False, f"no framing move ({tool})"


def after_unreachable(tool, args, slot_xz):
    """An arm goal was reported unreachable: a better arm goal, never base motion with the arm out."""
    if tool in BASE_MOTION:
        return False, "moves the base with the arm raised"
    return frame_the_oru(tool, args, slot_xz)


def no_survey_contact(tool, args, slot_xz):
    """Rover docked 0.23 m closer: do not drive the tool onto the handle from survey coordinates."""
    if tool in ARM_FEATURE and args.get("offset_m", 1.0) < 0.10:
        return False, f"survey-placed contact offset {args.get('offset_m')}"
    if tool in BASE_MOTION:
        return False, "moves the base with the arm raised"
    return True, tool


def approach_handle(tool, args, slot_xz):
    """ORU and handle located in the wrist view: approach the handle by vision."""
    ok = tool == "approach_target" and "handle" in args.get("target", "").lower() and args.get("orientation") == "grip"
    return ok, f"{tool} {args.get('orientation')} standoff {args.get('standoff_m')}"


# (name, record, cut before step, slot (x, z) in the rover frame then, rubric)
POINTS = [
    ("frame the ORU from ready", "ob5", 14, (-1.10, 0.55), frame_the_oru),
    ("after 'no configuration reaches' x2", "ob6_s15", 16, (-1.10, 0.55), after_unreachable),
    ("after 'reachable 0.15 m farther'", "ob6_s15c", 19, (-1.10, 0.55), after_unreachable),
    ("docked closer: tool to the handle?", "ob6_s15", 17, (-0.87, 0.55), no_survey_contact),
    ("handle located: approach", "ob6_s19", 19, (-1.10, 0.55), approach_handle),
]


def cut(record: str, before: int):
    facts, n, image = empty_facts(), 0, None
    for line in (RUNS / record / "ours/events.jsonl").read_text().splitlines():
        ev = json.loads(line)
        if ev["kind"] in ("tool_proposed", "reasoner_step_failed"):
            n += 1
            if n >= before:
                break
        apply(facts, ev)
        v = ev.get("value") if ev["kind"] == "query_answered" else None
        if isinstance(v, dict) and v.get("camera") == "wrist" and v.get("image"):
            image = v["image"]
    return render(facts, before, 80), image


def call(model: str, context: str, image: str | None, tools: list, system: str) -> dict:
    endpoint, vision = MODELS[model]
    client = OpenAI(api_key=os.environ["SPACE_LLM_API_KEY"] if endpoint == GATEWAY else "ollama", base_url=endpoint,
                    timeout=600, max_retries=0)
    content = context
    if vision and image:
        b64 = base64.b64encode(Path(image).read_bytes()).decode()
        content = [{"type": "text", "text": context + "\n\n## LATEST WRIST CAMERA FRAME (on record)\nattached image"},
                   {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]
    t = time.time()
    try:
        r = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
                                           tools=tools, tool_choice="auto")
        tc = r.choices[0].message.tool_calls
        if not tc:
            return dict(s=round(time.time() - t, 1), tool=None, args={}, note=(r.choices[0].message.content or "")[:200])
        return dict(s=round(time.time() - t, 1), tool=tc[0].function.name, args=json.loads(tc[0].function.arguments or "{}"))
    except Exception as exc:  # reason: provider/transport errors are a result of the comparison, recorded as such
        return dict(s=round(time.time() - t, 1), tool=None, args={}, note=f"{type(exc).__name__}: {str(exc)[:150]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--out", type=Path, default=REPO / "artifacts/reasoner_replay")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    tools = capability_tools() + local_tools()
    system = (REPO / "space_runtime/playbook.md").read_text()
    jobs = [(m, p, k) for m in a.models.split(",") for p in POINTS for k in range(a.repeats)]
    contexts = {p[0]: cut(p[1], p[2]) for p in POINTS}

    def run(job):
        m, (name, _, _, slot, rubric), k = job
        ctx, image = contexts[name]
        r = call(m, ctx, image, tools, system)
        ok, why = rubric(r["tool"], r["args"], slot) if r["tool"] else (False, r.get("note", "no tool call"))
        row = dict(model=m, point=name, repeat=k, ok=ok, why=why, **r)
        with (a.out / "results.jsonl").open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{m:22s} | {name:38s} | {'PASS' if ok else 'fail'} | {r['s']:6.1f}s | {r['tool']} {json.dumps(r['args'])[:90]} | {why}", flush=True)
        return row

    local = [j for j in jobs if MODELS[j[0]][0] == OLLAMA]
    remote = [j for j in jobs if MODELS[j[0]][0] == GATEWAY]
    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(run, j) for j in remote]
        for j in local:  # one local model instance: sequential
            run(j)
        for f in futures:
            f.result()


if __name__ == "__main__":
    main()
