"""Direct-with-Earth visibility at the lunar base site, precomputed with SPICE (execution_plan §7.2).

    python3 space_context/earth_visibility.py            # writes space_context/profiles/earth_link.json

The site is the scene's own ground: the centre of the LOLA Site01 "connecting ridge" DEM the scene is built on
(Barker et al. 2021; south polar stereographic, MOON_ME), on the reference sphere. Earth's elevation above the local
horizontal is computed from the planetary ephemeris (DE440) and the lunar orientation (DE440 PA -> ME). From the
lunar south pole Earth is visible for only about half of each sidereal month (NASA Lunar Communications and
Navigation Architecture white paper, 2023 Moon to Mars ACR), which is why relays are planned; this profile assumes
the Direct-with-Earth link only (no relay yet) and a flat 0 deg horizon mask -- terrain would shorten the window,
never lengthen it.

The mission epoch is placed `MISSION_START_BEFORE_LOS_S` before an Earth-set, the same for every Mission A/B scenario:
the window closes during every run, and matters only to a method that needs mission control after it closes. Its
length is three request-answer cycles of the ground protocol (docs/heldout_design.md §8: 4.27 s up, 300 s decision,
4.27 s down), fixed from the protocol alone before any L4 run (user decision 2026-09-24; 45 min before, which no run
reached: covered runs end at 5-12 min of mission time, L4 at ~25).
The one-way delay is the light time plus the operational ground/network latency of the lunar regime (3 s, the low end
of the 3-14 s of Landon et al. 2025, NASA/TM-20250003885).

Kernels (NAIF generic_kernels, fetched into space_context/kernels/): lsk/naif0012.tls, pck/pck00011.tpc,
spk/planets/de440s.bsp, pck/moon_pa_de440_200625.bpc, fk/satellites/moon_de440_250416.tf.
"""
import json
import math
from pathlib import Path

import numpy as np
import spiceypy as sp

HERE = Path(__file__).resolve().parent
KERNELS = ["naif0012.tls", "pck00011.tpc", "de440s.bsp", "moon_pa_de440_200625.bpc", "moon_de440_250416.tf"]
#: scene centre (assets/lunar_base/scene/layout.yaml `dem.center_px` on Site01_final_adj_5mpp_surf.tif), converted
#: from polar stereographic (x -9150 m, y -13750 m, R 1737.4 km) to planetocentric latitude/longitude
SITE = dict(name="LOLA Site01 connecting ridge, lunar base scene centre", lat_deg=-89.4553, lon_deg=213.642,
            dem="Site01_final_adj_5mpp_surf.tif px (1950, 1970)")
SEARCH_FROM, SEARCH_DAYS, STEP_S = "2028-09-01T00:00:00", 60, 600.0
MISSION_START_BEFORE_LOS_S = 925.0  # 3 x (4.27 + 300 + 4.27) s
GROUND_LATENCY_S = 3.0


def earth_elevation_deg(et: float, site_me: np.ndarray) -> tuple[float, float]:
    """Earth's elevation above the site's local horizontal (sphere normal), and the one-way light time."""
    earth, lt = sp.spkpos("EARTH", et, "MOON_ME", "LT+S", "MOON")
    d = np.asarray(earth) - site_me
    up = site_me / np.linalg.norm(site_me)
    return math.degrees(math.asin(float(d @ up) / float(np.linalg.norm(d)))), lt


def main():
    for k in KERNELS:
        sp.furnsh(str(HERE / "kernels" / k))
    # on the reference sphere: the site's ~km of height moves Earth's direction by < 0.0002 deg at 384,000 km
    radius_km = sp.bodvrd("MOON", "RADII", 3)[1][0]
    site_me = np.asarray(sp.latrec(radius_km, math.radians(SITE["lon_deg"]), math.radians(SITE["lat_deg"])))
    et0 = sp.str2et(SEARCH_FROM)
    ets = et0 + np.arange(0, SEARCH_DAYS * 86400, STEP_S)
    elev = np.array([earth_elevation_deg(et, site_me)[0] for et in ets])
    rises = [i for i in range(1, len(ets)) if elev[i - 1] <= 0 < elev[i]]
    sets = [i for i in range(1, len(ets)) if elev[i - 1] > 0 >= elev[i]]

    def refine(i):  # crossing to 1 s between samples i-1 and i
        lo, hi = ets[i - 1], ets[i]
        up = earth_elevation_deg(lo, site_me)[0] > 0
        while hi - lo > 1.0:
            mid = (lo + hi) / 2
            if (earth_elevation_deg(mid, site_me)[0] > 0) == up:
                lo = mid
            else:
                hi = mid
        return hi

    los = refine(next(i for i in sets if any(r < i for r in rises)))  # the first set after a full visible pass began
    aos = refine(next(i for i in rises if ets[i] > los))
    start = los - MISSION_START_BEFORE_LOS_S
    _, lt = earth_elevation_deg(start, site_me)
    profile = dict(
        site=SITE, epoch_utc=sp.et2utc(start, "ISOC", 0), epoch_et=start,
        los_after_start_s=round(los - start, 1), aos_after_start_s=round(aos - start, 1),
        earth_elevation_at_start_deg=round(earth_elevation_deg(start, site_me)[0], 4),
        one_way_delay_s=round(lt + GROUND_LATENCY_S, 2), light_time_s=round(lt, 3), ground_latency_s=GROUND_LATENCY_S,
        horizon_mask_deg=0.0, link="Direct-with-Earth only (no relay)",
        kernels=KERNELS, generated_by="space_context/earth_visibility.py",
        visible_passes_in_search=[dict(rise=sp.et2utc(ets[r], "ISOC", 0)) for r in rises],
    )
    out = HERE / "profiles/earth_link.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(profile, indent=1))
    print(json.dumps({k: v for k, v in profile.items() if k != "visible_passes_in_search"}, indent=1))


if __name__ == "__main__":
    main()
