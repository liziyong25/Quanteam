from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


def _find_whole_view_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Whole View Framework.md") if p.is_file())
    assert matches, "Whole View framework markdown is required for G33 contracts coverage"
    return matches[0]


def _extract_required_contracts(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            in_section = ("5.1" in line) and ("Contract" in line)
            continue
        if not in_section:
            continue
        m = re.match(r"^\d+\)\s*([A-Za-z0-9_.-]+\.json)\b", line)
        if m:
            out.append(m.group(1))
    assert out, "Section 5.1 required contracts extraction must not be empty"
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contracts_coverage_page_renders_required_contracts_and_disk_evidence() -> None:
    client = TestClient(app)
    framework = _find_whole_view_doc()
    required = _extract_required_contracts(framework)

    r = client.get("/ui/contracts-coverage")
    assert r.status_code == 200
    text = r.text

    assert "Whole View Required Contracts Coverage" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "5.1 必须落地的 Contracts（v1）" in text
    assert "Whole View Framework.md" in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    present_total = 0
    for contract_file in required:
        contract_path = Path("contracts") / contract_file
        assert contract_file in text
        assert f"contracts/{contract_file}" in text
        if contract_path.is_file():
            present_total += 1
            assert _sha256(contract_path) in text

    missing_total = len(required) - present_total
    assert re.search(rf'data-testid="required-total">\s*{len(required)}\s*<', text)
    assert re.search(rf'data-testid="present-total">\s*{present_total}\s*<', text)
    assert re.search(rf'data-testid="missing-total">\s*{missing_total}\s*<', text)


def test_contracts_coverage_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/contracts-coverage").status_code == 200
    assert client.post("/ui/contracts-coverage").status_code == 405
