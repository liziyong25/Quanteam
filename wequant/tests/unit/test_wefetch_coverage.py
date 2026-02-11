from __future__ import annotations

import json
from pathlib import Path

import pytest

import wequant.wefetch as wefetch


FIXTURE_PATH = Path('tests') / 'fixtures' / 'upstream_functions.json'


def _load_functions():
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
    return data


@pytest.mark.parametrize('func_name', [item['name'] for item in _load_functions()])
def test_wefetch_has_mapping(func_name):
    new_name = func_name.replace('QA_', '')
    assert hasattr(wefetch, new_name), f'missing wefetch.{new_name} for {func_name}'
    assert callable(getattr(wefetch, new_name))
    # Optional compatibility alias is expected in this repo
    assert hasattr(wefetch, func_name), f'missing wefetch.{func_name} alias'


def test_unimplemented_behavior_matches_quantaxis():
    with pytest.raises(NotImplementedError):
        wefetch.fetch_future_tick()
    assert wefetch.fetch_option_day_adv('000001') is None
