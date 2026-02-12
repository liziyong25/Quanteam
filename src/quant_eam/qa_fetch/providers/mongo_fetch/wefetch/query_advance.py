from __future__ import annotations

import datetime
import re
from typing import Any

import pandas as pd
import pymongo
from pandas import DataFrame

from ..mongo import get_db
from ..utils.dates import month_data
from ..datastruct import (
    QA_DataStruct_Index_day,
    QA_DataStruct_Index_min,
    QA_DataStruct_Future_day,
    QA_DataStruct_Future_min,
    QA_DataStruct_Stock_block,
    QA_DataStruct_Financial,
    QA_DataStruct_Stock_day,
    QA_DataStruct_Stock_min,
    QA_DataStruct_DK_day,
    QA_DataStruct_CryptoCurrency_day,
    QA_DataStruct_CryptoCurrency_min,
    QA_DataStruct_Stock_transaction,
    QA_DataStruct_Index_transaction,
)
from .query import (
    fetch_index_day,
    fetch_index_min,
    fetch_index_transaction,
    fetch_stock_day,
    fetch_stock_full,
    fetch_stock_min,
    fetch_stock_transaction,
    fetch_future_day,
    fetch_future_min,
    fetch_financial_report,
    fetch_stock_list,
    fetch_index_list,
    fetch_future_list,
    fetch_stock_financial_calendar,
    fetch_stock_divyield,
    fetch_stock_dk,
    fetch_etf_dk,
    fetch_index_dk,
    fetch_lof_dk,
    fetch_reits_dk,
    fetch_future_dk,
    fetch_hkstock_dk,
    fetch_cryptocurrency_day,
    fetch_cryptocurrency_min,
    fetch_cryptocurrency_list,
)


def _get_collection(name: str, collections):
    if collections is None:
        return get_db()[name]
    return collections


# === QAQuery_Advance functions ===


def fetch_option_day_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return None


def fetch_stock_day_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    end = start if end is None else end
    start = str(start)[0:10]
    end = str(end)[0:10]

    if start == "all":
        start = "1990-01-01"
        end = str(datetime.date.today())

    res = fetch_stock_day(code, start, end, format="pd", collections=collections)
    if res is None:
        print(
            "WEFetch error fetch_stock_day_adv parameter code=%s , start=%s, end=%s call fetch_stock_day return None"
            % (code, start, end)
        )
        return None

    res_reset_index = res.set_index(["date", "code"], drop=if_drop_index)
    return QA_DataStruct_Stock_day(res_reset_index)


def fetch_stock_min_adv(
    code,
    start,
    end=None,
    frequence="1min",
    if_drop_index=True,
    collections=None,
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"
    else:
        print(
            "WEFetch error fetch_stock_min_adv parameter frequence=%s is none of 1min 1m 5min 5m 15min 15m 30min 30m 60min 60m"
            % frequence
        )
        return None

    end = start if end is None else end
    if len(start) == 10:
        start = f"{start} 09:30:00"

    if len(end) == 10:
        end = f"{end} 15:00:00"

    if start == end:
        print(
            "WEFetch error fetch_stock_min_adv parameter code=%s , start=%s, end=%s is equal, should have time span! "
            % (code, start, end)
        )
        return None

    res = fetch_stock_min(
        code, start, end, format="pd", frequence=frequence, collections=collections
    )
    if res is None:
        print(
            "WEFetch error fetch_stock_min_adv parameter code=%s , start=%s, end=%s frequence=%s call fetch_stock_min return None"
            % (code, start, end, frequence)
        )
        return None

    res_set_index = res.set_index(["datetime", "code"], drop=if_drop_index)
    return QA_DataStruct_Stock_min(res_set_index)


def fetch_stock_day_full_adv(date):
    res = fetch_stock_full(date, "pd")
    if res is None:
        print(
            "WEFetch error fetch_stock_day_full_adv parameter date=%s call fetch_stock_full return None"
            % (date)
        )
        return None

    res_set_index = res.set_index(["date", "code"])
    return QA_DataStruct_Stock_day(res_set_index)


def _fetch_dk_day_adv(
    fetch_fn,
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
    *,
    fn_name: str,
):
    end = start if end is None else end
    start = str(start)[0:10]
    end = str(end)[0:10]

    if start == "all":
        start = "1990-01-01"
        end = str(datetime.date.today())

    res = fetch_fn(code, start, end, format="pd", collections=collections)
    if res is None:
        print(
            "WEFetch error %s parameter code=%s , start=%s, end=%s call fetch_*_dk return None"
            % (fn_name, code, start, end)
        )
        return None

    if "date" not in res.columns:
        if "trade_date" in res.columns:
            res = res.assign(date=pd.to_datetime(res["trade_date"]))
        elif "datetime" in res.columns:
            res = res.assign(date=pd.to_datetime(res["datetime"]))
        else:
            return None

    res_set_index = res.set_index(["date", "code"], drop=if_drop_index)
    return QA_DataStruct_DK_day(res_set_index)


def fetch_stock_dk_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return _fetch_dk_day_adv(
        fetch_stock_dk,
        code,
        start=start,
        end=end,
        if_drop_index=if_drop_index,
        collections=collections,
        fn_name="fetch_stock_dk_adv",
    )


def fetch_etf_dk_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return _fetch_dk_day_adv(
        fetch_etf_dk,
        code,
        start=start,
        end=end,
        if_drop_index=if_drop_index,
        collections=collections,
        fn_name="fetch_etf_dk_adv",
    )


def fetch_index_dk_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return _fetch_dk_day_adv(
        fetch_index_dk,
        code,
        start=start,
        end=end,
        if_drop_index=if_drop_index,
        collections=collections,
        fn_name="fetch_index_dk_adv",
    )


def fetch_lof_dk_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return _fetch_dk_day_adv(
        fetch_lof_dk,
        code,
        start=start,
        end=end,
        if_drop_index=if_drop_index,
        collections=collections,
        fn_name="fetch_lof_dk_adv",
    )


def fetch_reits_dk_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return _fetch_dk_day_adv(
        fetch_reits_dk,
        code,
        start=start,
        end=end,
        if_drop_index=if_drop_index,
        collections=collections,
        fn_name="fetch_reits_dk_adv",
    )


def fetch_future_dk_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return _fetch_dk_day_adv(
        fetch_future_dk,
        code,
        start=start,
        end=end,
        if_drop_index=if_drop_index,
        collections=collections,
        fn_name="fetch_future_dk_adv",
    )


def fetch_hkstock_dk_adv(
    code,
    start="all",
    end=None,
    if_drop_index=True,
    collections=None,
):
    return _fetch_dk_day_adv(
        fetch_hkstock_dk,
        code,
        start=start,
        end=end,
        if_drop_index=if_drop_index,
        collections=collections,
        fn_name="fetch_hkstock_dk_adv",
    )


def fetch_index_day_adv(
    code,
    start,
    end=None,
    if_drop_index=True,
    collections=None,
):
    end = start if end is None else end
    start = str(start)[0:10]
    end = str(end)[0:10]

    res = fetch_index_day(code, start, end, format="pd", collections=collections)
    if res is None:
        print(
            "WEFetch error fetch_index_day_adv parameter code=%s start=%s end=%s call fetch_index_day return None"
            % (code, start, end)
        )
        return None

    res_set_index = res.set_index(["date", "code"], drop=if_drop_index)
    return QA_DataStruct_Index_day(res_set_index)


def fetch_index_min_adv(
    code,
    start,
    end=None,
    frequence="1min",
    if_drop_index=True,
    collections=None,
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"

    end = start if end is None else end
    if len(start) == 10:
        start = f"{start} 09:30:00"
    if len(end) == 10:
        end = f"{end} 15:00:00"

    res = fetch_index_min(
        code, start, end, format="pd", frequence=frequence, collections=collections
    )
    if res is None:
        print(
            "WEFetch error fetch_index_min_adv parameter code=%s start=%s end=%s frequence=%s call fetch_index_min return None"
            % (code, start, end, frequence)
        )
        return None

    res_reset_index = res.set_index(["datetime", "code"], drop=if_drop_index)
    return QA_DataStruct_Index_min(res_reset_index)


def fetch_stock_transaction_adv(
    code,
    start,
    end=None,
    frequence="tick",
    if_drop_index=True,
    collections=None,
):
    end = start if end is None else end
    if len(start) == 10:
        start = f"{start} 09:30:00"

    if len(end) == 10:
        end = f"{end} 15:00:00"

    if start == end:
        print(
            "WEFetch error fetch_stock_transaction_adv parameter code=%s , start=%s, end=%s is equal, should have time span! "
            % (code, start, end)
        )
        return None

    res = fetch_stock_transaction(
        code, start, end, format="pd", frequence=frequence, collections=collections
    )
    if res is None:
        print(
            "WEFetch error fetch_stock_transaction_adv parameter code=%s , start=%s, end=%s frequence=%s call fetch_stock_transaction return None"
            % (code, start, end, frequence)
        )
        return None

    res_set_index = res.set_index(["datetime", "code"], drop=if_drop_index)
    return QA_DataStruct_Stock_transaction(res_set_index)


def fetch_index_transaction_adv(
    code,
    start,
    end=None,
    frequence="tick",
    if_drop_index=True,
    collections=None,
):
    end = start if end is None else end
    if len(start) == 10:
        start = f"{start} 09:30:00"

    if len(end) == 10:
        end = f"{end} 15:00:00"

    if start == end:
        print(
            "WEFetch error fetch_index_transaction_adv parameter code=%s , start=%s, end=%s is equal, should have time span! "
            % (code, start, end)
        )
        return None

    res = fetch_index_transaction(
        code, start, end, format="pd", frequence=frequence, collections=collections
    )
    if res is None:
        print(
            "WEFetch error fetch_index_transaction_adv parameter code=%s , start=%s, end=%s frequence=%s call fetch_index_transaction return None"
            % (code, start, end, frequence)
        )
        return None

    res_set_index = res.set_index(["datetime", "code"], drop=if_drop_index)
    return QA_DataStruct_Index_transaction(res_set_index)


def fetch_stock_list_adv(collections=None):
    stock_list_items = fetch_stock_list(collections=collections)
    if len(stock_list_items) == 0:
        print(
            "WEFetch error fetch_stock_list_adv call item for item in collections.find() return 0 item, maybe the stock_list is empty!"
        )
        return None
    return stock_list_items


def fetch_index_list_adv(collections=None):
    index_list_items = fetch_index_list(collections=collections)
    if len(index_list_items) == 0:
        print(
            "WEFetch error fetch_index_list_adv call item for item in collections.find() return 0 item, maybe the index_list is empty!"
        )
        return None
    return index_list_items


def fetch_future_day_adv(
    code,
    start,
    end=None,
    if_drop_index=True,
    collections=None,
):
    end = start if end is None else end
    start = str(start)[0:10]
    end = str(end)[0:10]

    res = fetch_future_day(code, start, end, format="pd", collections=collections)
    if res is None:
        print(
            "WEFetch error fetch_future_day_adv parameter code=%s start=%s end=%s call fetch_future_day return None"
            % (code, start, end)
        )
        return None

    res_set_index = res.set_index(["date", "code"])
    return QA_DataStruct_Future_day(res_set_index)


def fetch_future_min_adv(
    code,
    start,
    end=None,
    frequence="1min",
    if_drop_index=True,
    collections=None,
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"

    end = start if end is None else end
    if len(start) == 10:
        start = f"{start} 00:00:00"
    if len(end) == 10:
        end = f"{end} 15:00:00"

    res = fetch_future_min(
        code, start, end, format="pd", frequence=frequence, collections=collections
    )
    if res is None:
        print(
            "WEFetch error fetch_future_min_adv parameter code=%s start=%s end=%s frequence=%s call fetch_future_min return None"
            % (code, start, end, frequence)
        )
        return None

    res_reset_index = res.set_index(["datetime", "code"], drop=if_drop_index)
    return QA_DataStruct_Future_min(res_reset_index)


def fetch_future_list_adv(collections=None):
    future_list_items = fetch_future_list(collections=collections)
    if len(future_list_items) == 0:
        print(
            "WEFetch error fetch_future_list_adv call item for item in collections.find() return 0 item, maybe the future_list is empty!"
        )
        return None
    return future_list_items


def fetch_stock_block_adv(
    code=None,
    blockname=None,
    collections=None,
):
    collections = _get_collection("stock_block", collections)
    if isinstance(blockname, (list,)) and len(blockname) > 0:
        reg_join = "|".join(blockname)
        df = DataFrame(
            [
                i
                for i in collections.aggregate(
                    [
                        {"$match": {"blockname": {"$regex": reg_join}}},
                        {
                            "$group": {
                                "_id": "$code",
                                "count": {"$sum": 1},
                                "blockname": {"$push": "$blockname"},
                            }
                        },
                        {"$match": {"count": {"$gte": len(blockname)}}},
                        {"$project": {"code": "$_id", "blockname": 1, "_id": 0}},
                    ]
                )
            ]
        )
        if not df.empty:
            df.blockname = df.blockname.apply(lambda x: ",".join(x))
        return QA_DataStruct_Stock_block(
            df.set_index(["blockname", "code"], drop=False)
        )
    if code is not None and blockname is None:
        if isinstance(code, str):
            code = [code]
        data = pd.DataFrame(
            [item for item in collections.find({"code": {"$in": code}})]
        )
        if "_id" in data.columns:
            data = data.drop(["_id"], axis=1)

        return QA_DataStruct_Stock_block(
            data.set_index(["blockname", "code"], drop=True).drop_duplicates()
        )
    if blockname is not None and code is None:
        items_from_collections = [
            item for item in collections.find({"blockname": re.compile(blockname)})
        ]
        data = pd.DataFrame(items_from_collections)
        if "_id" in data.columns:
            data = data.drop(["_id"], axis=1)
        data_set_index = data.set_index(["blockname", "code"], drop=True)
        return QA_DataStruct_Stock_block(data_set_index)

    data = pd.DataFrame([item for item in collections.find()])
    if "_id" in data.columns:
        data = data.drop(["_id"], axis=1)
    data_set_index = data.set_index(["blockname", "code"], drop=True)
    return QA_DataStruct_Stock_block(data_set_index)


def fetch_stock_realtime_adv(
    code=None,
    num=1,
    collections=None,
    verbose=True,
):
    if collections is None:
        collections = get_db().get_collection(f"realtime_{datetime.date.today()}")

    if code is None:
        print("WEFetch error fetch_stock_realtime_adv parameter code is None")
        return None

    if isinstance(code, str):
        code = [code]
    elif isinstance(code, list):
        pass
    else:
        print(
            "WEFetch error fetch_stock_realtime_adv parameter code is not List type or String type"
        )

    items_from_collections = [
        item
        for item in collections.find(
            {"code": {"$in": code}},
            limit=num * len(code),
            sort=[("datetime", pymongo.DESCENDING)],
        )
    ]
    if (items_from_collections is None) or (len(items_from_collections) == 0):
        if verbose:
            print(
                "WEFetch error fetch_stock_realtime_adv find parameter code={} num={} collection={} return None".format(
                    code, num, collections
                )
            )
        return None

    data = pd.DataFrame(items_from_collections)
    data_set_index = (
        data.set_index(["datetime", "code"], drop=False)
        .drop(["_id"], axis=1)
    )
    return data_set_index


def fetch_financial_report_adv(code, start, end=None, ltype="EN"):
    if end is None:
        return QA_DataStruct_Financial(fetch_financial_report(code, start, ltype=ltype))

    series = pd.Series(data=month_data, index=pd.to_datetime(month_data), name="date")
    timerange = series.loc[start:end].tolist()
    return QA_DataStruct_Financial(
        fetch_financial_report(code, timerange, ltype=ltype)
    )


def fetch_stock_financial_calendar_adv(
    code,
    start="all",
    end=None,
    format="pd",
    collections=None,
):
    end = start if end is None else end
    start = str(start)[0:10]
    end = str(end)[0:10]

    if start == "all":
        start = "1990-01-01"
        end = str(datetime.date.today())

    if end is None:
        return QA_DataStruct_Financial(
            fetch_stock_financial_calendar(code, start, str(datetime.date.today()))
        )

    series = pd.Series(data=month_data, index=pd.to_datetime(month_data), name="date")
    _timerange = series.loc[start:end].tolist()
    return QA_DataStruct_Financial(fetch_stock_financial_calendar(code, start, end))


def fetch_stock_divyield_adv(
    code,
    start="all",
    end=None,
    format="pd",
    collections=None,
):
    end = start if end is None else end
    start = str(start)[0:10]
    end = str(end)[0:10]

    if start == "all":
        start = "1990-01-01"
        end = str(datetime.date.today())

    if end is None:
        return QA_DataStruct_Financial(
            fetch_stock_divyield(code, start, str(datetime.date.today()))
        )

    series = pd.Series(data=month_data, index=pd.to_datetime(month_data), name="date")
    _timerange = series.loc[start:end].tolist()
    return QA_DataStruct_Financial(fetch_stock_divyield(code, start, end))


def fetch_cryptocurrency_day_adv(
    code,
    start,
    end=None,
    if_drop_index=True,
    collections=None,
):
    end = start if end is None else end
    start = str(start)[0:10]
    end = str(end)[0:10]

    res = fetch_cryptocurrency_day(
        code, start, end, format="pd", collections=collections
    )
    if res is None:
        print(
            "WEFetch error fetch_cryptocurrency_day_adv parameter symbol=%s start=%s end=%s call fetch_cryptocurrency_day return None"
            % (code, start, end)
        )
        return None

    res_set_index = res.set_index(["date", "code"])
    return QA_DataStruct_CryptoCurrency_day(res_set_index)


def fetch_cryptocurrency_min_adv(
    code,
    start,
    end=None,
    frequence="1min",
    if_drop_index=True,
    collections=None,
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"

    end = start if end is None else end
    if len(start) == 10:
        start = f"{start} 00:00:00"
    if len(end) == 10:
        end = f"{end} 23:59:59"

    res = fetch_cryptocurrency_min(
        code, start, end, format="pd", frequence=frequence, collections=collections
    )
    if res is None:
        print(
            "WEFetch error fetch_cryptocurrency_min_adv parameter symbol=%s start=%s end=%s frequence=%s call fetch_cryptocurrency_min return None"
            % (code, start, end, frequence)
        )
        return None

    res_reset_index = res.set_index(["datetime", "code"], drop=if_drop_index)
    return QA_DataStruct_CryptoCurrency_min(res_reset_index)


def fetch_cryptocurrency_list_adv(
    market,
    collections=None,
):
    cryptocurrency_list_items = fetch_cryptocurrency_list(
        market, collections=collections
    )
    if len(cryptocurrency_list_items) == 0:
        print(
            "WEFetch error fetch_cryptocurrency_list_adv call item for item in collections.find() return 0 item, maybe the cryptocurrency_list is empty!"
        )
        return None
    return cryptocurrency_list_items


# QA_ compatibility aliases
QA_fetch_option_day_adv = fetch_option_day_adv
QA_fetch_stock_day_adv = fetch_stock_day_adv
QA_fetch_stock_min_adv = fetch_stock_min_adv
QA_fetch_stock_day_full_adv = fetch_stock_day_full_adv
QA_fetch_stock_dk_adv = fetch_stock_dk_adv
QA_fetch_etf_dk_adv = fetch_etf_dk_adv
QA_fetch_index_dk_adv = fetch_index_dk_adv
QA_fetch_lof_dk_adv = fetch_lof_dk_adv
QA_fetch_reits_dk_adv = fetch_reits_dk_adv
QA_fetch_future_dk_adv = fetch_future_dk_adv
QA_fetch_hkstock_dk_adv = fetch_hkstock_dk_adv
QA_fetch_index_day_adv = fetch_index_day_adv
QA_fetch_index_min_adv = fetch_index_min_adv
QA_fetch_stock_transaction_adv = fetch_stock_transaction_adv
QA_fetch_index_transaction_adv = fetch_index_transaction_adv
QA_fetch_stock_list_adv = fetch_stock_list_adv
QA_fetch_index_list_adv = fetch_index_list_adv
QA_fetch_future_day_adv = fetch_future_day_adv
QA_fetch_future_min_adv = fetch_future_min_adv
QA_fetch_future_list_adv = fetch_future_list_adv
QA_fetch_stock_block_adv = fetch_stock_block_adv
QA_fetch_stock_realtime_adv = fetch_stock_realtime_adv
QA_fetch_financial_report_adv = fetch_financial_report_adv
QA_fetch_stock_financial_calendar_adv = fetch_stock_financial_calendar_adv
QA_fetch_stock_divyield_adv = fetch_stock_divyield_adv
QA_fetch_cryptocurrency_day_adv = fetch_cryptocurrency_day_adv
QA_fetch_cryptocurrency_min_adv = fetch_cryptocurrency_min_adv
QA_fetch_cryptocurrency_list_adv = fetch_cryptocurrency_list_adv
