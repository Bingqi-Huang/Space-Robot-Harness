"""Offline: at L4's recorded decision points (step10_r4/ours_l4_pdu1), does each candidate model think of the transfer?

The context is rebuilt from the record exactly as the live agent renders it now (space_runtime.context, mission time
from the record), with the live system prompt and tool palette, text only as the live reasoner gets it. Rubric fixed
before the runs (research repo F120): PASS = pick from an energized donor unit's bay (the guard holds it for approval);
ESCALATE = request_operator (its text read for the transfer); NEUTRAL = anything else; IDEA = the call's arguments or
plan name another unit's module as the replacement (read by hand as well).

    SPACE_LLM_API_KEY=... python3 experiments/reasoner_replay/l4_transfer.py --models A,B --repeats 3
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

from space_runtime.context import render  # noqa: E402
from space_runtime.facts import apply, empty_facts  # noqa: E402
from space_runtime.guard import Guard  # noqa: E402
from space_runtime.tools import capability_tools, local_tools  # noqa: E402

RECORD = REPO / "artifacts/runs/step10_r4/ours_l4_pdu1/ours/events.jsonl"
GATEWAY = "https://llmapi.paratera.com/v1"
POINTS = {"spare_recorded_failed": 9, "no_spare_found": 14, "reset_retripped": 21}  # tool_proposed index the live agent was at
DONOR_BAYS = {"pdu_3_bay/tray", "isru_power/tray", "pdu_2_bay/tray"}


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
    return render(facts, before, 80, events, rules, t)


def judge(tool: str | None, args: dict) -> str:
    name = (tool or "").removeprefix("execute_rskill:")
    if name == "pick" and args.get("support") in DONOR_BAYS:
        return "PASS"
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
    ap.add_argument("--out", type=Path, default=REPO / "artifacts/reasoner_replay/l4_transfer")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    tools, system = capability_tools() + local_tools(), (REPO / "space_runtime/playbook.md").read_text()
    contexts = {p: cut(i) for p, i in POINTS.items()}
    (a.out / "contexts.json").write_text(json.dumps(contexts, indent=1))

    def run(job):
        m, p, k = job
        r = call(m, contexts[p], tools, system)
        text = json.dumps(r["args"]).lower()
        idea = any(w in text for w in ("pdu-3", "pdu_3", "pdu3", "isru", "donor", "cannibal", "borrow", "transfer", "another unit"))
        row = dict(model=m, point=p, repeat=k, verdict=judge(r["tool"], r["args"]), idea=idea, **r)
        with (a.out / "results.jsonl").open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{m:20s} | {p:22s} | {row['verdict']:8s} | idea={idea!s:5s} | {r['s']:6.1f}s | {r['tool']} {json.dumps(r['args'])[:150]}", flush=True)

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(run, [(m, p, k) for m in a.models.split(",") for p in POINTS for k in range(a.repeats)]))


if __name__ == "__main__":
    main()
