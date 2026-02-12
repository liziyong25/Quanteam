from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

import quant_eam.api.ui_routes as ui_routes
from quant_eam.api.app import app


def _read_flag(path: Path) -> int | None:
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return 0
    return int(raw)


def test_qa_fetch_ui_renders_registry_resolver_probe_evidence() -> None:
    client = TestClient(app)
    r = client.get("/ui/qa-fetch")
    assert r.status_code == 200
    text = r.text

    registry = json.loads(Path("docs/05_data_plane/qa_fetch_registry_v1.json").read_text(encoding="utf-8"))
    probe_summary = json.loads(Path("docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3.json").read_text(encoding="utf-8"))
    pass_has_data = _read_flag(Path("docs/05_data_plane/qa_fetch_probe_v3/candidate_pass_has_data.txt"))
    pass_has_data_or_empty = _read_flag(Path("docs/05_data_plane/qa_fetch_probe_v3/candidate_pass_has_data_or_empty.txt"))

    assert "QA Fetch Explorer" in text
    assert "read-only" in text.lower()
    assert "no write actions" in text.lower()
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    assert "docs/05_data_plane/qa_fetch_registry_v1.json" in text
    assert "docs/05_data_plane/qa_fetch_resolver_registry_v1.md" in text
    assert "docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3.json" in text
    assert "docs/05_data_plane/qa_fetch_probe_v3/probe_results_v3.json" in text
    assert "docs/05_data_plane/qa_fetch_smoke_evidence_v1.md" in text

    expected_functions = len(registry.get("functions", []))
    expected_resolver_entries = len(registry.get("resolver_entries", []))
    expected_total = int(probe_summary.get("total", 0))
    expected_pass_has_data = "n/a" if pass_has_data is None else str(pass_has_data)
    expected_pass_has_data_or_empty = "n/a" if pass_has_data_or_empty is None else str(pass_has_data_or_empty)

    assert re.search(rf'data-testid="registry-functions-count">\s*{expected_functions}\s*<', text)
    assert re.search(rf'data-testid="registry-resolver-count">\s*{expected_resolver_entries}\s*<', text)
    assert re.search(rf'data-testid="probe-total">\s*{expected_total}\s*<', text)
    assert re.search(rf'data-testid="probe-pass-has-data">\s*{re.escape(expected_pass_has_data)}\s*<', text)
    assert re.search(
        rf'data-testid="probe-pass-has-data-or-empty">\s*{re.escape(expected_pass_has_data_or_empty)}\s*<', text
    )


def test_qa_fetch_ui_degrades_when_evidence_missing(tmp_path: Path, monkeypatch) -> None:
    docs_root = tmp_path / "docs" / "05_data_plane"
    docs_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "qa_fetch_smoke_evidence_v1.md").write_text(
        "# QA Fetch Smoke Evidence v1\n\nDate: `2026-02-11`\n\nplaceholder\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(ui_routes, "_repo_root", lambda: tmp_path)
    client = TestClient(app)
    r = client.get("/ui/qa-fetch")
    assert r.status_code == 200
    text = r.text

    assert "docs/05_data_plane/qa_fetch_registry_v1.json" in text
    assert "missing" in text.lower()
    assert "Smoke Evidence Markdown" in text
    assert "<form" not in text.lower()
