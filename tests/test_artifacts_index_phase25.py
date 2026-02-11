from __future__ import annotations

import json
from pathlib import Path

from quant_eam.index.indexer import build_all_indexes, index_paths


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            rows.append(json.loads(ln))
    return rows


def test_phase25_indexer_append_only_and_stable(tmp_path: Path, monkeypatch) -> None:
    art = tmp_path / "artifacts"
    reg = art / "registry"
    jobs = art / "jobs"
    dossiers = art / "dossiers"
    (reg / "cards").mkdir(parents=True, exist_ok=True)
    jobs.mkdir(parents=True, exist_ok=True)
    dossiers.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg))
    monkeypatch.setenv("EAM_JOB_ROOT", str(jobs))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    # Fake dossiers.
    r1 = dossiers / "aaaa1111bbbb"
    r2 = dossiers / "cccc2222dddd"
    for d, snap, pb, overall in (
        (r1, "snap_001", "bundle_001", True),
        (r2, "snap_002", "bundle_002", False),
    ):
        d.mkdir(parents=True, exist_ok=True)
        _write_json(d / "dossier_manifest.json", {"schema_version": "dossier_v1", "run_id": d.name, "data_snapshot_id": snap, "policy_bundle_id": pb})
        _write_json(d / "config_snapshot.json", {"policy_bundle_id": pb, "runspec": {"policy_bundle_id": pb}})
        _write_json(d / "gate_results.json", {"schema_version": "gate_results_v1", "overall_pass": overall, "results": []})

    # Registry card pointing to r1.
    _write_json(reg / "cards" / "card_aaaa1111bbbb.json", {"schema_version": "experience_card_v1", "card_id": "card_aaaa1111bbbb", "primary_run_id": "aaaa1111bbbb"})

    # Fake job.
    j1 = jobs / "job_000000000001"
    (j1 / "outputs").mkdir(parents=True, exist_ok=True)
    _write_json(j1 / "job_spec.json", {"schema_version": "job_spec_v1", "snapshot_id": "snap_001", "policy_bundle_id": "bundle_001", "blueprint": {"schema_version": "blueprint_v1", "policy_bundle_id": "bundle_001"}})
    _append_jsonl(j1 / "events.jsonl", {"schema_version": "job_event_v2", "job_id": "job_000000000001", "event_type": "WAITING_APPROVAL", "outputs": {"step": "blueprint"}, "extensions": {"recorded_at": "2024-01-01T00:00:00Z"}})
    _write_json(j1 / "outputs" / "outputs.json", {"intent_agent_run_path": str(j1 / "outputs" / "agents" / "intent" / "agent_run.json")})

    # Build indexes.
    res1 = build_all_indexes(artifact_root_dir=art)
    assert res1["runs"]["indexed"] == 2
    assert res1["jobs"]["indexed"] == 1

    idxp = index_paths(artifact_root_dir=art)
    assert idxp.runs_index.is_file()
    assert idxp.jobs_index.is_file()

    runs_rows = _read_jsonl(idxp.runs_index)
    assert [r["run_id"] for r in runs_rows] == ["aaaa1111bbbb", "cccc2222dddd"]
    assert runs_rows[0]["card_ids"] == ["card_aaaa1111bbbb"]
    assert runs_rows[0]["dossier_path"] == "dossiers/aaaa1111bbbb"

    jobs_rows = _read_jsonl(idxp.jobs_index)
    assert jobs_rows[0]["job_id"] == "job_000000000001"
    assert jobs_rows[0]["state"]["waiting_step"] == "blueprint"
    assert jobs_rows[0]["job_dir"] == "jobs/job_000000000001"

    # Re-run: must not append duplicates (id-dedup).
    res2 = build_all_indexes(artifact_root_dir=art)
    assert res2["runs"]["indexed"] == 0
    assert res2["jobs"]["indexed"] == 0
    assert len(_read_jsonl(idxp.runs_index)) == 2
    assert len(_read_jsonl(idxp.jobs_index)) == 1

