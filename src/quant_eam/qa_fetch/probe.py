from __future__ import annotations

import inspect
import json
import os
import re
import signal
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .wbdata_bridge import resolve_wbdata_callable
from .wequant_bridge import resolve_wequant_callable


STATUS_PASS_HAS_DATA = "pass_has_data"
STATUS_PASS_EMPTY = "pass_empty"
STATUS_BLOCKED_SOURCE_MISSING = "blocked_source_missing"
STATUS_ERROR_RUNTIME = "error_runtime"

DEFAULT_MATRIX_V3_PATH = Path("docs/05_data_plane/_draft_qa_fetch_rename_matrix_v3.md")
DEFAULT_EXPECTED_COUNT = 0
DEFAULT_OUTPUT_DIR = Path("docs/05_data_plane/qa_fetch_probe_v3")
_MYSQL_WINDOW_CACHE: dict[str, tuple[str | None, str | None]] = {}
_MYSQL_SYMBOL_CACHE: dict[str, str | None] = {}
PROBE_TIMEOUT_SEC = 30
WB_BOND_DEFAULT_SYMBOL = "240011.IB"
WB_BOND_DEFAULT_START = "2010-01-01"
WB_BOND_DEFAULT_END = "2030-01-01"
WB_DEFAULT_ENV = {
    "DB_NAME": "test2",
    "DB_NAME_TEST2": "test2",
    "DB_USER": "root",
    "DB_PASSWORD": "liziyong25",
    "DB_HOST": "192.168.31.241",
    "DB_PORT": "3306",
}
WEQUANT_DEFAULT_ENV = {
    "WEQUANT_MONGO_URI": "mongodb://192.168.31.241:27017/quantaxis",
    "WEQUANT_DB_NAME": "quantaxis",
    "MONGO_URI": "mongodb://192.168.31.241:27017/quantaxis",
    "MONGO_DB_NAME": "quantaxis",
}


@dataclass(frozen=True)
class MatrixFunction:
    source: str
    function: str


@dataclass(frozen=True)
class ProbeResult:
    source: str
    function: str
    status: str
    reason: str
    type: str
    len: int
    columns: list[str]
    dtypes: dict[str, str]
    head_preview: Any
    args_preview: dict[str, Any]


@dataclass
class _CallSpec:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    blocked_reason: str | None = None


@dataclass
class _MongoContext:
    db: Any | None
    collections: set[str]
    error: str | None


@dataclass
class _MysqlContext:
    engine: Any | None
    tables: set[str]
    error: str | None


def parse_matrix_v3(path: str | Path = DEFAULT_MATRIX_V3_PATH) -> list[MatrixFunction]:
    matrix_path = Path(path)
    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    rows: list[MatrixFunction] = []
    for line in lines:
        if not line.startswith("| "):
            continue
        if "source | old_name | proposed_name" in line:
            continue
        if line.startswith("|---"):
            continue
        parts = [item.strip() for item in line.strip("|").split("|")]
        if len(parts) < 8:
            continue
        source = parts[0]
        function = parts[1].strip("`")
        rows.append(MatrixFunction(source=source, function=function))
    return rows


def probe_matrix_v3(
    *,
    matrix_path: str | Path = DEFAULT_MATRIX_V3_PATH,
    expected_count: int = DEFAULT_EXPECTED_COUNT,
) -> list[ProbeResult]:
    rows = parse_matrix_v3(matrix_path)
    if expected_count > 0 and len(rows) != expected_count:
        raise ValueError(
            f"matrix row count mismatch: expected={expected_count} actual={len(rows)} path={matrix_path}"
        )

    mongo_ctx = _load_mongo_context()
    mysql_ctx = _load_mysql_context()

    out: list[ProbeResult] = []
    for row in rows:
        try:
            if row.source == "wequant":
                result = _probe_wequant(row.function, mongo_ctx)
            elif row.source == "wbdata":
                result = _probe_wbdata(row.function, mysql_ctx)
            else:
                result = ProbeResult(
                    source=row.source,
                    function=row.function,
                    status=STATUS_ERROR_RUNTIME,
                    reason=f"unsupported source={row.source!r}",
                    type="unknown",
                    len=0,
                    columns=[],
                    dtypes={},
                    head_preview=None,
                    args_preview={},
                )
        except Exception as exc:  # noqa: BLE001
            result = ProbeResult(
                source=row.source,
                function=row.function,
                status=STATUS_ERROR_RUNTIME,
                reason=f"internal_probe_error: {type(exc).__name__}: {exc}",
                type="unknown",
                len=0,
                columns=[],
                dtypes={},
                head_preview=None,
                args_preview={},
            )
        out.append(result)
    return out


def results_to_frame(results: list[ProbeResult]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(
            columns=[
                "source",
                "function",
                "status",
                "reason",
                "type",
                "len",
                "columns",
                "dtypes",
                "head_preview",
                "args_preview",
            ]
        )
    rows: list[dict[str, Any]] = []
    for item in results:
        row = asdict(item)
        row["columns"] = json.dumps(row["columns"], ensure_ascii=False)
        row["dtypes"] = json.dumps(row["dtypes"], ensure_ascii=False)
        row["head_preview"] = json.dumps(row["head_preview"], ensure_ascii=False)
        row["args_preview"] = json.dumps(row["args_preview"], ensure_ascii=False)
        rows.append(row)
    return pd.DataFrame(rows)


def write_probe_artifacts(
    results: list[ProbeResult],
    *,
    out_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, str]:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)

    json_path = output / "probe_results_v3.json"
    csv_path = output / "probe_results_v3.csv"
    candidate_pass_path = output / "candidate_pass_has_data.txt"
    candidate_pass_or_empty_path = output / "candidate_pass_has_data_or_empty.txt"
    summary_path = output / "probe_summary_v3.json"

    result_dicts = [asdict(item) for item in results]
    json_path.write_text(json.dumps(result_dicts, ensure_ascii=False, indent=2), encoding="utf-8")
    results_to_frame(results).to_csv(csv_path, index=False)

    pass_has_data = sorted(
        [f"{item.source}.{item.function}" for item in results if item.status == STATUS_PASS_HAS_DATA]
    )
    pass_has_data_or_empty = sorted(
        [
            f"{item.source}.{item.function}"
            for item in results
            if item.status in {STATUS_PASS_HAS_DATA, STATUS_PASS_EMPTY}
        ]
    )
    candidate_pass_path.write_text("\n".join(pass_has_data) + "\n", encoding="utf-8")
    candidate_pass_or_empty_path.write_text(
        "\n".join(pass_has_data_or_empty) + "\n", encoding="utf-8"
    )

    summary = {
        "total": len(results),
        "status_counts": _status_counts(results),
        "source_counts": _source_counts(results),
        "pass_has_data": len(pass_has_data),
        "pass_has_data_or_empty": len(pass_has_data_or_empty),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "json": json_path.as_posix(),
        "csv": csv_path.as_posix(),
        "candidate_pass_has_data": candidate_pass_path.as_posix(),
        "candidate_pass_has_data_or_empty": candidate_pass_or_empty_path.as_posix(),
        "summary": summary_path.as_posix(),
    }


def _status_counts(results: list[ProbeResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in results:
        out[item.status] = out.get(item.status, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def _source_counts(results: list[ProbeResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in results:
        out[item.source] = out.get(item.source, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def _probe_wequant(function: str, ctx: _MongoContext) -> ProbeResult:
    if ctx.error:
        return _blocked_result(
            source="wequant",
            function=function,
            reason=f"mongo unavailable: {ctx.error}",
            args_preview={},
        )

    try:
        fn = resolve_wequant_callable(function)
    except Exception as exc:  # noqa: BLE001
        return _error_result("wequant", function, f"resolve failed: {exc}", args_preview={})

    call_spec = _build_wequant_call(function=function, fn=fn, ctx=ctx)
    if call_spec.blocked_reason:
        return _pass_empty_result(
            source="wequant",
            function=function,
            reason=f"no_data: {call_spec.blocked_reason}",
            args_preview={"args": _json_safe(call_spec.args), "kwargs": _json_safe(call_spec.kwargs)},
        )

    args_preview = {"args": _json_safe(call_spec.args), "kwargs": _json_safe(call_spec.kwargs)}

    try:
        result = _call_with_timeout(fn, call_spec.args, call_spec.kwargs, timeout_sec=PROBE_TIMEOUT_SEC)
        return _to_probe_result(
            source="wequant",
            function=function,
            result=result,
            args_preview=args_preview,
        )
    except Exception as exc:  # noqa: BLE001
        return _classify_exception(
            source="wequant",
            function=function,
            exc=exc,
            args_preview=args_preview,
        )


def _probe_wbdata(function: str, ctx: _MysqlContext) -> ProbeResult:
    if ctx.error:
        return _blocked_result(
            source="wbdata",
            function=function,
            reason=f"mysql unavailable: {ctx.error}",
            args_preview={},
        )

    try:
        fn = resolve_wbdata_callable(function)
    except Exception as exc:  # noqa: BLE001
        return _error_result("wbdata", function, f"resolve failed: {exc}", args_preview={})

    call_spec = _build_wbdata_call(function=function, fn=fn, ctx=ctx)
    if call_spec.blocked_reason:
        return _blocked_result(
            source="wbdata",
            function=function,
            reason=call_spec.blocked_reason,
            args_preview={"args": _json_safe(call_spec.args), "kwargs": _json_safe(call_spec.kwargs)},
        )

    args_preview = {"args": _json_safe(call_spec.args), "kwargs": _json_safe(call_spec.kwargs)}

    try:
        result = _call_with_timeout(fn, call_spec.args, call_spec.kwargs, timeout_sec=PROBE_TIMEOUT_SEC)
        return _to_probe_result(
            source="wbdata",
            function=function,
            result=result,
            args_preview=args_preview,
        )
    except Exception as exc:  # noqa: BLE001
        return _classify_exception(
            source="wbdata",
            function=function,
            exc=exc,
            args_preview=args_preview,
        )


def _build_wequant_call(function: str, fn: Any, ctx: _MongoContext) -> _CallSpec:
    db = ctx.db
    assert db is not None

    deps = _wequant_required_collections(function)
    missing = [name for name in deps if name not in ctx.collections]
    if missing:
        return _CallSpec(args=(), kwargs={}, blocked_reason=f"missing mongo collections: {', '.join(missing)}")

    if function == "fetch_future_tick":
        return _CallSpec(args=(), kwargs={})

    if function == "fetch_option_day_adv":
        return _CallSpec(args=(None,), kwargs={})

    if function == "fetch_trade_date":
        return _CallSpec(args=(), kwargs={})

    if function in {
        "fetch_stock_list",
        "fetch_stock_list_adv",
        "fetch_etf_list",
        "fetch_index_list",
        "fetch_future_list",
        "fetch_ctp_future_list",
        "fetch_stock_basic_info_tushare",
        "fetch_stock_terminated",
        "fetch_risk",
    }:
        return _CallSpec(args=(), kwargs={})

    if function == "fetch_get_hkstock_list":
        return _CallSpec(args=(), kwargs={})

    if function in {"fetch_stock_name", "fetch_index_name", "fetch_etf_name"}:
        coll_map = {
            "fetch_stock_name": "stock_list",
            "fetch_index_name": "index_list",
            "fetch_etf_name": "etf_list",
        }
        coll_name = coll_map[function]
        coll = db.get_collection(coll_name)
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason=f"no sample code in {coll_name}")
        return _CallSpec(args=(code,), kwargs={})

    if function in {"fetch_quotation", "fetch_quotations", "fetch_stock_realtime_adv"}:
        coll_name = _mongo_pick_realtime_collection(ctx.collections)
        if coll_name is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="missing realtime_<date> collection")
        coll = db.get_collection(coll_name)
        coll_date = _date_from_realtime_collection(coll_name)
        if coll_date is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason=f"cannot parse date from {coll_name}")
        if function == "fetch_quotations":
            return _CallSpec(args=(coll_date,), kwargs={"db": db})
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason=f"no sample code in {coll_name}")
        if function == "fetch_stock_realtime_adv":
            return _CallSpec(args=(code,), kwargs={"num": 1, "collections": coll})
        return _CallSpec(args=(code, coll_date), kwargs={"db": db})

    if function == "fetch_stock_realtime_min":
        coll_name = _mongo_pick_realtime_kline_collection(ctx.collections)
        if coll_name is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="missing realtime_kline_<date> collection")
        coll = db.get_collection(coll_name)
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason=f"no sample code in {coll_name}")
        freq = _mongo_sample_field(coll, "type") or "1min"
        return _CallSpec(args=(code,), kwargs={"frequence": str(freq), "collections": coll, "format": "pd"})

    if function == "fetch_stock_to_market_date":
        coll = db.get_collection("stock_info_tushare")
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample code in stock_info_tushare")
        return _CallSpec(args=(code,), kwargs={})

    if function in {"fetch_stock_full", "fetch_stock_day_full_adv"}:
        coll = db.get_collection("stock_day")
        start, _, with_time = _mongo_sample_range(coll)
        if start is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample date in stock_day")
        date_str = start.strftime("%Y-%m-%d")
        return _CallSpec(args=(date_str,), kwargs={})

    if function in {"fetch_stock_block", "fetch_stock_block_adv"}:
        coll = db.get_collection("stock_block")
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample code in stock_block")
        return _CallSpec(args=(code,), kwargs={})

    if function == "fetch_stock_block_history":
        coll = db.get_collection("stock_block_history")
        code = _mongo_sample_code(coll)
        date_val = _mongo_sample_field(coll, "updateDate")
        if code is None or date_val is None:
            return _CallSpec(
                args=(),
                kwargs={},
                blocked_reason="no sample code/updateDate in stock_block_history",
            )
        date_str = str(date_val)[0:10]
        return _CallSpec(args=(code, date_str, date_str), kwargs={})

    if function == "fetch_stock_block_slice_history":
        coll = db.get_collection("stock_block_slice_history")
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample code in stock_block_slice_history")
        return _CallSpec(args=(code,), kwargs={})

    if function == "fetch_stock_info":
        coll = db.get_collection("stock_info")
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample code in stock_info")
        return _CallSpec(args=(code,), kwargs={})

    if function == "fetch_stock_xdxr":
        coll = db.get_collection("stock_xdxr")
        code = _mongo_sample_code(coll)
        if code is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample code in stock_xdxr")
        return _CallSpec(args=(code,), kwargs={})

    if function in {"fetch_financial_report", "fetch_financial_report_adv"}:
        coll = db.get_collection("financial")
        code = _mongo_sample_code(coll)
        report_date = _mongo_sample_field(coll, "report_date")
        if code is None or report_date is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample code/report_date in financial")
        rd = str(report_date)
        if function == "fetch_financial_report_adv":
            return _CallSpec(args=(code, rd, rd), kwargs={})
        return _CallSpec(args=(code, rd), kwargs={})

    if function in {"fetch_stock_financial_calendar", "fetch_stock_financial_calendar_adv"}:
        coll = db.get_collection("report_calendar")
        code = _mongo_sample_code(coll)
        day = _mongo_sample_field(coll, "date")
        if code is None or day is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample code/date in report_calendar")
        day_str = str(day)[0:10]
        return _CallSpec(args=(code, day_str, day_str), kwargs={})

    if function in {"fetch_stock_divyield", "fetch_stock_divyield_adv"}:
        coll = db.get_collection("stock_divyield")
        code = _mongo_sample_field(coll, "a_stockcode")
        day = _mongo_sample_field(coll, "dir_dcl_date")
        if code is None or day is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample a_stockcode/dir_dcl_date in stock_divyield")
        day_str = str(day)[0:10]
        return _CallSpec(args=(str(code), day_str, day_str), kwargs={})

    if function == "fetch_lhb":
        coll = db.get_collection("lhb")
        day = _mongo_sample_field(coll, "date")
        if day is None:
            return _CallSpec(args=(), kwargs={}, blocked_reason="no sample date in lhb")
        return _CallSpec(args=(str(day),), kwargs={})

    # Generic market-data style builders.
    coll_name = _wequant_primary_collection(function)
    if coll_name is None:
        # last fallback by signature only
        return _build_signature_fallback(function, fn)

    coll = db.get_collection(coll_name)
    code = _mongo_sample_code(coll)
    if code is None:
        return _CallSpec(args=(), kwargs={}, blocked_reason=f"no sample code in {coll_name}")

    start_dt, end_dt, with_time = _mongo_sample_range(coll)
    if start_dt is None or end_dt is None:
        return _CallSpec(args=(), kwargs={}, blocked_reason=f"no sample date range in {coll_name}")

    if "transaction" in function or "ctp_tick" in function:
        with_time = True
    if "_min" in function and "day" not in function:
        with_time = True

    start, end = _format_window(start_dt, end_dt, with_time=with_time)

    sig = inspect.signature(fn)
    params = sig.parameters
    kwargs: dict[str, Any] = {}
    args: tuple[Any, ...]

    code_arg: Any = code
    if function == "fetch_hkstock_day":
        code_arg = [code]

    if function == "fetch_ctp_tick":
        freq = _mongo_sample_field(coll, "type") or "tick"
        args = (code_arg, start, end, str(freq))
        kwargs = {"format": "pd", "collections": coll}
        return _CallSpec(args=args, kwargs=kwargs)

    if "frequence" in params:
        if "transaction" in function:
            kwargs["frequence"] = str(_mongo_sample_field(coll, "type") or "tick")
        elif "_min" in function and "day" not in function:
            kwargs["frequence"] = str(_mongo_sample_field(coll, "type") or "1min")
        else:
            kwargs["frequence"] = str(_mongo_sample_field(coll, "type") or "day")

    if "format" in params:
        kwargs["format"] = "pd"
    if "collections" in params:
        kwargs["collections"] = coll

    if "start" in params and "end" in params:
        args = (code_arg, start, end)
    elif "start" in params and "end" not in params:
        args = (code_arg, start)
    else:
        args = (code_arg,)

    return _CallSpec(args=args, kwargs=kwargs)


def _build_wbdata_call(function: str, fn: Any, ctx: _MysqlContext) -> _CallSpec:
    deps = _wbdata_required_tables(function)
    missing = [tbl for tbl in deps if tbl not in ctx.tables]
    soft_missing_ok = {
        "fetch_bond_min",
        "fetch_cfets_repo_item",
        "fetch_clean_quote",
        "fetch_realtime_min",
    }
    if missing and function not in soft_missing_ok:
        return _CallSpec(args=(), kwargs={}, blocked_reason=f"missing mysql tables: {', '.join(missing)}")

    symbol = WB_BOND_DEFAULT_SYMBOL
    start = WB_BOND_DEFAULT_START
    end = WB_BOND_DEFAULT_END

    if function == "fetch_bond_date_list":
        return _CallSpec(args=(), kwargs={})

    if function == "fetch_bondInformation":
        return _CallSpec(args=(symbol,), kwargs={"query_date": None})

    if function in {"fetch_realtime_min", "fetch_realtime_bid", "fetch_realtime_transaction"}:
        return _CallSpec(args=(symbol,), kwargs={})

    if function in {
        "fetch_wind_indicators",
        "fetch_cfets_repo_item",
        "fetch_cfets_repo_buyback_item",
        "fetch_cfets_repo_buyout_item",
        "fetch_cfets_credit_item",
        "fetch_cfets_bond_amount",
        "fetch_cfets_credit_side",
        "fetch_cfets_repo_side",
    }:
        if function == "fetch_wind_indicators":
            return _CallSpec(args=("all", start, end), kwargs={})
        return _CallSpec(args=(start, end), kwargs={})

    # default: prefer fixed symbol/start/end rather than symbol='all'
    sig = inspect.signature(fn)
    params = sig.parameters

    kwargs: dict[str, Any] = {}
    args: list[Any] = []

    for name, param in params.items():
        if name == "engine":
            continue
        if name == "symbol":
            args.append(symbol)
            continue
        if name == "start":
            args.append(start)
            continue
        if name == "end":
            args.append(end)
            continue
        if name == "start_date":
            args.append(start)
            continue
        if name == "end_date":
            args.append(end)
            continue
        if name == "indicators":
            args.append("all")
            continue
        if name == "query_date":
            kwargs["query_date"] = None
            continue
        if name in {"with_new_age", "vaild_type", "columns", "convincing", "freq"}:
            # Keep function defaults for optional controls.
            continue
        if param.default is inspect._empty:
            return _CallSpec(
                args=tuple(args),
                kwargs=kwargs,
                blocked_reason=f"no fixed-param strategy for required `{name}` in {function}",
            )

    if not args and "engine" not in params:
        return _CallSpec(args=(), kwargs={})

    return _CallSpec(args=tuple(args), kwargs=kwargs)


def _build_signature_fallback(function: str, fn: Any) -> _CallSpec:
    sig = inspect.signature(fn)
    params = sig.parameters
    args: list[Any] = []
    kwargs: dict[str, Any] = {}

    for name, param in params.items():
        if name == "collections":
            continue
        if name == "format":
            kwargs[name] = "pd"
            continue
        if name in {"frequence", "freq"}:
            kwargs[name] = "day"
            continue
        if name in {"if_drop_index", "verbose"}:
            kwargs[name] = True
            continue
        if name == "num":
            kwargs[name] = 1
            continue
        if name in {"start", "start_date"}:
            args.append("2024-01-02")
            continue
        if name in {"end", "end_date"}:
            args.append("2024-01-05")
            continue
        if name in {"code", "symbol"}:
            args.append("000001")
            continue
        if name == "report_date":
            args.append("2024-01-02")
            continue
        if name == "date":
            args.append("2024-01-02")
            continue
        if name == "package":
            args.append(None)
            continue
        if name == "ltype":
            kwargs[name] = "EN"
            continue
        if name == "message":
            kwargs[name] = {}
            continue
        if name == "params":
            kwargs[name] = None
            continue

        if param.default is inspect._empty:
            return _CallSpec(args=(), kwargs={}, blocked_reason=f"no fallback for required parameter `{name}` in {function}")

    return _CallSpec(args=tuple(args), kwargs=kwargs)


def _load_mongo_context() -> _MongoContext:
    try:
        _ensure_probe_env_defaults()
        _ensure_repo_import_paths()
        from quant_eam.qa_fetch.providers.wequant_local.mongo import get_db

        db = get_db()
        names = set(db.list_collection_names())
        return _MongoContext(db=db, collections=names, error=None)
    except Exception as exc:  # noqa: BLE001
        return _MongoContext(db=None, collections=set(), error=str(exc))


def _load_mysql_context() -> _MysqlContext:
    try:
        _ensure_probe_env_defaults()
        _ensure_repo_import_paths()
        from sqlalchemy import text
        from quant_eam.qa_fetch.providers.wbdata_local.utils import DATABASE_TEST2

        with DATABASE_TEST2.connect() as conn:
            rows = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()")
            ).fetchall()
        tables = {str(row[0]) for row in rows}
        return _MysqlContext(engine=DATABASE_TEST2, tables=tables, error=None)
    except Exception as exc:  # noqa: BLE001
        return _MysqlContext(engine=None, tables=set(), error=str(exc))


def _ensure_repo_import_paths() -> None:
    root = Path(__file__).resolve().parents[3]
    candidates = [root, root / "src"]
    for item in candidates:
        if not item.exists():
            continue
        s = item.as_posix()
        if s not in sys.path:
            sys.path.insert(0, s)


def _ensure_probe_env_defaults() -> None:
    for key, value in WB_DEFAULT_ENV.items():
        os.environ.setdefault(key, value)
    for key, value in WEQUANT_DEFAULT_ENV.items():
        os.environ.setdefault(key, value)


def _wequant_primary_collection(function: str) -> str | None:
    explicit = {
        "fetch_stock_day": "stock_day",
        "fetch_stock_day_adv": "stock_day",
        "fetch_hkstock_day": "hkstock_day",
        "fetch_index_day": "index_day",
        "fetch_index_day_adv": "index_day",
        "fetch_future_day": "future_day",
        "fetch_future_day_adv": "future_day",
        "fetch_stock_min": "stock_min",
        "fetch_stock_min_adv": "stock_min",
        "fetch_index_min": "index_min",
        "fetch_index_min_adv": "index_min",
        "fetch_future_min": "future_min",
        "fetch_future_min_adv": "future_min",
        "fetch_stock_transaction": "stock_transaction",
        "fetch_stock_transaction_adv": "stock_transaction",
        "fetch_index_transaction": "index_transaction",
        "fetch_index_transaction_adv": "index_transaction",
        "fetch_ctp_tick": "ctp_tick",
        "fetch_dk_data": "dk_data",
        "fetch_stock_dk": "stock_dk",
        "fetch_stock_dk_adv": "stock_dk",
        "fetch_etf_dk": "etf_dk",
        "fetch_etf_dk_adv": "etf_dk",
        "fetch_index_dk": "index_dk",
        "fetch_index_dk_adv": "index_dk",
        "fetch_lof_dk": "lof_dk",
        "fetch_lof_dk_adv": "lof_dk",
        "fetch_reits_dk": "reits_dk",
        "fetch_reits_dk_adv": "reits_dk",
        "fetch_future_dk": "future_dk",
        "fetch_future_dk_adv": "future_dk",
        "fetch_hkstock_dk": "hkstock_dk",
        "fetch_hkstock_dk_adv": "hkstock_dk",
        "fetch_stock_adj": "stock_adj",
    }
    return explicit.get(function)


def _wequant_required_collections(function: str) -> list[str]:
    mapping = {
        "fetch_stock_list": ["stock_list"],
        "fetch_stock_list_adv": ["stock_list"],
        "fetch_etf_list": ["etf_list"],
        "fetch_index_list": ["index_list"],
        "fetch_future_list": ["future_list"],
        "fetch_ctp_future_list": ["ctp_future_list"],
        "fetch_stock_basic_info_tushare": ["stock_info_tushare"],
        "fetch_stock_terminated": ["stock_terminated"],
        "fetch_stock_name": ["stock_list"],
        "fetch_index_name": ["index_list"],
        "fetch_etf_name": ["etf_list"],
        "fetch_stock_to_market_date": ["stock_info_tushare"],
        "fetch_stock_full": ["stock_day"],
        "fetch_stock_day_full_adv": ["stock_day"],
        "fetch_stock_block": ["stock_block"],
        "fetch_stock_block_history": ["stock_block_history"],
        "fetch_stock_block_slice_history": ["stock_block_slice_history"],
        "fetch_stock_info": ["stock_info"],
        "fetch_stock_xdxr": ["stock_xdxr"],
        "fetch_financial_report": ["financial"],
        "fetch_financial_report_adv": ["financial"],
        "fetch_stock_financial_calendar": ["report_calendar"],
        "fetch_stock_financial_calendar_adv": ["report_calendar"],
        "fetch_stock_divyield": ["stock_divyield"],
        "fetch_stock_divyield_adv": ["stock_divyield"],
        "fetch_lhb": ["lhb"],
        "fetch_stock_realtime_min": [],
        "fetch_stock_realtime_adv": [],
        "fetch_quotation": [],
        "fetch_quotations": [],
        "fetch_get_hkstock_list": [],
        "fetch_trade_date": [],
        "fetch_risk": ["risk"],
        "fetch_future_tick": [],
        "fetch_option_day_adv": [],
    }
    primary = _wequant_primary_collection(function)
    if primary is not None:
        return [primary]
    if function in mapping:
        if function == "fetch_get_hkstock_list":
            return []
        return mapping[function]
    return []


def _wbdata_required_tables(function: str) -> list[str]:
    mapping = {
        "fetch_bond_date_list": ["wind_cbondcalendar"],
        "fetch_bond_day": ["clean_execreport_1d_v2"],
        "fetch_bond_industry_settlement": ["bond_industry_settlement"],
        "fetch_bondInformation": ["wind_bondinformation"],
        "fetch_bond_min": ["clean_execreport_1min"],
        "fetch_cfets_bond_amount": ["cfets_bond_amount"],
        "fetch_cfets_credit_item": ["cfets_credit_item"],
        "fetch_cfets_credit_side": ["cfets_credit_side"],
        "fetch_cfets_dfz_bond_day": ["clean_execreport_cfets_dfz_1d"],
        "fetch_cfets_repo_buyback_item": ["cfets_repo_buyback_item"],
        "fetch_cfets_repo_buyout_item": ["cfets_repo_buyout_item"],
        "fetch_cfets_repo_item": ["cfets_repo_item"],
        "fetch_cfets_repo_side": ["cfets_repo_side"],
        "fetch_clean_quote": ["clean_bond_quote"],
        "fetch_clean_transaction": ["clean_bondexecreport_v2"],
        "fetch_realtime_bid": ["realtime_bid"],
        "fetch_realtime_min": ["realtime_min1"],
        "fetch_realtime_transaction": ["realtime_trade"],
        "fetch_settlement_bond_day": ["clean_execreport_drquant_1d"],
        "fetch_wind_indicators": ["wind_indicators"],
        "fetch_yc_valuation": ["yc_valuation"],
        "fetch_zz_bond_valuation": [
            "zz_bond_valuation_ib",
            "zz_bond_valuation_bc",
            "zz_bond_valuation_sz",
            "zz_bond_valuation_bj",
            "zz_bond_valuation_sh",
        ],
        "fetch_zz_index": ["zz_index"],
        "fetch_zz_valuation": ["zz_valuation"],
    }
    return mapping.get(function, [])


def _mongo_sample_code(coll: Any) -> str | None:
    fields = ["code", "symbol", "a_stockcode", "InstrumentID", "base_code", "ts_code"]
    proj = {f: 1 for f in fields}
    doc = coll.find_one({}, proj)
    if not doc:
        return None
    for field in fields:
        value = doc.get(field)
        if value in (None, ""):
            continue
        s = str(value)
        if field in {"code", "a_stockcode", "base_code"} and s.isdigit() and len(s) < 6:
            s = s.zfill(6)
        return s
    return None


def _mongo_sample_field(coll: Any, field: str) -> Any:
    doc = coll.find_one({field: {"$exists": True}}, {field: 1})
    if not doc:
        return None
    return doc.get(field)


def _mongo_sample_range(coll: Any) -> tuple[pd.Timestamp | None, pd.Timestamp | None, bool]:
    candidates = [
        ("date_stamp", True),
        ("time_stamp", True),
        ("datetime", False),
        ("date", False),
        ("updateDate", False),
        ("dir_dcl_date", False),
        ("report_date", False),
        ("trade_date", False),
    ]
    for field, is_epoch in candidates:
        doc = coll.find_one({field: {"$exists": True}}, {field: 1})
        if not doc:
            continue
        first = coll.find_one({field: {"$exists": True}}, sort=[(field, 1)])
        last = coll.find_one({field: {"$exists": True}}, sort=[(field, -1)])
        if not first or not last:
            continue
        try:
            if is_epoch:
                start = pd.to_datetime(first[field], unit="s")
                end = pd.to_datetime(last[field], unit="s")
                return start, end, True
            start = pd.to_datetime(first[field])
            end = pd.to_datetime(last[field])
            with_time = ("min" in str(coll.name)) or ("transaction" in str(coll.name)) or (
                field in {"datetime", "time_stamp"}
            )
            return start, end, with_time
        except Exception:  # noqa: BLE001
            continue
    return None, None, False


def _format_window(
    start_dt: pd.Timestamp,
    end_dt: pd.Timestamp,
    *,
    with_time: bool,
) -> tuple[str, str]:
    if pd.isna(start_dt) or pd.isna(end_dt):
        return "2024-01-02", "2024-01-05"
    window = timedelta(hours=1) if with_time else timedelta(days=30)
    end_window = min(start_dt + window, end_dt)
    if with_time:
        return start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_window.strftime("%Y-%m-%d %H:%M:%S")
    return start_dt.strftime("%Y-%m-%d"), end_window.strftime("%Y-%m-%d")


def _mongo_pick_realtime_collection(collections: set[str]) -> str | None:
    cands = sorted([name for name in collections if name.startswith("realtime_") and not name.startswith("realtime_kline_")])
    if not cands:
        return None
    return cands[-1]


def _mongo_pick_realtime_kline_collection(collections: set[str]) -> str | None:
    cands = sorted([name for name in collections if name.startswith("realtime_kline_")])
    if not cands:
        return None
    return cands[-1]


def _date_from_realtime_collection(name: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})$", name)
    if not m:
        return None
    return m.group(1)


def _mysql_sample_window(ctx: _MysqlContext, table: str) -> tuple[str | None, str | None]:
    engine = ctx.engine
    if engine is None or not table:
        return None, None
    if table in _MYSQL_WINDOW_CACHE:
        return _MYSQL_WINDOW_CACHE[table]

    from sqlalchemy import text

    table_ident = _sql_table_ident(table)
    date_cols = ["trade_date", "date", "datetime", "transact_time", "update_time", "create_time"]

    with engine.connect() as conn:
        for col in date_cols:
            try:
                row = conn.execute(
                    text(f"SELECT MIN({col}) AS min_v, MAX({col}) AS max_v FROM {table_ident}")
                ).mappings().first()
            except Exception:  # noqa: BLE001
                continue
            if not row:
                continue
            min_v = row.get("min_v")
            max_v = row.get("max_v")
            if min_v is None or max_v is None:
                continue
            start = pd.to_datetime(min_v)
            end = pd.to_datetime(max_v)
            if pd.isna(start) or pd.isna(end):
                continue
            end_window = min(start + timedelta(days=7), end)
            value = (start.strftime("%Y-%m-%d"), end_window.strftime("%Y-%m-%d"))
            _MYSQL_WINDOW_CACHE[table] = value
            return value
    _MYSQL_WINDOW_CACHE[table] = (None, None)
    return _MYSQL_WINDOW_CACHE[table]


def _mysql_sample_symbol(ctx: _MysqlContext, table: str) -> str | None:
    engine = ctx.engine
    if engine is None or not table:
        return None
    if table in _MYSQL_SYMBOL_CACHE:
        return _MYSQL_SYMBOL_CACHE[table]

    from sqlalchemy import text

    table_ident = _sql_table_ident(table)
    symbol_cols = ["symbol", "code", "bond_code", "a_stockcode", "instrumentid", "InstrumentID"]
    with engine.connect() as conn:
        for col in symbol_cols:
            try:
                row = conn.execute(
                    text(
                        f"SELECT {col} AS v FROM {table_ident} "
                        f"WHERE {col} IS NOT NULL AND {col} <> '' LIMIT 1"
                    )
                ).mappings().first()
            except Exception:  # noqa: BLE001
                continue
            if not row:
                continue
            value = row.get("v")
            if value in (None, ""):
                continue
            result = str(value)
            _MYSQL_SYMBOL_CACHE[table] = result
            return result

    _MYSQL_SYMBOL_CACHE[table] = None
    return None


def _sql_table_ident(name: str) -> str:
    parts = [part for part in name.split(".") if part]
    return ".".join(f"`{part}`" for part in parts)


def _to_probe_result(
    *,
    source: str,
    function: str,
    result: Any,
    args_preview: dict[str, Any],
) -> ProbeResult:
    payload, payload_type = _normalize_payload(result)

    length = _payload_len(payload)
    columns: list[str] = []
    dtypes: dict[str, str] = {}
    head_preview: Any = None

    if isinstance(payload, pd.DataFrame):
        columns = [str(col) for col in payload.columns]
        dtypes = {str(col): str(dtype) for col, dtype in payload.dtypes.items()}
        if length > 0:
            head_preview = _json_safe(payload.head(5).to_dict(orient="records"))
        else:
            head_preview = []
    elif isinstance(payload, list):
        head_preview = _json_safe(payload[:5])
    elif isinstance(payload, dict):
        head_preview = _json_safe(payload)
    else:
        head_preview = _json_safe(payload)

    status = STATUS_PASS_HAS_DATA if length > 0 else STATUS_PASS_EMPTY
    reason = "ok"

    return ProbeResult(
        source=source,
        function=function,
        status=status,
        reason=reason,
        type=payload_type,
        len=length,
        columns=columns,
        dtypes=dtypes,
        head_preview=head_preview,
        args_preview=args_preview,
    )


def _normalize_payload(result: Any) -> tuple[Any, str]:
    if isinstance(result, pd.DataFrame):
        return result, "DataFrame"
    if result is None:
        return None, "NoneType"

    data_attr = getattr(result, "data", None)
    if isinstance(data_attr, pd.DataFrame):
        return data_attr, type(result).__name__

    if isinstance(result, (list, dict, tuple, str, int, float, bool)):
        return result, type(result).__name__

    if hasattr(result, "to_dict"):
        try:
            return result.to_dict(), type(result).__name__
        except Exception:  # noqa: BLE001
            pass

    return result, type(result).__name__


def _payload_len(payload: Any) -> int:
    if payload is None:
        return 0
    if isinstance(payload, pd.DataFrame):
        return int(len(payload))
    if isinstance(payload, (list, tuple, dict, str)):
        return int(len(payload))
    return 1


def _classify_exception(
    *,
    source: str,
    function: str,
    exc: Exception,
    args_preview: dict[str, Any],
) -> ProbeResult:
    if isinstance(exc, TimeoutError):
        msg = f"timeout_skip_{PROBE_TIMEOUT_SEC}s: {exc}"
        return _error_result(source=source, function=function, reason=msg, args_preview=args_preview)

    msg = f"{type(exc).__name__}: {exc}"
    lower = str(exc).lower()
    timeout_markers = [
        "function call exceeded",
        "statement timeout",
        "query timeout",
        "timed out",
    ]
    if any(marker in lower for marker in timeout_markers):
        msg = f"timeout_skip_{PROBE_TIMEOUT_SEC}s: {msg}"
        return _error_result(source=source, function=function, reason=msg, args_preview=args_preview)

    blocked_keywords = [
        "unknown table",
        "doesn't exist",
        "does not exist",
        "no such table",
        "collection",
        "serverselectiontimeouterror",
        "connection refused",
        "can't connect to mysql",
        "no module named",
    ]
    if any(key in lower for key in blocked_keywords):
        return _blocked_result(source=source, function=function, reason=msg, args_preview=args_preview)
    return _error_result(source=source, function=function, reason=msg, args_preview=args_preview)


def _blocked_result(
    *,
    source: str,
    function: str,
    reason: str,
    args_preview: dict[str, Any],
) -> ProbeResult:
    return ProbeResult(
        source=source,
        function=function,
        status=STATUS_BLOCKED_SOURCE_MISSING,
        reason=reason,
        type="unknown",
        len=0,
        columns=[],
        dtypes={},
        head_preview=None,
        args_preview=args_preview,
    )


def _pass_empty_result(
    *,
    source: str,
    function: str,
    reason: str,
    args_preview: dict[str, Any],
) -> ProbeResult:
    return ProbeResult(
        source=source,
        function=function,
        status=STATUS_PASS_EMPTY,
        reason=reason,
        type="unknown",
        len=0,
        columns=[],
        dtypes={},
        head_preview=[],
        args_preview=args_preview,
    )


def _error_result(
    source: str,
    function: str,
    reason: str,
    args_preview: dict[str, Any],
) -> ProbeResult:
    return ProbeResult(
        source=source,
        function=function,
        status=STATUS_ERROR_RUNTIME,
        reason=reason,
        type="unknown",
        len=0,
        columns=[],
        dtypes={},
        head_preview=None,
        args_preview=args_preview,
    )


def _json_safe(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_json_safe(item) for item in obj]
    if isinstance(obj, tuple):
        return [_json_safe(item) for item in obj]
    if isinstance(obj, dict):
        return {str(key): _json_safe(value) for key, value in obj.items()}
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if hasattr(obj, "name") and hasattr(obj, "find"):
        # pymongo collection-like object
        name = getattr(obj, "name", "unknown")
        return f"<collection:{name}>"
    return str(obj)


def _call_with_timeout(
    fn: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    timeout_sec: int,
) -> Any:
    if timeout_sec <= 0:
        return fn(*args, **kwargs)
    if not hasattr(signal, "SIGALRM"):
        return fn(*args, **kwargs)

    def _handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"function call exceeded {timeout_sec} seconds")

    prev_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_sec)
    try:
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
