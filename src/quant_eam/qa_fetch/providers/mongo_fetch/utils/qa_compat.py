from __future__ import annotations

from typing import Any

from .codes import code_to_list
from .dates import (
    date_valid,
    date_stamp,
    time_stamp,
    date_str2int,
    date_int2str,
    datetime_to_strdate,
    add_months,
    get_between_quarter,
    get_next_day,
    get_real_date,
)
from .transform import to_json_records_from_pandas


def QA_util_code_tolist(code, auto_fill: bool = True):
    return code_to_list(code, auto_fill=auto_fill)


def QA_util_date_valid(date_str_value: str) -> bool:
    return date_valid(date_str_value)


def QA_util_date_stamp(date_value) -> float:
    return date_stamp(date_value)


def QA_util_time_stamp(time_value) -> float:
    return time_stamp(time_value)


def QA_util_date_str2int(date_str_value) -> int:
    return date_str2int(date_str_value)


def QA_util_date_int2str(int_date) -> str:
    return date_int2str(int_date)


def QA_util_to_json_from_pandas(df):
    return to_json_records_from_pandas(df)


def QA_util_log_info(message: Any, ui_log=None):
    # ui_log compatibility is ignored in wequant
    print(message)


def QA_util_datetime_to_strdate(dt):
    return datetime_to_strdate(dt)


def QA_util_add_months(dt, months: int):
    return add_months(dt, months)


def QA_util_getBetweenQuarter(start: str, end: str):
    return get_between_quarter(start, end)


def QA_util_get_next_day(date, n: int = 1):
    return get_next_day(date, n)


def QA_util_get_real_date(date, trade_list=None, towards: int = -1):
    return get_real_date(date, trade_list=trade_list, towards=towards)


def QA_util_dict_remove_key(data: dict, key: str):
    if isinstance(data, dict) and key in data:
        data.pop(key, None)
    return data
