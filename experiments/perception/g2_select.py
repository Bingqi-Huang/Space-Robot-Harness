"""G2 (plan v4 §7): VLM set-of-mark selection among the G1 candidates, offline on the G0 views.

For every view with candidates: the shared scene VLM gets the numbered candidate image and "pick up <target>, holding
it by <part>" (`grasp_perception.select_candidate`, the prompt the pick skill uses), `--asks` times concurrently. Scored
against the simulator's handle (evaluator-only): the choice is correct when it is a G1 hit. Wrong-item test: ORU views
asked for the crate and crate views asked for the ORU -- the answer should say the item is not visible (or choose none).

    SPACE_LLM_API_KEY=... openral/.venv/bin/python experiments/perception/g2_select.py artifacts/perception/g0 [--asks 3]
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from openai import OpenAI
from openral_rskill.grasp_perception import Candidate, select_candidate

ITEMS = {"oru": "the spare ORU (orbital replacement unit, a gold MLI-covered box)", "crate": "the cargo crate (a white case)"}
PART = "its carry handle"
ap = argparse.ArgumentParser()
ap.add_argument("data", type=Path)
ap.add_argument("--asks", type=int, default=3)
ap.add_argument("--model", default="GLM-5.3-Flash")
a = ap.parse_args()
client = OpenAI(api_key=os.environ["SPACE_LLM_API_KEY"], base_url="https://llmapi.paratera.com/v1", timeout=120)
g1 = {r["view"]: r for r in json.loads((a.data / "g1/summary.json").read_text())}
jobs = []
for view, r in sorted(g1.items()):
    cands = [Candidate(**c) for c in json.loads((a.data / "g1" / f"{view}.json").read_text())]
    if not cands:
        continue
    item = view.split("_")[0]
    other = "crate" if item == "oru" else "oru"
    img = cv2.imread(str(a.data / "g1" / f"{view}.jpg"))
    jobs += [(view, "same", ITEMS[item], cands, img, r), (view, "wrong", ITEMS[other], cands, img, r)]


def run(job):
    view, kind, target, cands, img, r = job
    answers = [select_candidate(client, a.model, img, target, PART, cands) for _ in range(a.asks)]
    votes = [x["choice"] for x in answers if x["item_visible"] and x["choice"] is not None]
    top = max(set(votes), key=votes.count) if votes else None
    majority = top if top is not None and votes.count(top) * 2 > a.asks else None
    return dict(view=view, kind=kind, handle_visible=r["handle_visible"], g1_hits=r["hits"], choices=[x["choice"] for x in answers],
                visible=[x["item_visible"] for x in answers], majority=majority,
                correct=(majority in r["hits"]) if kind == "same" else majority is None,
                reasons=[x["reason"] for x in answers], saw=[x["what_is_visible"] for x in answers])


with ThreadPoolExecutor(16) as pool:
    rows = list(pool.map(run, jobs))
for row in rows:
    print(json.dumps({k: row[k] for k in ("view", "kind", "handle_visible", "g1_hits", "choices", "visible", "majority", "correct")}))
same = [r for r in rows if r["kind"] == "same" and r["g1_hits"]]
wrong = [r for r in rows if r["kind"] == "wrong"]
single = sum(r["choices"][0] in r["g1_hits"] for r in same)
print(json.dumps(dict(model=a.model, asks=a.asks, views_with_a_hit=len(same), majority_correct=sum(r["correct"] for r in same),
                      first_answer_correct=single, wrong_item_flagged=sum(r["correct"] for r in wrong), wrong_item_views=len(wrong))))
(a.data / f"g2_{a.model}.json").write_text(json.dumps(rows, indent=1))
