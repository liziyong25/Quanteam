import pandas as pd
import numpy as np

import re
from datetime import datetime, timedelta

from .utils import (
    DATABASE1,
    DATABASE2,
    DATABASE3,
    DATABASE_TEST2,
    bond_code2sql_fromat,
)

import re
import numpy as np
import pandas as pd


_MM_EXACT_MAP = {
    # repo R/OR
    "R001": "1d", "R007": "7d", "R014": "14d",
    "OR001": "1d", "OR007": "7d", "OR014": "14d",
    # credit IBO
    "IBO001": "1d", "IBO007": "7d", "IBO014": "14d",
}

_MM_GT14_PREFIXES = ("R", "OR", "IBO")
_MM_GT14_SUFFIXES = {"021", "1M", "2M", "3M", "4M", "6M", "9M", "1Y"}  # -> >14d

_MM_KEEP_AS_IS = {"利率债", "信用债", "同业存单"}  # 原样保留


def _add_new_age_money_market(df: pd.DataFrame, symbol_col: str = "symbol", out_col: str = "new_age") -> pd.DataFrame:
    """
    给 repo / credit（货币市场）数据增加 new_age 分桶。

    规则：
    - R/OR/IBO 这三类前缀的期限：
      - *001 -> 1d, *007 -> 7d, *014 -> 14d
      - *021 / *1M/*2M/*3M/*4M/*6M/*9M/*1Y -> >14d
    - '利率债','信用债','同业存单'：new_age 原样等于 symbol
    - 其它：NaN
    """
    if df is None or len(df) == 0:
        return df

    d = df.copy()
    if symbol_col not in d.columns:
        d[out_col] = np.nan
        return d

    s = d[symbol_col].astype(str).str.strip()

    # 默认 NaN
    d[out_col] = np.nan

    # 保留类
    mask_keep = s.isin(_MM_KEEP_AS_IS)
    d.loc[mask_keep, out_col] = s[mask_keep]

    # 精确映射
    d.loc[s.isin(_MM_EXACT_MAP.keys()), out_col] = s.map(_MM_EXACT_MAP)

    # >14d 分桶：R/OR/IBO + (021|1M|...|1Y)
    # 用正则抓前缀与后缀
    m = s.str.extract(r"^(R|OR|IBO)(\d{3}|1M|2M|3M|4M|6M|9M|1Y)$")
    # m[0]=prefix, m[1]=suffix
    mask_gt14 = m[0].notna() & m[1].isin(_MM_GT14_SUFFIXES)
    d.loc[mask_gt14, out_col] = ">14d"

    return d




def _format_table_name(table_name):
    if "." in table_name:
        return f"`{table_name}`"
    return table_name


def _apply_datetime(data, columns):
    for column in columns:
        if column in data.columns:
            data[column] = pd.to_datetime(data[column], errors="coerce")
    return data


def _clean_text(value):
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    s = str(value).replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    return s


_ALIAS_NORMALIZE = {
    "大行及政策行": "大行及政策行",
    "大行及政策行 ": "大行及政策行",
    "大型商业银行/政策性银行": "大行及政策行",
    "大型商业/政策性银行":'大行及政策行',
    "大型商业/政策性银行": "大行及政策行",
    "大型商业银行/政策性银行 ": "大行及政策行",
    "大型商业银行/政策性银行（Large Commercial Banks/Policy Banks）": "大行及政策行",
    "大型商业银行/政策性银行 （Large Commercial Banks/Policy Banks）": "大行及政策行",
    "大型商业银行/政策性银行(Large Commercial Banks/Policy Banks)": "大行及政策行",
    "大型商业银行/政策性银行 (Large Commercial Banks/Policy Banks)": "大行及政策行",
}


def _normalize_industry_raw(industry):
    s = _clean_text(industry)
    if s is None:
        return None
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = _ALIAS_NORMALIZE.get(s, s)
    return re.sub(r"\s+", " ", s).strip()


_NEW_INDUSTRY_MAP = {
    "大行及政策行": "大型银行",
    "股份制商业银行": "大型银行",
    "大型银行": "大型银行",
    "城市商业银行": "中小型银行",
    "农村金融机构": "中小型银行",
    "外资银行": "中小型银行",
    "中小型银行": "中小型银行",
    "其他产品类": "其他",
    "其他": "其他",
}


def _derive_new_industry(industry):
    ind = _normalize_industry_raw(industry)
    if ind is None:
        return None
    return _NEW_INDUSTRY_MAP.get(ind, ind)


def _add_new_industry(df: pd.DataFrame, industry_col: str = "industry") -> pd.DataFrame:
    out = df.copy()
    if industry_col in out.columns:
        out[industry_col] = out[industry_col].apply(_normalize_industry_raw)
        out["new_industry"] = out[industry_col].apply(_derive_new_industry)
    else:
        out["new_industry"] = None
    return out


def _age_start_num(age) -> float:
    s = _clean_text(age)
    if s is None:
        return np.nan
    if s in {"合计", "Total"}:
        return np.nan
    m = re.search(r"(\d+)", s)
    return float(m.group(1)) if m else np.nan


def _to_new_age(age):
    s = _clean_text(age)
    if s is None:
        return None
    if s in {"合计", "Total"}:
        return "合计" if s == "合计" else s
    start = _age_start_num(s)
    if pd.notna(start) and start >= 10:
        return "10年-50年"
    return s


def _add_new_age(df: pd.DataFrame, age_col: str = "age") -> pd.DataFrame:
    out = df.copy()
    if age_col in out.columns:
        out["new_age"] = out[age_col].apply(_to_new_age)
    else:
        out["new_age"] = None
    return out


def _build_date_filter(column, start, end):
    if start and end:
        return f"{column}>='{start}' and {column}<='{end}'"
    if start:
        return f"{column}>='{start}'"
    if end:
        return f"{column}<='{end}'"
    return None


def _build_symbol_filter(symbol):
    if symbol == "all":
        return None
    symbol_sql = bond_code2sql_fromat(symbol)
    return f"symbol in {symbol_sql}"


def _join_filters(filters):
    return " and ".join([f for f in filters if f])


def _fetch_trade_dates(table_name, engine):
    sql_query = f"SELECT DISTINCT trade_date FROM {table_name}"
    data = pd.read_sql_query(sql_query, engine)
    if data.empty or "trade_date" not in data.columns:
        return []
    data = _apply_datetime(data, ["trade_date"])
    dates = data["trade_date"].dropna().dt.date
    return sorted(dates.unique().tolist())


def _fetch_clean_transaction_table(
    table_name, symbol, start, end, vaild_type="vaild", engine=DATABASE_TEST2
):
    vaild_type_dict = {"vaild": "1", "invaild": "0", "both": ["1", "0"]}
    vaild_value = vaild_type_dict.get(vaild_type, vaild_type)
    vaild_sql = bond_code2sql_fromat(vaild_value)

    filters = [f"is_vaild in {vaild_sql}"]
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = f"SELECT * FROM {table_name}"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date", "create_time", "transact_time"])
    return data.drop_duplicates()


def fetch_bondInformation(symbol, query_date=None, engine=DATABASE_TEST2):
    """
    Fetch bond reference data from wind_bondinformation in test2.
    """
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = f"SELECT * FROM wind_bondinformation WHERE symbol in {symbol_sql}"
    else:
        sql_query = "SELECT * FROM wind_bondinformation"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = data.sort_values("coupon").drop_duplicates("symbol")
    data = _apply_datetime(
        data,
        ["list_date", "delist_date", "maturity_date", "issue_date", "first_accr_date"],
    )
    if "wind_class2" in data.columns and "common_class" not in data.columns:
        data["common_class"] = data["wind_class2"]
    if "symbol" in data.columns:
        data["bond_id"] = data["symbol"].apply(
            lambda x: str(x).split(".")[0] if pd.notna(x) else x
        )
        data["exchange"] = data["symbol"].apply(
            lambda x: str(x).split(".")[-1] if pd.notna(x) else x
        )
        data = data.set_index("symbol", drop=False)

    anchor_date = pd.Timestamp.now()
    if query_date is not None:
        anchor_date = pd.to_datetime(query_date)
    if "maturity_date" in data.columns:
        data["age_limit"] = (data["maturity_date"] - anchor_date).dt.days / 365
    if "list_date" in data.columns and "delist_date" in data.columns:
        data["age"] = data[["list_date", "delist_date"]].apply(
            lambda x: round((x["delist_date"] - x["list_date"]).days / 365,0)
            if pd.notna(x["delist_date"]) and pd.notna(x["list_date"])
            else None,
            axis=1,
        )
    if "issue_size" in data.columns:
        data["issue_size"] = data["issue_size"].fillna(0)
        data["issue_size"] = data["issue_size"].apply(
            lambda x: x / 1e8 if x > 1e6 else x
        )
        data["total_size"] = data["issue_size"]
    data = data.dropna(subset=["short_name"]) if "short_name" in data.columns else data
    data['issuer_type'] = data['short_name'].apply(lambda x: '增发' if '增' in x or '续' in x else '始发')
    data['issuer_type'] = data[['short_name','issuer_type']].apply(lambda x: '始发' if '永续' in x['short_name'] else x['issuer_type'],axis=1)
    data['clause'] = data['clause'].fillna("")
    return data


def fetch_clean_bondinformation(symbol="all", engine=DATABASE_TEST2):
    """
    Fetch cleaned bond reference data from clean_bondinformation in test2.
    """
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = f"SELECT * FROM clean_bondinformation WHERE symbol in {symbol_sql}"
    else:
        sql_query = "SELECT * FROM clean_bondinformation"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data

    data = _apply_datetime(
        data,
        ["list_date", "delist_date", "maturity_date", "issue_date", "first_accr_date"],
    )
    if "symbol" in data.columns:
        data["bond_id"] = data["symbol"].apply(
            lambda x: str(x).split(".")[0] if pd.notna(x) else x
        )
        data["exchange"] = data["symbol"].apply(
            lambda x: str(x).split(".")[-1] if pd.notna(x) else x
        )
        data = data.set_index("symbol", drop=False)
    if "maturity_date" in data.columns:
        data["age_limit"] = (
            data["maturity_date"] - pd.Timestamp.now()
        ).dt.days / 365
    if "list_date" in data.columns and "delist_date" in data.columns:
        data["age"] = data[["list_date", "delist_date"]].apply(
            lambda x: (x["delist_date"] - x["list_date"]).days / 365
            if pd.notna(x["delist_date"]) and pd.notna(x["list_date"])
            else None,
            axis=1,
        )

    return data


def fetch_clean_transaction(symbol, start, end, vaild_type="vaild", engine=DATABASE_TEST2):
    """
    Fetch cleaned transaction data from clean_bondexecreport_v2 in test2.
    """
    return _fetch_clean_transaction_table(
        "clean_bondexecreport_v2", symbol, start, end, vaild_type=vaild_type, engine=engine
    )


def fetch_clean_transaction_v1(
    symbol, start, end, vaild_type="vaild", engine=DATABASE_TEST2
):
    """
    Fetch cleaned transaction data from clean_bondexecreport (legacy) in test2.
    """
    return _fetch_clean_transaction_table(
        "clean_bondexecreport", symbol, start, end, vaild_type=vaild_type, engine=engine
    )


def fetch_clean_transaction_v2(
    symbol, start, end, vaild_type="vaild", engine=DATABASE_TEST2
):
    """
    Fetch cleaned transaction data from clean_bondexecreport_v2 in test2.
    """
    return _fetch_clean_transaction_table(
        "clean_bondexecreport_v2", symbol, start, end, vaild_type=vaild_type, engine=engine
    )


def fetch_clean_transaction_dates(engine=DATABASE_TEST2):
    """
    Fetch distinct trade_date values from clean_bondexecreport_v2 in test2.
    """
    return _fetch_trade_dates("clean_bondexecreport_v2", engine)


def fetch_clean_transaction_v1_dates(engine=DATABASE_TEST2):
    """
    Fetch distinct trade_date values from clean_bondexecreport (legacy) in test2.
    """
    return _fetch_trade_dates("clean_bondexecreport", engine)


def fetch_clean_transaction_v2_dates(engine=DATABASE_TEST2):
    """
    Fetch distinct trade_date values from clean_bondexecreport_v2 in test2.
    """
    return _fetch_trade_dates("clean_bondexecreport_v2", engine)


def fetch_clean_execreport_1d_dates(engine=DATABASE_TEST2):
    """
    Fetch distinct trade_date values from clean_execreport_1d in test2.
    """
    sql_query = "SELECT DISTINCT trade_date FROM clean_execreport_1d"
    data = pd.read_sql_query(sql_query, engine)
    if data.empty or "trade_date" not in data.columns:
        return []
    data = _apply_datetime(data, ["trade_date"])
    dates = data["trade_date"].dropna().dt.date
    return sorted(dates.unique().tolist())


def fetch_clean_execreport_1d_v2_dates(engine=DATABASE_TEST2):
    """
    Fetch distinct trade_date values from clean_execreport_1d_v2 in test2.
    """
    return _fetch_trade_dates("clean_execreport_1d_v2", engine)


def fetch_realtime_trade_backup(
    symbol, start, end, vaild_type="vaild", engine=DATABASE_TEST2
):
    """
    Fetch raw transaction backup data from realtime_trade_backup in test2.
    """
    vaild_type_dict = {"vaild": "1", "invaild": "0", "both": ["1", "0"]}
    vaild_value = vaild_type_dict.get(vaild_type, vaild_type)
    vaild_sql = bond_code2sql_fromat(vaild_value)

    filters = [f"is_vaild in {vaild_sql}"]
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = "SELECT * FROM realtime_trade_backup"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date", "create_time", "transact_time"])
    return data.drop_duplicates()


def fetch_realtime_trade_backup_dates(engine=DATABASE_TEST2):
    """
    Fetch distinct trade_date values from realtime_trade_backup in test2.
    """
    sql_query = "SELECT DISTINCT trade_date FROM realtime_trade_backup"
    data = pd.read_sql_query(sql_query, engine)
    if data.empty or "trade_date" not in data.columns:
        return []
    data = _apply_datetime(data, ["trade_date"])
    dates = data["trade_date"].dropna().dt.date
    return sorted(dates.unique().tolist())


def fetch_bond_day(symbol, start, end, engine=DATABASE_TEST2):
    """
    Fetch daily bond data from clean_execreport_1d_v2 in test2.
    """
    return fetch_bond_day_v2(symbol, start, end, engine=engine)


def fetch_bond_day_v1(symbol, start, end, engine=DATABASE_TEST2):
    """
    Fetch daily bond data from clean_execreport_1d in test2.
    """
    filters = ["is_vaild=1"]
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = "SELECT * FROM clean_execreport_1d"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date", "pre_date"])
    return data.sort_values("trade_date").drop_duplicates()


def fetch_bond_day_v2(symbol, start, end, engine=DATABASE_TEST2):
    """
    Fetch daily bond data from clean_execreport_1d_v2 in test2.
    """
    filters = ["is_vaild=1"]
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = "SELECT * FROM clean_execreport_1d_v2"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date", "pre_date"])
    return data.sort_values("trade_date").drop_duplicates()


def fetch_settlement_bond_day(symbol, start, end, engine=DATABASE_TEST2):
    """
    Fetch settlement daily data from clean_execreport_drquant_1d in test2.
    """
    filters = ["is_vaild=1"]
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = "SELECT * FROM clean_execreport_drquant_1d"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date", "pre_date"])
    return data.sort_values("trade_date").drop_duplicates()


def fetch_cfets_dfz_bond_day(symbol, start, end, engine=DATABASE_TEST2):
    """
    Fetch CFETS DFZ daily data from clean_execreport_cfets_dfz_1d in test2.
    """
    filters = ["is_vaild=1"]
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = "SELECT * FROM clean_execreport_cfets_dfz_1d"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date", "pre_date"])
    return data.sort_values("trade_date").drop_duplicates()


def fetch_bond_date_list(engine=DATABASE_TEST2):
    table = _format_table_name("test.wind_cbondcalendar")
    sql_query = (
        f"SELECT trade_days FROM {table} "
        "WHERE s_info_exchmarket='IB' ORDER BY trade_days"
    )
    try:
        data = pd.read_sql_query(sql_query, engine)
    except Exception:
        fallback = _format_table_name("wind_cbondcalendar")
        sql_query = (
            f"SELECT trade_days FROM {fallback} "
            "WHERE s_info_exchmarket='IB' ORDER BY trade_days"
        )
        data = pd.read_sql_query(sql_query, engine)
    if data.empty or "trade_days" not in data.columns:
        return []
    return list(pd.to_datetime(data["trade_days"]))


def _zz_bond_valuation_table_by_suffix(suffix):
    mapping = {
        "IB": "zz_bond_valuation_ib",
        "BC": "zz_bond_valuation_bc",
        "SZ": "zz_bond_valuation_sz",
        "BJ": "zz_bond_valuation_bj",
        "SH": "zz_bond_valuation_sh",
    }
    return mapping.get(suffix)


def _split_symbols_by_suffix(symbols):
    groups = {}
    for sym in symbols:
        parts = str(sym).split(".")
        suffix = parts[-1].upper() if len(parts) > 1 else None
        groups.setdefault(suffix, []).append(sym)
    return groups


def fetch_zz_bond_valuation_table(
    table_name,
    symbol,
    start,
    end,
    convincing=True,
    engine=DATABASE_TEST2,
    columns=None,
):
    select_cols = "*"
    if columns is not None:
        safe_cols = []
        for col in columns:
            col = str(col)
            if not col.replace("_", "").isalnum():
                continue
            safe_cols.append(col)
        if convincing and "convincing" not in safe_cols:
            safe_cols.append("convincing")
        if safe_cols:
            select_cols = ", ".join(safe_cols)
    if symbol == "all":
        sql_query = (
            f"SELECT {select_cols} FROM {table_name} "
            f"WHERE trade_date>='{start}' and trade_date<='{end}'"
        )
    else:
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            f"SELECT {select_cols} FROM {table_name} "
            f"WHERE symbol in {symbol_sql} and trade_date>='{start}' "
            f"and trade_date<='{end}'"
        )
    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date"])
    if all(col in data.columns for col in ["symbol", "trade_date", "age_limit"]):
        data = data.drop_duplicates(subset=["symbol", "trade_date", "age_limit"])
    if convincing:
        data = data.sort_values("convincing").drop_duplicates(['trade_date','symbol'])
    return data.sort_values("trade_date")


def fetch_zz_bond_valuation_all(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_table(
        "zz_bond_valuation_all", symbol, start, end, engine=engine
    )


def fetch_zz_bond_valuation_raw(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_table(
        "zz_bond_valuation", symbol, start, end, engine=engine
    )


def fetch_zz_bond_valuation_ib(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_table(
        "zz_bond_valuation_ib", symbol, start, end, engine=engine
    )


def fetch_zz_bond_valuation_bc(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_table(
        "zz_bond_valuation_bc", symbol, start, end, engine=engine
    )


def fetch_zz_bond_valuation_sz(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_table(
        "zz_bond_valuation_sz", symbol, start, end, engine=engine
    )


def fetch_zz_bond_valuation_bj(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_table(
        "zz_bond_valuation_bj", symbol, start, end, engine=engine
    )


def fetch_zz_bond_valuation_sh(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_table(
        "zz_bond_valuation_sh", symbol, start, end, engine=engine
    )


def fetch_zz_bond_valuation_intermarket(symbol, start, end, engine=DATABASE_TEST2):
    return fetch_zz_bond_valuation_ib(symbol, start, end, engine=engine)


def fetch_zz_bond_valuation(symbol, start, end, engine=DATABASE_TEST2, columns=None):
    tables = [
        "zz_bond_valuation_ib",
        "zz_bond_valuation_bc",
        "zz_bond_valuation_sz",
        "zz_bond_valuation_bj",
        "zz_bond_valuation_sh",
    ]
    if symbol == "all":
        frames = [
            fetch_zz_bond_valuation_table(t, "all", start, end, engine=engine, columns=columns)
            for t in tables
        ]
        data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if data.empty:
            return data
        if all(col in data.columns for col in ["symbol", "trade_date", "age_limit"]):
            data = data.drop_duplicates(subset=["symbol", "trade_date", "age_limit"])
        return data.sort_values("trade_date")

    symbols = symbol if isinstance(symbol, list) else [symbol]
    groups = _split_symbols_by_suffix(symbols)
    frames = []
    for suffix, sym_list in groups.items():
        table_name = _zz_bond_valuation_table_by_suffix(suffix)
        if table_name is None:
            for t in tables:
                frames.append(
                    fetch_zz_bond_valuation_table(t, sym_list, start, end, engine=engine, columns=columns)
                )
        else:
            frames.append(
                fetch_zz_bond_valuation_table(
                    table_name, sym_list, start, end, engine=engine, columns=columns
                )
            )
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    if all(col in data.columns for col in ["symbol", "trade_date", "age_limit"]):
        data = data.drop_duplicates(subset=["symbol", "trade_date", "age_limit"])
    return data.sort_values("trade_date")


def fetch_zz_valuation(symbol, start, end, engine=DATABASE_TEST2):
    if symbol == "all":
        sql_query = (
            "SELECT * from zz_valuation "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    else:
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            "SELECT * from zz_valuation "
            f"where bond_type in {symbol_sql} and trade_date>='{start}' "
            f"and trade_date<='{end}'"
        )
    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date"])
    if all(col in data.columns for col in ["bond_type", "age", "trade_date"]):
        data = data.drop_duplicates(subset=["bond_type", "age", "trade_date"])
    return data.sort_values("trade_date")


def fetch_yc_valuation(symbol, start, end, engine=DATABASE_TEST2):
    if symbol == "all":
        sql_query = (
            "SELECT * from yc_valuation "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    else:
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            "SELECT * from yc_valuation "
            f"where bond_type in {symbol_sql} and trade_date>='{start}' "
            f"and trade_date<='{end}'"
        )
    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date"])
    if all(col in data.columns for col in ["bond_type", "age", "trade_date"]):
        data = data.drop_duplicates(subset=["bond_type", "age", "trade_date"])
    return data.sort_values("trade_date")


def fetch_zz_index(symbol, start, end, engine=DATABASE_TEST2):
    if symbol == "all":
        sql_query = (
            "SELECT * FROM zz_index "
            f"WHERE trade_date>='{start}' and trade_date<='{end}'"
        )
    else:
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            "SELECT * FROM zz_index "
            f"WHERE trade_date>='{start}' and trade_date<='{end}' "
            f"and (symbol_caifu in {symbol_sql} "
            f"or symbol_dirty in {symbol_sql} "
            f"or symbol_clean in {symbol_sql})"
        )
    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date"])
    return data.sort_values("trade_date").drop_duplicates()


def fetch_bond_industry_amount(symbol="all", start=None, end=None, engine=DATABASE_TEST2):
    filters = []
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = "SELECT * FROM bond_industry_amount"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date"])
    return data.drop_duplicates()


def fetch_bond_industry_settlement(symbol="all", start=None, end=None, engine=DATABASE_TEST2):
    filters = []
    symbol_filter = _build_symbol_filter(symbol)
    if symbol_filter:
        filters.append(symbol_filter)
    date_filter = _build_date_filter("trade_date", start, end)
    if date_filter:
        filters.append(date_filter)
    where_clause = _join_filters(filters)
    sql_query = "SELECT * FROM bond_industry_settlement"
    if where_clause:
        sql_query = f"{sql_query} WHERE {where_clause}"

    data = pd.read_sql_query(sql_query, engine)
    if data.empty:
        return data
    data = _apply_datetime(data, ["trade_date", "maturity_date"])
    return data.drop_duplicates()


def fetch_text_event(start_date, end_date, engine=DATABASE2):
    sql_query = (
        "SELECT * FROM replay_weibo_scrapy "
        f"where date>='{start_date}' and date<='{end_date}'"
    )
    return pd.read_sql_query(sql_query, engine)


def fetch_wind_text_event(start_date, end_date, engine=DATABASE2):
    sql_query = (
        "SELECT * FROM wind_text_event "
        f"where trade_date>='{start_date}' and trade_date<='{end_date}'"
    )
    return pd.read_sql_query(sql_query, engine)


def fetch_realtime_transaction(symbol, vaild_type="vaild", engine=DATABASE_TEST2):
    vaild_type_dict = {"vaild": "1", "invaild": "0", "both": ["1", "0"]}
    vaild_value = vaild_type_dict.get(vaild_type, vaild_type)
    vaild_sql = bond_code2sql_fromat(vaild_value)
    columns = (
        "symbol,side,settl_date,strike_price,yield,transact_time,"
        "security_type,trade_date,create_time,seq_no,is_vaild"
    )
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            f"SELECT {columns} FROM realtime_trade "
            f"where is_vaild in {vaild_sql} and symbol in {symbol_sql}"
        )
    else:
        sql_query = (
            f"SELECT {columns} FROM realtime_trade "
            f"where is_vaild in {vaild_sql}"
        )
    data = pd.read_sql_query(sql_query, engine)
    return data.drop_duplicates()


def fetch_clean_quote(symbol, start, end, vaild_type="vaild", engine=DATABASE_TEST2):
    start = f"{start} 00:00:00"
    end = f"{end} 24:00:00"
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            "SELECT * FROM clean_bond_quote "
            f"where symbol in {symbol_sql} and trade_date>='{start}' "
            f"and trade_date<='{end}'"
        )
    else:
        sql_query = (
            "SELECT * FROM clean_bond_quote "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    return pd.read_sql_query(sql_query, engine)


def fetch_bond_min(symbol, start, end, engine=DATABASE2):
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            "SELECT * FROM clean_execreport_1min "
            f"where symbol in {symbol_sql} and trade_date>='{start}' "
            f"and trade_date<='{end}'"
        )
    else:
        sql_query = (
            "SELECT * FROM clean_execreport_1min "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    data = pd.read_sql_query(sql_query, engine)
    data = _apply_datetime(data, ["trade_date"])
    return data.sort_values("trade_date")


def fetch_realtime_min(symbol, engine=DATABASE2):
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = f"SELECT * FROM realtime_min1 where symbol in {symbol_sql}"
    else:
        sql_query = "SELECT * FROM realtime_min1"
    data = pd.read_sql_query(sql_query, engine)
    data = _apply_datetime(data, ["trade_date"])
    return data.sort_values("trade_date")


def fetch_future_list():
    import re

    sql_query = "SELECT id, symbol, create_time, update_time FROM fitsmqd.csmar_symbol_full"
    data = pd.read_sql_query(sql_query, DATABASE1)
    data = data[data["symbol"].apply(lambda x: "T" in x and "EFP" not in x)].sort_values(
        "symbol"
    )
    data["type"] = data["symbol"].apply(lambda x: re.split(r"(\\d+)", x)[0])
    return data


def fetch_future_day(symbol, start, end, engine=DATABASE2):
    symbol_sql = bond_code2sql_fromat(symbol)
    sql_query = (
        "SELECT * FROM fitsmqd.csmar_cffex_fix_1day "
        f"WHERE symbol in {symbol_sql} and transact_time>='{start}' "
        f"and transact_time<='{end}'"
    )
    return pd.read_sql_query(sql_query, engine)


def fetch_future_min(symbol, start, end, freq="1min", engine=DATABASE2):
    symbol_sql = bond_code2sql_fromat(symbol)
    sql_query = (
        f"SELECT * FROM fitsmqd.csmar_cffex_fix_{freq} "
        f"WHERE symbol in {symbol_sql} and transact_time>='{start}' "
        f"and transact_time<='{end}'"
    )
    return pd.read_sql_query(sql_query, engine)


def fetch_wind_indicators(indicators, start, end, engine=DATABASE2):
    if indicators == "all":
        sql_query = (
            "SELECT * from wind_indicators "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    else:
        indicators_sql = str(indicators).replace("'", "").replace("[", "").replace("]", "")
        sql_query = (
            f"SELECT {indicators_sql} from wind_indicators "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    data = pd.read_sql_query(sql_query, engine)
    return data.drop_duplicates(subset=["trade_date"])


def fetch_cfets_repo_item(start, end, engine=DATABASE2):
    sql_query = (
        "SELECT * FROM cfets_repo_item "
        f"where trade_date>='{start}' and trade_date<='{end}'"
    )
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    data = _apply_datetime(data, ["trade_date"])
    return data


def fetch_cfets_repo_buyback_item(start, end, engine=DATABASE_TEST2, with_new_age: bool = False):
    sql_query = (
        "SELECT * FROM cfets_repo_buyback_item "
        f"where trade_date>='{start}' and trade_date<='{end}'"
    )
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    data = _apply_datetime(data, ["trade_date"])

    # ✅ 你已有：new_industry
    data = _add_new_industry(data)

    # ✅ 新增：货币市场 new_age
    if with_new_age:
        data = _add_new_age_money_market(data, symbol_col="symbol", out_col="new_age")

    return data


def fetch_cfets_repo_buyout_item(start, end, engine=DATABASE_TEST2, with_new_age: bool = True):
    sql_query = (
        "SELECT * FROM cfets_repo_buyout_item "
        f"where trade_date>='{start}' and trade_date<='{end}'"
    )
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    data = _apply_datetime(data, ["trade_date"])

    data = _add_new_industry(data)
    if with_new_age:
        data = _add_new_age_money_market(data, symbol_col="symbol", out_col="new_age")

    return data


def fetch_cfets_credit_item(start, end, engine=DATABASE_TEST2, with_new_age: bool = True):
    sql_query = (
        "SELECT * FROM cfets_credit_item "
        f"where trade_date>='{start}' and trade_date<='{end}'"
    )
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    data = _apply_datetime(data, ["trade_date"])

    data = _add_new_industry(data)
    if with_new_age:
        data = _add_new_age_money_market(data, symbol_col="symbol", out_col="new_age")

    return data



def fetch_cfets_bond_amount(start, end, engine=DATABASE_TEST2, with_new_age: bool = True):
    sql_query = (
        "SELECT * FROM cfets_bond_amount "
        f"where trade_date>='{start}' and trade_date<='{end}'"
    )
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    data = _apply_datetime(data, ["trade_date"])
    data = _add_new_industry(data)
    if with_new_age:
        data = _add_new_age(data)
    return data


def fetch_cfets_credit_side(start, end, engine=DATABASE_TEST2, with_new_age: bool = False):
    sql_query = (
        "SELECT * FROM cfets_credit_side "
        f"where trade_date>='{start}' and trade_date<='{end}'"
    )
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    data = _apply_datetime(data, ["trade_date"])
    data = _add_new_industry(data)
    if with_new_age:
        data = _add_new_age(data)
    return data

def fetch_cfets_repo_side(start, end, engine=DATABASE_TEST2, with_new_age: bool = False):
    sql_query = (
        "SELECT * FROM cfets_repo_side "
        f"where trade_date>='{start}' and trade_date<='{end}'"
    )
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    data = _apply_datetime(data, ["trade_date"])
    data = _add_new_industry(data)
    if with_new_age:
        data = _add_new_age(data)
    return data


def fetch_bond_valuation(symbol, start, end, engine=DATABASE1):
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            "SELECT * FROM bond_valuation "
            f"where symbol in {symbol_sql} and trade_date>='{start}' "
            f"and trade_date<='{end}'"
        )
    else:
        sql_query = (
            "SELECT * FROM bond_valuation "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    return pd.read_sql_query(sql_query, engine)


def fetch_wind_issue(symbol, start="2018-01-01", end="2025-01-01", engine=DATABASE2):
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = (
            "SELECT * FROM wind_issue "
            f"where bond_type in {symbol_sql} and trade_date>='{start}' "
            f"and trade_date<='{end}'"
        )
    else:
        sql_query = (
            "SELECT * FROM wind_issue "
            f"where trade_date>='{start}' and trade_date<='{end}'"
        )
    data = pd.read_sql_query(sql_query, engine)
    data[["issue_amount", "issue_num"]] = data[["issue_amount", "issue_num"]].shift(-1)
    data["net_financing_amount"] = data["issue_amount"] - data["pay_amount"]
    return data.dropna()


def fetch_realtime_bid(symbol="all", vaild_type="vaild", engine=DATABASE_TEST2):
    vaild_type_dict = {"vaild": "1", "invaild": "0", "both": ["1", "0"]}
    _ = bond_code2sql_fromat(vaild_type_dict[vaild_type])
    if symbol != "all":
        symbol_sql = bond_code2sql_fromat(symbol)
        sql_query = f"SELECT * FROM realtime_bid where symbol in {symbol_sql}"
    else:
        sql_query = "SELECT * FROM realtime_bid"
    data = pd.read_sql_query(sql_query, engine)
    return data.drop_duplicates()


def _normalize_since_time(since_time):
    if since_time is None:
        now = datetime.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(since_time, (bytes, bytearray)):
        since_time = since_time.decode("utf-8", errors="ignore")
    s = str(since_time).strip()
    if not s:
        now = datetime.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if re.match(r"^\\d{2}:\\d{2}:\\d{2}$", s):
        s = f"{datetime.now().strftime('%Y-%m-%d')} {s}"
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        dt = pd.to_datetime(s, errors="coerce")
        if pd.isna(dt):
            raise ValueError(f"invalid since_time: {since_time}")
        return dt.to_pydatetime().replace(tzinfo=None)


def fetch_realtime_bid_since(symbols="all", since_time=None, lookback_sec=120, engine=DATABASE_TEST2):
    since_dt = _normalize_since_time(since_time)
    if lookback_sec:
        since_dt = since_dt - timedelta(seconds=int(lookback_sec))
    since_str = since_dt.strftime("%Y-%m-%d %H:%M:%S")
    if symbols != "all":
        symbol_sql = bond_code2sql_fromat(symbols)
        sql_query = (
            "SELECT * FROM realtime_bid "
            f"where trade_date>='{since_str}' and symbol in {symbol_sql}"
        )
    else:
        sql_query = f"SELECT * FROM realtime_bid where trade_date>='{since_str}'"
    data = pd.read_sql_query(sql_query, engine).drop_duplicates()
    if "trade_date" in data.columns:
        data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce").dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    return data
