from . import query as _query
from . import query_advance as _query_advance
from .query import *  # noqa: F401,F403 - re-export public fetch APIs
from .query_advance import *  # noqa: F401,F403 - re-export public adv APIs
from .etf import fetch_etf_day

__all__ = []
for name in sorted(dir(_query)):
    if name.startswith("fetch_") or name.startswith("QA_fetch_"):
        __all__.append(name)
for name in sorted(dir(_query_advance)):
    if name.startswith("fetch_") or name.startswith("QA_fetch_"):
        if name not in __all__:
            __all__.append(name)
if "fetch_etf_day" not in __all__:
    __all__.append("fetch_etf_day")
