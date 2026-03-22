"""
LENS post-call hook — Prompt Reflection and Reframe Offers.

Runs after the provider adapter and **before** the governance pipeline (ADR-009).
Input response type is `NormalizedProviderResponse`, not post-pipeline `CanonicalRelayResponse`.
"""

from __future__ import annotations

import re

from aegisrelay.governance import lens_constants as C
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse
from aegisrelay.models.lens import LensObservation

_REFLECTION_PATTERN = re.compile(
    r"\b("
    r"i\s+assumed|"
    r"interpreting\s+this\s+as|"
    r"based\s+on\s+my\s+understanding|"
    r"i('m|\s+am)\s+reading\s+this"
    r")\b",
    re.IGNORECASE,
)
_REFRAME_PATTERN = re.compile(
    r"\b("
    r"you\s+might\s+(also|instead)\s+want\s+to\s+ask|"
    r"a\s+better\s+question\s+(might|would)\s+be|"
    r"consider\s+reframing|"
    r"the\s+underlying\s+question"
    r")\b",
    re.IGNORECASE,
)


def _heuristic_confidence(signal_count: int) -> float:
    base = 0.5
    step = 0.2
    return min(1.0, base + step * max(signal_count, 1))


def evaluate_post_call(
    request: CanonicalRelayRequest,
    response: NormalizedProviderResponse,
) -> list[LensObservation]:
    """
    Evaluate Prompt Reflection and Reframe Offers on the completed exchange.
    Returns observations only for behaviors whose triggers fired.
    """
    body = response.body_text.strip()
    out: list[LensObservation] = []

    pr_signals: list[str] = []
    if _REFLECTION_PATTERN.search(body):
        pr_signals.append(C.SIGNAL_REFLECTION_PHRASE)
    # Response explicitly narrows or widens scope vs a detailed request
    if len(request.input_text) > 120 and len(body) < 40:
        pr_signals.append("pattern:response_much_shorter_than_request")

    if pr_signals:
        out.append(
            LensObservation(
                behavior="prompt_reflection",
                trigger_fired=True,
                confidence=_heuristic_confidence(len(pr_signals)),
                observation=(
                    "Response signals interpretation choices or a scope shift relative to the request."
                ),
                hook="post_call",
                lens_version=C.LENS_VERSION,
                matched_signals=pr_signals,
            )
        )

    rf_signals: list[str] = []
    if _REFRAME_PATTERN.search(body):
        rf_signals.append(C.SIGNAL_REFRAME_PHRASE)

    if rf_signals:
        out.append(
            LensObservation(
                behavior="reframe_offers",
                trigger_fired=True,
                confidence=_heuristic_confidence(len(rf_signals)),
                observation="Response suggests the stated question may not match the underlying need.",
                hook="post_call",
                lens_version=C.LENS_VERSION,
                matched_signals=rf_signals,
            )
        )

    return out
