"""Offline regression for a reasoner change: at decision points where the live model (DeepSeek-V4.1-Flash) did the right
thing in covered and held-out runs, does a candidate model still do it? Contexts rebuilt from each record as the live
agent renders them now; live system prompt and palette; text only. Rubric per point fixed before the runs (research
repo F121): FAIL = the mission-breaking choice at that point; PASS = the right direction (read from the call's
arguments and rationale, and a written plan); NEUTRAL = neither (e.g. one more observation).

    SPACE_LLM_API_KEY=... python3 experiments/reasoner_replay/model_regression.py --models A,B --repeats 3
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

RUNS = REPO / "artifacts/runs"
GATEWAY = "https://llmapi.paratera.com/v1"
ENDS = {"report_to_operator"}
OTHER_PANELS = ("pdu_1_panel", "pdu_3_panel", "bess_panel", "isru_panel")

# name -> (record, tool_proposed index the live agent was at, PASS words, FAIL test)
POINTS = {
    "A_covered_choose_unit": ("step9/ours_a_pdu2", 3, ("pdu_2", "pdu-2"),
                              lambda tool, text: any(p in text for p in OTHER_PANELS)),
    "A_misreport_choose_unit": ("step9/ours_a_misreport", 4, ("bess",),
                                lambda tool, text: tool in ("press", "dock_at_feature", "navigate_to_feature") and "pdu_2_panel" in text),
    "A_covered_after_restore": ("step9/ours_a_pdu2", 17, ("dock", "stow", "report", "return", "done"),
                                lambda tool, text: tool == "press"),
    "B_covered_after_pick": ("step9/ours_b_bat_bess", 11, ("bess_stand",),
                             lambda tool, text: tool in ("place", "dock_at_feature", "navigate_to_feature") and "bess_stand" not in text),
    "L2A_diagnose_overtemp": ("step10_r1/ours_l2a_pdu1", 7, ("radiator", "cover", "shutter"),
                              lambda tool, text: tool in ENDS),
    "L2A_after_both_presses": ("step10_r1/ours_l2a_pdu1", 20, ("power_status", "verify", "telemetry", "lamp"),
                               lambda tool, text: tool in ENDS),
    "L3BESS_plan_repair": ("step10_r1/ours_l3_bess", 7, ("bat-0102", "depot_spares", "spare", "swap", "replace"),
                           lambda tool, text: tool in ENDS or tool == "request_operator"),
    "L3BESS_after_removal": ("step10_r1/ours_l3_bess", 19, ("depot_spares", "bat-0102", "spare"),
                             lambda tool, text: tool in ENDS or tool == "press"),
    "L3ISRU_plan_repair": ("step10_r1/ours_l3_isru", 9, ("flt-0202", "isru_stand", "spare", "swap", "replace"),
                           lambda tool, text: tool in ENDS or tool == "request_operator"),
    "L3ISRU_after_install": ("step10_r1/ours_l3_isru", 29, ("isru_panel", "reset", "press", "stow"),
                             lambda tool, text: tool in ENDS),
}


def cut(record: str, before: int):
    facts, n, t, events = empty_facts(), 0, 0.0, []
    for line in (RUNS / record / "ours/events.jsonl").read_text().splitlines():
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


def call(model: str, context: str, tools: list, system: str) -> dict:
    client = OpenAI(api_key=__import__("os").environ["SPACE_LLM_API_KEY"], base_url=GATEWAY, timeout=900, max_retries=0)
    t = time.time()
    try:
        r = client.chat.completions.create(model=model, tools=tools, tool_choice="auto",
                                           messages=[{"role": "system", "content": system}, {"role": "user", "content": context}])
        m = r.choices[0].message
        tc = m.tool_calls[0] if m.tool_calls else None
        return dict(s=round(time.time() - t, 1), tool=tc.function.name if tc else None,
                    args=json.loads(tc.function.arguments or "{}") if tc else {}, content=(m.content or "")[:2000])
    except Exception as exc:  # reason: a provider error is a result of the comparison, recorded as such
        return dict(s=round(time.time() - t, 1), tool=None, args={}, content=f"{type(exc).__name__}: {str(exc)[:200]}")


def judge(point: str, tool: str | None, args: dict) -> str:
    if tool is None:
        return "ERROR"
    _, _, words, fail = POINTS[point]
    text = json.dumps(args).lower()
    if fail(tool, text):
        return "FAIL"
    return "PASS" if any(w in text for w in words) else "NEUTRAL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", type=Path, default=REPO / "artifacts/reasoner_replay/model_regression")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    tools, system = capability_tools() + local_tools(), (REPO / "space_runtime/playbook.md").read_text()
    contexts = {p: cut(r, i) for p, (r, i, _, _) in POINTS.items()}

    def run(job):
        m, p, k = job
        r = call(m, contexts[p], tools, system)
        row = dict(model=m, point=p, repeat=k, verdict=judge(p, r["tool"], r["args"]), **r)
        with (a.out / "results.jsonl").open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{m:20s} | {p:24s} | {row['verdict']:7s} | {r['s']:6.1f}s | {r['tool']} {json.dumps(r['args'])[:140]}", flush=True)

    with ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(run, [(m, p, k) for m in a.models.split(",") for p in POINTS for k in range(a.repeats)]))


if __name__ == "__main__":
    main()
