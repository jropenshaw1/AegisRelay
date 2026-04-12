"""Deterministic adapter for tests and offline demos."""

from __future__ import annotations

from aegisrelay.adapters.base import ProviderAdapter
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse


class StubAdapter(ProviderAdapter):
    async def send(self, request: CanonicalRelayRequest) -> NormalizedProviderResponse:
        body = f"Stub response for relay {request.relay_id}: {request.input_text.strip()}"
        return NormalizedProviderResponse(body_text=body, schema_version="1.0")
