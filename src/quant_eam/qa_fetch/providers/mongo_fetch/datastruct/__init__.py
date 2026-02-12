from __future__ import annotations

import pandas as pd

from .base import BaseDataStruct


def _select_columns(df, columns):
    if df is None:
        return df
    return df.loc[:, columns]


class QA_DataStruct_Stock_day(BaseDataStruct):
    def __init__(self, data, if_fq: str = "bfq"):
        super().__init__(data, if_fq=if_fq)

    def to_qfq(self):
        if self.data is None:
            return self
        if self.if_fq == "qfq":
            return self
        df = self.data.copy()
        if not isinstance(df.index, pd.MultiIndex) or df.index.nlevels < 2:
            # Not an ADV-style multi-index frame; leave unchanged.
            return self

        # QUANTAXIS DataStruct uses (date, code) index and does NOT keep date/code as columns.
        date_level = "date" if "date" in df.index.names else df.index.names[0]
        code_level = "code" if "code" in df.index.names else df.index.names[1]
        dates = pd.to_datetime(df.index.get_level_values(date_level))
        codes = df.index.get_level_values(code_level).astype(str)
        if len(codes) == 0:
            return self

        df.index = pd.MultiIndex.from_arrays([dates, codes], names=["date", "code"])
        start = dates.min().strftime("%Y-%m-%d")
        end = dates.max().strftime("%Y-%m-%d")
        code_list = sorted(set(codes))
        from ..wefetch.adj import fetch_stock_adj

        adj = fetch_stock_adj(code_list, start, end, format="pd")
        if adj is None or len(adj) == 0:
            return self
        adj = adj.copy()
        adj["date"] = pd.to_datetime(adj["date"])
        adj["code"] = adj["code"].astype(str)
        adj = adj.set_index(["date", "code"])

        data = df.join(adj, how="left")
        if "adj" in data.columns:
            data["adj"] = data["adj"].ffill()
            for col in ["open", "high", "low", "close"]:
                if col in data.columns:
                    data[col] = data[col] * data["adj"]
            if "high_limit" in data.columns:
                data["high_limit"] = data["high_limit"] * data["adj"]
            if "low_limit" in data.columns:
                data["low_limit"] = data["low_limit"] * data["adj"]
        return self.new(data, if_fq="qfq")

    def to_hfq(self):
        if self.data is None:
            return self
        if self.if_fq == "hfq":
            return self
        # minimal: reuse qfq implementation as a placeholder
        return self.to_qfq()


class QA_DataStruct_DK_day(BaseDataStruct):
    """DK day DataStruct with optional qfq/hfq adjustment on R/L values.

    Uses stock adjustment factors from `stock_adj` and applies them to:
    - R_value
    - L_value

    Join key is `base_code` (preferred) or `code.split('.')[0]`.
    """

    def __init__(self, data, if_fq: str = "bfq"):
        super().__init__(data, if_fq=if_fq)

    def to_qfq(self):
        if self.data is None:
            return self
        if self.if_fq == "qfq":
            return self

        df = self.data.copy()
        if not isinstance(df.index, pd.MultiIndex) or df.index.nlevels < 2:
            return self

        date_level = "date" if "date" in df.index.names else df.index.names[0]
        code_level = "code" if "code" in df.index.names else df.index.names[1]
        dates = pd.to_datetime(df.index.get_level_values(date_level))
        codes = df.index.get_level_values(code_level).astype(str)
        if len(codes) == 0:
            return self

        # Normalize index names
        df.index = pd.MultiIndex.from_arrays([dates, codes], names=["date", "code"])

        u = df.reset_index()
        if "base_code" not in u.columns:
            u["base_code"] = u["code"].astype(str).str.split(".").str[0]
        u["base_code"] = u["base_code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        u["date"] = pd.to_datetime(u["date"])

        base_codes = sorted({c for c in u["base_code"].tolist() if c and c != "nan"})
        if not base_codes:
            return self

        start = pd.to_datetime(u["date"]).min().strftime("%Y-%m-%d")
        end = pd.to_datetime(u["date"]).max().strftime("%Y-%m-%d")
        from ..wefetch.adj import fetch_stock_adj

        adj = fetch_stock_adj(base_codes, start, end, format="pd")
        if adj is None or len(adj) == 0:
            return self
        adj = adj.copy()
        adj["date"] = pd.to_datetime(adj["date"])
        adj["code"] = adj["code"].astype(str)
        adj = adj.set_index(["date", "code"])

        u = u.set_index(["date", "base_code"], drop=False)
        data = u.join(adj[["adj"]], how="left")
        if "adj" not in data.columns:
            return self
        data["adj"] = data.groupby("base_code", sort=False)["adj"].ffill()

        for col in ["R_value", "L_value"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce") * data["adj"].astype(float)

        data = data.set_index(["date", "code"], drop=True)
        return self.new(data, if_fq="qfq")

    def to_hfq(self):
        if self.data is None:
            return self
        if self.if_fq == "hfq":
            return self
        # minimal: reuse qfq implementation as a placeholder
        return self.to_qfq()


class QA_DataStruct_Stock_min(BaseDataStruct):
    def __init__(self, data, if_fq: str = "bfq"):
        super().__init__(data, if_fq=if_fq)
        if self.data is None:
            return
        if "preclose" in self.data.columns:
            cols = ["open", "high", "low", "close", "volume", "amount", "preclose", "type"]
        else:
            cols = ["open", "high", "low", "close", "volume", "amount", "type"]
        self.data = _select_columns(self.data, cols).sort_index()

    def to_qfq(self):
        if self.data is None:
            return self
        if self.if_fq == "qfq":
            return self
        df = self.data.copy()
        if not isinstance(df.index, pd.MultiIndex) or df.index.nlevels < 2:
            return self

        dt_level = "datetime" if "datetime" in df.index.names else df.index.names[0]
        code_level = "code" if "code" in df.index.names else df.index.names[1]
        dts = pd.to_datetime(df.index.get_level_values(dt_level))
        codes = df.index.get_level_values(code_level).astype(str)
        if len(codes) == 0:
            return self

        # Match QUANTAXIS: create a date column (used only for joining adj),
        # join on (date, code), then restore (datetime, code) index WITHOUT keeping
        # datetime/code as columns.
        u = df.reset_index()
        if "datetime" not in u.columns:
            u = u.rename(columns={dt_level: "datetime"})
        if "code" not in u.columns:
            u = u.rename(columns={code_level: "code"})
        u["date"] = pd.to_datetime(u["datetime"]).dt.date

        code_list = sorted(set(u["code"].astype(str)))
        start = pd.to_datetime(u["date"]).min().strftime("%Y-%m-%d")
        end = pd.to_datetime(u["date"]).max().strftime("%Y-%m-%d")
        from ..wefetch.adj import fetch_stock_adj

        adj = fetch_stock_adj(code_list, start, end, format="pd")
        if adj is None or len(adj) == 0:
            return self
        adj = adj.copy()
        adj["date"] = pd.to_datetime(adj["date"]).dt.date
        adj["code"] = adj["code"].astype(str)
        adj = adj.set_index(["date", "code"])

        u = u.set_index(["date", "code"], drop=False)
        data = u.join(adj, how="left").set_index(["datetime", "code"])
        if "adj" in data.columns:
            data["adj"] = data["adj"].ffill()
            for col in ["open", "high", "low", "close"]:
                if col in data.columns:
                    data[col] = data[col] * data["adj"]
        return self.new(data, if_fq="qfq")

    def to_hfq(self):
        if self.data is None:
            return self
        if self.if_fq == "hfq":
            return self
        return self.to_qfq()


class QA_DataStruct_Index_day(BaseDataStruct):
    def __init__(self, data, if_fq: str = "bfq"):
        super().__init__(data, if_fq=if_fq)


class QA_DataStruct_Index_min(BaseDataStruct):
    def __init__(self, data, if_fq: str = "bfq"):
        super().__init__(data, if_fq=if_fq)
        if self.data is None:
            return
        if "preclose" in self.data.columns:
            cols = ["open", "high", "low", "close", "volume", "amount", "preclose", "type"]
        else:
            cols = ["open", "high", "low", "close", "volume", "amount", "type"]
        self.data = _select_columns(self.data, cols).sort_index()


class QA_DataStruct_Future_day(BaseDataStruct):
    def __init__(self, data, if_fq: str = "bfq"):
        super().__init__(data, if_fq=if_fq)
        if self.data is None:
            return
        cols = ["open", "high", "low", "close", "volume", "position", "price"]
        self.data = _select_columns(self.data, cols).sort_index()


class QA_DataStruct_Future_min(BaseDataStruct):
    def __init__(self, data, if_fq: str = "bfq"):
        super().__init__(data, if_fq=if_fq)
        if self.data is None:
            return
        cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "position",
            "price",
            "tradetime",
            "type",
        ]
        self.data = _select_columns(self.data, cols).sort_index()


class QA_DataStruct_Stock_block(BaseDataStruct):
    pass


class QA_DataStruct_Financial(BaseDataStruct):
    pass


class QA_DataStruct_CryptoCurrency_day(BaseDataStruct):
    pass


class QA_DataStruct_CryptoCurrency_min(BaseDataStruct):
    pass


class QA_DataStruct_Stock_transaction(BaseDataStruct):
    pass


class QA_DataStruct_Index_transaction(BaseDataStruct):
    pass
