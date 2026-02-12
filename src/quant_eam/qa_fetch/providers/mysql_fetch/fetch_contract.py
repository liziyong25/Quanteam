from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class ContractCheck:
    name: str
    ok: bool
    detail: str | None = None


def validate_fetch_frame(
    df: pd.DataFrame,
    *,
    required_columns: Iterable[str] = (),
    datetime_columns: Iterable[str] = ("trade_date",),
    allow_empty: bool = True,
) -> list[ContractCheck]:
    checks: list[ContractCheck] = []

    if df is None:
        return [ContractCheck(name="df_not_none", ok=False, detail="df is None")]

    if (not allow_empty) and df.empty:
        checks.append(ContractCheck(name="df_not_empty", ok=False, detail="df is empty"))
        return checks

    missing = [c for c in required_columns if c not in df.columns]
    checks.append(
        ContractCheck(
            name="required_columns_present",
            ok=(len(missing) == 0),
            detail=None if not missing else f"missing={missing}",
        )
    )

    for col in datetime_columns:
        if col not in df.columns:
            checks.append(ContractCheck(name=f"{col}_present", ok=False, detail="missing"))
            continue
        parsed = pd.to_datetime(df[col], errors="coerce")
        nulls = int(parsed.isna().sum())
        checks.append(ContractCheck(name=f"{col}_parseable", ok=(nulls == 0), detail=f"nulls={nulls}"))

    return checks

