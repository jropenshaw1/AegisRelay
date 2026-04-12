"""Outbox-driven embedding worker — Phase 2 stub vector (no external API)."""

from __future__ import annotations

import json

from aegisrelay.db.base import DatabaseProvider


def process_one_embedding_job(db: DatabaseProvider) -> bool:
    """
    Claim the oldest pending ``embed`` outbox row, write a stub embedding, mark complete.

    Returns True if a row was processed, False if the queue was empty.
    """
    cur = db.execute(
        """
        SELECT * FROM outbox
        WHERE operation = 'embed' AND status = 'pending'
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

    with db.transaction():
        db.execute(
            """
            UPDATE memory_records
            SET embedding = :emb, embedding_status = 'complete'
            WHERE memory_id = :mid
            """,
            {"emb": "stub", "mid": memory_id},
        )
        db.execute(
            "UPDATE outbox SET status = 'complete' WHERE outbox_id = :oid",
            {"oid": outbox_id},
        )
    return True
