"""Live probe for the costmap robot-pose freeze (F112 §3): compares the local costmap's published footprint (its own
getRobotPose) with a fresh TF lookup odom->base_link; on a > 0.5 m disagreement lasting 5 s, dumps every thread's
state / wait channel / cpu time of controller_server and planner_server from /proc (no ptrace needed)."""
import sys, time, math, os, subprocess, json
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PolygonStamped
from tf2_ros import Buffer, TransformListener
out = open(sys.argv[1], 'a')
rclpy.init(); n = Node('freeze_probe', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', rclpy.Parameter.Type.BOOL, True)])
buf = Buffer(); TransformListener(buf, n)
fp = {}
n.create_subscription(PolygonStamped, '/local_costmap/published_footprint', lambda m: fp.update(odom=m), 10)
n.create_subscription(PolygonStamped, '/global_costmap/published_footprint', lambda m: fp.update(map=m), 10)
def pids(name):
    return [p for p in os.listdir('/proc') if p.isdigit() and name in open(f'/proc/{p}/cmdline', 'rb').read().decode(errors='ignore').split('\0')[0]]
def dump(tag):
    for name in ('controller_server', 'planner_server'):
        for p in pids(name):
            rows = []
            for t in os.listdir(f'/proc/{p}/task'):
                st = open(f'/proc/{p}/task/{t}/stat').read().split(')')[-1].split()
                comm = open(f'/proc/{p}/task/{t}/comm').read().strip(); wchan = open(f'/proc/{p}/task/{t}/wchan').read().strip()
                rows.append((t, comm, st[0], wchan, int(st[11]) + int(st[12])))
            out.write(json.dumps(dict(tag=tag, proc=name, pid=p, threads=rows)) + '\n')
    out.flush()
bad = {}; last_dump = 0
while rclpy.ok():
    rclpy.spin_once(n, timeout_sec=0.5)
    for frame in ('odom', 'map'):
        m = fp.get(frame)
        if m is None or not buf.can_transform(frame, 'base_link', rclpy.time.Time()): continue
        tr = buf.lookup_transform(frame, 'base_link', rclpy.time.Time()).transform.translation
        cx = sum(p.x for p in m.polygon.points) / len(m.polygon.points); cy = sum(p.y for p in m.polygon.points) / len(m.polygon.points)
        d = math.hypot(cx - tr.x, cy - tr.y)
        now = time.time()
        if d > 0.5:
            bad.setdefault(frame, now)
            if now - bad[frame] > 5 and now - last_dump > 60:
                out.write(json.dumps(dict(event='FREEZE', frame=frame, disagreement_m=round(d, 2), footprint=[round(cx, 2), round(cy, 2)], tf=[round(tr.x, 2), round(tr.y, 2)], fp_stamp=m.header.stamp.sec, wall=now)) + '\n')
                dump(f'freeze_{frame}'); last_dump = now
                print('FREEZE', frame, round(d, 2), flush=True)
        else:
            bad.pop(frame, None)
