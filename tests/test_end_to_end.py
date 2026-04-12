"""End-to-end relay → persist → audit bundle."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from aegisrelay.adapters.base import ProviderAdapter
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse
from aegisrelay.relay_service import execute_relay


class _RichStubAdapter(ProviderAdapter):
    """Provider body that exercises pipeline Stage 3/4 LENS hooks."""

    async def send(self, request: CanonicalRelayRequest) -> NormalizedProviderResponse:
        return NormalizedProviderResponse(
            body_text=(
                "From a technical perspective the policy allows it. "
                "Alternatively the security team could disagree. "
                "This probably applies to most tenants."
            )
        )


def test_execute_relay_returns_full_audit_trail(crud) -> None:
    req = CanonicalRelayRequest(
        relay_id="e2e-1",
        input_text="Explain the latest policy change.",
        operation="read",
        human_actor_id="actor-e2e",
        provider_name="stub",
        provider_model="test",
        submitted_at=datetime(2026, 4, 11, 14, 0, tzinfo=timezone.utc),
    )
    bundle = asyncio.run(execute_relay(req, _RichStubAdapter(), crud))
    assert bundle.request.relay_id == "e2e-1"
    assert bundle.response is not None
    assert "technical perspective" in bundle.response.response_text
    assert len(bundle.memory_records) >= 1
    pipeline_stages = [e for e in bundle.governance_events if e.event_type == "pipeline_stage"]
    assert len(pipeline_stages) >= 1
    lens_pipeline = [
        e
        for e in bundle.governance_events
        if e.event_type == "lens_observation" and e.stage.startswith("pipeline_stage")
    ]
    assert len(lens_pipeline) >= 1
