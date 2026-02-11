from __future__ import annotations

import json
from pathlib import Path


def test_notebook_function_coverage():
    func_items = json.loads(
        (Path('tests') / 'fixtures' / 'upstream_functions.json').read_text(encoding='utf-8')
    )
    nb = json.loads(
        (Path('wequant') / 'test' / 'test_fetch.ipynb').read_text(encoding='utf-8')
    )
    code_cells = [cell for cell in nb.get('cells', []) if cell.get('cell_type') == 'code']

    # 2 helper cells + one cell per upstream function
    assert len(code_cells) == len(func_items) + 2

    sources = "\n".join("".join(cell.get('source', [])) for cell in code_cells)
    for item in func_items:
        new_name = item['name'].replace('QA_', '')
        assert new_name in sources, f"missing {new_name} in notebook"
