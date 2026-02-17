from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_report_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    """Generate report.md + report_summary.json from a dossier directory reference.

    input_path points to dossier_manifest.json (deterministic anchor); other artifacts are resolved relative to it.
    """
    if provider != "mock":
        raise ValueError("ReportAgent MVP supports provider=mock only")

    input_path = Path(input_path)
    if input_path.name != "dossier_manifest.json":
        raise ValueError("ReportAgent input_path must point to dossier_manifest.json")
    dossier_dir = input_path.parent

    dossier_manifest = _load_json(input_path)
    if not isinstance(dossier_manifest, dict):
        raise ValueError("dossier_manifest.json must be a JSON object")

    # Evidence references (must exist; fail hard if missing).
    metrics_path = dossier_dir / "metrics.json"
    gate_path = dossier_dir / "gate_results.json"
    curve_path = dossier_dir / "curve.csv"
    trades_path = dossier_dir / "trades.csv"

    for p in (metrics_path, gate_path, curve_path, trades_path):
        if not p.is_file():
            raise ValueError(f"missing required artifact: {p.name}")

    metrics = _load_json(metrics_path)
    gate_results = _load_json(gate_path)

    overall_pass = bool(gate_results.get("overall_pass")) if isinstance(gate_results, dict) else False
    results = gate_results.get("results") if isinstance(gate_results, dict) else []
    failed = []
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict) and (not bool(r.get("pass"))):
                failed.append(str(r.get("gate_id") or "unknown"))

    total_return = metrics.get("total_return") if isinstance(metrics, dict) else None
    max_drawdown = metrics.get("max_drawdown") if isinstance(metrics, dict) else None
    sharpe = metrics.get("sharpe") if isinstance(metrics, dict) else None
    trade_count = metrics.get("trade_count") if isinstance(metrics, dict) else None

    holdout_summary = gate_results.get("holdout_summary") if isinstance(gate_results, dict) else None
    holdout_line = ""
    if isinstance(holdout_summary, dict):
        holdout_line = f"- holdout_summary: pass={bool(holdout_summary.get('pass'))} summary={str(holdout_summary.get('summary',''))}\n"

    run_id = str(dossier_manifest.get("run_id", ""))

    md = []
    md.append("# Report (ReportAgent v1, deterministic)\n")
    md.append("## Evidence (SSOT)\n")
    md.append(f"- dossier_dir: `{dossier_dir.as_posix()}`\n")
    md.append(f"- artifacts:\n")
    md.append(f"  - `dossier_manifest.json` (run_id={run_id})\n")
    md.append("  - `metrics.json`\n")
    md.append("  - `curve.csv`\n")
    md.append("  - `trades.csv`\n")
    md.append("  - `gate_results.json`\n")
    md.append("\n")

    md.append("## Gate Results\n")
    md.append(f"- overall_pass: `{overall_pass}` (from `gate_results.json`)\n")
    if failed:
        md.append(f"- failed_gates: {', '.join(failed)} (from `gate_results.json`)\n")
    else:
        md.append("- failed_gates: (none)\n")
    if holdout_line:
        md.append(holdout_line)
    md.append("\n")

    md.append("## Key Metrics (from metrics.json)\n")
    md.append(f"- total_return: `{total_return}`\n")
    md.append(f"- max_drawdown: `{max_drawdown}`\n")
    md.append(f"- sharpe: `{sharpe}`\n")
    md.append(f"- trade_count: `{trade_count}`\n")
    md.append("\n")

    md.append("## Notes\n")
    md.append("- This report contains no free-form arbitration; all statements reference artifacts.\n")

    # Phase-24: deterministic attribution evidence written into the dossier (SSOT, append-only).
    attribution_written: list[str] = []
    attribution_error: str | None = None
    try:
        from quant_eam.analysis.attribution_v1 import write_attribution_artifacts

        outp = write_attribution_artifacts(dossier_dir=dossier_dir)
        attribution_written = [p.relative_to(dossier_dir).as_posix() for p in outp if p.is_file()]
    except Exception as e:  # noqa: BLE001
        attribution_error = str(e)

    md.append("\n")
    md.append("## Attribution (Phase-24)\n")
    if attribution_written:
        md.append("- attribution artifacts written (dossier):\n")
        for rel in attribution_written:
            md.append(f"  - `{rel}`\n")
    elif attribution_error:
        md.append(f"- attribution generation failed: `{attribution_error}`\n")
    else:
        md.append("- attribution artifacts: (no-op; already present)\n")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_md = out_dir / "report_agent.md"
    report_md.write_text("".join(md), encoding="utf-8")

    summary = {
        "run_id": run_id,
        "overall_pass": overall_pass,
        "failed_gates": failed,
        "metrics": {
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "trade_count": trade_count,
        },
        "artifacts": {
            "dossier_manifest": str(input_path.name),
            "metrics": str(metrics_path.name),
            "curve": str(curve_path.name),
            "trades": str(trades_path.name),
            "gate_results": str(gate_path.name),
        },
    }
    summary_path = out_dir / "report_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # ReportAgent outputs are not contracts; only agent_run.json is validated.
    # Still, ensure gate_results contract is valid (defensive).
    code, msg = contracts_validate.validate_json(gate_path)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"gate_results invalid (ReportAgent refuses to proceed): {msg}")

    return [report_md, summary_path]
