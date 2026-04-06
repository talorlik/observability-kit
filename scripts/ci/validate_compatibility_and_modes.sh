#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 2 compatibility and mode artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

ROOT = Path(".")
base = ROOT / "contracts" / "compatibility"

matrix = json.loads((base / "COMPATIBILITY_MATRIX.json").read_text())
catalog = json.loads((base / "PROFILE_CATALOG.json").read_text())
grading = json.loads((base / "GRADING_RULES.json").read_text())
mode_table = json.loads((base / "MODE_DECISION_TABLE.json").read_text())
remediation = json.loads((base / "REMEDIATION_CATALOG.json").read_text())

allowed_status = {"supported", "conditional", "blocked"}
required_profile_keys = {
    "storage",
    "object_storage",
    "identity",
    "secret",
    "ingress_network",
    "gitops_controller",
}

def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)

def status_of(entries, key, value):
    for item in entries:
        if item.get(key) == value:
            return item.get("status"), item.get("conditions", [])
    return "blocked", []

def evaluate_grade(sample):
    reasons = []
    blocked = []
    inp = sample["input"]

    v_status, v_conditions = status_of(
        matrix["kubernetes"]["versions"], "version", inp["kubernetes_version"]
    )
    if v_status == "blocked":
        blocked.append("unsupported_kubernetes_version")
    elif v_status == "conditional":
        reasons.extend(v_conditions)

    d_status, d_conditions = status_of(
        matrix["kubernetes"]["distributions"], "name", inp["distribution"]
    )
    if d_status == "blocked":
        blocked.append("unsupported_distribution")
    elif d_status == "conditional":
        reasons.extend(d_conditions)

    profiles = inp["profiles"]
    if set(profiles.keys()) != required_profile_keys:
        blocked.append("missing_required_profile")
    else:
        for key, selected in profiles.items():
            entries = matrix["profiles"][key]
            p_status, p_conditions = status_of(entries, "id", selected)
            if p_status == "blocked":
                blocked.append("missing_required_profile")
            elif p_status == "conditional":
                reasons.extend(p_conditions)

    if inp.get("missing_prerequisites"):
        blocked.append("missing_prerequisite")

    if blocked:
        dedup = sorted(set(blocked))
        return {"grade": "blocked", "reasons": dedup}

    dedup = sorted(set(reasons))
    if dedup:
        return {"grade": "conditional", "reasons": dedup}
    return {"grade": "supported", "reasons": []}

def evaluate_mode(sample):
    rules = sorted(mode_table["rules"], key=lambda x: x["priority"])
    inp = sample["input"]
    for rule in rules:
        when = rule["when"]
        if all(inp.get(k) == v for k, v in when.items()):
            return rule["recommend"]
    fail(f"No mode rule matched sample: {sample['name']}")

# Coverage checks: compatibility matrix required dimensions and values.
if "kubernetes" not in matrix or "profiles" not in matrix:
    fail("Compatibility matrix must include kubernetes and profiles sections.")

if not matrix["kubernetes"].get("versions") or not matrix["kubernetes"].get("distributions"):
    fail("Compatibility matrix requires non-empty versions and distributions.")

if set(matrix["profiles"].keys()) != required_profile_keys:
    fail("Compatibility matrix profiles must cover all required profile categories.")

for section in [matrix["kubernetes"]["versions"], matrix["kubernetes"]["distributions"]]:
    for item in section:
        if item.get("status") not in {"supported", "conditional"}:
            fail("Matrix support entries must be supported or conditional.")

for key in required_profile_keys:
    for item in matrix["profiles"][key]:
        if item.get("status") not in {"supported", "conditional"}:
            fail(f"Profile matrix entry status invalid in {key}.")

# Profile catalog coverage and defaults.
if set(catalog.keys()) - {"metadata"} != required_profile_keys:
    fail("Profile catalog must contain all required profile categories.")

for key in required_profile_keys:
    section = catalog[key]
    default = section.get("default_profile")
    profiles = section.get("profiles", {})
    if not default or default not in profiles:
        fail(f"Profile catalog default missing or invalid for {key}.")
    for profile_name, profile in profiles.items():
        if not profile.get("prerequisites"):
            fail(f"Profile {key}.{profile_name} must list prerequisites.")

# Grading outputs behavior.
if set(grading.get("grading_scale", [])) != allowed_status:
    fail("Grading scale must be exactly supported/conditional/blocked.")

blocked_codes = {item["code"] for item in grading.get("blocked_conditions", [])}
for required in {
    "unsupported_kubernetes_version",
    "unsupported_distribution",
    "missing_required_profile",
    "missing_prerequisite",
}:
    if required not in blocked_codes:
        fail(f"Missing required blocked condition code: {required}")

for sample in grading.get("sample_cluster_evaluations", []):
    expected = sample["expected_output"]
    actual = evaluate_grade(sample)
    if actual["grade"] != expected["grade"]:
        fail(
            f"Grading mismatch for {sample['name']}: "
            f"expected {expected['grade']}, got {actual['grade']}"
        )
    if sorted(actual["reasons"]) != sorted(expected["reasons"]):
        fail(
            f"Grading reasons mismatch for {sample['name']}: "
            f"expected {expected['reasons']}, got {actual['reasons']}"
        )

# Mode decision table deterministic behavior.
rules = mode_table.get("rules", [])
if not rules:
    fail("Mode decision table requires at least one rule.")

priorities = [r["priority"] for r in rules]
if len(priorities) != len(set(priorities)):
    fail("Mode decision priorities must be unique.")

for rule in rules:
    mode = rule.get("recommend")
    if mode not in mode_table["metadata"]["supported_modes"]:
        fail(f"Mode rule {rule.get('id')} recommends unsupported mode {mode}.")

for sample in mode_table.get("sample_decisions", []):
    actual_mode = evaluate_mode(sample)
    expected_mode = sample["expected_mode"]
    if actual_mode != expected_mode:
        fail(
            f"Mode mismatch for {sample['name']}: "
            f"expected {expected_mode}, got {actual_mode}"
        )

# Remediation mappings for blocked conditions and conditional reasons.
remediations = remediation.get("remediations", {})
for code in blocked_codes:
    if code not in remediations:
        fail(f"Missing remediation for blocked code: {code}")
    if not remediations[code].get("actions"):
        fail(f"Remediation actions missing for blocked code: {code}")

all_conditional_reasons = set()
for section in matrix["kubernetes"].values():
    for item in section:
        all_conditional_reasons.update(item.get("conditions", []))
for key in required_profile_keys:
    for item in matrix["profiles"][key]:
        all_conditional_reasons.update(item.get("conditions", []))

for reason in sorted(all_conditional_reasons):
    if reason not in remediations:
        fail(f"Missing remediation for conditional reason: {reason}")

print("Batch 2 compatibility and mode checks passed.")
PY
