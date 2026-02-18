from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.api.ui_routes import WORKBENCH_ROUTE_INTERFACE_V43, _workbench_missing_route_pairs
from quant_eam.compiler.compile import main as compiler_main
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.registry import cli as registry_cli
from quant_eam.runner.run import main as runner_main
from quant_eam.worker.main import main as worker_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _request_via_asgi(method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def _build_demo_evidence(tmp_path: Path, monkeypatch) -> tuple[str, str]:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    reg_root = tmp_path / "registry"
    data_root.mkdir()
    art_root.mkdir()
    reg_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_ui_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)]) == 0
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == 0

    dossiers_dir = art_root / "dossiers"
    d = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])[0]
    run_id = d.name

    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (0, 2)
    assert registry_cli.main(["--registry-root", str(reg_root), "record-trial", "--dossier", str(d)]) == 0
    assert registry_cli.main(
        ["--registry-root", str(reg_root), "create-card", "--run-id", run_id, "--title", "buyhold_demo"]
    ) == 0

    card_id = f"card_{run_id}"
    return run_id, card_id


def test_readonly_api_and_ui_pages_200(tmp_path: Path, monkeypatch) -> None:
    run_id, card_id = _build_demo_evidence(tmp_path, monkeypatch)
    client = TestClient(app)

    r = client.get("/runs")
    assert r.status_code == 200
    assert any(x["run_id"] == run_id for x in r.json()["runs"])

    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["run_id"] == run_id

    assert client.get(f"/runs/{run_id}/curve").status_code == 200
    assert client.get(f"/runs/{run_id}/trades").status_code == 200
    assert client.get(f"/runs/{run_id}/artifacts").status_code == 200

    r = client.get("/registry/cards")
    assert r.status_code == 200
    assert any(c["card_id"] == card_id for c in r.json()["cards"])

    r = client.get(f"/registry/cards/{card_id}")
    assert r.status_code == 200
    assert r.json()["card_id"] == card_id

    r = client.get("/ui")
    assert r.status_code == 200
    assert card_id in r.text
    assert run_id in r.text
    assert 'class="page-header"' in r.text
    assert 'class="table-wrap"' in r.text

    r = client.get(f"/ui/runs/{run_id}")
    assert r.status_code == 200
    assert run_id in r.text
    assert f'Run {run_id}' in r.text
    assert 'class="page-title"' in r.text
    assert f"/ui/runs/{run_id}/gates" in r.text
    # Provenance linkage: run page must link to snapshot detail page (read-only).
    assert "/ui/snapshots/" in r.text
    # Phase-22: risk report rendered when present.
    assert "Risk" in r.text

    rg = client.get(f"/ui/runs/{run_id}/gates")
    assert rg.status_code == 200
    assert f"Run {run_id} Gates" in rg.text
    assert "Holdout (Minimal Summary)" in rg.text
    assert "<form" not in rg.text.lower()
    assert "method=\"post\"" not in rg.text.lower()

    r = client.get(f"/ui/cards/{card_id}")
    assert r.status_code == 200
    assert card_id in r.text
    assert f'Card {card_id}' in r.text

    r = client.get("/ui/jobs")
    assert r.status_code == 200
    assert "Workflow: blueprint -> compile -> WAITING_APPROVAL -> run -> gates -> registry" in r.text

    r = client.get("/ui/qa-fetch")
    assert r.status_code == 200
    assert "QA Fetch Explorer" in r.text
    assert "docs/05_data_plane/qa_fetch_registry_v1.json" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/governance-checks")
    assert r.status_code == 200
    assert "Whole View Governance Checklist" in r.text
    assert "g32_governance_checks_ui_scope" in r.text
    assert "python3 scripts/check_docs_tree.py" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/policies-constraints")
    assert r.status_code == 200
    assert "Policies and Constraints Evidence" in r.text
    assert "Whole View Hard Constraints" in r.text
    assert "Playbook Task Rules (0.1)" in r.text
    assert "Playbook Quality Gates (0.2)" in r.text
    assert "Whole View Framework.md" in r.text
    assert "Implementation Phases Playbook.md" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/contracts-coverage")
    assert r.status_code == 200
    assert "Whole View Required Contracts Coverage" in r.text
    assert "5.1 必须落地的 Contracts（v1）" in r.text
    assert "contracts/blueprint_schema_v1.json" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/contracts-principles")
    assert r.status_code == 200
    assert "Whole View Contracts-System Principles and Trace Plan/Result Boundary Evidence" in r.text
    assert "5. Contracts（Schema）体系：让 LLM/Codex 能产、Kernel 能编译、UI 能渲染" in r.text
    assert "trace 计划/结果分离" in r.text
    assert "/ui/contracts-principles" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/dossier-evidence")
    assert r.status_code == 200
    assert "Dossier Evidence Spec Coverage" in r.text
    assert "4.4 Dossier" in r.text
    assert "dossiers/&lt;run_id&gt;/" in r.text
    assert run_id in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/playbook-principles")
    assert r.status_code == 200
    assert "Playbook Construction Principles and Quality Gates Read-Only Evidence" in r.text
    assert "Playbook Section 0 Construction Principles" in r.text
    assert "Playbook Section 0.2 Global Quality Gates" in r.text
    assert "Quant‑EAM Implementation Phases Playbook.md" in r.text
    assert "/ui/playbook-principles" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/playbook-tech-stack")
    assert r.status_code == 200
    assert "Playbook Technical Stack Baseline Read-Only Evidence" in r.text
    assert "Playbook Section 1 Technical Stack Baseline" in r.text
    assert "Playbook Section 1.1 Foundation Stack" in r.text
    assert "Playbook Section 1.2 Service Stack" in r.text
    assert "Quant‑EAM Implementation Phases Playbook.md" in r.text
    assert "/ui/playbook-tech-stack" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/playbook-phase-template")
    assert r.status_code == 200
    assert "Playbook Phase Template Structure Read-Only Evidence" in r.text
    assert "Playbook Section 2 Phase Template Structure" in r.text
    assert "Phase‑X 标准输出结构" in r.text
    assert "Quant‑EAM Implementation Phases Playbook.md" in r.text
    assert "/ui/playbook-phase-template" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/playbook-codex-task-card")
    assert r.status_code == 200
    assert "Playbook Codex Task Card Template Read-Only Evidence" in r.text
    assert "Playbook Section 4 Codex Task Card Template" in r.text
    assert "Codex Task Card Template" in r.text
    assert "Quant‑EAM Implementation Phases Playbook.md" in r.text
    assert "/ui/playbook-codex-task-card" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/playbook-sequence")
    assert r.status_code == 200
    assert "Playbook Construction Sequence Recommendation Read-Only Evidence" in r.text
    assert "Playbook Section 5 Construction Sequence Recommendation" in r.text
    assert "Loop-First Rationale" in r.text
    assert "Agents Automation Positioning" in r.text
    assert "Contracts/Policies/DataCatalog/Runner/Dossier/Gates/UI" in r.text
    assert "Phase-0" in r.text
    assert "Phase-6" in r.text
    assert "Quant‑EAM Implementation Phases Playbook.md" in r.text
    assert "/ui/playbook-sequence" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/playbook-phases")
    assert r.status_code == 200
    assert "Playbook Phase Matrix Read-Only Evidence" in r.text
    assert "phase_dispatch_plan_v2" in r.text
    assert "goal_checklist" in r.text
    assert "G36" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/ia-coverage")
    assert r.status_code == 200
    assert "UI Information Architecture Coverage" in r.text
    assert "8. UI 信息架构（不看源码的审阅体验）" in r.text
    assert "Whole View IA Checklist Mapping" in r.text
    assert "/ui/runs/{run_id}/gates" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/agent-roles")
    assert r.status_code == 200
    assert "Agents Roles and Harness Boundary Evidence" in r.text
    assert "6.4 Agents Plane" in r.text
    assert "Phase-8" in r.text
    assert "agents_pipeline_v1" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/workflow-checkpoints")
    assert r.status_code == 200
    assert "Whole View Workflow Checkpoints Matrix" in r.text
    assert "3. Whole View 工作流（UI Checkpoint 驱动的状态机）" in r.text
    assert "phase_dispatch_plan_v2" in r.text
    assert "orchestrator_autopilot_v1" in r.text
    assert "G39" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/object-model")
    assert r.status_code == 200
    assert "Whole View Object Model I/O Coverage" in r.text
    assert "4. 核心对象模型（系统只认这些 I/O）" in r.text
    assert "Playbook Phase Flow/Context (Section 3)" in r.text
    assert "phase_dispatch_plan_v2" in r.text
    assert "g40_object_model_ui_scope" in r.text
    assert "G40" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/module-boundaries")
    assert r.status_code == 200
    assert "Whole View Modules Deterministic-Agent Boundary Evidence" in r.text
    assert "6. 模块（Modules）与职责边界（Deterministic vs Agent）" in r.text
    assert "Playbook Phase Flow/Context (Section 3)" in r.text
    assert "phase_dispatch_plan_v2" in r.text
    assert "g41_module_boundaries_ui_scope" in r.text
    assert "G41" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/diagnostics-promotion")
    assert r.status_code == 200
    assert "Codex Diagnostics Promotion Chain Read-Only Evidence" in r.text
    assert "7. Codex CLI 的定位：探索者 + 工具工，不是裁判" in r.text
    assert "Playbook Phase-12 Diagnostics Promote Evidence" in r.text
    assert "phase_dispatch_plan_v2" in r.text
    assert "g42_diagnostics_promotion_ui_scope" in r.text
    assert "G42" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/codex-role-boundary")
    assert r.status_code == 200
    assert "Whole View Codex Role Boundary Read-Only Evidence" in r.text
    assert "7. Codex CLI 的定位：探索者 + 工具工，不是裁判" in r.text
    assert "/ui/codex-role-boundary" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/ui-coverage-matrix")
    assert r.status_code == 200
    assert "Whole View UI Eight-Page Coverage Matrix" in r.text
    assert "8. UI 信息架构（不看源码的审阅体验）" in r.text
    assert "Whole View Section 8 Checklist Coverage Matrix" in r.text
    assert "Current UI Route Inventory" in r.text
    assert "phase_dispatch_plan_v2" in r.text
    assert "g43_ui_coverage_matrix_scope" in r.text
    assert "G43" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/runtime-topology")
    assert r.status_code == 200
    assert "Whole View Runtime Topology and Service Ports Read-Only Evidence" in r.text
    assert "9. 仓库与运行形态（Linux + Docker + Python）" in r.text
    assert "Playbook Section 1 Service Context" in r.text
    assert "Playbook Phase Flow/Context (Section 3)" in r.text
    assert "phase_dispatch_plan_v2" in r.text
    assert "g44_runtime_topology_ui_scope" in r.text
    assert "G44" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/preflight-checklist")
    assert r.status_code == 200
    assert "Whole View Anti-Drift Preflight Checklist Read-Only Evidence" in r.text
    assert "Whole View Section 10 Anti-Drift Checklist" in r.text
    assert "10. “不跑偏”检查清单（每次新增功能前先对齐）" in r.text
    assert "/ui/preflight-checklist" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/version-roadmap")
    assert r.status_code == 200
    assert "Whole View Version Roadmap Milestones Read-Only Evidence" in r.text
    assert "Whole View Section 11 Version Roadmap Milestones" in r.text
    assert "v0.4" in r.text
    assert "v0.5" in r.text
    assert "v0.6" in r.text
    assert "/ui/version-roadmap" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/system-definition")
    assert r.status_code == 200
    assert "Whole View System Definition and Five Planes Read-Only Evidence" in r.text
    assert "Whole View Section 0 System Definition" in r.text
    assert "Whole View Section 2 Five Planes Architecture" in r.text
    assert "Quant‑EAM Whole View Framework.md" in r.text
    assert "/ui/system-definition" in r.text
    assert "<form" not in r.text.lower()

    r = client.get("/ui/hard-constraints")
    assert r.status_code == 200
    assert "Whole View Hard Constraints Governance Evidence" in r.text
    assert "Whole View Section 1 Hard Constraints" in r.text
    assert "Quant‑EAM Whole View Framework.md" in r.text
    assert "/ui/hard-constraints" in r.text
    assert "<form" not in r.text.lower()


def test_ui_create_idea_job_from_form(tmp_path: Path, monkeypatch) -> None:
    print("DBG: setup start")
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
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snapshot_id = "demo_snap_ui_idea_001"
    print("DBG: ingest")
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    print("DBG: GET /ui")
    r = _request_via_asgi("GET", "/ui")
    assert r.status_code == 200
    assert "Create Idea Job" in r.text
    assert 'class="btn"' in r.text

    form = {
        "title": "UI Idea Demo",
        "hypothesis_text": "UI submission should create deterministic idea job artifacts.",
        "symbols": "AAA,BBB",
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "ui_e2e",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    print("DBG: POST /ui/jobs/idea")
    r = _request_via_asgi("POST", "/ui/jobs/idea", data=form, follow_redirects=False)
    assert r.status_code == 303, r.text
    loc = r.headers.get("location", "")
    assert loc.startswith("/ui/jobs/")
    job_id = loc.rsplit("/", 1)[-1]

    job_dir = job_root / job_id
    assert (job_dir / "job_spec.json").is_file()
    assert (job_dir / "inputs" / "idea_spec.json").is_file()
    assert (job_dir / "events.jsonl").is_file()

    lines = [ln for ln in (job_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    events = [json.loads(ln) for ln in lines]
    assert events
    assert any(str(ev.get("event_type")) == "IDEA_SUBMITTED" for ev in events)

    # After worker advance, the workflow should stop at blueprint checkpoint.
    print("DBG: worker once")
    assert worker_main(["--run-jobs", "--once"]) == 0
    lines2 = [ln for ln in (job_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    events2 = [json.loads(ln) for ln in lines2]
    assert any(
        str(ev.get("event_type")) == "WAITING_APPROVAL"
        and isinstance(ev.get("outputs"), dict)
        and str(ev["outputs"].get("step")) == "blueprint"
        for ev in events2
    )

    print("DBG: final GET job page")
    rd = _request_via_asgi("GET", loc)
    assert rd.status_code == 200
    assert job_id in rd.text


def test_path_traversal_blocked() -> None:
    r = _request_via_asgi("GET", "/runs/../../etc/passwd")
    assert r.status_code in (400, 404)


def test_holdout_leak_not_rendered(tmp_path: Path, monkeypatch) -> None:
    run_id, _card_id = _build_demo_evidence(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get(f"/ui/runs/{run_id}")
    assert r.status_code == 200
    # UI must not render holdout curve/trades artifacts.
    assert "holdout_curve" not in r.text
    assert "holdout_trades" not in r.text


def test_workbench_bundle_phase_chain_cards_and_governance(tmp_path: Path, monkeypatch) -> None:
    art_root = tmp_path / "artifacts"
    job_root = tmp_path / "jobs"
    reg_root = tmp_path / "registry"
    data_root = tmp_path / "data"
    art_root.mkdir()
    job_root.mkdir()
    reg_root.mkdir()
    data_root.mkdir()

    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))

    client = TestClient(app)

    # WB-002: dedicated requirement entry exists and existing review pages remain reachable.
    r = client.get("/ui/workbench/req/wb-002")
    assert r.status_code == 200
    assert "Create Workbench Session" in r.text
    assert "Requirement entry alias" in r.text
    r = client.get("/ui/workbench/req/wb-028")
    assert r.status_code == 200
    for method, path in WORKBENCH_ROUTE_INTERFACE_V43:
        assert f"{method} {path}" in r.text
    assert _workbench_missing_route_pairs() == []
    assert client.get("/ui/jobs").status_code == 200
    assert client.get("/ui/qa-fetch").status_code == 200

    payload = {
        "title": "WB Bundle Demo",
        "symbols": "AAPL,MSFT",
        "hypothesis_text": "Sequential phase progression should emit readable cards.",
    }
    created = client.post("/workbench/sessions", json=payload)
    assert created.status_code == 201, created.text
    created_doc = created.json()
    session_id = str(created_doc["session_id"])

    # WB-003: skip/jump is rejected; only current or immediate next step is allowed.
    bad = client.post(f"/workbench/sessions/{session_id}/continue", json={"target_step": "improvements"})
    assert bad.status_code == 409

    expected_steps = ["strategy_spec", "trace_preview", "runspec", "improvements"]
    for expected_step in expected_steps:
        resp = client.post(f"/workbench/sessions/{session_id}/continue", json={})
        assert resp.status_code == 200, resp.text
        doc = resp.json()
        assert doc["current_step"] == expected_step
        card = doc.get("card")
        assert isinstance(card, dict)
        assert str(card.get("phase")) == expected_step
        assert isinstance(card.get("summary_lines"), list)

    # Final stage continue is idempotent refresh (no forward jump possible).
    tail = client.post(f"/workbench/sessions/{session_id}/continue", json={})
    assert tail.status_code == 200, tail.text
    tail_doc = tail.json()
    assert tail_doc["current_step"] == "improvements"
    assert tail_doc["idempotent"] is True

    # WB-005: drafts keep selected index artifact for replay/approval trace.
    dresp = client.post(
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
        json={"content": {"note": "draft-v1"}},
    )
    assert dresp.status_code == 200, dresp.text
    draft_doc = dresp.json()
    assert int(draft_doc["draft_version"]) == 1
    apply = client.post(f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/1/apply", json={})
    assert apply.status_code == 200, apply.text
    selected_doc = apply.json()
    selected_path = Path(str(selected_doc["selected_index_path"]))
    assert selected_path.is_file()
    selected_payload = json.loads(selected_path.read_text(encoding="utf-8"))
    assert selected_payload["selected_version"] == 1

    # WB-004: UI renders readable cards and keeps evidence collapsed by default via <details>.
    page = client.get(f"/ui/workbench/{session_id}")
    assert page.status_code == 200
    assert "Result Cards" in page.text
    assert "Evidence details (collapsed by default)" in page.text
    assert "<details>" in page.text
    assert "Phase-0" in page.text
    assert "Phase-4" in page.text

    sess_doc = client.get(f"/workbench/sessions/{session_id}").json()
    cards = sess_doc.get("cards")
    assert isinstance(cards, list)
    phase_set = {str(card.get("phase")) for card in cards if isinstance(card, dict)}
    assert {"idea", "strategy_spec", "trace_preview", "runspec", "improvements"}.issubset(phase_set)

    events_path = art_root / "workbench" / "sessions" / session_id / "events.jsonl"
    assert events_path.is_file()
    rows = [json.loads(ln) for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows
    assert [int(ev["event_index"]) for ev in rows] == list(range(1, len(rows) + 1))
