"""Set the static joint friction of the LunarBot arm's seven joints to zero in the robot USD.

    openral/.venv/bin/python experiments/robot_check/zero_arm_joint_friction.py

PhysX's joint friction is a unitless coefficient on the force transmitted between the two links a joint connects. The USD
authored 0.4, 0.4, 0.3, 0.3, 0.2, 0.2, 0.1 on joints 1-7. With the articulation's base free (the robot standing on its wheels)
that coefficient times the constraint forces stuck the arm: a 0.10 rad step took 8 s to get half way, the drives saturated at
their torque limits (60/60/30/30/10/10/10 N m), and the arm never held a commanded posture (F96). With the base fixed, or the
friction zero, every joint reaches a 0.10 rad step in 0.05-0.3 s and holds with under 1 N m. The drives keep their damping.
"""
from pxr import Usd

PATH = "/mnt/SharedData/Research/Space_Robot_Harness/space_robotics_bench/assets/srb_assets/robot/mobile_manipulation/lunarbot/lunarbot.usdc"
stage = Usd.Stage.Open(PATH)
changed = []
for prim in stage.Traverse():
    if prim.GetName() in {f"joint{i}" for i in range(1, 8)}:
        attr = prim.GetAttribute("physxJoint:jointFriction")
        if attr and attr.IsValid():
            changed.append((prim.GetName(), attr.Get()))
            attr.Set(0.0)
stage.GetRootLayer().Save()
print("joint friction set to 0:", changed)
