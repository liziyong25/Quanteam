from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from quant_eam.api.app import app


def _request_via_asgi(method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def test_workbench_phase_card_matrix_wb045_coverage_and_order(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    reg_root = tmp_path / "registry"
    job_root = tmp_path / "jobs"
    data_root.mkdir()
    art_root.mkdir()
    reg_root.mkdir()
    job_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))

    created = _request_via_asgi(
        "POST",
        "/workbench/sessions",
        json={
            "title": "WB-045 matrix",
            "symbols": "AAA,BBB",
            "hypothesis_text": "deterministic phase cards",
        },
    )
    assert created.status_code == 201, created.text
    session_id = str(created.json()["session_id"])

    for _ in range(4):
        cont = _request_via_asgi("POST", f"/workbench/sessions/{session_id}/continue", json={})
        assert cont.status_code == 200, cont.text

    sess_doc = _request_via_asgi("GET", f"/workbench/sessions/{session_id}").json()
    cards = sess_doc.get("cards")
    assert isinstance(cards, list)
    assert len(cards) == 5
    cards_sorted = sorted(cards, key=lambda card: int(card.get("card_index") or 0))

    expected_phase_order = ["idea", "strategy_spec", "trace_preview", "runspec", "improvements"]
    expected_titles = {
        "idea": "Phase-0 Idea -> Blueprint Draft",
        "strategy_spec": "Phase-1 Strategy Spec Confirmation",
        "trace_preview": "Phase-2 Demo Validation",
        "runspec": "Phase-3 Research Backtest",
        "improvements": "Phase-4 Evaluation / Improvement / Registry / Compose",
    }
    assert [str(card.get("phase")) for card in cards_sorted] == expected_phase_order
    assert [str(card.get("phase_label")) for card in cards_sorted] == ["Phase-0", "Phase-1", "Phase-2", "Phase-3", "Phase-4"]

    for card in cards_sorted:
        phase = str(card.get("phase"))
        assert str(card.get("title")) == expected_titles[phase]
        summary_lines = card.get("summary_lines")
        assert isinstance(summary_lines, list)
        assert len(summary_lines) == 3
        assert str(summary_lines[0]).startswith("Result cards:")
        evidence = json.loads(str(card.get("evidence_json") or "{}"))
        definition = evidence.get("result_card_definition") if isinstance(evidence, dict) else {}
        assert isinstance(definition, dict)
        assert definition.get("requirement_id") == "WB-045"
        assert definition.get("step") == phase
        if phase == "idea":
            assert definition.get("phase_scope_requirement_id") == "WB-046"
            assert definition.get("deferred_requirement_ids") == ["WB-047", "WB-048"]

    ui_page = _request_via_asgi("GET", f"/ui/workbench/{session_id}")
    assert ui_page.status_code == 200
    assert "WB-045 Phase Result Card Matrix" in ui_page.text
    marker_positions: list[int] = []
    for step in expected_phase_order:
        marker = f'data-testid="workbench-phase-card-{step}"'
        assert marker in ui_page.text
        marker_positions.append(ui_page.text.index(marker))
    assert marker_positions == sorted(marker_positions)
