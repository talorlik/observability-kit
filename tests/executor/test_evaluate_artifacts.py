#!/usr/bin/env python3
"""Offline fixture-driven tests for `obskit evaluate` (Batch 17, TR-18).

Covers the derived-artifact stage end to end:

- a chained preflight -> discover -> evaluate run emits all four
  contracted artifacts (capability matrix, compatibility result, mode
  recommendation, remediation list);
- grading reproduces every GRADING_RULES.json
  sample_cluster_evaluations entry exactly (grade and reason order);
- mode resolution reproduces every MODE_DECISION_TABLE.json
  sample_decisions entry;
- every emitted remediation action string comes verbatim from
  REMEDIATION_CATALOG.json (hardcoded_decision_rules: forbidden).

Owned by scripts/ci/validate_discovery_executor.sh.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "executor" / "fixtures"
CONTRACTS = ROOT / "contracts"

sys.path.insert(0, str(ROOT / "tools" / "obskit"))

from obskit import evaluate as evaluate_module  # noqa: E402

EXPECTED_ARTIFACTS = [
    "capability_matrix.json",
    "compatibility_result.json",
    "mode_recommendation.json",
    "remediation_list.json",
]


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "tools" / "obskit")
    return env


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", "-m", "obskit.cli", *args],
        cwd=ROOT,
        env=_cli_env(),
        capture_output=True,
        text=True,
    )


def run_chain(workdir: Path) -> dict[str, dict]:
    """Chained run; returns every artifact parsed, keyed by filename."""
    preflight_path = workdir / "preflight_report.json"
    discovery_path = workdir / "discovery_probes.json"
    eval_dir = workdir / "evaluation"

    proc = _run_cli([
        "preflight",
        "--snapshot", str(FIXTURES / "snapshot_preflight_pass.json"),
        "--output", str(preflight_path),
    ])
    assert proc.returncode == 0, proc.stderr
    proc = _run_cli([
        "discover",
        "--snapshot", str(FIXTURES / "snapshot_discovery_reference.json"),
        "--output", str(discovery_path),
    ])
    assert proc.returncode == 0, proc.stderr
    proc = _run_cli([
        "evaluate",
        "--preflight", str(preflight_path),
        "--discovery", str(discovery_path),
        "--contracts-dir", str(CONTRACTS),
        "--profiles", str(FIXTURES / "profiles_reference.json"),
        "--output-dir", str(eval_dir),
    ])
    assert proc.returncode == 0, proc.stderr

    artifacts: dict[str, dict] = {}
    for filename in EXPECTED_ARTIFACTS:
        path = eval_dir / filename
        assert path.is_file(), f"missing artifact {filename}"
        artifacts[filename] = json.loads(path.read_text())
    return artifacts


def test_chained_run_emits_four_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifacts = run_chain(Path(tmp))

    matrix = artifacts["capability_matrix.json"]["capabilities"]
    # Candidates must mirror the discovery detections of the reference
    # snapshot; defaults must come from the candidates.
    assert matrix["gitops_controller_candidates"] == ["argocd"]
    assert matrix["default_gitops_controller"] == "argocd"
    assert matrix["default_storage_profile"] == "standard-rwo"
    assert "standard-rwo" in matrix["storage_profile_candidates"]

    compat = artifacts["compatibility_result.json"]["compatibility_result"]
    # Batch 23 added "kind" to the distribution matrix as conditional
    # (disposable evidence harness only, ADR-0007), so the reference
    # chain grades conditional with exactly that contract reason code.
    # Blocked-grade coverage lives in the sample cluster evaluations.
    assert compat["grade"] == "conditional", compat
    assert compat["reasons"] == (
        ["disposable_evidence_harness_only"]
    ), compat

    mode = artifacts["mode_recommendation.json"]
    decision = mode["decision"]
    inputs = mode["inputs"]
    # Argo CD detected + onboardable services -> derived
    # has_compatible_existing_services=true; defaults keep in-cluster
    # collectors, so the table resolves hybrid.
    assert inputs["has_compatible_existing_services"] is True
    assert inputs["has_compatible_existing_services_source"] == "derived"
    assert decision["recommended_mode"] == "hybrid", decision
    assert decision["rule_id"] == "hybrid-shared-backend", decision
    assert compat["recommended_deployment_mode"] == (
        decision["recommended_mode"]
    )

    remediations = artifacts["remediation_list.json"]["remediations"]
    assert [entry["reason"] for entry in remediations] == (
        compat["reasons"]
    )


def test_grading_reproduces_all_sample_cluster_evaluations() -> None:
    contracts = evaluate_module.load_contracts(str(CONTRACTS))
    samples = json.loads(
        (CONTRACTS / "compatibility" / "GRADING_RULES.json").read_text()
    )["sample_cluster_evaluations"]
    assert len(samples) == 4, "expected the four contracted samples"
    for sample in samples:
        given = sample["input"]
        result = evaluate_module.grade_compatibility(
            kubernetes_version=given["kubernetes_version"],
            distribution=given["distribution"],
            profiles=given["profiles"],
            missing_prerequisites=given["missing_prerequisites"],
            extra_conditions=[],
            compatibility_matrix=contracts.compatibility_matrix,
            grading_rules=contracts.grading_rules,
        )
        expected = sample["expected_output"]
        assert result.grade == expected["grade"], sample["name"]
        assert list(result.reasons) == expected["reasons"], sample["name"]


def test_mode_resolution_reproduces_all_sample_decisions() -> None:
    contracts = evaluate_module.load_contracts(str(CONTRACTS))
    samples = json.loads(
        (CONTRACTS / "compatibility" / "MODE_DECISION_TABLE.json").read_text()
    )["sample_decisions"]
    assert len(samples) == 4, "expected the four contracted samples"
    for sample in samples:
        decision = evaluate_module.resolve_mode(
            sample["input"], contracts.mode_decision_table
        )
        assert decision.mode == sample["expected_mode"], sample["name"]


def test_remediation_actions_come_from_catalog() -> None:
    catalog = json.loads(
        (CONTRACTS / "compatibility" / "REMEDIATION_CATALOG.json").read_text()
    )["remediations"]
    with tempfile.TemporaryDirectory() as tmp:
        artifacts = run_chain(Path(tmp))

    for entry in artifacts["remediation_list.json"]["remediations"]:
        catalog_entry = catalog.get(entry["reason"])
        assert catalog_entry is not None, (
            f"reason {entry['reason']!r} not in remediation catalog"
        )
        assert entry["actions"] == catalog_entry["actions"], entry
        assert entry["severity"] == catalog_entry["severity"], entry

    # The flattened compatibility_result remediation strings must also
    # come verbatim from the catalog.
    compat = artifacts["compatibility_result.json"]["compatibility_result"]
    catalog_actions = {
        action
        for catalog_entry in catalog.values()
        for action in catalog_entry["actions"]
    }
    for action in compat["remediation_list"]:
        assert action in catalog_actions, f"non-catalog action {action!r}"


if __name__ == "__main__":
    test_chained_run_emits_four_artifacts()
    print("test_chained_run_emits_four_artifacts passed")
    test_grading_reproduces_all_sample_cluster_evaluations()
    print("test_grading_reproduces_all_sample_cluster_evaluations passed")
    test_mode_resolution_reproduces_all_sample_decisions()
    print("test_mode_resolution_reproduces_all_sample_decisions passed")
    test_remediation_actions_come_from_catalog()
    print("test_remediation_actions_come_from_catalog passed")
