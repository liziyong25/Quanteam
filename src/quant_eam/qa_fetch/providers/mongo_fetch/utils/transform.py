from __future__ import annotations

import json
import pandas as pd

def to_json_records_from_pandas(df: pd.DataFrame):
    """Convert pandas DataFrame to list[dict] with date/datetime as str (QA compatible)."""
    if df is None:
        return []
    data = df.copy()
    if "datetime" in data.columns:
        data["datetime"] = data["datetime"].apply(str)
    if "date" in data.columns:
        data["date"] = data["date"].apply(str)
    return json.loads(data.to_json(orient="records"))
