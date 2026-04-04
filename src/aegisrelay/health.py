"""AegisRelay runtime health check.

Returns a structured health report covering every subsystem that can
be inspected at import time or with a cheap runtime probe.  Designed
to work as a plain function call today and as the backing logic for a
``/health`` HTTP endpoint when FastAPI is introduced in Phase 2.

Reference: n-agentic-harnesses 07 — UX, Observability, and Operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal


class SubsystemStatus(str, Enum):
    """Health status for an individual subsystem."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class SubsystemHealth:
    """Health report for one subsystem."""

    name: str
    status: SubsystemStatus
    detail: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class HealthReport:
    """Aggregate health report for the AegisRelay service."""

    status: SubsystemStatus
    version: str
    subsystems: tuple[SubsystemHealth, ...]
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON response."""
        return {
            "status": self.status.value,
            "version": self.version,
            "checked_at": self.checked_at,
            "subsystems": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "detail": s.detail,
                    "checked_at": s.checked_at,
                }
                for s in self.subsystems
            ],
        }


# ── Subsystem probes ────────────────────────────────────────────────


def _check_governance() -> SubsystemHealth:
    """Verify LENS behaviour registry is loaded and internally consistent."""
    try:
        from aegisrelay.governance.lens_constants import LENS_BEHAVIORS, LENS_VERSION

        required = [b for b, meta in LENS_BEHAVIORS.items() if meta["required"]]
        missing = [b for b in required if b not in LENS_BEHAVIORS]

        if missing:
            return SubsystemHealth(
                name="governance",
                status=SubsystemStatus.UNHEALTHY,
                detail=f"Required behaviours missing: {missing}",
            )

        hooks_present = {meta["hook"] for meta in LENS_BEHAVIORS.values()}
        if not {"pre_call", "post_call"}.issubset(hooks_present):
            return SubsystemHealth(
                name="governance",
                status=SubsystemStatus.DEGRADED,
                detail="Pre-call or post-call hook has no registered behaviours.",
            )

        return SubsystemHealth(
            name="governance",
            status=SubsystemStatus.HEALTHY,
            detail=f"LENS v{LENS_VERSION} — {len(LENS_BEHAVIORS)} behaviours, {len(required)} required.",
        )
    except Exception as exc:
        return SubsystemHealth(
            name="governance",
            status=SubsystemStatus.UNHEALTHY,
            detail=f"Import failed: {exc}",
        )


def _check_models() -> SubsystemHealth:
    """Smoke-test Pydantic model instantiation."""
    try:
        from aegisrelay.models.contracts import CanonicalRelayRequest, NormalizedProviderResponse

        CanonicalRelayRequest(input_text="health-check probe", operation="read")
        NormalizedProviderResponse(body_text="ok")

        return SubsystemHealth(
            name="models",
            status=SubsystemStatus.HEALTHY,
            detail="CanonicalRelayRequest and NormalizedProviderResponse instantiate cleanly.",
        )
    except Exception as exc:
        return SubsystemHealth(
            name="models",
            status=SubsystemStatus.UNHEALTHY,
            detail=f"Model validation failed: {exc}",
        )


def _check_provider_connectivity() -> SubsystemHealth:
    """Placeholder — no providers wired in Phase 1."""
    return SubsystemHealth(
        name="provider_connectivity",
        status=SubsystemStatus.NOT_CONFIGURED,
        detail="No provider adapters configured. Stub until Phase 2.",
    )


def _check_memory_store() -> SubsystemHealth:
    """Placeholder — no memory store wired in Phase 1."""
    return SubsystemHealth(
        name="memory_store",
        status=SubsystemStatus.NOT_CONFIGURED,
        detail="No memory store configured. Stub until OB/Supabase integration.",
    )


# ── Public API ──────────────────────────────────────────────────────


def get_health() -> HealthReport:
    """Run all subsystem probes and return an aggregate health report.

    Aggregate status logic:
    - If ANY subsystem is UNHEALTHY → overall UNHEALTHY
    - If ANY subsystem is DEGRADED → overall DEGRADED
    - NOT_CONFIGURED subsystems do not downgrade overall status
    - Otherwise → HEALTHY
    """
    from aegisrelay import __version__

    checks = (
        _check_governance(),
        _check_models(),
        _check_provider_connectivity(),
        _check_memory_store(),
    )

    active_statuses = [c.status for c in checks if c.status != SubsystemStatus.NOT_CONFIGURED]

    if SubsystemStatus.UNHEALTHY in active_statuses:
        overall = SubsystemStatus.UNHEALTHY
    elif SubsystemStatus.DEGRADED in active_statuses:
        overall = SubsystemStatus.DEGRADED
    elif not active_statuses:
        overall = SubsystemStatus.DEGRADED
    else:
        overall = SubsystemStatus.HEALTHY

    return HealthReport(
        status=overall,
        version=__version__,
        subsystems=checks,
    )
