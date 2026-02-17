#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "qa_fetch_golden_queries_v1"
SUMMARY_SCHEMA = "qa_fetch_golden_summary_v1"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_request(request: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(request).encode("utf-8")).hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("manifest root must be object")
    if str(raw.get("schema_version", "")).strip() != MANIFEST_SCHEMA:
        raise ValueError(f"manifest schema_version must be {MANIFEST_SCHEMA}")
    queries = raw.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("manifest queries must be non-empty list")

    seen: set[str] = set()
    for idx, row in enumerate(queries, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"queries[{idx}] must be object")
        qid = str(row.get("query_id", "")).strip()
        if not qid:
            raise ValueError(f"queries[{idx}] query_id is required")
        if qid in seen:
            raise ValueError(f"duplicate query_id: {qid}")
        seen.add(qid)
        req = row.get("request")
        if not isinstance(req, dict) or not req:
            raise ValueError(f"queries[{idx}] request must be non-empty object")
    return raw


def build_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    queries = manifest.get("queries") if isinstance(manifest.get("queries"), list) else []
    hashes: dict[str, str] = {}
    for row in queries:
        qid = str(row.get("query_id")).strip()
        req = row.get("request")
        hashes[qid] = _hash_request(req)
    sorted_hashes = {k: hashes[k] for k in sorted(hashes.keys())}
    return {
        "schema_version": SUMMARY_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total_queries": len(sorted_hashes),
        "query_hashes": sorted_hashes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build deterministic QA fetch golden-query hash summary.")
    ap.add_argument("--manifest", required=True, help="Path to golden query manifest JSON.")
    ap.add_argument("--out", required=True, help="Path to output summary JSON.")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    if not manifest_path.is_file():
        print(f"manifest not found: {manifest_path.as_posix()}", file=sys.stderr)
        return 2

    try:
        manifest = load_manifest(manifest_path)
        summary = build_summary(manifest)
    except Exception as exc:  # noqa: BLE001
        print(f"invalid manifest: {exc}", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"golden summary written: {out_path.as_posix()}")
    print(f"total_queries={summary['total_queries']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
