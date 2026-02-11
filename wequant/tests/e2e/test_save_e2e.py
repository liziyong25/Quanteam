from __future__ import annotations

import os
import sys
import logging
import pytest

from wequant.mongo import get_db
from wequant.wesu import (
    QA_SU_save_single_stock_day,
    QA_SU_save_single_future_day,
    QA_SU_save_single_etf_day,
    QA_SU_save_stock_list,
    QA_SU_save_future_list,
    QA_SU_save_etf_list,
)
from .sample_codes import sample_codes


if os.getenv("WEQUANT_E2E") != "1":
    pytest.skip("WEQUANT_E2E is not set", allow_module_level=True)


logging.getLogger("pymongo").setLevel(logging.WARNING)


def _ensure_mongo():
    from pymongo import MongoClient
    from wequant.config import load_mongo_config

    cfg = load_mongo_config()
    client = MongoClient(cfg.uri, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        pytest.skip(f"mongo not reachable: {exc}")


_ensure_mongo()


def _ensure_test_db():
    db_name = os.getenv("WEQUANT_DB_NAME", "")
    if not db_name or db_name == "quantaxis":
        pytest.skip("WEQUANT_DB_NAME is not set to a test database")


def _ensure_quantaxis():
    qa_path = os.getenv("WEQUANT_QA_PATH")
    if qa_path:
        sys.path.insert(0, qa_path)
        if qa_path.endswith("QUANTAXIS"):
            parent = os.path.dirname(qa_path)
            if parent and parent not in sys.path:
                sys.path.insert(0, parent)
        import types
        if "QUANTAXIS" not in sys.modules:
            pkg_dir = qa_path if qa_path.endswith("QUANTAXIS") else os.path.join(qa_path, "QUANTAXIS")
            if os.path.isdir(pkg_dir):
                mod = types.ModuleType("QUANTAXIS")
                mod.__path__ = [pkg_dir]
                sys.modules["QUANTAXIS"] = mod
    import pandas as pd
    if not getattr(pd, "_wequant_qmar_patch", False):
        _orig = pd.date_range

        def _patched(*args, **kwargs):
            if kwargs.get("freq") == "Q-MAR":
                kwargs["freq"] = "QE-MAR"
            return _orig(*args, **kwargs)

        pd.date_range = _patched
        pd._wequant_qmar_patch = True
    try:
        import QUANTAXIS  # noqa: F401
    except Exception as exc:
        pytest.skip(f"QUANTAXIS import failed: {exc}")


def test_save_stock_day_idempotent():
    _ensure_test_db()
    _ensure_quantaxis()
    codes = sample_codes("stock")
    if not codes:
        pytest.skip("no sample stock codes")
    code = codes[0]
    db = get_db()
    coll = db["stock_day"]
    if coll.find_one({"code": code}, {"_id": 1}) is None:
        pytest.skip("no existing stock_day data for sampled code")
    before = coll.count_documents({"code": code})
    QA_SU_save_single_stock_day(code=code)
    mid = coll.count_documents({"code": code})
    QA_SU_save_single_stock_day(code=code)
    after = coll.count_documents({"code": code})
    assert mid == after
    assert after >= before


def test_save_future_day_idempotent():
    _ensure_test_db()
    _ensure_quantaxis()
    codes = sample_codes("future")
    if not codes:
        pytest.skip("no sample future codes")
    code = codes[0]
    db = get_db()
    coll = db["future_day"]
    if coll.find_one({"code": code}, {"_id": 1}) is None:
        pytest.skip("no existing future_day data for sampled code")
    before = coll.count_documents({"code": code})
    QA_SU_save_single_future_day(code=code)
    mid = coll.count_documents({"code": code})
    QA_SU_save_single_future_day(code=code)
    after = coll.count_documents({"code": code})
    assert mid == after
    assert after >= before


def test_save_etf_day_idempotent():
    _ensure_test_db()
    _ensure_quantaxis()
    codes = sample_codes("etf")
    if not codes:
        pytest.skip("no sample etf codes")
    code = codes[0]
    db = get_db()
    coll = db["index_day"]
    if coll.find_one({"code": code}, {"_id": 1}) is None:
        pytest.skip("no existing index_day data for sampled etf code")
    before = coll.count_documents({"code": code})
    QA_SU_save_single_etf_day(code=code)
    mid = coll.count_documents({"code": code})
    QA_SU_save_single_etf_day(code=code)
    after = coll.count_documents({"code": code})
    assert mid == after
    assert after >= before


def test_save_stock_adj_idempotent():
    _ensure_test_db()
    pytest.skip("stock_adj save not migrated in QASU subset")


def test_save_stock_list_idempotent():
    _ensure_test_db()
    _ensure_quantaxis()
    db = get_db()
    coll = db["stock_list"]
    before = coll.count_documents({})
    QA_SU_save_stock_list()
    mid = coll.count_documents({})
    QA_SU_save_stock_list()
    after = coll.count_documents({})
    assert mid == after
    assert after >= 0


def test_save_future_list_idempotent():
    _ensure_test_db()
    _ensure_quantaxis()
    db = get_db()
    coll = db["future_list"]
    before = coll.count_documents({})
    QA_SU_save_future_list()
    mid = coll.count_documents({})
    QA_SU_save_future_list()
    after = coll.count_documents({})
    assert mid == after
    assert after >= 0


def test_save_etf_list_idempotent():
    _ensure_test_db()
    _ensure_quantaxis()
    db = get_db()
    coll = db["etf_list"]
    before = coll.count_documents({})
    QA_SU_save_etf_list()
    mid = coll.count_documents({})
    QA_SU_save_etf_list()
    after = coll.count_documents({})
    assert mid == after
    assert after >= 0
