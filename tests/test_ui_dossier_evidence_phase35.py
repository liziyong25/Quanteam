from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


def _find_whole_view_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Whole View Framework.md") if p.is_file())
    assert matches, "Whole View framework markdown is required for G35 dossier evidence page"
    return matches[0]


def _clean_md(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_dossier_run_entries(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            in_section = line.startswith("### 4.4") and ("Dossier" in line)
            continue
        if not in_section or (not line) or (line == "---") or ("建议目录" in line):
            continue
        item = line[2:].strip() if line.startswith("- ") else line
        item = _clean_md(item)
        if item.startswith("dossiers/<run_id>/"):
            item = item[len("dossiers/<run_id>/") :]
        if item in ("", "dossiers/<run_id>", "dossiers/<run_id>/"):
            continue
        normalized = item.strip("/")
        if not normalized:
            continue
        entry = f"{normalized}/" if item.endswith("/") else normalized
        if entry in seen:
            continue
        seen.add(entry)
        out.append(entry)
    assert out, "section 4.4 dossier structure extraction must not be empty"
    return out


def test_dossier_evidence_page_renders_structure_and_artifacts_index(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    dossiers_dir = artifact_root / "dossiers"
    run_a = dossiers_dir / "run_g35_a"
    run_b = dossiers_dir / "run_g35_b"
    run_a.mkdir(parents=True, exist_ok=True)
    run_b.mkdir(parents=True, exist_ok=True)

    required_entries = _extract_dossier_run_entries(_find_whole_view_doc())
    for entry in required_entries:
        target = run_a / entry.rstrip("/")
        if entry.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")

    for entry in required_entries[:3]:
        target = run_b / entry.rstrip("/")
        if entry.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")
    (run_b / "dossier_manifest.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(artifact_root))

    client = TestClient(app)
    r = client.get("/ui/dossier-evidence")
    assert r.status_code == 200
    text = r.text

    assert "Dossier Evidence Spec Coverage" in text
    assert "4.4 Dossier" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Artifacts Dossiers Evidence Index" in text
    assert "Required Entry Coverage Across Runs" in text
    assert "dossiers/&lt;run_id&gt;/" in text
    assert "run_g35_a" in text
    assert "run_g35_b" in text
    assert "dossier_manifest.json" in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    for entry in required_entries:
        assert entry in text

    expected_structure_total = len(required_entries) + 1  # dossiers/<run_id>/ root + run-level entries
    assert re.search(rf'data-testid="structure-entry-count">\s*{expected_structure_total}\s*<', text)
    assert re.search(rf'data-testid="required-run-entry-count">\s*{len(required_entries)}\s*<', text)
    assert re.search(r'data-testid="dossier-run-count">\s*2\s*<', text)
    assert "data-testid=\"dossier-run-row-1\"" in text
    assert "data-testid=\"dossier-entry-row-1\"" in text


def test_dossier_evidence_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/dossier-evidence").status_code == 200
    assert client.post("/ui/dossier-evidence").status_code == 405
