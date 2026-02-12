from __future__ import annotations

import argparse
import os
import sys
from typing import List

import pandas as pd

from .config import load_mongo_config
from pymongo.errors import DuplicateKeyError
from .mongo import get_client, get_db, collection_has_data
from .wefetch import (
    fetch_stock_day,
    fetch_future_day,
    fetch_etf_day,
    fetch_stock_adj,
    fetch_stock_list,
    fetch_future_list,
    fetch_etf_list,
)
from .wesu import save_stock_day, save_future_day, save_etf_day, save_stock_adj


def _parse_codes(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def cmd_doctor(_args: argparse.Namespace) -> int:
    cfg = load_mongo_config()
    print(f"WEQUANT_MONGO_URI={cfg.uri}")
    print(f"WEQUANT_DB_NAME={cfg.db_name}")
    try:
        get_client().admin.command("ping")
        print("mongo_ping=ok")
    except Exception as exc:
        print(f"mongo_ping=failed error={exc}")
        return 2

    db = get_db()
    names = set(db.list_collection_names())
    required = ["stock_day", "future_day", "stock_adj", "stock_list", "future_list", "etf_list"]
    optional = ["etf_day"]
    for name in required + optional:
        exists = name in names
        has_data = collection_has_data(db[name]) if exists else False
        print(f"collection={name} exists={exists} has_data={has_data}")
    return 0


def _ensure_day_indexes(coll) -> bool:
    ok = True
    try:
        coll.create_index([("code", 1), ("date", 1)], unique=True)
    except DuplicateKeyError as exc:
        print(f"index_unique_failed collection={coll.name} error={exc}")
        ok = False
    coll.create_index([("code", 1), ("date_stamp", 1)])
    return ok


def cmd_init_indexes(_args: argparse.Namespace) -> int:
    db = get_db()
    ok = True
    ok = _ensure_day_indexes(db["stock_day"]) and ok
    ok = _ensure_day_indexes(db["future_day"]) and ok
    ok = _ensure_day_indexes(db["stock_adj"]) and ok
    if "etf_day" in db.list_collection_names():
        ok = _ensure_day_indexes(db["etf_day"]) and ok
    print("indexes=ok" if ok else "indexes=partial")
    return 0 if ok else 1


def cmd_smoke_fetch(args: argparse.Namespace) -> int:
    codes = _parse_codes(args.code)
    if not codes:
        print("smoke-fetch requires --code")
        return 2
    if args.type == "stock":
        df = fetch_stock_day(codes, args.start, args.end, format="pd")
    elif args.type == "future":
        df = fetch_future_day(codes, args.start, args.end, format="pd")
    elif args.type == "etf":
        df = fetch_etf_day(codes, args.start, args.end, format="pd")
    else:
        print(f"unsupported type: {args.type}")
        return 2
    if df is None:
        print("result=None")
        return 1
    print(f"rows={len(df)}")
    print(df.head(5))
    return 0


def _load_or_sample_df(args: argparse.Namespace) -> pd.DataFrame:
    if args.csv:
        return pd.read_csv(args.csv)
    raise ValueError("smoke-save requires --csv (no synthetic data is generated)")


def cmd_smoke_save(args: argparse.Namespace) -> int:
    try:
        df = _load_or_sample_df(args)
    except Exception as exc:
        print(f"smoke-save error: {exc}")
        return 2

    if args.type == "stock":
        n = save_stock_day(df, upsert=True)
    elif args.type == "future":
        n = save_future_day(df, upsert=True)
    elif args.type == "etf":
        n = save_etf_day(df, upsert=True)
    elif args.type == "adj":
        n = save_stock_adj(df, upsert=True)
    else:
        print(f"unsupported type: {args.type}")
        return 2
    print(f"written_ops={n}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wequant")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doctor = sub.add_parser("doctor", help="print env and mongo connectivity")
    p_doctor.set_defaults(func=cmd_doctor)

    p_idx = sub.add_parser("init-indexes", help="create required MongoDB indexes")
    p_idx.set_defaults(func=cmd_init_indexes)

    p_fetch = sub.add_parser("smoke-fetch", help="smoke test fetch")
    p_fetch.add_argument("--type", choices=["stock", "future", "etf"], required=True)
    p_fetch.add_argument("--code", required=True, help="comma-separated codes")
    p_fetch.add_argument("--start", required=True)
    p_fetch.add_argument("--end", required=True)
    p_fetch.set_defaults(func=cmd_smoke_fetch)

    p_save = sub.add_parser("smoke-save", help="smoke test save (optional)")
    p_save.add_argument("--type", choices=["stock", "future", "etf", "adj"], required=True)
    p_save.add_argument("--csv", help="path to csv with columns matching target collection")
    p_save.add_argument("--code")
    p_save.add_argument("--date")
    p_save.add_argument("--open", type=float, default=1.0)
    p_save.add_argument("--high", type=float, default=1.0)
    p_save.add_argument("--low", type=float, default=1.0)
    p_save.add_argument("--close", type=float, default=1.0)
    p_save.add_argument("--volume", type=float, default=100.0)
    p_save.add_argument("--amount", type=float, default=100.0)
    p_save.add_argument("--position", type=float, default=0.0)
    p_save.add_argument("--price", type=float, default=0.0)
    p_save.add_argument("--trade", type=float, default=0.0)
    p_save.add_argument("--adj", type=float, default=1.0)
    p_save.set_defaults(func=cmd_smoke_save)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
