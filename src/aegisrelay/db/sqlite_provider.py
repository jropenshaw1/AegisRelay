"""SQLite-backed `DatabaseProvider` for local demo and pytest."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from aegisrelay.db.base import DatabaseProvider


class SQLiteProvider(DatabaseProvider):
    def __init__(self, database: str | Path = ":memory:", init_schema: Path | None = None) -> None:
        self._conn = sqlite3.connect(str(database), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if init_schema is not None:
            self._conn.executescript(init_schema.read_text(encoding="utf-8"))
            self._conn.commit()

    def execute(self, query: str, params: dict[str, Any] | None = None) -> sqlite3.Cursor:
        cur = self._conn.cursor()
        cur.execute(query, params or {})
        return cur

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        try:
            self._conn.execute("BEGIN")
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()
