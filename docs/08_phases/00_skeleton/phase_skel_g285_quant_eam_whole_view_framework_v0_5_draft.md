# Phase G285: Requirement Gap Closure (WV-039)

## Goal
- Close requirement gap `WV-039` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:185`.

## Scope Boundary
- In scope: `WV-039` as the umbrella clause `5.2 Data Contracts（v1 新增）` under Contracts/Schema.
- Out of scope: direct implementation closure of `WV-040`..`WV-043`; those remain separately planned requirements.

## Requirements
- Requirement IDs: WV-039
- Owner Track: skeleton
- Clause[WV-039]: Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated Mainline） / 5. Contracts（Schema）体系：让 LLM/Codex 能产、Kernel 能编译、UI 能渲染 / 5.2 Data Contracts（v1 新增）

## Preconditions Verified (2026-02-15)
- `G284` is `implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
- `WV-038` is `implemented` and linked to `G284` in `docs/12_workflows/skeleton_ssot_v1.yaml`.
- Source scope confirmed from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:185`.

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## Concrete Execution Plan
1. Verify dependency gate (`G284`, `WV-038`) before any write.
2. Keep `WV-039` mapped to standalone `G285` on `skeleton` track with `depends_on: G284`.
3. Preserve `WV-040`..`WV-043` as planned downstream requirements depending on `WV-039`.
4. Run acceptance commands sequentially for deterministic evidence.
5. Record command evidence in this phase doc.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Acceptance Evidence Notes (2026-02-15)
- Command: `python3 scripts/check_docs_tree.py`
  - Observed output:
    - `docs tree: OK`
- Command: `rg -n "G285|WV-039" docs/12_workflows/skeleton_ssot_v1.yaml`
  - Observed output (key lines):
    - `13928:- id: G285`
    - `13929:  title: Skeleton requirement execution for WV-039`
    - `16425:- req_id: WV-039`
    - `16436:  - G285`
    - `21330:  latest_phase_id: G285`
