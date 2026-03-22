"""Canonical ingress contracts (Phase 1).

`NormalizedProviderResponse` is the adapter output **before** the governance pipeline
(ADR-009 post-call hook). `CanonicalRelayResponse` (post-pipeline) is deferred to Phase 2.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CanonicalRelayRequest(BaseModel):
    """Inbound relay intent — pre-provider call (ADR-003 subset for Phase 1)."""

    model_config = {"extra": "forbid"}

    input_text: str = Field(..., min_length=1, description="Normalized user/provider-bound prompt text.")
    operation: Literal["read", "write", "unknown"] = Field(
        default="unknown",
        description="Structured hint for LENS pre-call; when unknown, heuristics inspect input_text.",
    )
    schema_version: str = Field(default="1.0", description="Contract version for safe evolution.")


class NormalizedProviderResponse(BaseModel):
    """Provider-normalized body **before** the eight-stage pipeline (ADR-009)."""

    model_config = {"extra": "forbid"}

    body_text: str = Field(..., description="Primary response text from the adapter.")
    schema_version: str = Field(default="1.0")
