#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 10 vector foundations artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

base = Path("contracts") / "vector"

ownership = json.loads((base / "CURATED_ARTIFACT_OWNERSHIP_VALIDATION.json").read_text())
snapshots = json.loads((base / "EXTRACTION_SNAPSHOTS_VALIDATION.json").read_text())
vector_writes = json.loads((base / "VECTORS_INDEX_WRITE_VALIDATION.json").read_text())
retrieval = json.loads((base / "RETRIEVAL_QUALITY_BASELINE_VALIDATION.json").read_text())
governance = json.loads((base / "GOVERNANCE_CONTROLS_VALIDATION.json").read_text())
rehearsal = json.loads((base / "VECTOR_PLAYBOOK_REHEARSAL_VALIDATION.json").read_text())

REQUIRED_ARTIFACT_TYPES = {"incident_records", "incident_summaries", "runbook_documents"}
REQUIRED_PII_PATTERNS = {"email", "phone_number", "credit_card", "national_id"}
REQUIRED_AUDIT_FIELDS = {
    "@timestamp",
    "request_id",
    "actor",
    "query_hash",
    "result_count",
    "policy_decision",
}
REQUIRED_PLAYBOOK_STEPS = {
    "run_quality_checks",
    "trigger_reindex",
    "validate_post_reindex_quality",
    "execute_rollback_to_previous_snapshot",
}
REQUIRED_METRICS = {"precision_at_5", "recall_at_10", "mean_reciprocal_rank"}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: curated artifact ownership.
if ownership.get("validation_result", {}).get("status") != "pass":
    fail("Curated artifact ownership validation must pass.")
artifact_types = {
    item.get("artifact_type") for item in ownership.get("curated_artifact_types", [])
}
if artifact_types != REQUIRED_ARTIFACT_TYPES:
    fail("Curated artifact list must include incidents, summaries, and runbooks.")
for item in ownership.get("curated_artifact_types", []):
    if not item.get("owner"):
        fail(f"Artifact owner is required for {item.get('artifact_type')}")
    if not item.get("refresh_rule"):
        fail(f"Refresh rule is required for {item.get('artifact_type')}")
if not ownership.get("ownership_controls", {}).get("owner_required"):
    fail("Owner-required control must be enabled.")
if not ownership.get("ownership_controls", {}).get("refresh_rule_required"):
    fail("Refresh rule-required control must be enabled.")


# Task 2: extraction snapshots.
if snapshots.get("validation_result", {}).get("status") != "pass":
    fail("Extraction snapshots validation must pass.")
snapshot_runs = snapshots.get("snapshot_runs", [])
if len(snapshot_runs) < 2:
    fail("Extraction snapshots must include at least two versioned runs.")
for run in snapshot_runs:
    if run.get("status") != "pass":
        fail(f"Snapshot run failed: {run.get('snapshot_id')}")
    if run.get("record_count", 0) <= 0:
        fail(f"Snapshot run has invalid record count: {run.get('snapshot_id')}")
if not snapshots.get("versioning_controls", {}).get("immutable_snapshots"):
    fail("Immutable snapshots must be enabled.")
if not snapshots.get("versioning_controls", {}).get("lineage_manifest_written"):
    fail("Snapshot lineage manifest must be written.")


# Task 3: vectors-* writes.
if vector_writes.get("validation_result", {}).get("status") != "pass":
    fail("Vector index write validation must pass.")
if vector_writes.get("target_index_pattern") != "vectors-*":
    fail("Target index pattern must be vectors-*.")
if len(vector_writes.get("indices_validated", [])) < 1:
    fail("At least one vectors index must be validated.")
if vector_writes.get("embedding_model", {}).get("dimensions", 0) <= 0:
    fail("Embedding model dimensions must be a positive value.")
for check in vector_writes.get("write_pipeline_checks", []):
    if check.get("status") != "pass":
        fail(f"Vector write check failed: {check.get('name')}")


# Task 4: retrieval quality baseline.
if retrieval.get("validation_result", {}).get("status") != "pass":
    fail("Retrieval quality baseline validation must pass.")
metrics = retrieval.get("quality_metrics", {})
thresholds = retrieval.get("minimum_thresholds", {})
if set(metrics.keys()) != REQUIRED_METRICS:
    fail("Retrieval quality metrics must include precision_at_5, recall_at_10, and MRR.")
if set(thresholds.keys()) != REQUIRED_METRICS:
    fail("Retrieval threshold metrics are incomplete.")
for metric in REQUIRED_METRICS:
    if metrics.get(metric, 0) < thresholds.get(metric, 1):
        fail(f"Retrieval metric {metric} is below minimum threshold.")
if retrieval.get("queries_evaluated", 0) < 10:
    fail("Retrieval quality baseline must evaluate at least 10 queries.")
if not retrieval.get("retrieval_endpoint", {}).get("returns_relevance_score"):
    fail("Retrieval endpoint must return relevance scores.")


# Task 5: governance controls.
if governance.get("validation_result", {}).get("status") != "pass":
    fail("Governance controls validation must pass.")
if not governance.get("pii_filtering", {}).get("enabled"):
    fail("PII filtering must be enabled.")
patterns = set(governance.get("pii_filtering", {}).get("blocked_patterns", []))
if patterns != REQUIRED_PII_PATTERNS:
    fail("PII filtering patterns do not match expected governance controls.")
if not governance.get("retrieval_audit_events", {}).get("enabled"):
    fail("Retrieval audit events must be enabled.")
audit_fields = set(governance.get("retrieval_audit_events", {}).get("required_fields", []))
if audit_fields != REQUIRED_AUDIT_FIELDS:
    fail("Retrieval audit required fields do not match governance baseline.")
for test in governance.get("governance_tests", []):
    if test.get("status") != "pass":
        fail(f"Governance test failed: {test.get('name')}")
if governance.get("ci_policy_checks", {}).get("status") != "pass":
    fail("Governance CI policy checks must pass.")


# Task 6: vector operations playbook rehearsal.
if rehearsal.get("validation_result", {}).get("status") != "pass":
    fail("Vector operations playbook rehearsal validation must pass.")
if rehearsal.get("rehearsal", {}).get("environment") == "production":
    fail("Playbook rehearsal must run in non-production.")
if rehearsal.get("rehearsal", {}).get("status") != "pass":
    fail("Playbook rehearsal status must pass.")
steps = {step.get("name") for step in rehearsal.get("steps_executed", [])}
if steps != REQUIRED_PLAYBOOK_STEPS:
    fail("Playbook rehearsal steps are incomplete.")
for step in rehearsal.get("steps_executed", []):
    if step.get("status") != "pass":
        fail(f"Playbook step failed: {step.get('name')}")
if len(rehearsal.get("evidence_artifacts", [])) < 3:
    fail("Playbook rehearsal must include at least three evidence artifacts.")

print("Batch 10 vector foundations checks passed.")
PY
