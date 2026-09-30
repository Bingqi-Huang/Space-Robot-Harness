"""Stage 2 of the §5.7 ablations (research repo F148): at every decision point, each arm's exact context is sent to the
exp1b reasoner three times and the call it chooses is recorded.

The decision is the first effect call, call to mission control, or query of the robot's current state. Calls before
it that change nothing outside the agent are carried forward offline and the model asked again on the context that
follows, as the live agent would ask it -- at most CARRY times: a call to its own plan (decompose_mission,
set_task_status) applied exactly as the agent applies it (the same events, the same ledger); a query of a static record
(STATIC: the site survey, the manifest, a feature's work stands) answered with the run's own earlier answer to the same
query and arguments (none on record: that query is the decision). A reply without a call gets the live harness's one reminder. The contexts are built in
memory by accidents.py and checked against the ones written to <points> (the audited inputs). Resumable: a finished
chain is not asked again.

    SPACE_LLM_API_KEY=... python3 stage2.py <points dir> <results dir> [--repeats 3] [--workers 12]
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI
from openral_reasoner.mission import MissionState

from accidents import all_points, link_los
from record import CFG, MAX_STEPS, fold, variant
from space_runtime import context
from space_runtime.tools import TEXTS

PLAN = ("decompose_mission", "set_task_status")
STATIC = ("site_map", "manifest", "work_stands")
CARRY = 6


def plan_events(evs: list[dict], name: str, args: dict, t: float, step: int) -> list[dict]:
    """The events the agent writes for a plan call (space_runtime/agent.py `dispatch`), then the next step's start."""
    rationale = args.pop("rationale", "")
    state = fold(evs)["ledger"]
    ledger = MissionState.from_state_dict(state) if state else None
    if name == "decompose_mission":
        subtasks, target = [s for s in args.get("subtasks", []) if s.strip()], args.get("target_task_id", "")
        args = {"target_task_id": target, "subtasks": subtasks}
        if not target:
            closed = [x for x in (ledger.to_state_dict()["tasks"] if ledger else []) if x["status"] in ("done", "abandoned")]
            fresh = MissionState(subtasks).to_state_dict()["tasks"]
            for i, x in enumerate(fresh):
                x["task_id"] = f"t{len(closed) + i + 1}"
            ok, detail, ledger = True, TEXTS["results"]["plan_written"], MissionState.from_state_dict({"tasks": closed + fresh})
        else:
            active = ledger.active() if ledger else None
            ok = active is not None and active.task_id == target and ledger.subdivide_active(subtasks) is not None
            detail = TEXTS["results"]["task_split"] if ok else TEXTS["results"]["task_split_refused"].format(target=target)
    else:
        ok = ledger is not None and ledger.active() is not None
        if ok:
            (ledger.complete_active if args["status"] == "done" else ledger.abandon_active)(args["note"])
        detail = TEXTS["results"]["task_marked"].format(status=args["status"]) if ok else TEXTS["results"]["no_active_task"]
    n, w = len(evs), evs[-1]["wall_t"]
    new = [{"seq": n, "kind": "tool_proposed", "wall_t": w, "sim_t": t, "tool": name, "args": args, "rationale": rationale},
           {"seq": n + 1, "kind": "local_tool", "wall_t": w, "success": ok, "detail": detail}]
    if ok:
        new.append({"seq": n + 2, "kind": "ledger_changed", "wall_t": w, "ledger": ledger.to_state_dict()})
    new.append({"seq": n + len(new), "kind": "reasoner_step_started", "wall_t": w, "sim_t": t, "step": step + 1})
    return new


def static_answer(evs: list[dict], name: str, args: dict, t: float, step: int) -> list[dict] | None:
    """The run's own latest answer to this static query, as the events a fresh ask would write; None if never asked."""
    args = {k: v for k, v in args.items() if k != "rationale"}
    old = next((e for e in reversed(evs) if e["kind"] == "query_answered" and e["query"] == name and e["args"] == args), None)
    if old is None:
        return None
    n, w = len(evs), evs[-1]["wall_t"]
    return [{"seq": n, "kind": "tool_proposed", "wall_t": w, "sim_t": t, "tool": name, "args": args, "rationale": ""},
            {**old, "seq": n + 1, "sim_t": t},
            {"seq": n + 2, "kind": "reasoner_step_started", "wall_t": w, "sim_t": t, "step": step + 1}]


def ask(point: dict, arm: str, out: Path) -> None:
    if out.exists():
        return
    rc, a = CFG["reasoner"], point["arms"][arm]
    st = a["_state"]
    evs, t, step, messages = list(st["events"]), st["mission_t"], point["step"], list(a["messages"])
    client = OpenAI(api_key=os.environ["SPACE_LLM_API_KEY"], base_url=rc["endpoint"], timeout=900, max_retries=0)
    chain, t0 = [], time.time()
    for k in range(CARRY + 1):
        sent = [{"role": "system", "content": a["system"]}, *messages]
        try:
            resp = client.chat.completions.create(model=rc["model"], messages=sent, tools=a["tools"], tool_choice="auto")
            if not resp.choices[0].message.tool_calls:
                sent += [{"role": "assistant", "content": resp.choices[0].message.content or ""},
                         {"role": "user", "content": TEXTS["reply_without_call"]}]
                resp = client.chat.completions.create(model=rc["model"], messages=sent, tools=a["tools"], tool_choice="auto")
        except Exception as exc:  # an outage is not a result: nothing written, the chain is asked again on the next pass
            print(f"{out.name}: {exc}", flush=True)
            return
        msg = resp.choices[0].message
        tc = (msg.tool_calls or [None])[0]
        call = {"name": tc.function.name, "arguments": tc.function.arguments} if tc else None
        chain.append({"call": call, "content": msg.content or "", "reasoning": getattr(msg, "reasoning_content", None) or "",
                      "prompt_tokens": resp.usage.prompt_tokens if resp.usage else None})
        if call is None or call["name"] not in (*PLAN, *STATIC) or k == CARRY:
            break
        try:
            args = json.loads(call["arguments"])
            new = (plan_events(evs, call["name"], args, t, step) if call["name"] in PLAN
                   else static_answer(evs, call["name"], args, t, step))
        except (ValueError, KeyError, TypeError):  # an invalid plan call: the decision is that call
            break
        if new is None:
            break
        with variant(st["variant"]), link_los(st["los"]):
            if st["variant"] == "no_context":
                messages = [*sent[1:], {"role": "assistant", "content": msg.content or "", "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}]},
                    {"role": "tool", "tool_call_id": tc.id,
                     "content": context.result_text(fold(evs + new), step + 1, MAX_STEPS, new, t)}]
            else:
                messages = [{"role": "user", "content": context.step_text(fold(evs + new), step + 1, MAX_STEPS, evs + new, t)}]
        evs, step = evs + new, step + 1
    out.write_text(json.dumps({"id": point["id"], "accident": point["accident"], "arm": arm, "model": rc["model"],
                               "latency_s": round(time.time() - t0, 1), "decision": chain[-1]["call"], "carried": len(chain) - 1,
                               "chain": chain}))
    print(f"{out.name}: {chain[-1]['call']['name'] if chain[-1]['call'] else 'no call'} after {len(chain) - 1} carried "
          f"({time.time() - t0:.0f} s)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("points", type=Path)
    ap.add_argument("results", type=Path)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--only", default="", help="comma-separated point ids (smoke test)")
    a = ap.parse_args()
    a.results.mkdir(parents=True, exist_ok=True)
    pts = [p for p in all_points() if not a.only or p["id"] in a.only.split(",")]
    for p in pts:  # the in-memory contexts are the audited ones
        disk = json.loads((a.points / (p["id"].replace("/", "__") + ".json")).read_text())
        assert all(disk["arms"][arm][k] == c[k] for arm, c in p["arms"].items() for k in ("system", "messages", "tools")), p["id"]
    jobs = [(p, arm, a.results / f"{p['id'].replace('/', '__')}__{arm}__r{k}.json")
            for p in pts for arm in p["arms"] for k in range(1, a.repeats + 1)]
    print(len(jobs), "chains,", sum(not o.exists() for _, _, o in jobs), "to do", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(lambda j: ask(*j), jobs))
    print("done:", sum(o.exists() for _, _, o in jobs), "of", len(jobs), flush=True)


if __name__ == "__main__":
    main()
