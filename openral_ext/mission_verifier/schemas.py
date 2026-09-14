"""Typed verifier event -- execution_plan.md §4.4 "Independent effect verification".

§4.4 specifies the verifier's output shape directly (physical condition/
effect result; evidence source/reference; timestamp/state version;
confidence/quality metadata) and its scope (answer *effect* questions --
"object moved?", "goal reached?" -- never *strategy* questions). This module
is that shape as a Pydantic model, nothing more: no mission-specific
if/then logic lives here (that would violate §8.2's "forbidden mission
logic" rule), only the generic event envelope. `panel_remount_logic.py`
holds the one task's actual condition-detection code.

Deliberately NOT placed in `openral_core.schemas`: that module's own
`*Evidence` family (`TimeoutEvidence`, `ForceEvidence`, ...) is a different,
narrower concept -- diagnosis for OpenRAL's replanning ladder after a
*failure*, keyed by `FailureEvidenceKind`. A verifier event is not a
failure signal; forcing "panel placed within tolerance" through that union
would be a semantic misfit. Per execution_plan.md's own dividing rule
("if OpenRAL or SRB would plausibly accept it upstream as a generic
feature, it goes on a fork branch; if it only makes sense for this paper,
it goes here"), this is a new, paper-specific schema and belongs in
`openral_ext`, not upstream in the fork.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EffectCondition(str, Enum):
    """What physical condition this event reports on.

    Deliberately task-agnostic names (not "panel_placed") so the envelope
    stays reusable if a second task is added later; the task-specific
    mapping (which condition means what for `panel_remount`) lives in
    `panel_remount_logic.py`, not here.
    """

    OBJECT_DISPLACED = "object_displaced"  # object moved from its rest pose
    OBJECT_AT_TARGET = "object_at_target"  # object within a target pose tolerance
    EPISODE_TERMINATED = "episode_terminated"  # the task's own self-reported terminal state


class EvidenceSource(str, Enum):
    """Where the verifier's judgment came from -- §4.4's "evidence source/reference".

    `SIMULATOR_TRUTH` and `TASK_SELF_REPORT` are both explicitly allowed
    verifier inputs per §4.4's list ("deterministic simulator truth for
    evaluation/verification" / "rSkill/action results" ... "task-progress/
    reward signals where they correspond to observable physical
    conditions") -- the independence this verifier provides is that its own
    primary judgment (`OBJECT_AT_TARGET`) is computed from `SIMULATOR_TRUTH`
    (raw `/tf`) and only *cross-checked* against `TASK_SELF_REPORT`
    (`/srb/env0/terminated`), never the other way around.
    """

    SIMULATOR_TRUTH = "simulator_truth"  # raw /tf pose, read directly, not via the task's own reward math
    TASK_SELF_REPORT = "task_self_report"  # the task's own /srb/env0/{terminated,reward/*} topics


class VerifierEvent(BaseModel):
    """One independently-verified physical effect, per execution_plan.md §4.4.

    Attributes:
        condition: Which physical condition this reports on.
        holds: Whether the condition currently holds (True/False), independent
            of any strategy judgment about whether that was the *right* thing
            to have happened.
        evidence_source: What kind of evidence backs this judgment.
        evidence_ref: A concrete pointer into that evidence -- e.g. the TF
            frame pair looked up (`"srb/env0 -> srb/env0/panel"`) or the topic
            read (`"/srb/env0/terminated"`) -- so the judgment is traceable,
            not just asserted.
        stamp_ns: Wall-clock or sim-clock nanoseconds the evidence was
            captured at (from the source message's own header stamp, not
            `time.time()` at publish time).
        state_version: Monotonically increasing counter, one per verifier
            tick, so a consumer can tell "this is a newer judgment than the
            last one" without comparing timestamps (sim time can repeat/jump
            across resets).
        confidence: 0..1. For a TF-pose-derived judgment this is the margin
            relative to the tolerance actually used (1.0 = exactly at the
            target, 0.0 = exactly at the tolerance boundary), not an
            invented number -- see `panel_remount_logic.py`.
        detail: Free-form, human-readable evidence detail (e.g. the measured
            distance and tolerance), never a substitute for `evidence_ref`.

    Example:
        >>> ev = VerifierEvent(
        ...     condition=EffectCondition.OBJECT_AT_TARGET,
        ...     holds=True,
        ...     evidence_source=EvidenceSource.SIMULATOR_TRUTH,
        ...     evidence_ref="srb/env0 -> srb/env0/panel",
        ...     stamp_ns=1_726_300_000_000_000_000,
        ...     state_version=42,
        ...     confidence=0.87,
        ...     detail="dist_to_target=0.013m (tol=0.1m), rot_cos_half=0.998 (tol=0.9)",
        ... )
        >>> ev.holds
        True
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition: EffectCondition
    holds: bool
    evidence_source: EvidenceSource
    evidence_ref: str
    stamp_ns: int = Field(ge=0)
    state_version: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    detail: str = ""
