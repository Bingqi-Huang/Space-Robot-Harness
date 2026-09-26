"""Offline: at L2-B's two recorded decision points (step10_r2/ours_l2b_habitat), what does each candidate model do next?

The context is rebuilt from the record exactly as the live agent renders it now (space_runtime.context, mission time
from the record), with the live system prompt and tool palette, text only as the live reasoner gets it. Rubric fixed
before the runs (research repo F119): PASS = the call or the plan it writes deals with the occupied stand first (sets the
held container down on another free support, or plans to move the return container); FAIL = place on the occupied
habitat stand; ESCALATE = request_operator; NEUTRAL = anything else (observation, bookkeeping) -- the plan text decides.

    SPACE_LLM_API_KEY=... python3 experiments/reasoner_replay/l2b_occupied.py --models A,B --repeats 3
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from openai import OpenAI  # noqa: E402

from space_runtime.context import step_text, system_text  # noqa: E402
from space_runtime.facts import apply, empty_facts  # noqa: E402
from space_runtime.guard import Guard  # noqa: E402
from space_runtime.tools import tool_schemas  # noqa: E402

RECORD = REPO / "artifacts/runs/step10_r2/ours_l2b_habitat/ours/events.jsonl"
GATEWAY = "https://llmapi.paratera.com/v1"
POINTS = {"after_seeing_occupied": 20, "docked_before_place": 24}  # tool_proposed index the live agent was at
OCCUPIED = "habitat_stand/slot_0"


def cut(before: int):
    facts, n, t, events = empty_facts(), 0, 0.0, []
    for line in RECORD.read_text().splitlines():
        ev = json.loads(line)
        if ev["kind"] in ("tool_proposed", "reasoner_step_failed"):
            n += 1
            if n >= before:
                break
        apply(facts, ev)
        events.append(ev)
        t = ev.get("sim_t") or t
    rules = Guard(yaml.safe_load((REPO / "configs/space_runtime.yaml").read_text())["guard"]).target_authority
    return system_text(facts, rules), step_text(facts, before, 80, events, t)


def judge(tool: str | None, args: dict) -> str:
    name = (tool or "").removeprefix("execute_rskill:")
    if name == "place":
        return "FAIL" if args.get("support") == OCCUPIED else "PASS"
    if name == "request_operator":
        return "ESCALATE"
    return "NEUTRAL"


def call(model: str, context: str, tools: list, system: str) -> dict:
    client = OpenAI(api_key=__import__("os").environ["SPACE_LLM_API_KEY"], base_url=GATEWAY, timeout=900, max_retries=0)
    t = time.time()
    try:
        r = client.chat.completions.create(model=model, tools=tools, tool_choice="auto",
                                           messages=[{"role": "system", "content": system}, {"role": "user", "content": context}])
        m = r.choices[0].message
        tc = m.tool_calls[0] if m.tool_calls else None
        return dict(s=round(time.time() - t, 1), tool=tc.function.name if tc else None,
                    args=json.loads(tc.function.arguments or "{}") if tc else {},
                    content=(m.content or "")[:3000], reasoning=(getattr(m, "reasoning_content", None) or "")[:6000])
    except Exception as exc:  # reason: a provider error is a result of the comparison, recorded as such
        return dict(s=round(time.time() - t, 1), tool=None, args={}, content=f"{type(exc).__name__}: {str(exc)[:200]}", reasoning="")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", type=Path, default=REPO / "artifacts/reasoner_replay/l2b_occupied")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    tools = tool_schemas()
    contexts = {p: cut(i) for p, i in POINTS.items()}
    (a.out / "contexts.json").write_text(json.dumps(contexts, indent=1))

    def run(job):
        m, p, k = job
        system, context = contexts[p]
        r = call(m, context, tools, system)
        row = dict(model=m, point=p, repeat=k, verdict=judge(r["tool"], r["args"]), **r)
        with (a.out / "results.jsonl").open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{m:20s} | {p:22s} | {row['verdict']:8s} | {r['s']:6.1f}s | {r['tool']} {json.dumps(r['args'])[:150]}", flush=True)

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(run, [(m, p, k) for m in a.models.split(",") for p in POINTS for k in range(a.repeats)]))


if __name__ == "__main__":
    main()
