"""Shared helpers for outbox workers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aegisrelay.db.base import DatabaseProvider


def parse_iso_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(s)


def outbox_payload(row: Any) -> dict[str, Any]:
    raw = row["payload"]
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return json.loads(str(raw))


def embedding_backoff_seconds(attempts: int) -> float:
    """Exponential backoff capped at 300s (attempts counts prior failures)."""
    if attempts <= 0:
        return 0.0
    return float(min(300, 2 ** min(attempts, 9)))


def in_backoff(row: Any, now: datetime) -> bool:
    att = row["attempts"] or 0
    if att <= 0:
        return False
    last = parse_iso_dt(row["last_attempted_at"])
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delay = embedding_backoff_seconds(att)
    return (now - last).total_seconds() < delay


def mark_outbox_failure(db: DatabaseProvider, outbox_id: str, now: datetime, row: Any) -> None:
    attempts = row["attempts"] or 0
    max_attempts = row["max_attempts"] if row["max_attempts"] is not None else 3
    new_att = attempts + 1
    status = "failed" if new_att >= max_attempts else "pending"
    db.execute(
        """
        UPDATE outbox
        SET attempts = :a,
            last_attempted_at = :ts,
            status = :st
        WHERE outbox_id = :oid
        """,
        {"a": new_att, "ts": now.isoformat(), "st": status, "oid": outbox_id},
    )
