from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class RealHTTPProvider:
    """A minimal HTTP JSON-completion provider.

    This repo intentionally avoids depending on a specific vendor SDK.
    Expected API:
      POST {EAM_LLM_REAL_BASE_URL}/complete_json
      Headers:
        Authorization: Bearer <EAM_LLM_REAL_API_KEY>   (optional)
      Body:
        {
          "model": "...",
          "system": "...",
          "user": "...",
          "schema": { ... },        # JSON Schema object
          "temperature": 0.0,
          "seed": null
        }

    Response:
      {
        "json": { ... },            # the completion object
        "usage": { ... }            # optional
      }

    Notes:
    - Tests/CI must use cassette replay; this provider must not be called in tests.
    - Timeouts/retries are implemented to avoid hanging the worker.
    """

    provider_id: str = "real"

    def _cfg(self) -> tuple[str, str | None, str, float, int]:
        base = str(os.getenv("EAM_LLM_REAL_BASE_URL", "")).strip()
        if not base:
            raise ValueError("EAM_LLM_REAL_BASE_URL is required for real provider")
        key = str(os.getenv("EAM_LLM_REAL_API_KEY", "")).strip() or None
        model = str(os.getenv("EAM_LLM_REAL_MODEL", "")).strip() or "default"
        try:
            timeout = float(os.getenv("EAM_LLM_REAL_TIMEOUT_SECONDS", "30"))
        except Exception:  # noqa: BLE001
            timeout = 30.0
        timeout = max(1.0, timeout)
        try:
            retries = int(os.getenv("EAM_LLM_REAL_RETRIES", "2"))
        except Exception:  # noqa: BLE001
            retries = 2
        retries = max(0, min(5, retries))
        return base.rstrip("/"), key, model, timeout, retries

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> dict[str, Any]:
        # Hard guard: tests/CI must never perform network IO.
        # (Phase-28 rollout requires replay-only in CI.)
        if os.getenv("PYTEST_CURRENT_TEST"):
            raise ValueError("real provider network is disabled in tests; use EAM_LLM_MODE=replay with a cassette")
        if str(os.getenv("EAM_LLM_DISABLE_NETWORK", "")).strip().lower() in ("1", "true", "yes", "on"):
            raise ValueError("real provider network disabled by EAM_LLM_DISABLE_NETWORK")

        base, api_key, model, timeout_s, retries = self._cfg()
        url = f"{base}/complete_json"
        headers: dict[str, str] = {"content-type": "application/json"}
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"

        req = {
            "model": model,
            "system": str(system),
            "user": str(user),
            "schema": schema,
            "temperature": float(temperature),
            "seed": seed,
        }

        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=timeout_s) as client:
                    r = client.post(url, headers=headers, content=json.dumps(req))
                if r.status_code >= 400:
                    raise ValueError(f"real provider HTTP {r.status_code}: {r.text[:500]}")
                doc = r.json()
                if not isinstance(doc, dict):
                    raise ValueError("real provider response must be a JSON object")
                out = doc.get("json")
                if not isinstance(out, dict):
                    raise ValueError("real provider response must contain object field 'json'")
                return out
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt >= retries:
                    break
                # Small deterministic-ish backoff (doesn't matter for offline tests).
                time.sleep(0.2 * float(attempt + 1))
        raise ValueError(f"real provider failed after retries: {last_err}")
