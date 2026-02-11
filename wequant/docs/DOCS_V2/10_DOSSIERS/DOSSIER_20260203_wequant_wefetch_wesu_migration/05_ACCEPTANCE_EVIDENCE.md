---
title: WEFetch/WESU Migration - Acceptance Evidence
kind: dossier
component: data_layer
topics: [acceptance, evidence, run_backed]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths: []
related_modules: []
related_tables: []
keywords: [conda, pytest, cli, e2e]
---

# 05_ACCEPTANCE_EVIDENCE
## DEV lane (Windows)

### Conda env
Command:
```
conda create -n wequant python=3.11 -y
```
Output (excerpt):
```
Solving environment: ... done
python-3.11.14
```

### pip (upgrade attempt)
Command:
```
conda run -n wequant python -m pip install -U pip
```
Output (excerpt):
```
ERROR: Could not install packages due to an OSError: [WinError 5] 拒绝访问
```

### pip restore + install
Command:
```
conda install -n wequant pip --force-reinstall -y
conda run -n wequant python -m pip install -e .
conda run -n wequant python -m pip install pytest ruff black mypy
```
Output (excerpt):
```
Successfully installed ... wequant-0.1.0
Successfully installed ... pytest-9.0.2 ruff-0.14.14 black-26.1.0 mypy-1.19.1
```

### Import smoke
Command:
```
conda run -n wequant python -c "import wequant; print(wequant.__version__)"
```
Output:
```
0.1.0
```

### pytest (default)
Command:
```
conda run -n wequant pytest -q
```
Output:
```
....
```

### pytest (e2e enabled)
Command:
```
$env:WEQUANT_E2E='1'; conda run -n wequant pytest -q -rs
```
Output (excerpt):
```
ssssssssssss....
SKIPPED [3] tests/e2e/test_fetch_e2e.py:87: QUANTAXIS import failed: No module named 'QUANTAXIS'
SKIPPED [7] tests/e2e/test_save_e2e.py:27: WEQUANT_DB_NAME is not set to a test database
```

### CLI doctor
Command:
```
conda run -n wequant wequant doctor
```
Output:
```
WEQUANT_MONGO_URI=mongodb://localhost:27017
WEQUANT_DB_NAME=quantaxis
mongo_ping=ok
collection=stock_day exists=True has_data=True
collection=future_day exists=True has_data=True
collection=stock_adj exists=True has_data=True
collection=stock_list exists=True has_data=True
collection=future_list exists=True has_data=True
collection=etf_list exists=True has_data=True
collection=etf_day exists=False has_data=False
```

### CLI init-indexes (test DB)
Command:
```
$env:WEQUANT_DB_NAME='wequant_e2e'; conda run -n wequant wequant init-indexes
```
Output:
```
indexes=ok
```

### CLI init-indexes (default DB)
Command:
```
conda run -n wequant wequant init-indexes
```
Output (excerpt):
```
command timed out after 124008 milliseconds
```

### CLI smoke-fetch (stock)
Command:
```
conda run -n wequant wequant smoke-fetch --type stock --code 000001 --start 2024-01-01 --end 2024-01-31
```
Output (excerpt):
```
rows=22
              code  open  high   low  close     volume        amount       date
date
2024-01-02  000001  9.39  9.42  9.21   9.21  1158366.0  1.075742e+09 2024-01-02
```

### CLI smoke-save (test DB)
Command:
```
$env:WEQUANT_DB_NAME='wequant_e2e'; conda run -n wequant wequant smoke-save --type stock --code 000001 --date 2099-01-01
```
Output:
```
written_ops=1
```

## PROD lane (Linux)
- N/A (未配置 Linux 环境；需在 Linux conda 环境复跑以上命令)
