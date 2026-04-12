"""
Eight-stage governance pipeline (ADR-004) — deterministic under retries.

Stages 3 and 4 emit LENS governance metadata per `03_Integration_Design_v1.0.md` §5.
Temporal anchors use `request.submitted_at` (not wall clock) so replays stay stable.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from aegisrelay.governance import lens_constants as C
from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse
from aegisrelay.models.governance_event import GovernanceEvent
from aegisrelay.models.memory_record import MemoryRecord

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID DNS — deterministic ids

_FRAME_CHOICE = re.compile(
    r"\b(from a technical perspective|commercially|legally|ethically|assuming that)\b",
    re.IGNORECASE,
)
_ALTERNATIVE_FRAME = re.compile(
    r"\b(could also|alternatively|another view|conversely)\b",
    re.IGNORECASE,
)
_UNCERT = re.compile(r"\b(probably|might|may\b|unclear|possibly|I think)\b", re.IGNORECASE)
_QUALIFIER = re.compile(r"\b(uncertainty|confidence|not certain|approximate)\b", re.IGNORECASE)
_TIME_SENSITIVE = re.compile(r"\b(latest|today|right now|current|as of)\b", re.IGNORECASE)
_CITATION_HINT = re.compile(r"https?://|\[[0-9]+\]")


def _event_id(relay_id: str, *parts: str) -> str:
    return str(uuid.uuid5(_NS, ":".join((relay_id,) + parts)))


def _stable_dt(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


@dataclass
class PipelineArtifacts:
    """Outputs from stage 8 before persistence."""

    memory_records: list[MemoryRecord] = field(default_factory=list)
    governance_events: list[GovernanceEvent] = field(default_factory=list)
    outbox_rows: list[dict[str, Any]] = field(default_factory=list)


def _normalize(body_text: str) -> str:
    """Collapse intra-paragraph whitespace; preserve blank-line paragraph boundaries."""
    blocks = body_text.split("\n\n")
    return "\n\n".join(" ".join(block.split()) for block in blocks)


def _segment(normalized: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n\n+", normalized) if p.strip()]
    if not parts:
        t = normalized.strip()
        return [t] if t else ["empty"]
    return parts


def _trust_tier(segment: str) -> str:
    if _CITATION_HINT.search(segment):
        return "provider_asserted_with_citations"
    if len(segment) < 220 and not _UNCERT.search(segment):
        return "system_verified"
    return "provider_asserted"


def _detect_cognitive_frame(segment: str) -> tuple[bool, bool, str | None]:
    material = bool(_FRAME_CHOICE.search(segment))
    user_alt = bool(_ALTERNATIVE_FRAME.search(segment)) or material
    name: str | None = None
    if m := _FRAME_CHOICE.search(segment):
        name = m.group(1).lower().replace(" ", "_")
    return material, user_alt, name


def _temporal_policy(
    segment: str, submitted_at: datetime
) -> tuple[str | None, datetime | None]:
    if not _TIME_SENSITIVE.search(segment):
        return None, None
    scope = "short_lived_current_affairs"
    expires = _stable_dt(submitted_at) + timedelta(days=7)
    return scope, expires


def _redact_stub(segment: str) -> str:
    return segment


def run_eight_stage_pipeline(
    relay_id: str,
    request: CanonicalRelayRequest,
    normalized_response: NormalizedProviderResponse,
    provider_request_ts: datetime,
    provider_response_ts: datetime,
) -> PipelineArtifacts:
    """
    Run normalize → segment → classify → uncertainty → temporal → redact → dedupe.

    Memory rows and outbox entries are produced in memory; caller persists atomically.
    """
    artifacts = PipelineArtifacts()
    submitted_at = _stable_dt(request.submitted_at)

    # --- Stage 1: Normalize ---
    norm_body = _normalize(normalized_response.body_text)
    artifacts.governance_events.append(
        GovernanceEvent(
            event_id=_event_id(relay_id, "pipeline_stage_1", "normalize"),
            relay_id=relay_id,
            event_type="pipeline_stage",
            stage="pipeline_stage_1",
            metadata={
                "stage": "normalize",
                "input_chars": len(normalized_response.body_text),
                "output_chars": len(norm_body),
            },
            created_at=provider_response_ts,
        )
    )

    # --- Stage 2: Segment ---
    segments = _segment(norm_body)
    artifacts.governance_events.append(
        GovernanceEvent(
            event_id=_event_id(relay_id, "pipeline_stage_2", "segment"),
            relay_id=relay_id,
            event_type="pipeline_stage",
            stage="pipeline_stage_2",
            metadata={"stage": "segment", "unit_count": len(segments)},
            created_at=provider_response_ts,
        )
    )

    seen_hashes: set[str] = set()
    seq = 0

    for segment in segments:
        seq += 1

        # --- Stage 3: Classify + LENS Cognitive Model Disclosure ---
        trust = _trust_tier(segment)
        material, user_alt, frame_name = _detect_cognitive_frame(segment)
        artifacts.governance_events.append(
            GovernanceEvent(
                event_id=_event_id(relay_id, "pipeline_stage_3", str(seq)),
                relay_id=relay_id,
                event_type="pipeline_stage",
                stage="pipeline_stage_3",
                metadata={"stage": "classify", "trust_tier": trust, "segment_index": seq},
                created_at=provider_response_ts,
            )
        )
        if material and user_alt:
            artifacts.governance_events.append(
                GovernanceEvent(
                    event_id=_event_id(relay_id, "lens", "cmd", str(seq)),
                    relay_id=relay_id,
                    event_type="lens_observation",
                    stage="pipeline_stage_3",
                    metadata={
                        "behavior": "cognitive_model_disclosure",
                        "trigger_fired": True,
                        "frame_detected": frame_name or "unspecified_frame",
                        "confidence": 0.72,
                        "lens_version": C.LENS_VERSION,
                        "observation": "Analytical framing choice may materially affect conclusions.",
                    },
                    created_at=provider_response_ts,
                )
            )

        # --- Stage 4: Mark uncertainty + LENS Uncertainty Flagging ---
        is_uncertain = bool(_UNCERT.search(segment))
        is_flagged = bool(_QUALIFIER.search(segment))
        artifacts.governance_events.append(
            GovernanceEvent(
                event_id=_event_id(relay_id, "pipeline_stage_4", str(seq)),
                relay_id=relay_id,
                event_type="pipeline_stage",
                stage="pipeline_stage_4",
                metadata={
                    "stage": "mark_uncertainty",
                    "segment_index": seq,
                    "is_uncertain": is_uncertain,
                    "is_flagged_in_text": is_flagged,
                },
                created_at=provider_response_ts,
            )
        )
        if is_uncertain and not is_flagged:
            artifacts.governance_events.append(
                GovernanceEvent(
                    event_id=_event_id(relay_id, "lens", "unc", str(seq)),
                    relay_id=relay_id,
                    event_type="lens_observation",
                    stage="pipeline_stage_4",
                    metadata={
                        "behavior": "uncertainty_flagging",
                        "trigger_fired": True,
                        "violation": True,
                        "claim_text": segment[:200],
                        "confidence": 0.68,
                        "lens_version": C.LENS_VERSION,
                        "observation": "Uncertain language present without explicit qualification.",
                    },
                    created_at=provider_response_ts,
                )
            )

        # --- Stage 5: Temporal policy ---
        scope, expires = _temporal_policy(segment, submitted_at)
        artifacts.governance_events.append(
            GovernanceEvent(
                event_id=_event_id(relay_id, "pipeline_stage_5", str(seq)),
                relay_id=relay_id,
                event_type="pipeline_stage",
                stage="pipeline_stage_5",
                metadata={
                    "stage": "temporal_policy",
                    "segment_index": seq,
                    "temporal_scope": scope,
                    "expires_at": expires.isoformat() if expires else None,
                },
                created_at=provider_response_ts,
            )
        )

        # --- Stage 6: Redact (stub) ---
        redacted = _redact_stub(segment)
        artifacts.governance_events.append(
            GovernanceEvent(
                event_id=_event_id(relay_id, "pipeline_stage_6", str(seq)),
                relay_id=relay_id,
                event_type="pipeline_stage",
                stage="pipeline_stage_6",
                metadata={"stage": "redact", "segment_index": seq, "changed": redacted != segment},
                created_at=provider_response_ts,
            )
        )

        content_hash = hashlib.sha256(redacted.encode("utf-8")).hexdigest()

        # --- Stage 7: Dedupe ---
        if content_hash in seen_hashes:
            artifacts.governance_events.append(
                GovernanceEvent(
                    event_id=_event_id(relay_id, "pipeline_stage_7", "skip", content_hash),
                    relay_id=relay_id,
                    event_type="pipeline_stage",
                    stage="pipeline_stage_7",
                    metadata={"stage": "deduplicate", "content_hash": content_hash, "skipped": True},
                    created_at=provider_response_ts,
                )
            )
            continue
        seen_hashes.add(content_hash)

        artifacts.governance_events.append(
            GovernanceEvent(
                event_id=_event_id(relay_id, "pipeline_stage_7", "keep", content_hash),
                relay_id=relay_id,
                event_type="pipeline_stage",
                stage="pipeline_stage_7",
                metadata={"stage": "deduplicate", "content_hash": content_hash, "skipped": False},
                created_at=provider_response_ts,
            )
        )

        memory_id = str(uuid.uuid5(_NS, f"{relay_id}:{content_hash}"))
        mem = MemoryRecord(
            memory_id=memory_id,
            relay_id=relay_id,
            body_text=redacted,
            content_hash=content_hash,
            trust_tier=trust,
            temporal_scope=scope,
            expires_at=expires,
            embedding_status="pending",
            schema_version="1.0",
        )
        artifacts.memory_records.append(mem)

        embed_oid = _event_id(relay_id, "outbox", "embed", memory_id)
        sync_oid = _event_id(relay_id, "outbox", "sync", memory_id)
        artifacts.outbox_rows.append(
            {
                "outbox_id": embed_oid,
                "relay_id": relay_id,
                "operation": "embed",
                "payload": {"memory_id": memory_id},
            }
        )
        artifacts.outbox_rows.append(
            {
                "outbox_id": sync_oid,
                "relay_id": relay_id,
                "operation": "sync_openbrain",
                "payload": {"memory_id": memory_id},
            }
        )

    # --- Stage 8 marker (persist is external) ---
    artifacts.governance_events.append(
        GovernanceEvent(
            event_id=_event_id(relay_id, "pipeline_stage_8", "persist_ready"),
            relay_id=relay_id,
            event_type="pipeline_stage",
            stage="pipeline_stage_8",
            metadata={
                "stage": "persist",
                "memory_count": len(artifacts.memory_records),
                "outbox_count": len(artifacts.outbox_rows),
            },
            created_at=provider_response_ts,
        )
    )

    return artifacts


def pipeline_artifacts_fingerprint(artifacts: PipelineArtifacts) -> str:
    """Stable hash of pipeline outputs for idempotency tests (excludes event_id)."""
    payload = {
        "memories": [m.model_dump(mode="json", exclude={"memory_id"}) for m in artifacts.memory_records],
        "hashes": sorted(m.content_hash for m in artifacts.memory_records),
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
