"""Postgres `DatabaseProvider` — production; uses psycopg3."""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Generator

from aegisrelay.db.base import DatabaseProvider

if TYPE_CHECKING:
    from aegisrelay.config.secrets import SecretsProvider

_PARAM = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


def _pg_sql(sqlite_style: str) -> str:
    """Map SQLite-style `:name` placeholders to psycopg ``%(name)s``."""

    def repl(m: re.Match[str]) -> str:
        return f"%({m.group(1)})s"

    return _PARAM.sub(repl, sqlite_style)


class PostgresProvider(DatabaseProvider):
    """Sync psycopg3 connection; matches ``SQLiteProvider`` execute/transaction semantics."""

    @classmethod
    def from_secrets(cls, secrets: SecretsProvider) -> PostgresProvider:
        """Connect using ``DATABASE_URL`` from a ``SecretsProvider``."""
        return cls(secrets.get("DATABASE_URL"))

    def __init__(self, dsn: str) -> None:
        import psycopg
        from psycopg.rows import dict_row

        self._psycopg = psycopg
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        sql = _pg_sql(query)
        return self._conn.execute(sql, params or {})

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        with self._conn.transaction():
            yield

    def close(self) -> None:
        self._conn.close()
