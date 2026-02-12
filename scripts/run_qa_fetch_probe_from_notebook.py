#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import json
import signal
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

STATUS_PASS_HAS_DATA = "pass_has_data"
STATUS_PASS_EMPTY = "pass_empty"
STATUS_BLOCKED_SOURCE_MISSING = "blocked_source_missing"
STATUS_ERROR_RUNTIME = "error_runtime"
SOURCE_MONGO = "mongo_fetch"
SOURCE_MYSQL = "mysql_fetch"
_SOURCE_ALIASES = {
    SOURCE_MONGO: SOURCE_MONGO,
    SOURCE_MYSQL: SOURCE_MYSQL,
    "wequant": SOURCE_MONGO,
    "wbdata": SOURCE_MYSQL,
}


@dataclass
class NotebookCase:
    cell_index: int
    function: str
    args: list[Any]
    kwargs: dict[str, Any]
    timeout_sec: int


@dataclass
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
    cell_index: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_source(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    if not token:
        return None
    return _SOURCE_ALIASES.get(token)


def is_mongo_source(value: Any) -> bool:
    return normalize_source(value) == SOURCE_MONGO


def is_mysql_source(value: Any) -> bool:
    return normalize_source(value) == SOURCE_MYSQL


def _ensure_import_paths() -> None:
    root = _repo_root()
    for path in (root, root / "src"):
        if path.exists():
            s = path.as_posix()
            if s not in sys.path:
                sys.path.insert(0, s)


def _parse_matrix_source_map(matrix_path: Path) -> dict[str, str]:
    lines = matrix_path.read_text(encoding="utf-8").splitlines()
    out: dict[str, str] = {}
    for line in lines:
        if not line.startswith("| "):
            continue
        if "source | old_name | proposed_name" in line:
            continue
        if line.startswith("|---"):
            continue
        parts = [item.strip() for item in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        source_token = parts[0]
        source = normalize_source(source_token)
        if source is None and source_token.strip().lower() == "fetch" and len(parts) >= 8:
            raw_notes = parts[7]
            if "/mongo_fetch/" in raw_notes:
                source = SOURCE_MONGO
            elif "/mysql_fetch/" in raw_notes:
                source = SOURCE_MYSQL
        fn = parts[1].strip("`")
        if source in {SOURCE_MONGO, SOURCE_MYSQL} and fn.startswith("fetch_"):
            out[fn] = source
    return out


def _load_window_profile(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
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
        if not fn.startswith("fetch_"):
            continue
        out[fn] = row
    return out


def _extract_notebook_cases(notebook_path: Path) -> list[NotebookCase]:
    payload = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = payload.get("cells", [])

    parsed: list[NotebookCase] = []
    for idx, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if "fetch_" not in source:
            continue
        try:
            tree = ast.parse(source)
        except Exception:
            continue

        enabled = True
        timeout_sec = 30
        fn_call: ast.Call | None = None

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "enabled":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                            enabled = node.value.value
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id != "_call_with_timeout":
                    continue
                for kw in node.keywords:
                    if kw.arg == "timeout_sec":
                        try:
                            timeout_sec = int(ast.literal_eval(kw.value))
                        except Exception:
                            timeout_sec = 30
                if node.args:
                    a0 = node.args[0]
                    if isinstance(a0, ast.Lambda) and isinstance(a0.body, ast.Call):
                        fn_call = a0.body
                    elif isinstance(a0, ast.Call):
                        fn_call = a0

        if not enabled or fn_call is None:
            continue
        fn_name = _call_name(fn_call.func)
        if fn_name is None or not fn_name.startswith("fetch_"):
            continue

        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        literal_ok = True

        for arg in fn_call.args:
            try:
                args.append(ast.literal_eval(arg))
            except Exception:
                literal_ok = False
                break
        if not literal_ok:
            continue
        for kw in fn_call.keywords:
            if kw.arg is None:
                literal_ok = False
                break
            try:
                kwargs[kw.arg] = ast.literal_eval(kw.value)
            except Exception:
                literal_ok = False
                break
        if not literal_ok:
            continue

        parsed.append(
            NotebookCase(
                cell_index=idx,
                function=fn_name,
                args=args,
                kwargs=kwargs,
                timeout_sec=timeout_sec,
            )
        )

    # Deduplicate by function, keep the latest cell as the current standard.
    dedup: dict[str, NotebookCase] = {}
    for item in parsed:
        dedup[item.function] = item
    return sorted(dedup.values(), key=lambda x: x.cell_index)


def _build_effective_cases(
    *,
    matrix_source_map: dict[str, str],
    notebook_cases: list[NotebookCase],
    window_profile: dict[str, dict[str, Any]],
) -> list[NotebookCase]:
    notebook_map = {c.function: c for c in notebook_cases}
    ordered_functions = list(matrix_source_map.keys())
    for fn in notebook_map:
        if fn not in matrix_source_map:
            ordered_functions.append(fn)

    out: list[NotebookCase] = []
    for fn in ordered_functions:
        base = notebook_map.get(fn)
        if base is None:
            base = NotebookCase(
                cell_index=-1,
                function=fn,
                args=[],
                kwargs={},
                timeout_sec=0,
            )
        prof = window_profile.get(fn, {})

        args = list(base.args)
        kwargs = dict(base.kwargs)
        smoke_args = prof.get("smoke_args")
        if not args and isinstance(smoke_args, list):
            args = smoke_args

        smoke_kwargs = prof.get("smoke_kwargs")
        if isinstance(smoke_kwargs, dict):
            for k, v in smoke_kwargs.items():
                kwargs.setdefault(str(k), v)

        timeout_sec = int(base.timeout_sec or 0)
        if timeout_sec <= 0:
            raw = prof.get("smoke_timeout_sec")
            try:
                timeout_sec = int(raw) if raw is not None else 30
            except Exception:
                timeout_sec = 30
        if timeout_sec <= 0:
            timeout_sec = 30

        out.append(
            NotebookCase(
                cell_index=base.cell_index,
                function=fn,
                args=args,
                kwargs=kwargs,
                timeout_sec=timeout_sec,
            )
        )

    return out


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_with_timeout(fn: Any, args: list[Any], kwargs: dict[str, Any], timeout_sec: int) -> Any:
    if timeout_sec <= 0 or not hasattr(signal, "SIGALRM"):
        return fn(*args, **kwargs)

    def _handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"timeout_skip_{timeout_sec}s")

    prev = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_sec)
    try:
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev)


def _normalize_result(result: Any) -> tuple[Any, str, int, list[str], dict[str, str], Any]:
    try:
        import pandas as pd
    except Exception:
        pd = None

    payload = result
    typ = type(result).__name__
    if pd is not None and isinstance(result, pd.DataFrame):
        payload = result
    else:
        data_attr = getattr(result, "data", None)
        if pd is not None and isinstance(data_attr, pd.DataFrame):
            payload = data_attr
            typ = type(result).__name__

    if payload is None:
        return payload, typ, 0, [], {}, None

    if pd is not None and isinstance(payload, pd.DataFrame):
        length = int(len(payload))
        columns = [str(c) for c in payload.columns]
        dtypes = {str(k): str(v) for k, v in payload.dtypes.items()}
        head = payload.head(5).to_dict(orient="records") if length > 0 else []
        return payload, "DataFrame", length, columns, dtypes, head

    try:
        length = int(len(payload))
    except Exception:
        length = 1
    return payload, typ, length, [], {}, _json_safe(payload)


def _classify_exception(source: str, exc: Exception) -> tuple[str, str]:
    msg = f"{type(exc).__name__}: {exc}"
    lower = msg.lower()
    if isinstance(exc, TimeoutError):
        return STATUS_ERROR_RUNTIME, msg

    wb_missing_markers = [
        "unknown table",
        "doesn't exist",
        "does not exist",
        "no such table",
        "can't connect to mysql",
        "connection refused",
    ]
    if is_mysql_source(source) and any(marker in lower for marker in wb_missing_markers):
        return STATUS_BLOCKED_SOURCE_MISSING, msg

    # User rule: mongo no-data should pass for now.
    wq_no_data_markers = [
        "none",
        "collection",
        "indexerror",
        "keyerror",
        "not found",
        "empty",
        "no data",
    ]
    if is_mongo_source(source) and any(marker in lower for marker in wq_no_data_markers):
        return STATUS_PASS_EMPTY, f"no_data: {msg}"

    return STATUS_ERROR_RUNTIME, msg


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


def _status_counts(results: list[ProbeResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in results:
        out[item.status] = out.get(item.status, 0) + 1
    return dict(sorted(out.items()))


def _source_counts(results: list[ProbeResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in results:
        out[item.source] = out.get(item.source, 0) + 1
    return dict(sorted(out.items()))


def _write_outputs(out_dir: Path, results: list[ProbeResult]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "probe_results_v3_notebook_params.json"
    csv_path = out_dir / "probe_results_v3_notebook_params.csv"
    summary_path = out_dir / "probe_summary_v3_notebook_params.json"
    pass_data_path = out_dir / "candidate_pass_has_data_notebook_params.txt"
    pass_all_path = out_dir / "candidate_pass_has_data_or_empty_notebook_params.txt"

    payload = [_json_safe(asdict(item)) for item in results]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "cell_index",
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
            ],
        )
        writer.writeheader()
        for row in payload:
            row = dict(row)
            row["columns"] = json.dumps(row.get("columns", []), ensure_ascii=False)
            row["dtypes"] = json.dumps(row.get("dtypes", {}), ensure_ascii=False)
            row["head_preview"] = json.dumps(row.get("head_preview"), ensure_ascii=False)
            row["args_preview"] = json.dumps(row.get("args_preview", {}), ensure_ascii=False)
            writer.writerow(row)

    pass_has_data = sorted(
        f"{item.source}.{item.function}" for item in results if item.status == STATUS_PASS_HAS_DATA
    )
    pass_has_data_or_empty = sorted(
        f"{item.source}.{item.function}"
        for item in results
        if item.status in {STATUS_PASS_HAS_DATA, STATUS_PASS_EMPTY}
    )
    pass_data_path.write_text("\n".join(pass_has_data) + "\n", encoding="utf-8")
    pass_all_path.write_text("\n".join(pass_has_data_or_empty) + "\n", encoding="utf-8")

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
        "summary": summary_path.as_posix(),
        "candidate_pass_has_data": pass_data_path.as_posix(),
        "candidate_pass_has_data_or_empty": pass_all_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe qa_fetch functions using params defined in manual notebook cells."
    )
    parser.add_argument(
        "--notebook",
        default="notebooks/qa_fetch_manual_params_v3.ipynb",
        help="Path to manual params notebook",
    )
    parser.add_argument(
        "--matrix",
        default="docs/05_data_plane/qa_fetch_function_baseline_v1.md",
        help="Path to fetch function baseline for source mapping",
    )
    parser.add_argument(
        "--out-dir",
        default="docs/05_data_plane/qa_fetch_probe_v3",
        help="Output directory",
    )
    parser.add_argument(
        "--window-profile",
        default="docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
        help="Optional smoke window profile JSON used to fill missing notebook args/kwargs",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit for debug runs (0 means full)",
    )
    args = parser.parse_args()

    _ensure_import_paths()
    from quant_eam.qa_fetch.mongo_bridge import resolve_mongo_fetch_callable
    from quant_eam.qa_fetch.mysql_bridge import resolve_mysql_fetch_callable

    notebook_path = Path(args.notebook)
    matrix_path = Path(args.matrix)
    out_dir = Path(args.out_dir)
    window_profile_path = Path(args.window_profile) if str(args.window_profile).strip() else None

    source_map = _parse_matrix_source_map(matrix_path)
    notebook_cases = _extract_notebook_cases(notebook_path)
    profile = _load_window_profile(window_profile_path)
    cases = _build_effective_cases(
        matrix_source_map=source_map,
        notebook_cases=notebook_cases,
        window_profile=profile,
    )
    if args.limit > 0:
        cases = cases[: args.limit]

    print(f"notebook={notebook_path}")
    print(f"matrix={matrix_path}")
    print(f"window_profile={window_profile_path if window_profile_path else ''}")
    print(f"cases={len(cases)}")

    results: list[ProbeResult] = []
    for idx, case in enumerate(cases, start=1):
        source = source_map.get(case.function)
        if source is None:
            # Best-effort fallback: try mongo provider first, then mysql.
            source = SOURCE_MONGO
        args_preview = {"args": _json_safe(case.args), "kwargs": _json_safe(case.kwargs)}

        try:
            if is_mongo_source(source):
                fn = resolve_mongo_fetch_callable(case.function)
            else:
                fn = resolve_mysql_fetch_callable(case.function)
        except Exception:
            if is_mongo_source(source):
                source = SOURCE_MYSQL
                try:
                    fn = resolve_mysql_fetch_callable(case.function)
                except Exception as exc:
                    msg = f"resolve failed: {type(exc).__name__}: {exc}"
                    results.append(
                        ProbeResult(
                            source=source,
                            function=case.function,
                            status=STATUS_ERROR_RUNTIME,
                            reason=msg,
                            type="unknown",
                            len=0,
                            columns=[],
                            dtypes={},
                            head_preview=None,
                            args_preview=args_preview,
                            cell_index=case.cell_index,
                        )
                    )
                    print(f"[{idx}/{len(cases)}] {source}.{case.function} -> {STATUS_ERROR_RUNTIME}")
                    continue
            else:
                source = SOURCE_MONGO
                try:
                    fn = resolve_mongo_fetch_callable(case.function)
                except Exception as exc:
                    msg = f"resolve failed: {type(exc).__name__}: {exc}"
                    results.append(
                        ProbeResult(
                            source=source,
                            function=case.function,
                            status=STATUS_ERROR_RUNTIME,
                            reason=msg,
                            type="unknown",
                            len=0,
                            columns=[],
                            dtypes={},
                            head_preview=None,
                            args_preview=args_preview,
                            cell_index=case.cell_index,
                        )
                    )
                    print(f"[{idx}/{len(cases)}] {source}.{case.function} -> {STATUS_ERROR_RUNTIME}")
                    continue

        try:
            out = _call_with_timeout(fn, case.args, case.kwargs, case.timeout_sec)
            _payload, typ, length, columns, dtypes, head = _normalize_result(out)
            status = STATUS_PASS_HAS_DATA if length > 0 else STATUS_PASS_EMPTY
            reason = "ok" if length > 0 else "no_data"
            item = ProbeResult(
                source=source,
                function=case.function,
                status=status,
                reason=reason,
                type=typ,
                len=length,
                columns=columns,
                dtypes=dtypes,
                head_preview=head,
                args_preview=args_preview,
                cell_index=case.cell_index,
            )
        except Exception as exc:
            status, reason = _classify_exception(source, exc)
            item = ProbeResult(
                source=source,
                function=case.function,
                status=status,
                reason=reason,
                type="unknown",
                len=0,
                columns=[],
                dtypes={},
                head_preview=None if status != STATUS_PASS_EMPTY else [],
                args_preview=args_preview,
                cell_index=case.cell_index,
            )

        results.append(item)
        print(f"[{idx}/{len(cases)}] {source}.{case.function} -> {item.status} len={item.len}")

    paths = _write_outputs(out_dir, results)
    summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
    print("done")
    print("status_counts=", json.dumps(summary["status_counts"], ensure_ascii=False))
    print("source_counts=", json.dumps(summary["source_counts"], ensure_ascii=False))
    for k, v in paths.items():
        print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
