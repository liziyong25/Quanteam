from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.compiler.compile import EXIT_OK as COMPILE_OK
from quant_eam.compiler.compile import compile_blueprint_to_runspec
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import EXIT_OK as GATE_OK
from quant_eam.gaterunner.run import run_once as gaterunner_run_once
from quant_eam.runner.run import EXIT_OK as RUN_OK
from quant_eam.runner.run import run_once as runner_run_once


def test_phase21_walk_forward_segments_end_to_end(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    artifact_root = tmp_path / "artifacts"
    data_root.mkdir()
    artifact_root.mkdir()

    snapshot_id = "snap_phase21_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    bp = json.loads((Path("contracts/examples/blueprint_buyhold_demo_ok.json")).read_text(encoding="utf-8"))
    ep = bp["evaluation_protocol"]
    # Narrow test range so walk-forward has valid train windows.
    ep["segments"]["train"] = {"start": "2024-01-01", "end": "2024-01-10"}
    ep["segments"]["test"] = {"start": "2024-01-05", "end": "2024-01-10"}
    ep["segments"]["holdout"] = {"start": "2024-01-08", "end": "2024-01-10"}
    ep["protocol"] = "walk_forward"
    ep["train_window_days"] = 4
    ep["test_window_days"] = 3
    ep["step_days"] = 2
    ep["purge_days"] = 1
    ep["embargo_days"] = 1
    ep["holdout_range"] = {"start": "2024-01-08", "end": "2024-01-10"}

    bp_path = tmp_path / "bp.json"
    bp_path.write_text(json.dumps(bp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runspec_path = tmp_path / "runspec.json"

    code, _msg = compile_blueprint_to_runspec(
        blueprint_path=bp_path,
        snapshot_id=snapshot_id,
        policy_bundle_path=Path("policies/policy_bundle_v1.yaml"),
        out_path=runspec_path,
        check_availability=False,
        data_root=data_root,
    )
    assert code == COMPILE_OK
    runspec = json.loads(runspec_path.read_text(encoding="utf-8"))
    seg_list = (runspec.get("segments") or {}).get("list")
    assert isinstance(seg_list, list) and len(seg_list) >= 3

    # Purge/embargo must be reflected in first walk-forward slice.
    t0 = next(s for s in seg_list if s.get("segment_id") == "test_000")
    tr0 = next(s for s in seg_list if s.get("segment_id") == "train_000")
    assert t0["start"] == "2024-01-06"  # test start 2024-01-05 + purge_days(1)
    assert tr0["end"] == "2024-01-03"  # train end 2024-01-04 - embargo_days(1)
    h0 = next(s for s in seg_list if s.get("segment_id") == "holdout_000")
    assert bool(h0.get("holdout")) is True

    code2, msg2 = runner_run_once(
        runspec_path=runspec_path,
        policy_bundle_path=Path("policies/policy_bundle_v1.yaml"),
        snapshot_id_override=None,
        data_root=data_root,
        artifact_root=artifact_root,
        behavior_if_exists="noop",
    )
    assert code2 == RUN_OK, msg2
    out = json.loads(msg2)
    run_id = out["run_id"]
    dossier_dir = Path(out["dossier_path"])
    assert dossier_dir.is_dir()
    assert (dossier_dir / "segments_summary.json").is_file()

    # Segment artifacts exist for non-holdout segments; holdout must not write curve/trades.
    assert (dossier_dir / "segments" / "test_000" / "curve.csv").is_file()
    assert (dossier_dir / "segments" / "test_000" / "trades.csv").is_file()
    assert (dossier_dir / "segments" / "test_000" / "metrics.json").is_file()

    holdout_seg_dir = dossier_dir / "segments" / "holdout_000"
    if holdout_seg_dir.exists():
        assert not (holdout_seg_dir / "curve.csv").exists()
        assert not (holdout_seg_dir / "trades.csv").exists()

    code3, msg3 = gaterunner_run_once(dossier_dir=dossier_dir, policy_bundle_path=Path("policies/policy_bundle_v1.yaml"))
    assert code3 == GATE_OK, msg3
    gate_results = json.loads((dossier_dir / "gate_results.json").read_text(encoding="utf-8"))
    assert "holdout_summary" in gate_results
    seg_res = gate_results.get("segment_results") if isinstance(gate_results.get("segment_results"), list) else None
    if seg_res is None:
        exts = gate_results.get("extensions") if isinstance(gate_results.get("extensions"), dict) else {}
        seg_res = exts.get("segment_results") if isinstance(exts.get("segment_results"), list) else None
    assert isinstance(seg_res, list) and len(seg_res) >= 1
    # Holdout segment result must not reference curve/trades artifacts.
    for sr in seg_res:
        if not isinstance(sr, dict):
            continue
        if sr.get("kind") == "holdout":
            arts = sr.get("artifacts") if isinstance(sr.get("artifacts"), dict) else {}
            assert "curve" not in arts and "trades" not in arts

    # UI: segments selector + holdout minimal-only.
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    client = TestClient(app)
    r = client.get(f"/ui/runs/{run_id}?segment_id=test_000")
    assert r.status_code == 200
    assert "Segments" in r.text
    assert "test_000" in r.text

    r2 = client.get(f"/ui/runs/{run_id}?segment_id=holdout_000")
    assert r2.status_code == 200
    assert "Holdout (Minimal Summary)" in r2.text
    # Must not render curve/candles sections in holdout view.
    assert "Equity Curve" not in r2.text
