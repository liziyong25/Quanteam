from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _finding(fid: str, severity: str, path: str, message: str) -> dict[str, str]:
    return {
        "id": fid,
        "severity": severity,
        "path": path,
        "message": message,
    }


def _build_report(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    required_keys = ("blueprint_final", "signal_dsl", "variable_dictionary", "calc_trace_plan")
    for key in required_keys:
        ok = isinstance(payload.get(key), dict)
        checks.append({"name": f"input.{key}.exists", "pass": bool(ok)})
        if not ok:
            findings.append(_finding("missing_required_input", "error", f"/{key}", f"missing {key} object"))

    idea = payload.get("idea_spec") if isinstance(payload.get("idea_spec"), dict) else {}
    symbols = idea.get("symbols") if isinstance(idea.get("symbols"), list) else []
    checks.append({"name": "idea_spec.symbols.non_empty", "pass": bool(symbols)})
    if not symbols:
        findings.append(_finding("empty_symbols", "warn", "/idea_spec/symbols", "idea_spec.symbols should be non-empty"))

    vd = payload.get("variable_dictionary") if isinstance(payload.get("variable_dictionary"), dict) else {}
    vars_rows = vd.get("variables") if isinstance(vd.get("variables"), list) else []
    checks.append({"name": "variable_dictionary.variables.non_empty", "pass": bool(vars_rows)})
    if not vars_rows:
        findings.append(_finding("empty_variable_dictionary", "warn", "/variable_dictionary/variables", "variables list is empty"))

    plan = payload.get("calc_trace_plan") if isinstance(payload.get("calc_trace_plan"), dict) else {}
    formula_count = 0
    if isinstance(plan.get("formulas"), list):
        formula_count = len(plan["formulas"])
    checks.append({"name": "calc_trace_plan.formulas.non_empty", "pass": formula_count > 0})
    if formula_count == 0:
        findings.append(_finding("empty_calc_trace_plan", "warn", "/calc_trace_plan/formulas", "formulas list is empty"))

    error_count = sum(1 for f in findings if f.get("severity") == "error")
    warn_count = sum(1 for f in findings if f.get("severity") == "warn")
    overall = "pass" if error_count == 0 else "fail"

    return {
        "schema_version": "spec_qa_report_v1",
        "agent_id": "spec_qa_agent_v1",
        "overall": overall,
        "summary": {
            "finding_count": len(findings),
            "error_count": error_count,
            "warn_count": warn_count,
        },
        "checks": checks,
        "findings": findings,
        "notes": [
            "Spec-QA is read-only and does not mutate contracts/policies.",
            "Findings are append-only evidence for checkpoint review.",
        ],
    }


def _report_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Spec-QA Report")
    lines.append("")
    lines.append(f"- overall: `{report.get('overall')}`")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines.append(f"- finding_count: `{summary.get('finding_count', 0)}`")
    lines.append(f"- error_count: `{summary.get('error_count', 0)}`")
    lines.append(f"- warn_count: `{summary.get('warn_count', 0)}`")
    lines.append("")
    lines.append("## Checks")
    checks = report.get("checks") if isinstance(report.get("checks"), list) else []
    if checks:
        for c in checks:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name") or "")
            passed = bool(c.get("pass"))
            lines.append(f"- [{'x' if passed else ' '}] {name}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Findings")
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    if findings:
        for f in findings:
            if not isinstance(f, dict):
                continue
            lines.append(
                f"- `{f.get('severity')}` `{f.get('id')}` `{f.get('path')}`: {f.get('message')}"
            )
    else:
        lines.append("- no findings")
    lines.append("")
    return "\n".join(lines)


def run_spec_qa_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    if str(provider).strip() != "mock":
        raise ValueError("provider 'external' is not supported in spec_qa_agent MVP")
    payload = _load_json(Path(input_path))
    if not isinstance(payload, dict):
        raise ValueError("spec_qa input must be a JSON object")

    report = _build_report(payload)
    report_path = Path(out_dir) / "spec_qa_report.json"
    report_md_path = Path(out_dir) / "spec_qa_report.md"
    _write_json(report_path, report)
    _write_text(report_md_path, _report_markdown(report))
    return [report_path, report_md_path]
