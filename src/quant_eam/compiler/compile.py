from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.policies.resolve import load_policy_bundle

EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def _taipei_tz() -> timezone:
    # Fixed offset to avoid tzdata dependency in slim containers.
    return timezone(timedelta(hours=8))


def _end_date_to_default_asof(end_date: str) -> str:
    # end_date is YYYY-MM-DD; default as_of is end date 23:59:59+08:00.
    dt = datetime.fromisoformat(end_date)
    dt = datetime(dt.year, dt.month, dt.day, 23, 59, 59, tzinfo=_taipei_tz())
    return dt.isoformat()


def _parse_date_ymd(s: str) -> date:
    return date.fromisoformat(str(s))


def _fmt_date(d: date) -> str:
    return d.isoformat()


def _add_days(s: str, days: int) -> str:
    d = _parse_date_ymd(s)
    return _fmt_date(d + timedelta(days=int(days)))


def _min_date(a: str, b: str) -> str:
    return _fmt_date(min(_parse_date_ymd(a), _parse_date_ymd(b)))


def _max_date(a: str, b: str) -> str:
    return _fmt_date(max(_parse_date_ymd(a), _parse_date_ymd(b)))


def _date_le(a: str, b: str) -> bool:
    return _parse_date_ymd(a) <= _parse_date_ymd(b)


@dataclass(frozen=True)
class SegmentDef:
    segment_id: str
    kind: str  # train|test|holdout
    start: str
    end: str
    as_of: str
    holdout: bool
    purge_days: int
    embargo_days: int

    def to_runspec_obj(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "kind": self.kind,
            "start": self.start,
            "end": self.end,
            "as_of": self.as_of,
            "holdout": bool(self.holdout),
            "purge_days": int(self.purge_days),
            "embargo_days": int(self.embargo_days),
        }


def _purge_embargo_days(bp: dict[str, Any]) -> tuple[int, int]:
    ep = bp.get("evaluation_protocol") if isinstance(bp.get("evaluation_protocol"), dict) else {}
    purge = ep.get("purge") if isinstance(ep.get("purge"), dict) else {}
    embargo = ep.get("embargo") if isinstance(ep.get("embargo"), dict) else {}
    # Blueprint v1 encodes purge/embargo in bars. For 1d bars, treat bars as days.
    purge_days = int(purge.get("bars") or 0) if isinstance(purge.get("bars"), int) else 0
    embargo_days = int(embargo.get("bars") or 0) if isinstance(embargo.get("bars"), int) else 0
    # Optional override: allow explicit *_days fields (forward-compatible).
    if isinstance(ep.get("purge_days"), int):
        purge_days = int(ep["purge_days"])
    if isinstance(ep.get("embargo_days"), int):
        embargo_days = int(ep["embargo_days"])
    return max(0, purge_days), max(0, embargo_days)


def _segment_from_bp(ep_seg: dict[str, Any]) -> tuple[str, str, str | None]:
    start = str(ep_seg.get("start", "")).strip()
    end = str(ep_seg.get("end", "")).strip()
    as_of = ep_seg.get("as_of")
    as_of_s = str(as_of).strip() if as_of is not None else None
    return start, end, as_of_s


def _eval_protocol_config(bp: dict[str, Any]) -> dict[str, Any]:
    ep = bp.get("evaluation_protocol") if isinstance(bp.get("evaluation_protocol"), dict) else {}
    ext = bp.get("extensions") if isinstance(bp.get("extensions"), dict) else {}
    # Allow both evaluation_protocol.* and blueprint.extensions.* as forward-compatible inputs.
    out: dict[str, Any] = {}
    for src in (ep, ext):
        if isinstance(src, dict):
            for k in (
                "protocol",
                "train_window_days",
                "test_window_days",
                "step_days",
                "holdout_range",
                "purge_days",
                "embargo_days",
            ):
                if k in src and k not in out:
                    out[k] = src.get(k)
    return out


def _build_segments_list(bp: dict[str, Any]) -> tuple[list[SegmentDef], dict[str, Any]]:
    """Build deterministic segments list.

    - Returns (segments, protocol_meta) where protocol_meta is safe to store under runspec.extensions.
    """
    ep = bp.get("evaluation_protocol") if isinstance(bp.get("evaluation_protocol"), dict) else {}
    segs = ep.get("segments") if isinstance(ep.get("segments"), dict) else {}
    train_raw = segs.get("train") if isinstance(segs.get("train"), dict) else {}
    test_raw = segs.get("test") if isinstance(segs.get("test"), dict) else {}
    holdout_raw = segs.get("holdout") if isinstance(segs.get("holdout"), dict) else {}

    train_start, train_end, train_asof = _segment_from_bp(train_raw)
    test_start, test_end, test_asof = _segment_from_bp(test_raw)
    holdout_start, holdout_end, holdout_asof = _segment_from_bp(holdout_raw)
    if not train_start or not train_end or not test_start or not test_end or not holdout_start or not holdout_end:
        raise ValueError("blueprint.evaluation_protocol.segments.{train,test,holdout}.start/end required")

    purge_days, embargo_days = _purge_embargo_days(bp)
    cfg = _eval_protocol_config(bp)
    protocol = str(cfg.get("protocol") or "fixed_split").strip() or "fixed_split"
    if protocol not in ("fixed_split", "walk_forward"):
        protocol = "fixed_split"

    # Optional explicit holdout_range override (start/end).
    hr = cfg.get("holdout_range")
    if isinstance(hr, dict):
        hs = str(hr.get("start") or "").strip()
        he = str(hr.get("end") or "").strip()
        if hs and he:
            holdout_start, holdout_end = hs, he

    # Normalize as_of defaults.
    train_asof = train_asof or _end_date_to_default_asof(train_end)
    test_asof = test_asof or _end_date_to_default_asof(test_end)
    holdout_asof = holdout_asof or _end_date_to_default_asof(holdout_end)

    # Apply embargo/purge to the base train/test boundary.
    train_end_adj = _add_days(train_end, -embargo_days) if embargo_days > 0 else train_end
    test_start_adj = _add_days(test_start, purge_days) if purge_days > 0 else test_start
    if not _date_le(train_start, train_end_adj):
        train_end_adj = train_end
    if not _date_le(test_start_adj, test_end):
        test_start_adj = test_start

    segments: list[SegmentDef] = []
    if protocol == "fixed_split":
        segments.append(
            SegmentDef(
                segment_id="train_000",
                kind="train",
                start=train_start,
                end=train_end_adj,
                as_of=train_asof,
                holdout=False,
                purge_days=purge_days,
                embargo_days=embargo_days,
            )
        )
        segments.append(
            SegmentDef(
                segment_id="test_000",
                kind="test",
                start=test_start_adj,
                end=test_end,
                as_of=test_asof,
                holdout=False,
                purge_days=purge_days,
                embargo_days=embargo_days,
            )
        )
    else:
        # Walk-forward slicing over the blueprint test range.
        tw = cfg.get("train_window_days")
        vw = cfg.get("test_window_days")
        st = cfg.get("step_days")
        if not isinstance(tw, int) or tw <= 0:
            raise ValueError("walk_forward requires train_window_days > 0")
        if not isinstance(vw, int) or vw <= 0:
            raise ValueError("walk_forward requires test_window_days > 0")
        if not isinstance(st, int) or st <= 0:
            raise ValueError("walk_forward requires step_days > 0")

        i = 0
        cur_test_start = test_start
        while True:
            cur_test_end = _add_days(cur_test_start, vw - 1)
            if not _date_le(cur_test_end, test_end):
                break

            cur_train_end = _add_days(cur_test_start, -1)
            cur_train_start = _add_days(cur_train_end, -(tw - 1))
            # Clamp train start to blueprint train start (avoid going out of declared range).
            cur_train_start = _max_date(cur_train_start, train_start)
            if not _date_le(cur_train_start, cur_train_end):
                break

            # Apply embargo/purge around boundary.
            cur_train_end_adj = _add_days(cur_train_end, -embargo_days) if embargo_days > 0 else cur_train_end
            cur_test_start_adj = _add_days(cur_test_start, purge_days) if purge_days > 0 else cur_test_start
            if not _date_le(cur_train_start, cur_train_end_adj):
                cur_train_end_adj = cur_train_end
            if not _date_le(cur_test_start_adj, cur_test_end):
                cur_test_start_adj = cur_test_start

            segments.append(
                SegmentDef(
                    segment_id=f"train_{i:03d}",
                    kind="train",
                    start=cur_train_start,
                    end=cur_train_end_adj,
                    as_of=_end_date_to_default_asof(cur_train_end_adj),
                    holdout=False,
                    purge_days=purge_days,
                    embargo_days=embargo_days,
                )
            )
            segments.append(
                SegmentDef(
                    segment_id=f"test_{i:03d}",
                    kind="test",
                    start=cur_test_start_adj,
                    end=cur_test_end,
                    as_of=_end_date_to_default_asof(cur_test_end),
                    holdout=False,
                    purge_days=purge_days,
                    embargo_days=embargo_days,
                )
            )

            i += 1
            cur_test_start = _add_days(cur_test_start, st)

    # Holdout is always appended last.
    segments.append(
        SegmentDef(
            segment_id="holdout_000",
            kind="holdout",
            start=holdout_start,
            end=holdout_end,
            as_of=holdout_asof,
            holdout=True,
            purge_days=purge_days,
            embargo_days=embargo_days,
        )
    )

    meta = {
        "protocol": protocol,
        "purge_days": purge_days,
        "embargo_days": embargo_days,
        "train_window_days": (cfg.get("train_window_days") if isinstance(cfg.get("train_window_days"), int) else None),
        "test_window_days": (cfg.get("test_window_days") if isinstance(cfg.get("test_window_days"), int) else None),
        "step_days": (cfg.get("step_days") if isinstance(cfg.get("step_days"), int) else None),
        "holdout_range": {"start": holdout_start, "end": holdout_end},
    }
    return segments, meta


def _blueprint_extract_minimum(bp: dict[str, Any]) -> tuple[str, list[str], str, str, str | None]:
    # dataset_id from first data requirement
    drs = bp.get("data_requirements")
    if not isinstance(drs, list) or not drs:
        raise ValueError("blueprint.data_requirements must be a non-empty array")
    dr0 = drs[0]
    if not isinstance(dr0, dict):
        raise ValueError("blueprint.data_requirements[0] must be an object")
    dataset_id = str(dr0.get("dataset_id", ""))
    if not dataset_id:
        raise ValueError("blueprint.data_requirements[0].dataset_id missing")

    uni = bp.get("universe", {})
    if not isinstance(uni, dict):
        raise ValueError("blueprint.universe must be an object")
    syms = uni.get("symbols")
    if not isinstance(syms, list) or not syms:
        raise ValueError("blueprint.universe.symbols must be a non-empty array")
    symbols = [str(s) for s in syms]

    segs = bp.get("evaluation_protocol", {}).get("segments", {})
    if not isinstance(segs, dict):
        raise ValueError("blueprint.evaluation_protocol.segments must be an object")
    test_seg = segs.get("test", {})
    if not isinstance(test_seg, dict):
        raise ValueError("blueprint.evaluation_protocol.segments.test must be an object")
    start = str(test_seg.get("start", ""))
    end = str(test_seg.get("end", ""))
    if not start or not end:
        raise ValueError("blueprint.evaluation_protocol.segments.test.start/end required")
    as_of = test_seg.get("as_of")
    as_of_str = str(as_of) if as_of is not None else None
    return dataset_id, symbols, start, end, as_of_str


def compile_blueprint_to_runspec(
    *,
    blueprint_path: Path,
    snapshot_id: str,
    policy_bundle_path: Path,
    out_path: Path,
    check_availability: bool = False,
    data_root: Path | None = None,
) -> tuple[int, str]:
    # Validate blueprint contract first.
    code, msg = contracts_validate.validate_json(blueprint_path)
    if code != contracts_validate.EXIT_OK:
        return EXIT_INVALID, msg

    bp = _load_json(blueprint_path)
    if not isinstance(bp, dict):
        return EXIT_INVALID, "INVALID: blueprint must be a JSON object"

    bundle_doc = load_policy_bundle(policy_bundle_path)
    bundle_id = str(bundle_doc["policy_bundle_id"])

    bp_bundle_id = str(bp.get("policy_bundle_id", ""))
    if bp_bundle_id != bundle_id:
        return EXIT_INVALID, (
            "INVALID: blueprint.policy_bundle_id mismatch "
            f"(blueprint={bp_bundle_id!r}, bundle={bundle_id!r})"
        )

    dataset_id, symbols, start, end, as_of = _blueprint_extract_minimum(bp)
    if dataset_id != "ohlcv_1d":
        return EXIT_INVALID, f"INVALID: only dataset_id=ohlcv_1d supported in Phase-05 (got {dataset_id!r})"

    as_of = as_of or _end_date_to_default_asof(end)

    # Adapter selection (MVP): allow explicit engine_contract in blueprint strategy_spec.extensions.
    # If omitted, default to vectorbt_signal_v1.
    adapter_id = "vectorbt_signal_v1"
    try:
        strat = bp.get("strategy_spec", {})
        if isinstance(strat, dict):
            ext = strat.get("extensions", {})
            if isinstance(ext, dict) and "engine_contract" in ext:
                engine_contract = ext.get("engine_contract")
                if engine_contract != adapter_id:
                    return EXIT_INVALID, f"INVALID: unsupported engine_contract: {engine_contract!r}"
    except Exception:
        # Treat unexpected structures as invalid.
        return EXIT_INVALID, "INVALID: failed to parse blueprint.strategy_spec.extensions.engine_contract"

    if check_availability:
        root = data_root or Path(os.getenv("EAM_DATA_ROOT", "/data"))
        cat = DataCatalog(root=root)
        rows, _stats = cat.query_ohlcv(
            snapshot_id=snapshot_id,
            symbols=symbols,
            start=start,
            end=end,
            as_of=as_of,
        )
        if not rows:
            return EXIT_INVALID, "INVALID: availability check failed (0 rows under as_of filter)"

    blueprint_hash = _canonical_sha256(bp)
    # Deterministic segments list (Phase-21). Stored under runspec.segments.list (additionalProperties allowed).
    segments_list, ep_meta = _build_segments_list(bp)
    # Protocol hardening (Phase-27):
    # - Prefer run_spec_v2 by default (segments.list is canonical and explicit).
    # - Exception: param-sweep pipeline currently requires run_spec_v1 for backward compatibility.
    bp_ext = bp.get("extensions") if isinstance(bp.get("extensions"), dict) else {}
    has_sweep = isinstance(bp_ext, dict) and isinstance(bp_ext.get("sweep_spec"), dict)
    runspec_schema_version = "run_spec_v1" if has_sweep else "run_spec_v2"

    runspec: dict[str, Any] = {
        "schema_version": runspec_schema_version,
        "blueprint_ref": {"blueprint_id": str(bp.get("blueprint_id", "")), "blueprint_hash": blueprint_hash},
        "policy_bundle_id": bundle_id,
        "data_snapshot_id": snapshot_id,
        "segments": {
            # Legacy v1 anchors (required by run_spec_v1 schema).
            "train": {"start": start, "end": end, "as_of": as_of},
            "test": {"start": start, "end": end, "as_of": as_of},
            "holdout": {"start": start, "end": end, "as_of": as_of},
            # Phase-21: multi-segment evaluation protocol. Canonical list, stable order.
            "list": [s.to_runspec_obj() for s in segments_list],
        },
        "adapter": {"adapter_id": adapter_id},
        "output_spec": {
            "write_dossier": True,
            "artifacts": {
                "dossier_manifest": "dossier_manifest.json",
                "config_snapshot": "config_snapshot.json",
                "data_manifest": "data_manifest.json",
                "metrics": "metrics.json",
                "curve": "curve.csv",
                "trades": "trades.csv",
                "positions": "positions.csv",
                "turnover": "turnover.csv",
                "exposure": "exposure.json",
                "report_md": "reports/report.md",
            },
        },
        "extensions": {
            "dataset_id": dataset_id,
            "symbols": symbols,
            "compiler_version": "compiler_mvp_v1",
            "strategy_id": "buy_and_hold_mvp",
            "evaluation_protocol_v1": ep_meta,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(runspec, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    code2, msg2 = contracts_validate.validate_json(out_path)
    if code2 != contracts_validate.EXIT_OK:
        return EXIT_INVALID, f"INVALID: generated runspec failed schema validation: {msg2}"

    return EXIT_OK, f"OK: wrote runspec to {out_path.as_posix()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.compiler.compile")
    parser.add_argument("--blueprint", required=True, help="Path to a Blueprint JSON (v1).")
    parser.add_argument("--snapshot-id", required=True, help="Data snapshot id to reference in RunSpec.")
    parser.add_argument("--out", required=True, help="Output path for RunSpec JSON.")
    parser.add_argument("--policy-bundle", required=True, help="Path to policy_bundle_v1.yaml (read-only).")
    parser.add_argument(
        "--check-availability",
        action="store_true",
        help="Optional: query DataCatalog to ensure snapshot has data under computed as_of.",
    )
    args = parser.parse_args(argv)

    try:
        code, msg = compile_blueprint_to_runspec(
            blueprint_path=Path(args.blueprint),
            snapshot_id=str(args.snapshot_id),
            policy_bundle_path=Path(args.policy_bundle),
            out_path=Path(args.out),
            check_availability=bool(args.check_availability),
        )
        if code == EXIT_OK:
            print(msg)
        else:
            print(msg, file=sys.stderr)
        return code
    except FileNotFoundError as e:
        print(f"ERROR: file not found: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
