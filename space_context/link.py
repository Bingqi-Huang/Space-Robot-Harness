"""The Direct-with-Earth link as mission time runs (execution_plan §7.4): the precomputed visibility profile
(`earth_visibility.py`) turned into what a method and the ground segment actually get -- whether the link is up, how
long until it closes or reopens, and the one-way delay. Mission time is the simulator clock since the mission started.
Store-and-forward (DTN): a message sent while the link is down is delivered when it next comes up, not dropped."""
import json
from pathlib import Path

PROFILE = json.loads((Path(__file__).resolve().parent / "profiles/earth_link.json").read_text())


def state(mission_t: float) -> dict:
    up = mission_t < PROFILE["los_after_start_s"] or mission_t >= PROFILE["aos_after_start_s"]
    return {"link": PROFILE["link"], "earth_visible": up, "one_way_delay_s": PROFILE["one_way_delay_s"],
            "closes_in_s": round(PROFILE["los_after_start_s"] - mission_t, 1) if mission_t < PROFILE["los_after_start_s"] else None,
            "reopens_in_s": None if up else round(PROFILE["aos_after_start_s"] - mission_t, 1),
            "epoch_utc": PROFILE["epoch_utc"], "source": "SPICE Earth elevation at the site, " + PROFILE["generated_by"]}


def delivery_time(sent_mission_t: float) -> float:
    """When a message sent at this mission time arrives at the other end."""
    t = sent_mission_t if state(sent_mission_t)["earth_visible"] else PROFILE["aos_after_start_s"]
    return t + PROFILE["one_way_delay_s"]
