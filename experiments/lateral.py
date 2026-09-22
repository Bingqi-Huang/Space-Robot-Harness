"""Lateral loop during a straight insertion. The arm's path drifts sideways by eps mm per mm of axial travel (open loop);
the servo corrects it with gain K through a delay L. Compare: (a) as built -- one speed cap on the whole error vector, axial error 12 cm;
(b) reference point advancing at v along the line, every component at the same gain."""
import numpy as np
DT = 0.05
def run(mode, v, eps=0.23, K=1.0, L=0.6, tau=0.25, T=12.0, ax0=0.12, vmax=0.025):
    n = int(T / DT); cmd = np.zeros(n + 1); meas = np.zeros(n + 1); ax = 0.0; lat = 0.0; drift = 0.0; hist = []
    for k in range(n):
        if mode == "as built":
            e_ax = max(ax0 - ax, 0.0); e_lat = -lat
            dx_ax, dx_lat = e_ax * K * DT, e_lat * K * DT
            cap = vmax * DT; nrm = np.hypot(dx_ax, dx_lat); s = min(1.0, cap / max(nrm, 1e-12))
            dax, dlat = dx_ax * s, dx_lat * s
        else:
            ref = min(ax0, v * k * DT); e_ax = ref - ax; e_lat = -lat
            dax, dlat = e_ax * K * DT, e_lat * K * DT
        cmd[k + 1] = cmd[k] + dlat
        d = int(round(L / DT)); u = cmd[max(k + 1 - d, 0)]
        meas[k + 1] = meas[k] + (u - meas[k]) * DT / tau
        ax += dax; drift += eps * dax        # open-loop path deviation grows with axial travel
        lat = meas[k + 1] + drift
        hist.append(lat)
    h = np.array(hist); t_arrive = (ax0 / (vmax if mode == 'as built' else v))
    a, b = int(1.0 / DT), int(min(t_arrive, T) / DT)
    return float(np.abs(h[a:b]).mean() * 1000), float(np.abs(h[a:b]).max() * 1000)
print("lateral error DURING the insertion, t from 1 s to arrival (mm): mean / worst")
for name, mode, v in (("as built (5 cm/s cap on the vector, 2.5 cm/s)", "as built", 0.025), ("reference advancing at 2.5 cm/s", "carrot", 0.025), ("reference advancing at 1.5 cm/s", "carrot", 0.015), ("reference advancing at 1.0 cm/s", "carrot", 0.010), ("reference advancing at 0.7 cm/s", "carrot", 0.007)):
    s, w = run(mode, v); print(f"  {name:48s} {s:5.1f} / {w:5.1f}")
print("  observed in gb7r4 (as built, 0.7-3.7 s): 8-11 mm, holding")
