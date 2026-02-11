from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from quant_eam.data_lake.timeutil import parse_daily_dt, parse_iso_datetime, taipei_tz, to_iso
from quant_eam.policies.load import default_policies_dir, load_yaml
from quant_eam.contracts import validate as contracts_validate


def _utc_now_iso() -> str:
    # Deterministic if SOURCE_DATE_EPOCH is set.
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class DatasetSummary:
    dataset_id: str
    file: str
    row_count: int
    fields: list[str]
    symbols: list[str]
    dt_min: str
    dt_max: str
    available_at_min: str
    available_at_max: str
    sha256: str


class DataLake:
    """Deterministic snapshot storage under <root>/lake/<snapshot_id>/."""

    MANIFEST_SCHEMA_VERSION = "data_snapshot_manifest_v1"

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            root = Path(os.getenv("EAM_DATA_ROOT", "/data"))
        self.root = Path(root)

    def snapshot_dir(self, snapshot_id: str) -> Path:
        return self.root / "lake" / snapshot_id

    def dataset_csv_path(self, snapshot_id: str, dataset_id: str) -> Path:
        return self.snapshot_dir(snapshot_id) / f"{dataset_id}.csv"

    def manifest_path(self, snapshot_id: str) -> Path:
        return self.snapshot_dir(snapshot_id) / "manifest.json"

    def quality_report_path(self, snapshot_id: str) -> Path:
        return self.snapshot_dir(snapshot_id) / "quality_report.json"

    def _load_asof_latency_policy(self, policies_dir: Path | None = None) -> dict[str, Any]:
        policies_dir = policies_dir or default_policies_dir()
        p = policies_dir / "asof_latency_policy_v1.yaml"
        doc = load_yaml(p)
        if not isinstance(doc, dict):
            raise ValueError("asof_latency_policy must be a mapping")
        if doc.get("policy_version") != "v1":
            raise ValueError("asof_latency_policy policy_version must be v1")
        params = doc.get("params")
        if not isinstance(params, dict):
            raise ValueError("asof_latency_policy params must be an object")
        if params.get("asof_rule") != "available_at<=as_of":
            raise ValueError('asof_latency_policy params.asof_rule must be "available_at<=as_of"')
        return doc

    def _ensure_available_at(
        self,
        rows: list[dict[str, Any]],
        *,
        policy: dict[str, Any],
        bar_close_hour: int = 16,
    ) -> tuple[str, str, str]:
        """Fill available_at if missing. Returns (strategy, min, max)."""
        params = policy["params"]
        default_latency_seconds = int(params.get("default_latency_seconds", 0))
        bar_close_to_signal_seconds = int(params.get("bar_close_to_signal_seconds", 0))

        any_provided = False
        min_av: datetime | None = None
        max_av: datetime | None = None
        for r in rows:
            if "dt" not in r:
                raise ValueError("missing dt")
            parsed = parse_daily_dt(r["dt"], bar_close_hour=bar_close_hour)
            dt_close = parsed.dt

            if "available_at" in r and r["available_at"] not in (None, ""):
                any_provided = True
                av = parse_iso_datetime(str(r["available_at"]))
                if av < dt_close:
                    raise ValueError("available_at must be >= dt (bar close)")
                r["available_at"] = to_iso(av)
            else:
                av = dt_close + timedelta(seconds=default_latency_seconds + bar_close_to_signal_seconds)
                r["available_at"] = to_iso(av)

            av_dt = parse_iso_datetime(str(r["available_at"]))
            min_av = av_dt if min_av is None else min(min_av, av_dt)
            max_av = av_dt if max_av is None else max(max_av, av_dt)

        strategy = "provided_by_source" if any_provided else "policy_default_latency"
        assert min_av is not None and max_av is not None
        return strategy, to_iso(min_av), to_iso(max_av)

    def write_ohlcv_1d_snapshot(
        self,
        *,
        snapshot_id: str,
        rows: Iterable[dict[str, Any]],
        policies_dir: Path | None = None,
        dataset_id: str = "ohlcv_1d",
    ) -> dict[str, Any]:
        """Write a snapshot with a single dataset 'ohlcv_1d' and a manifest. Returns the manifest dict."""
        if not snapshot_id.strip():
            raise ValueError("snapshot_id must be non-empty")
        if dataset_id != "ohlcv_1d":
            raise ValueError("Phase-03 MVP only supports dataset_id=ohlcv_1d")

        out_dir = self.snapshot_dir(snapshot_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Materialize rows to validate + deterministically sort/dedupe.
        materialized: list[dict[str, Any]] = [dict(r) for r in rows]
        required = ["symbol", "dt", "open", "high", "low", "close", "volume"]
        for r in materialized:
            for k in required:
                if k not in r:
                    raise ValueError(f"missing required field: {k}")

        # Dedupe by (symbol, dt) and sort deterministically.
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        duplicate_count = 0
        for r in sorted(materialized, key=lambda x: (str(x["symbol"]), str(x["dt"]))):
            key = (str(r["symbol"]), str(r["dt"]))
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
            deduped.append(r)

        policy = self._load_asof_latency_policy(policies_dir=policies_dir)
        available_at_strategy, av_min, av_max = self._ensure_available_at(deduped, policy=policy)

        # Compute dt min/max using the same daily parse rules.
        parsed_dts = [parse_daily_dt(r["dt"]).dt for r in deduped]
        dt_min = min(parsed_dts).astimezone(taipei_tz())
        dt_max = max(parsed_dts).astimezone(taipei_tz())

        # Minimal deterministic data quality checks + evidence.
        def _null_counts(rows2: list[dict[str, Any]], cols: list[str]) -> dict[str, int]:
            out2: dict[str, int] = {}
            for c in cols:
                n = 0
                for rr in rows2:
                    if c not in rr or rr.get(c) in (None, ""):
                        n += 1
                out2[c] = n
            return out2

        def _minmax(rows2: list[dict[str, Any]], col: str) -> tuple[float, float]:
            vals: list[float] = []
            for rr in rows2:
                v = rr.get(col)
                if v in (None, ""):
                    continue
                vals.append(float(v))
            if not vals:
                return 0.0, 0.0
            return min(vals), max(vals)

        numeric_cols = ["open", "high", "low", "close", "volume"]
        for c in numeric_cols:
            for rr in deduped:
                try:
                    v = float(rr[c])
                except Exception as e:  # noqa: BLE001
                    raise ValueError(f"invalid numeric value for {c}") from e
                if v < 0:
                    raise ValueError(f"{c} must be non-negative")

        quality_report = {
            "schema_version": "quality_report_v1",
            "snapshot_id": snapshot_id,
            "dataset_id": dataset_id,
            "created_at": _utc_now_iso(),
            "rows_before_dedupe": int(len(materialized)),
            "rows_after_dedupe": int(len(deduped)),
            "duplicate_count": int(duplicate_count),
            "null_count_by_col": _null_counts(deduped, required + ["available_at", "source"]),
            "dt_min": to_iso(dt_min),
            "dt_max": to_iso(dt_max),
            "available_at_min": av_min,
            "available_at_max": av_max,
            "min_by_col": {c: _minmax(deduped, c)[0] for c in numeric_cols},
            "max_by_col": {c: _minmax(deduped, c)[1] for c in numeric_cols},
        }

        quality_path = self.quality_report_path(snapshot_id)
        quality_path.write_text(json.dumps(quality_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Write CSV deterministically.
        csv_path = self.dataset_csv_path(snapshot_id, dataset_id)
        fields = ["symbol", "dt", "open", "high", "low", "close", "volume", "available_at", "source"]
        for r in deduped:
            r.setdefault("source", "demo")

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in deduped:
                w.writerow(
                    {
                        "symbol": str(r["symbol"]),
                        "dt": str(r["dt"]),
                        "open": f"{float(r['open']):.6f}",
                        "high": f"{float(r['high']):.6f}",
                        "low": f"{float(r['low']):.6f}",
                        "close": f"{float(r['close']):.6f}",
                        "volume": f"{float(r['volume']):.6f}",
                        "available_at": str(r["available_at"]),
                        "source": str(r.get("source", "demo")),
                    }
                )

        sha = _sha256_file(csv_path)
        symbols = sorted({str(r["symbol"]) for r in deduped})

        dataset_summary = DatasetSummary(
            dataset_id=dataset_id,
            file=csv_path.as_posix(),
            row_count=len(deduped),
            fields=fields,
            symbols=symbols,
            dt_min=to_iso(dt_min),
            dt_max=to_iso(dt_max),
            available_at_min=av_min,
            available_at_max=av_max,
            sha256=sha,
        )

        manifest: dict[str, Any] = {
            "schema_version": self.MANIFEST_SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "created_at": _utc_now_iso(),
            "datasets": [
                {
                    "dataset_id": dataset_summary.dataset_id,
                    "file": dataset_summary.file,
                    "row_count": dataset_summary.row_count,
                    "fields": dataset_summary.fields,
                    "symbols": dataset_summary.symbols,
                    "dt_min": dataset_summary.dt_min,
                    "dt_max": dataset_summary.dt_max,
                    "available_at_min": dataset_summary.available_at_min,
                    "available_at_max": dataset_summary.available_at_max,
                    "sha256": dataset_summary.sha256,
                    "extensions": {
                        "available_at_strategy": available_at_strategy,
                        "duplicate_count": duplicate_count,
                        "asof_latency_policy_id": str(policy.get("policy_id", "")),
                        "asof_rule": str(policy.get("params", {}).get("asof_rule", "")),
                        "quality_report_ref": quality_path.as_posix(),
                    },
                }
            ],
        }

        manifest_path = self.manifest_path(snapshot_id)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Self-validate manifest against contracts (Phase-15). No network IO.
        code, msg = contracts_validate.validate_payload(manifest)
        if code != contracts_validate.EXIT_OK:
            raise ValueError(f"data snapshot manifest contract invalid: {msg}")
        return manifest
