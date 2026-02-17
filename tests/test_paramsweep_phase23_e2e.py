from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.lake import DataLake
from quant_eam.worker.main import main as worker_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_budget_policy(tmp_path: Path) -> Path:
    p = tmp_path / "budget_policy_v1_sweep_test.yaml"
    p.write_text(
        "\n".join(
            [
                "policy_id: budget_policy_v1_sweep_test",
                'policy_version: "v1"',
                "title: Budget Policy v1 (sweep test)",
                "description: test budget",
                "params:",
                "  max_proposals_per_job: 3",  # used as max_trials default
                "  max_spawn_per_job: 3",
                "  max_total_iterations: 10",
                "  stop_if_no_improvement_n: 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return p


def _write_custom_snapshot(data_root: Path, snapshot_id: str) -> None:
    lake = DataLake(root=data_root)
    dts = [f"2024-01-{day:02d}" for day in range(1, 21)]
    # Regime switching close series to create SMA crossovers.
    closes = [1, 1, 1, 1, 10, 10, 10, 10, 1, 1, 1, 1, 10, 10, 10, 10, 1, 1, 1, 1]
    rows = []
    for dt, c in zip(dts, closes, strict=True):
        rows.append(
            {
                "symbol": "AAA",
                "dt": dt,
                "open": float(c),
                "high": float(c) + 0.1,
                "low": float(c) - 0.1,
                "close": float(c),
                "volume": 1000.0,
                "source": "phase23",
            }
        )
    _ = lake.write_ohlcv_1d_snapshot(snapshot_id=snapshot_id, rows=rows)


def _blueprint_with_sweep(*, budget_path: Path) -> dict:
    return {
        "schema_version": "blueprint_v1",
        "blueprint_id": "blueprint_phase23_sweep_v1",
        "title": "Phase-23 Sweep Demo",
        "description": "MA crossover strategy; params are swept by orchestrator.",
        "policy_bundle_id": "policy_bundle_v1_default",
        "universe": {"asset_pack": "demo", "symbols": ["AAA"], "timezone": "Asia/Taipei", "calendar": "DEMO"},
        "bar_spec": {"frequency": "1d"},
        "data_requirements": [
            {
                "dataset_id": "ohlcv_1d",
                "fields": ["open", "high", "low", "close", "volume", "available_at"],
                "frequency": "1d",
                "adjustment": "none",
                "asof_rule": {"mode": "asof"},
            }
        ],
        "strategy_spec": {
            "dsl_version": "signal_dsl_v1",
            "signals": {"entry": "entry", "exit": "exit"},
            "expressions": {
                "sma_fast": {
                    "type": "op",
                    "op": "sma",
                    "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "fast"}],
                },
                "sma_slow": {
                    "type": "op",
                    "op": "sma",
                    "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "slow"}],
                },
                "entry": {"type": "op", "op": "cross_above", "args": [{"type": "var", "var_id": "sma_fast"}, {"type": "var", "var_id": "sma_slow"}]},
                "exit": {"type": "op", "op": "cross_below", "args": [{"type": "var", "var_id": "sma_fast"}, {"type": "var", "var_id": "sma_slow"}]},
            },
            "params": {"fast": 2, "slow": 4},
            "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
            "extensions": {"engine_contract": "vectorbt_signal_v1", "strategy_id": "ma_sweep"},
        },
        "evaluation_protocol": {
            "segments": {
                "train": {"start": "2024-01-01", "end": "2024-01-16"},
                "test": {"start": "2024-01-01", "end": "2024-01-16"},
                "holdout": {"start": "2024-01-17", "end": "2024-01-20"},
            },
            "purge": {"bars": 0},
            "embargo": {"bars": 0},
            "gate_suite_id": "gate_suite_v1_default",
        },
        "report_spec": {"plots": False, "tables": True, "trace": False},
        "extensions": {
            "sweep_spec": {
                "param_grid": {"fast": [2, 3], "slow": [4, 5]},
                "metric": "total_return",
                "higher_is_better": True,
                "max_trials": 3,
                "budget_policy_path": str(budget_path),
            }
        },
    }


def test_phase23_budgeted_paramsweep_and_spawn_best(tmp_path: Path, monkeypatch) -> None:
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

    snap = "snap_phase23_001"
    _write_custom_snapshot(data_root, snap)
    budget_path = _write_budget_policy(tmp_path)

    client = TestClient(app)
    bp = _blueprint_with_sweep(budget_path=budget_path)
    r = client.post(
        "/jobs/blueprint",
        params={"snapshot_id": snap, "policy_bundle_path": "policies/policy_bundle_v1.yaml"},
        json=bp,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # Advance to blueprint approval.
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"}).status_code == 200

    # This pass should compile->run->gates->registry then block at sweep checkpoint.
    assert worker_main(["--run-jobs", "--once"]) == 0
    job_doc = client.get(f"/jobs/{job_id}").json()
    evs = job_doc["events"]
    assert any(ev.get("event_type") == "REGISTRY_UPDATED" for ev in evs)
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "sweep"
        for ev in evs
    )

    # Approve sweep and run once.
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "sweep"}).status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    # Sweep evidence must exist under job outputs.
    sweep_dir = job_root / job_id / "outputs" / "sweep"
    trials_path = sweep_dir / "trials.jsonl"
    lb_path = sweep_dir / "leaderboard.json"
    assert trials_path.is_file()
    assert lb_path.is_file()

    # Budget stop must be evidence-logged (grid_total=4, max_trials=3).
    evs2 = client.get(f"/jobs/{job_id}").json()["events"]
    stop = [ev for ev in evs2 if ev.get("event_type") == "STOPPED_BUDGET"]
    assert stop
    assert any((ev.get("outputs") or {}).get("reason") == "max_trials" for ev in stop)

    # Validate sweep trials contract for each line.
    trial_lines = [ln for ln in trials_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(trial_lines) == 3
    sweep_trial_schema = _repo_root() / "contracts" / "sweep_trial_schema_v1.json"
    for ln in trial_lines:
        doc = json.loads(ln)
        code, msg = contracts_validate.validate_payload(doc, schema_path=sweep_trial_schema)
        assert code == contracts_validate.EXIT_OK, msg

    # Validate leaderboard contract.
    leaderboard_schema = _repo_root() / "contracts" / "leaderboard_schema_v1.json"
    lb_doc = json.loads(lb_path.read_text(encoding="utf-8"))
    code, msg = contracts_validate.validate_payload(lb_doc, schema_path=leaderboard_schema)
    assert code == contracts_validate.EXIT_OK, msg
    assert lb_doc["schema_version"] == "leaderboard_v1"
    assert lb_doc["grid_total"] == 4
    assert lb_doc["max_trials"] == 3

    # Spawn best candidate.
    r2 = client.post(f"/jobs/{job_id}/spawn_best")
    assert r2.status_code == 200, r2.text
    child_job_id = r2.json()["child_job_id"]
    assert isinstance(child_job_id, str) and len(child_job_id) == 12

    # Child job must carry lineage and updated params.
    child_spec = json.loads((job_root / child_job_id / "job_spec.json").read_text(encoding="utf-8"))
    ext = child_spec.get("extensions") if isinstance(child_spec, dict) else {}
    lineage = ext.get("lineage") if isinstance(ext, dict) else {}
    assert isinstance(lineage, dict)
    assert lineage.get("root_job_id") == job_id
    assert lineage.get("parent_job_id") == job_id
    assert int(lineage.get("generation")) == 1

    best_params = (lb_doc.get("best") or {}).get("params")
    assert isinstance(best_params, dict) and best_params
    bp_child = child_spec.get("blueprint")
    assert isinstance(bp_child, dict)
    strat = bp_child.get("strategy_spec")
    assert isinstance(strat, dict)
    params_child = strat.get("params")
    assert isinstance(params_child, dict)
    for k, v in best_params.items():
        assert params_child.get(k) == v

    # Child job must return to blueprint approval checkpoint (no auto-run).
    assert worker_main(["--run-jobs", "--once"]) == 0
    evs_child = client.get(f"/jobs/{child_job_id}").json()["events"]
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "blueprint"
        for ev in evs_child
    )
