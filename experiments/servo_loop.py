"""1-D model of `_eye_in_hand.servo`, arithmetic copied from the code:
   e = goal - measured;  [integ += 0.8*e*dt (clip 5 cm) when sag_integral and |e|<3 cm]
   dx = (e + integ) * min(1, step/|e|);  dx capped to max_speed*dt;   command += dx;   measured = plant(command)
plant: pure delay L then a first-order lag tau.   Run at the 20 Hz the servo runs at."""
import numpy as np
DT = 0.05
def run(law, L, tau=0.25, T=25.0, e0=0.025, goal_noise=0.0, vmax=0.05, K=None, sag=True, tol=0.006, seed=0):
    rng = np.random.default_rng(seed)
    n = int(T / DT); cmd = np.zeros(n + 1); meas = np.zeros(n + 1); meas[0] = -e0; cmd[0] = -e0
    integ = 0.0; hist = []; inside = 0; settled = None
    for k in range(n):
        g = rng.normal(scale=goal_noise) if goal_noise else 0.0
        e = g - meas[k]
        if sag and abs(e) < 0.03: integ = float(np.clip(integ + e * DT * 0.8, -0.05, 0.05))
        if law == "present": dx = (e + integ) * min(1.0, 0.04 / max(abs(e), 1e-6))
        else: dx = (e + integ) * min(1.0, K * DT)          # speed = K * error
        cap = vmax * DT
        if abs(dx) > cap: dx = np.sign(dx) * cap
        cmd[k + 1] = cmd[k] + dx
        d = int(round(L / DT)); u = cmd[max(k + 1 - d, 0)]
        meas[k + 1] = meas[k] + (u - meas[k]) * DT / tau
        if abs(g - meas[k + 1]) < tol:
            inside += 1
            if inside >= 3 and settled is None: settled = (k + 1) * DT
        else: inside = 0
    tail = meas[int(n * 0.6):]
    return settled, float(np.ptp(tail) / 2 * 1000), float(np.abs(tail).max() * 1000)
print("law                      | L=0.3 s          | L=0.6 s          | L=1.0 s          | (settle time to <6 mm for 3 cycles / tail half-swing mm)")
for name, law, K, sag in (("present (bang, sag on)", "present", None, True), ("present, sag off", "present", None, False),
                           ("K=3/s, sag off", "k", 3.0, False), ("K=1.5/s, sag off", "k", 1.5, False), ("K=1.0/s, sag off", "k", 1.0, False), ("K=0.7/s, sag off", "k", 0.7, False),
                           ("K=1.5/s, sag ON", "k", 1.5, True)):
    row = []
    for L in (0.3, 0.6, 1.0):
        s, swing, _ = run(law, L, K=K, sag=sag)
        row.append(f"{'never' if s is None else f'{s:5.1f} s'} / {swing:4.1f} mm")
    print(f"{name:24s} | " + " | ".join(row))
print("\nwith 3 mm rms noise on the goal (the fit jitter), L=0.6:")
for name, law, K, sag in (("present (bang, sag on)", "present", None, True), ("K=1.0/s, sag off", "k", 1.0, False)):
    s, swing, mx = run(law, 0.6, K=K, sag=sag, goal_noise=0.003)
    print(f"  {name:24s} settle {s}, tail half-swing {swing:.1f} mm, tail max {mx:.1f} mm")
