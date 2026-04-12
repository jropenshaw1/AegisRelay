"""OpenBrain sync — Supabase ``thoughts`` insert + OpenRouter embeddings (optional)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Mapping

from aegisrelay.config.secrets import SecretsProvider
from aegisrelay.db.base import DatabaseProvider
from aegisrelay.workers._outbox_util import in_backoff, mark_outbox_failure, outbox_payload, parse_iso_dt

_OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
_OPENROUTER_MODEL = "openai/text-embedding-3-small"


def _sync_base_url(secrets: SecretsProvider | None) -> str | None:
    if secrets is not None:
        try:
            return secrets.get("OPENBRAIN_SYNC_URL")
        except KeyError:
            pass
    return os.environ.get("OPENBRAIN_SYNC_URL")


def _sync_token(secrets: SecretsProvider | None) -> str | None:
    if secrets is not None:
        try:
            return secrets.get("OPENBRAIN_SYNC_TOKEN")
        except KeyError:
            pass
    return os.environ.get("OPENBRAIN_SYNC_TOKEN")


def _openrouter_api_key(secrets: SecretsProvider | None) -> str | None:
    if secrets is not None:
        try:
            return secrets.get("OPENROUTER_API_KEY")
        except KeyError:
            pass
    return os.environ.get("OPENROUTER_API_KEY")


def _supabase_thoughts_url(base: str) -> str:
    b = base.rstrip("/")
    return f"{b}/rest/v1/thoughts"


def _fetch_openrouter_embedding(api_key: str, text: str) -> list[float]:
    payload = json.dumps({"model": _OPENROUTER_MODEL, "input": text}).encode("utf-8")
    req = urllib.request.Request(
        _OPENROUTER_EMBED_URL,
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
        raise TypeError("OpenRouter embedding response shape unexpected")
    return [float(x) for x in emb]


def _row_dict(row: Any) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _build_thought_metadata(
    mem: Mapping[str, Any],
    memory_id: str,
    relay: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Structured metadata from relay + memory only (no LLM extraction)."""
    operation = (relay or {}).get("operation") or "unknown"
    trust = mem.get("trust_tier") or "unknown"
    topics: list[str] = [
        "aegisrelay",
        "relay-result",
        f"trust_tier:{trust}",
        f"relay_operation:{operation}",
        f"relay_id:{mem['relay_id']}",
        f"memory_id:{memory_id}",
    ]
    scope = mem.get("temporal_scope")
    if scope:
        topics.append(f"temporal_scope:{scope}")
    return {
        "type": "reference",
        "topics": topics,
        "people": [],
        "action_items": [],
        "dates_mentioned": [],
        "source": "aegisrelay",
    }


def _post_supabase_thought(
    rest_url: str,
    service_token: str,
    content: str,
    embedding: list[float] | None,
    metadata: dict[str, Any],
) -> None:
    body: dict[str, Any] = {
        "content": content,
        "embedding": embedding,
        "metadata": metadata,
    }

    data = json.dumps(body, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "apikey": service_token,
        "Authorization": f"Bearer {service_token}",
        "Prefer": "return=representation",
    }
    req = urllib.request.Request(rest_url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60):
        pass


def process_one_ob_sync_job(
    db: DatabaseProvider,
    secrets: SecretsProvider | None = None,
) -> bool:
    """
    Process one pending ``sync_openbrain`` outbox entry when the memory row is eligible.

    Eligibility: trust tier in allowed set, embedding complete on the memory row,
    and record not expired. Ineligible rows are marked complete without a Supabase call.

    When ``OPENBRAIN_SYNC_URL`` (Supabase project base) and ``OPENBRAIN_SYNC_TOKEN``
    (service role) are set, inserts into ``/rest/v1/thoughts`` with content, metadata
    built from relay fields, and an embedding from OpenRouter
    (``openai/text-embedding-3-small``) when ``OPENROUTER_API_KEY`` is set; otherwise
    ``embedding`` is null. On HTTP / transport errors, increments ``attempts`` and
    applies the shared outbox backoff / ``failed`` policy.
    """
    now = datetime.now(timezone.utc)
    cur = db.execute(
        """
        SELECT * FROM outbox
        WHERE operation = 'sync_openbrain' AND status = 'pending'
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
        return False

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

    if mem["embedding_status"] != "complete":
        return False

    trust = mem["trust_tier"]
    exp = parse_iso_dt(mem["expires_at"]) if mem["expires_at"] else None
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    expired = exp is not None and exp <= now
    eligible = trust in ("system_verified", "provider_asserted_with_citations") and not expired

    base_url = _sync_base_url(secrets)

    if eligible and base_url:
        token = _sync_token(secrets)
        if not token:
            mark_outbox_failure(db, outbox_id, now, row)
            return True

        cur_r = db.execute(
            "SELECT * FROM relay_requests WHERE relay_id = :rid",
            {"rid": mem["relay_id"]},
        )
        relay_row = cur_r.fetchone()

        content = str(mem["body_text"])
        mem_d = _row_dict(mem)
        relay_d = _row_dict(relay_row) if relay_row is not None else None
        metadata = _build_thought_metadata(mem_d, memory_id, relay_d)

        or_key = _openrouter_api_key(secrets)
        embedding: list[float] | None = None
        embed_failed = False
        if or_key:
            try:
                embedding = _fetch_openrouter_embedding(or_key, content)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
                embed_failed = True
        if embed_failed:
            mark_outbox_failure(db, outbox_id, now, row)
            return True

        rest_url = _supabase_thoughts_url(base_url)
        try:
            _post_supabase_thought(rest_url, token, content, embedding, metadata)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            mark_outbox_failure(db, outbox_id, now, row)
            return True

    with db.transaction():
        db.execute(
            """
            UPDATE outbox SET status = 'complete', last_attempted_at = :ts
            WHERE outbox_id = :oid
            """,
            {"oid": outbox_id, "ts": now.isoformat()},
        )
    return True
