"""The thin invariant / authority guard (execution_plan §4.3) at Ours' effectful dispatch.

Checks only explicit execution boundaries: the capability exists and the arguments match its contract, it is not
hard-unavailable, no active fault prohibits it, no configured hard invariant is violated, and its authority permits it
(or an operator approval is on record): by the capability's own class, or -- for a call classed by what it acts on --
by a target rule (e.g. removing a module from an energized unit's bay needs ground authorization, 14 CFR 1214.403). Outcomes: allow | deny | approval_required | unavailable, each with a
structured reason that goes back to the agent as context. It never judges whether a call is a good next step.
"""
from openral_ext.capability_server.contracts import CONTRACTS, IX, check_args


def _fact(facts: dict, path: str):
    node = facts
    for part in path.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


class Guard:
    def __init__(self, cfg: dict):
        self.authority = cfg["authority"]
        self.invariants = cfg["invariants"]
        self.fdir_prohibits = cfg["fdir_prohibits"]
        self.target_authority = cfg["target_authority"]

    def target_rule(self, capability: str, args: dict, facts: dict) -> dict | None:
        """The first authority rule that classes this call by what it acts on: a site point of a given role (the site
        survey's own classification) whose unit is in a given state in the units' latest telemetry."""
        for rule in self.target_authority:
            if capability not in rule["applies_to"]:
                continue
            pt = IX["points"][args[rule["target_arg"]]]
            if pt.get("role") != rule["target_role"]:
                continue
            unit = facts["power"]["units"][pt["asset"]]
            if all(unit[k] == v for k, v in rule["when_unit"].items()):
                return rule
        return None

    def check(self, capability: str, args: dict, facts: dict) -> tuple[str, str]:
        contract = CONTRACTS["effects"].get(capability)
        if contract is None:
            return "deny", f"no registered effect capability {capability!r}"
        reason = check_args(contract, args)
        if reason:
            return "deny", f"arguments off-contract: {reason}"
        if capability in facts["unavailable"]:
            return "unavailable", facts["unavailable"][capability]
        for fault, groups in self.fdir_prohibits.items():
            if facts["fdir"].get(fault, {}).get("active") and ("all_effects" in groups or capability in groups):
                return "deny", f"active fault {fault!r} prohibits {capability}: {facts['fdir'][fault]['detail']}"
        for inv in self.invariants:
            if "all_effects" in inv["applies_to"] or capability in inv["applies_to"]:
                for path, want in inv["requires"].items():
                    if _fact(facts, path) != want:
                        return "deny", f"invariant {inv['name']}: requires {path} == {want!r} ({inv['why']})"
        rule = self.target_rule(capability, args, facts)
        if rule is not None:
            target = args[rule["target_arg"]]
            if {"capability": capability, "target": target} in facts["approvals"]:
                return "allow", ""
            return rule["outcome"], f"authority rule {rule['name']!r} on {target}: {rule['why']}"
        outcome = self.authority[contract["authority_class"]]
        if outcome == "approval_required" and {"capability": capability, "target": None} in facts["approvals"]:
            outcome = "allow"
        return outcome, "" if outcome == "allow" else f"authority class {contract['authority_class']!r}"
