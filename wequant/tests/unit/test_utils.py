from __future__ import annotations

from wequant.utils.codes import normalize_stock_code, code_to_list
from wequant.utils.dates import ensure_date_str, date_stamp, date_valid


def test_normalize_stock_code():
    assert normalize_stock_code("1") == "000001"
    assert normalize_stock_code("000001") == "000001"
    assert normalize_stock_code("SH600000") == "600000"
    assert normalize_stock_code("600000.SH") == "600000"
    assert normalize_stock_code("SHSE.600000") == "600000"


def test_code_to_list_auto_fill():
    assert code_to_list("1") == ["000001"]
    assert code_to_list(["1", "2"]) == ["000001", "000002"]
    assert code_to_list(["rb2001"], auto_fill=False) == ["rb2001"]


def test_date_helpers():
    assert date_valid("2020-01-01") is True
    assert ensure_date_str("2020-01-01") == "2020-01-01"
    assert isinstance(date_stamp("2020-01-01"), float)
