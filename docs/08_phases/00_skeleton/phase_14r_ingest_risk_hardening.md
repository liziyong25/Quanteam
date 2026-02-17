# Phase-14R: Non-blocking Risk Hardening for Ingest Adapter

## Goal

Harden the Phase-14 ingest adapter with minimal, non-breaking guardrails:

- `ingest_manifest.json` is a versioned contract (`ingest_manifest_v1`) and includes as-of audit fields
- dt semantics are normalized and documented (YYYY-MM-DD trading day; +08:00 close anchor)
- real provider stub fails with a clear deterministic exit code (tests remain offline)

Constraints:

- no external network dependencies; tests offline deterministic
- do not change existing policy `*_v1.yaml` assets
- do not refactor runner/compiler/gaterunner/orchestrator

## Background (Risk Points)

- Without a strict ingest manifest contract + audit fields, snapshot availability semantics can drift from policy.
- Provider dt formats can vary (date vs datetime); without normalization, dedupe/replay can be inconsistent.
- Real provider integration should not make CI flaky; failure mode must be explicit and deterministic.

## Changes

1) Ingest manifest contract (v1)

- `contracts/ingest_manifest_schema_v1.json` (dispatch supported by `python -m quant_eam.contracts.validate`)
- `ingest_manifest.json` includes:
  - required request + outputs + sha256 evidence
  - as-of audit fields from read-only `policies/asof_latency_policy_v1.yaml`
  - dt source audit in `extensions`

2) dt normalization

- Adapter normalizes all provider rows `dt` into `YYYY-MM-DD` (trading day string), using +08:00 for tz-naive inputs.
- Invalid dt fails with exit code `2`.

3) Real provider failure mode

- `--provider wequant` without wequant availability/integration exits `2` with actionable message.
- Tests/CI always use `--provider mock`.

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown (repo has no git metadata or HEAD not available)

## Acceptance Evidence

1) Build:

```bash
docker compose build api worker
```

2) Tests:

```bash
EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q
```

3) Mock ingest demo:

```bash
docker compose run --rm api python -m quant_eam.ingest.wequant_ohlcv \
  --provider mock --snapshot-id demo_wq_snap_002 \
  --symbols AAA,BBB --start 2024-01-01 --end 2024-01-10
```

4) Contract validate demo:

```bash
docker compose run --rm api python -m quant_eam.contracts.validate /data/lake/demo_wq_snap_002/ingest_manifest.json
```

5) Docs tree:

```bash
python3 scripts/check_docs_tree.py
```

