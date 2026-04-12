"""Postgres provider placeholder — wire asyncpg/psycopg when deploying."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from aegisrelay.db.base import DatabaseProvider


class _PostgresTransactionStub(AbstractContextManager[None]):
    def __enter__(self) -> None:
        raise NotImplementedError(
            "PostgresProvider is not implemented in the Phase 2 portfolio build; use SQLiteProvider."
        )

    def __exit__(self, *exc: object) -> None:
        return None


class PostgresProvider(DatabaseProvider):
    """Interface stub; portfolio tests use `SQLiteProvider` instead."""

    def __init__(self, dsn: str = "") -> None:
        self._dsn = dsn

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError(
            "PostgresProvider is not implemented in the Phase 2 portfolio build; use SQLiteProvider."
        )

    def transaction(self) -> AbstractContextManager[None]:
        return _PostgresTransactionStub()
