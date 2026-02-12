from __future__ import annotations

import pandas as pd


class BaseDataStruct:
    """Minimal QUANTAXIS-like DataStruct wrapper."""

    def __init__(self, data: pd.DataFrame, if_fq: str = "bfq"):
        self.if_fq = if_fq
        if data is None:
            self.data = None
            return
        df = data.copy()
        if "volume" not in df.columns:
            if "vol" in df.columns:
                df["volume"] = df["vol"]
            elif "trade" in df.columns:
                df["volume"] = df["trade"]
        self.data = df.drop_duplicates().sort_index()

    def new(self, data: pd.DataFrame, if_fq: str | None = None):
        return self.__class__(data, if_fq=if_fq or self.if_fq)

    def _index_to_series(self, name: str):
        if self.data is None:
            return None
        idx = self.data.index
        if isinstance(idx, pd.MultiIndex):
            if name in idx.names:
                return idx.get_level_values(name)
            if name in ("date", "datetime") and idx.nlevels >= 1:
                return idx.get_level_values(0)
            if name == "code" and idx.nlevels >= 2:
                return idx.get_level_values(1)
            return idx.get_level_values(0)
        if name in ("date", "datetime"):
            return idx
        if name == "code" and "code" in self.data.columns:
            return self.data["code"]
        return None

    def _ensure_date_code_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "date" not in out.columns:
            date_idx = self._index_to_series("date")
            if date_idx is not None:
                out["date"] = pd.to_datetime(date_idx)
        if "code" not in out.columns:
            code_idx = self._index_to_series("code")
            if code_idx is not None:
                out["code"] = code_idx
        return out

    def _ensure_datetime_code_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "datetime" not in out.columns:
            dt_idx = self._index_to_series("datetime")
            if dt_idx is not None:
                out["datetime"] = pd.to_datetime(dt_idx)
        if "code" not in out.columns:
            code_idx = self._index_to_series("code")
            if code_idx is not None:
                out["code"] = code_idx
        return out

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(rows={0 if self.data is None else len(self.data)})"

    def __len__(self):
        return 0 if self.data is None else len(self.data)

    def to_pandas(self) -> pd.DataFrame:
        return self.data

    def __getattr__(self, item):
        # delegate to dataframe for convenience
        if hasattr(self.data, item):
            return getattr(self.data, item)
        raise AttributeError(item)

    def to_qfq(self):
        # placeholder for compatibility
        return self

    def to_hfq(self):
        # placeholder for compatibility
        return self
