from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import dk_ingest  # noqa: E402


Category = Literal["china", "star", "global"]


@dataclass
class RunRow:
    month: str
    category: str
    file_path: str
    file_name: str
    trade_date: Optional[str]
    status: Literal["success", "failed", "missing"]
    rows_parsed: int = 0
    rows_upserted: int = 0
    duration_sec: float = 0.0
    sheet_names: List[str] | None = None
    error_type: str | None = None
    error_message: str | None = None


def _pick_one(paths_sorted: Sequence[Path], strategy: str) -> Path:
    if not paths_sorted:
        raise ValueError("empty paths")
    if strategy == "first":
        return paths_sorted[0]
    if strategy == "last":
        return paths_sorted[-1]
    if strategy == "middle":
        return paths_sorted[len(paths_sorted) // 2]
    raise ValueError(f"unknown pick strategy: {strategy}")


def _scan_by_month(root: Path, categories: Sequence[Category]) -> Dict[str, Dict[Category, List[Path]]]:
    grouped: Dict[str, Dict[Category, List[Path]]] = defaultdict(lambda: defaultdict(list))
    for p in root.glob("*.xlsx"):
        cat = dk_ingest.detect_category(p.name)
        if cat is None or cat not in categories:
            continue
        td = dk_ingest.extract_trade_date(p.name)
        if not td or len(td) < 6:
            continue
        month = td[:6]
        grouped[month][cat].append(p)

    for m in grouped:
        for c in grouped[m]:
            grouped[m][c].sort(key=lambda x: (dk_ingest.extract_trade_date(x.name) or "", x.name))
    return grouped


def _render_md(
    out_path: Path,
    *,
    root: Path,
    dry_run: bool,
    pick: str,
    mongo_info: str,
    rows: List[RunRow],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ok = sum(1 for r in rows if r.status == "success")
    failed = sum(1 for r in rows if r.status == "failed")
    missing = sum(1 for r in rows if r.status == "missing")

    lines: List[str] = []
    lines.append("# DK Monthly Sample Run")
    lines.append("")
    lines.append(f"- generated_at: {now}")
    lines.append(f"- root: {root}")
    lines.append(f"- pick: {pick}")
    lines.append(f"- dry_run: {dry_run}")
    lines.append(f"- mongo: {mongo_info}")
    lines.append(f"- total: {len(rows)}, success: {ok}, failed: {failed}, missing: {missing}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| month | category | file_name | trade_date | status | rows_parsed | rows_upserted | duration_sec | error_type |")
    lines.append("|---:|---|---|---:|---|---:|---:|---:|---|")
    for r in rows:
        lines.append(
            f"| {r.month} | {r.category} | {r.file_name} | {r.trade_date or ''} | {r.status} | {r.rows_parsed} | {r.rows_upserted} | {r.duration_sec:.2f} | {r.error_type or ''} |"
        )

    failures = [r for r in rows if r.status == "failed"]
    if failures:
        lines.append("")
        lines.append("## Failures (details)")
        lines.append("")

        def next_step(error_type: Optional[str]) -> str:
            if error_type == "SheetNotFoundError":
                return "需要新增/调整 sheet 匹配关键词（或排除关键词），并确认目标 sheet 是否改名。"
            if error_type == "KeyError":
                return "可能是表头行偏移/列名变化（例如缺少 'NO.'），需要人工确认并调整解析逻辑。"
            if error_type == "ValueError":
                return "可能是列数/数据布局变化（例如 global sheet 列不足），需要人工确认并调整列映射。"
            return "请根据 error_message 与 sheet_names 人工排查：可能是 sheet 改名、header 偏移、或列名变化。"

        for r in failures:
            lines.append(f"- month: `{r.month}`, category: `{r.category}`, file_name: `{r.file_name}`")
            lines.append(f"  - file_path: `{r.file_path}`")
            lines.append(f"  - trade_date: `{r.trade_date}`")
            lines.append(f"  - error_type: `{r.error_type}`")
            lines.append(f"  - error_message: `{dk_ingest._truncate(r.error_message, 300)}`")
            lines.append(f"  - sheet_names: `{r.sheet_names}`")
            lines.append(f"  - next_step: {next_step(r.error_type)}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Monthly sample-run 1 file per category per month and write a report.")
    parser.add_argument("--root", default=r"D:\zxxq_xlsx", help=r"Excel root dir (default: D:\zxxq_xlsx)")
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not upsert to MongoDB")
    parser.add_argument("--pick", choices=["first", "middle", "last"], default="last", help="Pick strategy per month/category")
    parser.add_argument("--out", default="", help="Output markdown path (default: wequant/test/dk_monthly_sample_run_*.md)")
    parser.add_argument("--log-level", choices=["INFO", "ERROR"], default="INFO")

    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logger = logging.getLogger("dk_monthly_sample_runner")

    root = Path(args.root)
    cats: List[Category] = ["china", "star", "global"]
    grouped = _scan_by_month(root, cats)
    months = sorted(grouped.keys())
    logger.info("found months=%d under %s", len(months), str(root))

    out = Path(args.out) if args.out else (ROOT_DIR / "wequant" / "test" / f"dk_monthly_sample_run_{datetime.now().strftime('%Y%m%d_%H%M')}.md")

    # mongo + ref data
    db = dk_ingest._connect_db()
    dk_ingest._ensure_indexes(db, logger)
    log_coll = db.get_collection("dk_ingest_log")

    from wequant.config import load_mongo_config  # type: ignore
    from wequant.wefetch import fetch_future_list, fetch_index_list  # type: ignore

    cfg = load_mongo_config()
    mongo_info = f"{cfg.uri} / {cfg.db_name}"

    index_info = fetch_index_list()
    future_list = fetch_future_list()
    stock_adj_cache: Dict[str, Dict[str, float]] = {}

    rows: List[RunRow] = []

    for month in months:
        for cat in cats:
            candidates = grouped.get(month, {}).get(cat, [])
            if not candidates:
                rows.append(
                    RunRow(
                        month=month,
                        category=cat,
                        file_path="",
                        file_name="(missing)",
                        trade_date=None,
                        status="missing",
                    )
                )
                continue

            p = _pick_one(candidates, args.pick)
            trade_date = dk_ingest.extract_trade_date(p.name)
            sheet_names = dk_ingest._load_excel_sheet_names(p)
            fp = dk_ingest._file_fingerprint(p)

            started_at = datetime.utcnow()
            t0 = time.time()

            try:
                if cat == "china":
                    df = dk_ingest.read_china_dk_file(p, index_info, future_list, stock_adj_cache=stock_adj_cache)
                elif cat == "star":
                    df = dk_ingest.read_strength_file(p)
                    coll_name = "dk_strength"
                    unique_keys = ["trade_date", "code", "type"]
                elif cat == "global":
                    df = dk_ingest.read_global_view_file(p)
                    coll_name = "hkstock_dk"
                    unique_keys = ["trade_date", "code"]
                else:
                    raise ValueError(f"unknown category: {cat}")

                rows_parsed = int(len(df))
                rows_upserted = 0
                if not args.dry_run:
                    if cat == "china":
                        type_to_coll = {
                            "stock": "stock_dk",
                            "etf": "etf_dk",
                            "index": "index_dk",
                            "lof": "lof_dk",
                            "reits": "reits_dk",
                            "future": "future_dk",
                        }
                        df0 = df.copy()
                        if "type" not in df0.columns:
                            df0["type"] = ""
                        df0["type"] = df0["type"].astype(str).str.strip().str.lower().fillna("")
                        df0["_target_coll"] = df0["type"].map(lambda t: type_to_coll.get(str(t), "stock_dk"))

                        for coll_name2, sub in df0.groupby("_target_coll", sort=False):
                            coll = db.get_collection(str(coll_name2))
                            _, n = dk_ingest.upsert_dataframe(
                                coll,
                                sub.drop(columns=["_target_coll"], errors="ignore"),
                                ["trade_date", "code"],
                                unset_fields=["adj", "L_value_adj", "R_value_adj", "source_sheet"],
                            )
                            rows_upserted += int(n)
                    else:
                        coll = db.get_collection(coll_name)
                        _, rows_upserted = dk_ingest.upsert_dataframe(coll, df, unique_keys)

                status: Literal["success", "failed", "missing"] = "success"
                err_type = None
                err_msg = None
            except Exception as e:
                status = "failed"
                rows_parsed = 0
                rows_upserted = 0
                err_type = e.__class__.__name__
                err_msg = repr(e)
                logger.error("failed: month=%s cat=%s file=%s err=%s", month, cat, p.name, dk_ingest._truncate(err_msg, 300))

            finished_at = datetime.utcnow()
            duration_sec = float(max(0.0, time.time() - t0))

            # always log to dk_ingest_log (even dry-run), but mark dry_run so it won't affect incremental skip
            dk_ingest._insert_ingest_log(
                log_coll,
                {
                    "file_path": str(p),
                    "file_name": p.name,
                    "category": cat,
                    "trade_date": trade_date,
                    **fp,
                    "status": status,
                    "mode": "monthly_sample",
                    "dry_run": bool(args.dry_run),
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_sec": duration_sec,
                    "sheet_names": sheet_names,
                    "rows_parsed": rows_parsed,
                    "rows_upserted": rows_upserted,
                    "error_type": err_type,
                    "error_message": dk_ingest._truncate(err_msg, 2000) if err_msg else None,
                },
                logger,
            )

            rows.append(
                RunRow(
                    month=month,
                    category=cat,
                    file_path=str(p),
                    file_name=p.name,
                    trade_date=trade_date,
                    status=status,
                    rows_parsed=rows_parsed,
                    rows_upserted=rows_upserted,
                    duration_sec=duration_sec,
                    sheet_names=sheet_names,
                    error_type=err_type,
                    error_message=err_msg,
                )
            )

    _render_md(out, root=root, dry_run=bool(args.dry_run), pick=args.pick, mongo_info=mongo_info, rows=rows)
    logger.info("report written: %s", str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
