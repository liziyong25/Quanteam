---
title: WEQUANT data_layer — Acceptance Evidence
kind: dossier
component: data_layer
topics: [acceptance, evidence]
status: draft
created: 2026-02-02
updated: 2026-02-02
source_paths: []
related_modules:
  - wequant/wefetch/__init__.py
  - wequant/wesu/__init__.py
related_tables: []
keywords: [DEV, PROD, PASS]
---

# 05_ACCEPTANCE_EVIDENCE（WEQUANT data_layer）

## Lane A：DEV（Windows）

CapturedAt (UTC+8): <fill>
Commit SHA: <fill>

Commands + Output Snippets（示例，需实际回填）：
```bash
python -V
pip -V
pip install -e .
pytest -q

python -c "from wequant.mongo import get_db; print(get_db().list_collection_names())"

python - << 'PY'
from wequant.wefetch import fetch_stock_list
df = fetch_stock_list()
print(df.head())
print('rows=', len(df))
PY
```

PASS 判据：
- pytest 全部通过
- list_collection_names 输出包含 `stock_list`
- fetch_stock_list rows > 0

## Lane B：PROD（Linux）
- N/A for now（待 Linux 环境准备好后按 Lane A 复制验证）
