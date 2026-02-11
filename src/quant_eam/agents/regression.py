from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.agents.harness import run_agent


EXIT_OK = 0
EXIT_INVALID = 2


def _canon(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _bundle_from_out(agent_id: str, out_dir: Path) -> dict[str, Any]:
    agent_id = str(agent_id).strip()
    if agent_id == "intent_agent_v1":
        bp = _load_json(out_dir / "blueprint_draft.json")
        return {"blueprint_draft": bp}
    if agent_id == "strategy_spec_agent_v1":
        bf = _load_json(out_dir / "blueprint_final.json")
        dsl = _load_json(out_dir / "signal_dsl.json")
        vd = _load_json(out_dir / "variable_dictionary.json")
        tp = _load_json(out_dir / "calc_trace_plan.json")
        return {"blueprint_final": bf, "signal_dsl": dsl, "variable_dictionary": vd, "calc_trace_plan": tp}
    if agent_id == "report_agent_v1":
        md = (out_dir / "report_agent.md").read_text(encoding="utf-8")
        summ = _load_json(out_dir / "report_summary.json")
        return {"report_md": md, "report_summary": summ}
    if agent_id == "improvement_agent_v1":
        props = _load_json(out_dir / "improvement_proposals.json")
        return {"improvement_proposals": props}
    raise ValueError(f"unsupported agent_id: {agent_id}")


@dataclass(frozen=True)
class CaseResult:
    case_dir: Path
    out_dir: Path
    passed: bool
    message: str


def run_regression_cases(*, agent_id: str, cases_dir: Path, out_root: Path, provider: str = "mock") -> list[CaseResult]:
    cases_dir = Path(cases_dir)
    out_root = Path(out_root)
    if not cases_dir.is_dir():
        raise FileNotFoundError(cases_dir.as_posix())

    case_dirs = sorted([p for p in cases_dir.iterdir() if p.is_dir()])
    results: list[CaseResult] = []
    for case_dir in case_dirs:
        expected_p = case_dir / "expected_output.json"
        input_p = case_dir / "input.json"
        if not expected_p.is_file() or not input_p.is_file():
            # Ignore non-case directories.
            continue

        # Some agents use a non-input.json anchor file; keep fixtures still providing input.json.
        actual_input_p = input_p
        if agent_id == "report_agent_v1":
            dm = case_dir / "dossier_manifest.json"
            if dm.is_file():
                actual_input_p = dm

        out_dir = out_root / agent_id / case_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        _ = run_agent(agent_id=agent_id, input_path=actual_input_p, out_dir=out_dir, provider=provider)

        actual = _bundle_from_out(agent_id, out_dir)
        expected = _load_json(expected_p)

        if _canon(actual) != _canon(expected):
            results.append(
                CaseResult(
                    case_dir=case_dir,
                    out_dir=out_dir,
                    passed=False,
                    message="output mismatch vs expected_output.json",
                )
            )
        else:
            results.append(CaseResult(case_dir=case_dir, out_dir=out_dir, passed=True, message="ok"))

    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline regression runner for harnessed agents (Phase-19).")
    ap.add_argument("--agent", required=True, help="agent id (e.g. intent_agent_v1)")
    ap.add_argument("--cases", required=True, help="cases dir (e.g. tests/fixtures/agents/<agent_id>)")
    ap.add_argument("--out-root", default=os.getenv("EAM_AGENT_REGRESSION_OUT", ".eam_regression_out"))
    ap.add_argument("--provider", default="mock", choices=["mock"], help="provider for harness (offline only)")
    args = ap.parse_args(argv)

    agent_id = str(args.agent).strip()
    cases_dir = Path(str(args.cases))
    out_root = Path(str(args.out_root))

    results = run_regression_cases(agent_id=agent_id, cases_dir=cases_dir, out_root=out_root, provider=str(args.provider))
    if not results:
        print("no cases found")
        return EXIT_INVALID

    bad = [r for r in results if not r.passed]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{status} case={r.case_dir.name} out={r.out_dir.as_posix()} msg={r.message}")

    return EXIT_OK if not bad else EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())

