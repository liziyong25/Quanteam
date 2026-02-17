---
name: requirement-splitter
description: Compress and split requirement markdown into stable, dependency-aware requirement rows for `docs/12_workflows/skeleton_ssot_v1.yaml`. Use when requirement extraction is over-fragmented, when adding a new requirement source document, or when tuning goal generation density before controller/subagent dispatch.
---

# Requirement Splitter

## Overview

Use the repository splitter pipeline to convert large markdown documents into compact machine-readable clauses. Keep requirement IDs stable, reduce noisy narrative clauses, and feed cleaner requirement gaps into `whole_view_autopilot.py`.

## Workflow

1. Preview extraction count per source:
```bash
python3 scripts/requirement_splitter.py \
  --source docs/00_overview/workbench_ui_productization_v1.md \
  --prefix WB \
  --config docs/12_workflows/requirement_splitter_profiles_v1.yaml \
  --show 20
```
2. Tune profile rules in `docs/12_workflows/requirement_splitter_profiles_v1.yaml`.
3. Rebuild SSOT requirement trace:
```bash
python3 scripts/whole_view_autopilot.py --mode migrate --skip-gates --disable-push
```
4. Validate structure and scheduler readiness:
```bash
python3 scripts/check_docs_tree.py
python3 scripts/whole_view_autopilot.py --mode plan --skip-gates --disable-push
```

## Add New Requirement Document

1. Add the source path in `scripts/whole_view_autopilot.py` `REQ_SOURCE_CANDIDATES`.
2. Map prefix to track in `REQ_PREFIX_OWNER_TRACK`.
3. Add a profile in `docs/12_workflows/requirement_splitter_profiles_v1.yaml`.
4. Run migrate and confirm new `<PREFIX>-*` rows appear in `requirements_trace_v1`.

## Guardrails

1. Keep extraction deterministic: avoid random sampling and unstable sorting.
2. Keep clauses requirement-dense: prioritize FR/NFR/API/DoD/phase acceptance statements.
3. Exclude narrative-only sections (background/changelog/notes) unless explicitly required.
4. Keep `depends_on_req_ids` chain intact to preserve gate ordering.
5. Re-run plan mode after every profile change to avoid empty queue or blocked-by-dependency regressions.
6. Extraction granularity is not phase granularity: requirement rows may be bundled by `ssot-goal-planner`
   into one goal based on `planning_policy_v2.goal_bundle_policy`.

## References

Load `skills/requirement-splitter/references/profile_tuning.md` when tuning compression ratios or regex scope.
