from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from quant_eam.api.security import require_safe_id
from quant_eam.data_lake.timeutil import parse_iso_datetime
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.snapshots.catalog import SnapshotCatalog

router = APIRouter()


def _data_root() -> Path:
    return Path(os.getenv("EAM_DATA_ROOT", "/data"))


@router.get("/snapshots")
def list_snapshots() -> dict[str, Any]:
    cat = SnapshotCatalog(root=_data_root())
    out: list[dict[str, Any]] = []
    for rec in cat.list_snapshots():
        try:
            snap = cat.load_snapshot(rec.snapshot_id)
        except Exception:
            # Skip broken snapshots from listing.
            continue
        man = snap.get("manifest") if isinstance(snap.get("manifest"), dict) else {}
        datasets = man.get("datasets") if isinstance(man.get("datasets"), list) else []
        ds_out: list[dict[str, Any]] = []
        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            syms = ds.get("symbols") if isinstance(ds.get("symbols"), list) else []
            ds_out.append(
                {
                    "dataset_id": ds.get("dataset_id"),
                    "row_count": ds.get("row_count"),
                    "symbols_count": len(syms),
                    "dt_min": ds.get("dt_min"),
                    "dt_max": ds.get("dt_max"),
                    "sha256": ds.get("sha256"),
                }
            )
        out.append(
            {
                "snapshot_id": rec.snapshot_id,
                "created_at": man.get("created_at", rec.created_at),
                "datasets": ds_out,
                "has_quality": bool(snap.get("quality_report")),
                "has_ingest_manifest": bool(snap.get("ingest_manifest")),
            }
        )
    return {"snapshots": out}


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str) -> dict[str, Any]:
    snapshot_id = require_safe_id(snapshot_id, kind="snapshot_id")
    cat = SnapshotCatalog(root=_data_root())
    try:
        snap = cat.load_snapshot(snapshot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return snap


@router.get("/snapshots/{snapshot_id}/quality")
def get_snapshot_quality(snapshot_id: str) -> dict[str, Any]:
    snapshot_id = require_safe_id(snapshot_id, kind="snapshot_id")
    cat = SnapshotCatalog(root=_data_root())
    try:
        snap = cat.load_snapshot(snapshot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    q = snap.get("quality_report")
    if not isinstance(q, dict):
        raise HTTPException(status_code=404, detail="quality_report not found")
    return {"snapshot_id": snapshot_id, "quality_report": q}


@router.get("/snapshots/{snapshot_id}/preview/ohlcv")
def preview_ohlcv(
    snapshot_id: str,
    symbols: str,
    start: str,
    end: str,
    as_of: str,
    limit: int = 200,
) -> dict[str, Any]:
    snapshot_id = require_safe_id(snapshot_id, kind="snapshot_id")
    syms = [s.strip() for s in str(symbols).split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="symbols must be non-empty")
    if not start.strip() or not end.strip():
        raise HTTPException(status_code=400, detail="start/end required")
    try:
        # Accept tz-naive as_of and interpret as +08:00 per timeutil.
        _ = parse_iso_datetime(as_of)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid as_of")

    if limit <= 0:
        limit = 200
    limit = min(int(limit), 2000)

    dc = DataCatalog(root=_data_root())
    try:
        rows, stats = dc.query_ohlcv(snapshot_id=snapshot_id, symbols=syms, start=start, end=end, as_of=as_of)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="snapshot/dataset not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "snapshot_id": snapshot_id,
        "dataset_id": "ohlcv_1d",
        "rows": rows[:limit],
        "stats": {"rows_before_asof": stats.rows_before_asof, "rows_after_asof": stats.rows_after_asof},
    }

