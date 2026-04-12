"""Pydantic models — Phase 2 extensions."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aegisrelay.models import (
    CanonicalRelayRequest,
    CanonicalRelayResponse,
    GovernanceEvent,
    MemoryRecord,
    RelayAuditBundle,
    RelaySummary,
)


def test_canonical_relay_response_roundtrip() -> None:
    t0 = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 1, 12, 0, 5, tzinfo=timezone.utc)
    r = CanonicalRelayResponse(
        relay_id="r1",
        provider_name="p",
        provider_model="m",
        response_text="hello",
        provider_request_ts=t0,
        provider_response_ts=t1,
    )
    restored = CanonicalRelayResponse.model_validate_json(r.model_dump_json())
    assert restored == r


def test_memory_record_defaults() -> None:
    m = MemoryRecord(
        memory_id="m1",
        relay_id="r1",
        body_text="x",
        content_hash="abc",
    )
    assert m.embedding_status == "pending"
    assert m.schema_version == "1.0"


def test_governance_event_metadata_dict() -> None:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ge = GovernanceEvent(
        event_id="e1",
        relay_id="r1",
        event_type="lens_observation",
        stage="pre_call",
        metadata={"behavior": "decision_checkpoints", "trigger_fired": True},
        created_at=ts,
    )
    assert ge.metadata["behavior"] == "decision_checkpoints"


def test_relay_audit_bundle_empty_lists() -> None:
    req = CanonicalRelayRequest(input_text="hi")
    b = RelayAuditBundle(request=req)
    assert b.response is None
    assert b.memory_records == []
    assert b.governance_events == []


def test_relay_summary_fields() -> None:
    s = RelaySummary(
        relay_id="r",
        human_actor_id="a",
        provider_name="p",
        provider_model="m",
        submitted_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
        status="complete",
        operation="read",
    )
    assert s.status == "complete"


def test_governance_event_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        GovernanceEvent.model_validate(
            {
                "event_id": "e",
                "relay_id": "r",
                "event_type": "t",
                "stage": "s",
                "metadata": {},
                "created_at": datetime.now(timezone.utc),
                "unexpected": True,
            }
        )
