"""Transactional CRUD for relay audit retrieval (Phase 2)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from aegisrelay.db.base import DatabaseProvider
from aegisrelay.governance.pipeline import PipelineArtifacts
from aegisrelay.models.audit_bundle import RelayAuditBundle, RelaySummary
from aegisrelay.models.contracts import CanonicalRelayRequest, CanonicalRelayResponse
from aegisrelay.models.governance_event import GovernanceEvent
from aegisrelay.models.lens import LensObservation
from aegisrelay.models.memory_record import MemoryRecord

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _event_id(relay_id: str, *parts: str) -> str:
    return str(uuid.uuid5(_NS, ":".join((relay_id,) + parts)))


def lens_observation_to_governance_event(
    relay_id: str,
    obs: LensObservation,
    seq: str,
    created_at: datetime,
) -> GovernanceEvent:
    """Map a `LensObservation` to a `governance_events` row."""
    return GovernanceEvent(
        event_id=_event_id(relay_id, "lens", obs.hook, obs.behavior, seq),
        relay_id=relay_id,
        event_type="lens_observation",
        stage=obs.hook,
        metadata={
            "behavior": obs.behavior,
            "trigger_fired": obs.trigger_fired,
            "confidence": obs.confidence,
            "observation": obs.observation,
            "lens_version": obs.lens_version,
            "matched_signals": obs.matched_signals,
        },
        created_at=created_at,
    )


def _dt_to_str(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    s = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(s)


def _irreversible_sql_val(v: bool | None) -> int | None:
    if v is None:
        return None
    return 1 if v else 0


class CrudService:
    """SQLite or Postgres via `DatabaseProvider`."""

    def __init__(self, db: DatabaseProvider) -> None:
        self._db = db

    def create_relay(
        self,
        request: CanonicalRelayRequest,
        pre_call_observations: list[LensObservation],
    ) -> str:
        """
        Transaction 1 — persist inbound request (pending) and pre-call LENS rows.
        """
        relay_id = request.relay_id
        with self._db.transaction():
            self._db.execute(
                """
                INSERT INTO relay_requests (
                    relay_id, human_actor_id, provider_name, provider_model,
                    input_text, operation, is_irreversible, session_id,
                    submitted_at, schema_version, status
                ) VALUES (
                    :relay_id, :human_actor_id, :provider_name, :provider_model,
                    :input_text, :operation, :is_irreversible, :session_id,
                    :submitted_at, :schema_version, 'pending'
                )
                """,
                {
                    "relay_id": relay_id,
                    "human_actor_id": request.human_actor_id,
                    "provider_name": request.provider_name,
                    "provider_model": request.provider_model,
                    "input_text": request.input_text,
                    "operation": request.operation,
                    "is_irreversible": _irreversible_sql_val(request.is_irreversible),
                    "session_id": request.session_id,
                    "submitted_at": _dt_to_str(request.submitted_at),
                    "schema_version": request.schema_version,
                },
            )
            for i, obs in enumerate(pre_call_observations):
                ge = lens_observation_to_governance_event(
                    relay_id, obs, str(i), request.submitted_at
                )
                self._insert_governance_event(ge)
        return relay_id

    def finalize_relay(
        self,
        relay_id: str,
        canonical_response: CanonicalRelayResponse,
        post_call_observations: list[LensObservation],
        artifacts: PipelineArtifacts,
    ) -> None:
        """
        Transaction 2 — response row, post-call + pipeline governance, memories, outbox, status.
        """
        with self._db.transaction():
            self._db.execute(
                """
                INSERT INTO relay_responses (
                    relay_id, provider_name, provider_model, response_text,
                    provider_request_ts, provider_response_ts, raw_provider_response, schema_version
                ) VALUES (
                    :relay_id, :provider_name, :provider_model, :response_text,
                    :provider_request_ts, :provider_response_ts, :raw_provider_response, :schema_version
                )
                """,
                {
                    "relay_id": relay_id,
                    "provider_name": canonical_response.provider_name,
                    "provider_model": canonical_response.provider_model,
                    "response_text": canonical_response.response_text,
                    "provider_request_ts": _dt_to_str(canonical_response.provider_request_ts),
                    "provider_response_ts": _dt_to_str(canonical_response.provider_response_ts),
                    "raw_provider_response": (
                        json.dumps(canonical_response.raw_provider_response)
                        if canonical_response.raw_provider_response is not None
                        else None
                    ),
                    "schema_version": canonical_response.schema_version,
                },
            )
            ts_post = canonical_response.provider_response_ts
            for i, obs in enumerate(post_call_observations):
                ge = lens_observation_to_governance_event(relay_id, obs, str(i), ts_post)
                self._insert_governance_event(ge)

            for ge in artifacts.governance_events:
                self._insert_governance_event(ge)

            for mem in artifacts.memory_records:
                self._insert_memory_record(mem)

            for row in artifacts.outbox_rows:
                self._db.execute(
                    """
                    INSERT INTO outbox (outbox_id, relay_id, operation, payload, status)
                    VALUES (:outbox_id, :relay_id, :operation, :payload, 'pending')
                    """,
                    {
                        "outbox_id": row["outbox_id"],
                        "relay_id": row["relay_id"],
                        "operation": row["operation"],
                        "payload": json.dumps(row["payload"], sort_keys=True),
                    },
                )

            self._db.execute(
                "UPDATE relay_requests SET status = 'complete' WHERE relay_id = :relay_id",
                {"relay_id": relay_id},
            )

    def _insert_governance_event(self, ge: GovernanceEvent) -> None:
        self._db.execute(
            """
            INSERT OR IGNORE INTO governance_events (event_id, relay_id, event_type, stage, metadata, created_at)
            VALUES (:event_id, :relay_id, :event_type, :stage, :metadata, :created_at)
            """,
            {
                "event_id": ge.event_id,
                "relay_id": ge.relay_id,
                "event_type": ge.event_type,
                "stage": ge.stage,
                "metadata": json.dumps(ge.metadata, sort_keys=True, default=str),
                "created_at": _dt_to_str(ge.created_at),
            },
        )

    def _insert_memory_record(self, mem: MemoryRecord) -> None:
        self._db.execute(
            """
            INSERT OR IGNORE INTO memory_records (
                memory_id, relay_id, body_text, content_hash,
                trust_tier, temporal_scope, expires_at, embedding_status, schema_version
            ) VALUES (
                :memory_id, :relay_id, :body_text, :content_hash,
                :trust_tier, :temporal_scope, :expires_at, :embedding_status, :schema_version
            )
            """,
            {
                "memory_id": mem.memory_id,
                "relay_id": mem.relay_id,
                "body_text": mem.body_text,
                "content_hash": mem.content_hash,
                "trust_tier": mem.trust_tier,
                "temporal_scope": mem.temporal_scope,
                "expires_at": _dt_to_str(mem.expires_at) if mem.expires_at else None,
                "embedding_status": mem.embedding_status,
                "schema_version": mem.schema_version,
            },
        )

    def insert_memory_record_idempotent(self, mem: MemoryRecord) -> None:
        """Public wrapper for idempotency tests (same memory row twice)."""
        with self._db.transaction():
            self._insert_memory_record(mem)

    def get_relay(self, relay_id: str) -> RelayAuditBundle:
        cur = self._db.execute(
            "SELECT * FROM relay_requests WHERE relay_id = :relay_id",
            {"relay_id": relay_id},
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"Unknown relay_id: {relay_id}")
        req = self._row_to_request(row)

        cur = self._db.execute(
            "SELECT * FROM relay_responses WHERE relay_id = :relay_id",
            {"relay_id": relay_id},
        )
        rrow = cur.fetchone()
        response: CanonicalRelayResponse | None = None
        if rrow is not None:
            raw = rrow["raw_provider_response"]
            raw_d: dict[str, Any] | None = json.loads(raw) if raw else None
            response = CanonicalRelayResponse(
                relay_id=rrow["relay_id"],
                provider_name=rrow["provider_name"],
                provider_model=rrow["provider_model"],
                response_text=rrow["response_text"],
                provider_request_ts=_parse_dt(rrow["provider_request_ts"]) or req.submitted_at,
                provider_response_ts=_parse_dt(rrow["provider_response_ts"]) or req.submitted_at,
                schema_version=rrow["schema_version"],
                raw_provider_response=raw_d,
            )

        cur = self._db.execute(
            "SELECT * FROM memory_records WHERE relay_id = :relay_id ORDER BY memory_id",
            {"relay_id": relay_id},
        )
        memories = [self._row_to_memory(m) for m in cur.fetchall()]

        cur = self._db.execute(
            "SELECT * FROM governance_events WHERE relay_id = :relay_id ORDER BY created_at, event_id",
            {"relay_id": relay_id},
        )
        events = [self._row_to_governance(e) for e in cur.fetchall()]

        return RelayAuditBundle(
            request=req,
            response=response,
            memory_records=memories,
            governance_events=events,
        )

    def list_relays(
        self,
        limit: int = 50,
        offset: int = 0,
        filters: dict[str, str] | None = None,
    ) -> list[RelaySummary]:
        filters = filters or {}
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status := filters.get("status"):
            where.append("status = :status")
            params["status"] = status
        if actor := filters.get("human_actor_id"):
            where.append("human_actor_id = :human_actor_id")
            params["human_actor_id"] = actor
        wh = (" WHERE " + " AND ".join(where)) if where else ""
        cur = self._db.execute(
            f"""
            SELECT relay_id, human_actor_id, provider_name, provider_model,
                   submitted_at, status, operation
            FROM relay_requests
            {wh}
            ORDER BY submitted_at DESC
            LIMIT :limit OFFSET :offset
            """,
            params,
        )
        out: list[RelaySummary] = []
        for row in cur.fetchall():
            out.append(
                RelaySummary(
                    relay_id=row["relay_id"],
                    human_actor_id=row["human_actor_id"],
                    provider_name=row["provider_name"],
                    provider_model=row["provider_model"],
                    submitted_at=_parse_dt(row["submitted_at"])
                    or datetime(1970, 1, 1, tzinfo=timezone.utc),
                    status=row["status"],
                    operation=row["operation"],
                )
            )
        return out

    def _row_to_request(self, row: Any) -> CanonicalRelayRequest:
        ir: bool | None = None
        if row["is_irreversible"] is not None:
            ir = bool(row["is_irreversible"])
        sa = _parse_dt(row["submitted_at"])
        if sa is None:
            raise ValueError("relay_requests.submitted_at missing")
        return CanonicalRelayRequest(
            relay_id=row["relay_id"],
            human_actor_id=row["human_actor_id"],
            provider_name=row["provider_name"],
            provider_model=row["provider_model"],
            input_text=row["input_text"],
            operation=row["operation"],
            schema_version=row["schema_version"],
            session_id=row["session_id"],
            submitted_at=sa,
            is_irreversible=ir,
            has_downstream_effects=None,
        )

    def _row_to_memory(self, row: Any) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            relay_id=row["relay_id"],
            body_text=row["body_text"],
            content_hash=row["content_hash"],
            trust_tier=row["trust_tier"],
            temporal_scope=row["temporal_scope"],
            expires_at=_parse_dt(row["expires_at"]) if row["expires_at"] else None,
            embedding_status=row["embedding_status"],
            schema_version=row["schema_version"],
        )

    def _row_to_governance(self, row: Any) -> GovernanceEvent:
        meta = json.loads(row["metadata"])
        return GovernanceEvent(
            event_id=row["event_id"],
            relay_id=row["relay_id"],
            event_type=row["event_type"],
            stage=row["stage"],
            metadata=meta,
            created_at=_parse_dt(row["created_at"]) or datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
