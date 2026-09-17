"""The thin invariant / authority guard (execution_plan §4.3) at Ours' effectful dispatch.

Checks only explicit execution boundaries: the capability exists and the arguments match its contract, it is not
hard-unavailable, its authority class permits it (or an operator approval is on record), no active fault prohibits it,
and no configured hard invariant is violated. Outcomes: allow | deny | approval_required | unavailable, each with a
structured reason that goes back to the agent as context. It never judges whether a call is a good next step.
"""
from openral_ext.capability_server.contracts import CONTRACTS, check_args


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
        outcome = self.authority[contract["authority_class"]]
        if outcome == "approval_required" and capability in facts["approvals"]:
            outcome = "allow"
        return outcome, "" if outcome == "allow" else f"authority class {contract['authority_class']!r}"
