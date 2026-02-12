from __future__ import annotations

import inspect
import json
import signal
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .resolver import resolve_fetch
from .wbdata_bridge import resolve_wbdata_callable
from .wequant_bridge import resolve_wequant_callable


STATUS_PASS_HAS_DATA = "pass_has_data"
STATUS_PASS_EMPTY = "pass_empty"
STATUS_BLOCKED_SOURCE_MISSING = "blocked_source_missing"
STATUS_ERROR_RUNTIME = "error_runtime"

DEFAULT_WINDOW_PROFILE_PATH = Path("docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json")
DEFAULT_EXCEPTION_DECISIONS_PATH = Path("docs/05_data_plane/qa_fetch_exception_decisions_v1.md")


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
    mode: str = "smoke"  # smoke | research | backtest
    timeout_sec: int | None = None
    on_no_data: str = "pass_empty"  # pass_empty | error


@dataclass
class FetchExecutionResult:
    status: str
    reason: str
    source: str | None
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
    it = _coerce_intent(intent)
    pl = _coerce_policy(policy)

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
        function=resolution.target_name,
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
) -> FetchExecutionResult:
    pl = _coerce_policy(policy)
    profile = load_smoke_window_profile(window_profile_path)
    decisions = load_exception_decisions(exception_decisions_path)
    fn_name = str(function).strip()
    if not fn_name:
        raise ValueError("function must be non-empty")

    decision = decisions.get(fn_name, {})
    decision_status = str(decision.get("decision", "")).strip().lower()
    if decision_status in {"pending", "drop", "disabled"}:
        return FetchExecutionResult(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            reason=f"disabled_by_exception_policy: decision={decision_status}",
            source=source_hint,
            resolved_function=fn_name,
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
    fn, resolved_source = _resolve_callable(fn_name, source_hint=source_hint)
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
            source=resolved_source,
            resolved_function=fn_name,
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
            source=resolved_source,
            resolved_function=fn_name,
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
) -> dict[str, str]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    request_path = out_path / "fetch_request.json"
    meta_path = out_path / "fetch_result_meta.json"
    preview_path = out_path / "fetch_preview.csv"
    error_path = out_path / "fetch_error.json"

    request_path.write_text(
        json.dumps(_json_safe(request_payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    meta = asdict(result)
    meta.pop("data", None)
    meta_path.write_text(json.dumps(_json_safe(meta), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _write_preview_csv(preview_path, result)

    if result.status in {STATUS_BLOCKED_SOURCE_MISSING, STATUS_ERROR_RUNTIME}:
        err_obj = {
            "status": result.status,
            "reason": result.reason,
            "source": result.source,
            "resolved_function": result.resolved_function,
            "public_function": result.public_function,
            "mode": result.mode,
            "final_kwargs": _json_safe(result.final_kwargs),
        }
        error_path.write_text(json.dumps(err_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif error_path.exists():
        error_path.unlink()

    paths = {
        "fetch_request_path": request_path.as_posix(),
        "fetch_result_meta_path": meta_path.as_posix(),
        "fetch_preview_path": preview_path.as_posix(),
    }
    if error_path.exists():
        paths["fetch_error_path"] = error_path.as_posix()
    return paths


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


def _resolve_callable(function: str, *, source_hint: str | None) -> tuple[Any, str]:
    hint = (source_hint or "").strip().lower()
    if hint == "wequant":
        return resolve_wequant_callable(function), "wequant"
    if hint == "wbdata":
        return resolve_wbdata_callable(function), "wbdata"
    try:
        return resolve_wequant_callable(function), "wequant"
    except Exception:
        return resolve_wbdata_callable(function), "wbdata"


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

    if source == "wequant":
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
