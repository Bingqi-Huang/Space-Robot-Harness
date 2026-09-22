"""Scenario manifest / certificate schema -- execution_plan.md §12, §13.2.

Loads and minimally validates `experiments/scenarios/**/*.yaml` (every §12 field
present) and `*.certificate.yaml` (the four-item closed-capability checklist). No
mission-specific logic here -- same pattern as `openral_ext.mission_verifier.schemas`
and `openral_ext.run_manifest.schemas` (a small Pydantic model, nothing more).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, ConfigDict

__all__ = ["ScenarioManifest", "ClosedCapabilityCertificate", "load_manifest", "load_certificate", "iter_manifests"]


class EvidenceVerifierMapping(BaseModel):
    model_config = ConfigDict(extra="allow")  # per-instance diagnostic fields vary (e.g. diagnostic_note)

    source_topic: str
    evaluator_only: bool
    success_condition: str
    fields_used: list[str]


class ScenarioManifest(BaseModel):
    """One §12 scenario instance. `extra='allow'`: `simulator`/`notes`/`held_out_basis` carry
    per-instance detail that has no fixed shape across missions -- §12 lists what must be
    present, not a closed schema for every nested block."""

    model_config = ConfigDict(extra="allow")

    manifest_version: int
    scenario_id: str
    mission_family: str
    coverage: Literal["covered", "held_out"]
    mission_brief: str
    simulator: dict[str, Any]
    required_capabilities: list[str]
    mission_deadline_s: float | None
    space_context_profile: str | None
    perturbations_semantic_conditions: list[str]
    evidence_verifier_mapping: EvidenceVerifierMapping


class ChecklistItem(BaseModel):
    status: Literal["OPEN", "CONFIRMED"]
    note: str


class ClosedCapabilityCertificate(BaseModel):
    """§13.2 four-bullet checklist. `solution_sequence` must stay null -- this file is
    evaluator-only and the solution is never written down, even here."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    checklist: dict[str, ChecklistItem]
    evaluator_only: bool
    solution_sequence: None = None

    REQUIRED_ITEMS: ClassVar[frozenset[str]] = frozenset((
        "valid_solution_with_only_pre_freeze_capabilities",
        "required_observation_available_via_shared_perception",
        "no_scenario_specific_solution_in_method_artifacts",
        "baseline_missing_knowledge_is_mission_level_not_controller_sensor",
    ))


def load_manifest(path: Path) -> ScenarioManifest:
    return ScenarioManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_certificate(path: Path) -> ClosedCapabilityCertificate:
    cert = ClosedCapabilityCertificate.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    missing = ClosedCapabilityCertificate.REQUIRED_ITEMS - cert.checklist.keys()
    if missing:
        msg = f"{path}: certificate missing checklist items {sorted(missing)}"
        raise ValueError(msg)
    return cert


def iter_manifests(scenarios_dir: Path):
    """Yield (manifest_path, ScenarioManifest) for every scenario YAML under `scenarios_dir`
    (skips `*.certificate.yaml` and `README.md`)."""
    for path in sorted(scenarios_dir.glob("*/*/*.yaml")):
        if path.name.endswith(".certificate.yaml"):
            continue
        yield path, load_manifest(path)
