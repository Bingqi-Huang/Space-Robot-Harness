"""The arm holding the spare ORU still, in a bare simulation: what the joints' drives carry when nothing else is in the scene.

    /home/bingqi/Programs/isaac-sim/python.sh experiments/robot_check/carry_static.py --state <carry_state.json> [--no_oru 1]
        [--grip_effort N] [--fix_base 0|1] [--dwell_s S]

The state file is a carry recorded from a real run (arm joints, jaw, the ORU's pose in the gripper base frame). The arm holds those
joints, the jaws close on the handle, and this prints the drive efforts against their limits (60/60/30/30/10/10/10 N m) and how far
each joint sits from its target. Written after gc3 and gt1c2 showed joint 4 at 30 N m and joints 5-7 at 10 N m for tens of seconds
with a 1 kg unit in 1.625 m/s^2 -- a 1.6 N weight (F97 follow-up).
"""
import argparse
import json
import os

from isaaclab.app import AppLauncher

p = argparse.ArgumentParser()
p.add_argument("--state", required=True)
p.add_argument("--dwell_s", type=float, default=5.0)
p.add_argument("--grip_effort", type=float, default=-1.0)
p.add_argument("--no_oru", type=int, default=0)
p.add_argument("--fix_base", type=int, default=1)
p.add_argument("--hz", type=float, default=200.0)
p.add_argument("--csv", default="")
p.add_argument("--kick_j4", type=float, default=0.0)
p.add_argument("--arm_k", type=float, default=-1.0)
p.add_argument("--arm_c_scale", type=float, default=1.0)
AppLauncher.add_app_launcher_args(p)
args = p.parse_args()
args.headless = True
app = AppLauncher(args).app

import numpy as np  # noqa: E402
import torch  # noqa: E402
import isaaclab.sim as sim_utils  # noqa: E402
from isaaclab.assets import Articulation, RigidObject, RigidObjectCfg  # noqa: E402
from isaaclab.utils.math import quat_from_matrix  # noqa: E402

from srb.assets.robot.mobile_manipulation.lunarbot import LunarBot  # noqa: E402

ORU = "/mnt/SharedData/Research/Space_Robot_Harness/space_robotics_bench/assets/lunar_base/usd/power/orbital_replacement_unit/orbital_replacement_unit.usdc"
st = json.load(open(args.state))
DT = 1 / args.hz
sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=DT, gravity=(0.0, 0.0, -1.625)))
g = sim_utils.GroundPlaneCfg()
g.func("/World/ground", g)
cfg = LunarBot().asset_cfg.replace(prim_path="/World/Robot")
if args.fix_base:
    cfg.spawn.articulation_props.fix_root_link = True
if args.grip_effort >= 0:
    cfg.actuators["gripper"].effort_limit = float(args.grip_effort)
if args.arm_k >= 0:
    cfg.actuators["arm"].stiffness = float(args.arm_k)
if args.arm_c_scale != 1.0:
    cfg.actuators["arm"].damping = {j: c * args.arm_c_scale for j, c in cfg.actuators["arm"].damping.items()}
robot = Articulation(cfg)
oru = None
if not args.no_oru:
    oru = RigidObject(RigidObjectCfg(prim_path="/World/oru", spawn=sim_utils.UsdFileCfg(usd_path=ORU),
                                     init_state=RigidObjectCfg.InitialStateCfg(pos=(3.0, 3.0, 3.0))))
sim.reset()
names = list(robot.joint_names)
arm_ids = [names.index(f"joint{i}") for i in range(1, 8)]
grip_ids = [names.index(f"eg2_joint{i}") for i in range(1, 7)]
sign = torch.tensor([1.0, 1.0, -1.0, -1.0, 1.0, 1.0], device=robot.device)
q = robot.data.default_joint_pos.clone()
for i, j in enumerate(names):
    if j in st["joints"]:
        q[0, i] = st["joints"][j]
robot.write_joint_state_to_sim(q, torch.zeros_like(q))
target = q.clone()
target[0, grip_ids] = sign * 0.10  # the close command
robot.set_joint_position_target(target)
robot.write_data_to_sim()
sim.step()
robot.update(DT)
eg2 = robot.find_bodies("eg2_base")[0][0]
R = torch.zeros(1, 3, 3, device=robot.device)
qw = robot.data.body_quat_w[0, eg2]
from isaaclab.utils.math import matrix_from_quat  # noqa: E402

Te = torch.eye(4, device=robot.device)
Te[:3, :3] = matrix_from_quat(qw.unsqueeze(0))[0]
Te[:3, 3] = robot.data.body_pos_w[0, eg2]
inertia = robot.root_physx_view.get_inertias()[0].reshape(-1, 3, 3)
print("INERTIA_DIAG", {b: [round(float(inertia[i, k, k]), 5) for k in range(3)] for i, b in enumerate(robot.body_names) if b.startswith(("Link", "eg2_base"))}, flush=True)
print("ARMATURE", {j: round(float(a), 4) for j, a in zip(robot.joint_names, robot.root_physx_view.get_dof_armatures()[0].tolist()) if j.startswith(("joint", "eg2"))}, flush=True)
print("STIFFNESS", {j: round(float(a), 2) for j, a in zip(robot.joint_names, robot.root_physx_view.get_dof_stiffnesses()[0].tolist()) if j.startswith("joint")}, flush=True)
print("DAMPING", {j: round(float(a), 2) for j, a in zip(robot.joint_names, robot.root_physx_view.get_dof_dampings()[0].tolist()) if j.startswith("joint")}, flush=True)
M = robot.root_physx_view.get_generalized_mass_matrices()[0].cpu().numpy()
print("MASS_MATRIX_DIAG", {j: round(float(M[i, i]), 4) for i, j in enumerate(names) if j.startswith(("joint", "eg2_joint1"))}, "shape", M.shape, flush=True)
print("MASSES_KG", {b: round(float(m), 3) for b, m in zip(robot.body_names, robot.root_physx_view.get_masses()[0].tolist())}, flush=True)
if oru is not None:
    To = Te @ torch.tensor(st["oru_in_eg2"], device=robot.device, dtype=torch.float32)
    quat = quat_from_matrix(To[:3, :3].unsqueeze(0))[0]
    pose = torch.cat([To[:3, 3], quat]).unsqueeze(0)
    oru.write_root_pose_to_sim(pose)
    oru.write_root_velocity_to_sim(torch.zeros(1, 6, device=robot.device))
lim = np.array([60, 60, 30, 30, 10, 10, 10.0])
log = []
fine = []
if args.kick_j4:  # a step of the elbow target, as a disturbance to the arm alone
    target[0, arm_ids[3]] += args.kick_j4
steps = int(args.dwell_s / DT)
for k in range(steps):
    robot.set_joint_position_target(target)
    robot.write_data_to_sim()
    if oru is not None:
        oru.write_data_to_sim()
    sim.step()
    robot.update(DT)
    if oru is not None:
        oru.update(DT)
    fine.append([k * DT] + robot.data.applied_torque[0, arm_ids].cpu().tolist() + (target[0, arm_ids] - robot.data.joint_pos[0, arm_ids]).cpu().tolist())
    if k % int(0.5 / DT) == 0 or k == steps - 1:
        eff = robot.data.applied_torque[0, arm_ids].cpu().numpy()
        err = (target[0, arm_ids] - robot.data.joint_pos[0, arm_ids]).cpu().numpy()
        jaw = float(robot.data.joint_pos[0, grip_ids[0]])
        z = float(oru.data.root_pos_w[0, 2]) if oru is not None else None
        log.append((k * DT, eff, err, jaw, z))
        print(f"t {k * DT:4.1f} effort {np.round(eff, 1).tolist()} err_rad {np.round(err, 3).tolist()} jaw {jaw:.3f} oru_z {z}", flush=True)
last = [r for r in log if r[0] >= args.dwell_s - 2.0]
print("SUMMARY effort_mean", np.round(np.mean([r[1] for r in last], axis=0), 1).tolist(), "of limits", lim.tolist(), flush=True)
if args.csv:
    np.savetxt(args.csv, np.array(fine), delimiter=",")
    F = np.array(fine)
    for j in (3, 5):
        e = F[:, 8 + j] - F[:, 8 + j].mean()
        sp = np.abs(np.fft.rfft(e * np.hanning(len(e))))
        fr = np.fft.rfftfreq(len(e), DT)
        print(f"FFT joint{j + 1} err peak Hz", round(float(fr[1 + int(np.argmax(sp[1:]))]), 2), "rms", round(float(e.std()), 4), flush=True)
os._exit(0)
