"""Canonical ingress and post-adapter contracts (ADR-003)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class CanonicalRelayRequest(BaseModel):
    """Inbound relay intent — pre-provider call."""

    model_config = {"extra": "forbid"}

    input_text: str = Field(..., min_length=1, description="Normalized user/provider-bound prompt text.")
    operation: Literal["read", "write", "unknown"] = Field(
        default="unknown",
        description="Structured hint for LENS pre-call; when unknown, heuristics inspect input_text.",
    )
    schema_version: str = Field(default="1.0", description="Contract version for safe evolution.")
    relay_id: str = Field(default_factory=lambda: str(uuid4()))
    human_actor_id: str = Field(default="anonymous")
    provider_name: str = Field(default="unknown")
    provider_model: str = Field(default="unknown")
    session_id: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_irreversible: Optional[bool] = None
    has_downstream_effects: Optional[bool] = Field(
        default=None,
        description="When True, Decision Checkpoints records explicit downstream/cascade risk.",
    )


class NormalizedProviderResponse(BaseModel):
    """Provider-normalized body **before** the eight-stage pipeline (ADR-009)."""

    model_config = {"extra": "forbid"}

    body_text: str = Field(..., description="Primary response text from the adapter.")
    schema_version: str = Field(default="1.0")


class CanonicalRelayResponse(BaseModel):
    """Post-adapter provider payload persisted before pipeline consumes normalized text."""

    model_config = {"extra": "forbid"}

    relay_id: str
    provider_name: str
    provider_model: str
    response_text: str
    provider_request_ts: datetime
    provider_response_ts: datetime
    schema_version: str = Field(default="1.0")
    raw_provider_response: Optional[dict[str, Any]] = None
