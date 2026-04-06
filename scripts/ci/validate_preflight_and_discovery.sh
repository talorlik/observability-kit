#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 3 preflight and discovery artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

ROOT = Path(".")
base = ROOT / "contracts" / "discovery"
compat_base = ROOT / "contracts" / "compatibility"

preflight = json.loads((base / "PREFLIGHT_REPORT_SAMPLE.json").read_text())
probes = json.loads((base / "DISCOVERY_PROBES_SAMPLE.json").read_text())
capabilities = json.loads((base / "GENERATED_CAPABILITY_MATRIX.json").read_text())
compat_result = json.loads((base / "GENERATED_COMPATIBILITY_RESULT.json").read_text())
readiness = json.loads((base / "READINESS_REPORT_SCAFFOLD.json").read_text())
mode_table = json.loads((compat_base / "MODE_DECISION_TABLE.json").read_text())
remediation_catalog = json.loads(
    (compat_base / "REMEDIATION_CATALOG.json").read_text()
)

ALLOWED_PREFLIGHT = {"pass", "fail"}
ALLOWED_GRADES = {"supported", "conditional", "blocked"}
ALLOWED_READINESS = {"pending", "pass", "fail"}
SUPPORTED_MODES = set(mode_table["metadata"]["supported_modes"])


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: Preflight pass/fail reporting.
checks = preflight.get("checks", [])
if not checks:
    fail("Preflight report must include checks.")

statuses = [c.get("status") for c in checks]
if any(status not in ALLOWED_PREFLIGHT for status in statuses):
    fail("Preflight checks only allow pass/fail status values.")
if "pass" not in statuses or "fail" not in statuses:
    fail("Preflight sample must demonstrate both pass and fail outcomes.")

summary = preflight.get("summary", {})
if summary.get("pass") != statuses.count("pass"):
    fail("Preflight summary pass count does not match checks.")
if summary.get("fail") != statuses.count("fail"):
    fail("Preflight summary fail count does not match checks.")
if summary.get("outcome") not in {"pass", "fail"}:
    fail("Preflight summary outcome must be pass or fail.")


# Tasks 2-4: Discovery probes for capabilities and workloads.
probes_root = probes.get("probes", {})
for key in {"storage_and_ingress", "gitops_and_secrets", "workload_inventory"}:
    if key not in probes_root:
        fail(f"Discovery probes missing required section: {key}")

storage_classes = probes_root["storage_and_ingress"].get("storage_classes", [])
if not storage_classes:
    fail("Discovery must list storage classes.")
default_storage = [item["name"] for item in storage_classes if item.get("default")]
if len(default_storage) != 1:
    fail("Discovery must mark exactly one default storage class.")

gitops_detected = [
    item["name"]
    for item in probes_root["gitops_and_secrets"].get("gitops_controllers", [])
    if item.get("detected")
]
if not gitops_detected:
    fail("Discovery must detect at least one GitOps controller.")

secrets_detected = [
    item["name"]
    for item in probes_root["gitops_and_secrets"].get("secret_integrations", [])
    if item.get("detected")
]
if not secrets_detected:
    fail("Discovery must detect at least one secret integration.")

services = probes_root["workload_inventory"].get("services", [])
if not services:
    fail("Workload inventory must include services.")
if not any(service.get("onboardable_candidate") for service in services):
    fail("Workload inventory must include onboardable candidates.")


# Task 5: Generated outputs for capability + compatibility + mode + remediation.
caps = capabilities.get("capabilities", {})
required_caps = {
    "storage_profile_candidates",
    "default_storage_profile",
    "ingress_profile_candidates",
    "default_ingress_profile",
    "gitops_controller_candidates",
    "default_gitops_controller",
    "secret_profile_candidates",
    "default_secret_profile",
}
if not required_caps.issubset(caps.keys()):
    fail("Generated capability matrix is missing required keys.")

if caps["default_storage_profile"] not in caps["storage_profile_candidates"]:
    fail("Capability matrix default storage profile is invalid.")
if caps["default_gitops_controller"] not in caps["gitops_controller_candidates"]:
    fail("Capability matrix default GitOps controller is invalid.")
if caps["default_secret_profile"] not in caps["secret_profile_candidates"]:
    fail("Capability matrix default secret profile is invalid.")
if caps["default_ingress_profile"] not in caps["ingress_profile_candidates"]:
    fail("Capability matrix default ingress profile is invalid.")

result = compat_result.get("compatibility_result", {})
if result.get("grade") not in ALLOWED_GRADES:
    fail("Generated compatibility grade must be supported/conditional/blocked.")
if result.get("recommended_deployment_mode") not in SUPPORTED_MODES:
    fail("Generated mode recommendation must match supported modes.")
if not isinstance(result.get("remediation_list"), list):
    fail("Generated remediation list must be a list.")

reasons = result.get("reasons", [])
catalog = remediation_catalog.get("remediations", {})
for reason in reasons:
    if reason not in catalog:
        fail(f"Generated compatibility reason has no remediation mapping: {reason}")


# Task 6: Readiness report scaffold emitted after dry-run install.
if readiness.get("metadata", {}).get("emitted_after") != "dry-run-install":
    fail("Readiness report scaffold must be emitted after dry-run install.")

sections = readiness.get("readiness_sections", [])
if len(sections) < 3:
    fail("Readiness report scaffold must include baseline readiness sections.")
for section in sections:
    if section.get("status") not in ALLOWED_READINESS:
        fail("Readiness section status must be pending/pass/fail.")

print("Batch 3 preflight and discovery checks passed.")
PY
