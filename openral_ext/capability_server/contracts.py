"""The capability contracts and the site interaction layer, shared by the boundary (node.py) and every caller that
validates a call before sending it (Ours' invariant guard)."""
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CONTRACTS = yaml.safe_load((HERE / "contracts.yaml").read_text())
IX = json.loads((HERE / "../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json").resolve().read_text())


def item_catalogue(record: dict) -> dict:
    """Public equipment data, not current object pose or a grasp solution.

    The asset-side catalogue is the equipment specification; the scene interaction
    export can retain older handle fields. All methods receive this same record.
    """
    source = Path(record["usd"]).with_suffix(".json")
    data = json.loads(source.read_text())
    result = {"size_m": data["size_m"], "mass_kg": data["mass_kg"],
              "catalogue_source": str(source.relative_to(HERE.parents[1]))}
    handle = data.get("handle")
    if handle:
        result["handle_height_above_base_m"] = round(handle["xyz"][2], 3)
        if "neck_thickness_m" in handle and "head_width_m" in handle:
            captive = "collar_thickness_m" in handle
            result["carry_handle"] = ("captive lifting collar on top" if captive else "T-shaped lifting eye on top")
            result["grasp_interface"] = {
                "type": "slot_between_head_and_collar" if captive else "neck_with_overhanging_head",
                "contact_region": ("slot on the narrow neck, between the transverse head above and the collar below"
                                   if captive else
                                   "narrow neck between the transverse head and the wider mounting pedestal"),
                "engagement": ("fingers close on opposite sides of the neck and sit in the slot; the head above "
                               "supports the lifted load and the collar below stops the fingers dropping, so the "
                               "load cannot roll out of the jaws" if captive else
                               "fingers close on opposite sides of the neck below the head; the head supports the lifted load"),
                "release_constraint": "below_overhang: after opening, withdraw sideways below the head before lifting clear",
                "carry_constraint": (
                    ("the head is the upper stop and the collar the lower one, so the fingers are captive in the "
                     "slot: a roll about the approach axis has to lift one finger out of it and press the other "
                     "into it, and both are stopped within (neck_height - the fingers' own height)/2. Against a "
                     "twist about the neck's upright axis there is still only friction on a flat rectangle -- "
                     "turned by phi the neck presents neck_thickness*cos(phi) + neck_width*sin(phi) to jaws closed "
                     "on its thickness" if captive else
                     "the head takes a vertical pull and the pads take a sideways swing, but against a twist about "
                     "the neck's own upright axis there is only friction on a flat rectangle. Turned by phi the neck "
                     "presents neck_thickness*cos(phi) + neck_width*sin(phi) to jaws closed on its thickness, so a "
                     "few degrees of slip widens what they hold by half again. A turn is the move that does this: it "
                     "asks for the torque continuously, and the slip accumulates instead of swinging back")),
                "not_clamping_regions": ["transverse head", "collar", "wider mounting pedestal"],
                "observation_requirement": "distinguish the neck from both the head and pedestal, and see clearance for both fingers",
                "closing_width_m": handle["neck_thickness_m"],  # the neck thickness is what the jaws close across
                "dimensions_m": {k.removesuffix("_m"): handle[k] for k in (
                    "neck_thickness_m", "neck_width_m", "neck_height_m", "head_width_m", "head_depth_m",
                    "collar_thickness_m", "collar_width_m", "collar_depth_m", "standoff_m") if k in handle},
                "evidence_requirement": "catalogue geometry does not locate the interface; confirm the visible part before contact",
            }
    return result


def check_args(contract: dict, args: dict) -> str:
    """'' when `args` matches the contract's inputs, else the reason."""
    inputs = contract.get("inputs") or {}
    for key in args:
        if key not in inputs:
            return f"unknown input {key!r} (contract inputs: {sorted(inputs)})"
    for key, (typ, required, _) in inputs.items():
        if key not in args:
            if required:
                return f"missing required input {key!r}"
            continue
        v = args[key]
        if typ == "number" and not isinstance(v, (int, float)):
            return f"{key!r} must be a number"
        if typ.startswith("number[") and not (isinstance(v, list) and len(v) == int(typ[7:-1]) and all(isinstance(e, (int, float)) for e in v)):
            return f"{key!r} must be {typ}"
        if typ == "string" and not isinstance(v, str):
            return f"{key!r} must be a string"
        if typ.startswith("string(") and v not in typ[7:-1].split("|"):
            return f"{key!r} must be one of {typ[7:-1].split('|')}"
        if key == "feature" and (v not in IX["points"] or "object" in IX["points"][v]):
            return f"unknown feature {v!r}"
        if key == "support" and (v not in IX["points"] or IX["points"][v]["type"] != "place"):
            return f"unknown support {v!r} (a site map point of type place)"
    return ""
