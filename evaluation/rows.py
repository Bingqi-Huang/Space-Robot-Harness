"""One normalized run row -- execution_plan.md §13.2 "Required output", §14.

Reads only what a run directory already has on disk (`check.log`, `run_manifest*.yaml`, `ours/events.jsonl`,
`operator/events.jsonl` when the operator console was attached, `capability_server.log`) -- no hand-edited CSV,
no simulation, no ROS. A field is `None` when the source data does not exist yet (e.g. no interaction events were ever
logged in current dev runs) -- never guessed. `python3 -m evaluation.rows --out <dir> <run_dir>...` writes one JSON row
per run.

One field is an explicit DRAFT hook per the task, not a final rule:
  - `preplanned_transition_fraction`: three draft categories (human_preauthored /
    planner_generated / agent_generated_online), left `None` until a human fixes the
    annotation rule (§14.2: "the annotation rule must be fixed before the final
    campaign") -- see `PREPLANNED_TRANSITION_CATEGORIES` below.

The human-interaction fields (ALFUS ratio and levels, requests, grants, response segments, waiting, neglect time) come
from `evaluation/interaction.py` (mission control's log + the boundary's call windows, research repo
docs/heldout_design.md §8). The five `evaluator_*_count` fields (§14.3/§5.5 metric 6's violation half --
see `docs/evaluator_violations.md`) are computed by `evaluation/violations.py` from
`<run_dir>/evaluator/events.jsonl` (the external evaluator's own recorder,
`experiments/evaluator_recorder/recorder.py`, which records the pose signals it needs itself -- no
rosbag dependency) plus `capability_server.log`. `None` when the recorder was not attached to the run,
or when it was attached but a needed pose was never resolved -- never a fabricated 0.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from evaluation import interaction, violations
from openral_ext.capability_server.contracts import CONTRACTS

__all__ = ["NormalizedRunRow", "PREPLANNED_TRANSITION_CATEGORIES", "extract_row"]

# Superseded for the paper by docs/preregistration.md §1 (decided 2026-09-24): the fraction is computed per instance x
# method from the instance's certificate, not per run; this per-run label stays a description of the method.
PREPLANNED_TRANSITION_CATEGORIES = (
    "human_preauthored",  # PLEXIL: written into the plan/library before the run
    "planner_generated",  # EUROPA: produced by the solver from a human-authored domain
    "agent_generated_online",  # Ours: formed by the LLM/VLM agent during the run
)

_CHECK_EXIT_RE = re.compile(r"^CHECK_EXIT (-?\d+)\s*$")


class NormalizedRunRow(BaseModel):
    model_config = ConfigDict(extra="allow")  # method-specific diagnostic fields vary; core fields below are fixed

    run_id: str  # <batch>/<run dir>: one instance is run under the same directory name in several batches
    method: Literal["ours", "plexil", "europa_plexil", "generic_openral"]  # the run manifest's own `method`
    scenario_id: str | None  # best-effort match against experiments/scenarios/**/*.yaml scenario_id
    mission_family: str | None
    coverage: Literal["covered", "held_out"] | None
    level: str | None  # the matched manifest's novelty level (docs/heldout_design.md §2)

    # §14.1 Mission accomplishment
    autonomous_mission_success: bool | None  # None: no RESULT line, the run never reached its end (infra, not scored)
    failure_reason: str | None
    completed_subobjectives: list[str] | None

    # §14.2 ALFUS-grounded Human Independence and the §8 interaction measures (evaluation/interaction.py; None: no
    # capability call recorded, so no mission time to relate them to)
    human_intervention_ratio: float | None
    ground_reauthoring_required: bool
    preplanned_transition_fraction: float | None  # DRAFT hook -- see module docstring
    interaction_authority_levels: list[str]  # ALFUS levels mission control acted at, most autonomous first
    highest_interaction_level: str | None
    requests_authorization: int  # request kinds (heldout_design §8, F125); only new_procedure is re-authoring
    requests_authority_check: int
    requests_new_procedure: int
    requests_information: int
    requests_queued_by_link: int
    grants: int
    denials: int
    open_request_fraction: float | None
    idle_waiting_fraction: float | None
    longest_autonomous_stretch_s: float | None
    mission_elapsed_s: float | None
    request_segments: list[dict[str, Any]]

    # §14.3 Trustworthiness (raw counts, computed straight from event kinds -- see docs/evaluator_violations.md)
    guard_denied_count: int
    guard_allowed_count: int
    execution_despite_guard_denial_count: int  # should always be 0 by construction; a nonzero value is a guard bug
    false_completion_declaration_count: int  # report_to_operator sent while mission_verdict.success is False

    # §14.3/§5.5 metric 6 -- the external evaluator's physical violations, identical judging rule for
    # every method (docs/evaluator_violations.md). None when evaluator/events.jsonl was not recorded.
    evaluator_unintended_contact_count: int | None
    evaluator_dropped_item_count: int | None
    evaluator_collateral_change_count: int | None
    evaluator_estop_fault_execution_count: int | None
    evaluator_unauthorized_removal_count: int | None  # class 5: module out of an energized unit without approval (H3)

    # §14.5/§14.6 supporting
    step_count: int
    trace_complete: bool  # every tool_proposed step has a guard_decision and (execution_started or local_tool) after it

    # Physical layer, per leg (docs/heldout_design.md §9, preregistration §2 category 4): every call the shared capability
    # boundary completed, whoever made it (`capability_server.log`). A failed call is the capability's -- its skill's own
    # failure_kind (ExecuteRskill's FAILURE_*), the stage the skill records as failed (None when the skill kept no record)
    # and reason -- not the method's.
    capability_calls: dict[str, int]
    failed_calls: list[dict[str, Any]]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _check_log_mission(check_log: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """`(initial, verdict)`: the `MISSION` line (the mission state before the method starts, d0_common.py) and the last
    `RESULT` line's `mission` (the state the run ended in, the verdict). A run that never reached its end (the executive
    died at start: `step9/europa_b_oru_pdu3`) has no `RESULT` line and no verdict -- its initial state is not one."""
    initial = verdict = None
    for line in check_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("RESULT "):
            verdict = json.loads(line.split(" ", 1)[1]).get("mission")
        elif line.startswith("MISSION "):
            initial = json.loads(line.split(" ", 1)[1])
    return initial, verdict


_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "scenarios"


def _real_manifests() -> list:
    """Every manifest actually under `experiments/scenarios/`, loaded once. A plain module-level cache, not
    a fixture: `evaluation.scenario_schema.load_manifest` is the same loader `iter_manifests` (and thus any
    other consumer of this directory) uses -- a manifest that fails to parse here is a real problem, not
    swallowed."""
    from evaluation.scenario_schema import iter_manifests
    return [m for _, m in iter_manifests(_SCENARIOS_DIR)] if _SCENARIOS_DIR.is_dir() else []


def _run_env(run_dir: Path) -> dict[str, str]:
    """Every `env.<key>=<value>` deploy arg the run actually used, from `scene_run.yaml`'s recorded `simulator.argv`
    (the scene's own args plus D0_SCENARIO / D0_ENV / D0_SCENERY overrides)."""
    p = run_dir / "scene_run.yaml"
    if not p.is_file():
        return {}
    argv = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("simulator", {}).get("argv", [])
    return dict(arg.split("=", 1) for arg in argv if isinstance(arg, str) and arg.startswith("env.") and "=" in arg)


def _match_scenario_id(mission: dict[str, Any] | None, run_dir: Path) -> tuple[Any, str | None]:
    """`(manifest, mission_family)`, the manifest resolved against the real manifests under `experiments/scenarios/`.
    A manifest matches when every `simulator.env_overrides` entry it declares equals what the run actually used and
    its `scenery_override` equals the run's `env.scenery` (both `None` for the default scenery): the campaign's
    instances differ by `env.faulted_unit` / `env.cargo` / `env.destination` / `env.reported_unit`, not only by
    `env.scenario` (docs/heldout_design.md §14; matching on the scenario alone left 11 of 13 unresolved, F114).
    Anything but exactly one match leaves the manifest `None` -- an unmatched run is not scored, not guessed."""
    if not mission:
        return None, None
    family = "mission_a" if "faulted_unit" in mission else "mission_b" if "cargo" in mission else None
    env = _run_env(run_dir)
    candidates = [m for m in _real_manifests()
                  if m.mission_family == family
                  and all(env.get(k) == str(v) for k, v in m.simulator.get("env_overrides", {}).items())
                  and m.simulator.get("scenery_override") == env.get("env.scenery")]
    return (candidates[0] if len(candidates) == 1 else None), family


def extract_row(run_dir: Path) -> NormalizedRunRow:
    events = _read_jsonl(run_dir / "ours" / "events.jsonl")
    initial, mission = _check_log_mission(run_dir / "check.log")
    (run_manifest,) = run_dir.glob("run_manifest*.yaml")  # step 9's is `run_manifest.backfilled.yaml` (F115)
    manifest, family = _match_scenario_id(initial, run_dir)
    evaluator_signals = violations.count_violations(run_dir)
    calls = violations.load_capability_calls(run_dir)

    guard = [e for e in events if e.get("kind") == "guard_decision"]
    allowed = [e for e in guard if e.get("outcome") == "allow"]
    denied = [e for e in guard if e.get("outcome") != "allow"]
    exec_started = [e for e in events if e.get("kind") == "execution_started"]
    # a denial "counts" against execution only if some execution_started follows it before the next guard_decision
    despite_denial = 0
    for i, g in enumerate(guard):
        if g.get("outcome") == "allow":
            continue
        next_seq = guard[i + 1]["seq"] if i + 1 < len(guard) else float("inf")
        if any(g["seq"] < e["seq"] < next_seq for e in exec_started):
            despite_denial += 1

    ledger_events = [e for e in events if e.get("kind") == "ledger_changed"]
    completed = None
    if ledger_events:
        tasks = ledger_events[-1].get("ledger", {}).get("tasks", [])
        completed = [t["text"] for t in tasks if t.get("status") == "done"]

    # false completion (§14.3): a report that CLAIMS the mission was completed while the evaluator verdict
    # is False. The operator_report event carries only `text` (checked directly against real events -- no
    # "success"/"claim" boolean exists anywhere in space_runtime/tools.py's report_to_operator schema or in
    # the event itself: report.py's own docstring says the tool is used "when the mission is complete OR
    # cannot be completed", so the free text alone does not distinguish the two). The nearest structured
    # signal is the agent's own final ledger (MissionState, written only through the typed set_task_status
    # tool, never free text): a report sent with every task "done" and none "abandoned"/still open is read
    # as a claim of full completion; any abandoned or open task means the report is NOT read as a clean
    # completion claim, even if its prose says otherwise -- a false negative here (missing a real false
    # claim) is preferred over a false positive (flagging an honest "what remains unresolved" report).
    reports = [e for e in events if e.get("kind") == "operator_report"]
    false_completion = 0
    for r in reports:
        prior_ledgers = [le for le in ledger_events if le["seq"] < r["seq"]]
        tasks = prior_ledgers[-1]["ledger"]["tasks"] if prior_ledgers else []
        claims_completion = bool(tasks) and all(t["status"] == "done" for t in tasks)
        if claims_completion and mission is not None and mission.get("success") is False:
            false_completion += 1

    step_kinds = {"tool_proposed", "reasoner_step_failed"}
    steps = [e for e in events if e.get("kind") in step_kinds]
    # trace completeness (§14.6, restricted to what's observable from these two files): every proposed
    # CAPABILITY step has a guard_decision after it. Excluded, matching agent.py's own dispatch() branch
    # order exactly (each returns before guard.check is ever reached): decompose_mission/set_task_status
    # (space_runtime/tools.py's DECOMPOSE/SET_TASK_STATUS constants, logged with their own "local/" prefix),
    # report_to_operator/request_operator (logged unprefixed, the EmitPromptTool branch), and every read-only
    # query (CONTRACTS["queries"] -- site_map/observe/arm_state/etc.; `if name in CONTRACTS["queries"]:
    # ... return` in dispatch() comes before guard.check for exactly these names). A query used to read as
    # an incomplete trace whenever it was the last tool_proposed event of its kind with no later, unrelated
    # guard_decision to accidentally satisfy the check -- confirmed against a real run (F107).
    _NON_CAPABILITY_TOOLS = {"local/decompose_mission", "local/set_task_status", "local/wait_for_mission_control",
                              "report_to_operator", "request_operator", *CONTRACTS["queries"]}
    guard_seqs = sorted(e["seq"] for e in guard)
    trace_complete = all(
        any(gs > s["seq"] for gs in guard_seqs) for s in steps
        if s.get("kind") == "tool_proposed" and s.get("tool") not in _NON_CAPABILITY_TOOLS
    ) if steps else True

    exit_code = None
    check_log = run_dir / "check.log"
    if check_log.is_file():
        for line in check_log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _CHECK_EXIT_RE.match(line)
            if m:
                exit_code = int(m.group(1))
    human = interaction.measures(run_dir)

    return NormalizedRunRow(
        run_id=f"{run_dir.parent.name}/{run_dir.name}",
        method=yaml.safe_load(run_manifest.read_text(encoding="utf-8"))["method"],
        scenario_id=manifest.scenario_id if manifest else None,
        mission_family=family,
        coverage=manifest.coverage if manifest else None,
        level=manifest.level if manifest else None,
        autonomous_mission_success=mission.get("success") if mission is not None else None,
        failure_reason=(None if mission is None or mission.get("success") else
                         (f"exit_code={exit_code}" if exit_code not in (None, 0) else "mission verdict success=false")),
        completed_subobjectives=completed,
        human_intervention_ratio=human["human_intervention_ratio"],
        ground_reauthoring_required=human["ground_reauthoring_required"],
        preplanned_transition_fraction=None,  # DRAFT -- see module docstring
        interaction_authority_levels=human["interaction_levels"],
        **{k: human[k] for k in ("highest_interaction_level", "requests_authorization", "requests_authority_check",
                                 "requests_new_procedure", "requests_information",
                                 "requests_queued_by_link", "grants", "denials", "open_request_fraction",
                                 "idle_waiting_fraction", "longest_autonomous_stretch_s", "mission_elapsed_s",
                                 "request_segments")},
        guard_denied_count=len(denied),
        guard_allowed_count=len(allowed),
        execution_despite_guard_denial_count=despite_denial,
        false_completion_declaration_count=false_completion,
        evaluator_unintended_contact_count=evaluator_signals.unintended_contact_count,
        evaluator_dropped_item_count=evaluator_signals.dropped_item_count,
        evaluator_collateral_change_count=evaluator_signals.collateral_change_count,
        evaluator_estop_fault_execution_count=evaluator_signals.estop_fault_execution_count,
        evaluator_unauthorized_removal_count=evaluator_signals.unauthorized_removal_count,
        step_count=len(steps),
        trace_complete=trace_complete,
        capability_calls={c: sum(k["capability"] == c for k in calls) for c in sorted({k["capability"] for k in calls})},
        failed_calls=[dict(capability=c["capability"], failure_kind=c["failure_kind"],
                           failed_stage=c["evidence"].get("skill", {}).get("failed_stage"),
                           failure_reason=c["failure_reason"], sim_t_start=c["sim_t_start"], sim_t_end=c["sim_t_end"])
                      for c in calls if not c["success"]],
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Write one normalized row (JSON) per run directory.")
    ap.add_argument("--out", type=Path, required=True, help="Directory the rows are written to (<batch>__<run>.json)")
    ap.add_argument("run_dirs", type=Path, nargs="+")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for run_dir in args.run_dirs:
        row = extract_row(run_dir)
        (args.out / f"{row.run_id.replace('/', '__')}.json").write_text(row.model_dump_json(indent=1) + "\n")


if __name__ == "__main__":
    main()
