#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 8 security, isolation, and resilience artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

base = Path("contracts") / "security"

isolation = json.loads((base / "TEAM_ENV_ISOLATION_VALIDATION.json").read_text())
encryption = json.loads((base / "ENCRYPTION_CONTROLS_VALIDATION.json").read_text())
audit = json.loads((base / "AUDIT_LOGGING_VALIDATION.json").read_text())
backup = json.loads((base / "BACKUP_RESTORE_DRILL_VALIDATION.json").read_text())
rollback = json.loads((base / "ROLLBACK_DRILL_VALIDATION.json").read_text())
hardening = json.loads((base / "HARDENING_CHECKLIST_VALIDATION.json").read_text())

REQUIRED_AUDIT_FIELDS = {"@timestamp", "actor", "action", "target", "result"}
REQUIRED_HARDENING_CONTROLS = {
    "least_privilege_roles",
    "network_policy_defaults",
    "secrets_source_enforcement",
    "pod_security_constraints",
    "audit_log_forwarding",
    "backup_and_rollback_drill_signoff",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: environment and team isolation.
if isolation.get("validation_result", {}).get("status") != "pass":
    fail("Team and environment isolation validation must pass.")
if not isolation.get("isolation_controls", {}).get("index_partitioning", {}).get("enforced"):
    fail("Index partitioning must be enforced for isolation.")
for test in isolation.get("access_tests", []):
    if test.get("status") != "pass":
        fail(f"Isolation access test failed: {test.get('name')}")
    if test.get("expected_decision") != test.get("observed_decision"):
        fail(f"Isolation decision mismatch: {test.get('name')}")


# Task 2: encryption controls.
if encryption.get("validation_result", {}).get("status") != "pass":
    fail("Encryption control validation must pass.")
if not encryption.get("encryption_in_transit", {}).get("otlp_tls_required"):
    fail("OTLP TLS must be required.")
if not encryption.get("encryption_at_rest", {}).get("telemetry_indices_encrypted"):
    fail("Telemetry index encryption at rest must be enabled.")
for check in encryption.get("control_checks", []):
    if check.get("status") != "pass":
        fail(f"Encryption check failed: {check.get('name')}")


# Task 3: audit logging controls.
if audit.get("validation_result", {}).get("status") != "pass":
    fail("Audit logging validation must pass.")
if audit.get("retention_days", 0) < 30:
    fail("Audit retention must be at least 30 days.")
if set(audit.get("required_audit_fields", [])) != REQUIRED_AUDIT_FIELDS:
    fail("Audit required fields do not match expected governance fields.")
for test in audit.get("audit_tests", []):
    if test.get("status") != "pass":
        fail(f"Audit test failed: {test.get('name')}")
    if not test.get("expected_fields_present"):
        fail(f"Audit event missing required fields: {test.get('name')}")


# Task 4: backup and restore drill.
if backup.get("validation_result", {}).get("status") != "pass":
    fail("Backup and restore validation must pass.")
if backup.get("restore_drill", {}).get("environment") == "production":
    fail("Restore drills must run in non-production.")
if backup.get("restore_drill", {}).get("status") != "pass":
    fail("Restore drill status must pass.")
if backup.get("restore_drill", {}).get("restore_time_minutes", 0) <= 0:
    fail("Restore drill time must be a positive value.")
if not backup.get("evidence_artifacts"):
    fail("Backup and restore validation requires evidence artifacts.")


# Task 5: rollback drills.
if rollback.get("validation_result", {}).get("status") != "pass":
    fail("Rollback drill validation must pass.")
for scenario in rollback.get("rollback_scenarios", []):
    if scenario.get("status") != "pass":
        fail(f"Rollback scenario failed: {scenario.get('name')}")
    if scenario.get("rollback_time_minutes", 0) <= 0:
        fail(f"Rollback scenario missing timing evidence: {scenario.get('name')}")
if len(rollback.get("required_steps", [])) < 4:
    fail("Rollback validation must define complete rollback procedure steps.")


# Task 6: hardening checklist completion.
if hardening.get("validation_result", {}).get("status") != "pass":
    fail("Hardening checklist validation must pass.")
if hardening.get("validation_result", {}).get("completion_percent") != 100:
    fail("Hardening checklist must be fully complete.")
controls = {item.get("control") for item in hardening.get("checklist", [])}
if controls != REQUIRED_HARDENING_CONTROLS:
    fail("Hardening checklist controls are incomplete or invalid.")
for item in hardening.get("checklist", []):
    if item.get("status") != "complete":
        fail(f"Hardening control is not complete: {item.get('control')}")

print("Batch 8 security, isolation, and resilience checks passed.")
PY
