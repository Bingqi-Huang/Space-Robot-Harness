"""Site acceptance for the held-out ladder's assets (research repo docs/heldout_design.md §4, step 3 gates).

Through the common capability boundary only: the units' telemetry and the inventory record reach the boundary; every
ORU bay and every radiator cover button has a stand the arm can do the whole job from (`work_stands`, the robot's own
IK); from the radiator and panel view poses the front camera + VLM can tell a drawn shutter from an open one and read
the lamp. Run with D0_CAPABILITY_SERVER=1 D0_SCENARIO=heldout_radiator_cover (faulted pdu_2: its shutter drawn).
"""
from d0_boundary import cap, query
from d0_common import *  # noqa: F401,F403

log("POWER", **query("power_status"))
log("INVENTORY", records=query("manifest")["inventory"])
oru_handle = IX["objects"]["oru_pdu_1"]["handle"]["xyz"][2]
for pdu in ("pdu_1", "pdu_2", "pdu_3"):
    bay = f"{pdu}_bay/tray"
    log("STANDS", **query("work_stands", feature=bay, grasp_height_m=IX["points"][bay]["xyz"][2] + oru_handle))
    log("STANDS", **query("work_stands", feature=f"{pdu}_radiator/cover_button"))
log("STANDS", reference="placed on live in Mission B", **query("work_stands", feature="pdu_1_shelf/shelf"))

views = query("site_map")["view_poses"]
for view, question in (("pdu_2_radiator", "Look at the radiator panel straight ahead: are its white fins exposed, or is a grey "
                                          "roll-up shutter drawn down over them? Answer 'exposed' or 'shutter drawn' and why."),
                       ("pdu_1_radiator", "Look at the radiator panel straight ahead: are its white fins exposed, or is a grey "
                                          "roll-up shutter drawn down over them? Answer 'exposed' or 'shutter drawn' and why."),
                       ("pdu_2", "What colour is the status lamp on the yellow service panel straight ahead?")):
    v = views[view]
    run(f"navigate to view {view}", lambda v=v: cap("navigate_to_pose", x=v["x"], y=v["y"], yaw=v["yaw"]))
    log("OBSERVE", view=view, **query("observe", camera="front", question=question))
