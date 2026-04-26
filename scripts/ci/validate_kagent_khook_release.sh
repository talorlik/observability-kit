#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 10 productization and release scaffolding..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
import json
import sys
import tempfile

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
install_schema_path = root / "contracts" / "install" / "INSTALL_CONTRACT_SCHEMA.json"
install_modes_path = (
    root / "install" / "profiles" / "ai-runtime" / "INSTALL_MODE_CONTRACTS_V1.json"
)
mode_rules_path = root / "install" / "discovery-engine" / "mode_recommendation_rules.yaml"
compat_matrix_path = (
    root / "install" / "profiles" / "compatibility" / "COMPATIBILITY_MATRIX.yaml"
)
release_suite_path = root / "tests" / "safety" / "RELEASE_VALIDATION_SUITE_V1.json"
perf_upgrade_suite_path = root / "tests" / "perf" / "ai_runtime" / "PERF_UPGRADE_SUITE_V1.json"
approval_runbook_path = root / "docs" / "runbooks" / "AI_APPROVAL_FLOW_RUNBOOK.md"
install_runbook_path = root / "docs" / "runbooks" / "INSTALL_RUNBOOK.md"
rollback_runbook_path = root / "docs" / "runbooks" / "ROLLBACK_UNINSTALL_RUNBOOK.md"
signoff_path = (
    root / "docs" / "operations" / "PRODUCTION_ACTIVATION_SIGNOFF_WORKFLOW.md"
)

for required in [
    install_schema_path,
    install_modes_path,
    mode_rules_path,
    compat_matrix_path,
    release_suite_path,
    perf_upgrade_suite_path,
    approval_runbook_path,
    install_runbook_path,
    rollback_runbook_path,
    signoff_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 10 artifact: {required}")

install_schema = json.loads(install_schema_path.read_text(encoding="utf-8"))
install_modes = json.loads(install_modes_path.read_text(encoding="utf-8"))
mode_rules = yaml.safe_load(mode_rules_path.read_text(encoding="utf-8"))
compat_matrix = yaml.safe_load(compat_matrix_path.read_text(encoding="utf-8"))
release_suite = json.loads(release_suite_path.read_text(encoding="utf-8"))
perf_upgrade_suite = json.loads(perf_upgrade_suite_path.read_text(encoding="utf-8"))
approval_runbook = approval_runbook_path.read_text(encoding="utf-8")
install_runbook = install_runbook_path.read_text(encoding="utf-8")
rollback_runbook = rollback_runbook_path.read_text(encoding="utf-8")
signoff = signoff_path.read_text(encoding="utf-8")

# 1) Validate install mode contract schemas.
required_install_fields = {"deployment_mode", "cluster_name", "environment"}
schema_required = set(install_schema.get("required", []))
if not required_install_fields.issubset(schema_required):
    fail("Install contract schema missing required install fields.")

supported_modes = set(install_modes.get("supported_modes", []))
expected_modes = {"quickstart", "attach", "standalone", "hybrid"}
if supported_modes != expected_modes:
    fail("Install mode contract must define quickstart/attach/standalone/hybrid.")
mode_contracts = install_modes.get("mode_contracts", {})
for mode in expected_modes:
    contract = mode_contracts.get(mode)
    if not contract:
        fail(f"Install mode contract missing mode definition: {mode}")
    if not contract.get("required_inputs"):
        fail(f"Install mode {mode} missing required_inputs.")
    if not contract.get("outputs"):
        fail(f"Install mode {mode} missing outputs.")

# 2) Validate capability discovery-to-overlay determinism.
rule_modes = set(mode_rules.get("supported_modes", []))
if rule_modes != expected_modes:
    fail("Mode recommendation rules supported_modes drift from install mode contracts.")
rules = mode_rules.get("rules", [])
if len(rules) < 3:
    fail("Mode recommendation rules must include deterministic rule set.")
fallback = mode_rules.get("fallback", {})
if fallback.get("recommend") not in expected_modes:
    fail("Mode recommendation fallback must be one of supported modes.")

with tempfile.TemporaryDirectory(prefix="batch10_det_") as tmp:
    base = Path(tmp)
    preflight_out = base / "preflight.json"
    out1 = base / "out1"
    out2 = base / "out2"
    out1.mkdir(parents=True, exist_ok=True)
    out2.mkdir(parents=True, exist_ok=True)

    from subprocess import run

    run(
        [
            "python3",
            "install/discovery-engine/preflight_checks.py",
            "--input",
            "tests/smoke/platform_smoke_bundle/reference_cluster_profile.json",
            "--output",
            str(preflight_out),
        ],
        check=True,
    )
    cmd = [
        "python3",
        "install/discovery-engine/report_generator.py",
        "--preflight",
        str(preflight_out),
        "--probes",
        "contracts/discovery/DISCOVERY_PROBES_SAMPLE.json",
        "--mode-table",
        "contracts/compatibility/MODE_DECISION_TABLE.json",
        "--remediations",
        "contracts/compatibility/REMEDIATION_CATALOG.json",
    ]
    run(cmd + ["--output-dir", str(out1)], check=True)
    run(cmd + ["--output-dir", str(out2)], check=True)

    result1 = json.loads((out1 / "GENERATED_COMPATIBILITY_RESULT.json").read_text())
    result2 = json.loads((out2 / "GENERATED_COMPATIBILITY_RESULT.json").read_text())
    if result1 != result2:
        fail("Discovery-to-overlay generation must be deterministic for same inputs.")

# 3) Validate compatibility matrix state definitions.
grading = compat_matrix.get("grading", {})
for state in ["supported", "conditional", "blocked"]:
    if state not in grading:
        fail(f"Compatibility matrix grading missing state: {state}")
if not compat_matrix.get("kubernetes", {}).get("supported"):
    fail("Compatibility matrix must define supported Kubernetes versions.")
if not compat_matrix.get("distributions", {}).get("supported"):
    fail("Compatibility matrix must define supported distributions.")

# 4) Validate release suite coverage (functional/safety/performance/upgrade).
coverage = release_suite.get("coverage", {})
for section in ["functional", "safety", "performance", "upgrade"]:
    if section not in coverage or not coverage.get(section):
        fail(f"Release validation suite missing required coverage section: {section}")
if perf_upgrade_suite.get("suite") != "ai-runtime-perf-upgrade-v1":
    fail("Performance/upgrade suite must use ai-runtime-perf-upgrade-v1.")

# 5) Validate operator runbook completeness.
if "validate_install_contract.sh" not in install_runbook:
    fail("Install runbook must include install contract validation command.")
for token in [
    "validate_compatibility_and_modes.sh",
    "validate_preflight_and_discovery.sh",
    "kubectl apply -f gitops/apps/platform-core-application.yaml",
]:
    if token not in install_runbook:
        fail(f"Install runbook missing required install workflow token: {token}")
if "approval" not in approval_runbook.lower():
    fail("Approval flow runbook must include approval workflow guidance.")
if "rollback" not in rollback_runbook.lower() or "uninstall" not in rollback_runbook.lower():
    fail("Rollback runbook must include rollback and uninstall guidance.")
for token in [
    "validate_kagent_khook_release.sh",
    "argocd app rollback platform-core",
    "kubectl -n argocd delete application platform-core",
    "kubectl delete namespace observability-system ai-runtime ai-triggers mcp-system mcp-services ai-gateway ai-policy --ignore-not-found",
]:
    if token not in rollback_runbook:
        fail(f"Rollback/uninstall runbook missing required command token: {token}")

# 6) Validate final production activation gate sign-off workflow.
required_tokens = [
    "validate_kagent_khook_release.sh",
    "approved",
    "hold",
    "rejected",
    "signoff",
]
for token in required_tokens:
    if token not in signoff:
        fail(f"Production activation signoff workflow missing token: {token}")

workflow = (root / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
batch10_smoke = (root / "scripts" / "ci" / "validate_batch10_smoke.sh").read_text(
    encoding="utf-8"
)
if "validate_kagent_khook_release.sh" not in workflow:
    fail("Main CI workflow must include Kagent Khook release validator.")
if "validate_kagent_khook_release.sh" not in batch10_smoke:
    fail("Batch 10 smoke bundle must include Kagent Khook release validator.")

print("Batch 10 productization and release scaffold checks passed.")
PY
