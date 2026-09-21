"""Step response of each arm joint of the LunarBot in a bare simulation: the robot on a ground plane, nothing commanding it
but this script. A 0.10 rad step per joint, and what the drives, dampers and limits are as PhysX holds them.

    /home/bingqi/Programs/isaac-sim/python.sh experiments/robot_check/arm_steps.py [--self_collisions 0|1] [--fix_base 0|1]

Written after the arm's roll joints 1, 3 and 7 followed commands at 0.002-0.009 rad/s with their torque saturated (F96): this
separates the robot model from everything above it (skills, harness, HAL, the ROS bridge).
"""
import argparse
import json

from isaaclab.app import AppLauncher

p = argparse.ArgumentParser()
p.add_argument("--self_collisions", type=int, default=1)
p.add_argument("--fix_base", type=int, default=0)
p.add_argument("--dwell_s", type=float, default=8.0)
p.add_argument("--zero_friction", type=int, default=0)
p.add_argument("--no_sleep", type=int, default=0)
p.add_argument("--root_mass", type=float, default=0.0)
p.add_argument("--arm_friction", type=float, default=-1.0)
p.add_argument("--usd_friction", type=float, default=-1.0)
p.add_argument("--iters", type=str, default="")
p.add_argument("--hz", type=float, default=200.0)
AppLauncher.add_app_launcher_args(p)
args = p.parse_args()
args.headless = True
app = AppLauncher(args).app

import numpy as np  # noqa: E402
import isaaclab.sim as sim_utils  # noqa: E402
from isaaclab.assets import Articulation  # noqa: E402

from srb.assets.robot.mobile_manipulation.lunarbot import LunarBot  # noqa: E402

DT = 1 / args.hz
sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=DT, gravity=(0.0, 0.0, -1.625)))
ground = sim_utils.GroundPlaneCfg()
ground.func("/World/ground", ground)
cfg = LunarBot().asset_cfg.replace(prim_path="/World/Robot")
cfg.spawn.articulation_props.enabled_self_collisions = bool(args.self_collisions)
if args.fix_base:
    cfg.spawn.articulation_props.fix_root_link = True
if args.arm_friction >= 0:  # the joint static friction is a coefficient on the force between the two links, not a torque: the USD authors 0.1-0.4
    cfg.actuators["arm"].friction = float(args.arm_friction)
if args.iters:
    cfg.spawn.articulation_props.solver_position_iteration_count, cfg.spawn.articulation_props.solver_velocity_iteration_count = map(int, args.iters.split(","))
if args.no_sleep:  # a 200 kg articulation whose arm moves at a few cm/s has a mass-normalised kinetic energy under PhysX's sleep threshold
    cfg.spawn.articulation_props.sleep_threshold = 0.0
    cfg.spawn.articulation_props.stabilization_threshold = 0.0
robot = Articulation(cfg)
if args.usd_friction >= 0:  # the coefficient the USD authors on each arm joint, changed on the stage before the physics starts
    import omni.usd  # noqa: E402

    n_set = 0
    for prim in omni.usd.get_context().get_stage().Traverse():
        if str(prim.GetPath()).startswith("/World/Robot") and prim.GetName() in {f"joint{i}" for i in range(1, 8)}:
            a = prim.GetAttribute("physxJoint:jointFriction")
            if a and a.IsValid():
                a.Set(float(args.usd_friction))
                n_set += 1
    print("USD friction set on", n_set, "joints", flush=True)
sim.reset()


def step(seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        robot.write_data_to_sim()
        sim.step()
        robot.update(DT)


if args.root_mass:  # the articulation root is a 1 g frame body under a 100 kg chassis: give the root a real share of it
    import torch  # noqa: E402

    view0 = robot.root_physx_view
    bn = robot.body_names
    m0 = view0.get_masses().clone()
    i0 = view0.get_inertias().clone()
    ir, ic = bn.index("chassis_base_link"), bn.index("chassis")
    share = float(args.root_mass)
    for idx, new in ((ir, share), (ic, float(m0[0, ic]) - share + float(m0[0, ir]))):
        i0[0, idx] *= new / float(m0[0, idx])
        m0[0, idx] = new
    view0.set_masses(m0, torch.tensor([0], dtype=torch.int32))
    view0.set_inertias(i0, torch.tensor([0], dtype=torch.int32))
names = robot.joint_names
arm = [names.index(f"joint{i}") for i in range(1, 8)]
view = robot.root_physx_view
if args.zero_friction:  # the coefficients the USD authors (0.1-0.4): PhysX joint friction scales with the joint's constraint force
    import torch  # noqa: E402

    robot.write_joint_friction_coefficient_to_sim(torch.zeros_like(robot.data.joint_friction_coeff))
out = {"variant": {"self_collisions": args.self_collisions, "fix_base": args.fix_base, "zero_friction": args.zero_friction, "no_sleep": args.no_sleep, "arm_friction": args.arm_friction, "usd_friction": args.usd_friction, "root_mass": args.root_mass, "iters": args.iters, "hz": args.hz}}
for label, getter in (("stiffness", "get_dof_stiffnesses"), ("damping", "get_dof_dampings"), ("max_force", "get_dof_max_forces"),
                      ("max_velocity", "get_dof_max_velocities"), ("armature", "get_dof_armatures"), ("friction", "get_dof_friction_coefficients")):
    try:
        v = getattr(view, getter)()[0].cpu().numpy()
        out[f"physx_{label}"] = [round(float(v[i]), 4) for i in arm]
    except Exception as exc:  # reason: an API name that this Isaac Lab version does not have is reported, not fatal
        out[f"physx_{label}"] = f"unavailable: {type(exc).__name__}"
robot.set_joint_position_target(robot.data.joint_pos.clone())
step(6.0)
# is the chassis itself at rest? an arm on a rocking or sliding base sees inertial torques and fights them
rest = []
for _ in range(int(2.0 / DT)):
    robot.write_data_to_sim()
    sim.step()
    robot.update(DT)
    rest.append(np.concatenate([robot.data.root_lin_vel_w[0].cpu().numpy(), robot.data.root_ang_vel_w[0].cpu().numpy(), robot.data.root_pos_w[0].cpu().numpy()]))
rest = np.array(rest)
out["chassis_at_rest_2s"] = dict(peak_lin_vel_m_s=round(float(np.abs(rest[:, 0:3]).max()), 4), peak_ang_vel_rad_s=round(float(np.abs(rest[:, 3:6]).max()), 4),
                                 drift_m=[round(float(v), 4) for v in rest[-1, 6:9] - rest[0, 6:9]], height_m=round(float(rest[-1, 8]), 3))
wheel_names = [n for n in names if "wheel" in n or "steering" in n]
out["wheel_and_steering_speed_rad_s"] = {n: round(float(robot.data.joint_vel[0, names.index(n)]), 3) for n in wheel_names}
out["settled_torque"] = [round(float(robot.data.applied_torque[0, i]), 2) for i in arm]
res = {}
for j, ji in enumerate(arm):
    q0 = robot.data.joint_pos.clone()
    tgt = q0.clone()
    delta = 0.10
    tgt[0, ji] += delta
    robot.set_joint_position_target(tgt)
    t, pos, tq, vel = [], [], [], []
    for k in range(int(args.dwell_s / DT)):
        robot.write_data_to_sim()
        sim.step()
        robot.update(DT)
        if k % 10 == 0:
            t.append(k * DT)
            pos.append(float(robot.data.joint_pos[0, ji] - q0[0, ji]))
            tq.append(float(robot.data.applied_torque[0, ji]))
            vel.append(float(robot.data.joint_vel[0, ji]))
    pos, tq, vel, t = map(np.array, (pos, tq, vel, t))
    prog = pos / delta
    t50 = float(t[np.argmax(prog >= 0.5)]) if (prog >= 0.5).any() else None
    t90 = float(t[np.argmax(prog >= 0.9)]) if (prog >= 0.9).any() else None
    res[f"joint{j + 1}"] = dict(t50=t50, t90=t90, error_after=round(float(delta - pos[-1]), 4), peak_torque=round(float(np.abs(tq).max()), 1),
                                end_torque=round(float(tq[-1]), 1), peak_speed=round(float(np.abs(vel).max()), 3))
    robot.set_joint_position_target(q0)
    step(3.0)
out["steps"] = res
print("RESULT " + json.dumps(out), flush=True)
import os  # noqa: E402

os._exit(0)  # the Kit shutdown can hang for minutes after the result is out
