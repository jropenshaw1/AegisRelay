"""Outbox-driven embedding worker — OpenAI when configured, else null vector + complete."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from aegisrelay.config.secrets import SecretsProvider
from aegisrelay.db.base import DatabaseProvider
from aegisrelay.db.postgres_provider import PostgresProvider
from aegisrelay.workers._outbox_util import in_backoff, mark_outbox_failure, outbox_payload

_OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"
_EMBED_MODEL = "text-embedding-3-small"


def _openai_api_key(secrets: SecretsProvider | None) -> str | None:
    if secrets is not None:
        try:
            return secrets.get("OPENAI_API_KEY")
        except KeyError:
            return None
    return os.environ.get("OPENAI_API_KEY")


def _fetch_openai_embedding(api_key: str, text: str) -> list[float]:
    payload = json.dumps({"model": _EMBED_MODEL, "input": text}).encode("utf-8")
    req = urllib.request.Request(
        _OPENAI_EMBED_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    emb = raw["data"][0]["embedding"]
    if not isinstance(emb, list):
        raise TypeError("OpenAI embedding response shape unexpected")
    return [float(x) for x in emb]


def _pgvector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


def process_one_embedding_job(
    db: DatabaseProvider,
    secrets: SecretsProvider | None = None,
) -> bool:
    """
    Claim the oldest eligible pending ``embed`` outbox row, fill ``memory_records.embedding``,
    mark the outbox row complete.

    Uses OpenAI ``text-embedding-3-small`` when ``OPENAI_API_KEY`` is available; otherwise
    sets a null embedding and ``embedding_status = 'complete'`` (graceful no-op).

    Applies exponential backoff using ``attempts`` / ``last_attempted_at``; marks ``failed``
    after ``max_attempts``.
    """
    now = datetime.now(timezone.utc)
    cur = db.execute(
        """
        SELECT * FROM outbox
        WHERE operation = 'embed' AND status = 'pending'
        ORDER BY created_at
        """,
        {},
    )
    row = None
    for r in cur.fetchall():
        if not in_backoff(r, now):
            row = r
            break
    if row is None:
        cur_any = db.execute(
            "SELECT 1 AS o FROM outbox WHERE operation = 'embed' AND status = 'pending' LIMIT 1",
            {},
        )
        if cur_any.fetchone() is not None:
            return False
        return _process_one_memory_without_embedding(db, secrets, now)

    outbox_id = row["outbox_id"]
    payload = outbox_payload(row)
    memory_id = payload["memory_id"]

    cur_m = db.execute(
        "SELECT * FROM memory_records WHERE memory_id = :mid",
        {"mid": memory_id},
    )
    mem = cur_m.fetchone()
    if mem is None:
        mark_outbox_failure(db, outbox_id, now, row)
        return True

    api_key = _openai_api_key(secrets)
    vec: list[float] | None = None
    api_error = False
    if api_key:
        try:
            vec = _fetch_openai_embedding(api_key, str(mem["body_text"]))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            api_error = True
    if api_error:
        mark_outbox_failure(db, outbox_id, now, row)
        return True

    emb_val: str | None
    if isinstance(db, PostgresProvider):
        emb_val = _pgvector_literal(vec) if vec is not None else None
        mem_sql = """
            UPDATE memory_records
            SET embedding = CAST(:emb AS vector), embedding_status = 'complete'
            WHERE memory_id = :mid
            """
    else:
        emb_val = _pgvector_literal(vec) if vec is not None else None
        mem_sql = """
            UPDATE memory_records
            SET embedding = :emb, embedding_status = 'complete'
            WHERE memory_id = :mid
            """

    with db.transaction():
        db.execute(mem_sql, {"emb": emb_val, "mid": memory_id})
        db.execute(
            """
            UPDATE outbox
            SET status = 'complete', last_attempted_at = :ts
            WHERE outbox_id = :oid
            """,
            {"oid": outbox_id, "ts": now.isoformat()},
        )
    return True


def _process_one_memory_without_embedding(
    db: DatabaseProvider,
    secrets: SecretsProvider | None,
    now: datetime,
) -> bool:
    """
    Repair path: ``memory_records`` still pending with null embedding (no outbox row).
    Same OpenAI / no-key semantics; does not touch outbox.
    """
    cur = db.execute(
        """
        SELECT memory_id, body_text FROM memory_records
        WHERE embedding_status = 'pending' AND embedding IS NULL
        ORDER BY created_at
        LIMIT 1
        """,
        {},
    )
    mem = cur.fetchone()
    if mem is None:
        return False

    memory_id = mem["memory_id"]
    api_key = _openai_api_key(secrets)
    vec: list[float] | None = None
    if api_key:
        try:
            vec = _fetch_openai_embedding(api_key, str(mem["body_text"]))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False

    emb_val: str | None
    if isinstance(db, PostgresProvider):
        emb_val = _pgvector_literal(vec) if vec is not None else None
        mem_sql = """
            UPDATE memory_records
            SET embedding = CAST(:emb AS vector), embedding_status = 'complete'
            WHERE memory_id = :mid
            """
    else:
        emb_val = _pgvector_literal(vec) if vec is not None else None
        mem_sql = """
            UPDATE memory_records
            SET embedding = :emb, embedding_status = 'complete'
            WHERE memory_id = :mid
            """

    with db.transaction():
        db.execute(mem_sql, {"emb": emb_val, "mid": memory_id})
    return True
