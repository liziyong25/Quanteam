from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from quant_eam.data_lake.lake import DataLake
from quant_eam.data_lake.timeutil import parse_daily_dt, taipei_tz
from quant_eam.contracts import validate as contracts_validate
from quant_eam.policies.load import default_policies_dir, load_yaml


EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2

INGEST_MANIFEST_SCHEMA_VERSION = "ingest_manifest_v1"


def _utc_now_iso() -> str:
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


def _parse_symbols(s: str) -> list[str]:
    return [p.strip() for p in str(s).split(",") if p.strip()]


def _iter_dates_inclusive(start: str, end: str) -> list[str]:
    sdt = parse_daily_dt(start).dt
    edt = parse_daily_dt(end).dt
    if edt < sdt:
        raise ValueError("end must be >= start")
    out: list[str] = []
    cur = sdt
    while cur <= edt:
        out.append(cur.date().isoformat())
        cur = cur + timedelta(days=1)
    return out


class WeQuantProvider(Protocol):
    def fetch_ohlcv_1d(self, *, symbols: list[str], start: str, end: str) -> list[dict[str, Any]]:
        """Return rows with columns: symbol, dt, open, high, low, close, volume (available_at optional)."""


def _num_from(sym: str, dt: str, salt: str) -> float:
    # Deterministic pseudo-number in [0, 1).
    h = hashlib.sha256(f"{salt}|{sym}|{dt}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class MockWeQuantProvider:
    """Deterministic offline provider for tests/CI.

    It intentionally does NOT provide available_at; DataLake must fill it from asof_latency_policy_v1.
    """

    def __init__(self, *, seed: str = "mock", dt_mode: str = "date") -> None:
        self.seed = str(seed)
        self.dt_mode = str(dt_mode)

    def fetch_ohlcv_1d(self, *, symbols: list[str], start: str, end: str) -> list[dict[str, Any]]:
        dts = _iter_dates_inclusive(start, end)
        out: list[dict[str, Any]] = []
        for sym in symbols:
            for i, dt in enumerate(dts):
                u = _num_from(sym, dt, self.seed)
                base = 100.0 + (u * 10.0) + (i * 0.05)
                dt_value: Any
                if self.dt_mode == "date":
                    dt_value = dt
                elif self.dt_mode == "datetime":
                    # Provide a datetime close timestamp (Asia/Taipei) for dt-normalization tests.
                    dt_value = parse_daily_dt(dt).dt
                else:
                    raise ValueError("invalid mock dt_mode (expected date|datetime)")
                out.append(
                    {
                        "symbol": sym,
                        "dt": dt_value,
                        "open": base,
                        "high": base + 1.0,
                        "low": base - 1.0,
                        "close": base + 0.5,
                        "volume": 1000.0 + float(i),
                        "source": "wequant_mock",
                    }
                )
        return out


class RealWeQuantProvider:
    """Optional real provider. Tests must not depend on it.

    This wrapper checks local qa_fetch provider modules at runtime.
    """

    def __init__(self) -> None:
        try:
            from quant_eam.qa_fetch.providers.wequant_local import wefetch  # noqa: F401
        except Exception as e:  # noqa: BLE001
            raise ValueError(
                "wequant local provider is not available under quant_eam.qa_fetch.providers; "
                "use --provider mock (tests/CI) or complete qa_fetch providers migration"
            ) from e

    def fetch_ohlcv_1d(self, *, symbols: list[str], start: str, end: str) -> list[dict[str, Any]]:
        # Placeholder minimal integration point (implementation depends on your wequant client API).
        # Keep deterministic/offline tests by not calling this provider in tests.
        raise ValueError(
            "RealWeQuantProvider is a stub in this MVP; "
            "integrate your wequant client here or use --provider mock"
        )


def _load_policy_bundle_and_asof_policy() -> tuple[dict[str, Any], dict[str, Any]]:
    policies_dir = default_policies_dir()
    bundle_path = policies_dir / "policy_bundle_v1.yaml"
    asof_path = policies_dir / "asof_latency_policy_v1.yaml"

    bundle = load_yaml(bundle_path)
    if not isinstance(bundle, dict):
        raise ValueError("policy bundle must be a mapping")
    asof = load_yaml(asof_path)
    if not isinstance(asof, dict):
        raise ValueError("asof_latency_policy must be a mapping")

    # Minimal v1 invariants (governance: read-only; fixed semantics).
    if bundle.get("policy_version") != "v1":
        raise ValueError("policy bundle policy_version must be v1")
    if asof.get("policy_version") != "v1":
        raise ValueError("asof_latency_policy policy_version must be v1")
    params = asof.get("params")
    if not isinstance(params, dict):
        raise ValueError("asof_latency_policy params must be a mapping")
    if str(params.get("asof_rule") or "") != "available_at<=as_of":
        raise ValueError('asof_latency_policy params.asof_rule must be "available_at<=as_of"')

    # Bundle reference is canonical by id (no inline override).
    want_id = str(bundle.get("asof_latency_policy_id") or "").strip()
    got_id = str(asof.get("policy_id") or "").strip()
    if want_id and got_id and want_id != got_id:
        raise ValueError("policy_bundle.asof_latency_policy_id mismatch with asof_latency_policy.policy_id")

    return bundle, asof


def _normalize_dt_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize row['dt'] to YYYY-MM-DD (trading day string).

    Returns metadata for manifest.extensions (dt source audit only).
    """
    counts: dict[str, int] = {"date": 0, "iso_datetime": 0, "datetime": 0}
    examples: dict[str, str] = {}

    for r in rows:
        if "dt" not in r:
            raise ValueError("missing dt")
        v = r["dt"]
        kind = "date"
        if isinstance(v, datetime):
            kind = "datetime"
            raw = v.isoformat()
        elif isinstance(v, str):
            s = v.strip()
            if len(s) == 10 and s[4] == "-" and s[7] == "-":
                kind = "date"
                raw = s
            else:
                kind = "iso_datetime"
                raw = s
        else:
            raw = str(v)

        parsed = parse_daily_dt(v)
        dt_local = parsed.dt.astimezone(taipei_tz())
        r["dt"] = dt_local.date().isoformat()

        counts[kind] = int(counts.get(kind, 0)) + 1
        if kind not in examples:
            examples[kind] = raw

    return {"dt_source_counts": counts, "dt_source_examples": examples}


@dataclass(frozen=True)
class IngestResult:
    snapshot_id: str
    dataset_id: str
    rows_written: int
    data_file: str
    snapshot_manifest: str
    ingest_manifest: str
    sha256_of_data_file: str


def ingest_wequant_ohlcv_1d(
    *,
    provider: WeQuantProvider,
    provider_id: str,
    provider_version: str | None = None,
    root: Path,
    snapshot_id: str,
    symbols: list[str],
    start: str,
    end: str,
) -> IngestResult:
    lake = DataLake(root=root)
    dataset_id = "ohlcv_1d"

    rows = provider.fetch_ohlcv_1d(symbols=symbols, start=start, end=end)
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("provider must return list[dict]")

    # Adapter rule (Phase-14R): normalize dt to trading day string YYYY-MM-DD.
    dt_meta = _normalize_dt_rows(rows)

    manifest = lake.write_ohlcv_1d_snapshot(snapshot_id=snapshot_id, rows=rows, dataset_id=dataset_id)
    ds = manifest["datasets"][0]
    data_file = Path(str(ds["file"]))
    sha = str(ds["sha256"])
    ds_ext = ds.get("extensions") if isinstance(ds.get("extensions"), dict) else {}
    asof_pid = str(ds_ext.get("asof_latency_policy_id") or "")
    asof_rule = str(ds_ext.get("asof_rule") or "")

    # Audit fields must come from read-only policy assets (not CLI overrides).
    _bundle, asof_pol = _load_policy_bundle_and_asof_policy()
    asof_params = asof_pol.get("params") if isinstance(asof_pol.get("params"), dict) else {}
    default_latency_seconds = int(asof_params.get("default_latency_seconds", 0))
    trade_lag_bars_default = asof_params.get("trade_lag_bars_default", None)
    if trade_lag_bars_default is not None and not isinstance(trade_lag_bars_default, int):
        trade_lag_bars_default = None

    snap_dir = lake.snapshot_dir(snapshot_id)
    ingest_manifest_path = snap_dir / "ingest_manifest.json"
    quality_report_path = lake.quality_report_path(snapshot_id)

    ingest_manifest: dict[str, Any] = {
        "schema_version": INGEST_MANIFEST_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "dataset_id": dataset_id,
        "provider_id": str(provider_id),
        "provider_version": str(provider_version) if provider_version else None,
        "request_spec": {"symbols": symbols, "start": start, "end": end, "frequency": "1d"},
        "rows_written": int(ds["row_count"]),
        # Convenience alias (some tooling expects 'sha256' key).
        "sha256": sha,
        "sha256_of_data_file": sha,
        "created_at": _utc_now_iso(),
        "asof_latency_policy_id": asof_pid,
        "asof_rule": asof_rule,
        "default_latency_seconds": int(default_latency_seconds),
        "trade_lag_bars_default": int(trade_lag_bars_default) if isinstance(trade_lag_bars_default, int) else None,
        "output_paths": {
            "data_file": data_file.as_posix(),
            "snapshot_manifest": lake.manifest_path(snapshot_id).as_posix(),
            "ingest_manifest": ingest_manifest_path.as_posix(),
            "quality_report": quality_report_path.as_posix(),
        },
        "extensions": {
            "available_at_strategy": str(ds_ext.get("available_at_strategy") or ""),
            "duplicate_count": int(ds_ext.get("duplicate_count") or 0),
            "quality_report_ref": quality_report_path.as_posix(),
            **dt_meta,
        },
    }

    # Clean None keys deterministically.
    if ingest_manifest.get("provider_version") is None:
        ingest_manifest.pop("provider_version", None)
    if ingest_manifest.get("trade_lag_bars_default") is None:
        ingest_manifest.pop("trade_lag_bars_default", None)

    # Contract validate before writing.
    code, msg = contracts_validate.validate_payload(ingest_manifest)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"ingest manifest contract invalid: {msg}")

    ingest_manifest_path.write_text(json.dumps(ingest_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Double-check sha256 for audit (must match DataLake manifest).
    actual_sha = _sha256_file(data_file)
    if actual_sha != sha:
        raise ValueError("sha256 mismatch between DataLake manifest and actual file")

    return IngestResult(
        snapshot_id=snapshot_id,
        dataset_id=dataset_id,
        rows_written=int(ds["row_count"]),
        data_file=data_file.as_posix(),
        snapshot_manifest=lake.manifest_path(snapshot_id).as_posix(),
        ingest_manifest=ingest_manifest_path.as_posix(),
        sha256_of_data_file=sha,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m quant_eam.ingest.wequant_ohlcv")
    p.add_argument("--provider", choices=["mock", "wequant"], required=True)
    p.add_argument("--root", default=None, help="Data root (default: env EAM_DATA_ROOT or /data).")
    p.add_argument("--snapshot-id", required=True)
    p.add_argument("--symbols", required=True, help="Comma-separated symbols (e.g. AAA,BBB).")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    args = p.parse_args(argv)

    try:
        root = Path(args.root) if args.root else Path(os.getenv("EAM_DATA_ROOT", "/data"))
        symbols = _parse_symbols(args.symbols)
        if not symbols:
            print("ERROR: symbols must be non-empty", file=sys.stderr)
            return EXIT_USAGE_OR_ERROR

        if args.provider == "mock":
            provider = MockWeQuantProvider(seed=f"{args.snapshot_id}|{args.start}|{args.end}")
            provider_id = "mock"
            provider_version = "v1"
        else:
            provider = RealWeQuantProvider()
            provider_id = "wequant"
            provider_version = None

        res = ingest_wequant_ohlcv_1d(
            provider=provider,
            provider_id=provider_id,
            provider_version=provider_version,
            root=root,
            snapshot_id=str(args.snapshot_id),
            symbols=symbols,
            start=str(args.start),
            end=str(args.end),
        )

        print(f"snapshot_id={res.snapshot_id}")
        print(f"dataset_id={res.dataset_id}")
        print(f"rows_written={res.rows_written}")
        print(f"data_file={res.data_file}")
        print(f"snapshot_manifest={res.snapshot_manifest}")
        print(f"ingest_manifest={res.ingest_manifest}")
        print(f"sha256_of_data_file={res.sha256_of_data_file}")
        return EXIT_OK
    except ValueError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return EXIT_INVALID
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
