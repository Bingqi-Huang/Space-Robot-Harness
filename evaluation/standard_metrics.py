"""Community-standard metrics, computed post hoc from the recorded runs (user decision 2026-09-30): supplementary to the
preregistered measures, which are unchanged. Every number comes from the raw record (evaluator rows, check.log RESULT,
capability_server.log, ours/model_io.jsonl, bags); no simulation, no model call. Definitions and sources:
docs/report_parts/06_standard_metrics.md.

    python3 evaluation/standard_metrics.py > artifacts/eval/standard_metrics.md

Experiment I = the 51 scored exp1b runs; Experiment II = the hidden-case runs before (pre) and after (post) the extension.
"""
import glob
import json
import math
import sqlite3
import statistics
import sys
from collections import defaultdict
from math import comb
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
sys.path.insert(0, str(R / "experiments/video"))
from evaluation import rows as rowsmod  # noqa: E402
from replay_render import tf_message  # noqa: E402

M = {"ours": "Ours", "plexil": "PLEXIL", "europa_plexil": "EUROPA→PLEXIL"}
ORDER = ["ours", "plexil", "europa_plexil"]
VIOL = ["evaluator_unintended_contact_count", "evaluator_dropped_item_count", "evaluator_collateral_change_count",
        "evaluator_estop_fault_execution_count", "evaluator_unauthorized_removal_count"]
CHAIN = {"a_l2_radiator_cover_pdu1": "l2a_pdu", "a_l2_radiator_cover_bess": "l2a_bess", "b_l2_destination_occupied_habitat": "l2b_habitat",
         "a_l3_module_failure_bess": "l3_bess", "a_l3_module_failure_isru": "l3_isru", "a_l4_cannibalize_pdu1": "l4_far"}


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def calls(run: Path):
    """Every capability call in the boundary's log: (capability, sim start, sim end, success); the effect names."""
    out, effects = [], set()
    for line in (run / "capability_server.log").read_text(errors="replace").splitlines():
        if "capability boundary up: effects" in line:
            effects = set(eval(line.split("effects ", 1)[1].split("], queries")[0] + "]"))
        elif "CAPABILITY {" in line:
            c = json.loads(line.split("CAPABILITY ", 1)[1])
            out.append((c["capability"], c.get("sim_t_start"), c.get("sim_t_end"), c["success"]))
    return out, effects


def result(run: Path):
    return rowsmod._check_log_mission(run / "check.log")[1] or {}


def goal_conditions(res: dict, scenario: str) -> list[bool]:
    """The evaluator's success conjunction, one boolean per condition (part 1b §6.2)."""
    ps = bool(res.get("parked_and_stowed"))
    if "cargo" in res:  # Mission B: the cargo on the destination (+ the occupier cleared off it) + parked and stowed
        conds = [bool(res.get("delivered"))]
        if "destination_occupied" in scenario:
            conds.append(res["objects"].get("return_container") != "habitat_stand/slot_0")
        return conds + [ps]
    u = res["units"][res["faulted_unit"]]
    return [bool(u["healthy"] and not u["tripped"]), ps]


def distance(run: Path, hz: float = 2.0) -> float:
    """Metres the rover's root travelled in the plane, from the bag's full /tf at hz."""
    db = sqlite3.connect(glob.glob(str(run / "bag" / "*.db3"))[0])
    tid = db.execute("select id from topics where name='/tf'").fetchone()[0]
    ids = db.execute("select id, timestamp from messages where topic_id=? and length(data)>2000 order by timestamp", (tid,)).fetchall()
    pick, last = [], -1e18
    for i, t in ids:
        if t - last >= 1e9 / hz:
            pick.append(i); last = t
    d, prev = 0.0, None
    for (buf,) in (db.execute("select data from messages where id=?", (i,)).fetchone() for i in pick):
        p = tf_message(buf)["srb/env0/robot"][0]
        if prev is not None:
            d += math.hypot(p[0] - prev[0], p[1] - prev[1])
        prev = p
    return d


def model_use(run: Path):
    """Ours' mission-level reasoner: calls, prompt / completion tokens, latency per call."""
    f = run / "ours" / "model_io.jsonl"
    if not f.exists():
        return None
    recs = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    return (len(recs), sum(r["usage"]["prompt_tokens"] for r in recs), sum(r["usage"]["completion_tokens"] for r in recs),
            [r["latency_s"] for r in recs])


# ---------------------------------------------------------------- Experiment I
rows = [json.loads(p.read_text()) for p in sorted((R / "artifacts/eval/exp1b/rows").glob("*.json"))]
for r in rows:
    run = R / "artifacts/runs" / r["run_id"]
    r["_run"] = run
    r["_res"] = result(run)
    r["_gc"] = goal_conditions(r["_res"], r["scenario_id"])
    cl, eff = calls(run)
    r["_calls"], r["_effects"] = cl, eff
    r["_actions"] = sum(1 for c in cl if c[0] in eff and c[0] != "arm_ready")
    r["_viol"] = sum(r[k] for k in VIOL)
    print(f"# loaded {r['run_id']}", file=sys.stderr, flush=True)

# reference solution length per instance: held-out = the certificate's chain; covered = PLEXIL's covered procedure
ref = {}
for r in rows:
    inst = r["scenario_id"].split("/")[-1]
    if r["coverage"] == "held_out" and inst in CHAIN:
        ref[r["scenario_id"]] = len(json.loads((R / "experiments/launch/lunar_base_d0/chains" / f"{CHAIN[inst]}.json").read_text()))
    elif r["coverage"] == "covered" and r["method"] == "plexil":
        ref[r["scenario_id"]] = r["_actions"]

groups = defaultdict(list)
for r in rows:
    groups[(r["method"], r["coverage"])].append(r)


def cell(f, cov):
    return " | ".join(f(groups[(m, cov)]) for m in ORDER)


print("# Community-standard metrics, computed post hoc from the recorded runs\n")
print("Generated by `evaluation/standard_metrics.py` (2026-09-30). Supplementary to the preregistered measures; "
      "definitions and sources in docs/report_parts/06_standard_metrics.md.\n")

print("## 1. Experiment I (exp1b, 51 scored runs)\n")
print("### 1.1 Task success, goal-condition success, path-length-weighted success, safe success\n")
print("| coverage | measure | Ours | PLEXIL | EUROPA→PLEXIL |\n|---|---|---|---|---|")
for cov in ("covered", "held_out"):
    n = lambda g: len(g)
    print(f"| {cov} | runs | {cell(lambda g: str(n(g)), cov)} |")
    print(f"| {cov} | task success (SR) | {cell(lambda g: f'{sum(r['autonomous_mission_success'] for r in g)}/{n(g)} = {sum(r['autonomous_mission_success'] for r in g)/n(g):.2f}', cov)} |")
    print(f"| {cov} | goal-condition success (GC, mean) | {cell(lambda g: f'{statistics.mean(sum(r['_gc'])/len(r['_gc']) for r in g):.2f}', cov)} |")
    print(f"| {cov} | goal effect achieved (unit restored / cargo delivered) | {cell(lambda g: f'{sum(r['_gc'][0] for r in g)}/{n(g)}', cov)} |")
    print(f"| {cov} | parked and stowed at the end | {cell(lambda g: f'{sum(r['_gc'][-1] for r in g)}/{n(g)}', cov)} |")
    print(f"| {cov} | path-length-weighted success (PLW, mean) | {cell(lambda g: f'{statistics.mean((r['autonomous_mission_success'] * ref[r['scenario_id']] / max(ref[r['scenario_id']], r['_actions'])) for r in g):.2f}', cov)} |")
    print(f"| {cov} | actions per run, median (reference median) | {cell(lambda g: f'{med([r['_actions'] for r in g]):.0f} ({med([ref[r['scenario_id']] for r in g]):.0f})', cov)} |")
    print(f"| {cov} | safe success (success and no violation of any class) | {cell(lambda g: f'{sum(r['autonomous_mission_success'] and r['_viol'] == 0 for r in g)}/{n(g)}', cov)} |")
print()
print("Held-out goal-condition success per level (mean GC over runs):\n")
print("| level | Ours | PLEXIL | EUROPA→PLEXIL |\n|---|---|---|---|")
for lvl in ("L2-A", "L2-B", "L3", "L4"):
    vals = []
    for m in ORDER:
        g = [r for r in groups[(m, "held_out")] if r["level"] == lvl]
        vals.append(f"{statistics.mean(sum(r['_gc'])/len(r['_gc']) for r in g):.2f} (n={len(g)})")
    print(f"| {lvl} | " + " | ".join(vals) + " |")
print()

print("### 1.2 Reliability over repeated runs: pass^k (Ours, held-out, 3 runs per instance)\n")
by_inst = defaultdict(list)
for r in groups[("ours", "held_out")]:
    by_inst[r["scenario_id"]].append(r["autonomous_mission_success"])
print("| k | pass^k (mean over the 6 instances of C(c,k)/C(n,k)) |\n|---|---|")
for k in (1, 2, 3):
    print(f"| {k} | {statistics.mean(comb(sum(v), k) / comb(len(v), k) for v in by_inst.values()):.2f} |")
print("\nBaselines: one run per instance (deterministic executives): pass^1 = SR above; no k > 1.\n")

print("### 1.3 Fault detection and recovery coverage (FDIR framing)\n")
print("| measure | Ours | PLEXIL | EUROPA→PLEXIL |\n|---|---|---|---|")
ho = {m: groups[(m, "held_out")] for m in ORDER}
det = {m: [r for r in ho[m] if r["autonomous_mission_success"] or any(r[f"requests_{k}"] for k in ("authorization", "authority_check", "new_procedure", "information"))] for m in ORDER}
print("| held-out anomaly detected (run succeeded, or escalated / asked mission control) | " + " | ".join(f"{len(det[m])}/{len(ho[m])}" for m in ORDER) + " |")
print("| held-out anomaly missed (false completion) | " + " | ".join(f"{sum(r['false_completion_declaration_count'] > 0 for r in ho[m])}/{len(ho[m])}" for m in ORDER) + " |")
print("| held-out mission recovered autonomously (success, no ground re-authoring) | " + " | ".join(f"{sum(r['autonomous_mission_success'] and not r['ground_reauthoring_required'] for r in ho[m])}/{len(ho[m])}" for m in ORDER) + " |")
print("| ended in a safe hold awaiting the ground (escalated, not recovered) | " + " | ".join(f"{sum((not r['autonomous_mission_success']) and r['requests_new_procedure'] > 0 for r in ho[m])}/{len(ho[m])}" for m in ORDER) + " |")
for cov in ("covered", "held_out"):
    fails = {m: [(r, c) for r in groups[(m, cov)] for c in r["_calls"] if not c[3]] for m in ORDER}
    rec = {m: sum(1 for r, c in fails[m] if any(d[0] == c[0] and d[3] and (d[1] or 0) >= (c[1] or 0) for d in r["_calls"])) for m in ORDER}
    print(f"| {cov}: failed capability calls later recovered (a later call of the same capability succeeded) | " + " | ".join(f"{rec[m]}/{len(fails[m])}" for m in ORDER) + " |")
print()

print("### 1.4 Efficiency and model use\n")
dist = {}
for r in rows:
    dist[r["run_id"]] = distance(r["_run"])
    print(f"# distance {r['run_id']} {dist[r['run_id']]:.1f}", file=sys.stderr, flush=True)
print("| coverage | measure | Ours | PLEXIL | EUROPA→PLEXIL |\n|---|---|---|---|---|")
for cov in ("covered", "held_out"):
    print(f"| {cov} | mission time, median (s) | {cell(lambda g: f'{med([r['mission_elapsed_s'] for r in g]):.0f}', cov)} |")
    print(f"| {cov} | distance driven, median (m) | {cell(lambda g: f'{med([dist[r['run_id']] for r in g]):.0f}', cov)} |")
    print(f"| {cov} | capability calls on the robot (incl. arm_ready), median | {cell(lambda g: f'{med([len(r['_calls']) for r in g]):.0f}', cov)} |")
    mu = [(r, model_use(r["_run"])) for r in groups[("ours", cov)]]
    print(f"| {cov} | Ours reasoner calls per run, median | {med([u[0] for _, u in mu]):.0f} | -- | -- |")
    print(f"| {cov} | Ours prompt / completion tokens per run, median (k) | {med([u[1] for _, u in mu])/1e3:.0f} / {med([u[2] for _, u in mu])/1e3:.1f} | -- | -- |")
    print(f"| {cov} | Ours tokens per run, total over the {len(mu)} runs (M) | {sum(u[1] + u[2] for _, u in mu)/1e6:.2f} | -- | -- |")
    lat = [x for _, u in mu for x in u[3]]
    print(f"| {cov} | Ours latency per reasoning call, median [IQR] (s wall) | {med(lat):.1f} [{statistics.quantiles(lat, n=4)[0]:.1f}, {statistics.quantiles(lat, n=4)[2]:.1f}] | -- | -- |")
print("\nThe baselines use no mission-level model; every method calls the same VLM inside the shared press/pick skills.\n")

print("### 1.5 Human-autonomy interaction (standard names)\n")
print("| coverage | measure | Ours | PLEXIL | EUROPA→PLEXIL |\n|---|---|---|---|---|")
for cov in ("covered", "held_out"):
    def mtbi(g):
        k = sum(len(r["request_segments"]) for r in g)
        return f"{sum(r['mission_elapsed_s'] for r in g) / k:.0f} ({k} intervention{'s' if k > 1 else ''})" if k else "no intervention"
    print(f"| {cov} | mean time between interventions, pooled (s of mission time) | {cell(mtbi, cov)} |")
    print(f"| {cov} | runs without any intervention | {cell(lambda g: f'{sum(not r['request_segments'] for r in g)}/{len(g)}', cov)} |")
print()
print("Intervention response time, decomposed (Steinfeld et al. 2006 segments; mission time, medians over requests):\n")
print("| method | request kind | n | delivery (uplink) | ground decision | answer delivery (downlink) | robot resumes an action after the answer |")
print("|---|---|---|---|---|---|---|")
seg = defaultdict(list)
for r in rows:
    for s in r["request_segments"]:
        parts = (s["uplink_s"], s["decision_s"], s["downlink_s"])
        back = s["sent"] + sum(parts) if None not in parts else None  # None: no answer arrived (loss of signal)
        nxt = [c[1] for c in r["_calls"] if back is not None and c[0] in r["_effects"] and c[1] is not None and c[1] >= back]
        seg[(r["method"], s["kind"])].append(parts + ((min(nxt) - back) if nxt else None, back is None))
for (m, k), v in sorted(seg.items(), key=lambda x: (ORDER.index(x[0][0]), x[0][1])):
    col = lambda j: [x[j] for x in v if x[j] is not None]
    res_ = col(3)
    print(f"| {M[m]} | {k} | {len(v)}{f' ({sum(x[4] for x in v)} unanswered)' if any(x[4] for x in v) else ''} | {med(col(0)):.2f} s | "
          f"{med(col(1)):.0f} s | {med(col(2)):.2f} s | {(f'{med(res_):.1f} s ({len(res_)} of {len(v)})') if res_ else 'never (held)'} |")
print()

print("### 1.6 Runtime assurance\n")
print("| measure | Ours | PLEXIL | EUROPA→PLEXIL |\n|---|---|---|---|")
allr = {m: groups[(m, "covered")] + groups[(m, "held_out")] for m in ORDER}
g_den = sum(r["guard_denied_count"] for r in allr["ours"]); g_all = sum(r["guard_allowed_count"] for r in allr["ours"])
print(f"| guard intervention rate (held proposals / proposed actions) | {g_den}/{g_den + g_all} = {g_den/(g_den + g_all):.3f} | no guard | no guard |")
print(f"| actions executed despite a hold | {sum(r['execution_despite_guard_denial_count'] for r in allr['ours'])} | -- | -- |")
act = {m: sum(r["_actions"] for r in allr[m]) for m in ORDER}
ver = {"ours": sum(r["_actions"] for r in allr["ours"] if r["trace_complete"])}
for m in ("plexil", "europa_plexil"):
    ver[m] = sum(1 for r in allr[m] for c in r["_calls"] if c[0] == "press")
print("| independent verification coverage (actions whose effect is checked against an observation other than the skill's own flag / actions) | "
      + " | ".join(f"{ver[m]}/{act[m]} = {ver[m]/act[m]:.2f}" for m in ORDER) + " |")
print()

# ---------------------------------------------------------------- Experiment II
print("## 2. Experiment II hidden cases (before / after the extension)\n")
print("| phase | case | method | runs | SR | GC (mean) | pass^k over the runs |\n|---|---|---|---|---|---|---|")
for phase in ("pre", "post"):
    for case in ("h1", "h2"):
        for m, tag in (("ours", "ours"), ("plexil", "plexil"), ("europa_plexil", "europa")):
            runs = [p for p in sorted((R / "artifacts/runs/exp2" / phase).glob(f"{phase}_{tag}_{case}*")) if p.is_dir()]
            if not runs:
                continue
            ok = [bool(result(p).get("success")) for p in runs]
            gc = [sum(goal_conditions(result(p), "")) / len(goal_conditions(result(p), "")) for p in runs]
            pk = comb(sum(ok), len(ok)) / comb(len(ok), len(ok))
            print(f"| {phase} | {case.upper()} | {M[m]} | {len(runs)} | {sum(ok)}/{len(ok)} | {statistics.mean(gc):.2f} | pass^{len(ok)} = {pk:.2f} |")
print("\nGC here: the named unit on the destination (the evaluator scores the serial) + parked and stowed.\n")
