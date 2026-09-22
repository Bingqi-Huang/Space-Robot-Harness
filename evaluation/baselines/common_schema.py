"""Common trace-event schema for §14.6 "trace completeness" across methods.

§14.6: "For PLEXIL/EUROPA baselines, store the analogous plan node/token/activity
identifiers so failure analysis remains comparable." One event shape, method-neutral
fields plus one identifier field per method's own unit of execution:
`plan_node_id` (PLEXIL universalExec node name) and `token_id` (EUROPA -- schema slot
only, no EUROPA baseline exists yet to populate it from; see module docstring in
`evaluation/baselines/plexil_normalize.py`).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

__all__ = ["CommonEvent"]


class CommonEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: Literal["plan_started", "plan_finished", "execution_started", "execution_finished"]
    seq: int
    t: float
    method: Literal["plexil", "europa_plexil"]
    capability: str | None = None
    plan_node_id: str | None = None  # PLEXIL universalExec node name, when the source line names one
    token_id: str | None = None  # EUROPA schema slot -- never populated (no EUROPA baseline built yet)
    success: bool | None = None
    failure_reason: str | None = None
    args: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
