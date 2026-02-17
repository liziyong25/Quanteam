from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate


_SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def safe_snapshot_id(snapshot_id: str) -> str:
    s = str(snapshot_id)
    if not _SNAPSHOT_ID_RE.match(s):
        raise ValueError("invalid snapshot_id")
    return s


def _data_root() -> Path:
    return Path(os.getenv("EAM_DATA_ROOT", "/data"))


def _lake_root(root: Path | None = None) -> Path:
    r = root or _data_root()
    return Path(r) / "lake"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso_maybe(s: str) -> tuple[bool, datetime | None]:
    try:
        return True, datetime.fromisoformat(s)
    except Exception:
        return False, None


@dataclass(frozen=True)
class SnapshotRecord:
    snapshot_id: str
    created_at: str
    manifest_path: Path
    ingest_manifest_path: Path | None
    quality_report_path: Path | None


class SnapshotCatalog:
    """Read-only snapshot catalog backed by DataLake directory layout."""

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else _data_root()

    def list_snapshots(self) -> list[SnapshotRecord]:
        lake = _lake_root(self.root)
        if not lake.is_dir():
            return []

        recs: list[SnapshotRecord] = []
        for d in sorted([p for p in lake.iterdir() if p.is_dir()], key=lambda p: p.name):
            sid = d.name
            if not _SNAPSHOT_ID_RE.match(sid):
                continue
            manifest_path = d / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                man = _load_json(manifest_path)
            except Exception:
                continue
            created_at = str(man.get("created_at", "")).strip()
            if not created_at:
                created_at = "unknown"

            ing = d / "ingest_manifest.json"
            q = d / "quality_report.json"
            recs.append(
                SnapshotRecord(
                    snapshot_id=sid,
                    created_at=created_at,
                    manifest_path=manifest_path,
                    ingest_manifest_path=ing if ing.is_file() else None,
                    quality_report_path=q if q.is_file() else None,
                )
            )

        # Stable sort: created_at (if parseable) then snapshot_id.
        def key(r: SnapshotRecord) -> tuple[int, str, str]:
            ok, dt = _parse_iso_maybe(r.created_at)
            if ok and dt is not None:
                return (0, dt.isoformat(), r.snapshot_id)
            return (1, r.created_at, r.snapshot_id)

        recs.sort(key=key)
        return recs

    def load_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        sid = safe_snapshot_id(snapshot_id)
        snap_dir = _lake_root(self.root) / sid
        if not snap_dir.is_dir():
            raise FileNotFoundError("snapshot not found")

        manifest_path = snap_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError("manifest.json not found")

        manifest = _load_json(manifest_path)
        code, msg = contracts_validate.validate_payload(manifest)
        if code != contracts_validate.EXIT_OK:
            raise ValueError(f"invalid manifest contract: {msg}")

        ingest_manifest_path = snap_dir / "ingest_manifest.json"
        ingest_manifest = None
        if ingest_manifest_path.is_file():
            ingest_manifest = _load_json(ingest_manifest_path)
            code, msg = contracts_validate.validate_payload(ingest_manifest)
            if code != contracts_validate.EXIT_OK:
                raise ValueError(f"invalid ingest_manifest contract: {msg}")

        quality_report_path = snap_dir / "quality_report.json"
        quality_report = None
        if quality_report_path.is_file():
            quality_report = _load_json(quality_report_path)
            code, msg = contracts_validate.validate_payload(quality_report)
            if code != contracts_validate.EXIT_OK:
                raise ValueError(f"invalid quality_report contract: {msg}")

        return {
            "snapshot_id": sid,
            "paths": {
                "snapshot_dir": snap_dir.as_posix(),
                "manifest": manifest_path.as_posix(),
                "ingest_manifest": ingest_manifest_path.as_posix() if ingest_manifest is not None else None,
                "quality_report": quality_report_path.as_posix() if quality_report is not None else None,
            },
            "manifest": manifest,
            "ingest_manifest": ingest_manifest,
            "quality_report": quality_report,
        }
