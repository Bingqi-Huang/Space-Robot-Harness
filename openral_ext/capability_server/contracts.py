"""The capability contracts and the site interaction layer, shared by the boundary (node.py) and every caller that
validates a call before sending it (Ours' invariant guard)."""
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CONTRACTS = yaml.safe_load((HERE / "contracts.yaml").read_text())
IX = json.loads((HERE / "../../space_robotics_bench/assets/lunar_base/usd/scene/lunar_base/interaction.json").resolve().read_text())


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
        if key == "feature" and v not in IX["points"]:
            return f"unknown feature {v!r}"
    return ""
