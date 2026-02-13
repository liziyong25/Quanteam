from __future__ import annotations

import hashlib
import inspect
import json
import signal
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .resolver import resolve_fetch
from .mongo_bridge import resolve_mongo_fetch_callable
from .mysql_bridge import resolve_mysql_fetch_callable
from .source import is_mongo_source, is_mysql_source, normalize_source


STATUS_PASS_HAS_DATA = "pass_has_data"
STATUS_PASS_EMPTY = "pass_empty"
STATUS_BLOCKED_SOURCE_MISSING = "blocked_source_missing"
STATUS_ERROR_RUNTIME = "error_runtime"

DEFAULT_WINDOW_PROFILE_PATH = Path("docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json")
DEFAULT_EXCEPTION_DECISIONS_PATH = Path("docs/05_data_plane/qa_fetch_exception_decisions_v1.md")
DEFAULT_FUNCTION_REGISTRY_PATH = Path("docs/05_data_plane/qa_fetch_function_registry_v1.json")


@dataclass(frozen=True)
class FetchIntent:
    asset: str | None = None
    freq: str | None = None
    venue: str | None = None
    adjust: str = "raw"
    symbols: str | list[str] | None = None
    start: str | None = None
    end: str | None = None
    function_override: str | None = None
    extra_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchExecutionPolicy:
    mode: str = "smoke"  # demo | smoke | research | backtest
    timeout_sec: int | None = None
    on_no_data: str = "pass_empty"  # pass_empty | error | retry


@dataclass
class FetchExecutionResult:
    status: str
    reason: str
    source: str | None
    source_internal: str | None
    engine: str | None
    provider_id: str | None
    provider_internal: str | None
    resolved_function: str | None
    public_function: str | None
    elapsed_sec: float
    row_count: int
    columns: list[str]
    dtypes: dict[str, str]
    preview: Any
    final_kwargs: dict[str, Any]
    mode: str
    data: Any | None = None


def execute_fetch_by_intent(
    intent: FetchIntent | dict[str, Any],
    *,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str | Path = DEFAULT_WINDOW_PROFILE_PATH,
    exception_decisions_path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH,
) -> FetchExecutionResult:
    normalized_intent, normalized_policy = _unwrap_fetch_request_payload(intent, policy)
    it = _coerce_intent(normalized_intent)
    pl = _coerce_policy(normalized_policy)

    if it.function_override:
        kwargs = dict(it.extra_kwargs)
        if it.symbols is not None and "symbols" not in kwargs:
            kwargs["symbols"] = it.symbols
        if it.start is not None and "start" not in kwargs:
            kwargs["start"] = it.start
        if it.end is not None and "end" not in kwargs:
            kwargs["end"] = it.end
        return execute_fetch_by_name(
            function=it.function_override,
            kwargs=kwargs,
            policy=pl,
            window_profile_path=window_profile_path,
            exception_decisions_path=exception_decisions_path,
            public_function=it.function_override,
        )

    if not it.asset or not it.freq:
        raise ValueError("intent must provide asset/freq or function_override")

    resolution = resolve_fetch(asset=it.asset, freq=it.freq, venue=it.venue, adjust=it.adjust)
    kwargs = dict(it.extra_kwargs)
    if it.symbols is not None and "symbols" not in kwargs:
        kwargs["symbols"] = it.symbols
    if it.start is not None and "start" not in kwargs:
        kwargs["start"] = it.start
    if it.end is not None and "end" not in kwargs:
        kwargs["end"] = it.end

    return execute_fetch_by_name(
        function=resolution.public_name,
        kwargs=kwargs,
        policy=pl,
        source_hint=resolution.source,
        public_function=resolution.public_name,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
    )


def execute_fetch_by_name(
    *,
    function: str,
    kwargs: dict[str, Any] | None = None,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    source_hint: str | None = None,
    public_function: str | None = None,
    window_profile_path: str | Path = DEFAULT_WINDOW_PROFILE_PATH,
    exception_decisions_path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH,
    function_registry_path: str | Path = DEFAULT_FUNCTION_REGISTRY_PATH,
) -> FetchExecutionResult:
    pl = _coerce_policy(policy)
    profile = load_smoke_window_profile(window_profile_path)
    decisions = load_exception_decisions(exception_decisions_path)
    registry = load_function_registry(function_registry_path)
    fn_name = str(function).strip()
    if not fn_name:
        raise ValueError("function must be non-empty")

    registry_row = registry.get(fn_name)
    if registry_row is None:
        normalized_hint = normalize_source(source_hint)
        return FetchExecutionResult(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            reason="not_in_baseline",
            source="fetch",
            source_internal=normalized_hint,
            engine=_engine_from_source(normalized_hint),
            provider_id="fetch",
            provider_internal=normalized_hint,
            resolved_function=None,
            public_function=public_function or fn_name,
            elapsed_sec=0.0,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs=dict(kwargs or {}),
            mode=pl.mode,
            data=None,
        )

    target_name = str(registry_row.get("target_name") or fn_name).strip()
    resolved_source_hint = (
        str(registry_row.get("source_internal") or registry_row.get("provider_internal") or "").strip().lower()
        or str(registry_row.get("source") or source_hint or "").strip().lower()
        or None
    )

    decision = decisions.get(fn_name, {})
    decision_status = str(decision.get("decision", "")).strip().lower()
    if decision_status in {"pending", "drop", "disabled"}:
        return FetchExecutionResult(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            reason=f"disabled_by_exception_policy: decision={decision_status}",
            source="fetch",
            source_internal=normalize_source(resolved_source_hint),
            engine=_engine_from_source(resolved_source_hint),
            provider_id="fetch",
            provider_internal=normalize_source(resolved_source_hint),
            resolved_function=target_name,
            public_function=public_function or fn_name,
            elapsed_sec=0.0,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs=dict(kwargs or {}),
            mode=pl.mode,
            data=None,
        )

    merged_kwargs = dict(kwargs or {})
    prof = profile.get(fn_name, {})
    smoke_kwargs = prof.get("smoke_kwargs") if isinstance(prof, dict) else None
    if pl.mode == "smoke" and isinstance(smoke_kwargs, dict):
        for key, value in smoke_kwargs.items():
            merged_kwargs.setdefault(str(key), value)

    timeout_sec = _effective_timeout(pl, prof)
    fn, resolved_source = _resolve_callable(target_name, source_hint=resolved_source_hint)
    final_kwargs = _prepare_kwargs_for_callable(fn, merged_kwargs)

    started = time.time()
    try:
        out = _call_with_timeout(lambda: fn(**final_kwargs), timeout_sec=timeout_sec)
        payload, typ, row_count, cols, dtypes, preview = _normalize_payload(out)
        elapsed = time.time() - started
        if row_count > 0:
            status = STATUS_PASS_HAS_DATA
            reason = "ok"
        else:
            if pl.on_no_data == "error":
                status = STATUS_ERROR_RUNTIME
                reason = "no_data"
            else:
                status = STATUS_PASS_EMPTY
                reason = "no_data"
        return FetchExecutionResult(
            status=status,
            reason=reason,
            source="fetch",
            source_internal=resolved_source,
            engine=_engine_from_source(resolved_source),
            provider_id="fetch",
            provider_internal=resolved_source,
            resolved_function=target_name,
            public_function=public_function or fn_name,
            elapsed_sec=elapsed,
            row_count=row_count,
            columns=cols,
            dtypes=dtypes,
            preview=preview,
            final_kwargs=_json_safe(final_kwargs),
            mode=pl.mode,
            data=payload,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - started
        status, reason = _classify_exception(resolved_source, exc)
        if status == STATUS_PASS_EMPTY and pl.on_no_data == "error":
            status = STATUS_ERROR_RUNTIME
        return FetchExecutionResult(
            status=status,
            reason=reason,
            source="fetch",
            source_internal=resolved_source,
            engine=_engine_from_source(resolved_source),
            provider_id="fetch",
            provider_internal=resolved_source,
            resolved_function=target_name,
            public_function=public_function or fn_name,
            elapsed_sec=elapsed,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[] if status == STATUS_PASS_EMPTY else None,
            final_kwargs=_json_safe(final_kwargs),
            mode=pl.mode,
            data=None,
        )


def write_fetch_evidence(
    *,
    request_payload: dict[str, Any],
    result: FetchExecutionResult,
    out_dir: str | Path,
    step_records: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    request_path = out_path / "fetch_request.json"
    meta_path = out_path / "fetch_result_meta.json"
    preview_path = out_path / "fetch_preview.csv"
    error_path = out_path / "fetch_error.json"
    steps_index_path = out_path / "fetch_steps_index.json"

    normalized_steps: list[tuple[str, dict[str, Any], FetchExecutionResult]] = []
    if isinstance(step_records, list):
        for row in step_records:
            if not isinstance(row, dict):
                continue
            step_kind = str(row.get("step_kind") or "").strip() or "step"
            req = row.get("request_payload")
            res = row.get("result")
            if isinstance(req, dict) and isinstance(res, FetchExecutionResult):
                normalized_steps.append((step_kind, req, res))
    if not normalized_steps:
        normalized_steps = [("single_fetch", request_payload, result)]

    multi_step = len(normalized_steps) > 1
    step_entries: list[dict[str, Any]] = []
    step_written_paths: list[tuple[Path, Path, Path, Path | None]] = []

    for idx, (step_kind, step_request, step_result) in enumerate(normalized_steps, start=1):
        if multi_step:
            prefix = f"step_{idx:03d}"
            req_file = out_path / f"{prefix}_fetch_request.json"
            meta_file = out_path / f"{prefix}_fetch_result_meta.json"
            preview_file = out_path / f"{prefix}_fetch_preview.csv"
            err_file = out_path / f"{prefix}_fetch_error.json"
        else:
            req_file = request_path
            meta_file = meta_path
            preview_file = preview_path
            err_file = error_path

        req_file.write_text(
            json.dumps(_json_safe(step_request), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        step_meta = _build_fetch_meta_doc(step_request, step_result)
        meta_file.write_text(json.dumps(_json_safe(step_meta), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_preview_csv(preview_file, step_result)

        wrote_error = None
        if step_result.status in {STATUS_BLOCKED_SOURCE_MISSING, STATUS_ERROR_RUNTIME}:
            err_obj = {
                "status": step_result.status,
                "reason": step_result.reason,
                "source": step_result.source,
                "source_internal": step_result.source_internal,
                "engine": step_result.engine,
                "provider_id": step_result.provider_id,
                "provider_internal": step_result.provider_internal,
                "resolved_function": step_result.resolved_function,
                "public_function": step_result.public_function,
                "mode": step_result.mode,
                "final_kwargs": _json_safe(step_result.final_kwargs),
            }
            err_file.write_text(json.dumps(err_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            wrote_error = err_file
        elif err_file.exists():
            err_file.unlink()

        step_entry = {
            "step_index": idx,
            "step_kind": step_kind,
            "status": step_result.status,
            "request_path": req_file.as_posix(),
            "result_meta_path": meta_file.as_posix(),
            "preview_path": preview_file.as_posix(),
        }
        if wrote_error is not None:
            step_entry["error_path"] = wrote_error.as_posix()
        step_entries.append(step_entry)
        step_written_paths.append((req_file, meta_file, preview_file, wrote_error))

    if multi_step and step_written_paths:
        final_req, final_meta, final_preview, final_err = step_written_paths[-1]
        shutil.copy2(final_req, request_path)
        shutil.copy2(final_meta, meta_path)
        shutil.copy2(final_preview, preview_path)
        if final_err is not None and final_err.is_file():
            shutil.copy2(final_err, error_path)
        elif error_path.exists():
            error_path.unlink()

    steps_index = {
        "schema_version": "qa_fetch_steps_index_v1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "steps": step_entries,
    }
    steps_index_path.write_text(
        json.dumps(_json_safe(steps_index), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    paths = {
        "fetch_request_path": request_path.as_posix(),
        "fetch_result_meta_path": meta_path.as_posix(),
        "fetch_preview_path": preview_path.as_posix(),
        "fetch_steps_index_path": steps_index_path.as_posix(),
    }
    if error_path.exists():
        paths["fetch_error_path"] = error_path.as_posix()
    return paths


def _build_fetch_meta_doc(request_payload: dict[str, Any], result: FetchExecutionResult) -> dict[str, Any]:
    meta = asdict(result)
    meta.pop("data", None)
    min_ts, max_ts = _extract_time_bounds_from_preview(result.preview)
    as_of = _extract_request_as_of(request_payload)
    meta["selected_function"] = result.resolved_function
    meta["col_count"] = len(result.columns)
    meta["request_hash"] = _canonical_request_hash(request_payload)
    meta["coverage"] = _build_coverage_summary(request_payload, result.preview)
    meta["min_ts"] = min_ts
    meta["max_ts"] = max_ts
    meta["as_of"] = as_of
    meta["availability_summary"] = _build_availability_summary(preview=result.preview, as_of=as_of)
    meta["probe_status"] = result.status
    meta["sanity_checks"] = _build_preview_sanity_checks(result.preview)
    warnings: list[str] = []
    if result.status in {STATUS_BLOCKED_SOURCE_MISSING, STATUS_ERROR_RUNTIME} and result.reason:
        warnings.append(str(result.reason))
    elif result.status == STATUS_PASS_EMPTY:
        warnings.append("no_data")
    meta["warnings"] = warnings
    return meta


def _canonical_request_hash(request_payload: dict[str, Any]) -> str:
    canonical = _json_safe(request_payload)
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_symbols(value: Any) -> list[str]:
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
        return out
    return []


def _extract_request_symbols(request_payload: dict[str, Any]) -> list[str]:
    intent_obj = request_payload.get("intent")
    kwargs_obj = request_payload.get("kwargs")
    values: list[str] = []
    values.extend(_normalize_symbols(request_payload.get("symbols")))
    if isinstance(intent_obj, dict):
        values.extend(_normalize_symbols(intent_obj.get("symbols")))
    if isinstance(kwargs_obj, dict):
        values.extend(_normalize_symbols(kwargs_obj.get("symbol")))
        values.extend(_normalize_symbols(kwargs_obj.get("symbols")))
    deduped = sorted({x for x in values if x})
    return deduped


def _extract_observed_symbols(preview: Any) -> list[str]:
    if not isinstance(preview, list):
        return []
    out: set[str] = set()
    for row in preview:
        if not isinstance(row, dict):
            continue
        for key in ("code", "symbol", "symbols", "ticker"):
            if key in row:
                out.update(_normalize_symbols(row.get(key)))
    return sorted(out)


def _extract_time_bounds_from_preview(preview: Any) -> tuple[str | None, str | None]:
    if not isinstance(preview, list):
        return None, None
    stamps: list[str] = []
    for row in preview:
        if not isinstance(row, dict):
            continue
        for key in ("date", "datetime", "trade_date", "dt", "timestamp"):
            raw = row.get(key)
            if raw is None:
                continue
            val = _json_safe(raw)
            sval = str(val).strip()
            if sval:
                stamps.append(sval)
    if not stamps:
        return None, None
    ordered = sorted(stamps)
    return ordered[0], ordered[-1]


def _build_coverage_summary(request_payload: dict[str, Any], preview: Any) -> dict[str, Any]:
    requested = _extract_request_symbols(request_payload)
    observed = _extract_observed_symbols(preview)
    return {
        "requested_symbol_count": len(requested),
        "requested_symbols": requested,
        "observed_symbol_count": len(observed),
        "observed_symbols": observed,
    }


def _pick_timestamp_field(preview: Any) -> str:
    if not isinstance(preview, list):
        return ""
    candidates = ("date", "datetime", "trade_date", "dt", "timestamp")
    for key in candidates:
        for row in preview:
            if isinstance(row, dict) and key in row:
                return key
    return ""


def _build_preview_sanity_checks(preview: Any) -> dict[str, Any]:
    if not isinstance(preview, list):
        return {
            "timestamp_field": "",
            "timestamp_monotonic_non_decreasing": True,
            "timestamp_duplicate_count": 0,
            "missing_ratio_by_column": {},
            "preview_row_count": 0,
        }

    rows = [row for row in preview if isinstance(row, dict)]
    row_count = len(rows)
    if row_count == 0:
        return {
            "timestamp_field": "",
            "timestamp_monotonic_non_decreasing": True,
            "timestamp_duplicate_count": 0,
            "missing_ratio_by_column": {},
            "preview_row_count": 0,
        }

    ts_field = _pick_timestamp_field(rows)
    ts_values: list[str] = []
    if ts_field:
        for row in rows:
            if ts_field not in row:
                continue
            val = row.get(ts_field)
            if val is None:
                continue
            sval = str(_json_safe(val)).strip()
            if sval:
                ts_values.append(sval)

    monotonic = True
    for idx in range(1, len(ts_values)):
        if ts_values[idx] < ts_values[idx - 1]:
            monotonic = False
            break
    duplicate_count = len(ts_values) - len(set(ts_values))

    all_cols: set[str] = set()
    for row in rows:
        all_cols.update(str(k) for k in row.keys())

    missing_ratio: dict[str, float] = {}
    for col in sorted(all_cols):
        miss = 0
        for row in rows:
            val = row.get(col) if col in row else None
            if val is None:
                miss += 1
                continue
            if isinstance(val, str) and not val.strip():
                miss += 1
        missing_ratio[col] = round(miss / row_count, 6)

    return {
        "timestamp_field": ts_field,
        "timestamp_monotonic_non_decreasing": monotonic,
        "timestamp_duplicate_count": int(duplicate_count),
        "missing_ratio_by_column": missing_ratio,
        "preview_row_count": row_count,
    }


def _extract_request_as_of(request_payload: dict[str, Any]) -> str | None:
    candidates: list[Any] = [request_payload.get("as_of")]
    intent_obj = request_payload.get("intent")
    if isinstance(intent_obj, dict):
        candidates.append(intent_obj.get("as_of"))
    kwargs_obj = request_payload.get("kwargs")
    if isinstance(kwargs_obj, dict):
        candidates.append(kwargs_obj.get("as_of"))
    for raw in candidates:
        if raw is None:
            continue
        sval = str(_json_safe(raw)).strip()
        if sval:
            return sval
    return None


def _parse_dt_for_compare(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception:
        if len(text) == 10 and text.count("-") == 2:
            try:
                return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_availability_summary(*, preview: Any, as_of: str | None) -> dict[str, Any]:
    out = {
        "has_as_of": as_of is not None,
        "as_of": as_of,
        "available_at_field_present": False,
        "available_at_min": None,
        "available_at_max": None,
        "available_at_violation_count": 0,
        "rule": "available_at<=as_of",
    }
    if not isinstance(preview, list):
        return out

    rows = [row for row in preview if isinstance(row, dict)]
    if not rows:
        return out

    if not any("available_at" in row for row in rows):
        return out

    out["available_at_field_present"] = True
    available_rows: list[str] = []
    for row in rows:
        val = row.get("available_at")
        if val is None:
            continue
        sval = str(_json_safe(val)).strip()
        if sval:
            available_rows.append(sval)
    if not available_rows:
        return out

    ordered = sorted(available_rows)
    out["available_at_min"] = ordered[0]
    out["available_at_max"] = ordered[-1]

    as_of_dt = _parse_dt_for_compare(as_of or "")
    if as_of_dt is None:
        return out

    violations = 0
    for row_val in available_rows:
        av_dt = _parse_dt_for_compare(row_val)
        if av_dt is None:
            continue
        if av_dt > as_of_dt:
            violations += 1
    out["available_at_violation_count"] = violations
    return out


def load_smoke_window_profile(path: str | Path = DEFAULT_WINDOW_PROFILE_PATH) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = payload.get("functions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function", "")).strip()
        if not fn:
            continue
        out[fn] = row
    return out


def load_exception_decisions(path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH) -> dict[str, dict[str, str]]:
    p = Path(path)
    if not p.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("|---") or "function | issue_type" in line:
            continue
        parts = [x.strip() for x in line.strip("|").split("|")]
        if len(parts) < 6:
            continue
        fn = parts[0].strip("`")
        if not fn.startswith("fetch_"):
            continue
        out[fn] = {
            "issue_type": parts[1],
            "smoke_policy": parts[2],
            "research_policy": parts[3],
            "decision": parts[4],
            "notes": parts[5],
        }
    return out


def load_function_registry(path: str | Path = DEFAULT_FUNCTION_REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = payload.get("functions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function", "")).strip()
        status = str(row.get("status", "")).strip().lower()
        if not fn.startswith("fetch_"):
            continue
        if status not in {"active", "allow", "review", ""}:
            continue
        out[fn] = row
    return out


def _coerce_intent(intent: FetchIntent | dict[str, Any]) -> FetchIntent:
    if isinstance(intent, FetchIntent):
        return intent
    if not isinstance(intent, dict):
        raise ValueError("intent must be FetchIntent or dict")
    extra_kwargs = intent.get("extra_kwargs")
    if not isinstance(extra_kwargs, dict):
        extra_kwargs = {}
    return FetchIntent(
        asset=intent.get("asset"),
        freq=intent.get("freq"),
        venue=intent.get("venue"),
        adjust=str(intent.get("adjust", "raw") or "raw"),
        symbols=intent.get("symbols"),
        start=intent.get("start"),
        end=intent.get("end"),
        function_override=intent.get("function_override"),
        extra_kwargs=extra_kwargs,
    )


def _unwrap_fetch_request_payload(
    intent: FetchIntent | dict[str, Any],
    policy: FetchExecutionPolicy | dict[str, Any] | None,
) -> tuple[FetchIntent | dict[str, Any], FetchExecutionPolicy | dict[str, Any] | None]:
    if isinstance(intent, FetchIntent) or not isinstance(intent, dict):
        return intent, policy

    wrapper_policy = policy if policy is not None else intent.get("policy")
    intent_obj = intent.get("intent")

    if intent_obj is not None:
        if not isinstance(intent_obj, dict):
            raise ValueError("fetch_request.intent must be an object when provided")
        merged_intent: dict[str, Any] = dict(intent_obj)
        for key in ("asset", "freq", "venue", "adjust", "symbols", "start", "end", "function_override"):
            if merged_intent.get(key) is None and intent.get(key) is not None:
                merged_intent[key] = intent.get(key)

        function_name = intent.get("function")
        if merged_intent.get("function_override") is None and isinstance(function_name, str) and function_name.strip():
            merged_intent["function_override"] = function_name.strip()

        kwargs_obj = intent.get("kwargs")
        if kwargs_obj is not None and not isinstance(kwargs_obj, dict):
            raise ValueError("fetch_request.kwargs must be an object when provided")

        extra_kwargs = merged_intent.get("extra_kwargs")
        if extra_kwargs is not None and not isinstance(extra_kwargs, dict):
            raise ValueError("intent.extra_kwargs must be an object when provided")

        merged_kwargs: dict[str, Any] = {}
        if isinstance(kwargs_obj, dict):
            merged_kwargs.update(kwargs_obj)
        if isinstance(extra_kwargs, dict):
            merged_kwargs.update(extra_kwargs)
        if merged_kwargs:
            merged_intent["extra_kwargs"] = merged_kwargs
        return merged_intent, wrapper_policy

    # Compatibility with function+kwargs shaped fetch_request without an explicit intent block.
    kwargs_obj = intent.get("kwargs")
    function_name = intent.get("function")
    if kwargs_obj is not None or function_name is not None or "policy" in intent:
        if kwargs_obj is not None and not isinstance(kwargs_obj, dict):
            raise ValueError("fetch_request.kwargs must be an object when provided")
        merged_intent = {
            "asset": intent.get("asset"),
            "freq": intent.get("freq"),
            "venue": intent.get("venue"),
            "adjust": intent.get("adjust", "raw"),
            "symbols": intent.get("symbols"),
            "start": intent.get("start"),
            "end": intent.get("end"),
            "function_override": function_name,
            "extra_kwargs": dict(kwargs_obj or {}),
        }
        return merged_intent, wrapper_policy

    return intent, policy


def _coerce_policy(policy: FetchExecutionPolicy | dict[str, Any] | None) -> FetchExecutionPolicy:
    if policy is None:
        return FetchExecutionPolicy()
    if isinstance(policy, FetchExecutionPolicy):
        return policy
    if not isinstance(policy, dict):
        raise ValueError("policy must be FetchExecutionPolicy or dict")
    return FetchExecutionPolicy(
        mode=str(policy.get("mode", "smoke") or "smoke"),
        timeout_sec=policy.get("timeout_sec"),
        on_no_data=str(policy.get("on_no_data", "pass_empty") or "pass_empty"),
    )


def _effective_timeout(policy: FetchExecutionPolicy, profile_item: dict[str, Any]) -> int | None:
    if policy.timeout_sec is not None:
        return int(policy.timeout_sec)
    if policy.mode == "smoke":
        raw = profile_item.get("smoke_timeout_sec") if isinstance(profile_item, dict) else None
        if raw is None:
            return 30
        try:
            return int(raw)
        except Exception:
            return 30
    return None


def _engine_from_source(source_internal: str | None) -> str | None:
    normalized = normalize_source(source_internal)
    if is_mongo_source(normalized):
        return "mongo"
    if is_mysql_source(normalized):
        return "mysql"
    return None


def _resolve_callable(function: str, *, source_hint: str | None) -> tuple[Any, str]:
    hint = normalize_source(source_hint)
    if is_mongo_source(hint):
        return resolve_mongo_fetch_callable(function), "mongo_fetch"
    if is_mysql_source(hint):
        return resolve_mysql_fetch_callable(function), "mysql_fetch"
    try:
        return resolve_mongo_fetch_callable(function), "mongo_fetch"
    except Exception:
        return resolve_mysql_fetch_callable(function), "mysql_fetch"


def _prepare_kwargs_for_callable(fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    params = sig.parameters
    out = dict(kwargs)

    if "symbols" in out:
        symbols = out.pop("symbols")
        if "code" in params and "code" not in out:
            out["code"] = symbols
        elif "symbol" in params and "symbol" not in out:
            out["symbol"] = symbols
        elif _has_var_kw(params):
            out["symbols"] = symbols

    if "freq" in out and "frequence" in params and "frequence" not in out:
        out["frequence"] = out.pop("freq")

    if "format" in params and "format" not in out:
        out["format"] = "pd"

    if not _has_var_kw(params):
        out = {k: v for k, v in out.items() if k in params}

    missing = []
    for name, p in params.items():
        if p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            continue
        if p.default is inspect._empty and name not in out:
            missing.append(name)
    if missing:
        raise ValueError(f"missing required params for {fn.__name__}: {', '.join(missing)}")

    return out


def _has_var_kw(params: dict[str, inspect.Parameter]) -> bool:
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


def _normalize_payload(payload: Any) -> tuple[Any, str, int, list[str], dict[str, str], Any]:
    try:
        import pandas as pd
    except Exception:
        pd = None

    data = payload
    typ = type(payload).__name__
    if pd is not None and isinstance(payload, pd.DataFrame):
        pass
    else:
        data_attr = getattr(payload, "data", None)
        if pd is not None and isinstance(data_attr, pd.DataFrame):
            data = data_attr
            typ = type(payload).__name__

    if data is None:
        return None, typ, 0, [], {}, None

    if pd is not None and isinstance(data, pd.DataFrame):
        cols = [str(c) for c in data.columns]
        dtypes = {str(k): str(v) for k, v in data.dtypes.items()}
        row_count = int(len(data))
        preview = _json_safe(data.head(5).to_dict(orient="records")) if row_count > 0 else []
        return data, "DataFrame", row_count, cols, dtypes, preview

    try:
        row_count = int(len(data))
    except Exception:
        row_count = 1
    return data, typ, row_count, [], {}, _json_safe(data)


def _classify_exception(source: str | None, exc: Exception) -> tuple[str, str]:
    msg = f"{type(exc).__name__}: {exc}"
    lower = msg.lower()
    if isinstance(exc, TimeoutError):
        return STATUS_ERROR_RUNTIME, msg

    blocked_markers = [
        "unknown table",
        "doesn't exist",
        "does not exist",
        "no such table",
        "can't connect to mysql",
        "connection refused",
        "serverselectiontimeout",
    ]
    if any(marker in lower for marker in blocked_markers):
        return STATUS_BLOCKED_SOURCE_MISSING, msg

    if is_mongo_source(source):
        no_data_markers = [
            "none",
            "empty",
            "no data",
            "not found",
            "dataframe' object has no attribute 'datetime'",
        ]
        if any(marker in lower for marker in no_data_markers):
            return STATUS_PASS_EMPTY, f"no_data: {msg}"

    return STATUS_ERROR_RUNTIME, msg


def _call_with_timeout(fn: Any, *, timeout_sec: int | None) -> Any:
    if timeout_sec is None or timeout_sec <= 0 or not hasattr(signal, "SIGALRM"):
        return fn()

    def _handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"timeout_skip_{timeout_sec}s")

    prev = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_sec)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev)


def _write_preview_csv(path: Path, result: FetchExecutionResult) -> None:
    try:
        import pandas as pd
    except Exception:
        pd = None

    data = result.data
    if pd is not None and isinstance(data, pd.DataFrame):
        data.head(20).to_csv(path, index=False)
        return

    preview = result.preview
    if isinstance(preview, list) and preview and isinstance(preview[0], dict):
        if pd is not None:
            pd.DataFrame(preview).to_csv(path, index=False)
        else:
            path.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    row = {
        "status": result.status,
        "reason": result.reason,
        "row_count": result.row_count,
        "source": result.source,
        "source_internal": result.source_internal,
        "engine": result.engine,
        "resolved_function": result.resolved_function,
    }
    path.write_text(",".join(row.keys()) + "\n" + ",".join(str(v) for v in row.values()) + "\n", encoding="utf-8")


def _json_safe(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, tuple):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    try:
        import pandas as pd

        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
    except Exception:
        pass
    return str(obj)
