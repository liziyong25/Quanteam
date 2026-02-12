from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_qa_fetch_registry_json.py"
REGISTRY_PATH = REPO_ROOT / "docs" / "05_data_plane" / "qa_fetch_registry_v1.json"


def _run_registry_script(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def test_phase27_check_mode_passes_for_checked_in_registry() -> None:
    cp = _run_registry_script("--check")
    assert cp.returncode == 0, cp.stderr
    assert "in sync" in cp.stdout


def test_phase27_check_mode_fails_for_semantic_drift(tmp_path: Path) -> None:
    drifted_doc = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    drifted_doc["naming"]["default_adjust"] = "hfq"

    drifted_path = tmp_path / "qa_fetch_registry_v1.json"
    drifted_path.write_text(
        json.dumps(drifted_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    cp = _run_registry_script("--check", "--registry-path", str(drifted_path))
    assert cp.returncode == 1
    assert "drift detected" in cp.stderr
