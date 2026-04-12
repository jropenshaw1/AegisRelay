"""Database abstraction — SQLite for tests, Postgres for production."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any


class DatabaseProvider(ABC):
    """Minimal parametric SQL facade used by CRUD and workers."""

    @abstractmethod
    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Run a single statement; returns driver-specific cursor or result."""

    @abstractmethod
    def transaction(self) -> AbstractContextManager[None]:
        """Transactional scope — commit on success, rollback on exception."""
