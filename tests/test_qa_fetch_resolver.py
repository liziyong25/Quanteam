from __future__ import annotations

import pytest

import quant_eam.qa_fetch.resolver as resolver
from quant_eam.qa_fetch.resolver import FetchResolution, fetch_market_data, qa_fetch_registry_payload, resolve_fetch
from quant_eam.qa_fetch.source import SOURCE_MONGO, SOURCE_MYSQL


def test_registry_payload_has_machine_entries() -> None:
    payload = qa_fetch_registry_payload(include_drop=False)
    assert payload["schema_version"] == "qa_fetch_registry_v1"
    assert len(payload.get("functions", [])) == 71
    assert len(payload.get("resolver_entries", [])) >= 10
    sources = {row.get("source") for row in payload.get("functions", [])}
    provider_ids = {row.get("provider_id") for row in payload.get("functions", [])}
    engines = {row.get("engine") for row in payload.get("functions", [])}
    assert sources == {"fetch"}
    assert provider_ids == {"fetch"}
    assert engines == {"mongo", "mysql"}


def test_resolve_fetch_defaults_generic_source() -> None:
    r = resolve_fetch(asset="bond", freq="day", adjust="raw")
    assert r.public_name == "fetch_bond_day"
    assert r.source == SOURCE_MYSQL
    assert r.target_name == "fetch_bond_day"

    r_cfets = resolve_fetch(asset="bond", freq="day", venue="cfets", adjust="raw")
    assert r_cfets.public_name == "fetch_bond_day_cfets"
    assert r_cfets.source == SOURCE_MYSQL
    assert r_cfets.target_name == "fetch_settlement_bond_day"


def test_resolve_fetch_adjustment_semantics() -> None:
    r = resolve_fetch(asset="stock", freq="day", adjust="qfq")
    assert r.used_adv is True
    assert r.public_name == "fetch_stock_day_adv"
    assert r.target_name == "fetch_stock_day_adv"

    try:
        resolve_fetch(asset="bond", freq="day", adjust="qfq")
        raised = False
    except ValueError:
        raised = True
    assert raised is True


def test_resolve_fetch_runtime_normalization_is_stable() -> None:
    r_stock = resolve_fetch(asset=" Stock ", freq=" DAY ", adjust=" QFQ ")
    assert r_stock.asset == "stock"
    assert r_stock.freq == "day"
    assert r_stock.adjust == "qfq"
    assert r_stock.used_adv is True

    r_bond = resolve_fetch(asset=" bond ", freq=" day ", venue=" CFETS ", adjust=" ")
    assert r_bond.asset == "bond"
    assert r_bond.freq == "day"
    assert r_bond.venue == "cfets"
    assert r_bond.adjust == "raw"
    assert r_bond.used_adv is False


def test_resolve_fetch_rejects_non_string_fields_deterministically() -> None:
    class Opaque:
        pass

    with pytest.raises(ValueError, match=r"unsupported asset=<Opaque>; expected one of"):
        resolve_fetch(asset=Opaque(), freq="day")

    with pytest.raises(ValueError, match=r"unsupported venue=<Opaque>; expected string or None"):
        resolve_fetch(asset="bond", freq="day", venue=Opaque())


def _stub_resolution(*, used_adv: bool = False, adjust: str = "raw") -> FetchResolution:
    return FetchResolution(
        asset="stock",
        freq="day",
        venue=None,
        adjust=adjust,
        source=SOURCE_MONGO,
        target_name="fetch_stock_day_adv" if used_adv else "fetch_stock_day",
        public_name="fetch_stock_day_adv" if used_adv else "fetch_stock_day",
        raw_source=SOURCE_MONGO,
        raw_target_name="fetch_stock_day",
        raw_public_name="fetch_stock_day",
        adv_source=SOURCE_MONGO,
        adv_target_name="fetch_stock_day_adv",
        adv_public_name="fetch_stock_day_adv",
        used_adv=used_adv,
    )


def test_fetch_market_data_normalizes_runtime_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_fetch(*, code: list[str] | str, start: str, end: str, format: str) -> dict[str, str]:
        captured["code"] = code
        captured["start"] = start
        captured["end"] = end
        captured["format"] = format
        return {"ok": "1"}

    monkeypatch.setattr(resolver, "resolve_fetch", lambda **_: _stub_resolution())
    monkeypatch.setattr(resolver, "_resolve_callable", lambda source, target_name: _fake_fetch)

    out = fetch_market_data(
        asset="stock",
        freq="day",
        symbols=[" 000001 ", " 000002 "],
        start=" 2024-01-01 ",
        end=" 2024-01-31 ",
        format=" pandas ",
    )

    assert out == {"ok": "1"}
    assert captured["code"] == ["000001", "000002"]
    assert captured["start"] == "2024-01-01"
    assert captured["end"] == "2024-01-31"
    assert captured["format"] == "pandas"


def test_fetch_market_data_rejects_invalid_symbols_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def _no_dispatch(_source: str, _target_name: str):
        nonlocal called
        called = True
        raise AssertionError("dispatch should not run for invalid symbols")

    monkeypatch.setattr(resolver, "resolve_fetch", lambda **_: _stub_resolution())
    monkeypatch.setattr(resolver, "_resolve_callable", _no_dispatch)

    with pytest.raises(
        ValueError,
        match=r"symbols must be a non-empty string or non-empty list\[str\]; got <object>",
    ):
        fetch_market_data(
            asset="stock",
            freq="day",
            symbols=object(),
            start="2024-01-01",
            end="2024-01-31",
        )
    assert called is False


def test_fetch_market_data_rejects_invalid_symbol_item_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolver, "resolve_fetch", lambda **_: _stub_resolution())
    monkeypatch.setattr(resolver, "_resolve_callable", lambda source, target_name: lambda **_: None)

    with pytest.raises(
        ValueError,
        match=r"symbols\[1\] must be non-empty string; got <object>",
    ):
        fetch_market_data(
            asset="stock",
            freq="day",
            symbols=["000001", object()],
            start="2024-01-01",
            end="2024-01-31",
        )


def test_fetch_market_data_rejects_invalid_text_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolver, "resolve_fetch", lambda **_: _stub_resolution())
    monkeypatch.setattr(resolver, "_resolve_callable", lambda source, target_name: lambda **_: None)

    with pytest.raises(ValueError, match=r"start must be a non-empty string; got 20240101"):
        fetch_market_data(
            asset="stock",
            freq="day",
            symbols="000001",
            start=20240101,
            end="2024-01-31",
        )

    with pytest.raises(ValueError, match=r"format must be a non-empty string"):
        fetch_market_data(
            asset="stock",
            freq="day",
            symbols="000001",
            start="2024-01-01",
            end="2024-01-31",
            format=" ",
        )
