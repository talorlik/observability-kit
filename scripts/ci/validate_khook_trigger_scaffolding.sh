#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 8 Khook trigger scaffolding..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
import json
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
hook_catalog_path = root / "triggers" / "khook" / "hooks" / "HOOK_CATALOG_V1.yaml"
enrichment_path = (
    root / "triggers" / "khook" / "policies" / "EVENT_ENRICHMENT_V1.yaml"
)
dedupe_path = (
    root / "triggers" / "khook" / "policies" / "DEDUPE_BURST_CONTROL_V1.yaml"
)
dispatch_path = (
    root / "triggers" / "khook" / "dispatch" / "READ_ONLY_DISPATCH_POLICY_V1.yaml"
)
outputs_path = root / "triggers" / "khook" / "dispatch" / "OUTPUT_ATTACHMENTS_V1.yaml"
flow_path = (
    root / "tests" / "integration" / "khook_event_flows" / "TRIGGER_TO_SUMMARY_FLOW_V1.json"
)
burst_flow_path = (
    root / "tests" / "integration" / "khook_event_flows" / "BURST_RESILIENCE_FLOW_V1.json"
)

for required in [
    hook_catalog_path,
    enrichment_path,
    dedupe_path,
    dispatch_path,
    outputs_path,
    flow_path,
    burst_flow_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 8 artifact: {required}")

hook_catalog = yaml.safe_load(hook_catalog_path.read_text(encoding="utf-8"))
enrichment = yaml.safe_load(enrichment_path.read_text(encoding="utf-8"))
dedupe = yaml.safe_load(dedupe_path.read_text(encoding="utf-8"))
dispatch = yaml.safe_load(dispatch_path.read_text(encoding="utf-8"))
outputs = yaml.safe_load(outputs_path.read_text(encoding="utf-8"))
flow = json.loads(flow_path.read_text(encoding="utf-8"))
burst_flow = json.loads(burst_flow_path.read_text(encoding="utf-8"))

# 1) Hook schema deployment for restart and health events.
hooks = {item.get("id"): item for item in hook_catalog.get("hooks", [])}
required_hooks = {
    "pod-restart",
    "oom-kill",
    "probe-failed",
    "pod-pending",
    "node-not-ready",
}
if not required_hooks.issubset(set(hooks.keys())):
    missing = sorted(required_hooks - set(hooks.keys()))
    fail(f"Hook catalog missing required hooks: {missing}")

required_event_fields = set(
    hook_catalog.get("schema_requirements", {}).get("required_event_fields", [])
)
for field in [
    "event_id",
    "event_timestamp",
    "cluster",
    "namespace",
    "object_kind",
    "object_name",
    "reason",
    "message",
]:
    if field not in required_event_fields:
        fail(f"Hook schema missing required event field: {field}")

# 2) Enrichment field completeness.
enrichment_required = set(enrichment.get("enrichment_fields", {}).get("required", []))
for field in [
    "namespace",
    "owner",
    "criticality",
    "rollout_marker",
    "incident_correlation_key",
]:
    if field not in enrichment_required:
        fail(f"Enrichment policy missing required field: {field}")
if enrichment.get("bounds", {}).get("deny_if_required_field_missing") is not True:
    fail("Enrichment policy must deny when required fields are missing.")
if int(enrichment.get("bounds", {}).get("max_enriched_payload_bytes", 0)) < 4096:
    fail("Enrichment policy must set a practical payload bound (>=4096 bytes).")
derivation = enrichment.get("field_derivation", {})
if derivation.get("incident_correlation_key", {}).get("strategy") != "stable-hash":
    fail("Enrichment policy must derive incident_correlation_key via stable-hash.")
inputs = set(
    derivation.get("incident_correlation_key", {}).get("inputs", [])
)
expected_inputs = {"cluster", "namespace", "object_kind", "object_name", "reason"}
if inputs != expected_inputs:
    fail("Enrichment correlation key inputs must match expected deterministic set.")

# 3) Deduplication and burst-control behavior.
if dedupe.get("deduplication", {}).get("window_seconds") != 300:
    fail("Dedupe policy must use 300 second dedupe window.")
if dedupe.get("deduplication", {}).get("behavior_on_duplicate") != "suppress_new_investigation":
    fail("Dedupe policy must suppress new investigation on duplicate.")
if dedupe.get("burst_control", {}).get("per_key_max_events_per_window") != 10:
    fail("Burst control policy must set per-key max events per window to 10.")
if dedupe.get("burst_control", {}).get("overflow_behavior") != "aggregate_and_emit_single_summary":
    fail("Burst control overflow behavior must aggregate and emit single summary.")
if dedupe.get("resilience", {}).get("policy_on_store_unavailable") != "fail_closed":
    fail("Dedupe policy must fail closed when state store is unavailable.")
retry_backoff = dedupe.get("resilience", {}).get("retry_backoff_seconds", [])
if retry_backoff != [1, 2, 5]:
    fail("Dedupe resilience retry backoff must be [1, 2, 5].")

# 4) Read-only dispatch restrictions.
denied_write_targets = set(dispatch.get("dispatch", {}).get("denied_write_targets", []))
for target in ["action-governor", "runbook-planner", "remediation-executor"]:
    if target not in denied_write_targets:
        fail(f"Dispatch policy must deny write-path target: {target}")
if dispatch.get("constraints", {}).get("require_read_only_mode") is not True:
    fail("Dispatch policy must require read-only mode.")

# 5) Case-file and operator channel output attachment.
attachments = outputs.get("attachments", {})
if attachments.get("case_file", {}).get("required") is not True:
    fail("Case-file attachment must be required.")
if attachments.get("operator_channel", {}).get("required") is not True:
    fail("Operator channel attachment must be required.")
case_fields = set(attachments.get("case_file", {}).get("required_fields", []))
for field in ["summary", "evidence_handles", "correlation_key", "source_hook_id"]:
    if field not in case_fields:
        fail(f"Case-file attachment required field missing: {field}")

# 6) Functional and resilience smoke outcomes.
if flow.get("dispatch_mode") != "read-only":
    fail("Trigger-to-summary flow must dispatch in read-only mode.")
if flow.get("outputs", {}).get("case_file", {}).get("attached") is not True:
    fail("Trigger-to-summary flow must attach output to case file.")
if flow.get("outputs", {}).get("operator_channel", {}).get("attached") is not True:
    fail("Trigger-to-summary flow must attach output to operator channel.")
if flow.get("reliability", {}).get("delivery_guarantee") != "at-least-once":
    fail("Trigger-to-summary flow must assert at-least-once delivery guarantee.")
if flow.get("reliability", {}).get("max_end_to_summary_seconds", 0) > 30:
    fail("Trigger-to-summary flow exceeds baseline end-to-summary threshold.")
if flow.get("reliability", {}).get("retry_count", -1) < 0:
    fail("Trigger-to-summary flow retry_count must be non-negative.")
results = burst_flow.get("results", {})
if results.get("new_investigations_created") != 1:
    fail("Burst resilience flow must create exactly one investigation.")
if results.get("aggregated_overflow_summary_emitted") is not True:
    fail("Burst resilience flow must emit overflow summary.")
if results.get("suppressed_duplicates", 0) < 1:
    fail("Burst resilience flow must suppress duplicate events.")
summary = results.get("summary", {})
for required_field in ["suppressed_event_count", "first_seen_at", "last_seen_at"]:
    if required_field not in summary:
        fail(f"Burst resilience summary missing field: {required_field}")
if summary.get("suppressed_event_count") != results.get("suppressed_duplicates"):
    fail("Burst resilience summary count must match suppressed_duplicates.")

workflow = (root / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
batch8_smoke = (root / "scripts" / "ci" / "validate_batch8_smoke.sh").read_text(
    encoding="utf-8"
)
if "validate_khook_trigger_scaffolding.sh" not in workflow:
    fail("Main CI workflow must include Khook trigger scaffolding validator.")
if "validate_khook_trigger_scaffolding.sh" not in batch8_smoke:
    fail("Batch 8 smoke bundle must include Khook trigger scaffolding validator.")

print("Batch 8 Khook trigger scaffold checks passed.")
PY

echo "Running Khook trigger flow integration fixture checks..."
python3 tests/integration/khook_event_flows/test_khook_event_flows.py
