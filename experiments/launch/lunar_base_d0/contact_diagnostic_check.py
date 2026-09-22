"""Open-jaw fixture restore, production visual contact, closure, then stop."""
from d0_common import *
from geometry_msgs.msg import PoseWithCovarianceStamped
import yaml

source = Path(os.environ['CONTACT_SNAPSHOT'])
done = []
pub = n.create_publisher(String, '/srb/envs/snapshot', 10)
n.create_subscription(String, '/srb/envs/snapshot/done', lambda m: done.append(json.loads(m.data)), 10)
while pub.get_subscription_count() == 0:
    spin(0.2)
pub.publish(String(data=json.dumps({'op': 'restore', 'path': str(source)})))
while not done:
    spin(0.2)
log('RESTORE', response=done)
estimate = json.loads(source.with_suffix('.json').read_text())
ip = PoseWithCovarianceStamped()
ip.header.frame_id = 'map'
ip.pose.pose.position.x, ip.pose.pose.position.y = estimate['x'], estimate['y']
ip.pose.pose.orientation.z = math.sin(estimate['yaw']/2)
ip.pose.pose.orientation.w = math.cos(estimate['yaw']/2)
ip.pose.covariance[0] = ip.pose.covariance[7] = 0.02**2
ip.pose.covariance[35] = 0.02**2
ip_pub = n.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
while ip_pub.get_subscription_count() == 0:
    spin(0.2)
ip_pub.publish(ip)
want = [estimate['arm'][f'joint{i}'] for i in range(1,8)]
dispatch('joints', {'joint_targets': want, 'tolerance_rad': 0.05}, deadline=90.0)
spin(1.0)
off = {k: arm[k]-q for k,q in estimate['arm'].items() if k in arm and abs(arm[k]-q)>0.05}
log('RESTORED_ARM', off=off)
if off:
    raise SystemExit('restore did not reach the open-jaw fixture posture')
client = ActionClient(n, ExecuteRskill, '/openral/execute_rskill')
client.wait_for_server()
goal = ExecuteRskill.Goal()
goal.rskill_id = 'OpenRAL/rskill-contact-diagnostic'
contracts = yaml.safe_load((HERE/'../../../openral_ext/capability_server/contracts.yaml').resolve().read_text())
goal.deadline_s = float(contracts['effects']['pick']['default_deadline_s'])
goal.goal_params_json = json.dumps({
    'target': 'spare ORU (gold MLI-covered box) staged on the depot stand',
    'part': 'the narrow neck between the transverse head and the wider mounting pedestal, just below the T-shaped head; not the head or pedestal',
    'evidence_dir': str(Path(os.environ['D0_LOG'])/'evidence'),
})
last_feedback_seq = None
def feedback(message):
    global last_feedback_seq
    if message.feedback.evidence_json:
        evidence = json.loads(message.feedback.evidence_json)
        if evidence.get('seq') == last_feedback_seq:
            return
        last_feedback_seq = evidence.get('seq')
        log('FEEDBACK', evidence=evidence)
        with (Path(os.environ['D0_LOG'])/'contact_feedback.jsonl').open('a') as stream:
            stream.write(json.dumps({'wall_t': time.time(), 'evidence': evidence})+'\n')
future = client.send_goal_async(goal, feedback_callback=feedback)
while not future.done():
    spin(0.1)
handle = future.result()
if not handle.accepted:
    raise SystemExit('diagnostic goal rejected')
future = handle.get_result_async()
while not future.done():
    spin(0.2)
result = future.result().result
evidence = json.loads(result.evidence_json)
(Path(os.environ['D0_LOG'])/'contact_result.json').write_text(json.dumps({
    'success': result.success, 'failure_reason': result.failure_reason, 'evidence': evidence}, indent=2))
log('CONTACT_RESULT', success=result.success, failure_reason=result.failure_reason)
rclpy.shutdown()
