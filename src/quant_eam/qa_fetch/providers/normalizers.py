from __future__ import annotations

from typing import Any

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore[assignment]


def normalize_fetch_output(value: Any) -> dict[str, Any]:
    if value is None:
        return {
            "type": "NoneType",
            "rows": 0,
            "columns": [],
            "dtypes": {},
            "data": None,
        }

    if pd is not None and isinstance(value, pd.DataFrame):
        return {
            "type": "DataFrame",
            "rows": int(len(value)),
            "columns": [str(c) for c in value.columns],
            "dtypes": {str(k): str(v) for k, v in value.dtypes.items()},
            "data": value,
        }

    data_attr = getattr(value, "data", None)
    if pd is not None and isinstance(data_attr, pd.DataFrame):
        return {
            "type": type(value).__name__,
            "rows": int(len(data_attr)),
            "columns": [str(c) for c in data_attr.columns],
            "dtypes": {str(k): str(v) for k, v in data_attr.dtypes.items()},
            "data": data_attr,
        }

    try:
        size = int(len(value))
    except Exception:
        size = 1
    return {
        "type": type(value).__name__,
        "rows": size,
        "columns": [],
        "dtypes": {},
        "data": value,
    }

