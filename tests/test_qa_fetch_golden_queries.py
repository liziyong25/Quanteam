from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def _canonical_hash(obj: dict) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_golden_queries_runner_writes_deterministic_summary(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    summary = tmp_path / "summary.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "qa_fetch_golden_queries_v1",
                "queries": [
                    {
                        "query_id": "q_stock_day",
                        "request": {"intent": {"asset": "stock", "freq": "day"}, "symbols": ["000001"]},
                    },
                    {
                        "query_id": "q_index_day",
                        "request": {"intent": {"asset": "index", "freq": "day"}, "symbols": ["000300"]},
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [
            "python3",
            "scripts/run_qa_fetch_golden_queries.py",
            "--manifest",
            manifest.as_posix(),
            "--out",
            summary.as_posix(),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr
    assert summary.is_file()

    out = json.loads(summary.read_text(encoding="utf-8"))
    assert out["schema_version"] == "qa_fetch_golden_summary_v1"
    assert out["total_queries"] == 2
    assert list(out["query_hashes"].keys()) == ["q_index_day", "q_stock_day"]
    assert out["query_hashes"]["q_stock_day"] == _canonical_hash(
        {"intent": {"asset": "stock", "freq": "day"}, "symbols": ["000001"]}
    )


def test_golden_queries_runner_rejects_duplicate_query_ids(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest_dup.json"
    summary = tmp_path / "summary_dup.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "qa_fetch_golden_queries_v1",
                "queries": [
                    {"query_id": "q_dup", "request": {"intent": {"asset": "stock", "freq": "day"}}},
                    {"query_id": "q_dup", "request": {"intent": {"asset": "index", "freq": "day"}}},
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [
            "python3",
            "scripts/run_qa_fetch_golden_queries.py",
            "--manifest",
            manifest.as_posix(),
            "--out",
            summary.as_posix(),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 2
    assert "duplicate query_id" in cp.stderr
