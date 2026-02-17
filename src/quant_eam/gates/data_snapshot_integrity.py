from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from quant_eam.gates.types import GateContext, GateEvidence, GateResult
from quant_eam.snapshots.catalog import SnapshotCatalog, safe_snapshot_id


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_dataset(manifest: dict[str, Any], dataset_id: str) -> dict[str, Any] | None:
    dss = manifest.get("datasets")
    if not isinstance(dss, list):
        return None
    for ds in dss:
        if isinstance(ds, dict) and str(ds.get("dataset_id")) == dataset_id:
            return ds
    # Fallback: first dataset if present.
    for ds in dss:
        if isinstance(ds, dict):
            return ds
    return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_data_snapshot_integrity_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    """Anti-tamper + self-consistency gate for DataLake snapshots.

    Deterministic rules (v1):
    - Snapshot manifest / ingest_manifest / quality_report must be contract-valid.
    - Recompute dataset CSV sha256 and match manifest + ingest_manifest (if present).
    - Enforce minimal self-consistency between manifest and quality_report.
    """
    _ = params or {}

    # Evidence anchor: snapshot_id comes from the run evidence (runspec/dossier_manifest).
    snapshot_id_raw = str(ctx.runspec.get("data_snapshot_id", "")).strip()
    if not snapshot_id_raw:
        snapshot_id_raw = str(ctx.dossier_manifest.get("data_snapshot_id", "")).strip()
    if not snapshot_id_raw:
        return GateResult(
            gate_id="data_snapshot_integrity_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"reason": "missing snapshot_id in runspec.data_snapshot_id / dossier_manifest.data_snapshot_id"},
            evidence=GateEvidence(artifacts=["config_snapshot.json", "dossier_manifest.json"]),
        )

    try:
        snapshot_id = safe_snapshot_id(snapshot_id_raw)
    except Exception:
        return GateResult(
            gate_id="data_snapshot_integrity_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"reason": "invalid snapshot_id format", "snapshot_id": snapshot_id_raw},
            evidence=GateEvidence(artifacts=["config_snapshot.json", "dossier_manifest.json"]),
        )

    data_root = Path(os.getenv("EAM_DATA_ROOT", "/data"))
    cat = SnapshotCatalog(root=data_root)

    errors: list[str] = []
    try:
        snap = cat.load_snapshot(snapshot_id)
    except FileNotFoundError:
        errors.append("snapshot not found under EAM_DATA_ROOT/lake")
        snap = {"paths": {}, "manifest": {}, "ingest_manifest": None, "quality_report": None}
    except Exception as e:  # noqa: BLE001
        errors.append(f"snapshot contract validation failed: {e}")
        snap = {"paths": {}, "manifest": {}, "ingest_manifest": None, "quality_report": None}

    paths = snap.get("paths") if isinstance(snap.get("paths"), dict) else {}
    manifest = snap.get("manifest") if isinstance(snap.get("manifest"), dict) else {}
    ingest_manifest = snap.get("ingest_manifest") if isinstance(snap.get("ingest_manifest"), dict) else None
    quality_report = snap.get("quality_report") if isinstance(snap.get("quality_report"), dict) else None

    missing_ingest_manifest = ingest_manifest is None
    if quality_report is None:
        errors.append("missing quality_report.json")

    ds = _find_dataset(manifest, "ohlcv_1d") if manifest else None
    if ds is None:
        errors.append("manifest missing datasets[] entry")
        data_file = None
        manifest_sha = None
        manifest_row_count = None
        manifest_dt_min = None
        manifest_dt_max = None
        manifest_av_min = None
        manifest_av_max = None
    else:
        file_s = str(ds.get("file") or "").strip()
        data_file = Path(file_s) if file_s else None
        manifest_sha = str(ds.get("sha256") or "")
        manifest_row_count = ds.get("row_count")
        manifest_dt_min = ds.get("dt_min")
        manifest_dt_max = ds.get("dt_max")
        manifest_av_min = ds.get("available_at_min")
        manifest_av_max = ds.get("available_at_max")

        if data_file is None or (not data_file.is_file()):
            errors.append("data file missing (manifest.datasets[].file not found)")

    actual_sha = None
    if data_file and data_file.is_file():
        try:
            actual_sha = _sha256_file(data_file)
        except Exception as e:  # noqa: BLE001
            errors.append(f"failed to hash data file: {e}")

    if actual_sha and manifest_sha and actual_sha != manifest_sha:
        errors.append("sha256 mismatch: manifest.datasets[].sha256 != sha256(data_file)")

    ingest_sha = None
    if ingest_manifest is not None:
        ingest_sha = str(ingest_manifest.get("sha256_of_data_file") or "")
        if actual_sha and ingest_sha and actual_sha != ingest_sha:
            errors.append("sha256 mismatch: ingest_manifest.sha256_of_data_file != sha256(data_file)")

    # Self-consistency checks.
    if quality_report is not None and ds is not None:
        qr_rows = quality_report.get("rows_after_dedupe")
        if isinstance(qr_rows, int) and isinstance(manifest_row_count, int) and qr_rows != manifest_row_count:
            errors.append("row_count mismatch: quality_report.rows_after_dedupe != manifest.datasets[].row_count")

        def _cmp(name: str, a: Any, b: Any) -> None:
            if a in (None, "") or b in (None, ""):
                return
            if str(a) != str(b):
                errors.append(f"{name} mismatch between quality_report and manifest")

        _cmp("dt_min", quality_report.get("dt_min"), manifest_dt_min)
        _cmp("dt_max", quality_report.get("dt_max"), manifest_dt_max)
        _cmp("available_at_min", quality_report.get("available_at_min"), manifest_av_min)
        _cmp("available_at_max", quality_report.get("available_at_max"), manifest_av_max)

    passed = not errors
    metrics: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "missing_ingest_manifest": bool(missing_ingest_manifest),
        "manifest_sha256": manifest_sha,
        "ingest_manifest_sha256": ingest_sha,
        "actual_sha256": actual_sha,
        "manifest_row_count": manifest_row_count,
        "quality_rows_after_dedupe": (quality_report.get("rows_after_dedupe") if isinstance(quality_report, dict) else None),
    }
    if errors:
        metrics["errors"] = errors

    evidence_artifacts = [
        str(paths.get("manifest") or ""),
        str(paths.get("ingest_manifest") or ""),
        str(paths.get("quality_report") or ""),
        (data_file.as_posix() if isinstance(data_file, Path) else ""),
    ]
    evidence_artifacts = [x for x in evidence_artifacts if x]

    return GateResult(
        gate_id="data_snapshot_integrity_v1",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=metrics,
        evidence=GateEvidence(
            artifacts=evidence_artifacts,
            notes="validates snapshot manifest/ingest_manifest/quality_report contracts and sha256 integrity; enforces minimal self-consistency for replay",
        ),
    )
