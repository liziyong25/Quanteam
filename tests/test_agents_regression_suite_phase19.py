from __future__ import annotations

from pathlib import Path

from quant_eam.agents.regression import run_regression_cases


def test_phase19_regression_runner_fixtures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")

    cases_dir = Path("tests/fixtures/agents/intent_agent_v1")
    out_root = tmp_path / "out"
    results = run_regression_cases(agent_id="intent_agent_v1", cases_dir=cases_dir, out_root=out_root, provider="mock")
    assert results
    assert all(r.passed for r in results), [f"{r.case_dir.name}: {r.message}" for r in results]

    cases_dir2 = Path("tests/fixtures/agents/strategy_spec_agent_v1")
    results2 = run_regression_cases(agent_id="strategy_spec_agent_v1", cases_dir=cases_dir2, out_root=out_root, provider="mock")
    assert results2
    assert all(r.passed for r in results2), [f"{r.case_dir.name}: {r.message}" for r in results2]
