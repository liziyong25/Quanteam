from __future__ import annotations

from fastapi.testclient import TestClient

from quant_eam.api.app import app


def test_governance_checks_page_renders_readonly_checklist() -> None:
    client = TestClient(app)
    url = "/ui/governance-checks"
    r = client.get(url)
    assert r.status_code == 200
    text = r.text

    assert "Whole View Governance Checklist" in text
    assert "GET/HEAD read-only evidence" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text

    assert "g32_governance_checks_ui_scope" in text
    assert "Whole View Hard Constraints" in text
    assert "Playbook Governance Rules" in text
    assert "Minimum Final Checks" in text
    assert "whole_view_hard_constraint" in text
    assert "minimum_final_check" in text

    assert "docs/00_overview/" in text
    assert "Whole View Framework.md" in text
    assert "Implementation Phases Playbook.md" in text
    assert "docs/12_workflows/skeleton_ssot_v1.yaml" in text

    assert "python3 scripts/check_docs_tree.py" in text
    assert "python3 scripts/check_subagent_packet.py --phase-id" in text

    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()


def test_governance_checks_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/governance-checks").status_code == 200
    assert client.post("/ui/governance-checks").status_code == 405


def test_governance_checks_page_shows_constraint_rows() -> None:
    client = TestClient(app)
    r = client.get("/ui/governance-checks")
    assert r.status_code == 200
    text = r.text
    assert "data-testid=\"whole-view-constraint-1\"" in text
    assert "data-testid=\"checklist-row-1\"" in text
