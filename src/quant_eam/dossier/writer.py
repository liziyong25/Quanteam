from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class DossierPaths:
    dossier_dir: Path
    manifest: Path


class DossierAlreadyExists(RuntimeError):
    pass


class DossierWriter:
    """Append-only dossier writer. Writes to a temp dir then atomically renames."""

    def __init__(self, artifact_root: Path) -> None:
        self.artifact_root = Path(artifact_root)

    def dossier_dir(self, run_id: str) -> Path:
        return self.artifact_root / "dossiers" / run_id

    def write(
        self,
        *,
        run_id: str,
        blueprint_hash: str,
        policy_bundle_id: str,
        data_snapshot_id: str,
        artifacts: dict[str, str],
        config_snapshot: dict[str, Any],
        data_manifest: dict[str, Any],
        metrics: dict[str, Any],
        curve_csv: str,
        trades_csv: str,
        report_md: str,
        extra_json: dict[str, Any] | None = None,
        extra_text: dict[str, str] | None = None,
        behavior_if_exists: str = "noop",  # "noop" or "reject"
    ) -> DossierPaths:
        final_dir = self.dossier_dir(run_id)
        if final_dir.exists():
            if behavior_if_exists == "noop":
                return DossierPaths(dossier_dir=final_dir, manifest=final_dir / "dossier_manifest.json")
            raise DossierAlreadyExists(final_dir.as_posix())

        parent = final_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = parent / f".tmp_{run_id}"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=False)

        try:
            # Write non-manifest artifacts first.
            (tmp_dir / "reports").mkdir(parents=True, exist_ok=True)

            def wjson(rel: str, obj: Any) -> None:
                p = tmp_dir / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            def wtext(rel: str, text: str) -> None:
                p = tmp_dir / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")

            wjson("config_snapshot.json", config_snapshot)
            wjson("data_manifest.json", data_manifest)
            wjson("metrics.json", metrics)
            wtext("curve.csv", curve_csv)
            wtext("trades.csv", trades_csv)
            wtext("reports/report.md", report_md)

            # Optional additional artifacts (Phase-21+). Written before dossier_manifest.json so hashes can include them
            # if referenced by `artifacts`.
            if isinstance(extra_json, dict):
                for rel, obj in sorted(extra_json.items(), key=lambda kv: kv[0]):
                    wjson(str(rel), obj)
            if isinstance(extra_text, dict):
                for rel, text in sorted(extra_text.items(), key=lambda kv: kv[0]):
                    wtext(str(rel), str(text))

            # Build dossier manifest (contracts/dossier_schema_v1).
            dossier_manifest: dict[str, Any] = {
                "schema_version": "dossier_v1",
                "run_id": run_id,
                "created_at": _utc_now_iso(),
                "blueprint_hash": blueprint_hash,
                "policy_bundle_id": policy_bundle_id,
                "data_snapshot_id": data_snapshot_id,
                "append_only": True,
                "artifacts": dict(artifacts),
                "hashes": {},
            }

            # Compute hashes for referenced artifact paths.
            hashes: dict[str, str] = {}
            for _, rel in artifacts.items():
                p = tmp_dir / rel
                if p.is_file():
                    hashes[rel] = _sha256_file(p)
            dossier_manifest["hashes"] = hashes
            wjson("dossier_manifest.json", dossier_manifest)

            # Atomic finalize.
            tmp_dir.replace(final_dir)
            return DossierPaths(dossier_dir=final_dir, manifest=final_dir / "dossier_manifest.json")
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
