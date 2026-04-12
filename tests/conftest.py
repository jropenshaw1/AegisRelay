"""Shared fixtures for Phase 2 tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegisrelay.admin.crud_service import CrudService
from aegisrelay.db.sqlite_provider import SQLiteProvider

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "aegisrelay" / "db" / "schema_sqlite.sql"


@pytest.fixture
def sqlite_db() -> SQLiteProvider:
    provider = SQLiteProvider(init_schema=SCHEMA_PATH)
    yield provider
    provider.close()


@pytest.fixture
def crud(sqlite_db: SQLiteProvider) -> CrudService:
    return CrudService(sqlite_db)
