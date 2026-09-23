"""The common capability boundary as a check script calls it: effects on /space/capability/execute, queries on
/space/capability/query -- the interface PLEXIL Commands/Lookups and Ours' tools use (§21.4). Needs D0_CAPABILITY_SERVER=1."""
from d0_common import json, n, rclpy, sim, time
from rclpy.action import ActionClient
from space_harness_msgs.action import ExecuteCapability
from space_harness_msgs.srv import QueryCapability

cap_client = ActionClient(n, ExecuteCapability, "/space/capability/execute")
query_client = n.create_client(QueryCapability, "/space/capability/query")
assert cap_client.wait_for_server(timeout_sec=120) and query_client.wait_for_service(timeout_sec=60), "capability boundary not up"


def cap(name, deadline=0.0, **args):
    goal = ExecuteCapability.Goal(capability=name, args_json=json.dumps(args), deadline_s=float(deadline))
    t, sim0 = time.time(), sim["t"]
    f = cap_client.send_goal_async(goal)
    rclpy.spin_until_future_complete(n, f, timeout_sec=60)
    rf = f.result().get_result_async()
    while not rf.done():
        rclpy.spin_once(n, timeout_sec=0.1)
    r = rf.result().result
    return dict(capability=name, success=r.success, failure_reason=r.failure_reason, failure_kind=r.failure_kind,
                evidence=json.loads(r.evidence_json or "{}"), wall_s=round(time.time() - t, 1), sim_s=round(sim["t"] - sim0, 1))


def query(query_name, **args):
    """A query's value; a VLM-backed query or a first stand settlement takes tens of seconds, so no short timeout."""
    f = query_client.call_async(QueryCapability.Request(query=query_name, args_json=json.dumps(args)))
    rclpy.spin_until_future_complete(n, f)
    r = f.result()
    assert r.success, r.failure_reason
    return json.loads(r.value_json)
