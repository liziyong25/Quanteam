from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


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


def _patch_pandas_qmar():
    if getattr(pd, "_wequant_qmar_patch", False):
        return

    _orig = pd.date_range

    def _patched(*args, **kwargs):
        if kwargs.get("freq") == "Q-MAR":
            kwargs["freq"] = "QE-MAR"
        return _orig(*args, **kwargs)

    pd.date_range = _patched
    pd._wequant_qmar_patch = True


def _ensure_quantaxis_namespace(path: str):
    import types

    if "QUANTAXIS" in sys.modules:
        return
    pkg_dir = path if path.endswith("QUANTAXIS") else os.path.join(path, "QUANTAXIS")
    if not os.path.isdir(pkg_dir):
        pytest.skip(f"WEQUANT_QA_PATH invalid: {path}")
    mod = types.ModuleType("QUANTAXIS")
    mod.__path__ = [pkg_dir]
    sys.modules["QUANTAXIS"] = mod


QA_AVAILABLE = False
QA_IMPORT_ERROR = None
QAQ = None
QAQA = None

qa_path = os.getenv("WEQUANT_QA_PATH")
if not qa_path:
    pytest.skip("WEQUANT_QA_PATH is not set", allow_module_level=True)

try:
    sys.path.insert(0, qa_path)
    if qa_path.endswith("QUANTAXIS"):
        parent = os.path.dirname(qa_path)
        if parent and parent not in sys.path:
            sys.path.insert(0, parent)

    _patch_pandas_qmar()
    _ensure_quantaxis_namespace(qa_path)
    import QUANTAXIS.QAFetch.QAQuery as QAQ  # type: ignore[import-not-found]
    import QUANTAXIS.QAFetch.QAQuery_Advance as QAQA  # type: ignore[import-not-found]

    QA_AVAILABLE = True
except Exception as exc:  # pragma: no cover - environment dependent
    QA_IMPORT_ERROR = exc


FIXTURE_PATH = Path("tests") / "fixtures" / "upstream_functions.json"
FUNC_ITEMS = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_qa_map():
    if not QA_AVAILABLE:
        return {}
    out = {}
    for item in FUNC_ITEMS:
        qa_name = item["name"]
        new_name = qa_name.replace("QA_", "")
        module = QAQA if item["file"].endswith("QAQuery_Advance.py") else QAQ
        out[new_name] = getattr(module, qa_name)
    return out


QA_FUNC_BY_NEW_NAME = _build_qa_map()


def _extract_new_name(cell_src: str) -> str | None:
    for line in cell_src.splitlines():
        if line.startswith("# new:"):
            # e.g. "# new: wequant.wefetch.fetch_stock_day"
            value = line.split(":", 1)[1].strip()
            return value.split(".")[-1]
    return None


NOTEBOOK_PATH = Path("wequant") / "test" / "test_fetch.ipynb"
NOTEBOOK = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


CELL0 = "".join(NOTEBOOK["cells"][0]["source"])
CELL1 = "".join(NOTEBOOK["cells"][1]["source"])


CELL_CASES: list[tuple[int, str]] = []
for idx, cell in enumerate(NOTEBOOK["cells"]):
    if cell.get("cell_type") != "code":
        continue
    src = "".join(cell.get("source", ""))
    name = _extract_new_name(src)
    if name:
        CELL_CASES.append((idx, name))


def _normalize_res(res):
    if hasattr(res, "data"):
        return res.data
    return res


def _compare_frames(df_qa: pd.DataFrame | None, df_we: pd.DataFrame | None, tol=1e-6):
    if df_qa is None:
        assert df_we is None
        return
    assert df_we is not None
    assert set(df_qa.columns) == set(df_we.columns)

    key_candidates = [
        "date",
        "datetime",
        "updateDate",
        "dir_dcl_date",
        "report_date",
        "blockname",
        "code",
        "a_stockcode",
        "symbol",
    ]

    qa = df_qa.copy()
    we = df_we.copy()
    if any(name in key_candidates for name in qa.index.names):
        qa = qa.reset_index(drop=True)
    if any(name in key_candidates for name in we.index.names):
        we = we.reset_index(drop=True)

    key_cols = [c for c in key_candidates if c in qa.columns]
    qa = qa.sort_values(key_cols).reset_index(drop=True) if key_cols else qa.reset_index(drop=True)
    we = we.sort_values(key_cols).reset_index(drop=True) if key_cols else we.reset_index(drop=True)

    for col in key_cols:
        assert qa[col].astype(str).equals(we[col].astype(str))

    numeric_cols = [c for c in qa.columns if pd.api.types.is_numeric_dtype(qa[c])]
    for col in numeric_cols:
        assert np.allclose(
            qa[col].to_numpy(),
            we[col].to_numpy(),
            rtol=tol,
            atol=tol,
            equal_nan=True,
        )

    other_cols = [c for c in qa.columns if c not in numeric_cols and c not in key_cols]
    for col in other_cols:
        assert qa[col].astype(str).equals(we[col].astype(str))


def _compare_list_of_dicts(qa_res, we_res):
    assert isinstance(qa_res, list)
    assert isinstance(we_res, list)
    assert len(qa_res) == len(we_res)
    if not qa_res:
        return
    if not isinstance(qa_res[0], dict):
        assert qa_res == we_res
        return

    candidate_keys = ["code", "symbol", "a_stockcode", "ts_code", "account_cookie", "cookie", "id"]
    key = None
    for k in candidate_keys:
        if all(k in item for item in qa_res) and all(k in item for item in we_res):
            key = k
            break

    if key:
        qa_map = {item[key]: item for item in qa_res}
        we_map = {item[key]: item for item in we_res}
        sample_keys = sorted(set(qa_map).intersection(we_map))[:5]
        for k in sample_keys:
            assert set(qa_map[k].keys()) == set(we_map[k].keys())
            for field in qa_map[k].keys():
                assert str(qa_map[k][field]) == str(we_map[k][field])
        return

    assert set(qa_res[0].keys()) == set(we_res[0].keys())


def _compare_any(qa_res, we_res, *, func_name: str):
    qa_n = _normalize_res(qa_res)
    we_n = _normalize_res(we_res)

    if qa_n is None:
        if we_n is None:
            return
        if func_name == "fetch_hkstock_day":
            # Local hkstock_day does not contain `vol`, but upstream QAQuery expects it.
            pytest.skip("hkstock_day missing `vol` field in Mongo; QUANTAXIS returns None")
        if func_name == "fetch_dk_data":
            # Some deployments store DK data in a different collection and/or use YYYYMMDD for `datetime`.
            # Upstream QUANTAXIS QA_fetch_dk_data can't handle this schema consistently.
            pytest.skip("dk_data schema mismatch; QUANTAXIS returned None")
        pytest.fail(f"{func_name}: QUANTAXIS returned None, wefetch returned {type(we_n).__name__}")

    if we_n is None:
        pytest.fail(f"{func_name}: QUANTAXIS returned {type(qa_n).__name__}, wefetch returned None")

    if isinstance(qa_n, pd.DataFrame):
        assert isinstance(we_n, pd.DataFrame)
        if func_name == "fetch_dk_data" and qa_n.empty and not we_n.empty:
            pytest.skip("dk_data schema mismatch; QUANTAXIS returned empty while wefetch returned data")
        _compare_frames(qa_n, we_n)
        return

    if isinstance(qa_n, np.ndarray):
        assert isinstance(we_n, np.ndarray)
        if np.issubdtype(qa_n.dtype, np.number) and np.issubdtype(we_n.dtype, np.number):
            assert np.allclose(qa_n, we_n, rtol=1e-6, atol=1e-6, equal_nan=True)
        else:
            assert (qa_n.astype(str) == we_n.astype(str)).all()
        return

    if isinstance(qa_n, list):
        assert isinstance(we_n, list)
        _compare_list_of_dicts(qa_n, we_n)
        return

    assert qa_n == we_n


class _DualResult:
    def __init__(self, we_obj, qa_obj, *, func_name: str):
        self._we = we_obj
        self._qa = qa_obj
        self._func_name = func_name

    @property
    def data(self):
        return getattr(self._we, "data", self._we)

    def to_qfq(self, *args, **kwargs):
        if not hasattr(self._we, "to_qfq") or not hasattr(self._qa, "to_qfq"):
            return self
        we2 = self._we.to_qfq(*args, **kwargs)
        try:
            qa2 = self._qa.to_qfq(*args, **kwargs)
        except Exception as exc:
            # QUANTAXIS DataStruct qfq/hfq helpers are not compatible with newer pandas APIs.
            pytest.skip(f"QUANTAXIS to_qfq failed ({type(exc).__name__}): {exc}")
        _compare_any(qa2, we2, func_name=f"{self._func_name}.to_qfq")
        return _DualResult(we2, qa2, func_name=f"{self._func_name}.to_qfq")

    def to_hfq(self, *args, **kwargs):
        if not hasattr(self._we, "to_hfq") or not hasattr(self._qa, "to_hfq"):
            return self
        we2 = self._we.to_hfq(*args, **kwargs)
        try:
            qa2 = self._qa.to_hfq(*args, **kwargs)
        except Exception as exc:
            pytest.skip(f"QUANTAXIS to_hfq failed ({type(exc).__name__}): {exc}")
        _compare_any(qa2, we2, func_name=f"{self._func_name}.to_hfq")
        return _DualResult(we2, qa2, func_name=f"{self._func_name}.to_hfq")

    def __getattr__(self, item):
        return getattr(self._we, item)

    def __repr__(self) -> str:  # pragma: no cover
        return repr(self._we)


@pytest.mark.parametrize("cell_index,new_name", CELL_CASES, ids=[name for _, name in CELL_CASES])
def test_notebook_test_fetch_params_match_quantaxis(cell_index: int, new_name: str, capsys):
    if not QA_AVAILABLE:
        pytest.skip(f"QUANTAXIS import failed: {QA_IMPORT_ERROR}")

    qa_func = QA_FUNC_BY_NEW_NAME.get(new_name)
    if qa_func is None:
        pytest.fail(f"missing QA function mapping for {new_name}")

    ns: dict[str, object] = {}
    exec(CELL0, ns, ns)
    exec(CELL1, ns, ns)

    we_func = ns.get(new_name)
    if not callable(we_func):
        pytest.fail(f"notebook namespace missing callable {new_name}")

    called = False

    def _wrapper(*args, **kwargs):
        nonlocal called
        called = True
        we_res = we_func(*args, **kwargs)
        try:
            qa_res = qa_func(*args, **kwargs)
        except Exception as exc:
            if new_name == "fetch_dk_data":
                pytest.skip(f"dk_data schema mismatch; QUANTAXIS raised {type(exc).__name__}: {exc}")
            raise
        _compare_any(qa_res, we_res, func_name=new_name)
        if hasattr(we_res, "data") or hasattr(we_res, "to_qfq") or hasattr(we_res, "to_hfq"):
            return _DualResult(we_res, qa_res, func_name=new_name)
        return we_res

    ns[new_name] = _wrapper

    cell_src = "".join(NOTEBOOK["cells"][cell_index]["source"])
    exec(cell_src, ns, ns)

    out = capsys.readouterr().out
    if not called:
        reason = "cell did not invoke function"
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("skip:"):
                reason = s
                break
        pytest.skip(reason)
