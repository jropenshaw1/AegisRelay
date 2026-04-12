"""Governance audit event (LENS + pipeline stages)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GovernanceEvent(BaseModel):
    """Row aligned with `governance_events` — metadata holds LENS observation payload."""

    model_config = {"extra": "forbid"}

    event_id: str
    relay_id: str
    event_type: str
    stage: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
