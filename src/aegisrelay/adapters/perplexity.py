"""Perplexity / Sonar adapter — API key via `SecretsProvider`; stubs when unset."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from aegisrelay.adapters.base import ProviderAdapter
from aegisrelay.config.secrets import SecretsProvider
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse


class PerplexityAdapter(ProviderAdapter):
    """Calls api.perplexity.ai when `PERPLEXITY_API_KEY` is available."""

    def __init__(self, secrets: SecretsProvider, model: str = "sonar-pro") -> None:
        self._secrets = secrets
        self._model = model

    async def send(self, request: CanonicalRelayRequest) -> NormalizedProviderResponse:
        try:
            api_key = self._secrets.get("PERPLEXITY_API_KEY")
        except KeyError:
            return NormalizedProviderResponse(
                body_text=(
                    f"[perplexity stub — set PERPLEXITY_API_KEY] Echo: {request.input_text.strip()[:2000]}"
                ),
                schema_version="1.0",
            )

        payload = json.dumps(
            {
                "model": self._model,
                "messages": [{"role": "user", "content": request.input_text}],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.perplexity.ai/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return NormalizedProviderResponse(
                body_text="[perplexity error — falling back to stub] Provider call failed.",
                schema_version="1.0",
            )

        try:
            text = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            text = json.dumps(raw)[:8000]
        return NormalizedProviderResponse(body_text=str(text), schema_version="1.0")
