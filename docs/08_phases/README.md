# docs/08_phases Tracks

`docs/08_phases` remains the single DoD root for all phase logs.

## Tracks

- `00_skeleton/`: Whole View / governance / phase skeleton logs.
- `10_impl_fetchdata/`: implementation logs for fetch-data capability track.

## Path Rules

- Shared phase template stays at `docs/08_phases/phase_template.md`.
- Numbered phase logs must live in a track directory, not directly under `docs/08_phases/`.
- Current repository decision: `phase_00a` to `phase_75` are under `docs/08_phases/00_skeleton/`.

## SSOT Reference Guidance

`docs/12_workflows/skeleton_ssot_v1.yaml` currently does not use a `phase_doc_path` key.
Use existing equivalent fields to reference phase logs:

- `goal_checklist[].expected_artifacts`
- `autopilot_stop_condition_exceptions_v1[].preauthorized_scope.allowed_code_paths`
- `whole_view_autopilot_v1.failure_policy.on_retry_exhausted.required_outputs`

When adding new phase references, point to the active track path, for example:

- `docs/08_phases/00_skeleton/phase_<id>_*.md`
- `docs/08_phases/10_impl_fetchdata/phase_<id>_*.md`

## Migration Map

See `docs/08_phases/MIGRATION.md` for the old-root to track-path mapping.
