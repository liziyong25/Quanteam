from __future__ import annotations


class RegistryInvalid(ValueError):
    """Semantic invalidation (exit=2)."""


class RegistryUsageOrError(RuntimeError):
    """Usage or unexpected error (exit=1)."""

