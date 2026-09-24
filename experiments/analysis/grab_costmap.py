"""Grab one global costmap and the AMCL pose from a live run's ROS graph into a JSON file (run inside the run's
container with its ROS_DOMAIN_ID and Fast DDS profile). Never open a live bag; this reads the topics instead."""
import rclpy, json, time, sys
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseWithCovarianceStamped
rclpy.init(); n=Node('grab'); out={}
q=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE)
def g(m):
    if 'global' not in out: out['global']=dict(res=m.info.resolution,w=m.info.width,h=m.info.height,ox=m.info.origin.position.x,oy=m.info.origin.position.y,data=list(m.data))
n.create_subscription(OccupancyGrid,'/global_costmap/costmap',g,q)
n.create_subscription(PoseWithCovarianceStamped,'/amcl_pose',lambda m: out.__setitem__('amcl',[m.pose.pose.position.x,m.pose.pose.position.y]),q)
t=time.time()
while time.time()-t<30 and len(out)<2: rclpy.spin_once(n,timeout_sec=0.5)
json.dump(out,open(sys.argv[1],'w')); print(out.get('amcl'))
