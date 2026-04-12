"""Full relay retrieval types for CRUD / portfolio audit."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from aegisrelay.models.contracts import CanonicalRelayRequest, CanonicalRelayResponse
from aegisrelay.models.governance_event import GovernanceEvent
from aegisrelay.models.memory_record import MemoryRecord


class RelayAuditBundle(BaseModel):
    """Complete audit trail for one relay (request through governance)."""

    model_config = {"extra": "forbid"}

    request: CanonicalRelayRequest
    response: Optional[CanonicalRelayResponse] = None
    memory_records: list[MemoryRecord] = Field(default_factory=list)
    governance_events: list[GovernanceEvent] = Field(default_factory=list)


class RelaySummary(BaseModel):
    """Lightweight row for `list_relays`."""

    model_config = {"extra": "forbid"}

    relay_id: str
    human_actor_id: str
    provider_name: str
    provider_model: str
    submitted_at: datetime
    status: str
    operation: str
