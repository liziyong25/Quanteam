# WEQUANT

WEQUANT is a research-first quant data layer + backtest workspace.

- **wequant/**: Core Python package (WEFetch / WESU and future modules)
- **vectorbt/**: Existing vectorbt code (vendored or submodule; not modified here)
- **docs/**: DOCS_V2-style documentation system (SSOT dossiers + KB + lessons)

## Quickstart (dev)

1) Create a Python 3.11+ environment (conda recommended)
2) Install WEQUANT in editable mode:

```bash
pip install -e .
```

3) Verify import:

```bash
python -c "import wequant; print(wequant.__version__)"
```

## Documentation

Entry: `docs/DOCS_V2/00_START_HERE.md`
