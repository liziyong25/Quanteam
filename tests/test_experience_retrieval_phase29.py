from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.agents.intent_agent import run_intent_agent
from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.index.indexer import build_all_indexes
from quant_eam.registry.experience_retrieval import ExperienceQuery, search_experience_cards


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_phase29_search_ranking_stable_and_job_ui_renders_pack(tmp_path: Path, monkeypatch) -> None:
    # Layout: artifacts root contains dossiers + registry; jobs root separate.
    art = tmp_path / "artifacts"
    reg = art / "registry"
    dossiers = art / "dossiers"
    jobs = tmp_path / "jobs"
    (reg / "cards").mkdir(parents=True, exist_ok=True)
    dossiers.mkdir(parents=True, exist_ok=True)
    jobs.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg))
    monkeypatch.setenv("EAM_JOB_ROOT", str(jobs))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    # Create two runs/dossiers.
    def make_run(run_id: str, symbols: list[str], title: str) -> None:
        d = dossiers / run_id
        d.mkdir(parents=True, exist_ok=True)
        _write_json(d / "dossier_manifest.json", {"schema_version": "dossier_v1", "run_id": run_id, "data_snapshot_id": "snap_x", "policy_bundle_id": "policy_bundle_v1_default"})
        _write_json(
            d / "config_snapshot.json",
            {
                "policy_bundle_id": "policy_bundle_v1_default",
                "runspec": {"policy_bundle_id": "policy_bundle_v1_default", "extensions": {"symbols": symbols}},
            },
        )
        _write_json(d / "metrics.json", {"total_return": 0.1})
        _write_json(d / "gate_results.json", {"schema_version": "gate_results_v1", "overall_pass": True, "results": [], "holdout_summary": {"pass": True, "summary": ""}})
        # Optional attribution evidence.
        _write_json(d / "attribution_report.json", {"schema_version": "attribution_report_v1", "run_id": run_id, "created_at": "x", "returns": {"net_return": 0.1}, "drawdown": {"max_drawdown": 0.0, "dd_duration_bars": 0, "top_dd_points": []}, "trades": {"trade_count": 0}, "evidence_refs": {"curve": "curve.csv", "trades": "trades.csv", "metrics": "metrics.json", "config_snapshot": "config_snapshot.json"}})

        # Registry card for this run.
        cdir = reg / "cards" / f"card_{run_id}"
        cdir.mkdir(parents=True, exist_ok=True)
        _write_json(
            cdir / "card_v1.json",
            {
                "schema_version": "experience_card_v1",
                "card_id": f"card_{run_id}",
                "created_at": "2024-01-01T00:00:00Z",
                "title": title,
                "status": "draft",
                "primary_run_id": run_id,
                "policy_bundle_id": "policy_bundle_v1_default",
                "evidence": {
                    "run_id": run_id,
                    "dossier_path": str(d),
                    "gate_results_path": str(d / "gate_results.json"),
                    "key_artifacts": ["metrics.json", "gate_results.json"],
                },
                "applicability": {"freq": "ohlcv_1d"},
                "extensions": {"tags": ["buyhold", "demo"] if "Buy" in title else ["rsi", "meanrev"]},
            },
        )
        (cdir / "events.jsonl").write_text("", encoding="utf-8")

    make_run("aaaa1111bbbb", ["AAA", "BBB"], "Buy Hold Demo")
    make_run("cccc2222dddd", ["CCC"], "RSI Mean Reversion")

    # Build Phase-25 index (so retrieval can use it).
    _ = build_all_indexes(artifact_root_dir=art)

    q = ExperienceQuery(query="buy hold AAA", symbols=["AAA"], frequency="ohlcv_1d", tags=["demo"], top_k=5)
    res = search_experience_cards(q=q, reg_root=reg)
    assert res
    # Stable: the buy/hold + AAA match must come first.
    assert res[0].card_id == "card_aaaa1111bbbb"

    # Create a job (idea_spec_v1 as job_spec.json) and run IntentAgent on it.
    job_id = "111122223333"
    job_dir = jobs / job_id
    (job_dir / "outputs" / "agents" / "intent").mkdir(parents=True, exist_ok=True)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Buy Hold Demo",
        "hypothesis_text": "AAA buy and hold",
        "symbols": ["AAA"],
        "frequency": "ohlcv_1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase29",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    _write_json(job_dir / "job_spec.json", idea)

    _ = run_intent_agent(input_path=job_dir / "job_spec.json", out_dir=job_dir / "outputs" / "agents" / "intent", provider="mock")

    pack_path = job_dir / "outputs" / "experience" / "experience_pack.json"
    assert pack_path.is_file()

    schema = Path(__file__).resolve().parents[1] / "contracts" / "experience_pack_schema_v1.json"
    code, msg = contracts_validate.validate_json(pack_path, schema_path=schema)
    assert code == contracts_validate.EXIT_OK, msg

    client = TestClient(app)
    r = client.get(f"/ui/jobs/{job_id}")
    assert r.status_code == 200
    assert "ExperiencePack" in r.text
    assert "card_aaaa1111bbbb" in r.text

