"""Governed memory unit persisted after the pipeline (ADR-003)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """Retrievable memory row aligned with `memory_records` table."""

    model_config = {"extra": "forbid"}

    memory_id: str
    relay_id: str
    body_text: str
    content_hash: str
    trust_tier: Optional[str] = None
    temporal_scope: Optional[str] = None
    expires_at: Optional[datetime] = None
    embedding_status: str = Field(default="pending")
    schema_version: str = Field(default="1.0")
