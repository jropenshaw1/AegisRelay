"""Eight-stage pipeline — stage behavior and LENS hooks."""

from __future__ import annotations

from datetime import datetime, timezone

from aegisrelay.governance.pipeline import run_eight_stage_pipeline
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse


def _req(rid: str = "relay-pipe-test") -> CanonicalRelayRequest:
    return CanonicalRelayRequest(
        relay_id=rid,
        input_text="test",
        operation="read",
        submitted_at=datetime(2026, 4, 11, 10, 0, 0, tzinfo=timezone.utc),
    )


def test_pipeline_normalize_and_segment_events() -> None:
    t0 = datetime(2026, 4, 11, 10, 0, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 11, 10, 0, 2, tzinfo=timezone.utc)
    req = _req()
    norm = NormalizedProviderResponse(body_text="Alpha.\n\nBeta.")
    art = run_eight_stage_pipeline(req.relay_id, req, norm, t0, t1)
    stages = {e.stage for e in art.governance_events}
    assert "pipeline_stage_1" in stages
    assert "pipeline_stage_2" in stages
    assert len(art.memory_records) == 2


def test_pipeline_cognitive_model_disclosure_fires() -> None:
    t0 = datetime(2026, 4, 11, 10, 0, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 11, 10, 0, 2, tzinfo=timezone.utc)
    req = _req("relay-cog")
    body = (
        "From a technical perspective the API is stable. "
        "Alternatively you could view latency as the bottleneck."
    )
    norm = NormalizedProviderResponse(body_text=body)
    art = run_eight_stage_pipeline(req.relay_id, req, norm, t0, t1)
    lens = [e for e in art.governance_events if e.metadata.get("behavior") == "cognitive_model_disclosure"]
    assert len(lens) == 1
    assert lens[0].stage == "pipeline_stage_3"
    assert lens[0].metadata.get("trigger_fired") is True


def test_pipeline_uncertainty_flagging_fires() -> None:
    t0 = datetime(2026, 4, 11, 10, 0, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 11, 10, 0, 2, tzinfo=timezone.utc)
    req = _req("relay-unc")
    body = "This probably works fine for most cases."
    norm = NormalizedProviderResponse(body_text=body)
    art = run_eight_stage_pipeline(req.relay_id, req, norm, t0, t1)
    lens = [e for e in art.governance_events if e.metadata.get("behavior") == "uncertainty_flagging"]
    assert len(lens) >= 1
    assert lens[0].metadata.get("violation") is True


def test_pipeline_dedupe_skips_duplicate_segments() -> None:
    t0 = datetime(2026, 4, 11, 10, 0, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 11, 10, 0, 2, tzinfo=timezone.utc)
    req = _req("relay-dedupe")
    norm = NormalizedProviderResponse(body_text="Same.\n\nSame.\n\nSame.")
    art = run_eight_stage_pipeline(req.relay_id, req, norm, t0, t1)
    assert len(art.memory_records) == 1
    skips = [e for e in art.governance_events if e.metadata.get("skipped") is True]
    assert len(skips) >= 2
