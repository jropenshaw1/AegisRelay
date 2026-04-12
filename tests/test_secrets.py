"""Secrets provider abstraction."""

from __future__ import annotations

import os

import pytest

from aegisrelay.config.secrets import EnvSecretsProvider


def test_env_secrets_provider_reads_existing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGISRELAY_TEST_SECRET", "xyzzy")
    sp = EnvSecretsProvider()
    assert sp.get("AEGISRELAY_TEST_SECRET") == "xyzzy"


def test_env_secrets_provider_missing_key_raises() -> None:
    sp = EnvSecretsProvider()
    key = "AEGISRELAY_KEY_THAT_SHOULD_NOT_EXIST_9f3a"
    os.environ.pop(key, None)
    with pytest.raises(KeyError):
        sp.get(key)
