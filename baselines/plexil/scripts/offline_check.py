"""Offline check of the PLEXIL baseline (docs/baselines/plexil.md; docs/baselines/authoring_spec.md, locked 2026-09-23).

Writes one plexilscript simulation per case, runs it under plexiltest and checks that the plan issued exactly the
expected commands in order and then stopped: the mission done (`ok: true`), or one RequestOperator and nothing after
it (the hold). A command the plan issues with other arguments than the script answers never completes, so any
difference in arguments shows up as a hung case.

  Mission A covered at every serviced unit (covered_misreport is the same run: the plan never reads the report);
  a reset that does not hold (3 presses, escalate, hold); a re-trip seen at the dock; no tripped unit;
  Mission B covered for every item x destination;
  at every call site of both plans: the call failing twice then succeeding (the 3rd attempt runs, the mission
  completes), and failing three times (escalate, hold);
  Mission B with the destination recorded occupied (docs/reauthoring/cases/l2b.md): the occupier moved to the return
  stand first, then the delivery.

  python3 baselines/plexil/scripts/offline_check.py          (PLEXIL_HOME set, plexilc/plexiltest on PATH)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ITEMS = json.loads((HERE.parent / "item_descriptions.json").read_text())
UNITS = ["pdu_1", "pdu_2", "pdu_3", "bess", "isru"]
# the plan's own Button table (MissionA_Covered.ple)
BUTTON = {**{u: "the round red push button set into the yellow sub-panel" for u in UNITS[:3]},
          "bess": "the round white push button on the graphite control panel with the teal border",
          "isru": "the round black push button on the white control panel with the orange border"}
CARGO = {"spare_oru": ("orbital replacement unit (ORU)", "depot_stand/slot_0"),
         "bat_spare": ("battery module", "depot_spares_stand/slot_0"),
         "consumables_container": ("consumables container", "landing_stand/slot_0")}
DESTINATION = {**{u: f"{u}_shelf/shelf" for u in UNITS[:3]}, "bess": "bess_stand/slot_0", "habitat": "habitat_stand/slot_0"}
HOLD = " No procedure applies; holding, requesting instructions."


def lit(v):
    return f'"{v}":string' if isinstance(v, str) else f"{float(v)}:real"


def call(label, cmd, *args, before=()):
    """One capability call of the plan; `before`: state changes the script makes before the call's success returns."""
    return dict(label=label, cmd=cmd, args=args, before=list(before))


def state(name, args, value):
    return f"  state {name} ({', '.join(map(lit, args))}) = {lit(value)};"


def script(initial, steps):
    """steps: [(call, ok)] or ("operator", question)"""
    out = ["initial-state {", *(state(*s) for s in initial), "}", "", "script {"]
    for step in steps:
        if step[0] == "operator":
            a = lit(step[1])
            out += [f'  command RequestOperator ({a}) = "noted":string;', f"  command-success RequestOperator ({a});"]
            continue
        c, ok = step
        a = ", ".join(map(lit, c["args"]))
        out += [state(*s) for s in c["before"]] if ok else []
        out += [f"  command {c['cmd']} ({a}) = {'true' if ok else 'false'}:bool;",
                f"  command-{'success' if ok else 'failed'} {c['cmd']} ({a});"]
    return "\n".join(out + ["}"]) + "\n"


def mission_a(u):
    f = f"{u}_panel/press"
    initial = [("PowerUnit", (v, "breaker"), "tripped" if v == u else "closed") for v in UNITS]
    initial.append(("PowerUnit", (u, "trip_cause"), "OVERCURRENT"))
    calls = [call("ToUnit.Nav", "navigate_to_feature", f, 1.2), call("ToUnit.Dock", "dock_at_feature", f, 0.0, 1.2),
             call("Reset.Press", "press", BUTTON[u], f, before=[("PowerUnit", (u, "breaker"), "closed")]),
             call("Return.Stow", "stow", 0.08), call("Return.Return", "navigate_to_pose", 0.0, 0.0, 0.0)]
    escalation = {"ToUnit": f"Could not reach the panel of {u}: a call failed 3 times." + HOLD,
                  "Reset": f"The reset of {u} did not restore it after 3 attempts; trip cause: OVERCURRENT." + HOLD,
                  "Return": "Could not return to the dock: a call failed 3 times." + HOLD}
    return "MissionA_Covered", initial, calls, escalation


def mission_b(cargo, dest, occupant=""):
    item, src = CARGO[cargo]
    dst, d = DESTINATION[dest], ITEMS[item]
    initial = [("MissionGoal", ("item",), item), ("MissionGoal", ("source",), src), ("MissionGoal", ("destination",), dst),
               *(("ItemDescription", (item, k), d[k]) for k in ("target", "part", "release_constraint")),
               ("ManifestAt", (dst, "item"), occupant)]
    calls = []
    if occupant:
        o, ret = ITEMS[occupant], "return_stand/slot_0"
        initial += [("ItemDescription", (occupant, k), o[k]) for k in ("target", "part", "release_constraint")]
        calls = [call("ToOccupant.Nav", "navigate_to_feature", dst, 1.2), call("ToOccupant.Dock", "dock_at_feature", dst, 0.0, 1.2),
                 call("PickOccupant.Ready", "arm_ready", 0.08), call("PickOccupant.Pick", "pick", o["target"], o["part"], occupant, dst),
                 call("ToReturnStand.Nav", "navigate_to_feature", ret, 1.2),
                 call("ToReturnStand.Dock", "dock_at_feature", ret, 0.0, 1.2),
                 call("PlaceOccupant.Place", "place", ret, o["release_constraint"], occupant), call("StowOccupant.Stow", "stow", 0.08)]
    calls += [call("ToSource.Nav", "navigate_to_feature", src, 1.2), call("ToSource.Dock", "dock_at_feature", src, 0.0, 1.2),
             call("Pick.Ready", "arm_ready", 0.08), call("Pick.Pick", "pick", d["target"], d["part"], item, src),
             call("ToDestination.Nav", "navigate_to_feature", dst, 1.2),
             call("ToDestination.Dock", "dock_at_feature", dst, 0.0, 1.2),
             call("Place.Place", "place", dst, d["release_constraint"], item),
             call("Return.Stow", "stow", 0.08), call("Return.Return", "navigate_to_pose", 0.0, 0.0, 0.0)]
    message = f"Delivering the {item} from {src} to {dst}: a call failed 3 times." + HOLD
    return "MissionB_Covered", initial, calls, {c["label"].split(".")[0]: message for c in calls}


def failing(calls, escalation, label, n):
    """The call at `label` fails n times: after 2 the 3rd attempt succeeds; after 3 the plan escalates and holds."""
    k = next(i for i, c in enumerate(calls) if c["label"] == label)
    steps = [(c, True) for c in calls[:k]] + [(calls[k], False)] * n
    if n < 3:
        return steps + [(c, True) for c in calls[k:]], True
    return steps + [("operator", escalation[label.split(".")[0]])], False


def cases():
    for u in UNITS:
        plan, initial, calls, esc = mission_a(u)
        yield f"A covered {u}", plan, initial, [(c, True) for c in calls], True
    plan, initial, calls, esc = mission_a("bess")
    press = dict(calls[2], before=[])  # the reset does not hold: the breaker still reads tripped at every check
    yield "A reset does not hold (bess)", plan, initial, [(c, True) for c in calls[:2]] + [(press, True)] * 3 + [
        ("operator", esc["Reset"])], False
    plan, initial, calls, esc = mission_a("pdu_2")
    back = dict(calls[4], before=[("PowerUnit", ("pdu_2", "breaker"), "tripped"), ("PowerUnit", ("pdu_2", "trip_cause"), "OVERTEMP")])
    yield "A re-trip seen at the dock (pdu_2)", plan, initial, [(c, True) for c in calls[:4]] + [(back, True), (
        "operator", "pdu_2 tripped again after the reset; trip cause: OVERTEMP." + HOLD)], False
    yield "A no tripped unit", plan, [("PowerUnit", (v, "breaker"), "closed") for v in UNITS], [(
        "operator", "Power telemetry shows no tripped unit; the reported fault cannot be located. Holding; requesting instructions.")], False
    for c in CARGO:
        for d in DESTINATION:
            plan, initial, calls, esc = mission_b(c, d)
            yield f"B covered {c} -> {d}", plan, initial, [(x, True) for x in calls], True
    plan, initial, calls, esc = mission_b("consumables_container", "habitat", occupant="return container")
    yield "B destination occupied: return container -> return stand, then consumables_container -> habitat", plan, initial, [
        (x, True) for x in calls], True
    for name, (plan, initial, calls, esc) in (("A", mission_a("isru")), ("B", mission_b("consumables_container", "habitat"))):
        for x in calls:
            for n in (2, 3):
                steps, ok = failing(calls, esc, x["label"], n)
                yield f"{name} {x['label']} fails {n}x", plan, initial, steps, ok


def main():
    plans = HERE / "plans"
    for f in [*plans.glob("lib/*.ple"), *plans.glob("*.ple")]:
        subprocess.run(["plexilc", "-q", str(f)], check=True, capture_output=True)
    tmp = Path(tempfile.mkdtemp(prefix="plexil_offline_"))
    (tmp / "Debug.cfg").write_text("Test:testOutput\n")
    failed = 0
    for n, (name, plan, initial, steps, ok) in enumerate(cases()):
        pst = tmp / f"case{n}.pst"
        pst.write_text(script(initial, steps))
        subprocess.run(["plexilc", "-q", str(pst)], check=True, capture_output=True)
        try:
            out = subprocess.run(["plexiltest", "-p", str(plans / f"{plan}.plx"), "-s", str(pst.with_suffix(".psx")),
                                  "-L", str(plans / "lib"), "-d", str(tmp / "Debug.cfg")],
                                 capture_output=True, text=True, timeout=60).stdout
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode() + "\n<hung>"
        issued = [l.split("Executing ", 1)[1].split("(", 1)[0] for l in out.splitlines()
                  if "]Executing " in l and "Executing pprint" not in l]
        expected = ["RequestOperator" if s[0] == "operator" else s[0]["cmd"] for s in steps]
        done = [l for l in out.splitlines() if l.startswith(f"{plan} ")]
        good = issued == expected and len(done) == 1 and f" ok: {'true' if ok else 'false'} " in done[0] + " "
        failed += not good
        print(f"{'PASS' if good else 'FAIL'}  {name}: {' '.join(issued)}")
        if not good:
            print(f"      expected: {' '.join(expected)}\n      final: {done}\n      script: {pst}")
    print(f"{failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
