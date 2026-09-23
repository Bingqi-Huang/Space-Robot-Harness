"""Site acceptance for the held-out ladder's base-wide scene (research repo docs/heldout_design.md §4, §9).

Through the common capability boundary only: the units' telemetry, the inventory record and the mission brief reach
the methods; every serviced unit's control-panel button, shutter button and equipment bay, and every logistics stand
slot, has a stand the arm can do the whole job from (`work_stands`, the robot's own IK); from view poses the front
camera + VLM can tell the BESS condenser's drawn shutter and read the BESS and ISRU plant lamps. Run with
D0_CAPABILITY_SERVER=1 D0_SCENARIO=heldout_radiator_cover D0_ENV="env.faulted_unit=bess" (the battery unit's HVAC
shutter drawn, its lamp red).
"""
from d0_boundary import cap, query
from d0_common import *  # noqa: F401,F403

log("BRIEF", text=latched_string("/srb/env0/mission_brief"))
log("POWER", **query("power_status"))
log("INVENTORY", records=query("manifest")["inventory"])


def grasp_height(place: str, obj: str) -> float:
    return IX["points"][place]["xyz"][2] + IX["objects"][obj]["handle"]["xyz"][2]


for unit, spec in IX["units"].items():
    log("STANDS", **query("work_stands", feature=f"{spec['panel']}/press"))
    if spec["cover"]:
        log("STANDS", **query("work_stands", feature=f"{spec['cover']}/cover_button"))
    for bay in spec["bays"]:
        module = next(n for n, o in IX["objects"].items() if o["support"] == f"{bay}/tray")
        log("STANDS", **query("work_stands", feature=f"{bay}/tray", grasp_height_m=grasp_height(f"{bay}/tray", module)))
# every stand slot a module or container is staged on or delivered to, with the tallest handle it may carry there
tallest = max(IX["objects"], key=lambda n: IX["objects"][n]["handle"]["xyz"][2])
for slot in sorted(k for k, v in IX["points"].items() if v["type"] == "place" and "_stand/" in k):
    log("STANDS", **query("work_stands", feature=slot, grasp_height_m=grasp_height(slot, tallest)))

views = query("site_map")["view_poses"]
LAMP = "What colour is the round status lamp on the control panel straight ahead? Answer with the colour and where it is."
for view, question in (("bess", LAMP),
                       ("bess_hvac", "Look at the condenser unit straight ahead: are its fans and fins exposed, or is a "
                                     "dark roll-up shutter drawn down over them? Answer 'exposed' or 'shutter drawn' and why."),
                       ("isru", LAMP)):
    v = views[view]
    run(f"navigate to view {view}", lambda v=v: cap("navigate_to_pose", x=v["x"], y=v["y"], yaw=v["yaw"]))
    log("OBSERVE", view=view, **query("observe", camera="front", question=question))
