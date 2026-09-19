"""EUROPA->PLEXIL baseline: the online host (execution_plan §11.2 "Online host and replanning loop").

  1 load the frozen NDDL domain and the mission instance (site map from the common boundary's query service)
  2 write the current state as facts and the open mission goals as goal tokens
  3 solve in a fresh EUROPA Plan Database (planner/europa_plan)
  4 read the plan's activity tokens off the database, in order of earliest start
  5 dispatch the next activity through PLEXIL (plexil/plans/ActivityDispatch.plx over the HostLink adapter)
  6 turn the raw capability result into plan-database facts (facts_from_result: this baseline's artifact)
  7 an activity that ended as planned advances the plan; one that did not makes the host replan from the updated facts
The domain stays frozen: a situation it cannot plan for needs an operator. It asks through the same console channel
`space_runtime`/the PLEXIL adapter use (`/space/operator/{request,reply}`, matched by request_id) and waits; the
answer is logged, and only an explicit "continue" resumes the loop (anything else stops the run) -- what a "no plan"
means and whether the operator can actually fix it is baseline logic, not this mechanism's.

  python host.py --run-dir <dir> --goal depot_stand/slot_0@work --goal dock --final dock
"""
import argparse
import json
import math
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
HORIZON = 10000
NEAR_M = 3.0  # dock_at_feature closes "the last metre" after navigate_to_feature: a base this close to the feature can dock
ATTEMPTS = 3  # the same call failing this often ends the run -- the domain has no other way to that state


def ident(name):
    return re.sub(r"\W", "_", name)


# ---- mission instance and state as NDDL --------------------------------------------------------------------------
def instance(site):
    """Site objects of the skeleton domain: the dock, `elsewhere`, and every surveyed feature with its two stances."""
    lines = ['NamedPose dock = new NamedPose("dock");', 'Location elsewhere = new Location("elsewhere");']
    names = {"dock": "dock", "elsewhere": "elsewhere"}
    for f in site["points"]:
        i = ident(f)
        lines += [f'Location {i}_a = new Location("{f}@approach");', f'Location {i}_w = new Location("{f}@work");',
                  f'Feature {i} = new Feature("{f}", {i}_a, {i}_w);']
        names.update({i: f, f"{i}_a": f"{f}@approach", f"{i}_w": f"{f}@work"})
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
def capability_call(act, names, site):
    """An activity's parameters are the capability's arguments: a feature goes by its site name, a named pose as its
    coordinates."""
    args = {}
    for p, v in act["params"].items():
        if p == "pose":
            args.update(site["dock"] if v == "dock" else {})
        elif isinstance(v, str):
            args[p] = names[v]
        else:
            args[p] = v
    return act["type"].split(".", 1)[1], args


def post_state(act):
    """The activity's planned post-state on each timeline it touches: its latest-starting slave there."""
    post = {}
    for s in sorted(act["slaves"], key=lambda s: s["start"][0]):
        post[s["timeline"]] = [s["type"].split(".")[1], s["params"]]
    return post


# ---- raw result -> plan-database facts (the baseline's result translation, §11.2 step 6) -------------------------
def facts_from_result(state, act, cap, args, res, site):
    """The facts the host believes after one capability call, and whether the activity ended as planned.

    success: the plan's own post-state holds (the contract did what it says).
    failure of a base move: where the robot's own pose estimate (evidence.base_pose) left it -- near the feature it
    was going to (within NEAR_M: dock_at_feature can close in from there) or `elsewhere` (only Nav2 moves from there).
    An empty result (the boundary never accepted the call) changes nothing.
    """
    if res["success"]:
        return {**state, **post_state(act)}, True
    pose = res["evidence"].get("base_pose")
    if pose is None:
        return state, False
    feature = args.get("feature")
    if feature and math.dist((pose["x"], pose["y"]), site["points"][feature]["xyz"][:2]) < NEAR_M:
        return {**state, "rover.base": ["At", {"loc": f"{ident(feature)}_a"}]}, False
    return {**state, "rover.base": ["At", {"loc": "elsewhere"}]}, False


def initial_state(pose, site):
    at_dock = math.dist((pose["x"], pose["y"]), (site["dock"]["x"], site["dock"]["y"])) < 0.6
    return {"rover.base": ["At", {"loc": "dock" if at_dock else "elsewhere"}]}


# ---- the PLEXIL link (HostLink adapter) --------------------------------------------------------------------------
class Link:
    def __init__(self, port):
        srv = socket.create_server(("127.0.0.1", port))
        self.sock, _ = srv.accept()
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
    ap.add_argument("--model", default=str(HERE / "domain/skeleton-model.nddl"))
    ap.add_argument("--goal", action="append", default=[], help="a base location to reach, in order")
    ap.add_argument("--final", help="the base location the run ends at")
    ap.add_argument("--port", type=int, default=47810)
    a = ap.parse_args()
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
    site_lines, names = instance(site)
    loc = {v: k for k, v in names.items()}
    goals = [("rover.base", "At", {"loc": loc[g]}, False) for g in a.goal]
    goals += [("rover.base", "At", {"loc": loc[a.final]}, True)] if a.final else []
    state = initial_state(query(node, client, "base_pose"), site)
    log("mission", goals=goals, state=state)
    link = Link(a.port)
    failures, n_plan = {}, 0
    while True:
        if all(state.get(g[0]) == [g[1], g[2]] for g in goals):
            log("done", state=state)
            break
        n_plan += 1
        plan = solve(model, problem(model, site_lines, state, goals), run_dir, n_plan)
        log("plan", n=n_plan, solved=plan["solved"], steps=plan["steps"],
            activities=[(x["type"], x["params"]) for x in plan["activities"]])
        if not plan["solved"]:
            log("no_plan", state=state, goals=goals)
            if needs_operator(f"EUROPA found no plan from state {state} for goals {goals}. "
                              "Reply 'continue' to retry planning, anything else to abort."):
                continue
            break
        for act in plan["activities"]:
            cap, args = capability_call(act, names, site)
            log("dispatch", capability=cap, args=args)
            res = link.dispatch(cap, args)
            state, as_planned = facts_from_result(state, act, cap, args, res, site)
            # an intermediate goal, once reached, leaves the goal set; the final one must hold at the horizon
            while goals and not goals[0][3] and state.get(goals[0][0]) == [goals[0][1], goals[0][2]]:
                goals.pop(0)
            log("result", capability=cap, success=res["success"], failure_kind=res["failure_kind"],
                failure_reason=res["failure_reason"], state=state, as_planned=as_planned)
            if not as_planned:
                key = json.dumps([cap, args], sort_keys=True)
                failures[key] = failures.get(key, 0) + 1
                break
        if any(v >= ATTEMPTS for v in failures.values()):
            log("no_plan", reason="attempts exhausted", failures=failures)
            if needs_operator(f"Repeated failures, no plan around them: {failures}. "
                              "Reply 'continue' to retry, anything else to abort."):
                continue
            break
    link.finish()


if __name__ == "__main__":
    main()
