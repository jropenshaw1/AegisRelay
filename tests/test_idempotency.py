"""Idempotency — deterministic pipeline and duplicate memory inserts."""

from __future__ import annotations

from datetime import datetime, timezone

from aegisrelay.admin.crud_service import CrudService
from aegisrelay.governance.pipeline import pipeline_artifacts_fingerprint, run_eight_stage_pipeline
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse
from aegisrelay.models.memory_record import MemoryRecord


def test_pipeline_fingerprint_stable_across_runs() -> None:
    t0 = datetime(2026, 4, 11, 10, 0, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 4, 11, 10, 0, 2, tzinfo=timezone.utc)
    req = CanonicalRelayRequest(
        relay_id="idem-relay",
        input_text="q",
        submitted_at=datetime(2026, 4, 11, 10, 0, 0, tzinfo=timezone.utc),
    )
    norm = NormalizedProviderResponse(body_text="Stable body for hashing.")
    a1 = run_eight_stage_pipeline(req.relay_id, req, norm, t0, t1)
    a2 = run_eight_stage_pipeline(req.relay_id, req, norm, t0, t1)
    assert pipeline_artifacts_fingerprint(a1) == pipeline_artifacts_fingerprint(a2)
    assert a1.memory_records[0].content_hash == a2.memory_records[0].content_hash


def test_insert_memory_twice_no_duplicate_row(crud: CrudService, sqlite_db) -> None:
    req = CanonicalRelayRequest(
        relay_id="idem-db",
        input_text="x",
        submitted_at=datetime(2026, 4, 11, 11, 0, tzinfo=timezone.utc),
    )
    crud.create_relay(req, [])
    mem = MemoryRecord(
        memory_id="mid-fixed",
        relay_id="idem-db",
        body_text="body",
        content_hash="deadbeef",
    )
    crud.insert_memory_record_idempotent(mem)
    crud.insert_memory_record_idempotent(mem)
    cur = sqlite_db.execute(
        "SELECT COUNT(*) AS c FROM memory_records WHERE relay_id = :r",
        {"r": "idem-db"},
    )
    assert cur.fetchone()["c"] == 1
