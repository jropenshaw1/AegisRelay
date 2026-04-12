"""Outbox retries, backoff metadata, and embedding failure paths."""

from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from aegisrelay.workers._outbox_util import embedding_backoff_seconds, in_backoff, mark_outbox_failure
from aegisrelay.workers.embedding_worker import process_one_embedding_job
from aegisrelay.workers.ob_sync_worker import _build_thought_metadata, _supabase_thoughts_url


def test_supabase_thoughts_rest_path() -> None:
    assert (
        _supabase_thoughts_url("https://blreixaevpbmhbhyqgbq.supabase.co")
        == "https://blreixaevpbmhbhyqgbq.supabase.co/rest/v1/thoughts"
    )
    assert (
        _supabase_thoughts_url("https://example.supabase.co/")
        == "https://example.supabase.co/rest/v1/thoughts"
    )


def test_build_thought_metadata_from_relay_fields() -> None:
    meta = _build_thought_metadata(
        {
            "relay_id": "rel-9",
            "trust_tier": "system_verified",
            "temporal_scope": None,
        },
        "mem-9",
        {"operation": "read"},
    )
    assert meta["type"] == "reference"
    assert meta["source"] == "aegisrelay"
    assert meta["people"] == []
    assert "aegisrelay" in meta["topics"]
    assert "relay-result" in meta["topics"]
    assert "trust_tier:system_verified" in meta["topics"]
    assert "relay_operation:read" in meta["topics"]
    assert "memory_id:mem-9" in meta["topics"]


def test_embedding_backoff_seconds_caps() -> None:
    assert embedding_backoff_seconds(0) == 0.0
    assert embedding_backoff_seconds(1) == 2.0
    assert embedding_backoff_seconds(10) == 300.0


def test_in_backoff_respects_last_attempt() -> None:
    now = datetime(2026, 4, 11, 15, 0, 0, tzinfo=timezone.utc)
    row = {
        "attempts": 2,
        "last_attempted_at": (now - timedelta(seconds=1)).isoformat(),
    }
    assert in_backoff(row, now) is True
    row["last_attempted_at"] = (now - timedelta(seconds=10)).isoformat()
    assert in_backoff(row, now) is False


def test_mark_outbox_failure_increments_attempts(sqlite_db) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    sqlite_db.execute(
        """
        INSERT INTO relay_requests (
            relay_id, human_actor_id, provider_name, provider_model,
            input_text, submitted_at
        ) VALUES ('r-fail', 'a', 'p', 'm', 'x', :ts)
        """,
        {"ts": ts},
    )
    sqlite_db.execute(
        """
        INSERT INTO outbox (outbox_id, relay_id, operation, payload, status, attempts, max_attempts)
        VALUES ('o-fail', 'r-fail', 'embed', :p, 'pending', 0, 3)
        """,
        {"p": json.dumps({"memory_id": "missing"})},
    )
    cur = sqlite_db.execute("SELECT * FROM outbox WHERE outbox_id = 'o-fail'", {})
    row = cur.fetchone()
    now = datetime.now(timezone.utc)
    mark_outbox_failure(sqlite_db, "o-fail", now, row)
    cur2 = sqlite_db.execute(
        "SELECT attempts, status FROM outbox WHERE outbox_id = 'o-fail'",
        {},
    )
    row2 = cur2.fetchone()
    assert row2["attempts"] == 1
    assert row2["status"] == "pending"


def test_mark_outbox_failure_goes_failed_at_max(sqlite_db) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    sqlite_db.execute(
        """
        INSERT INTO relay_requests (
            relay_id, human_actor_id, provider_name, provider_model,
            input_text, submitted_at
        ) VALUES ('r-fail2', 'a', 'p', 'm', 'x', :ts)
        """,
        {"ts": ts},
    )
    sqlite_db.execute(
        """
        INSERT INTO outbox (outbox_id, relay_id, operation, payload, status, attempts, max_attempts)
        VALUES ('o-fail2', 'r-fail2', 'embed', :p, 'pending', 2, 3)
        """,
        {"p": json.dumps({"memory_id": "missing"})},
    )
    cur = sqlite_db.execute("SELECT * FROM outbox WHERE outbox_id = 'o-fail2'", {})
    row = cur.fetchone()
    now = datetime.now(timezone.utc)
    mark_outbox_failure(sqlite_db, "o-fail2", now, row)
    cur2 = sqlite_db.execute(
        "SELECT attempts, status FROM outbox WHERE outbox_id = 'o-fail2'",
        {},
    )
    row2 = cur2.fetchone()
    assert row2["attempts"] == 3
    assert row2["status"] == "failed"


def test_embedding_openai_error_increments_attempts(monkeypatch, sqlite_db) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    sqlite_db.execute(
        """
        INSERT INTO relay_requests (
            relay_id, human_actor_id, provider_name, provider_model,
            input_text, submitted_at
        ) VALUES ('r-api', 'a', 'p', 'm', 'x', :ts)
        """,
        {"ts": ts},
    )
    sqlite_db.execute(
        """
        INSERT INTO memory_records (
            memory_id, relay_id, body_text, content_hash, embedding_status
        ) VALUES ('m-api', 'r-api', 'hello', 'h1', 'pending')
        """,
        {},
    )
    sqlite_db.execute(
        """
        INSERT INTO outbox (outbox_id, relay_id, operation, payload, status, attempts, max_attempts)
        VALUES ('o-api', 'r-api', 'embed', :p, 'pending', 0, 5)
        """,
        {"p": json.dumps({"memory_id": "m-api"})},
    )

    def _boom(*_a, **_k):
        raise urllib.error.URLError("network down")

    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    with patch("aegisrelay.workers.embedding_worker._fetch_openai_embedding", _boom):
        assert process_one_embedding_job(sqlite_db, None) is True

    cur = sqlite_db.execute("SELECT attempts, status FROM outbox WHERE outbox_id = 'o-api'", {})
    r = cur.fetchone()
    assert r["attempts"] == 1
    assert r["status"] == "pending"
