# LunarBot arm — RealMan RM-75 datasheet (authoritative copy)

Supplied by the user on 2026-09-14. This is the source of truth for every
arm-side limit in `openral/robots/lunar_bot/robot.yaml` and for any
kernel/HAL bound that references the arm. Do not re-derive these numbers
from the simulator asset; the simulator asset should match them.

| Parameter | Value |
|---|---|
| Degrees of freedom | 7 |
| Configuration | humanoid (anthropomorphic) |
| Brakes | J1–J4 hard (mechanical) brake; J5–J7 soft brake |
| Working radius | 610 mm (standard); 627 mm (6FB); 638.5 mm (6F) |
| Rated payload | 5 kg |
| Mass | 7.8 kg (standard); 7.9 kg (six-axis F/T version) |
| Repeatability | ±0.05 mm |
| TCP linear speed | ≤ 1.8 m/s |
| Typical power | ≤ 200 W |
| Peak power | ≤ 1000 W |
| Mounting | any orientation |
| Base diameter | φ107 mm |
| Materials | aluminium alloy / ABS |
| Operating temperature | 0–45 °C |
| Operating humidity | 25–85 % non-condensing |

## Joint ranges and speeds

| Joint | Range (°) | Range (rad) | Max speed (°/s) | Max speed (rad/s) |
|---|---|---|---|---|
| J1 | −178 … +178 | ±3.1067 | 180 | 3.1416 |
| J2 | −130 … +130 | ±2.2689 | 180 | 3.1416 |
| J3 | −178 … +178 | ±3.1067 | 225 | 3.9270 |
| J4 | −135 … +135 | ±2.3562 | 225 | 3.9270 |
| J5 | −178 … +178 | ±3.1067 | 225 | 3.9270 |
| J6 | −128 … +128 | ±2.2340 | 225 | 3.9270 |
| J7 | −360 … +360 | ±6.2832 | 225 | 3.9270 |

`rad = deg × π / 180`, rounded to 4 decimals; the manifest carries the
rounded radian values. Joint order J1…J7 corresponds to SRB's
`joint1`…`joint7` (`lunarbot.py`), which is also the order the live
`/srb/env0/robot/joint_states` publishes them in.

## How the numbers are used

- `robot.yaml` `joints[joint1..joint7].position_limits` — the radian ranges
  above. The C++ safety kernel's JOINT_POSITION per-joint bound check
  compares every commanded target against these.
- `robot.yaml` `joints[...].velocity_limit` — SRB's `lunarbot.py` already
  declares 3.14 (J1–J2) / 3.92 (J3–J7) rad/s, which matches the datasheet;
  the manifest keeps those values.
- `robot.yaml` `capabilities.can_lift_kg` — 5.0.
- `safety.max_ee_speed_m_s` — the datasheet's 1.8 m/s is the mechanical
  ceiling, not an operational bound; the manifest keeps the deliberately
  conservative bring-up value (0.2 m/s) and this ceiling is recorded here so
  no future value exceeds it.
- Fault-injection / FDIR design (later phases): J1–J4 hard brakes vs. J5–J7
  soft brakes is a real asymmetry worth reflecting if arm-brake faults are
  simulated.
