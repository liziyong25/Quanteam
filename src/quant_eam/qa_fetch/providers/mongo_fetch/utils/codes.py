from __future__ import annotations

from typing import Iterable, List, Union

def normalize_stock_code(code: Union[str, int]) -> str:
    """Normalize stock-like codes to 6-digit strings (QUANTAXIS-compatible)."""
    if isinstance(code, int):
        return f"{code:06d}"
    code = str(code).strip()
    if len(code) == 6 and code.isdigit():
        return code
    if len(code) == 8:
        # e.g. SH600000 -> 600000
        return code[-6:]
    if len(code) == 9:
        # e.g. 600000.SH -> 600000
        return code[:6]
    if len(code) == 11:
        # e.g. SHSE.600000 or 600000.XSHG
        if code[0] in ["S"]:
            return code.split(".")[1]
        return code.split(".")[0]
    if code.isdigit() and len(code) < 6:
        return code.zfill(6)
    return code


def code_to_list(code: Union[str, Iterable[str]], *, auto_fill: bool = True) -> List[str]:
    """Convert code(s) to list; optionally auto-fill stock/ETF codes to 6 digits."""
    if code is None:
        return []
    if isinstance(code, str):
        return [normalize_stock_code(code) if auto_fill else code]
    codes = list(code)
    if auto_fill:
        return [normalize_stock_code(item) for item in codes]
    return [str(item).strip() for item in codes]
