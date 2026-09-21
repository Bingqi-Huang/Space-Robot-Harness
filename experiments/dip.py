"""How far the COMMAND overshoots when the measured tool is disturbed at insertion start.
Observed in gb7r5: measured z bump +9 mm at ~1.4 s, back to +2 mm by ~3 s; the command (which the scene check reads) reached -6.5 mm.
Model: y_arm(t) = lag_0.25( cmd(t - L) );  measured = y_arm + d(t);  cmd += K * (0 - measured) * dt."""
import numpy as np
DT = 0.05
def disturbance(t, A, rise=0.5, decay=1.5, t0=0.6):
    s = np.maximum(t - t0, 0.0)
    return A * (1 - np.exp(-s / rise)) * np.exp(-s / decay) * 2.6      # peak ~ A
def run(K, L, A=0.009, ramp_scale=1.0, T=12.0, tau=0.25):
    t = np.arange(0, T, DT); d = disturbance(t, A * ramp_scale); n = len(t)
    cmd = np.zeros(n); arm = np.zeros(n); meas = np.zeros(n)
    for k in range(1, n):
        meas[k - 1] = arm[k - 1] + d[k - 1]
        cmd[k] = cmd[k - 1] + K * (0.0 - meas[k - 1]) * DT
        u = cmd[max(k - int(round(L / DT)), 0)]
        arm[k] = arm[k - 1] + (u - arm[k - 1]) * DT / tau
    meas[-1] = arm[-1] + d[-1]
    return float(cmd.min() * 1000), float((arm + d).max() * 1000), float(np.abs(meas[int(0.7 * n):]).max() * 1000), float(d.max() * 1000)
print("open-loop disturbance peak: %.1f mm (observed +9)" % run(0, 0.6)[3])
print("command's lowest excursion (mm), measured peak (mm), residual after 8 s (mm):  window is +-5 mm")
print("  K /s      L=0.6 s                       L=1.0 s")
for K in (2.0, 1.0, 0.7, 0.5, 0.35):
    a = run(K, 0.6); b = run(K, 1.0)
    print(f"  {K:4.2f}   {a[0]:+6.1f} / {a[1]:+5.1f} / {a[2]:4.1f}        {b[0]:+6.1f} / {b[1]:+5.1f} / {b[2]:4.1f}")
print("with the axial start ramped so the disturbance is half as large (ramp over 2 s):")
for K in (1.0, 0.7, 0.5):
    a = run(K, 0.6, ramp_scale=0.5); b = run(K, 1.0, ramp_scale=0.5); print(f"  {K:4.2f}   {a[0]:+6.1f} / {a[1]:+5.1f} / {a[2]:4.1f}        {b[0]:+6.1f} / {b[1]:+5.1f} / {b[2]:4.1f}")
