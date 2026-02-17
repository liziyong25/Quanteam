from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMProvider(Protocol):
    provider_id: str

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Return a JSON object that should validate against the provided schema."""


@dataclass(frozen=True)
class MockProvider:
    """Deterministic placeholder provider.

    In this repo, agent outputs are produced deterministically by agent implementations (provider='mock').
    The harness can still RECORD/REPLAY calls using cassettes without calling an external model.
    """

    provider_id: str = "mock"

    def complete_json(  # pragma: no cover - harness avoids calling mock provider in v1
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> dict[str, Any]:
        raise ValueError("MockProvider is not used for generation in this MVP (agent code is deterministic).")


@dataclass(frozen=True)
class RealStubProvider:
    provider_id: str = "real_stub"

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> dict[str, Any]:
        raise ValueError("Real LLM provider is not configured; use EAM_LLM_PROVIDER=mock and record/replay modes.")


def get_provider(provider_id: str) -> LLMProvider:
    pid = str(provider_id).strip()
    if pid in ("", "mock"):
        return MockProvider()
    if pid in ("real_stub",):
        return RealStubProvider()
    if pid in ("real",):
        from quant_eam.llm.providers.real_http import RealHTTPProvider

        return RealHTTPProvider()
    raise ValueError(f"unknown provider_id: {pid}")
