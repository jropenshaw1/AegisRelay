"""LENS observation contract for governance_events metadata (Phase 1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LensBehaviorId = Literal[
    "decision_checkpoints",
    "assumption_surfacing",
    "prompt_reflection",
    "reframe_offers",
    "cognitive_model_disclosure",
    "uncertainty_flagging",
]

LensHookId = Literal["pre_call", "post_call"]


class LensObservation(BaseModel):
    """Single LENS evaluation result; side-effect free — caller persists to governance_events."""

    model_config = {"extra": "forbid"}

    behavior: LensBehaviorId
    trigger_fired: bool = Field(..., description="Whether the behavior's trigger condition matched.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Heuristic strength (not a calibrated probability); see module docstrings.",
    )
    observation: str = Field(..., min_length=1, description="One-sentence human-readable summary.")
    hook: LensHookId
    lens_version: str
    matched_signals: list[str] = Field(
        default_factory=list,
        description="Rule or keyword ids that contributed to the score (audit traceability).",
    )
