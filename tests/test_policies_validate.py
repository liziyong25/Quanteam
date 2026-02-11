from __future__ import annotations

from pathlib import Path

from quant_eam.policies import validate


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_single_policy_ok() -> None:
    p = _repo_root() / "policies" / "execution_policy_v1.yaml"
    assert validate.main([str(p)]) == validate.EXIT_OK


def test_policy_version_wrong_is_invalid() -> None:
    p = _repo_root() / "policies" / "examples" / "execution_policy_version_bad.yaml"
    assert validate.main([str(p)]) == validate.EXIT_INVALID


def test_bundle_ok() -> None:
    p = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    assert validate.main([str(p)]) == validate.EXIT_OK


def test_bundle_missing_reference_is_invalid() -> None:
    p = _repo_root() / "policies" / "examples" / "policy_bundle_missing_ref_bad.yaml"
    assert validate.main([str(p)]) == validate.EXIT_INVALID


def test_gate_suite_holdout_output_wrong_is_invalid() -> None:
    p = _repo_root() / "policies" / "examples" / "gate_suite_holdout_output_bad.yaml"
    assert validate.main([str(p)]) == validate.EXIT_INVALID


def test_asof_rule_wrong_is_invalid() -> None:
    p = _repo_root() / "policies" / "examples" / "asof_rule_bad.yaml"
    assert validate.main([str(p)]) == validate.EXIT_INVALID


def test_bundle_inline_params_is_invalid(tmp_path: Path) -> None:
    p = tmp_path / "bundle_inline_params.yaml"
    p.write_text(
        "\n".join(
            [
                "policy_bundle_id: bundle_inline_params_bad",
                'policy_version: "v1"',
                "params:",
                "  execution_policy_id: execution_policy_v1_default",
                "execution_policy_id: execution_policy_v1_default",
                "cost_policy_id: cost_policy_v1_default",
                "asof_latency_policy_id: asof_latency_policy_v1_default",
                "risk_policy_id: risk_policy_v1_default",
                "gate_suite_id: gate_suite_v1_default",
                "",
            ]
        ),
        encoding="utf-8",
    )
    assert validate.main([str(p)]) == validate.EXIT_INVALID


def test_duplicate_policy_id_in_directory_is_invalid(tmp_path: Path) -> None:
    # Build an isolated policies dir with duplicate ids.
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()

    pol1 = pol_dir / "execution_policy_v1.yaml"
    pol1.write_text(
        "\n".join(
            [
                "policy_id: dup_policy",
                'policy_version: "v1"',
                "title: One",
                "description: One",
                "params:",
                "  order_timing: next_open",
                "  allow_short: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    pol2 = pol_dir / "execution_policy_v1_copy.yaml"
    pol2.write_text(
        "\n".join(
            [
                "policy_id: dup_policy",
                'policy_version: "v1"',
                "title: Two",
                "description: Two",
                "params:",
                "  order_timing: next_open",
                "  allow_short: false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    bundle = tmp_path / "policy_bundle_v1.yaml"
    bundle.write_text(
        "\n".join(
            [
                "policy_bundle_id: bundle_with_dups",
                'policy_version: "v1"',
                "execution_policy_id: dup_policy",
                "cost_policy_id: dup_policy",
                "asof_latency_policy_id: dup_policy",
                "risk_policy_id: dup_policy",
                "gate_suite_id: dup_policy",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert (
        validate.main(["--policies-dir", str(pol_dir), str(bundle)]) == validate.EXIT_INVALID
    )


def test_lock_tamper_detection_for_bundle(tmp_path: Path) -> None:
    repo = _repo_root()
    src_dir = repo / "policies"
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()

    # Copy v1 YAML assets only (exclude examples).
    for p in src_dir.glob("*_v1.y*ml"):
        (pol_dir / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    # Write lock for the tmp policies dir.
    assert validate.main(["--write-lock", str(pol_dir)]) == validate.EXIT_OK

    bundle = pol_dir / "policy_bundle_v1.yaml"
    assert validate.main(["--policies-dir", str(pol_dir), str(bundle)]) == validate.EXIT_OK

    # Tamper with a referenced policy file -> bundle validation must fail due to sha mismatch.
    cost = pol_dir / "cost_policy_v1.yaml"
    cost.write_text(cost.read_text(encoding="utf-8").replace("slippage_bps: 2.0", "slippage_bps: 2.5"), encoding="utf-8")
    assert validate.main(["--policies-dir", str(pol_dir), str(bundle)]) == validate.EXIT_INVALID


def test_validate_directory_fails_if_any_bad_present(tmp_path: Path) -> None:
    repo = _repo_root()
    src_dir = repo / "policies"
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()

    for p in src_dir.glob("*_v1.y*ml"):
        (pol_dir / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    # Introduce a bad v1 policy file into the directory.
    bad = repo / "policies" / "examples" / "asof_rule_bad.yaml"
    (pol_dir / "asof_latency_policy_v1.yaml").write_text(bad.read_text(encoding="utf-8"), encoding="utf-8")

    assert validate.main([str(pol_dir)]) == validate.EXIT_INVALID
