"""Ours-internal ablations (research_content §5.7, execution_plan §9.7, research repo F148): one harness component
removed at a time, everything else as frozen for Experiment I (tag exp1b). `OURS_ABLATION` names the variant; unset is
the full method, byte for byte.

  no_facts         no authoritative fact record in what the model reads: its own working plan (the tasks it wrote and
                   closed itself) and its last steps' results -- each with the verification of its effect -- are the
                   state; nothing accumulates verified effects, item locations, attempts or unresolved anomalies
  no_verification  the effect of a call is the skill's own success flag; no measurement, no look at a carried item
  no_guard         nothing checks a call before it runs; the authority rules stay in the standing text, and an
                   authorization request names the call it asks for (mission control decides it by the same table)
  no_context       no context rebuilt from the record: the model reads one accumulating conversation -- its calls and
                   each call's result as it came -- and a new reasoner session starts from the mission alone

Every text a variant changes is a copy under prompts/ours_ablation/<variant>/ (the diff is the whole change); the rest
is read from prompts/ours/. A variant adds or removes no mission knowledge.
"""
import os
from pathlib import Path

VARIANTS = ("no_facts", "no_verification", "no_guard", "no_context")
VARIANT = os.environ.get("OURS_ABLATION") or None
assert VARIANT in (None, *VARIANTS), f"OURS_ABLATION={VARIANT!r}: not one of {VARIANTS}"

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def prompt(name: str) -> Path:
    """The variant's own copy of a prompt file when it has one, else the full method's."""
    own = PROMPTS / "ours_ablation" / str(VARIANT) / name
    return own if VARIANT and own.exists() else PROMPTS / "ours" / name
