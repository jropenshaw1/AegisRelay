"""Postgres provider — optional integration (requires ``DATABASE_URL`` + psycopg)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("psycopg")

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


def test_postgres_provider_select_one() -> None:
    from aegisrelay.db.postgres_provider import PostgresProvider

    db = PostgresProvider(os.environ["DATABASE_URL"])
    try:
        cur = db.execute("SELECT 1 AS one", {})
        row = cur.fetchone()
        assert row is not None
        assert row["one"] == 1
    finally:
        db.close()


def test_postgres_provider_transaction_rollback() -> None:
    from aegisrelay.db.postgres_provider import PostgresProvider

    db = PostgresProvider(os.environ["DATABASE_URL"])
    try:
        try:
            with db.transaction():
                db.execute("SELECT 1/0 AS x", {})
        except Exception:
            pass
        cur = db.execute("SELECT 1 AS ok", {})
        assert cur.fetchone()["ok"] == 1
    finally:
        db.close()
