from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


Category = Literal["china", "star", "global"]

# This module is the engineering implementation for DK Excel ingestion.


class SheetNotFoundError(RuntimeError):
    pass


# ============================================================
# Notebook-migrated functions (from wequant/test/save_dk.ipynb)
# ============================================================

# =========================
# 1) Normalize helpers
# =========================
def _normalize_code_base(x) -> str:
    """
    规范成底层 code_base：
    - 含英文字母：原样（期货等）
    - 纯数字：
        * '1'/'1.0' -> '000001'
        * '000001' -> '000001'
        * 5位如 '00003'（港股常见）保持 5 位
        * 其它 <6 位补到 6 位
    """
    if x is None:
        return ""
    if isinstance(x, float) and np.isnan(x):
        return ""

    s = str(x).strip()
    s = re.sub(r"\.0$", "", s)

    if re.search(r"[A-Za-z]", s):
        return s

    if re.fullmatch(r"\d+", s):
        if len(s) == 5:
            return s
        if len(s) < 6:
            return s.zfill(6)
        return s

    return s


def tb_symbol_stock_etf(code_base: str) -> str:
    """
    A股/ETF 常规补后缀（不含 LOF/REITs）：
    - 60/68 + SH
    - 00/30/15 + SZ
    - 50/51/56/58 + SH
    """
    x = str(code_base)
    if not re.fullmatch(r"\d{6}", x):
        return x
    if x[:2] in ["60", "68", "50", "51", "56", "58"]:
        return x + ".SH"
    if x[:2] in ["00", "30", "15"]:
        return x + ".SZ"
    return x


# =========================
# 2) Enrich: code1/type
# =========================
def enrich_code1_and_type(
    total_dk_data: pd.DataFrame,
    index_info: pd.DataFrame,
    *,
    code_col: str = "code",
    rvalue_col: str = "R_value",
    datetime_col: str = "datetime",
    index_code_col: str = "code",
    index_preclose_col: str = "pre_close",
    index_sse_col: str = "sse",
    index_sec_col: str = "sec",
    # 仅用于冲突码（像 000001）判别指数
    rel_tol: float = 0.20,
    abs_tol: float = 200.0,
) -> pd.DataFrame:
    """
    输出新增两列：
      - code1: 加 .SH/.SZ（期货先保持原 code）
      - type : index / stock / etf / lof / reits / future / ''

    补充规则：
      - 16xxxxxx: LOF -> .SZ, type='lof'
      - 18xxxxxx: REITs -> .SH, type='reits'
      - 期货：含字母 -> type='future'（code1 先不改，后续用 patch_future_code1_to_main 统一映射主连）
    """
    # 防御：去掉重复列名
    df0 = total_dk_data.copy()
    df0 = df0.loc[:, ~df0.columns.duplicated()]
    orig_index = df0.index
    df = df0.reset_index(drop=True)

    # 防御：避免外部已有 _code_base
    df = df.drop(columns=["_code_base"], errors="ignore")
    df["_code_base"] = df[code_col].map(_normalize_code_base)

    # --- index_info 预处理（尽量只保留 index_cn） ---
    idx = index_info.copy()
    idx = idx.loc[:, ~idx.columns.duplicated()]
    if index_code_col not in idx.columns:
        idx = idx.reset_index().rename(columns={"index": index_code_col})
    idx = idx.drop(columns=["_code_base"], errors="ignore")
    idx["_code_base"] = idx[index_code_col].map(_normalize_code_base)

    if index_sec_col in idx.columns:
        idx = idx[idx[index_sec_col].astype(str).str.contains("index", case=False, na=False)].copy()

    keep_cols = ["_code_base"]
    if index_preclose_col in idx.columns:
        keep_cols.append(index_preclose_col)
    if index_sse_col in idx.columns:
        keep_cols.append(index_sse_col)
    idx = idx[keep_cols].drop_duplicates("_code_base", keep="first") if not idx.empty else idx

    # --- init ---
    df["code1"] = df["_code_base"].astype(str)
    df["type"] = ""

    base = df["_code_base"].astype(str)
    has_alpha = base.str.contains(r"[A-Za-z]", na=False)

    # future（先标类型，code1 暂不处理）
    df.loc[has_alpha, "type"] = "future"
    non_fut = ~has_alpha

    # LOF / REITs
    is_6d = base.str.fullmatch(r"\d{6}", na=False)
    lof_mask = non_fut & is_6d & base.str.startswith("16")
    reit_mask = non_fut & is_6d & base.str.startswith("18")

    df.loc[lof_mask, "type"] = "lof"
    df.loc[lof_mask, "code1"] = base.loc[lof_mask].values + ".SZ"

    df.loc[reit_mask, "type"] = "reits"
    df.loc[reit_mask, "code1"] = base.loc[reit_mask].values + ".SH"

    # --- merge index info ---
    if not idx.empty and (index_preclose_col in idx.columns):
        df2 = df.merge(idx, on="_code_base", how="left")
        in_index = non_fut & df2[index_preclose_col].notna()
    else:
        df2 = df.copy()
        in_index = pd.Series(False, index=df2.index)

    # 冲突前缀（容易与股票/ETF 重名）
    ambig_prefixes = ["60", "00", "30", "15", "68", "50", "51", "56", "58"]
    ambig = base.str[:2].isin(ambig_prefixes)

    grp_cols = [datetime_col, "_code_base"] if datetime_col in df2.columns else ["_code_base"]

    # 只允许覆盖空/stock/etf（不覆盖 lof/reits/future）
    eligible_for_index = df2["type"].isin(["", "stock", "etf"])

    if index_preclose_col in df2.columns:
        # 1) 重复组：冲突码挑最接近 pre_close 的一条为 index
        dup_mask = df2.duplicated(subset=grp_cols, keep=False)
        cand_mask = in_index & ambig & dup_mask & eligible_for_index
        cand_cols = list(dict.fromkeys(grp_cols + [rvalue_col, index_preclose_col]))
        cand = df2.loc[cand_mask, cand_cols].copy()
        cand = cand.loc[:, ~cand.columns.duplicated()]

        if not cand.empty:
            cand["r"] = pd.to_numeric(cand[rvalue_col], errors="coerce")
            cand["pre"] = pd.to_numeric(cand[index_preclose_col], errors="coerce")
            cand = cand.dropna(subset=["r", "pre"])
            if not cand.empty:
                cand["diff"] = (cand["r"] - cand["pre"]).abs()
                idx_min = cand.groupby(grp_cols, sort=False)["diff"].idxmin()
                df2.loc[idx_min.to_numpy(), "type"] = "index"

        # 2) 非冲突指数码：在 index_info 就直接认 index（399xxx 等）
        non_ambig_index = in_index & (~ambig) & df2["type"].ne("index") & df2["type"].isin(["", "stock", "etf"])
        df2.loc[non_ambig_index, "type"] = "index"

        # 3) 冲突码剩余：阈值判别
        remain_ambig = in_index & ambig & df2["type"].ne("index") & df2["type"].isin(["", "stock", "etf"])
        if remain_ambig.any():
            r = pd.to_numeric(df2.loc[remain_ambig, rvalue_col], errors="coerce")
            pre = pd.to_numeric(df2.loc[remain_ambig, index_preclose_col], errors="coerce")
            diff = (r - pre).abs()
            thr = np.maximum(abs_tol, rel_tol * pre.abs())
            close = pre.notna() & r.notna() & (diff <= thr)
            df2.loc[close[close].index, "type"] = "index"

        # 4) index 补后缀
        is_index_mask = df2["type"].eq("index")
        if is_index_mask.any():
            if index_sse_col in df2.columns:
                sse = df2.loc[is_index_mask, index_sse_col].fillna("sh").astype(str).str.lower()
            else:
                sse = pd.Series("sh", index=df2.loc[is_index_mask].index)
            suffix = np.where(sse.eq("sz"), ".SZ", ".SH")
            df2.loc[is_index_mask, "code1"] = df2.loc[is_index_mask, "_code_base"].astype(str).to_numpy() + suffix

    # 5) 其余走 stock/etf
    remain = df2["type"].eq("") & non_fut & is_6d
    remain_base = df2.loc[remain, "_code_base"].astype(str)
    if not remain_base.empty:
        df2.loc[remain_base.index, "code1"] = remain_base.map(tb_symbol_stock_etf).values
        p2 = remain_base.str[:2]
        stock_rows = p2[p2.isin(["60", "00", "30", "15", "68"])].index
        etf_rows = p2[p2.isin(["50", "51", "56", "58"])].index
        df2.loc[stock_rows, "type"] = "stock"
        df2.loc[etf_rows, "type"] = "etf"

    out = df2[df.columns].copy()
    out = out.drop(columns=["_code_base"], errors="ignore")
    out.index = orig_index
    return out


# =========================
# 3) FUTURE patch: map to 主连（且明确“不用带 '-' 的”）
# =========================
def build_future_main_map_no_dash(
    future_list: pd.DataFrame,
    *,
    name_col: str = "name",
    keyword: str = "主连",
) -> dict:
    """
    构建 base(字母前缀) -> 主连symbol，且：
      - 过滤掉所有带 '-' 的主连（如 'L-FL8', 'PP-FL8', 'V-FL8'）
      - 只保留不带 '-' 的主连（如 'LL8', 'PPL8', 'VL8'）

    base 的提取：
      - '*L8' -> base=symbol[:-2]  (NIL8->NI, TL8->T, TLL8->TL)
    """
    fl = future_list.copy()

    # 只取 name 含“主连”的
    if name_col in fl.columns:
        fl = fl[fl[name_col].astype(str).str.contains(keyword, na=False)].copy()

    symbols = fl.index.astype(str)

    # 过滤：不要带 '-' 的
    symbols = [s for s in symbols.tolist() if "-" not in s]

    mp = {}
    for sym in symbols:
        sym = str(sym)
        if not sym.endswith("L8"):
            continue
        base = sym[:-2].upper()
        # 若出现重复 base（罕见），保留更短的
        if base not in mp or len(sym) < len(mp[base]):
            mp[base] = sym
    return mp


def patch_future_code1_to_main_no_dash(
    df: pd.DataFrame,
    future_list: pd.DataFrame,
    *,
    code_col: str = "code",
    type_col: str = "type",
    code1_col: str = "code1",
    name_col: str = "name",
    keyword: str = "主连",
) -> pd.DataFrame:
    """
    把 df 中 type=='future' 的 code1 改成“不带 '-' 的主连”symbol：
      - code='NI'    -> code1='NIL8'
      - code='SC00'  -> code1='SCL8'（取字母前缀 SC）
      - code='ZS2007'-> code1='ZSL8'（若存在）
    """
    out = df.copy()
    mp = build_future_main_map_no_dash(future_list, name_col=name_col, keyword=keyword)

    fut_mask = out[type_col].eq("future")
    if not fut_mask.any():
        return out

    codes = out.loc[fut_mask, code_col].astype(str).str.strip()

    # 取字母前缀（不是前两位）：SC00->SC, ZS2007->ZS
    base = codes.str.extract(r"^([A-Za-z]+)", expand=False).fillna("").str.upper()

    mapped = base.map(mp)  # Series: str 或 NaN

    # 用 np.where 覆盖（最稳，不会触发 len mismatch）
    out.loc[fut_mask, code1_col] = np.where(
        mapped.notna(),
        mapped.astype(str).to_numpy(),
        out.loc[fut_mask, code1_col].astype(str).to_numpy(),
    )
    return out


def read_first_sheet_strength_table(xlsx_path: str) -> pd.DataFrame:
    """
    Read the 1st sheet (sheet_name=0) and convert it into ONE dataframe with ENGLISH columns:
      - code              (代码)
      - short_name        (简称)
      - total_market_cap  (总市值)
      - type              (类型): weak / strong
          weak   = 强转弱
          strong = 弱转强
      - trade_date        (从文件名提取 8 位日期，如 20241009)

    Notes:
    - The sheet layout is two blocks side-by-side:
        [京沪深强转弱] 代码 简称 总市值 | [京沪深弱转强] 代码 简称 总市值
      and real data starts from row 3 (0-based row index 2).
    """
    # -------- trade_date from file name --------
    fname = os.path.basename(xlsx_path)
    dates = re.findall(r"(\d{8})", fname)  # 抓所有 8 位数字
    trade_date = dates[-1] if dates else None  # 取最后一个最稳（通常就在文件尾部）

    raw = pd.read_excel(xlsx_path, sheet_name=0, header=None, engine="openpyxl")

    # Left block: 强转弱 -> weak
    left = raw.iloc[2:, 0:3].copy()
    left.columns = ["code", "short_name", "total_market_cap"]
    left["type"] = "weak"

    # Right block: 弱转强 -> strong
    right = raw.iloc[2:, 3:6].copy()
    right.columns = ["code", "short_name", "total_market_cap"]
    right["type"] = "strong"

    df = pd.concat([left, right], ignore_index=True)

    # --- clean ---
    df = df.dropna(subset=["code"])

    # keep code as string, keep leading zeros
    df["code"] = df["code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["code"] = df["code"].apply(lambda s: s.zfill(6) if s.isdigit() and len(s) < 6 else s)

    df["short_name"] = df["short_name"].astype(str).str.strip()

    # market cap might contain '--'
    df["total_market_cap"] = df["total_market_cap"].astype(str).str.strip().replace(
        {"--": pd.NA, "nan": pd.NA, "None": pd.NA}
    )

    # add trade_date
    df["trade_date"] = trade_date  # 字符串 'YYYYMMDD'；若没抓到就是 None

    return df[["trade_date", "code", "short_name", "total_market_cap", "type"]]


_FP_CACHE: Dict[str, Dict[str, Any]] = {}


def detect_category(file_name: str) -> Optional[Category]:
    name = str(file_name)
    # Excel temp/lock files (cannot read)
    if name.startswith("~$"):
        return None
    if not name.lower().endswith(".xlsx"):
        return None

    # NOTE: 有些文件名前面会带数字前缀 + '_'，所以这里用 contains 而不是 startswith
    if "【V】奇衡DK全球" in name:
        return "global"
    if "【V】奇衡DK" in name and "全球" not in name:
        return "china"

    # DK 强弱转换（star/strength）
    if "奇衡DK星球" in name and ("指数" in name or "数据" in name) and "【V】奇衡DK" not in name:
        return "star"

    return None


def extract_trade_date(file_name: str) -> Optional[str]:
    dates = re.findall(r"(\d{8})", str(file_name))
    return dates[-1] if dates else None


def list_target_files(root: str | Path, categories: Sequence[Category]) -> List[Path]:
    root_path = Path(root)
    out: List[Path] = []

    for p in root_path.rglob("*.xlsx"):
        cat = detect_category(p.name)
        if cat is None:
            continue
        if cat not in categories:
            continue
        out.append(p)

    def _sort_key(path: Path) -> Tuple[int, str]:
        td = extract_trade_date(path.name)
        if td is None:
            return (10**9, path.name)
        try:
            return (int(td), path.name)
        except Exception:
            return (10**9, path.name)

    out.sort(key=_sort_key)
    return out


def pick_sheet(
    sheet_names: Sequence[str],
    include_keywords: Sequence[str],
    prefer_keywords: Optional[Sequence[str]] = None,
    exclude_keywords: Optional[Sequence[str]] = None,
) -> str:
    names = [str(x) for x in sheet_names]
    exclude_keywords = list(exclude_keywords or [])
    include_keywords = list(include_keywords or [])
    prefer_keywords = list(prefer_keywords or [])

    def ok(n: str) -> bool:
        if exclude_keywords and any(k in n for k in exclude_keywords):
            return False
        return True

    # prefer first
    for pk in prefer_keywords:
        for n in names:
            if ok(n) and pk in n:
                return n

    # then include
    for n in names:
        if not ok(n):
            continue
        if any(k in n for k in include_keywords):
            return n

    raise SheetNotFoundError(
        f"Sheet not found. include_keywords={include_keywords}, prefer_keywords={prefer_keywords}, "
        f"exclude_keywords={exclude_keywords}, sheet_names={names}"
    )


def _zfill_numeric_str(s: Any, width: int) -> str:
    if s is None:
        return ""
    s2 = str(s).strip()
    s2 = re.sub(r"\.0$", "", s2)
    if s2.isdigit() and len(s2) < width:
        return s2.zfill(width)
    return s2


def _safe_datetime_yyyymmdd_to_iso(yyyymmdd: Optional[str]) -> Optional[str]:
    if not yyyymmdd or not re.fullmatch(r"\d{8}", str(yyyymmdd)):
        return None
    return str(pd.to_datetime(yyyymmdd))[:10]


def _load_excel_sheet_names(file_path: Path) -> List[str]:
    try:
        xls = pd.ExcelFile(file_path, engine="openpyxl")
        return list(map(str, xls.sheet_names))
    except Exception:
        return []


def _sha1_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_fingerprint(path: Path) -> Dict[str, Any]:
    k = str(path)
    if k in _FP_CACHE:
        return _FP_CACHE[k]
    st = path.stat()
    fp = {
        "file_size": int(st.st_size),
        "mtime": int(st.st_mtime),
        "content_hash": _sha1_file(path),
    }
    _FP_CACHE[k] = fp
    return fp


def _truncate(s: Any, n: int) -> str:
    t = str(s) if s is not None else ""
    return t if len(t) <= n else t[: n - 3] + "..."


def _to_jsonable(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (datetime,)):
        return x.isoformat()
    if isinstance(x, (pd.Timestamp,)):
        return x.to_pydatetime().isoformat()
    if isinstance(x, (np.generic,)):
        return x.item()
    if isinstance(x, (Path,)):
        return str(x)
    if isinstance(x, (dict,)):
        return {str(k): _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]
    return x


def _normalize_mongo_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if v is pd.NA:
        return None
    if isinstance(v, (np.generic,)):
        return v.item()
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, dict):
        return {k: _normalize_mongo_value(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_normalize_mongo_value(val) for val in v]
    return v


def _stable_row_hash(doc: Dict[str, Any]) -> str:
    s = json.dumps(_to_jsonable(doc), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def upsert_dataframe(
    collection,
    df: pd.DataFrame,
    unique_keys: Sequence[str],
    extra_meta: Optional[Dict[str, Any]] = None,
    *,
    batch_size: int = 1000,
    fallback_unique_keys: Optional[Sequence[str]] = None,
    fallback_missing_key: Optional[str] = None,
    unset_fields: Optional[Sequence[str]] = None,
) -> Tuple[int, int]:
    """
    幂等 upsert：严禁 insert_many；使用 bulk_write(UpdateOne, upsert=True)。
    Returns (rows_parsed, rows_upserted_attempted)
    """
    from pymongo import UpdateOne  # type: ignore

    if df is None or len(df) == 0:
        return (0, 0)

    extra_meta = dict(extra_meta or {})
    rows = df.to_dict(orient="records")

    rows_parsed = len(rows)
    rows_upserted = 0

    ops: List[Any] = []

    def flush() -> None:
        nonlocal ops, rows_upserted
        if not ops:
            return
        collection.bulk_write(ops, ordered=False)
        rows_upserted += len(ops)
        ops = []

    for rec in rows:
        doc = {k: _normalize_mongo_value(v) for k, v in rec.items()}
        doc.update(extra_meta)

        primary = {k: doc.get(k) for k in unique_keys if k in doc}
        if any(primary.get(k) in (None, "") for k in unique_keys):
            doc["_id"] = _stable_row_hash(doc)
            filt: Dict[str, Any] = {"_id": doc["_id"]}
        else:
            filt = primary
            if fallback_unique_keys:
                fallback = {k: doc.get(k) for k in fallback_unique_keys if k in doc}
                if not any(fallback.get(k) in (None, "") for k in fallback_unique_keys):
                    if fallback_missing_key:
                        fb = dict(fallback)
                        fb[fallback_missing_key] = {"$exists": False}
                        fallback = fb
                    filt = {"$or": [primary, fallback]}

        update: Dict[str, Any] = {"$set": doc}
        if unset_fields:
            update["$unset"] = {str(k): "" for k in unset_fields}
        ops.append(UpdateOne(filt, update, upsert=True))
        if len(ops) >= batch_size:
            flush()

    flush()
    return (rows_parsed, rows_upserted)


def _connect_db() -> Any:
    """
    MongoDB 连接优先使用 wequant.mongo.get_db；失败则用 env:
      - MONGO_URI
      - MONGO_DB_NAME (default: test)
    """
    try:
        from wequant.mongo import get_db  # type: ignore

        return get_db()
    except Exception as e1:
        uri = os.environ.get("MONGO_URI")
        db_name = os.environ.get("MONGO_DB_NAME", "test")
        if not uri:
            raise RuntimeError("MongoDB connection failed (no wequant.mongo.get_db and MONGO_URI not set)") from e1
        from pymongo import MongoClient  # type: ignore

        client = MongoClient(uri)
        return client[db_name]


def _ensure_indexes(db, logger: logging.Logger) -> None:
    """
    自动创建必要索引（best-effort；失败不阻断 ingestion）。
    """
    try:
        from pymongo import ASCENDING  # type: ignore

        # dk_strength
        col = db.get_collection("dk_strength")
        try:
            col.create_index([("trade_date", ASCENDING), ("code", ASCENDING), ("type", ASCENDING)], unique=True)
        except Exception as e:
            logger.warning("create_index(dk_strength unique) failed: %s", repr(e))
        col.create_index([("trade_date", ASCENDING)])
        col.create_index([("code", ASCENDING)])

        # DK china split tables: stock/etf/index/lof/reits/future
        for name in ["stock_dk", "etf_dk", "index_dk", "lof_dk", "reits_dk", "future_dk"]:
            col = db.get_collection(name)
            # unique: (trade_date, code) with partial filter for forward-compat
            try:
                col.create_index(
                    [("trade_date", ASCENDING), ("code", ASCENDING)],
                    unique=True,
                    partialFilterExpression={
                        "trade_date": {"$exists": True, "$type": "string"},
                        "code": {"$exists": True},
                    },
                    name="uniq_trade_date_code",
                )
            except Exception as e:
                logger.warning("create_index(%s uniq_trade_date_code) failed: %s", name, repr(e))
            col.create_index([("datetime", ASCENDING)])
            col.create_index([("trade_date", ASCENDING)])
            col.create_index([("code", ASCENDING)])
            col.create_index([("base_code", ASCENDING)])
            col.create_index([("type", ASCENDING)])

        # hkstock_dk (formerly gobal_dk_data)
        col = db.get_collection("hkstock_dk")
        try:
            col.create_index(
                [("trade_date", ASCENDING), ("code", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "trade_date": {"$exists": True, "$type": "string"},
                    "code": {"$exists": True},
                },
                name="uniq_trade_date_code",
            )
        except Exception as e:
            logger.warning("create_index(hkstock_dk uniq_trade_date_code) failed: %s", repr(e))
        col.create_index([("datetime", ASCENDING)])
        col.create_index([("trade_date", ASCENDING)])
        col.create_index([("code", ASCENDING)])

        # dk_ingest_log
        col = db.get_collection("dk_ingest_log")
        col.create_index([("file_path", ASCENDING), ("status", ASCENDING), ("finished_at", ASCENDING)])
        col.create_index([("category", ASCENDING), ("trade_date", ASCENDING)])
    except Exception as e:
        logger.warning("ensure_indexes skipped: %s", repr(e))


def should_skip_incremental(file_path: str | Path, log_collection) -> bool:
    """
    incremental 模式跳过规则：
    - 仅跳过此前 status=success 且 dry_run=False 的文件
    - 且 file_size + mtime + sha1(content_hash) 全部一致
    """
    path = Path(file_path)
    st = path.stat()
    size = int(st.st_size)
    mtime = int(st.st_mtime)

    doc = log_collection.find_one(
        {"file_path": str(path), "status": "success", "dry_run": False},
        sort=[("finished_at", -1)],
    )
    if not doc:
        return False
    if int(doc.get("file_size", -1)) != size or int(doc.get("mtime", -1)) != mtime:
        return False
    if "content_hash" not in doc or not doc.get("content_hash"):
        return False

    fp = _file_fingerprint(path)  # will use cache
    return str(doc.get("content_hash", "")) == fp["content_hash"]


def _insert_ingest_log(log_collection: Any, doc: Dict[str, Any], logger: logging.Logger) -> None:
    try:
        log_collection.insert_one(doc)
    except Exception as e:
        logger.warning("insert dk_ingest_log failed: %s", repr(e))


@dataclass
class IngestResult:
    file_path: str
    file_name: str
    category: str
    trade_date: Optional[str]
    status: Literal["success", "failed", "skipped"]
    sheet_names: List[str]
    rows_parsed: int = 0
    rows_upserted: int = 0
    rows_upserted_by_collection: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


def write_daily_ingest_summary_md(
    report_path: str | Path,
    results: Sequence[IngestResult],
    *,
    root: Path,
    mode: str,
    categories: Sequence[Category],
    dry_run: bool,
) -> None:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_day: Dict[str, List[IngestResult]] = {}
    for r in results:
        td = r.trade_date or "unknown"
        by_day.setdefault(td, []).append(r)

    days_sorted = sorted(by_day.keys(), key=lambda x: int(x) if re.fullmatch(r"\d{8}", x) else 10**9)

    def _agg(day: str, cat: Category) -> Dict[str, Any]:
        items = [r for r in by_day.get(day, []) if r.category == cat]
        return {
            "files": len(items),
            "success": sum(1 for r in items if r.status == "success"),
            "failed": sum(1 for r in items if r.status == "failed"),
            "skipped": sum(1 for r in items if r.status == "skipped"),
            "rows_parsed": sum(int(r.rows_parsed or 0) for r in items),
            "rows_upserted": sum(int(r.rows_upserted or 0) for r in items),
            "items": items,
        }

    def _china_split(day: str) -> Dict[str, int]:
        totals: Dict[str, int] = {k: 0 for k in ["stock_dk", "etf_dk", "index_dk", "lof_dk", "reits_dk", "future_dk"]}
        for r in by_day.get(day, []):
            if r.category != "china" or r.status != "success" or not r.rows_upserted_by_collection:
                continue
            for coll_name, meta in r.rows_upserted_by_collection.items():
                try:
                    totals[str(coll_name)] += int(meta.get("rows_upserted", 0))
                except Exception:
                    continue
        return totals

    lines: List[str] = []
    lines.append("# DK Daily Ingest Summary")
    lines.append("")
    lines.append(f"- generated_at: {now}")
    lines.append(f"- root: {root}")
    lines.append(f"- mode: {mode}")
    lines.append(f"- dry_run: {dry_run}")
    lines.append(f"- categories: {', '.join(categories)}")
    lines.append(f"- days: {len(days_sorted)}")
    lines.append("")
    lines.append("## Daily Summary")
    lines.append("")
    lines.append(
        "| trade_date | china (ok/fail/skip) | stock_dk | etf_dk | index_dk | lof_dk | reits_dk | future_dk | star (ok/fail/skip) | hk (ok/fail/skip) | errors |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    failures: List[IngestResult] = []
    for day in days_sorted:
        err_cnt = 0
        china = _agg(day, "china")
        star = _agg(day, "star")
        glob = _agg(day, "global")

        for r in by_day.get(day, []):
            if r.status == "failed":
                err_cnt += 1
                failures.append(r)

        split = _china_split(day) if "china" in categories else {k: 0 for k in ["stock_dk", "etf_dk", "index_dk", "lof_dk", "reits_dk", "future_dk"]}

        lines.append(
            "| {td} | {c_ok}/{c_fail}/{c_skip} | {stock} | {etf} | {idx} | {lof} | {reits} | {future} | {s_ok}/{s_fail}/{s_skip} | {g_ok}/{g_fail}/{g_skip} | {err} |".format(
                td=day,
                c_ok=china["success"],
                c_fail=china["failed"],
                c_skip=china["skipped"],
                stock=split.get("stock_dk", 0),
                etf=split.get("etf_dk", 0),
                idx=split.get("index_dk", 0),
                lof=split.get("lof_dk", 0),
                reits=split.get("reits_dk", 0),
                future=split.get("future_dk", 0),
                s_ok=star["success"],
                s_fail=star["failed"],
                s_skip=star["skipped"],
                g_ok=glob["success"],
                g_fail=glob["failed"],
                g_skip=glob["skipped"],
                err=err_cnt,
            )
        )

    if failures:
        lines.append("")
        lines.append("## Failures (details)")
        lines.append("")
        for r in failures:
            lines.append(f"- trade_date: `{r.trade_date}`, category: `{r.category}`, file_name: `{r.file_name}`")
            lines.append(f"  - file_path: `{r.file_path}`")
            lines.append(f"  - status: `{r.status}`")
            lines.append(f"  - error_type: `{r.error_type}`")
            lines.append(f"  - error_message: `{_truncate(r.error_message, 300)}`")
            lines.append(f"  - sheet_names: `{r.sheet_names}`")
            if r.error_type == "SheetNotFoundError":
                lines.append("  - next_step: 检查 sheet 改名/新增关键词映射（报告里的 sheet_names 可用于人工判定）")
            elif r.error_type == "KeyError":
                lines.append("  - next_step: 可能是表头偏移或列名变化（例如缺少 'NO.'），需要调整解析逻辑")
            elif r.error_type == "ValueError":
                lines.append("  - next_step: 可能是列数量/布局变化，需要人工确认并更新列映射")
            else:
                lines.append("  - next_step: 根据 error_message 人工排查")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sample_pick_evenly(sorted_paths: Sequence[Path], n: int) -> List[Path]:
    if n <= 0 or not sorted_paths:
        return []
    if n >= len(sorted_paths):
        return list(sorted_paths)
    if n == 1:
        return [sorted_paths[len(sorted_paths) // 2]]
    idxs = np.linspace(0, len(sorted_paths) - 1, num=n)
    uniq: List[Path] = []
    seen = set()
    for i in idxs:
        j = int(round(float(i)))
        if j not in seen:
            seen.add(j)
            uniq.append(sorted_paths[j])
    for p in sorted_paths:
        if len(uniq) >= n:
            break
        if p not in uniq:
            uniq.append(p)
    return uniq


def write_sample_report_md(report_path: str | Path, report_obj: Dict[str, Any]) -> None:
    p = Path(report_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# DK Sample Report")
    lines.append("")
    lines.append(f"- generated_at: {report_obj.get('generated_at')}")
    lines.append(f"- root: {report_obj.get('root')}")
    lines.append(f"- categories: {', '.join(report_obj.get('categories', []))}")
    lines.append(f"- sample_per_year: {report_obj.get('sample_per_year')}")
    lines.append("")

    years = sorted(report_obj.get("years", {}).keys())
    for y in years:
        lines.append(f"## {y}")
        yobj = report_obj["years"][y]
        for cat in ["china", "star", "global"]:
            if cat not in yobj:
                continue
            cobj = yobj[cat]
            files = cobj.get("files", [])
            ok_cnt = int(cobj.get("success", 0))
            fail_cnt = int(cobj.get("failed", 0))
            lines.append(f"### {cat}")
            lines.append(f"- sampled: {len(files)}, success: {ok_cnt}, failed: {fail_cnt}")
            lines.append("")
            if files:
                lines.append("| file_name | trade_date | status | error_type |")
                lines.append("|---|---:|---|---|")
                for it in files:
                    lines.append(
                        f"| {it.get('file_name','')} | {it.get('trade_date','')} | {it.get('status','')} | {it.get('error_type','')} |"
                    )
                lines.append("")

            fails = [it for it in files if it.get("status") == "failed"]
            if fails:
                lines.append("#### Failures")
                for it in fails:
                    lines.append(f"- file_name: `{it.get('file_name')}`")
                    lines.append(f"  - category: `{it.get('category')}`")
                    lines.append(f"  - trade_date: `{it.get('trade_date')}`")
                    lines.append(f"  - error_type: `{it.get('error_type')}`")
                    lines.append(f"  - error_message: `{_truncate(it.get('error_message'), 300)}`")
                    lines.append(f"  - sheet_names: `{it.get('sheet_names')}`")
                    lines.append(f"  - next_step: {it.get('next_step')}")
                lines.append("")

    p.write_text("\n".join(lines), encoding="utf-8")


def _suggest_next_step(error: Exception) -> str:
    if isinstance(error, SheetNotFoundError):
        return "需要新增/调整 sheet 匹配关键词（或排除关键词），并确认目标 sheet 是否改名。"
    if isinstance(error, KeyError):
        return "可能是表头行偏移/列名变化（例如缺少 'NO.'），需要人工确认并调整解析逻辑。"
    if isinstance(error, ValueError):
        return "可能是列数/数据布局变化（例如 global sheet 列不足），需要人工确认并调整列映射。"
    return "请根据 error_message 与 sheet_names 人工排查：可能是 sheet 改名、header 偏移、或列名变化。"


def _fetch_stock_adj_for_date(
    codes_6d: Sequence[str],
    iso_date: str,
    stock_adj_cache: Dict[str, Dict[str, float]],
    logger: logging.Logger,
) -> Dict[str, float]:
    """
    Build fq_dict: code -> adj for a specific iso_date (YYYY-MM-DD).
    Best-effort: if wefetch unavailable / error, return {}.
    """
    if iso_date in stock_adj_cache:
        return stock_adj_cache[iso_date]

    fq_dict: Dict[str, float] = {}
    try:
        from wequant.wefetch import fetch_stock_adj  # type: ignore

        start = iso_date
        end = (pd.to_datetime(iso_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        data_fq = fetch_stock_adj(list(codes_6d), start, end, format="pd")
        if data_fq is None or len(data_fq) == 0:
            fq_dict = {}
        else:
            df = pd.DataFrame(data_fq)
            if "date" in df.columns:
                df = df[df["date"].astype(str).str.startswith(iso_date)]
            if {"code", "adj"}.issubset(df.columns):
                fq_dict = pd.to_numeric(df.set_index("code")["adj"], errors="coerce").fillna(1.0).to_dict()
            else:
                fq_dict = {}
    except Exception as e:
        logger.warning("fetch_stock_adj failed; fallback adj=1. err=%s", repr(e))
        fq_dict = {}

    stock_adj_cache[iso_date] = fq_dict
    return fq_dict


def read_china_dk_file(
    file_path: str | Path,
    index_info: pd.DataFrame,
    future_list: pd.DataFrame,
    stock_adj_cache: Optional[Dict[str, Dict[str, float]]] = None,
) -> pd.DataFrame:
    """
    读取 “【V】奇衡DK...(非全球)” 文件，复刻 notebook 的 total_dk_data2 语义：
    - 多 sheet 合并（矩形/UBW/原共享/主连/情绪数据库/可选 2023/可选 指数数据库）
    - 列处理 + code 生成 + datetime 从文件名提取
    - 去重（按 code）
    - code1/type 补全 + future 主连映射
    """
    logger = logging.getLogger("dk_ingest.china")
    path = Path(file_path)
    file_name = path.name

    trade_date = extract_trade_date(file_name) or ""
    if not trade_date:
        raise ValueError(f"Cannot extract trade_date from file name: {file_name}")

    stock_adj_cache = stock_adj_cache or {}

    xls = pd.ExcelFile(path, engine="openpyxl")
    sheet_names = list(map(str, xls.sheet_names))

    sheet_name1 = pick_sheet(sheet_names, include_keywords=["矩形"])
    sheet_name2 = pick_sheet(sheet_names, include_keywords=["UBW"])
    sheet_name3 = pick_sheet(sheet_names, include_keywords=["原共享"], prefer_keywords=["原共享池"])
    sheet_name4 = pick_sheet(sheet_names, include_keywords=["主连"], prefer_keywords=["原共享池主连"])
    # 情绪数据库：部分历史月份的命名为“全域增强模块”（语义等价）
    sheet_name5 = pick_sheet(
        sheet_names,
        include_keywords=["情绪数据库", "全域增强模块", "全域增强"],
        prefer_keywords=["情绪数据库", "全域增强模块"],
    )

    sheet_name6 = None
    for s in sheet_names:
        if "2023" in s:
            sheet_name6 = s
            break

    sheet_name7 = None
    for s in sheet_names:
        if "指数数据库" in s:
            sheet_name7 = s
            break

    dk_columns = [
        "L_value",
        "R_value",
        "R_switch",
        "L_switch",
        "L_label",
        "R_label",
        "R_bias",
        "L_bias",
        "acitve1",
        "acitve2",
        "exceed1",
        "exceed2",
        "exceed3",
        "switch1",
        "switch2",
        "switch3",
        "code",
    ]

    total_parts: List[pd.DataFrame] = []

    def _read_block(sheet_name: str) -> pd.DataFrame:
        df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
        df.columns = df.iloc[0]
        df = df.iloc[1:].copy()
        if "NO." not in df.columns:
            raise KeyError(f"Missing 'NO.' column in sheet={sheet_name}")
        df["code"] = df["NO."].apply(lambda x: _zfill_numeric_str(x, 6))
        df = df.iloc[:, 2:].copy()
        df.columns = dk_columns
        return df

    total_parts.append(_read_block(sheet_name1))
    total_parts.append(_read_block(sheet_name2))
    total_parts.append(_read_block(sheet_name3))

    df5 = pd.read_excel(path, sheet_name=sheet_name5, engine="openpyxl")
    df5 = df5.iloc[5:, [0, 2, 3]].copy()
    df5.columns = ["code", "L_value", "R_value"]
    df5["code"] = df5["code"].apply(lambda x: _zfill_numeric_str(x, 6))
    total_parts.append(df5)

    if sheet_name6 is not None:
        df6 = pd.read_excel(path, sheet_name=sheet_name6, engine="openpyxl")
        df6 = df6.iloc[5:, [0, 2, 3]].copy()
        df6.columns = ["code", "L_value", "R_value"]
        df6["code"] = df6["code"].apply(lambda x: _zfill_numeric_str(x, 6))
        total_parts.append(df6)

    def _strip_L8(v: Any) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return ""
        s = str(v).strip()
        return s[:-2] if len(s) >= 2 else s

    df4 = pd.read_excel(path, sheet_name=sheet_name4, engine="openpyxl")
    df4.columns = df4.iloc[0]
    df4 = df4.iloc[1:].copy()
    df4["code"] = df4.iloc[:, 0].apply(_strip_L8).apply(lambda x: _zfill_numeric_str(x, 6))
    df4 = df4.iloc[:, 2:].copy()
    df4.columns = dk_columns
    total_parts.append(df4)

    if sheet_name7 is not None:
        df7 = pd.read_excel(path, sheet_name=sheet_name7, engine="openpyxl")
        df7.columns = df7.iloc[0]
        df7 = df7.iloc[1:].copy()
        if "NO." not in df7.columns:
            raise KeyError(f"Missing 'NO.' column in sheet={sheet_name7}")
        df7["code"] = df7["NO."].apply(lambda x: "9" + _zfill_numeric_str(x, 6))
        df7 = df7.iloc[:, 2:].copy()
        df7.columns = dk_columns
        total_parts.append(df7)

    total_dk_data = pd.concat(total_parts, ignore_index=True)
    total_dk_data["datetime"] = trade_date  # notebook: 'YYYYMMDD'

    total_dk_data = total_dk_data.fillna(0)

    total_dk_data2 = enrich_code1_and_type(total_dk_data, index_info)
    total_dk_data2 = patch_future_code1_to_main_no_dash(total_dk_data2, future_list)

    # 输出口径：用 code1 替代 code（用户要求：code1 -> code，原 code 不保留）
    out = total_dk_data2.copy()
    out["trade_date"] = trade_date
    if "code1" in out.columns:
        out = out.drop(columns=["code"], errors="ignore").rename(columns={"code1": "code"})

    out["code"] = out["code"].astype(str).str.strip().replace({"nan": ""})
    out = out[out["code"].astype(str).str.strip().ne("")].copy()
    out = out.drop_duplicates(subset=["code"], keep="first")
    out["base_code"] = out["code"].astype(str).str.split(".").str[0].str.strip().replace({"nan": ""})
    return out


def read_strength_file(file_path: str | Path) -> pd.DataFrame:
    return read_first_sheet_strength_table(str(file_path))


def read_global_view_file(file_path: str | Path) -> pd.DataFrame:
    """
    读取 “【V】奇衡DK全球...” 文件（实际为港股 DK），复刻 notebook 逻辑并增强健壮性：
    - sheet_name=None 读出所有 sheet
    - 每个 sheet 统一列名 ['code','name','date','R_value','L_value']（按位置取前 5 列）
    - 港股 code 若为数值且不足 5 位：左侧补 0 到 5 位（>=5 位保持不变）
    - 合并后保留 code/R_value/L_value，并补充 datetime（文件名最后一个 8 位数字 -> YYYY-MM-DD）
    """
    path = Path(file_path)
    file_name = path.name
    trade_date = extract_trade_date(file_name) or ""
    if not trade_date:
        raise ValueError(f"Cannot extract trade_date from file name: {file_name}")

    # 某些“全球视野学习材料”文件：只需要读「主清单」，且列块重复两次：
    #   No / item / R / L  |  No / item / R / L
    # 需要把两块都读完并合并。
    xls = pd.ExcelFile(path, engine="openpyxl")
    sheet_names = list(map(str, xls.sheet_names))
    main_sheet = next((s for s in sheet_names if "主清单" in s), None)

    def _normalize_code_series(code_series: pd.Series) -> pd.Series:
        code_str = code_series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        digit_mask = code_str.str.fullmatch(r"\d+", na=False)
        if digit_mask.any():
            # HK: pad to at least 5 digits (do NOT force 6-digit padding)
            code_str.loc[digit_mask] = code_str.loc[digit_mask].str.zfill(5)
        return code_str

    if main_sheet is not None:
        df = pd.read_excel(path, sheet_name=main_sheet, engine="openpyxl")
        cols = list(df.columns)

        def _norm_col_name(c: Any) -> str:
            s = str(c).strip()
            s = re.sub(r"\.\d+$", "", s)  # pandas mangle duplicated columns
            s = re.sub(r"[^A-Za-z0-9]+", "", s).lower()  # 'No.' -> 'no'
            return s

        target = ["no", "item", "r", "l"]
        starts: List[int] = []
        for i in range(0, max(0, len(cols) - 3)):
            if [_norm_col_name(cols[i + j]) for j in range(4)] == target:
                starts.append(i)

        if not starts:
            # 兜底：按位置取两块（常见 8 列）
            if df.shape[1] >= 8:
                starts = [0, 4]
            elif df.shape[1] >= 4:
                starts = [0]
            else:
                raise ValueError(f"Global 主清单 columns < 4: cols={df.shape[1]}")

        parts: List[pd.DataFrame] = []
        for st in starts:
            sub = df.iloc[:, st : st + 4].copy()
            sub.columns = ["code", "name", "R_value", "L_value"]
            sub = sub.dropna(subset=["code"])
            sub["code"] = _normalize_code_series(sub["code"])
            sub = sub[sub["code"].astype(str).str.strip().ne("")]
            out = sub[["code", "R_value", "L_value"]].copy()
            parts.append(out)

        total = pd.concat(parts, ignore_index=True)
        total = total.drop_duplicates(subset=["code"], keep="first")
        total["trade_date"] = trade_date
        total["datetime"] = _safe_datetime_yyyymmdd_to_iso(trade_date) or trade_date
        return total[["trade_date", "datetime", "code", "R_value", "L_value"]]

    # fallback：按 notebook 逻辑读取所有 sheet
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    sheet_names2 = list(map(str, sheets.keys()))

    parts2: List[pd.DataFrame] = []
    for sheet_name in sheet_names2:
        df = sheets[sheet_name].copy()
        if df.shape[1] < 5:
            raise ValueError(f"Global sheet columns < 5: sheet={sheet_name}, cols={df.shape[1]}")

        df = df.iloc[:, :5].copy()
        df.columns = ["code", "name", "date", "R_value", "L_value"]
        df["code"] = _normalize_code_series(df["code"])

        out = df[["code", "R_value", "L_value"]].copy()
        parts2.append(out)

    total = pd.concat(parts2, ignore_index=True)
    total = total.drop_duplicates(subset=["code"], keep="first")
    total["trade_date"] = trade_date
    total["datetime"] = _safe_datetime_yyyymmdd_to_iso(trade_date) or trade_date
    return total[["trade_date", "datetime", "code", "R_value", "L_value"]]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="DK Excel ingestion (full/incremental/sample)")
    parser.add_argument("--root", default=r"D:\zxxq_xlsx", help=r"Root directory (default: D:\zxxq_xlsx)")
    parser.add_argument("--mode", choices=["full", "incremental", "sample"], required=True)
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not write data collections")
    parser.add_argument(
        "--trade-date",
        default="",
        help="Only process files whose trade_date (last 8 digits in filename) equals this value (e.g. 20260203)",
    )
    parser.add_argument(
        "--categories",
        default="china,star,global",
        help="Comma separated: china,star,global (default: all)",
    )
    parser.add_argument("--sample-per-year", type=int, default=2, help="Sample count per year per category (sample mode)")
    parser.add_argument("--report-dir", default="./reports", help="Report output dir (sample mode)")
    parser.add_argument(
        "--daily-summary-md",
        default="",
        help="Write per-trade_date ingest summary markdown (full/incremental only). Example: wequant/test/dk_daily_ingest_YYYYMMDD_HHMM.md",
    )
    parser.add_argument("--log-level", default="INFO", choices=["INFO", "ERROR"])

    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logger = logging.getLogger("dk_ingest")

    categories = [c.strip() for c in str(args.categories).split(",") if c.strip()]
    cat_list: List[Category] = []
    for c in categories:
        if c not in ("china", "star", "global"):
            raise SystemExit(f"Unknown category: {c}")
        cat_list.append(c)  # type: ignore[arg-type]

    root = Path(args.root)
    files = list_target_files(root, cat_list)
    if args.trade_date:
        td = str(args.trade_date).strip()
        files = [p for p in files if extract_trade_date(p.name) == td]
        logger.info("filtered by trade_date=%s -> %d files", td, len(files))
    logger.info("found %d target files under %s", len(files), str(root))

    # ---------------------------------------------------------
    # sample mode: parse only + markdown report, no MongoDB
    # ---------------------------------------------------------
    if args.mode == "sample":
        try:
            from wequant.wefetch import fetch_index_list, fetch_future_list  # type: ignore

            index_info = fetch_index_list()
            future_list = fetch_future_list()
        except Exception:
            index_info = pd.DataFrame()
            future_list = pd.DataFrame()

        report_obj: Dict[str, Any] = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "root": str(root),
            "categories": cat_list,
            "sample_per_year": int(args.sample_per_year),
            "years": {},
        }

        grouped: Dict[str, Dict[Category, List[Path]]] = {}
        for p in files:
            td = extract_trade_date(p.name) or ""
            year = td[:4] if re.fullmatch(r"\d{8}", td) else "unknown"
            cat = detect_category(p.name)
            if cat is None:
                continue
            grouped.setdefault(year, {}).setdefault(cat, []).append(p)

        for year, by_cat in grouped.items():
            report_obj["years"].setdefault(year, {})
            for cat, paths in by_cat.items():
                paths_sorted = sorted(paths, key=lambda x: extract_trade_date(x.name) or x.name)
                picked = _sample_pick_evenly(paths_sorted, int(args.sample_per_year))
                ok = 0
                fail = 0
                items: List[Dict[str, Any]] = []
                for p in picked:
                    td = extract_trade_date(p.name)
                    sheet_names = _load_excel_sheet_names(p)
                    try:
                        if cat == "china":
                            _ = read_china_dk_file(p, index_info, future_list, stock_adj_cache={})
                        elif cat == "star":
                            _ = read_strength_file(p)
                        elif cat == "global":
                            _ = read_global_view_file(p)
                        else:
                            raise ValueError(f"unknown category {cat}")
                        ok += 1
                        items.append(
                            {
                                "file_name": p.name,
                                "category": cat,
                                "trade_date": td,
                                "status": "success",
                                "error_type": "",
                                "error_message": "",
                                "sheet_names": sheet_names,
                                "next_step": "",
                            }
                        )
                    except Exception as e:
                        fail += 1
                        items.append(
                            {
                                "file_name": p.name,
                                "category": cat,
                                "trade_date": td,
                                "status": "failed",
                                "error_type": e.__class__.__name__,
                                "error_message": _truncate(repr(e), 2000),
                                "sheet_names": sheet_names,
                                "next_step": _suggest_next_step(e),
                            }
                        )

                report_obj["years"][year][cat] = {"success": ok, "failed": fail, "files": items}

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        report_path = Path(args.report_dir) / f"dk_sample_report_{ts}.md"
        write_sample_report_md(report_path, report_obj)
        logger.info("sample report written: %s", str(report_path))
        return 0

    # ---------------------------------------------------------
    # full / incremental: MongoDB (log always best-effort)
    # ---------------------------------------------------------
    db = None
    log_collection = None
    try:
        db = _connect_db()
        _ensure_indexes(db, logger)
        log_collection = db.get_collection("dk_ingest_log")
    except Exception as e:
        if not args.dry_run:
            raise
        logger.warning("MongoDB not available in dry-run; will run without ingest_log. err=%s", repr(e))
        db = None
        log_collection = None

    try:
        from wequant.wefetch import fetch_index_list, fetch_future_list  # type: ignore

        index_info = fetch_index_list()
        future_list = fetch_future_list()
    except Exception as e:
        logger.warning("fetch_index_list/fetch_future_list failed; fallback empty. err=%s", repr(e))
        index_info = pd.DataFrame()
        future_list = pd.DataFrame()

    stock_adj_cache: Dict[str, Dict[str, float]] = {}

    success = 0
    failed = 0
    skipped = 0
    results: List[IngestResult] = []

    for p in files:
        cat = detect_category(p.name)
        if cat is None:
            continue

        started_at = datetime.utcnow()
        t0 = time.time()

        trade_date = extract_trade_date(p.name)
        sheet_names = _load_excel_sheet_names(p)
        fp = _file_fingerprint(p)

        # incremental skip decision
        if args.mode == "incremental" and log_collection is not None:
            try:
                if should_skip_incremental(p, log_collection):
                    skipped += 1
                    finished_at = datetime.utcnow()
                    duration_sec = float(max(0.0, time.time() - t0))
                    if log_collection is not None:
                        _insert_ingest_log(
                            log_collection,
                            {
                                "file_path": str(p),
                                "file_name": p.name,
                                "category": cat,
                                "trade_date": trade_date,
                                **fp,
                                "status": "skipped",
                                "mode": args.mode,
                                "dry_run": bool(args.dry_run),
                                "started_at": started_at,
                                "finished_at": finished_at,
                                "duration_sec": duration_sec,
                                "sheet_names": sheet_names,
                                "rows_parsed": 0,
                                "rows_upserted": 0,
                            },
                            logger,
                        )
                    logger.info("skipped (unchanged): %s", p.name)
                    results.append(
                        IngestResult(
                            file_path=str(p),
                            file_name=p.name,
                            category=cat,
                            trade_date=trade_date,
                            status="skipped",
                            sheet_names=sheet_names,
                            rows_parsed=0,
                            rows_upserted=0,
                        )
                    )
                    continue
            except Exception as e:
                logger.warning("skip check failed; will process. file=%s err=%s", p.name, repr(e))

        rows_upserted_by_collection: Optional[Dict[str, Any]] = None
        try:
            if cat == "china":
                df = read_china_dk_file(p, index_info, future_list, stock_adj_cache=stock_adj_cache)
                rows_parsed = int(len(df))
                rows_upserted = 0

                # Route by `type` into split collections.
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

                unknown_types = sorted(set(df0["type"].unique()) - set(type_to_coll.keys()))
                if unknown_types:
                    logger.warning("china dk unknown types=%s -> route to stock_dk", unknown_types)

                rows_upserted_by_collection = {}
                for coll_name, sub in df0.groupby("_target_coll", sort=False):
                    sub = sub.drop(columns=["_target_coll"], errors="ignore")
                    rows_upserted_by_collection[str(coll_name)] = {"rows_parsed": int(len(sub)), "rows_upserted": 0}
                    if args.dry_run:
                        continue
                    if db is None:
                        raise RuntimeError("MongoDB is not available but dry-run is False")
                    coll = db.get_collection(str(coll_name))
                    _, n = upsert_dataframe(
                        coll,
                        sub,
                        ["trade_date", "code"],
                        unset_fields=["adj", "L_value_adj", "R_value_adj", "source_sheet"],
                    )
                    rows_upserted += int(n)
                    rows_upserted_by_collection[str(coll_name)]["rows_upserted"] = int(n)

            elif cat == "star":
                df = read_strength_file(p)
                rows_parsed = int(len(df))
                rows_upserted = 0
                if not args.dry_run:
                    if db is None:
                        raise RuntimeError("MongoDB is not available but dry-run is False")
                    coll = db.get_collection("dk_strength")
                    _, rows_upserted = upsert_dataframe(coll, df, ["trade_date", "code", "type"])

            elif cat == "global":
                df = read_global_view_file(p)
                rows_parsed = int(len(df))
                rows_upserted = 0
                if not args.dry_run:
                    if db is None:
                        raise RuntimeError("MongoDB is not available but dry-run is False")
                    coll = db.get_collection("hkstock_dk")
                    _, rows_upserted = upsert_dataframe(
                        coll,
                        df,
                        ["trade_date", "code"],
                        unset_fields=["source_sheet"],
                    )
            else:
                raise ValueError(f"Unknown category: {cat}")

            success += 1
            status = "success"
            err_type = None
            err_msg = None
        except Exception as e:
            failed += 1
            rows_parsed = 0
            rows_upserted = 0
            status = "failed"
            err_type = e.__class__.__name__
            err_msg = _truncate(repr(e), 2000)
            logger.error("failed: file=%s cat=%s err=%s", p.name, cat, err_msg)

        finished_at = datetime.utcnow()
        duration_sec = float(max(0.0, time.time() - t0))

        results.append(
            IngestResult(
                file_path=str(p),
                file_name=p.name,
                category=cat,
                trade_date=trade_date,
                status=status,
                sheet_names=sheet_names,
                rows_parsed=rows_parsed,
                rows_upserted=rows_upserted,
                rows_upserted_by_collection=rows_upserted_by_collection,
                error_type=err_type,
                error_message=err_msg,
            )
        )

        if log_collection is not None:
            _insert_ingest_log(
                log_collection,
                {
                    "file_path": str(p),
                    "file_name": p.name,
                    "category": cat,
                    "trade_date": trade_date,
                    **fp,
                    "status": status,
                    "mode": args.mode,
                    "dry_run": bool(args.dry_run),
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_sec": duration_sec,
                    "sheet_names": sheet_names,
                    "rows_parsed": rows_parsed,
                    "rows_upserted": rows_upserted,
                    "rows_upserted_by_collection": rows_upserted_by_collection,
                    "error_type": err_type,
                    "error_message": err_msg,
                },
                logger,
            )

        if status == "success":
            logger.info("success: file=%s cat=%s rows=%d", p.name, cat, rows_parsed)

    if args.daily_summary_md:
        try:
            write_daily_ingest_summary_md(
                args.daily_summary_md,
                results,
                root=root,
                mode=str(args.mode),
                categories=cat_list,
                dry_run=bool(args.dry_run),
            )
            logger.info("daily summary written: %s", str(args.daily_summary_md))
        except Exception as e:
            logger.warning("write daily summary failed: %s", repr(e))

    logger.info("done. success=%d failed=%d skipped=%d", success, failed, skipped)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
