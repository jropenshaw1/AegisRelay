"""Provider adapter boundary (ADR-009)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse


class ProviderAdapter(ABC):
    """Translate a canonical relay request into a normalized provider body."""

    @abstractmethod
    async def send(self, request: CanonicalRelayRequest) -> NormalizedProviderResponse:
        """Invoke the provider and return text before the governance pipeline."""
