"""Selective OpenBrain sync worker — Phase 2 interface stub (no live OB writes)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from aegisrelay.db.base import DatabaseProvider


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    s = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(s)


def process_one_ob_sync_job(db: DatabaseProvider) -> bool:
    """
    Process one pending ``sync_openbrain`` outbox entry when the memory row is eligible.

    Eligibility (ADR / handoff): trust tier in allowed set, embedding complete,
    and record not expired. Ineligible rows are marked complete without an OB call
    so the queue does not stall.
    """
    cur = db.execute(
        """
        SELECT * FROM outbox
        WHERE operation = 'sync_openbrain' AND status = 'pending'
        ORDER BY created_at
        LIMIT 1
        """,
        {},
    )
    row = cur.fetchone()
    if row is None:
        return False

    outbox_id = row["outbox_id"]
    payload = json.loads(row["payload"])
    memory_id = payload["memory_id"]

    cur_m = db.execute(
        "SELECT * FROM memory_records WHERE memory_id = :mid",
        {"mid": memory_id},
    )
    mem = cur_m.fetchone()
    now = datetime.now(timezone.utc)

    if mem is None:
        with db.transaction():
            db.execute(
                """
                UPDATE outbox
                SET status = 'failed', attempts = attempts + 1,
                    last_attempted_at = :ts
                WHERE outbox_id = :oid
                """,
                {"oid": outbox_id, "ts": now.isoformat()},
            )
        return True

    if mem["embedding_status"] != "complete":
        return False

    trust = mem["trust_tier"]
    exp = _parse_dt(mem["expires_at"]) if mem["expires_at"] else None
    expired = exp is not None and exp <= now
    eligible = trust in ("system_verified", "provider_asserted_with_citations") and not expired

    with db.transaction():
        if eligible:
            # Stub: production would POST to OpenBrain with [source:aegisrelay] tagging.
            _ = (memory_id, mem["body_text"][:200])

        db.execute(
            """
            UPDATE outbox SET status = 'complete', last_attempted_at = :ts
            WHERE outbox_id = :oid
            """,
            {"oid": outbox_id, "ts": now.isoformat()},
        )
    return True
