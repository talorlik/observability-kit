#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 5 logs pipeline artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import re
import sys

base = Path("contracts") / "logs"

cri_json = json.loads((base / "CRI_JSON_PARSING_VALIDATION.json").read_text())
multiline = json.loads((base / "MULTILINE_GROUPING_VALIDATION.json").read_text())
redaction = json.loads((base / "SENSITIVE_FIELD_REDACTION_VALIDATION.json").read_text())
template = json.loads((base / "LOGS_INDEX_TEMPLATE_POLICY.json").read_text())
correlation = json.loads((base / "TRACE_CORRELATION_VALIDATION.json").read_text())
dashboard_file = (
    Path("gitops")
    / "platform"
    / "search"
    / "dashboards"
    / "saved-objects"
    / "LOGS_OPERATIONS.ndjson"
)

REQUIRED_BASE_FIELDS = {
    "@timestamp",
    "message",
    "service.name",
    "deployment.environment",
    "k8s.cluster.name",
    "severity",
}
REQUIRED_TRACE_FIELDS = {"trace_id", "span_id"}
EXPECTED_TEMPLATE_PATTERN = "logs-*"
INDEX_NAME_REGEX = re.compile(r"^logs-[a-z0-9]+-[a-z0-9]+-\d{4}\.\d{2}\.\d{2}$")
DASHBOARD_REQUIRED_IDS = {
    "logs-operations-overview",
    "logs-parse-failure-rate",
    "logs-redaction-counter",
    "logs-ingest-lag-seconds",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: CRI and JSON parsing defaults.
if cri_json.get("validation_result", {}).get("status") != "pass":
    fail("CRI and JSON parsing validation must pass.")
required_fields = set(cri_json.get("required_base_fields", []))
if not REQUIRED_BASE_FIELDS.issubset(required_fields):
    fail("CRI and JSON parsing artifact is missing required base fields.")
for example in cri_json.get("input_examples", []):
    expected_fields = example.get("expected_fields", {})
    if "message" in expected_fields and not expected_fields["message"]:
        fail(f"Parsed JSON message cannot be empty in sample: {example.get('name')}")


# Task 2: multiline grouping.
if multiline.get("validation_result", {}).get("status") != "pass":
    fail("Multiline grouping validation must pass.")
for case in multiline.get("test_cases", []):
    if case.get("status") != "pass":
        fail(f"Multiline test case failed: {case.get('name')}")
    if case.get("observed_grouped_events") != case.get("expected_grouped_events"):
        fail(f"Multiline grouping mismatch in case: {case.get('name')}")


# Task 3: sensitive field redaction and never-index controls.
if redaction.get("validation_result", {}).get("status") != "pass":
    fail("Sensitive field redaction validation must pass.")
if redaction.get("validation_result", {}).get("unredacted_matches") != 0:
    fail("Sensitive redaction found unredacted prohibited matches.")
policy = redaction.get("policy", {})
if not policy.get("never_index_fields"):
    fail("Never-index field policy cannot be empty.")
for event in redaction.get("test_events", []):
    if event.get("status") != "pass":
        fail(f"Redaction test event failed: {event.get('name')}")
    after = event.get("after", {})
    for value in after.values():
        if isinstance(value, str) and "secret" in value.lower():
            fail(f"Potential sensitive value leaked after redaction: {event.get('name')}")


# Task 4: logs-* template and naming rules.
if template.get("validation_result", {}).get("status") != "pass":
    fail("logs-* template validation must pass.")
patterns = template.get("index_template", {}).get("index_patterns", [])
if EXPECTED_TEMPLATE_PATTERN not in patterns:
    fail("Index template must target logs-* pattern.")
if template.get("mapping_policy", {}).get("dynamic") != "strict":
    fail("logs mapping policy must enforce strict dynamic mapping.")
mapping_fields = set(template.get("mapping_policy", {}).get("required_keywords", []))
if not REQUIRED_TRACE_FIELDS.issubset(mapping_fields):
    fail("logs mapping policy must include trace_id and span_id fields.")
for name in template.get("naming_strategy", {}).get("valid_examples", []):
    if INDEX_NAME_REGEX.fullmatch(name) is None:
        fail(f"Invalid logs index naming example: {name}")


# Task 5: trace correlation behavior.
if correlation.get("validation_result", {}).get("status") != "pass":
    fail("Trace correlation validation must pass.")
trace_fields = set(correlation.get("requirements", {}).get("trace_context_fields", []))
if trace_fields != REQUIRED_TRACE_FIELDS:
    fail("Trace correlation must require both trace_id and span_id.")
for sample in correlation.get("query_samples", []):
    if sample.get("status") != "pass":
        fail(f"Trace correlation query sample failed: {sample.get('name')}")
    if sample.get("observed_hits", 0) < sample.get("expected_min_hits", 0):
        fail(f"Trace correlation hits below expectation: {sample.get('name')}")


# Task 6: logs operations dashboard render artifact.
if not dashboard_file.exists():
    fail("LOGS_OPERATIONS.ndjson dashboard artifact is missing.")

observed_ids = set()
parsed_lines = 0
for raw_line in dashboard_file.read_text().splitlines():
    line = raw_line.strip()
    if not line:
        continue
    parsed_lines += 1
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        fail(f"Invalid NDJSON object in LOGS_OPERATIONS.ndjson: {exc}")
    object_id = obj.get("id")
    if object_id:
        observed_ids.add(object_id)

if parsed_lines == 0:
    fail("LOGS_OPERATIONS.ndjson cannot be empty.")
missing_ids = DASHBOARD_REQUIRED_IDS - observed_ids
if missing_ids:
    missing_str = ", ".join(sorted(missing_ids))
    fail(f"LOGS_OPERATIONS.ndjson missing required object IDs: {missing_str}")

print("Batch 5 logs pipeline checks passed.")
PY
