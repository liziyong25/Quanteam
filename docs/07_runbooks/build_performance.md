# Build Performance (Phase-25)

This runbook documents small, non-semantic optimizations for build/test speed and repeatability.

## Docker Image Dependency Cache

The repo Docker image installs the project with dev tooling:

- `docker/Dockerfile` runs `pip install -e ".[dev]"`

To improve build speed:

- Prefer incremental builds (avoid `--no-cache` when iterating locally).
- Keep `pyproject.toml` stable to maximize Docker layer cache reuse.

## pip Cache (Local)

If you run Python tooling outside Docker, use a persistent pip cache directory:

```bash
export PIP_CACHE_DIR="$HOME/.cache/pip"
```

## Optional Extras Split (Future)

If dependency weight becomes a bottleneck, consider splitting optional dependencies in `pyproject.toml`:

- `dev` (tests + linters)
- `llm` (provider SDKs)
- `viz` (plotting)

This phase does not require changing dependency sets; it only documents the option.

