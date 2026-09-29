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
  held-out case L4 (re-authored, lib/ReplaceFromDonor): PDU-1's reset does not hold, trip cause ORU_SELFTEST_FAIL --
  the authorization request goes out while the failed module is taken out; granted: PDU-3's module is swapped in, the
  reset holds, the mission completes; denied, or the reset still not holding: escalate, hold; the same reset failure
  with another cause escalates as before.

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
    """steps: [(call, ok)], ("operator", question), ("authorize", args, granted) or ("delay",) (one more exec step
    with no event: a Concurrence's second branch issues its first command a step after the first branch's)"""
    out = ["initial-state {", *(state(*s) for s in initial), "}", "", "script {"]
    for step in steps:
        if step[0] == "delay":
            out += ["  delay;"]
            continue
        if step[0] == "operator":
            a = lit(step[1])
            out += [f'  command RequestOperator ({a}) = "noted":string;', f"  command-success RequestOperator ({a});"]
            continue
        if step[0] == "authorize":
            a = ", ".join(map(lit, step[1]))
            out += [f"  command RequestAuthorization ({a}) = {'true' if step[2] else 'false'}:bool;",
                    f"  command-success RequestAuthorization ({a});"]
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


def mission_b(cargo, dest):
    item, src = CARGO[cargo]
    dst, d = DESTINATION[dest], ITEMS[item]
    initial = [("MissionGoal", ("item",), item), ("MissionGoal", ("source",), src), ("MissionGoal", ("destination",), dst),
               *(("ItemDescription", (item, k), d[k]) for k in ("target", "part", "release_constraint"))]
    calls = [call("ToSource.Nav", "navigate_to_feature", src, 1.2), call("ToSource.Dock", "dock_at_feature", src, 0.0, 1.2),
             call("Pick.Ready", "arm_ready", 0.08), call("Pick.Pick", "pick", d["target"], d["part"], item, src),
             call("ToDestination.Nav", "navigate_to_feature", dst, 1.2),
             call("ToDestination.Dock", "dock_at_feature", dst, 0.0, 1.2),
             call("Place.Place", "place", dst, d["release_constraint"], item),
             call("Return.Stow", "stow", 0.08), call("Return.Return", "navigate_to_pose", 0.0, 0.0, 0.0)]
    message = f"Delivering the {item} from {src} to {dst}: a call failed 3 times." + HOLD
    return "MissionB_Covered", initial, calls, {c["label"].split(".")[0]: message for c in calls}


L4_REQUEST = ("Request for authorization: remove ORU-0258 from the bay of PDU-3 (pdu_3_bay/tray) and install it in "
              "PDU-1. PDU-1 (habitat life support, crew-critical) is down: its reset did not restore it after 3 "
              "attempts, trip cause ORU_SELFTEST_FAIL; its ORU-0211 has failed and the only spare, ORU-0417, is "
              "recorded failed. Consequence: PDU-3 is de-energized and the science instruments it feeds "
              "(non-critical) lose power until a serviceable ORU is supplied.")
L4_REASON = ("restores crew-critical PDU-1 (habitat life support), whose ORU-0211 failed its self-test with no "
             "serviceable spare on site; PDU-3 feeds a non-critical load (science instruments)")


def mission_a_l4(granted=True, holds=True):
    """L4 at PDU-1: 3 presses that do not hold, then the removal (answered first) while the authorization is out
    (answered after it); returns (steps, expected issue order, ok)."""
    plan, initial, calls, esc = mission_a("pdu_1")
    initial[-1] = ("PowerUnit", ("pdu_1", "trip_cause"), "ORU_SELFTEST_FAIL")
    ORU = "orbital replacement unit (ORU)"
    d, bay, shelf, donor, panel = ITEMS[ORU], "pdu_1_bay/tray", "pdu_1_shelf/shelf", "pdu_3_bay/tray", "pdu_1_panel/press"
    initial += [("ItemDescription", (ORU, k), d[k]) for k in ("target", "part", "release_constraint")]
    press = dict(calls[2], before=[])
    remove = [call("ToBay.Nav", "navigate_to_feature", bay, 1.2), call("ToBay.Dock", "dock_at_feature", bay, 0.0, 1.2),
              call("PickFailed.Ready", "arm_ready", 0.08), call("PickFailed.Pick", "pick", d["target"], d["part"], ORU, bay),
              call("ToSetDown.Nav", "navigate_to_feature", shelf, 1.2),
              call("ToSetDown.Dock", "dock_at_feature", shelf, 0.0, 1.2),
              call("SetDown.Place", "place", shelf, d["release_constraint"], ORU), call("Fold", "stow", 0.08),
              call("ToDonor.Nav", "navigate_to_feature", donor, 1.2),
              call("ToDonor.Dock", "dock_at_feature", donor, 0.0, 1.2)]
    swap = [call("PickDonor.Ready", "arm_ready", 0.08), call("PickDonor.Pick", "pick", d["target"], d["part"], ORU, donor),
            call("BackToBay.Nav", "navigate_to_feature", bay, 1.2), call("BackToBay.Dock", "dock_at_feature", bay, 0.0, 1.2),
            call("Install.Place", "place", bay, d["release_constraint"], ORU), call("FoldAgain", "stow", 0.08),
            call("ToPanel.Nav", "navigate_to_feature", panel, 1.2), call("ToPanel.Dock", "dock_at_feature", panel, 0.0, 1.2)]
    steps = [(c, True) for c in calls[:2]] + [(press, True)] * 3 + [("delay",)] + [(c, True) for c in remove] + [
        ("authorize", (L4_REQUEST, "pick", donor, L4_REASON), granted)]
    if not granted:
        steps += [("operator", "Mission control did not grant removing the ORU from pdu_3_bay/tray; pdu_1 stays down "
                               "(ORU_SELFTEST_FAIL)." + HOLD)]
    elif not holds:
        steps += [(c, True) for c in swap] + [(press, True)] * 3 + [(
            "operator", "Replacing the failed ORU of pdu_1 with the one from pdu_3_bay/tray did not restore it: a call "
                        "failed 3 times or the reset did not hold." + HOLD)]
    else:
        steps += [(c, True) for c in swap] + [(calls[2], True)] + [(c, True) for c in calls[3:]]
    expected = ["navigate_to_feature", "dock_at_feature"] + ["press"] * 3 + ["RequestAuthorization"] + [
        "RequestOperator" if s[0] == "operator" else s[0]["cmd"] for s in steps[5:] if s[0] not in ("delay", "authorize")]
    return plan, initial, steps, expected, granted and holds


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
    for name, kw in (("granted", {}), ("denied", {"granted": False}), ("granted, reset still not holding", {"holds": False})):
        plan, initial, steps, expected, ok = mission_a_l4(**kw)
        yield f"A L4 pdu_1 ORU_SELFTEST_FAIL, {name}", plan, initial, steps, ok, expected
    plan, initial, calls, esc = mission_a("pdu_1")
    press = dict(calls[2], before=[])
    yield "A reset does not hold (pdu_1, OVERCURRENT)", plan, initial, [(c, True) for c in calls[:2]] + [(press, True)] * 3 + [
        ("operator", esc["Reset"])], False
    for c in CARGO:
        for d in DESTINATION:
            plan, initial, calls, esc = mission_b(c, d)
            yield f"B covered {c} -> {d}", plan, initial, [(x, True) for x in calls], True
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
    for n, (name, plan, initial, steps, ok, *expected) in enumerate(cases()):
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
        expected = expected[0] if expected else ["RequestOperator" if s[0] == "operator" else s[0]["cmd"] for s in steps]
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
