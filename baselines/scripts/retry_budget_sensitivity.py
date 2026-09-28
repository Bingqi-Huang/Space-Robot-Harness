"""Retry-budget sensitivity of the two locked baselines, offline (docs/baselines/authoring_spec.md "After the freeze";
docs/prefreeze_workorder.md item 5): every held-out instance of docs/heldout_design.md §14, N = 1, 2, 3, 5 attempts per
call, one row per (baseline, instance, N): outcome (solved / detected -> escalated / other), capability calls made,
retries used (calls beyond the first of the same capability with the same arguments).

Where N lives (nothing here edits a plan, the domain or the host):
  EUROPA  `attempts` in baselines/europa/config/host_config.json, read by host.py as ATTEMPTS: the same call failing, or
          a reached restore relapsing, that often ends planning and asks mission control. Set per run in the host
          process (host.ATTEMPTS = N before host.main()); the chain is run_offline_mission_{a,b}.sh's.
  PLEXIL  no parameter: every `Try` in the plans is unrolled into three identical legs (MissionA_Covered Reset1-3;
          lib/DriveAndDock Nav1-3, Dock1-3; lib/PickItem Ready1-3, Pick1-3; lib/PlaceItem Place1-3; lib/StowAndReturn
          Stow1-3, Return1-3) and the escalation texts say "3 times". Any other N is a derived plan (user decision
          2026-09-28, research repo F143): `derived()` keeps the first N legs of every Try, or adds legs 4..N as copies
          of leg 2 (legs 2-3 are the retries, identical up to their labels), and says N in the escalation texts ("failed
          N times", "after N attempts"); written and compiled under runs/plexil/plans_N<n>, the locked files untouched. derived(3) must
          reproduce the locked plans character for character (checked before every run).

Each held-out state as the offline stand-ins show it to a covered baseline (the physics: space_robotics_bench
srb/tasks/mobile_manipulation/lunar_base/site.py; a press returns ~20 s of sim time after its contact, step10_r1):
  L2-A  the reset closes the breaker and still reads closed when press returns (OVERTEMP re-trip after retrip_delay_s
        30 s), tripped at the next read after that (sim_boundary --no-hold)
  L3/L4 the self-test trips it again 3 s after the reset: it reads tripped after every press (sim_boundary --no-close)
  L2-B  every place onto the occupied habitat stand fails (sim_boundary --fail place:K)
PLEXIL runs under plexiltest with a world that answers each command the plan issues (the plexilscript grows one reply
per rerun); EUROPA runs the real host -> HostLink -> universalExec -> adapter chain over sim_boundary.py.

  python3 baselines/scripts/retry_budget_sensitivity.py      (run-farm image: ROS Humble, ros/install, PLEXIL_HOME)
Run the container with `docker run --init`, which reaps the killed processes of the 24 EUROPA chains run one after
another (without it the 14th chain's host hung before its first query once, 2026-09-26; with it 24/24 ran through).
Writes artifacts/eval/retry_budget/{results.md, rows.jsonl, runs/}.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "baselines/plexil/scripts"))
import offline_check as px  # noqa: E402

OUT = REPO / "artifacts/eval/retry_budget"
EUROPA = REPO / "baselines/europa"
BUDGETS = (1, 2, 3, 5)
PLEXIL_N = 3  # the unrolled legs of every Try in the locked plans
# docs/heldout_design.md §14, the held-out rows; `reset`: how the faulted unit answers a press, `cause` its trip cause
INSTANCES = {
    "L2-A pdu_1 radiator shutter": dict(mission="A", unit="pdu_1", reset="later", cause="OVERTEMP"),
    "L2-A bess HVAC shutter": dict(mission="A", unit="bess", reset="later", cause="OVERTEMP"),
    "L2-B habitat stand occupied": dict(mission="B", cargo="consumables_container", destination="habitat"),
    "L3 bess module failure": dict(mission="A", unit="bess", reset="never", cause="BATTERY_MODULE_FAULT"),
    "L3 isru module failure": dict(mission="A", unit="isru", reset="never", cause="FILTER_CLOGGED"),
    "L4 pdu_1 cannibalize": dict(mission="A", unit="pdu_1", reset="never", cause="ORU_SELFTEST_FAIL"),
}


def derived(text, n):
    """The plan text with every Try's three legs made n (see the module docstring)."""
    out, i = [], 0
    for m in re.finditer(r"^( *)\w+: Try\n\1\{\n", text, re.M):
        body_start = m.end()
        depth, j = 1, body_start
        while depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        body = text[body_start:j - 1]
        legs = list(re.finditer(rf"^{m.group(1)}  ([A-Za-z]+)([123]): ", body, re.M))
        assert [int(l.group(2)) for l in legs] == [1, 2, 3], body
        head = body[:legs[0].start()]
        chunk = [body[legs[k].start():legs[k + 1].start() if k < 2 else len(body)] for k in range(3)]
        tail_ws = re.search(r"\s*$", chunk[2]).group(0)
        chunk[2] = chunk[2][:len(chunk[2]) - len(tail_ws)] + "\n"
        leg = lambda k: chunk[0] if k == 1 else re.sub(r"\b([A-Z][A-Za-z]*)2:", lambda x: f"{x.group(1)}{k}:", chunk[1])
        new = head + "".join(leg(k) for k in range(1, n + 1))
        new = new[:len(new) - 1] + tail_ws
        out.append(text[i:body_start] + new)
        i = j - 1
    out.append(text[i:])
    plural = "s" if n > 1 else ""
    return "".join(out).replace("failed 3 times", f"failed {n} time{plural}").replace("after 3 attempts", f"after {n} attempt{plural}")


def plexil_plans(runs, n):
    """The PLEXIL plans for budget n, compiled under runs/plexil/plans_N<n> (derived() from the locked .ple)."""
    src, plans = REPO / "baselines/plexil/plans", runs / f"plexil/plans_N{n}"
    (plans / "lib").mkdir(parents=True)
    (plans / "Debug.cfg").write_text("Test:testOutput\n")
    for f in [*src.glob("*.ple"), *src.glob("lib/*.ple")]:
        t = f.read_text()
        assert derived(t, PLEXIL_N) == t, f"derived({PLEXIL_N}) does not reproduce {f}"
        (plans / f.relative_to(src)).write_text(derived(t, n))
    subprocess.run(["plexilc", "-q", "-O", str(plans / "lib"), *map(str, plans.glob("lib/*.ple"))], check=True)
    subprocess.run(["plexilc", "-q", "-O", str(plans), *map(str, plans.glob("*.ple"))], check=True)
    return plans


def printed(c):
    """A call as plexiltest prints it when the plan issues it."""
    return f"{c['cmd']}({', '.join(a if isinstance(a, str) else f'{a:g}' for a in c['args'])})"


def summary(calls, escalated, solved, question):
    outcome = "solved" if solved else "detected -> escalated" if escalated else "other"
    return dict(outcome=outcome, calls=len(calls), retries=len(calls) - len(set(calls)), sequence=calls, escalation=question)


# ---- PLEXIL ------------------------------------------------------------------------------------------------------
def plexil(inst, plans, d):
    if inst["mission"] == "A":
        plan, initial, calls, _ = px.mission_a(inst["unit"])
        initial = [s for s in initial if s[1][1] != "trip_cause"] + [("PowerUnit", (inst["unit"], "trip_cause"), inst["cause"])]
    else:
        plan, initial, calls, _ = px.mission_b(inst["cargo"], inst["destination"])
    known = {printed(c): c for c in calls}
    steps, pending = [], []
    while True:
        pst = d / f"{plan}.pst"
        pst.write_text(px.script(initial, steps))
        subprocess.run(["plexilc", "-q", str(pst)], check=True, capture_output=True)
        out = subprocess.run(["plexiltest", "-p", str(plans / f"{plan}.plx"), "-s", str(pst.with_suffix(".psx")),
                              "-L", str(plans / "lib"), "-d", str(plans / "Debug.cfg")], capture_output=True, text=True).stdout
        issued = [l.split("]Executing ", 1)[1] for l in out.splitlines() if "]Executing " in l and "]Executing pprint" not in l]
        done = [l for l in out.splitlines() if l.startswith(f"{plan} ")]
        if done or len(issued) == len(steps):
            break
        line = issued[len(steps)]
        if line.startswith("RequestOperator("):
            steps.append(("operator", line[len("RequestOperator("):-1]))
            continue
        c = known[line]
        before, pending = pending, []
        if c["cmd"] == "press" and inst["reset"] == "later":
            before = [("PowerUnit", (inst["unit"], "breaker"), "closed")]
            pending = [("PowerUnit", (inst["unit"], "breaker"), "tripped")]
        steps.append((dict(c, before=before), c["cmd"] != "place"))  # L2-B: every place onto the occupied stand fails
    (d / f"{plan}.out").write_text(out)
    ops = [s[1] for s in steps if s[0] == "operator"]
    capability = [x for x in issued if not x.startswith("RequestOperator(")]
    escalated = bool(ops) and issued[-1].startswith("RequestOperator(") and bool(done) and " ok: false " in done[0] + " "
    return summary(capability, escalated, bool(done) and " ok: true " in done[0] + " " and not ops, ops[0] if ops else None)


# ---- EUROPA ------------------------------------------------------------------------------------------------------
CHAIN = """set -eo pipefail
export ROS_DOMAIN_ID=92 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PLEXIL_HOME=$HOME/Programs/plexil
export PATH=$PLEXIL_HOME/scripts:/usr/bin:/bin
source /opt/ros/humble/setup.bash
source {repo}/openral/install/setup.bash
source {repo}/ros/install/local_setup.bash
export LD_LIBRARY_PATH={repo}/ros/install/lib:{eu}/plexil/build:$PLEXIL_HOME/lib:$LD_LIBRARY_PATH
(cd {eu}/plexil/plans && plexilc ActivityDispatch.ple > /dev/null)
python3 {eu}/sim_boundary.py {boundary} > {run}/boundary.log 2>&1 &
BOUNDARY=$!
python3 -c 'import sys; sys.path.insert(0, "{eu}"); sys.argv[0] = "host.py"; import host; host.ATTEMPTS = {n}; host.main()' \\
  --run-dir {run} {goals} > {run}/host.log 2>&1 &
HOST=$!
sleep 2
$PLEXIL_HOME/bin/universalExec -c {eu}/plexil/interface-config.xml -p {eu}/plexil/plans/ActivityDispatch.plx \\
  > {run}/exec.log 2>&1 &
EXEC=$!
trap 'kill $BOUNDARY $HOST $EXEC 2>/dev/null' EXIT
wait $HOST $EXEC
"""


def europa(inst, n, run):
    run.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if inst["mission"] == "A":
        boundary = f"--tripped {inst['unit']} " + ("--no-hold" if inst["reset"] == "later" else "--no-close")
        goals = "--goal restored --goal stowed --final dock"
    else:
        item, source = px.CARGO[inst["cargo"]]
        env["MISSION_GOAL"] = json.dumps(dict(item=item, source=source, destination=px.DESTINATION[inst["destination"]]))
        boundary = " ".join(f"--fail place:{k}" for k in range(1, 2 * max(BUDGETS)))  # every place fails
        goals = "--goal delivered --goal stowed --final dock"
    subprocess.run(["bash", "-c", CHAIN.format(repo=REPO, eu=EUROPA, boundary=boundary, run=run, n=n, goals=goals)], env=env)
    events = [json.loads(l) for l in (run / "events.jsonl").read_text().splitlines()]
    calls = [json.dumps([e["capability"], e["args"]], sort_keys=True) for e in events if e["kind"] == "dispatch"]
    last = events[-1]
    return summary(calls, last["kind"] == "operator_answered", last["kind"] == "done",
                   last.get("question") if last["kind"] == "operator_answered" else None)


# ---- table -------------------------------------------------------------------------------------------------------
def cell(r):
    return f"{r['outcome']}, {r['calls']} calls, {r['retries']} retries"


def table(rows):
    at = {(r["baseline"], r["instance"], r["N"]): r for r in rows}
    out = ["# Retry-budget sensitivity (offline)", "",
           "Generated by `baselines/scripts/retry_budget_sensitivity.py` (docstring: where N lives, how each held-out "
           "state is stood in for). Cell: outcome, capability calls made, retries used (calls beyond the first of the "
           "same capability with the same arguments). Raw rows: `rows.jsonl`; per-run logs: `runs/`.", "",
           "| Baseline | Instance | " + " | ".join(f"N={n}" for n in BUDGETS) + " | outcome unchanged over the N run |",
           "|---|---|" + "---|" * len(BUDGETS) + "---|"]
    for b in ("PLEXIL", "EUROPA"):
        for name in INSTANCES:
            got = [at.get((b, name, n)) for n in BUDGETS]
            ran = {r["outcome"] for r in got if r}
            same = "yes" if len(ran) == 1 else "NO"
            out.append(f"| {b} | {name} | " + " | ".join(map(cell, got)) + f" | {same} |")
    return "\n".join(out) + "\n"


def main():
    runs = OUT / "runs"
    shutil.rmtree(runs, ignore_errors=True)  # the host appends to events.jsonl
    plans = {n: plexil_plans(runs, n) for n in BUDGETS}  # the locked .plx in the tree stay untouched
    rows = []
    for name, inst in INSTANCES.items():
        for n in BUDGETS:
            d = runs / "plexil" / f"{name.replace(' ', '_')}_N{n}"
            d.mkdir()
            rows.append(dict(baseline="PLEXIL", instance=name, N=n, **plexil(inst, plans[n], d)))
            print(json.dumps(rows[-1])[:240], flush=True)
        for n in BUDGETS:
            rows.append(dict(baseline="EUROPA", instance=name, N=n, **europa(inst, n, runs / "europa" / f"{name.replace(' ', '_')}_N{n}")))
            print(json.dumps(rows[-1])[:240], flush=True)
    (OUT / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (OUT / "results.md").write_text(table(rows))
    print(table(rows))


if __name__ == "__main__":
    main()
