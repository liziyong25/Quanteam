from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_phase11_idea_intent_two_checkpoints_then_report(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snapshot_id = "demo_snap_idea_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Demo",
        "hypothesis_text": "Buy and hold should produce stable deterministic artifacts.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "demo_e2e",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }

    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # Worker should run IntentAgent and stop at blueprint checkpoint (no dossier created).
    assert worker_main(["--run-jobs", "--once"]) == 0
    dossiers_dir = art_root / "dossiers"
    assert (not dossiers_dir.exists()) or (len([p for p in dossiers_dir.glob("*")]) == 0)

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "BLUEPRINT_PROPOSED" for ev in evs)
    assert any(ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "blueprint" for ev in evs)

    outputs = r.json().get("outputs") or {}
    bp_path = Path(outputs["blueprint_draft_path"])
    assert bp_path.is_file()
    code, _ = contracts_validate.validate_json(bp_path)
    assert code == contracts_validate.EXIT_OK

    # Approve blueprint and advance to strategy_spec checkpoint.
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "STRATEGY_SPEC_PROPOSED" for ev in evs)
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "strategy_spec" for ev in evs
    )

    outputs = r.json().get("outputs") or {}
    # StrategySpec artifacts validate.
    for k in ("blueprint_final_path", "signal_dsl_path", "variable_dictionary_path", "calc_trace_plan_path", "strategy_spec_agent_run_path"):
        p = Path(outputs[k])
        assert p.is_file(), k
        code, _ = contracts_validate.validate_json(p)
        assert code == contracts_validate.EXIT_OK, (k, p)

    # Approve strategy_spec and advance to runspec checkpoint.
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "strategy_spec"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "RUNSPEC_COMPILED" for ev in evs)
    assert any(ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "runspec" for ev in evs)

    outputs = r.json().get("outputs") or {}
    runspec_path = Path(outputs["runspec_path"])
    assert runspec_path.is_file()
    code, _ = contracts_validate.validate_json(runspec_path)
    assert code == contracts_validate.EXIT_OK

    # Approve runspec and advance to trace_preview checkpoint (still no dossier).
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "runspec"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "TRACE_PREVIEW_COMPLETED" for ev in evs)
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "trace_preview" for ev in evs
    )

    dossiers_dir = art_root / "dossiers"
    assert (not dossiers_dir.exists()) or (len([p for p in dossiers_dir.glob("*")]) == 0)

    outputs = r.json().get("outputs") or {}
    tp = Path(outputs["calc_trace_preview_path"])
    tm = Path(outputs["trace_meta_path"])
    assert tp.is_file()
    assert tm.is_file()
    # Preview should contain lag effect and eligible(as_of) correctness.
    import csv

    with tp.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert all(r.get("eligible") == "true" for r in rows)
    assert any(r.get("entry_raw") == "true" and r.get("entry_lagged") == "false" for r in rows)

    meta = json.loads(tm.read_text(encoding="utf-8"))
    assert int(meta.get("rows_written", 0)) == len(rows)

    # Approve trace preview and complete job to DONE.
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "trace_preview"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "REPORT_COMPLETED" for ev in evs)
    assert any(ev.get("event_type") == "IMPROVEMENTS_PROPOSED" for ev in evs)
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "improvements" for ev in evs
    )

    outputs = r.json().get("outputs") or {}
    dossier_dir = Path(outputs["dossier_path"])
    assert dossier_dir.is_dir()
    assert (dossier_dir / "gate_results.json").is_file()
    assert (dossier_dir / "metrics.json").is_file()

    # Contracts validate for key evidence.
    assert contracts_validate.validate_json(dossier_dir / "dossier_manifest.json")[0] == contracts_validate.EXIT_OK
    assert contracts_validate.validate_json(dossier_dir / "gate_results.json")[0] == contracts_validate.EXIT_OK

    # Agent outputs exist and agent_run.json validates.
    agent_run = Path(outputs["report_agent_run_path"])
    assert agent_run.is_file()
    assert contracts_validate.validate_json(agent_run)[0] == contracts_validate.EXIT_OK
    assert Path(outputs["report_md_path"]).is_file()
    assert Path(outputs["report_summary_path"]).is_file()

    # Registry updated evidence exists.
    trial_log = reg_root / "trial_log.jsonl"
    assert trial_log.is_file()
    run_id = str(outputs.get("run_id"))
    assert run_id in trial_log.read_text(encoding="utf-8")

    # Approve improvements (acknowledge) and finish job to DONE.
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "improvements"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "DONE" for ev in evs)

    # UI must expose LLM evidence (read-only) for agent runs.
    r = client.get(f"/ui/jobs/{job_id}")
    assert r.status_code == 200
    assert "LLM Evidence" in r.text
