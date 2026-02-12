#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_REL_PATH = Path("docs/05_data_plane/qa_fetch_registry_v1.json")
COMPARE_IGNORE_KEYS = frozenset({"generated_at_utc"})


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate or check qa_fetch registry JSON.")
    ap.add_argument(
        "--check",
        action="store_true",
        help="Check whether registry JSON is semantically in sync with generated payload.",
    )
    ap.add_argument(
        "--registry-path",
        default=None,
        help="Optional registry JSON path (default: docs/05_data_plane/qa_fetch_registry_v1.json).",
    )
    return ap.parse_args()


def _normalize_payload_for_compare(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: _normalize_payload_for_compare(v)
            for k, v in node.items()
            if k not in COMPARE_IGNORE_KEYS
        }
    if isinstance(node, list):
        return [_normalize_payload_for_compare(v) for v in node]
    return node


def _registry_path(repo_root: Path, *, registry_path_arg: str | None) -> Path:
    if registry_path_arg:
        p = Path(registry_path_arg)
        if p.is_absolute():
            return p
        return (repo_root / p).resolve()
    return (repo_root / DEFAULT_REGISTRY_REL_PATH).resolve()


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if src_root.as_posix() not in sys.path:
        sys.path.insert(0, src_root.as_posix())

    from quant_eam.qa_fetch.resolver import qa_fetch_registry_payload

    out_path = _registry_path(repo_root, registry_path_arg=args.registry_path)
    payload = qa_fetch_registry_payload(include_drop=False)
    fn_count = len(payload.get("functions", []))
    rs_count = len(payload.get("resolver_entries", []))

    if args.check:
        if not out_path.is_file():
            print(f"missing registry file: {out_path.as_posix()}", file=sys.stderr)
            return 2
        try:
            existing_doc = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"invalid json in {out_path.as_posix()}: {exc}", file=sys.stderr)
            return 2

        generated_norm = _normalize_payload_for_compare(payload)
        existing_norm = _normalize_payload_for_compare(existing_doc)
        if generated_norm == existing_norm:
            print(f"in sync: {out_path.as_posix()} (functions={fn_count}, resolver_entries={rs_count})")
            return 0
        print(
            f"drift detected: {out_path.as_posix()} differs from generated payload (ignoring generated_at_utc)",
            file=sys.stderr,
        )
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path.as_posix()} (functions={fn_count}, resolver_entries={rs_count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
