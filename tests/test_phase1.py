"""Phase 1 — LENS hooks, contracts, and constants (14 tests)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aegisrelay.governance.lens_constants import (
    LENS_BEHAVIORS,
    LENS_SOURCE_TAG,
    LENS_TAG_PREFIX,
    LENS_VERSION,
)
from aegisrelay.governance.lens_post_call import evaluate_post_call
from aegisrelay.governance.lens_pre_call import evaluate_pre_call
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse
from aegisrelay.models.lens import LensObservation


def test_lens_version_and_tags_are_stable_strings() -> None:
    assert LENS_VERSION == "1.0"
    assert LENS_TAG_PREFIX == "lens"
    assert LENS_SOURCE_TAG == "[source:lens]"


def test_lens_behaviors_registry_covers_all_six_behaviors() -> None:
    assert set(LENS_BEHAVIORS) == {
        "decision_checkpoints",
        "assumption_surfacing",
        "prompt_reflection",
        "reframe_offers",
        "uncertainty_flagging",
        "cognitive_model_disclosure",
    }
    for meta in LENS_BEHAVIORS.values():
        assert "hook" in meta and "required" in meta and "violation_on" in meta


def test_lens_observation_rejects_confidence_above_one() -> None:
    with pytest.raises(ValidationError):
        LensObservation(
            behavior="decision_checkpoints",
            trigger_fired=True,
            confidence=1.01,
            observation="x",
            hook="pre_call",
            lens_version=LENS_VERSION,
        )


def test_lens_observation_rejects_confidence_below_zero() -> None:
    with pytest.raises(ValidationError):
        LensObservation(
            behavior="prompt_reflection",
            trigger_fired=True,
            confidence=-0.01,
            observation="x",
            hook="post_call",
            lens_version=LENS_VERSION,
        )


def test_evaluate_pre_call_returns_empty_for_benign_read() -> None:
    req = CanonicalRelayRequest(input_text="What is the capital of France?", operation="read")
    assert evaluate_pre_call(req) == []


def test_evaluate_pre_call_fires_decision_checkpoint_on_write_operation() -> None:
    req = CanonicalRelayRequest(input_text="List open issues.", operation="write")
    obs = evaluate_pre_call(req)
    assert len(obs) == 1
    assert obs[0].behavior == "decision_checkpoints"
    assert obs[0].hook == "pre_call"
    assert "operation:write" in obs[0].matched_signals


def test_evaluate_pre_call_fires_decision_checkpoint_on_irreversible_keyword() -> None:
    req = CanonicalRelayRequest(
        input_text="Please delete all temporary files when done.",
        operation="read",
    )
    obs = evaluate_pre_call(req)
    behaviors = {o.behavior for o in obs}
    assert "decision_checkpoints" in behaviors
    dc = next(o for o in obs if o.behavior == "decision_checkpoints")
    assert any("irreversible" in s for s in dc.matched_signals)


def test_evaluate_pre_call_fires_assumption_surfacing_on_ambiguous_scope() -> None:
    req = CanonicalRelayRequest(
        input_text="Update either the primary or the backup — unspecified which.",
        operation="read",
    )
    obs = evaluate_pre_call(req)
    behaviors = {o.behavior for o in obs}
    assert "assumption_surfacing" in behaviors


def test_evaluate_pre_call_fires_decision_checkpoint_on_cascade_language() -> None:
    req = CanonicalRelayRequest(
        input_text="Propagate this change downstream to every consumer service.",
        operation="read",
    )
    obs = evaluate_pre_call(req)
    assert any(o.behavior == "decision_checkpoints" for o in obs)
    dc = next(o for o in obs if o.behavior == "decision_checkpoints")
    assert any("cascade" in s for s in dc.matched_signals)


def test_evaluate_pre_call_fires_on_explicit_has_downstream_effects() -> None:
    req = CanonicalRelayRequest(
        input_text="Apply a small configuration tweak.",
        operation="read",
        has_downstream_effects=True,
    )
    obs = evaluate_pre_call(req)
    assert any(o.behavior == "decision_checkpoints" for o in obs)
    dc = next(o for o in obs if o.behavior == "decision_checkpoints")
    assert "explicit:has_downstream_effects" in dc.matched_signals


def test_evaluate_post_call_returns_empty_for_plain_completion() -> None:
    req = CanonicalRelayRequest(input_text="2+2?", operation="read")
    resp = NormalizedProviderResponse(body_text="4")
    assert evaluate_post_call(req, resp) == []


def test_evaluate_post_call_fires_prompt_reflection_on_disclosed_interpretation() -> None:
    req = CanonicalRelayRequest(input_text="Summarize the attached policy.", operation="read")
    resp = NormalizedProviderResponse(
        body_text="Interpreting this as the 2024 IT policy, the key points are …",
    )
    obs = evaluate_post_call(req, resp)
    assert len(obs) >= 1
    pr = next(o for o in obs if o.behavior == "prompt_reflection")
    assert pr.hook == "post_call"
    assert any("phrase:interpretation_disclosed" in s for s in pr.matched_signals)


def test_evaluate_post_call_fires_reframe_offer_on_suggestion_phrase() -> None:
    req = CanonicalRelayRequest(input_text="How do I tune this query?", operation="read")
    resp = NormalizedProviderResponse(
        body_text="You might also want to ask whether indexes cover the filter columns.",
    )
    obs = evaluate_post_call(req, resp)
    behaviors = {o.behavior for o in obs}
    assert "reframe_offers" in behaviors


def test_canonical_relay_request_json_roundtrip() -> None:
    req = CanonicalRelayRequest(input_text="hello", operation="unknown")
    restored = CanonicalRelayRequest.model_validate_json(req.model_dump_json())
    assert restored == req


def test_normalized_provider_response_json_roundtrip() -> None:
    resp = NormalizedProviderResponse(body_text="ok")
    restored = NormalizedProviderResponse.model_validate_json(resp.model_dump_json())
    assert restored == resp
