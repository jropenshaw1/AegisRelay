"""Outbox rows and embedding worker."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from aegisrelay.adapters.stub import StubAdapter
from aegisrelay.admin.crud_service import CrudService
from aegisrelay.relay_service import execute_relay
from aegisrelay.workers.embedding_worker import process_one_embedding_job
from aegisrelay.workers.ob_sync_worker import process_one_ob_sync_job

from aegisrelay.models.contracts import CanonicalRelayRequest


def test_outbox_populated_after_relay(crud: CrudService, sqlite_db) -> None:
    req = CanonicalRelayRequest(
        relay_id="obx-1",
        input_text="Short prompt",
        operation="read",
        submitted_at=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
    )
    asyncio.run(execute_relay(req, StubAdapter(), crud))
    cur = sqlite_db.execute(
        "SELECT COUNT(*) AS c FROM outbox WHERE relay_id = :r",
        {"r": "obx-1"},
    )
    assert cur.fetchone()["c"] >= 2


def test_embedding_worker_marks_memory_complete(crud: CrudService, sqlite_db) -> None:
    req = CanonicalRelayRequest(
        relay_id="obx-emb",
        input_text="Another",
        operation="read",
        submitted_at=datetime(2026, 4, 11, 12, 30, tzinfo=timezone.utc),
    )
    asyncio.run(execute_relay(req, StubAdapter(), crud))
    for _ in range(16):
        if not process_one_embedding_job(sqlite_db):
            break
    cur = sqlite_db.execute(
        "SELECT embedding_status FROM memory_records WHERE relay_id = :r LIMIT 1",
        {"r": "obx-emb"},
    )
    row = cur.fetchone()
    assert row is not None
    assert row["embedding_status"] == "complete"


def test_ob_sync_runs_after_embedding(crud: CrudService, sqlite_db) -> None:
    req = CanonicalRelayRequest(
        relay_id="obx-sync",
        input_text="Sync test",
        operation="read",
        submitted_at=datetime(2026, 4, 11, 13, 0, tzinfo=timezone.utc),
    )
    asyncio.run(execute_relay(req, StubAdapter(), crud))
    for _ in range(32):
        process_one_embedding_job(sqlite_db)
    for _ in range(32):
        if not process_one_ob_sync_job(sqlite_db):
            continue
    cur = sqlite_db.execute(
        "SELECT COUNT(*) AS c FROM outbox WHERE relay_id = :r AND status = 'complete'",
        {"r": "obx-sync"},
    )
    assert cur.fetchone()["c"] >= 1
