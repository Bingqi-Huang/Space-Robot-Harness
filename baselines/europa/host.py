"""EUROPA->PLEXIL baseline: the online host (execution_plan §11.2 "Online host and replanning loop").

  1 load the frozen NDDL domain and the mission instance (site map from the common boundary's query service)
  2 write the current state as facts and the open mission goals as goal tokens
  3 solve in a fresh EUROPA Plan Database (planner/europa_plan)
  4 read the plan's activity tokens off the database, in order of earliest start
  5 dispatch the next activity through PLEXIL (plexil/plans/ActivityDispatch.plx over the HostLink adapter)
  6 turn the raw capability result into plan-database facts (facts_from_result: this baseline's artifact)
  7 an activity that ended as planned advances the plan; one that did not makes the host replan from the updated facts
The domain (domain/lunar-base-model.nddl, one for both missions) stays frozen: a situation it cannot plan for needs an
operator. It asks through the same console channel `space_runtime`/the PLEXIL adapter use
(`/space/operator/{request,reply}`, matched by request_id) and waits; the answer is logged, and only an explicit
"continue" resumes the loop (anything else stops the run, the rover holding where it is) -- what a "no plan" means and
whether the operator can actually fix it is baseline logic, not this mechanism's.

  python host.py --run-dir <dir> --goal restored --goal stowed --final dock                                # Mission A
  MISSION_GOAL='{"item": "orbital replacement unit (ORU)", "source": "depot_stand/slot_0", "destination": "pdu_1_shelf/shelf"}' \\
  python host.py --run-dir <dir> --goal delivered --goal stowed --final dock                              # Mission B

The mission instance is the site as the boundary reports it: every surveyed feature (site_map), every item of the
inventory record on its recorded support (manifest), every serviced unit with its breaker as its own telemetry reads
(power_status). The goals are only the mission's own outcomes (docs/baselines/authoring_spec.md, "Mission goals"):
Mission A every unit restored, Mission B the launcher's item X from source S on destination D (MISSION_GOAL, the same
variable the PLEXIL baseline's plan reads); then arm stowed and base at the dock. navigate_to_feature/dock_at_feature/
arm_ready and which unit to press are not goals at all -- pick/place/press's own domain preconditions force the solver
to derive them, the same way the point of using EUROPA over a hand-sequenced plan is that a single high-level goal
expands into the steps that satisfy it (nasa/europa's own Rover example: TakeSample(rock4) alone yields
Go->Unstow->Place->TakeSample->PhoneHome).
"""
import argparse
import json
import math
import os
import queue
import re
import socket
import subprocess
import time
import uuid
from pathlib import Path

import rclpy
from openral_msgs.msg import PromptStamped
from space_harness_msgs.srv import QueryCapability

REQUEST_TOPIC = "/space/operator/request"
REPLY_TOPIC = "/space/operator/reply"

HERE = Path(__file__).resolve().parent
PLANNER = HERE / "planner/build/europa_plan"
CONFIG = HERE / "config/PlannerConfig.xml"
HOST_CONFIG = json.loads((HERE / "config/host_config.json").read_text())
HORIZON = 10000
NEAR_M = HOST_CONFIG["near_m"]      # dock_at_feature closes "the last metre" after navigate_to_feature: a base
                                     # this close to the feature can dock
ATTEMPTS = HOST_CONFIG["attempts"]  # the same call failing this often ends the run -- the domain has no other way there
JAW_HOLD = (HOST_CONFIG["jaw_holding_min_rad"], HOST_CONFIG["jaw_holding_max_rad"])  # d0_common.py's own bands

# An item's natural-language description (pick's target/part) and catalogue release constraint (place's) are text
# the solver has no reason to search over -- there is exactly one way to describe an item. The table is shared with the
# PLEXIL baseline (docs/baselines/authoring_spec.md), keyed by the item's equipment-catalogue name, and kept outside the
# NDDL domain on purpose (domain/lunar-base-model.nddl's own comment on pick/place).
ITEM_DESCRIPTIONS = json.loads((HERE.parent / "item_descriptions.json").read_text())
# The serviced units' reset buttons: same status as ITEM_DESCRIPTIONS, text, not domain reasoning; the same table as
# the PLEXIL baseline's MissionA_Covered `Button`. Every PDU's service panel carries the same reset button (site survey).
UNIT_DESCRIPTIONS = {**{u: {"target": "the round red push button set into the yellow sub-panel"} for u in ("pdu_1", "pdu_2", "pdu_3")},
                     "bess": {"target": "the round white push button on the graphite control panel with the teal border"},
                     "isru": {"target": "the round black push button on the white control panel with the orange border"}}


def ident(name):
    return re.sub(r"\W", "_", name)


# ---- mission instance and state as NDDL --------------------------------------------------------------------------
def instance(site, items, units):
    """Site objects of the domain: the dock, `elsewhere`, every surveyed feature with its two stances, every item of
    the inventory record (`items`: serial -> its support; where it stands is a fact, not part of the object) and every
    serviced unit (`units`: name -> its button's feature name, a structural property of the `Unit` constructor itself,
    not a fact)."""
    lines = ['NamedPose dock = new NamedPose("dock");', 'Location elsewhere = new Location("elsewhere");']
    names = {"dock": "dock", "elsewhere": "elsewhere"}
    for f in site["points"]:
        i = ident(f)
        lines += [f'Location {i}_a = new Location("{f}@approach");', f'Location {i}_w = new Location("{f}@work");',
                  f'Feature {i} = new Feature("{f}", {i}_a, {i}_w);']
        names.update({i: f, f"{i}_a": f"{f}@approach", f"{i}_w": f"{f}@work"})
    for item in items:
        i = ident(item)
        lines.append(f'Item {i} = new Item("{item}");')
        names[i] = item
    for unit, button in units.items():
        i = ident(unit)
        lines.append(f'Unit {i} = new Unit("{unit}", {ident(button)});')
        names[i] = unit
    return lines, names


def problem(model, site_lines, state, goals):
    """state: {timeline: [predicate, {param: value}]}; goals: [(timeline, predicate, params, final)] in order."""
    out = [f'#include "{model.name}"', *site_lines, "LunarBot rover = new LunarBot();", "close();"]
    for k, (tl, (pred, params)) in enumerate(state.items()):
        out += [f"fact({tl}.{pred} s{k});", f"eq(s{k}.start, 0);", *(f"eq(s{k}.{p}, {v});" for p, v in params.items())]
    for k, (tl, pred, params, final) in enumerate(goals):
        out += [f"goal({tl}.{pred} g{k});", f"leq(1, g{k}.start);", *(f"eq(g{k}.{p}, {v});" for p, v in params.items())]
        out += [f"eq(g{k}.end, {HORIZON});" if final else f"leq(g{k}.end, {HORIZON});"]
        if k:
            out.append(f"precedes(g{k - 1}.end, g{k}.start);")
    return "\n".join(out) + "\n"


def solve(model, text, run_dir, n):
    path = run_dir / f"problem_{n}.nddl"
    path.write_text(text)
    out = subprocess.run([str(PLANNER), str(path), str(CONFIG), str(HORIZON), "5000", "LunarBot."], cwd=model.parent,
                         capture_output=True, text=True)
    return json.loads(out.stdout)


# ---- activity -> capability call ---------------------------------------------------------------------------------
def capability_call(act, names, site, kinds):
    """An activity's parameters are the capability's arguments: a feature goes by its site name, an item by its
    serial (the dispatch sends its catalogue name), a named pose as its coordinates; an item's fixed description text
    is filled in from ITEM_DESCRIPTIONS by its catalogue name `kinds[serial]` (its own comment says why that is not a
    domain parameter)."""
    cap = act["type"].split(".", 1)[1]
    args = {}
    for p, v in act["params"].items():
        if p == "pose":
            args.update(site["dock"] if v == "dock" else {})
        elif isinstance(v, str):
            args[p] = names[v]
        else:
            args[p] = v
    if cap == "pick":
        item = ITEM_DESCRIPTIONS[kinds[args["item"]]]
        args.update(target=item["target"], part=item["part"])
    elif cap == "place":
        args["release_constraint"] = ITEM_DESCRIPTIONS[kinds[args["item"]]]["release_constraint"]
    elif cap == "press":
        unit = args.pop("unit")  # a domain-only concept (which unit's button); press's own contract has no such arg
        args["target"] = UNIT_DESCRIPTIONS[unit]["target"]
    return cap, args


def post_state(act):
    """The activity's planned post-state on each timeline it touches: its latest-starting slave there. A `met_by`
    condition slave (the state a transition starts FROM) comes back with no owner at all (PSToken::getOwner()
    empty, verified against a raw plan dump) rather than the timeline it is actually a fact of -- skipped, or its
    empty-string key corrupts the next solve's problem text (`fact(.Stowed ...)`, invalid NDDL, confirmed offline)."""
    post = {}
    for s in sorted(act["slaves"], key=lambda s: s["start"][0]):
        if s["timeline"]:
            post[s["timeline"]] = [s["type"].split(".")[1], s["params"]]
    return post


# ---- raw result -> plan-database facts (the baseline's result translation, §11.2 step 6) -------------------------
def facts_from_result(state, cap, args, res, site):
    """The facts the host believes after one capability call, and whether the activity ended as planned.

    success: the plan's own post-state holds (the contract did what it says) -- `post_state`, called by the caller.
    failure of a base move: where the robot's own pose estimate (evidence.base_pose) left it -- near the feature it
    was going to (within NEAR_M: dock_at_feature can close in from there) or `elsewhere` (only Nav2 moves from there).
    failure of an arm/manipulation call: every capability's evidence carries the arm's own state (posture, jaw angle
    -- openral_ext/capability_server/node.py's `_execute` attaches it unconditionally), so no extra query is needed.
    A failed pick with empty jaws leaves the item exactly where the state already has it (nothing moved); a failed
    place with empty jaws (dropped in transit, on no surveyed support) is not a state this domain can represent --
    the same open gap `AGENT/todo.md` already tracks for Ours (gc3), not solved here either. An empty result (the
    boundary never accepted the call) changes nothing.
    """
    evd = res.get("evidence") or {}
    if cap in ("navigate_to_feature", "dock_at_feature", "navigate_to_pose"):
        pose = evd.get("base_pose")
        if pose is None:
            return state, False
        feature = args.get("feature")
        if feature and math.dist((pose["x"], pose["y"]), site["points"][feature]["xyz"][:2]) < NEAR_M:
            return {**state, "rover.base": ["At", {"loc": f"{ident(feature)}_a"}]}, False
        return {**state, "rover.base": ["At", {"loc": "elsewhere"}]}, False
    if cap in ("arm_ready", "stow", "pick", "place", "press"):
        arm = evd.get("arm")
        if arm is None:
            return state, False
        new = {**state, "rover.posture": ["Ready" if arm.get("posture") == "ready" else "Stowed", {}]}
        item = args.get("item")
        if item:
            holding = JAW_HOLD[0] < arm.get("jaw_rad", 1.0) < JAW_HOLD[1]
            new["rover.jaws"] = ["Holding", {"item": ident(item)}] if holding else ["Empty", {}]
            if holding:
                new[f"{ident(item)}.loc"] = ["Held", {}]
        return new, False
    return state, False


def initial_state(pose, arm, site, items_at):
    at_dock = math.dist((pose["x"], pose["y"]), (site["dock"]["x"], site["dock"]["y"])) < 0.6
    state = {"rover.base": ["At", {"loc": "dock" if at_dock else "elsewhere"}],
             "rover.posture": ["Ready" if arm.get("posture") == "ready" else "Stowed", {}],
             "rover.jaws": ["Empty", {}]}  # every covered instance starts with empty jaws; nothing here detects otherwise
    for item, support in items_at.items():
        state[f"{ident(item)}.loc"] = ["On", {"support": ident(support)}]
    return state


def panels_from_telemetry(state, units, telemetry):
    """The serviced units' panel facts as their own telemetry reports them (breaker tripped -> Faulted): the host
    verifies a restore by reading the unit, not by trusting the plan's post-state."""
    return {**state, **{f"{ident(u)}.panel": ["Faulted" if telemetry["units"][u]["breaker"] == "tripped" else "Restored", {}]
                        for u in units}}


def parse_goal(token, loc, units, delivery):
    """A `--goal`/`--final` token: `restored` (Mission A: every serviced unit's panel Restored, held to the horizon --
    a restore that relapses is a failure), `delivered` (Mission B: `delivery` = (item serial, destination), the
    launcher's goal), an arm posture (`stowed`/`ready`) or a base location (a feature stance name, `dock`). Returns
    [(timeline, predicate, params, final)]."""
    if token == "restored":
        return [(f"{ident(u)}.panel", "Restored", {}, True) for u in units]
    if token == "delivered":
        return [(f"{ident(delivery[0])}.loc", "On", {"support": loc[delivery[1]]}, False)]
    if token in ("stowed", "ready"):
        return [("rover.posture", token.capitalize(), {}, False)]
    return [("rover.base", "At", {"loc": loc[token]}, False)]


# ---- the PLEXIL link (HostLink adapter) --------------------------------------------------------------------------
class Link:
    def __init__(self, listener):
        self.sock, _ = listener.accept()
        self.rf = self.sock.makefile("rb")

    def send(self, payload):
        b = payload.encode()
        self.sock.sendall(f"{len(b)}\n".encode() + b)

    def recv(self):
        n = int(self.rf.readline())
        return self.rf.read(n).decode()

    def dispatch(self, cap, args):
        assert self.recv() == "NEXT"
        self.send(cap)
        self.send(json.dumps(args))
        assert self.recv() == "RESULT"
        raw = self.recv()
        self.send("OK")
        if not raw:
            return dict(success=False, failure_kind=None, failure_reason="not dispatched", evidence={})
        return json.loads(raw, strict=False)

    def finish(self):
        assert self.recv() == "NEXT"
        self.send("")
        self.send("{}")


def query(node, client, name):
    req = QueryCapability.Request()
    req.query, req.args_json = name, "{}"
    f = client.call_async(req)
    rclpy.spin_until_future_complete(node, f)
    return json.loads(f.result().value_json)


def ask_operator(node, pub, inbox, question):
    """Publish `question` on REQUEST_TOPIC and block (spinning `node`) for the console's reply on
    REPLY_TOPIC, matched by request_id. Returns (answer_text, {authority_level, interaction_id})."""
    request_id = uuid.uuid4().hex[:12]
    pub.publish(PromptStamped(text=question, metadata_json=json.dumps({"request_id": request_id})))
    while True:
        rclpy.spin_once(node, timeout_sec=0.1)
        while not inbox.empty():
            msg = inbox.get()
            meta = json.loads(msg.metadata_json or "{}")
            if meta.get("request_id") == request_id:
                return msg.text, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--model", default=str(HERE / "domain/lunar-base-model.nddl"))
    ap.add_argument("--goal", action="append", default=[], help="restored/delivered/a posture/a location to reach, in order")
    ap.add_argument("--final", help="the goal (of the same kinds as --goal) the run ends at")
    ap.add_argument("--port", type=int, default=47810)
    a = ap.parse_args()
    # Listen before anything else: the check script starts universalExec shortly after this process, and its HostLink
    # adapter connects once. Listening only after the boundary queries below lost that race with six runs on one host
    # (the exec exited, this process waited in accept() forever; research repo F114). A connect now waits in the backlog.
    listener = socket.create_server(("127.0.0.1", a.port))
    run_dir, model = Path(a.run_dir), Path(a.model)
    run_dir.mkdir(parents=True, exist_ok=True)
    events = (run_dir / "events.jsonl").open("a")

    def log(kind, **kw):
        events.write(json.dumps(dict(kind=kind, wall_t=round(time.time(), 3), **kw)) + "\n")
        events.flush()
        print(kind, json.dumps(kw)[:300], flush=True)

    rclpy.init()
    node = rclpy.create_node("europa_host")
    client = node.create_client(QueryCapability, "/space/capability/query")
    client.wait_for_service()
    request_pub = node.create_publisher(PromptStamped, REQUEST_TOPIC, 10)
    reply_inbox = queue.SimpleQueue()
    node.create_subscription(PromptStamped, REPLY_TOPIC, reply_inbox.put, 10)

    def needs_operator(question):
        """Ask, log the exchange, and say whether the operator's answer was an explicit "continue"."""
        answer, meta = ask_operator(node, request_pub, reply_inbox, question)
        log("operator_answered", question=question, answer=answer, authority_level=meta.get("authority_level"),
            interaction_id=meta.get("interaction_id"))
        return answer.strip().lower() == "continue"

    site = query(node, client, "site_map")
    inventory = query(node, client, "manifest")["inventory"]
    items_at = {r["serial"]: r["recorded_location"] for r in inventory}
    kinds = {r["serial"]: r["item"] for r in inventory}
    # the serviced units are the ones reporting on the base network; each unit's panel reset is its `<unit>_panel/press`
    units = {u: f"{u}_panel/press" for u in query(node, client, "power_status")["units"]}
    site_lines, names = instance(site, items_at, units)
    loc = {v: k for k, v in names.items()}
    delivery = None
    if "MISSION_GOAL" in os.environ:
        g = json.loads(os.environ["MISSION_GOAL"])
        serial = next(r["serial"] for r in inventory if r["item"] == g["item"] and r["recorded_location"] == g["source"])
        delivery = (serial, g["destination"])
    goals = [x for t in a.goal for x in parse_goal(t, loc, units, delivery)]
    if a.final:
        goals += [x[:3] + (True,) for x in parse_goal(a.final, loc, units, delivery)]
    state = initial_state(query(node, client, "base_pose"), query(node, client, "arm_state"), site, items_at)
    state = panels_from_telemetry(state, units, query(node, client, "power_status"))
    log("mission", goals=goals, state=state)
    link = Link(listener)
    failures, n_plan, reached = {}, 0, set()
    while True:
        state = panels_from_telemetry(state, units, query(node, client, "power_status"))
        # a unit restore that was reached and no longer holds (read from the unit's telemetry) is a failure of the
        # activities that reached it; the rover leaving the dock or unfolding the arm on the way is not
        for g in goals:
            if not g[0].endswith(".panel"):
                continue
            key = json.dumps(g[:3])
            if state.get(g[0]) == [g[1], g[2]]:
                reached.add(key)
            elif key in reached:
                reached.discard(key)
                failures[key] = failures.get(key, 0) + 1
        if any(v >= ATTEMPTS for v in failures.values()):
            log("no_plan", reason="attempts exhausted", failures=failures)
            if needs_operator(f"Repeated failures, no plan around them: {failures}. "
                              "Reply 'continue' to retry, anything else to abort."):
                failures = {}
                continue
            break
        if all(state.get(g[0]) == [g[1], g[2]] for g in goals):
            log("done", state=state)
            break
        n_plan += 1
        # one goal per solve, not the whole remaining chain: introduced when nasa/europa's solver segfaulted on
        # `precedes`-chained goals (F105; the TemporalNetwork TEQ defect fixed by patches/teq-leaderless-src.patch,
        # after which chained goals solve too) and kept as the baseline's locked behaviour. The goal *sequence*
        # semantics do not change: each solve still finds its own minimal path to the next unmet goal from
        # wherever the previous one left off, which is what the chain meant in the first place.
        plan = solve(model, problem(model, site_lines, state, [next(g for g in goals if state.get(g[0]) != [g[1], g[2]])]), run_dir, n_plan)
        log("plan", n=n_plan, solved=plan["solved"], steps=plan["steps"],
            activities=[(x["type"], x["params"]) for x in plan["activities"]])
        if not plan["solved"]:
            log("no_plan", state=state, goals=goals)
            if needs_operator(f"EUROPA found no plan from state {state} for goals {goals}. "
                              "Reply 'continue' to retry planning, anything else to abort."):
                continue
            break
        for act in plan["activities"]:
            cap, args = capability_call(act, names, site, kinds)
            # the domain names an item by its serial; the capability contract by its equipment-catalogue name
            sent = {**args, "item": kinds[args["item"]]} if "item" in args else args
            log("dispatch", capability=cap, args=sent)
            res = link.dispatch(cap, sent)
            if res["success"]:
                state, as_planned = {**state, **post_state(act)}, True
            else:
                state, as_planned = facts_from_result(state, cap, args, res, site)
            # every panel fact is re-read from the unit's own telemetry: a press that "succeeded" on a unit still
            # reading tripped did not end as planned
            read = panels_from_telemetry(state, units, query(node, client, "power_status"))
            as_planned = as_planned and read == state
            state = read
            reached |= {json.dumps(g[:3]) for g in goals if state.get(g[0]) == [g[1], g[2]]}
            # an intermediate goal, once reached, leaves the goal set; the final one must hold at the horizon
            while goals and not goals[0][3] and state.get(goals[0][0]) == [goals[0][1], goals[0][2]]:
                goals.pop(0)
            log("result", capability=cap, success=res["success"], failure_kind=res["failure_kind"],
                failure_reason=res["failure_reason"], state=state, as_planned=as_planned)
            if not as_planned:
                key = json.dumps([cap, args], sort_keys=True)
                failures[key] = failures.get(key, 0) + 1
                break
    link.finish()


if __name__ == "__main__":
    main()
