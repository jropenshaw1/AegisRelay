"""Secrets access — hybrid env + abstraction (Gee review)."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class SecretsProvider(ABC):
    """Abstract secret lookup; implementations wrap env, vault, or test doubles."""

    @abstractmethod
    def get(self, key: str) -> str:
        """Return the secret value for `key`."""


class EnvSecretsProvider(SecretsProvider):
    """Reads from environment variables — default for dev and demo."""

    def get(self, key: str) -> str:
        return os.environ[key]
