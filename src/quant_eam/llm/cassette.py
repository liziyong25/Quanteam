from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    return hashlib.sha256(_canonical_bytes(obj)).hexdigest()


def prompt_hash_v1(*, request: dict[str, Any]) -> str:
    """Stable hash for cassette lookup (based on sanitized request)."""
    return sha256_hex({"v": 1, "request": request})


def _jsonl_append(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            doc = json.loads(ln)
            if isinstance(doc, dict):
                out.append(doc)
    return out


@dataclass(frozen=True)
class CassetteStore:
    path: Path

    def append_call(self, call_obj: dict[str, Any]) -> None:
        _jsonl_append(self.path, call_obj)

    def replay_response(self, prompt_hash: str) -> dict[str, Any] | None:
        """Return response_json for the first matching prompt_hash, else None."""
        for doc in _iter_jsonl(self.path):
            if str(doc.get("prompt_hash", "")) == str(prompt_hash):
                r = doc.get("response_json")
                return r if isinstance(r, dict) else None
        return None

    def tail_calls(self, limit: int = 50) -> list[dict[str, Any]]:
        docs = _iter_jsonl(self.path)
        if limit <= 0:
            return []
        return docs[-limit:]

