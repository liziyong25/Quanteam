from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.llm.cassette import sha256_hex


SENSITIVE_KEY_FRAGMENTS = (
    "holdout",
    "vault",
    "secret",
    "token",
    "auth",
    "password",
    "apikey",
    "api_key",
    "bearer",
    "cookie",
)


def _is_sensitive_key(k: str) -> bool:
    kl = str(k).lower()
    return any(f in kl for f in SENSITIVE_KEY_FRAGMENTS)


def _replace_known_roots(s: str) -> tuple[str, int]:
    """Replace absolute root paths with stable placeholders (to avoid leaking host structure)."""
    replaced = 0
    roots = {
        os.getenv("EAM_DATA_ROOT", "/data"): "<EAM_DATA_ROOT>",
        os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"): "<EAM_ARTIFACT_ROOT>",
        os.getenv("EAM_JOB_ROOT", ""): "<EAM_JOB_ROOT>",
    }
    out = str(s)
    for k, v in roots.items():
        if not k:
            continue
        if k in out:
            out = out.replace(k, v)
            replaced += 1
    # Common defaults even if env differs.
    if "/data" in out:
        out = out.replace("/data", "<EAM_DATA_ROOT>")
        replaced += 1
    if "/artifacts" in out:
        out = out.replace("/artifacts", "<EAM_ARTIFACT_ROOT>")
        replaced += 1
    return out, replaced


@dataclass(frozen=True)
class RedactionSummary:
    removed_keys: list[str]
    truncated_strings: int
    truncated_lists: int
    truncated_dicts: int
    replaced_paths: int
    sanitized_sha256: str

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "removed_keys": list(self.removed_keys),
            "truncated_strings": int(self.truncated_strings),
            "truncated_lists": int(self.truncated_lists),
            "truncated_dicts": int(self.truncated_dicts),
            "replaced_paths": int(self.replaced_paths),
            "sanitized_sha256": str(self.sanitized_sha256),
        }


def sanitize_for_llm(
    obj: Any,
    *,
    max_depth: int = 10,
    max_str_chars: int = 20_000,
    max_list_items: int = 50,
    max_dict_items: int = 200,
) -> tuple[Any, RedactionSummary]:
    removed: list[str] = []
    trunc_str = 0
    trunc_list = 0
    trunc_dict = 0
    replaced_paths = 0

    def walk(x: Any, path: str, depth: int) -> Any:
        nonlocal trunc_str, trunc_list, trunc_dict, replaced_paths
        if depth > max_depth:
            return "<TRUNCATED_DEPTH>"
        if isinstance(x, dict):
            # Deterministic key order (sorted) and cap size.
            keys = sorted([str(k) for k in x.keys()])
            if len(keys) > max_dict_items:
                trunc_dict += 1
                keys = keys[:max_dict_items]
            out: dict[str, Any] = {}
            for k in keys:
                if _is_sensitive_key(k):
                    removed.append(f"{path}/{k}" if path else f"/{k}")
                    continue
                out[k] = walk(x.get(k), f"{path}/{k}" if path else f"/{k}", depth + 1)
            return out
        if isinstance(x, list):
            xs = x
            if len(xs) > max_list_items:
                trunc_list += 1
                xs = xs[:max_list_items]
            return [walk(v, f"{path}/{i}" if path else f"/{i}", depth + 1) for i, v in enumerate(xs)]
        if isinstance(x, (str, Path)):
            s = str(x)
            s2, rep = _replace_known_roots(s)
            replaced_paths += rep
            if len(s2) > max_str_chars:
                trunc_str += 1
                s2 = s2[:max_str_chars] + "<TRUNCATED>"
            return s2
        if isinstance(x, (int, float, bool)) or x is None:
            return x
        # Fallback to string (stable).
        s = str(x)
        s2, rep = _replace_known_roots(s)
        replaced_paths += rep
        if len(s2) > max_str_chars:
            trunc_str += 1
            s2 = s2[:max_str_chars] + "<TRUNCATED>"
        return s2

    sanitized = walk(obj, "", 0)
    sanitized_sha = sha256_hex(sanitized)
    return (
        sanitized,
        RedactionSummary(
            removed_keys=removed,
            truncated_strings=trunc_str,
            truncated_lists=trunc_list,
            truncated_dicts=trunc_dict,
            replaced_paths=replaced_paths,
            sanitized_sha256=sanitized_sha,
        ),
    )


def write_redaction_summary(path: Path, summary: RedactionSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.to_json_obj(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

