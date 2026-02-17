from __future__ import annotations

import inspect
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from .policy import apply_user_policy, snake_case
from .registry import FetchMapping, build_fetch_mappings
from .mongo_bridge import resolve_mongo_fetch_callable
from .mysql_bridge import resolve_mysql_fetch_callable
from .source import SOURCE_MONGO, SOURCE_MYSQL, is_mongo_source, is_mysql_source, normalize_source


SOURCE_PRIORITY = {SOURCE_MYSQL: 0, SOURCE_MONGO: 1}
SUPPORTED_ASSETS = {"bond", "stock", "hkstock", "future", "etf", "index"}
SUPPORTED_FREQ = {"day", "min", "transaction", "dk"}
SUPPORTED_ADJUST = {"raw", "qfq", "hfq"}
_SYMBOL_SEQ_TYPES = (list, tuple)


@dataclass(frozen=True)
class FetchResolution:
    asset: str
    freq: str
    venue: str | None
    adjust: str
    source: str
    target_name: str
    public_name: str
    raw_source: str
    raw_target_name: str
    raw_public_name: str
    adv_source: str | None
    adv_target_name: str | None
    adv_public_name: str | None
    used_adv: bool


@dataclass
class _IndexEntry:
    asset: str
    freq: str
    venue: str | None
    raw_source: str | None = None
    raw_target_name: str | None = None
    raw_public_name: str | None = None
    adv_source: str | None = None
    adv_target_name: str | None = None
    adv_public_name: str | None = None


def _source_better(new_source: str, current_source: str | None) -> bool:
    new_key = normalize_source(new_source) or str(new_source)
    cur_key = normalize_source(current_source) if current_source is not None else None
    if current_source is None:
        return True
    return SOURCE_PRIORITY.get(new_key, -1) > SOURCE_PRIORITY.get(cur_key, -1)


def _parse_market_signature(name: str) -> tuple[str, str, str | None, bool] | None:
    n = snake_case(name)
    is_adv = n.endswith("_adv")
    base = n[: -len("_adv")] if is_adv else n
    if not base.startswith("fetch_"):
        return None
    parts = base.split("_")
    if len(parts) < 3:
        return None
    asset = parts[1]
    freq = parts[2]
    if asset not in SUPPORTED_ASSETS or freq not in SUPPORTED_FREQ:
        return None
    venue = "_".join(parts[3:]) if len(parts) > 3 else None
    return asset, freq, venue or None, is_adv


@lru_cache(maxsize=1)
def _policy_rows() -> tuple[FetchMapping, ...]:
    return apply_user_policy(build_fetch_mappings())


@lru_cache(maxsize=1)
def _market_index() -> dict[tuple[str, str, str], _IndexEntry]:
    idx: dict[tuple[str, str, str], _IndexEntry] = {}
    for row in _policy_rows():
        if row.status == "drop":
            continue
        sig = _parse_market_signature(row.proposed_name)
        if sig is None:
            continue
        asset, freq, venue, is_adv = sig
        key = (asset, freq, venue or "")
        if key not in idx:
            idx[key] = _IndexEntry(asset=asset, freq=freq, venue=venue)
        ent = idx[key]
        if is_adv:
            if _source_better(row.source, ent.adv_source):
                ent.adv_source = row.source
                ent.adv_target_name = row.old_name
                ent.adv_public_name = row.proposed_name
        else:
            if _source_better(row.source, ent.raw_source):
                ent.raw_source = row.source
                ent.raw_target_name = row.old_name
                ent.raw_public_name = row.proposed_name
    return idx


def _resolve_callable(source: str, target_name: str):
    normalized = normalize_source(source)
    if is_mongo_source(normalized):
        return resolve_mongo_fetch_callable(target_name)
    if is_mysql_source(normalized):
        return resolve_mysql_fetch_callable(target_name)
    raise ValueError(f"unsupported source={source!r}")


def _stable_value_repr(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return repr(value)
    return f"<{type(value).__name__}>"


def _normalize_selector(
    *,
    field: str,
    value: Any,
    expected: set[str],
    default_if_blank: str | None = None,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"unsupported {field}={_stable_value_repr(value)}; expected one of {sorted(expected)}"
        )
    text = value.strip()
    if text == "" and default_if_blank is not None:
        text = default_if_blank
    normalized = snake_case(text)
    if normalized not in expected:
        raise ValueError(
            f"unsupported {field}={_stable_value_repr(value)}; expected one of {sorted(expected)}"
        )
    return normalized


def _normalize_venue(venue: Any) -> str | None:
    if venue is None:
        return None
    if not isinstance(venue, str):
        raise ValueError(f"unsupported venue={_stable_value_repr(venue)}; expected string or None")
    text = venue.strip()
    if not text:
        return None
    return snake_case(text)


def _normalize_symbols(symbols: Any) -> list[str] | str:
    if isinstance(symbols, str):
        token = symbols.strip()
        if not token:
            raise ValueError("symbols must be a non-empty string or non-empty list[str]")
        return token

    if isinstance(symbols, _SYMBOL_SEQ_TYPES):
        normalized: list[str] = []
        for i, item in enumerate(symbols):
            if not isinstance(item, str):
                raise ValueError(
                    f"symbols[{i}] must be non-empty string; got {_stable_value_repr(item)}"
                )
            token = item.strip()
            if not token:
                raise ValueError(f"symbols[{i}] must be non-empty string")
            normalized.append(token)
        if not normalized:
            raise ValueError("symbols must be a non-empty string or non-empty list[str]")
        return normalized

    raise ValueError(
        f"symbols must be a non-empty string or non-empty list[str]; got {_stable_value_repr(symbols)}"
    )


def _normalize_required_text(*, field: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a non-empty string; got {_stable_value_repr(value)}")
    text = value.strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string")
    return text


def _call_fetch_fn(
    fn: Any,
    *,
    code: list[str] | str,
    start: str,
    end: str,
    format: str,
    extra_kwargs: dict[str, Any],
) -> Any:
    sig = inspect.signature(fn)
    params = sig.parameters
    accepted_kwargs = {
        k: v
        for k, v in extra_kwargs.items()
        if k in params and k not in {"code", "symbol", "start", "end", "format"}
    }

    if "code" in params:
        call_kwargs: dict[str, Any] = {"code": code, **accepted_kwargs}
        if "start" in params:
            call_kwargs["start"] = start
        if "end" in params:
            call_kwargs["end"] = end
        if "format" in params:
            call_kwargs["format"] = format
        return fn(**call_kwargs)

    if "symbol" in params:
        call_kwargs = {"symbol": code, **accepted_kwargs}
        if "start" in params:
            call_kwargs["start"] = start
        if "end" in params:
            call_kwargs["end"] = end
        if "format" in params:
            call_kwargs["format"] = format
        return fn(**call_kwargs)

    # Fallback to positional call when signature is non-standard.
    if "format" in params:
        return fn(code, start, end, format=format, **accepted_kwargs)
    return fn(code, start, end, **accepted_kwargs)


def qa_fetch_registry_payload(*, include_drop: bool = False) -> dict[str, Any]:
    rows = _policy_rows()
    if not include_drop:
        rows = tuple(r for r in rows if r.status != "drop")

    functions: list[dict[str, Any]] = []
    for row in rows:
        sig = _parse_market_signature(row.proposed_name)
        asset = freq = venue = None
        is_market_data = False
        if sig is not None:
            asset, freq, venue, _is_adv = sig
            is_market_data = True
        item = asdict(row)
        item["source_internal"] = row.source
        item["source"] = "fetch"
        if is_mongo_source(row.source):
            item["engine"] = "mongo"
            item["provider_internal"] = "mongo_fetch"
        elif is_mysql_source(row.source):
            item["engine"] = "mysql"
            item["provider_internal"] = "mysql_fetch"
        else:
            item["engine"] = None
            item["provider_internal"] = None
        item["provider_id"] = "fetch"
        item["is_market_data"] = is_market_data
        item["asset"] = asset
        item["freq"] = freq
        item["venue"] = venue
        functions.append(item)

    resolver_entries = []
    for key in sorted(_market_index()):
        entry = _market_index()[key]
        if entry.raw_target_name is None or entry.raw_source is None or entry.raw_public_name is None:
            continue
        resolver_entries.append(
            {
                "asset": entry.asset,
                "freq": entry.freq,
                "venue": entry.venue,
                "raw": {
                    "source": "fetch",
                    "source_internal": entry.raw_source,
                    "engine": "mongo" if is_mongo_source(entry.raw_source) else "mysql",
                    "provider_id": "fetch",
                    "provider_internal": "mongo_fetch" if is_mongo_source(entry.raw_source) else "mysql_fetch",
                    "target_name": entry.raw_target_name,
                    "public_name": entry.raw_public_name,
                },
                "adjustment": {
                    "supports_raw": True,
                    "supports_qfq": bool(entry.adv_target_name),
                    "supports_hfq": bool(entry.adv_target_name),
                    "adv": (
                        {
                            "source": "fetch",
                            "source_internal": entry.adv_source,
                            "engine": "mongo" if is_mongo_source(entry.adv_source) else "mysql",
                            "provider_id": "fetch",
                            "provider_internal": "mongo_fetch" if is_mongo_source(entry.adv_source) else "mysql_fetch",
                            "target_name": entry.adv_target_name,
                            "public_name": entry.adv_public_name,
                        }
                        if entry.adv_target_name and entry.adv_source and entry.adv_public_name
                        else None
                    ),
                },
            }
        )

    return {
        "schema_version": "qa_fetch_registry_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "naming": {
            "pattern": "fetch_<asset>_<freq>[_<venue>]",
            "asset": sorted(SUPPORTED_ASSETS),
            "freq": sorted(SUPPORTED_FREQ),
            "adjust": sorted(SUPPORTED_ADJUST),
            "default_adjust": "raw",
            "default_venue_behavior": "if venue is omitted, use non-venue generic function",
        },
        "functions": functions,
        "resolver_entries": resolver_entries,
    }


def resolve_fetch(
    *,
    asset: str,
    freq: str,
    venue: str | None = None,
    adjust: str = "raw",
) -> FetchResolution:
    asset_n = _normalize_selector(field="asset", value=asset, expected=SUPPORTED_ASSETS)
    freq_n = _normalize_selector(field="freq", value=freq, expected=SUPPORTED_FREQ)
    venue_n = _normalize_venue(venue)
    adjust_n = _normalize_selector(
        field="adjust",
        value=adjust,
        expected=SUPPORTED_ADJUST,
        default_if_blank="raw",
    )

    key = (asset_n, freq_n, venue_n or "")
    ent = _market_index().get(key)
    if ent is None:
        if venue_n:
            raise ValueError(
                f"no resolver mapping for asset={asset_n!r} freq={freq_n!r} venue={venue_n!r}"
            )
        raise ValueError(f"no resolver mapping for asset={asset_n!r} freq={freq_n!r}")

    if not ent.raw_source or not ent.raw_target_name or not ent.raw_public_name:
        raise ValueError(
            f"invalid resolver entry for asset={asset_n!r} freq={freq_n!r} venue={venue_n!r}: missing raw target"
        )

    if adjust_n == "raw":
        return FetchResolution(
            asset=asset_n,
            freq=freq_n,
            venue=venue_n,
            adjust=adjust_n,
            source=ent.raw_source,
            target_name=ent.raw_target_name,
            public_name=ent.raw_public_name,
            raw_source=ent.raw_source,
            raw_target_name=ent.raw_target_name,
            raw_public_name=ent.raw_public_name,
            adv_source=ent.adv_source,
            adv_target_name=ent.adv_target_name,
            adv_public_name=ent.adv_public_name,
            used_adv=False,
        )

    if not ent.adv_source or not ent.adv_target_name or not ent.adv_public_name:
        raise ValueError(
            f"adjust={adjust_n!r} is not supported for asset={asset_n!r} freq={freq_n!r} venue={venue_n!r}; no *_adv mapping"
        )

    return FetchResolution(
        asset=asset_n,
        freq=freq_n,
        venue=venue_n,
        adjust=adjust_n,
        source=ent.adv_source,
        target_name=ent.adv_target_name,
        public_name=ent.adv_public_name,
        raw_source=ent.raw_source,
        raw_target_name=ent.raw_target_name,
        raw_public_name=ent.raw_public_name,
        adv_source=ent.adv_source,
        adv_target_name=ent.adv_target_name,
        adv_public_name=ent.adv_public_name,
        used_adv=True,
    )


def fetch_market_data(
    *,
    asset: str,
    freq: str,
    symbols: list[str] | str,
    start: str,
    end: str,
    venue: str | None = None,
    adjust: str = "raw",
    format: str = "pd",
    **kwargs: Any,
) -> Any:
    resolution = resolve_fetch(asset=asset, freq=freq, venue=venue, adjust=adjust)
    code = _normalize_symbols(symbols)
    start_n = _normalize_required_text(field="start", value=start)
    end_n = _normalize_required_text(field="end", value=end)
    format_n = _normalize_required_text(field="format", value=format)
    fn = _resolve_callable(resolution.source, resolution.target_name)
    user_kwargs = {k: v for k, v in kwargs.items() if k not in {"tag"}}

    if not resolution.used_adv:
        return _call_fetch_fn(
            fn,
            code=code,
            start=start_n,
            end=end_n,
            format=format_n,
            extra_kwargs=user_kwargs,
        )

    adv_obj = _call_fetch_fn(
        fn,
        code=code,
        start=start_n,
        end=end_n,
        format=format_n,
        extra_kwargs=user_kwargs,
    )
    if adv_obj is None:
        return None
    method = getattr(adv_obj, f"to_{resolution.adjust}", None)
    if not callable(method):
        raise ValueError(
            f"resolved adv object does not support to_{resolution.adjust}(): {resolution.public_name}"
        )
    out = method()
    if format_n.lower() in {"p", "pd", "pandas"}:
        try:
            import pandas as pd  # noqa: PLC0415
        except Exception:
            return out
        if isinstance(out, pd.DataFrame):
            return out
        maybe_data = getattr(out, "data", None)
        if isinstance(maybe_data, pd.DataFrame):
            return maybe_data
    return out


__all__ = [
    "FetchResolution",
    "qa_fetch_registry_payload",
    "resolve_fetch",
    "fetch_market_data",
]
