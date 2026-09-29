"""Recorded Ours runs as the §5.7 ablations read them offline (research repo F148): a run's event log cut before one
step, folded by the harness's own reducer and rendered by its own context builder under a variant -- the same code the
live agent runs (space_runtime, tag exp1b + the variant switches), so a variant's context at a recorded decision point
is exactly what that variant would have shown the model there.

Runs are read from the main checkout's artifacts (the worktree has none). Run inside the runfarm container with the
openral venv's python (ROS + openral install sourced), repo root on sys.path.
"""
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from space_runtime import ablation, context  # noqa: E402
from space_runtime.facts import apply, empty_facts  # noqa: E402
from space_runtime.guard import Guard  # noqa: E402
from space_runtime.tools import tool_schemas  # noqa: E402

RUNS = Path("/mnt/SharedData/Research/Space_Robot_Harness/artifacts/runs")
CFG = yaml.safe_load((REPO / "configs/space_runtime.yaml").read_text())
RULES = Guard(CFG["guard"]).target_authority
MAX_STEPS = CFG["reasoner"]["max_steps"]
STEP_KINDS = ("tool_proposed", "reasoner_step_failed")


def events(run: str) -> list[dict]:
    return [json.loads(line) for line in (RUNS / run / "ours/events.jsonl").read_text().splitlines()]


def model_io(run: str) -> list[dict]:
    return [json.loads(line) for line in (RUNS / run / "ours/model_io.jsonl").read_text().splitlines()]


def fold(evs: list[dict]) -> dict:
    facts = empty_facts()
    for ev in evs:
        apply(facts, ev)
    return facts


def before(evs: list[dict], step: int) -> tuple[list[dict], float]:
    """The events the live agent had when it rendered `step` (up to that step's `reasoner_step_started`), and the mission
    time then."""
    i = next(k for k, e in enumerate(evs) if e["kind"] == "reasoner_step_started" and e["step"] == step)
    return evs[:i + 1], evs[i]["sim_t"]


@contextmanager
def variant(name: str | None):
    was, ablation.VARIANT = ablation.VARIANT, name
    try:
        yield
    finally:
        ablation.VARIANT = was


def tools(name: str | None) -> list[dict]:
    with variant(name):
        return tool_schemas(yaml.safe_load(ablation.prompt("tools.yaml").read_text()))


def render(name: str | None, evs: list[dict], step: int, mission_t: float) -> tuple[str, str]:
    """(standing text, step message) a variant renders from these events (not no_context: see transcript)."""
    facts = fold(evs)
    with variant(name):
        return context.system_text(facts, RULES), context.step_text(facts, step, MAX_STEPS, evs, mission_t)
