#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_FILES = [
    Path("docs/README.md"),
    Path("docs/00_overview.md"),
    Path("docs/01_governance.md"),
    Path("docs/02_protocols.md"),
    Path("docs/03_contracts/contracts_index.md"),
    Path("docs/03_contracts/blueprint_v1.md"),
    Path("docs/03_contracts/signal_dsl_v1.md"),
    Path("docs/03_contracts/variable_dictionary_v1.md"),
    Path("docs/03_contracts/calc_trace_plan_v1.md"),
    Path("docs/03_contracts/run_spec_v1.md"),
    Path("docs/03_contracts/run_spec_v2.md"),
    Path("docs/03_contracts/dossier_v1.md"),
    Path("docs/03_contracts/gate_results_v2.md"),
    Path("docs/04_policies/policies_index.md"),
    Path("docs/04_policies/execution_policy_v1.md"),
    Path("docs/04_policies/cost_policy_v1.md"),
    Path("docs/04_policies/asof_latency_policy_v1.md"),
    Path("docs/04_policies/budget_policy_v1.md"),
    Path("docs/04_policies/llm_budget_policy_v1.md"),
    Path("docs/04_policies/risk_policy_v1.md"),
    Path("docs/04_policies/gate_suite_v1.md"),
    Path("docs/04_policies/policy_bundle_v1.md"),
    Path("docs/05_data_plane/data_plane_mvp.md"),
    Path("docs/05_data_plane/data_contracts_v1.md"),
    Path("docs/05_data_plane/snapshot_catalog_v1.md"),
    Path("docs/05_data_plane/wequant_adapter_ingest.md"),
    Path("docs/05_data_plane/wequant_ingest_adapter_v1.md"),
    Path("docs/06_backtest_plane/backtest_index.md"),
    Path("docs/06_backtest_plane/vectorbt_adapter_mvp.md"),
    Path("docs/06_backtest_plane/signal_dsl_execution_v1.md"),
    Path("docs/06_backtest_plane/risk_constraints_v1.md"),
    Path("docs/06_backtest_plane/risk_evidence_artifacts_v1.md"),
    Path("docs/06_backtest_plane/evaluation_protocol_v1.md"),
    Path("docs/06_backtest_plane/attribution_v1.md"),
    Path("docs/06_backtest_plane/runner_and_dossier_mvp.md"),
    Path("docs/07_compiler/compiler_index.md"),
    Path("docs/07_compiler/compiler_mvp.md"),
    Path("docs/07_runbooks/local_dev.md"),
    Path("docs/07_runbooks/troubleshooting.md"),
    Path("docs/07_runbooks/build_performance.md"),
    Path("docs/07_runbooks/lint_coverage_plan.md"),
    Path("docs/07_runbooks/llm_recording.md"),
    Path("docs/08_phases/phase_template.md"),
    Path("docs/08_phases/phase_00a_repo_bootstrap.md"),
    Path("docs/08_phases/phase_00d_docs_governance.md"),
    Path("docs/08_phases/phase_01_contracts_v1.md"),
    Path("docs/08_phases/phase_02_policies_v1.md"),
    Path("docs/08_phases/phase_03_data_plane_mvp.md"),
    Path("docs/08_phases/phase_03b_wequant_adapter_ingest.md"),
    Path("docs/08_phases/phase_04_backtest_runner_dossier_mvp.md"),
    Path("docs/08_phases/phase_05_compiler_mvp.md"),
    Path("docs/08_phases/phase_06_gaterunner_holdout_v1.md"),
    Path("docs/08_phases/phase_07_registry_v1.md"),
    Path("docs/08_phases/phase_08_ui_mvp.md"),
    Path("docs/08_phases/phase_09_composer_mvp.md"),
    Path("docs/08_phases/phase_10_orchestrator_v1.md"),
    Path("docs/08_phases/phase_11_agents_harness_mvp.md"),
    Path("docs/08_phases/phase_12_strategy_spec_and_trace_preview.md"),
    Path("docs/08_phases/phase_13_budget_stop_and_improvement_mvp.md"),
    Path("docs/08_phases/phase_13r_risk_hardening.md"),
    Path("docs/08_phases/phase_14_wequant_ingest_adapter_mvp.md"),
    Path("docs/08_phases/phase_14r_ingest_risk_hardening.md"),
    Path("docs/08_phases/phase_15_data_contracts_and_quality_v1.md"),
    Path("docs/08_phases/phase_16_snapshot_catalog_and_quality_review.md"),
    Path("docs/08_phases/phase_17_snapshot_integrity_gate_and_provenance.md"),
    Path("docs/08_phases/phase_18_llm_harness_and_replay_v1.md"),
    Path("docs/08_phases/phase_19_agent_promptpack_guard_regression.md"),
    Path("docs/08_phases/phase_26_llm_real_provider_and_budget_v1.md"),
    Path("docs/08_phases/phase_27_protocol_hardening_v1.md"),
    Path("docs/08_phases/phase_28_live_llm_rollout_v1.md"),
    Path("docs/08_phases/phase_20_signal_dsl_execution_and_trace_consistency.md"),
    Path("docs/08_phases/phase_21_evaluation_protocol_v1.md"),
    Path("docs/08_phases/phase_22_risk_constraints_and_gate_v1.md"),
    Path("docs/08_phases/phase_23_budgeted_paramsweep_v1.md"),
    Path("docs/08_phases/phase_24_attribution_and_diagnostics_v1.md"),
    Path("docs/08_phases/phase_25_ops_hardening_v1.md"),
    Path("docs/08_phases/phase_29_experience_retrieval_v1.md"),
    Path("docs/08_gates/gates_index.md"),
    Path("docs/08_gates/gaterunner_v1.md"),
    Path("docs/08_gates/holdout_vault_v1.md"),
    Path("docs/08_gates/data_snapshot_integrity_v1.md"),
    Path("docs/08_gates/risk_policy_compliance_v1.md"),
    Path("docs/08_gates/holdout_leak_guard_v1.md"),
    Path("docs/09_registry/registry_index.md"),
    Path("docs/09_registry/trial_log_v1.md"),
    Path("docs/09_registry/experience_cards_v1.md"),
    Path("docs/09_registry/experience_retrieval_v1.md"),
    Path("docs/10_ui/ui_mvp.md"),
    Path("docs/10_ui/snapshots_review_ui_v1.md"),
    Path("docs/11_composer/composer_index.md"),
    Path("docs/11_composer/composer_curve_level_mvp.md"),
    Path("docs/12_workflows/orchestrator_v1.md"),
    Path("docs/12_workflows/param_sweep_v1.md"),
    Path("docs/12_workflows/agents_ui_ssot_v1.yaml"),
    Path("docs/12_workflows/subagent_dev_workflow_v1.md"),
    Path("docs/12_workflows/subagent_control_packet_v1.md"),
    Path("docs/12_workflows/templates/subagent_task_card_v1.yaml"),
    Path("docs/12_workflows/templates/subagent_executor_report_v1.yaml"),
    Path("docs/12_workflows/templates/subagent_validator_report_v1.yaml"),
    Path("docs/13_agents/agents_harness_v1.md"),
    Path("docs/13_agents/intent_agent_v1.md"),
    Path("docs/13_agents/report_agent_v1.md"),
    Path("docs/13_agents/strategy_spec_agent_v1.md"),
    Path("docs/13_agents/llm_provider_and_cassette_v1.md"),
    Path("docs/13_agents/llm_live_rollout_v1.md"),
    Path("docs/13_agents/promptpack_and_regression_v1.md"),
    Path("docs/13_agents/llm_budget_and_usage_v1.md"),
    Path("docs/14_trace_preview/trace_preview_v1.md"),
    Path("docs/15_improvement/improvement_agent_v1.md"),
    Path("docs/16_budget_stop/budget_policy_v1.md"),
    Path("docs/09_adr/0000_template.md"),
    Path("docs/09_adr/0003_job_event_contract_evolution.md"),
    Path("docs/09_adr/0004_runspec_and_gate_results_v2.md"),
    Path("docs/_snippets/codex_phase_footer.md"),
    Path("GOVERNANCE.md"),
]


def main() -> int:
    repo_root = Path.cwd()
    missing: list[Path] = []
    for rel in REQUIRED_FILES:
        p = repo_root / rel
        if not p.is_file():
            missing.append(rel)

    if missing:
        print("Missing required docs files:", file=sys.stderr)
        for rel in missing:
            print(f"- {rel.as_posix()}", file=sys.stderr)
        return 2

    print("docs tree: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
