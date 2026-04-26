#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 7 onboarding and subscription artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

base = Path("contracts") / "onboarding"

one_block = json.loads((base / "ONE_BLOCK_ONBOARDING_VALIDATION.json").read_text())
modes = json.loads((base / "SUBSCRIPTION_MODES_VALIDATION.json").read_text())
metadata = json.loads((base / "METADATA_POLICY_VALIDATION.json").read_text())
schema = json.loads((base / "ONBOARDING_SCHEMA.json").read_text())
ci_schema = json.loads((base / "CI_SCHEMA_VALIDATION.json").read_text())
lead_time = json.loads((base / "ONBOARDING_LEAD_TIME_VALIDATION.json").read_text())

REQUIRED_SUBSCRIPTION_MODES = {"passive", "low-touch", "instrumentation"}
REQUIRED_METADATA_FIELDS = {"service.name", "deployment.environment", "service.owner"}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: one-block onboarding.
if one_block.get("validation_result", {}).get("status") != "pass":
    fail("One-block onboarding validation must pass.")
contract = one_block.get("onboarding_contract", {})
keys = set(contract.get("single_block_required_keys", []))
for required in {"serviceName", "environment", "owner", "subscriptionMode"}:
    if required not in keys:
        fail(f"One-block onboarding is missing required key: {required}")
render = one_block.get("pilot_render_result", {})
if render.get("status") != "pass":
    fail("Pilot render result for one-block onboarding must pass.")
if render.get("values_blocks_detected") != 1:
    fail("Pilot onboarding must use exactly one values block.")
if not render.get("rendered_resources"):
    fail("Pilot onboarding render must produce resources.")


# Task 2: passive, low-touch, and instrumentation modes.
if modes.get("validation_result", {}).get("status") != "pass":
    fail("Subscription mode validation must pass.")
if set(modes.get("required_modes", [])) != REQUIRED_SUBSCRIPTION_MODES:
    fail("Subscription modes must include passive, low-touch, instrumentation.")
for test in modes.get("mode_tests", []):
    if test.get("status") != "pass":
        fail(f"Subscription mode test failed: {test.get('mode')}")
    if test.get("expected_behavior") != test.get("observed_behavior"):
        fail(f"Subscription mode behavior mismatch: {test.get('mode')}")


# Task 3: metadata policy checks.
if metadata.get("validation_result", {}).get("status") != "pass":
    fail("Metadata policy validation must pass.")
if set(metadata.get("required_metadata_fields", [])) != REQUIRED_METADATA_FIELDS:
    fail("Metadata policy fields do not match required set.")
for policy_test in metadata.get("policy_tests", []):
    if policy_test.get("status") != "pass":
        fail(f"Metadata policy test failed: {policy_test.get('name')}")
    if policy_test.get("expected_decision") != policy_test.get("observed_decision"):
        fail(f"Metadata policy decision mismatch: {policy_test.get('name')}")
    if policy_test.get("expected_decision") == "deny" and not policy_test.get("error_message"):
        fail(f"Denied metadata policy case needs clear error: {policy_test.get('name')}")


# Task 4: onboarding schema checks in CI.
if schema.get("type") != "object":
    fail("Onboarding schema must define an object contract.")
required_schema_fields = set(schema.get("required", []))
for field in {"serviceName", "environment", "owner", "subscriptionMode"}:
    if field not in required_schema_fields:
        fail(f"Onboarding schema missing required field: {field}")
subscription_enum = (
    schema.get("properties", {})
    .get("subscriptionMode", {})
    .get("enum", [])
)
if set(subscription_enum) != REQUIRED_SUBSCRIPTION_MODES:
    fail("Onboarding schema subscription mode enum is invalid.")
if ci_schema.get("validation_result", {}).get("status") != "pass":
    fail("CI schema validation artifact must pass.")
for check in ci_schema.get("ci_checks", []):
    if check.get("status") != "pass":
        fail(f"CI schema check failed: {check.get('name')}")


# Task 6: onboarding lead-time measurement.
if lead_time.get("validation_result", {}).get("status") != "pass":
    fail("Onboarding lead-time validation must pass.")
baseline = lead_time.get("baseline_cycle_time_hours", 0)
current = lead_time.get("current_cycle_time_hours", 0)
if baseline <= 0 or current <= 0:
    fail("Lead-time values must be positive.")
if current >= baseline:
    fail("Current onboarding cycle time must improve over baseline.")
if len(lead_time.get("friction_points_removed", [])) < 2:
    fail("At least two friction points must be removed.")
improvement = lead_time.get("validation_result", {}).get("improvement_percent", 0)
if improvement <= 0:
    fail("Lead-time improvement percent must be positive.")

print("Batch 7 onboarding and subscription checks passed.")
PY
