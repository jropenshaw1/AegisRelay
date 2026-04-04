"""Health module tests (8 tests)."""

from __future__ import annotations

from aegisrelay.health import (
    HealthReport,
    SubsystemHealth,
    SubsystemStatus,
    get_health,
    _check_governance,
    _check_models,
    _check_provider_connectivity,
    _check_memory_store,
)


# ── Individual probe tests ──────────────────────────────────────────


def test_governance_probe_is_healthy() -> None:
    result = _check_governance()
    assert result.name == "governance"
    assert result.status == SubsystemStatus.HEALTHY
    assert "LENS v1.0" in result.detail
    assert "6 behaviours" in result.detail


def test_models_probe_is_healthy() -> None:
    result = _check_models()
    assert result.name == "models"
    assert result.status == SubsystemStatus.HEALTHY


def test_provider_connectivity_is_not_configured() -> None:
    result = _check_provider_connectivity()
    assert result.name == "provider_connectivity"
    assert result.status == SubsystemStatus.NOT_CONFIGURED


def test_memory_store_is_not_configured() -> None:
    result = _check_memory_store()
    assert result.name == "memory_store"
    assert result.status == SubsystemStatus.NOT_CONFIGURED


# ── Aggregate health tests ──────────────────────────────────────────


def test_get_health_returns_healthy_overall() -> None:
    report = get_health()
    assert report.status == SubsystemStatus.HEALTHY
    assert report.version == "0.1.0"
    assert len(report.subsystems) == 4


def test_get_health_not_configured_does_not_downgrade() -> None:
    """NOT_CONFIGURED stubs should not make overall status DEGRADED."""
    report = get_health()
    not_configured = [s for s in report.subsystems if s.status == SubsystemStatus.NOT_CONFIGURED]
    assert len(not_configured) == 2
    assert report.status == SubsystemStatus.HEALTHY


def test_health_report_to_dict_structure() -> None:
    report = get_health()
    d = report.to_dict()
    assert d["status"] == "healthy"
    assert "version" in d
    assert "checked_at" in d
    assert isinstance(d["subsystems"], list)
    assert len(d["subsystems"]) == 4
    for sub in d["subsystems"]:
        assert "name" in sub
        assert "status" in sub
        assert "detail" in sub
        assert "checked_at" in sub


def test_subsystem_health_has_timestamp() -> None:
    result = _check_governance()
    assert result.checked_at is not None
    assert "T" in result.checked_at  # ISO format
