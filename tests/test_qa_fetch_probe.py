from __future__ import annotations

import json
from pathlib import Path

from quant_eam.qa_fetch.probe import (
    ProbeResult,
    parse_matrix_v3,
    write_probe_artifacts,
)


def test_parse_matrix_v3_count() -> None:
    rows = parse_matrix_v3(Path("docs/05_data_plane/qa_fetch_function_baseline_v1.md"))
    assert len(rows) > 0
    assert rows[0].source in {"mongo_fetch", "mysql_fetch"}
    assert rows[0].function.startswith("fetch_")


def test_write_probe_artifacts(tmp_path: Path) -> None:
    results = [
        ProbeResult(
            source="mongo_fetch",
            function="fetch_stock_day",
            status="pass_has_data",
            reason="ok",
            type="DataFrame",
            len=3,
            columns=["code", "date"],
            dtypes={"code": "object", "date": "datetime64[ns]"},
            head_preview=[{"code": "000001", "date": "2024-01-02"}],
            args_preview={"args": ["000001", "2024-01-02", "2024-01-05"], "kwargs": {"format": "pd"}},
        ),
        ProbeResult(
            source="mysql_fetch",
            function="fetch_bond_min",
            status="blocked_source_missing",
            reason="missing mysql tables: clean_execreport_1min",
            type="unknown",
            len=0,
            columns=[],
            dtypes={},
            head_preview=None,
            args_preview={"args": [], "kwargs": {}},
        ),
    ]

    paths = write_probe_artifacts(results, out_dir=tmp_path)

    for key in ["json", "csv", "candidate_pass_has_data", "candidate_pass_has_data_or_empty", "summary"]:
        assert key in paths
        assert Path(paths[key]).exists()

    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert len(payload) == 2
    assert payload[0]["status"] == "pass_has_data"

    summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
    assert summary["total"] == 2
    assert summary["status_counts"]["pass_has_data"] == 1
