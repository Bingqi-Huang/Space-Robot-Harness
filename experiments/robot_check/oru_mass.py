"""What PhysX holds for the spare ORU: mass, inertia, and its fall under lunar gravity, alone on a ground plane.

    /home/bingqi/Programs/isaac-sim/python.sh experiments/robot_check/oru_mass.py

Written after the arm held the ORU with its wrist and elbow drives at their torque limits for tens of seconds (F97 follow-up):
a 1 kg unit in 1.625 m/s^2 weighs 1.6 N, and this reads what the simulator makes of the asset.
"""
import os

from isaaclab.app import AppLauncher

app = AppLauncher(headless=True).app

import isaaclab.sim as sim_utils  # noqa: E402
from isaaclab.assets import RigidObject, RigidObjectCfg  # noqa: E402

ORU = "/mnt/SharedData/Research/Space_Robot_Harness/space_robotics_bench/assets/lunar_base/usd/power/orbital_replacement_unit/orbital_replacement_unit.usdc"
DT = 1 / 200
sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=DT, gravity=(0.0, 0.0, -1.625)))
g = sim_utils.GroundPlaneCfg()
g.func("/World/ground", g)
oru = RigidObject(RigidObjectCfg(prim_path="/World/oru", spawn=sim_utils.UsdFileCfg(usd_path=ORU),
                                 init_state=RigidObjectCfg.InitialStateCfg(pos=(0.0, 0.0, 2.0))))
sim.reset()
v = oru.root_physx_view
print("MASS_KG", v.get_masses().tolist(), flush=True)
print("INERTIA", v.get_inertias().tolist(), flush=True)
print("COM", v.get_coms().tolist(), flush=True)
z = []
for i in range(120):
    oru.write_data_to_sim()
    sim.step()
    oru.update(DT)
    z.append(float(oru.data.root_pos_w[0, 2]))
t = 120 * DT
print("FALL", {"t_s": t, "z0": 2.0, "z": z[-1], "g_est_m_s2": 2 * (2.0 - z[-1]) / t ** 2}, flush=True)
os._exit(0)
