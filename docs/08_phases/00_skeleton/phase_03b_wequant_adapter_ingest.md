# Phase-03B: WeQuant Adapter Ingest (DataLake snapshot + ingest manifest)

## 1) 目标（Goal）

- Wrap WeQuant fetching into a deterministic ingest adapter that writes DataLake snapshots.
- Enforce or generate `available_at` using `asof_latency_policy_v1` semantics (`available_at<=as_of`).
- Produce an ingest manifest for audit + replay.
- Provide offline tests (no network IO) via a fake client.

## 2) 范围（Scope）

### In Scope

- `src/quant_eam/wequant_adapter/**` (client abstraction + ingest CLI)
- Light reuse of Phase-03 DataLake writer + manifest
- Unit tests using `FakeWequantClient` (tmp_path + `EAM_DATA_ROOT`)
- Docs describing mapping and available_at rules

### Out of Scope

- No real vendor integration details or credentials storage
- No DataCatalog changes (Phase-03 already provides query)
- No compiler/runner/backtest/gates

## 3) 交付物（Deliverables）

- CLI:
  - `python -m quant_eam.wequant_adapter.ingest ...`
- Docs:
  - `docs/05_data_plane/wequant_adapter_ingest.md`
- Phase log:
  - this file

## 4) 验收标准（Acceptance / DoD）

- Build:
  - `docker compose build api worker`
- Tests:
  - `docker compose run --rm api pytest -q`
- Offline demo:
  - `docker compose run --rm api python -m quant_eam.wequant_adapter.ingest --client fake --snapshot-id demo_wq_001 --dataset-id ohlcv_1d --symbols AAA,BBB --start 2024-01-01 --end 2024-01-10 --policy-bundle policies/policy_bundle_v1.yaml`
  - output must include: `rows_written`, output paths, `asof_latency_policy_id`
- Docs gate:
  - `python3 scripts/check_docs_tree.py`

## 5) 完成记录（Execution Log）

- Start Date: 2026-02-09 (Asia/Taipei)
- End Date: 2026-02-09 (Asia/Taipei)
- PR/Commit: unknown (repo is not a git repository; `git rev-parse --short HEAD` fails)
- Notes:
  - Added WeQuant ingest adapter with fake client for offline replayable tests
  - Enforced available_at generation/validation based on asof_latency_policy_v1
  - Added ingest manifest under snapshot/ingest_manifests/

## 6) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

