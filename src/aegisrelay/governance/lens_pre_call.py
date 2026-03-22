"""
LENS pre-call hook — Decision Checkpoints and Assumption Surfacing.

Returns **only observations where a trigger matched** (sparse list), per
`03_Integration_Design_v1.0.md`. Confidence is a capped heuristic score, not a probability.
"""

from __future__ import annotations

import re

from aegisrelay.governance import lens_constants as C
from aegisrelay.models.contracts import CanonicalRelayRequest
from aegisrelay.models.lens import LensObservation

# Irreversible / commit verbs — word-boundary match, case-insensitive.
_IRREVERSIBLE_PATTERN = re.compile(
    r"\b(delete|publish|send|commit|remove|drop|erase|destroy)\b",
    re.IGNORECASE,
)
_CASCADE_PATTERN = re.compile(
    r"\b(cascade|downstream|bulk\s+update|all\s+rows|every\s+record)\b",
    re.IGNORECASE,
)
_AMBIGUOUS_SCOPE_PATTERN = re.compile(
    r"\b(any|either|or\s+else|multiple|unspecified|unclear\s+which)\b",
    re.IGNORECASE,
)


def _heuristic_confidence(signal_count: int) -> float:
    base = 0.5
    step = 0.18
    return min(1.0, base + step * max(signal_count, 1))


def evaluate_pre_call(request: CanonicalRelayRequest) -> list[LensObservation]:
    """
    Evaluate Decision Checkpoints and Assumption Surfacing before provider invocation.
    Returns observations only for behaviors whose triggers fired.
    """
    text = request.input_text.strip()
    lower = text.lower()
    out: list[LensObservation] = []

    # --- Decision checkpoints ---
    dc_signals: list[str] = []
    if request.operation == "write":
        dc_signals.append(C.SIGNAL_WRITE_OP)
    if _IRREVERSIBLE_PATTERN.search(text):
        dc_signals.append(C.SIGNAL_IRREVERSIBLE)
    if _CASCADE_PATTERN.search(text):
        dc_signals.append(C.SIGNAL_CASCADE)

    if dc_signals:
        out.append(
            LensObservation(
                behavior="decision_checkpoints",
                trigger_fired=True,
                confidence=_heuristic_confidence(len(dc_signals)),
                observation=(
                    "Request suggests a write, irreversible action, or downstream cascade "
                    "warrants a decision checkpoint before provider execution."
                ),
                hook="pre_call",
                lens_version=C.LENS_VERSION,
                matched_signals=dc_signals,
            )
        )

    # --- Assumption surfacing ---
    as_signals: list[str] = []
    if _AMBIGUOUS_SCOPE_PATTERN.search(text):
        as_signals.append(C.SIGNAL_AMBIGUOUS_SCOPE)
    # Very short prompt with a pronoun — possible missing referent
    if len(text) < 80 and re.search(r"\b(it|them|this|that)\b", lower):
        as_signals.append("pattern:short_prompt_with_pronoun")

    if as_signals:
        out.append(
            LensObservation(
                behavior="assumption_surfacing",
                trigger_fired=True,
                confidence=_heuristic_confidence(len(as_signals)),
                observation=(
                    "Request may rely on unstated scope, targets, or context that could "
                    "materially change the provider's interpretation."
                ),
                hook="pre_call",
                lens_version=C.LENS_VERSION,
                matched_signals=as_signals,
            )
        )

    return out
