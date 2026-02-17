from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from quant_eam.qa_fetch.runtime import (
    FetchExecutionPolicy,
    FetchExecutionResult,
    STATUS_BLOCKED_SOURCE_MISSING,
    STATUS_ERROR_RUNTIME,
    STATUS_PASS_EMPTY,
    STATUS_PASS_HAS_DATA,
    load_function_registry,
    write_fetch_evidence,
)
from quant_eam.qa_fetch.facade import execute_fetch_by_intent, execute_fetch_by_name

_AUTO_LIST_BY_ASSET: dict[str, list[str]] = {
    "stock": ["fetch_stock_list"],
    "future": ["fetch_future_list", "fetch_ctp_future_list"],
    "etf": ["fetch_etf_list"],
    "index": ["fetch_index_list"],
    "hkstock": ["fetch_get_hkstock_list"],
    "bond": ["fetch_bond_date_list"],
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_fetch_out_dir(*, out_dir: Path, payload: dict[str, Any]) -> Path:
    for parent in [out_dir, *out_dir.parents]:
        if parent.name == "outputs":
            return parent / "fetch"

    job_id = str(payload.get("job_id", "")).strip()
    if job_id:
        job_root = Path(os.getenv("EAM_JOB_ROOT", "/jobs"))
        return job_root / job_id / "outputs" / "fetch"
    return out_dir / "fetch"


def _error_result(
    *,
    reason: str,
    mode: str,
    source: str | None = None,
    source_internal: str | None = None,
    engine: str | None = None,
    resolved_function: str | None = None,
    public_function: str | None = None,
    kwargs: dict[str, Any] | None = None,
) -> FetchExecutionResult:
    return FetchExecutionResult(
        status=STATUS_ERROR_RUNTIME,
        reason=reason,
        source=source,
        source_internal=source_internal,
        engine=engine,
        provider_id="fetch" if source else None,
        provider_internal=source_internal,
        resolved_function=resolved_function,
        public_function=public_function or resolved_function,
        elapsed_sec=0.0,
        row_count=0,
        columns=[],
        dtypes={},
        preview=None,
        final_kwargs=dict(kwargs or {}),
        mode=mode,
        data=None,
    )


@lru_cache(maxsize=1)
def _fetch_registry_names() -> set[str]:
    return set(load_function_registry().keys())


def _normalize_symbol_tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        token = value.strip()
        return [token] if token else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                token = item.strip()
                if token:
                    out.append(token)
        return out
    return []


def _extract_explicit_symbols(fetch_request: dict[str, Any]) -> list[str]:
    out: list[str] = []
    out.extend(_normalize_symbol_tokens(fetch_request.get("symbols")))
    intent_obj = fetch_request.get("intent")
    if isinstance(intent_obj, dict):
        out.extend(_normalize_symbol_tokens(intent_obj.get("symbols")))
    kwargs_obj = fetch_request.get("kwargs")
    if isinstance(kwargs_obj, dict):
        out.extend(_normalize_symbol_tokens(kwargs_obj.get("symbol")))
        out.extend(_normalize_symbol_tokens(kwargs_obj.get("symbols")))
    # Keep deterministic order while deduping.
    seen: set[str] = set()
    uniq: list[str] = []
    for token in out:
        if token in seen:
            continue
        seen.add(token)
        uniq.append(token)
    return uniq


def _is_auto_symbols_enabled(fetch_request: dict[str, Any]) -> bool:
    top_level = fetch_request.get("auto_symbols")
    intent_obj = fetch_request.get("intent")
    intent_level = intent_obj.get("auto_symbols") if isinstance(intent_obj, dict) else None
    if isinstance(intent_level, bool):
        return intent_level
    if isinstance(top_level, bool):
        return top_level
    return False


def _extract_sample_plan(fetch_request: dict[str, Any]) -> tuple[int, str]:
    sample_obj = fetch_request.get("sample")
    intent_obj = fetch_request.get("intent")
    if not isinstance(sample_obj, dict) and isinstance(intent_obj, dict):
        sample_obj = intent_obj.get("sample")
    sample_n = 5
    sample_method = "stable_first_n"
    if isinstance(sample_obj, dict):
        raw_n = sample_obj.get("n")
        if isinstance(raw_n, (int, float)):
            try:
                sample_n = max(1, int(raw_n))
            except Exception:
                sample_n = 5
        raw_method = sample_obj.get("method")
        if isinstance(raw_method, str) and raw_method.strip():
            sample_method = raw_method.strip()
    return sample_n, sample_method


def _extract_candidates_from_preview(preview: Any) -> list[str]:
    if not isinstance(preview, list):
        return []
    out: list[str] = []
    for row in preview:
        if not isinstance(row, dict):
            continue
        for key in ("code", "symbol", "ticker", "secid", "wind_code"):
            out.extend(_normalize_symbol_tokens(row.get(key)))
    # Deterministic stable dedupe.
    uniq: list[str] = []
    seen: set[str] = set()
    for token in out:
        if token in seen:
            continue
        seen.add(token)
        uniq.append(token)
    return uniq


def _select_sample_symbols(candidates: list[str], sample_n: int, sample_method: str) -> list[str]:
    # Default strategy is stable-first-n as required by planner contract.
    if sample_method != "stable_first_n":
        sample_method = "stable_first_n"
    return candidates[: max(1, int(sample_n))]


def _resolve_list_function(fetch_request: dict[str, Any]) -> str | None:
    registry = _fetch_registry_names()
    candidates: list[str] = []

    fn_name = fetch_request.get("function")
    if isinstance(fn_name, str) and fn_name.strip():
        day_fn = fn_name.strip()
        if day_fn.endswith("_day"):
            candidates.append(day_fn[:-4] + "_list")
        if day_fn.endswith("_min"):
            candidates.append(day_fn[:-4] + "_list")
        if day_fn.endswith("_transaction"):
            candidates.append(day_fn[:-12] + "_list")

    intent_obj = fetch_request.get("intent")
    asset = None
    if isinstance(intent_obj, dict):
        raw_asset = intent_obj.get("asset")
        if isinstance(raw_asset, str) and raw_asset.strip():
            asset = raw_asset.strip().lower()
    if asset in _AUTO_LIST_BY_ASSET:
        candidates.extend(_AUTO_LIST_BY_ASSET[asset])

    for name in candidates:
        if name in registry:
            return name

    fallback = sorted([x for x in registry if x.endswith("_list")])
    return fallback[0] if fallback else None


def _build_list_request(fetch_request: dict[str, Any], *, mode: str, policy_obj: dict[str, Any]) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    out: dict[str, Any] = {
        "mode": mode,
        "policy": dict(policy_obj),
    }
    list_function = _resolve_list_function(fetch_request)
    list_kwargs: dict[str, Any] = {}

    intent_obj = fetch_request.get("intent")
    if isinstance(intent_obj, dict):
        for key in ("start", "end", "venue", "adjust"):
            if intent_obj.get(key) is not None:
                list_kwargs[key] = intent_obj.get(key)

    kwargs_obj = fetch_request.get("kwargs")
    if isinstance(kwargs_obj, dict):
        for key in ("start", "end", "venue", "adjust"):
            if kwargs_obj.get(key) is not None:
                list_kwargs[key] = kwargs_obj.get(key)

    if list_function:
        out["function"] = list_function
        out["kwargs"] = dict(list_kwargs)
    else:
        out["reason"] = "auto_symbols_list_function_missing"
    return out, list_function, list_kwargs


def _inject_symbols_for_day(fetch_request: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    req = json.loads(json.dumps(fetch_request, ensure_ascii=True))
    symbol_payload: str | list[str]
    if len(symbols) == 1:
        symbol_payload = symbols[0]
    else:
        symbol_payload = symbols

    req["symbols"] = symbol_payload
    if "auto_symbols" in req:
        req["auto_symbols"] = False
    intent_obj = req.get("intent")
    if isinstance(intent_obj, dict):
        intent_obj["symbols"] = symbol_payload
        if "auto_symbols" in intent_obj:
            intent_obj["auto_symbols"] = False
    kwargs_obj = req.get("kwargs")
    if isinstance(kwargs_obj, dict):
        if "symbol" in kwargs_obj:
            kwargs_obj["symbol"] = symbol_payload
        else:
            kwargs_obj["symbols"] = symbol_payload
    return req


def _planner_sample_result(*, mode: str, symbols: list[str], sample_n: int, sample_method: str) -> FetchExecutionResult:
    status = STATUS_PASS_HAS_DATA if symbols else STATUS_PASS_EMPTY
    reason = "ok" if symbols else "no_candidates"
    rows = [{"symbol": token, "rank": i + 1} for i, token in enumerate(symbols)]
    return FetchExecutionResult(
        status=status,
        reason=reason,
        source="fetch",
        source_internal="planner",
        engine=None,
        provider_id="fetch",
        provider_internal="planner",
        resolved_function="planner_sample_symbols",
        public_function="planner_sample_symbols",
        elapsed_sec=0.0,
        row_count=len(rows),
        columns=["symbol", "rank"] if rows else [],
        dtypes={"symbol": "object", "rank": "int64"} if rows else {},
        preview=rows,
        final_kwargs={"sample_n": sample_n, "sample_method": sample_method},
        mode=mode,
        data=rows,
    )


def _run_auto_symbols_planner(
    *,
    fetch_request: dict[str, Any],
    mode: str,
    policy: FetchExecutionPolicy,
    policy_obj: dict[str, Any],
    window_profile: str | None,
    exception_path: str | None,
) -> tuple[FetchExecutionResult, list[dict[str, Any]], list[str]]:
    step_records: list[dict[str, Any]] = []
    sampled_symbols: list[str] = []

    list_request, list_function, list_kwargs = _build_list_request(fetch_request, mode=mode, policy_obj=policy_obj)
    if not list_function:
        list_result = _error_result(reason="auto_symbols: list function is not resolvable", mode=mode)
    else:
        try:
            list_result = execute_fetch_by_name(
                function=list_function,
                kwargs=dict(list_kwargs),
                policy=policy,
                source_hint=str(fetch_request.get("source_hint", "") or "") or None,
                public_function=list_function,
                window_profile_path=window_profile or "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
                exception_decisions_path=exception_path or "docs/05_data_plane/qa_fetch_exception_decisions_v1.md",
            )
        except Exception as exc:  # noqa: BLE001
            list_result = _error_result(reason=f"{type(exc).__name__}: {exc}", mode=mode, resolved_function=list_function)
    step_records.append({"step_kind": "list", "request_payload": list_request, "result": list_result})

    sample_n, sample_method = _extract_sample_plan(fetch_request)
    if list_result.status == STATUS_PASS_HAS_DATA:
        candidates = _extract_candidates_from_preview(list_result.preview)
        sampled_symbols = _select_sample_symbols(candidates, sample_n=sample_n, sample_method=sample_method)
        sample_result = _planner_sample_result(
            mode=mode,
            symbols=sampled_symbols,
            sample_n=sample_n,
            sample_method=sample_method,
        )
    elif list_result.status == STATUS_PASS_EMPTY:
        sample_result = _planner_sample_result(mode=mode, symbols=[], sample_n=sample_n, sample_method=sample_method)
    else:
        sample_result = FetchExecutionResult(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            reason=f"upstream_list_failed: {list_result.status}",
            source="fetch",
            source_internal="planner",
            engine=None,
            provider_id="fetch",
            provider_internal="planner",
            resolved_function="planner_sample_symbols",
            public_function="planner_sample_symbols",
            elapsed_sec=0.0,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs={"sample_n": sample_n, "sample_method": sample_method},
            mode=mode,
            data=None,
        )
    sample_request = {
        "mode": mode,
        "planner_step": "sample",
        "sample": {"n": sample_n, "method": sample_method},
        "candidates_preview_count": int(getattr(list_result, "row_count", 0)),
    }
    step_records.append({"step_kind": "sample", "request_payload": sample_request, "result": sample_result})

    day_request = _inject_symbols_for_day(fetch_request, sampled_symbols)
    if sampled_symbols:
        try:
            if isinstance(day_request.get("function"), str) and str(day_request.get("function")).strip():
                fn_name = str(day_request.get("function")).strip()
                kwargs = day_request.get("kwargs")
                kwargs = dict(kwargs) if isinstance(kwargs, dict) else {}
                day_result = execute_fetch_by_name(
                    function=fn_name,
                    kwargs=kwargs,
                    policy=policy,
                    source_hint=str(day_request.get("source_hint", "") or "") or None,
                    public_function=str(day_request.get("public_function", "") or "") or None,
                    window_profile_path=window_profile or "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
                    exception_decisions_path=exception_path or "docs/05_data_plane/qa_fetch_exception_decisions_v1.md",
                )
            else:
                day_result = execute_fetch_by_intent(
                    day_request,
                    policy=policy,
                    window_profile_path=window_profile or "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
                    exception_decisions_path=exception_path or "docs/05_data_plane/qa_fetch_exception_decisions_v1.md",
                )
        except Exception as exc:  # noqa: BLE001
            day_result = _error_result(reason=f"{type(exc).__name__}: {exc}", mode=mode)
    else:
        day_result = _error_result(reason="auto_symbols: sample step produced no symbols", mode=mode)
    step_records.append({"step_kind": "day", "request_payload": day_request, "result": day_result})
    return day_result, step_records, sampled_symbols


def _run_fetch_request(*, payload: dict[str, Any], out_dir: Path) -> tuple[dict[str, Any], list[Path]]:
    fetch_request = payload.get("fetch_request")
    if not isinstance(fetch_request, dict):
        return {"enabled": False, "reason": "no_fetch_request"}, []

    mode = str(fetch_request.get("mode", "smoke") or "smoke")
    policy_obj = fetch_request.get("policy")
    policy_payload = dict(policy_obj) if isinstance(policy_obj, dict) else {}
    policy_payload.setdefault("mode", mode)
    policy = FetchExecutionPolicy(**policy_payload)
    window_profile = fetch_request.get("window_profile_path") or None
    exception_path = fetch_request.get("exception_decisions_path") or None
    auto_symbols_enabled = _is_auto_symbols_enabled(fetch_request)
    explicit_symbols = _extract_explicit_symbols(fetch_request)
    planner_applied = auto_symbols_enabled and not explicit_symbols
    step_records: list[dict[str, Any]] | None = None
    planner_sample_symbols: list[str] = []

    try:
        if planner_applied:
            result, step_records, planner_sample_symbols = _run_auto_symbols_planner(
                fetch_request=fetch_request,
                mode=mode,
                policy=policy,
                policy_obj=policy_payload,
                window_profile=window_profile,
                exception_path=exception_path,
            )
        elif isinstance(fetch_request.get("function"), str) and str(fetch_request.get("function")).strip():
            fn_name = str(fetch_request.get("function")).strip()
            kwargs = fetch_request.get("kwargs")
            kwargs = dict(kwargs) if isinstance(kwargs, dict) else {}
            result = execute_fetch_by_name(
                function=fn_name,
                kwargs=kwargs,
                policy=policy,
                source_hint=str(fetch_request.get("source_hint", "") or "") or None,
                public_function=str(fetch_request.get("public_function", "") or "") or None,
                window_profile_path=window_profile or "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
                exception_decisions_path=exception_path or "docs/05_data_plane/qa_fetch_exception_decisions_v1.md",
            )
        else:
            intent_obj = fetch_request.get("intent")
            if isinstance(intent_obj, dict):
                intent_payload = dict(intent_obj)
            else:
                intent_payload = {
                    "asset": fetch_request.get("asset"),
                    "freq": fetch_request.get("freq"),
                    "venue": fetch_request.get("venue"),
                    "adjust": fetch_request.get("adjust", "raw"),
                    "symbols": fetch_request.get("symbols"),
                    "start": fetch_request.get("start"),
                    "end": fetch_request.get("end"),
                    "function_override": fetch_request.get("function_override"),
                    "extra_kwargs": fetch_request.get("extra_kwargs", {}),
                }
            result = execute_fetch_by_intent(
                intent_payload,
                policy=policy,
                window_profile_path=window_profile or "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
                exception_decisions_path=exception_path or "docs/05_data_plane/qa_fetch_exception_decisions_v1.md",
            )
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        result = _error_result(
            reason=reason,
            mode=mode,
            source=None,
            resolved_function=str(fetch_request.get("function", "") or "") or None,
            public_function=str(fetch_request.get("public_function", "") or "") or None,
            kwargs=fetch_request.get("kwargs") if isinstance(fetch_request.get("kwargs"), dict) else {},
        )

    fetch_out_dir = _resolve_fetch_out_dir(out_dir=out_dir, payload=payload)
    path_map = write_fetch_evidence(
        request_payload=fetch_request,
        result=result,
        out_dir=fetch_out_dir,
        step_records=step_records,
    )
    fetch_files = [Path(v) for v in path_map.values() if isinstance(v, str)]
    meta = {
        "enabled": True,
        "status": result.status,
        "reason": result.reason,
        "mode": result.mode,
        "source": result.source,
        "source_internal": result.source_internal,
        "engine": result.engine,
        "resolved_function": result.resolved_function,
        "public_function": result.public_function,
        "row_count": result.row_count,
        "planner_applied": planner_applied,
        "planner_sampled_symbols": planner_sample_symbols,
        "planner_step_count": len(step_records or []),
        "evidence_paths": path_map,
    }
    return meta, fetch_files


def run_demo_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    if str(provider).strip() != "mock":
        raise ValueError("provider 'external' is not supported in demo_agent MVP")
    payload = _load_json(Path(input_path))
    if not isinstance(payload, dict):
        raise ValueError("demo_agent input must be a JSON object")
    fetch_meta, fetch_files = _run_fetch_request(payload=payload, out_dir=Path(out_dir))

    run_plan = {
        "schema_version": "demo_agent_plan_v1",
        "agent_id": "demo_agent_v1",
        "job_id": payload.get("job_id"),
        "snapshot_id": payload.get("snapshot_id"),
        "symbols": payload.get("symbols"),
        "start": payload.get("start"),
        "end": payload.get("end"),
        "as_of": payload.get("as_of"),
        "fetch": fetch_meta,
        "notes": [
            "Demo step is deterministic and read-only.",
            "Trace preview execution is performed by orchestrator deterministic kernel.",
        ],
    }
    out_path = Path(out_dir) / "demo_plan.json"
    _write_json(out_path, run_plan)
    return [out_path, *fetch_files]
