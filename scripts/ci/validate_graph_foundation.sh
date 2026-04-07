#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 11 graph foundation artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

base = Path("contracts") / "graph"

module_profile = json.loads((base / "GRAPH_MODULE_PROFILE_VALIDATION.json").read_text())
schema = json.loads((base / "GRAPH_SCHEMA_VERSIONING_VALIDATION.json").read_text())
sync = json.loads((base / "GRAPH_IDEMPOTENT_SYNC_VALIDATION.json").read_text())
freshness = json.loads((base / "GRAPH_FRESHNESS_ALERTS_VALIDATION.json").read_text())
queries = json.loads((base / "GRAPH_DEPENDENCY_QUERIES_VALIDATION.json").read_text())
runbook = json.loads((base / "GRAPH_RUNBOOK_DRY_RUN_VALIDATION.json").read_text())

REQUIRED_CORE_HEALTH_CHECKS = {
    "otel_ingest_pipeline",
    "opensearch_write_path",
    "core_dashboards_available",
}
REQUIRED_ENTITY_TYPES = {"service", "dependency", "ownership", "incident"}
REQUIRED_SYNC_MODES = {"full", "replay"}
REQUIRED_ALERT_SIGNALS = {
    "graph_data_lag_minutes",
    "graph_sync_failure_rate_percent",
}
REQUIRED_QUERY_TYPES = {"dependency_path", "blast_radius", "ownership_traversal"}
REQUIRED_RUNBOOK_STEPS = {
    "rebuild_graph_from_latest_snapshot",
    "repair_inconsistent_relationships",
    "switch_to_core_only_fallback_mode",
    "restore_graph_mode_after_validation",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: optional module enable/disable behavior.
if module_profile.get("validation_result", {}).get("status") != "pass":
    fail("Graph module profile validation must pass.")
if not module_profile.get("graph_module", {}).get("optional"):
    fail("Graph module must be optional.")
if not module_profile.get("enable_disable_validation", {}).get(
    "enable_without_core_disruption"
):
    fail("Enable behavior must not disrupt core platform.")
if not module_profile.get("enable_disable_validation", {}).get(
    "disable_without_core_disruption"
):
    fail("Disable behavior must not disrupt core platform.")
health_checks = {
    check.get("name")
    for check in module_profile.get("enable_disable_validation", {}).get(
        "core_pipeline_health_checks", []
    )
}
if health_checks != REQUIRED_CORE_HEALTH_CHECKS:
    fail("Core pipeline health checks are incomplete for module toggle validation.")
for check in module_profile.get("enable_disable_validation", {}).get(
    "core_pipeline_health_checks", []
):
    if check.get("status") != "pass":
        fail(f"Core health check failed during graph toggle validation: {check.get('name')}")


# Task 2: schema versioning.
if schema.get("validation_result", {}).get("status") != "pass":
    fail("Graph schema versioning validation must pass.")
if set(schema.get("entity_types", [])) != REQUIRED_ENTITY_TYPES:
    fail("Graph schema entity types must include service, dependency, ownership, incident.")
if not schema.get("migration_procedure", {}).get("documented"):
    fail("Graph schema migration procedure must be documented.")
if not schema.get("migration_procedure", {}).get("dry_run_supported"):
    fail("Graph schema migration must support dry-run.")
if not schema.get("migration_procedure", {}).get("rollback_supported"):
    fail("Graph schema migration must support rollback.")
if not schema.get("review_approval", {}).get("approved"):
    fail("Graph schema definition must be approved.")


# Task 3: idempotent sync jobs.
if sync.get("validation_result", {}).get("status") != "pass":
    fail("Graph idempotent sync validation must pass.")
runs = sync.get("sync_runs", [])
if len(runs) < 2:
    fail("Graph sync validation must include at least two runs.")
modes = {run.get("mode") for run in runs}
if modes != REQUIRED_SYNC_MODES:
    fail("Graph sync validation must include full and replay modes.")
for run in runs:
    if run.get("status") != "pass":
        fail(f"Graph sync run failed: {run.get('run_id')}")
    if run.get("duplicates_detected", 1) != 0:
        fail(f"Graph sync run detected duplicate writes: {run.get('run_id')}")
if not sync.get("convergence_checks", {}).get("repeated_runs_converge"):
    fail("Graph sync runs must converge.")
if not sync.get("convergence_checks", {}).get("run_to_run_hash_match"):
    fail("Graph sync run-to-run hash must match.")
if not sync.get("convergence_checks", {}).get("late_out_of_order_handling_defined"):
    fail("Late and out-of-order handling must be defined for sync.")


# Task 4: freshness and sync quality alerts.
if freshness.get("validation_result", {}).get("status") != "pass":
    fail("Graph freshness alerts validation must pass.")
if freshness.get("freshness_slo", {}).get("max_graph_lag_minutes", 0) <= 0:
    fail("Graph freshness lag threshold must be a positive value.")
signals = {alert.get("signal") for alert in freshness.get("alerts", [])}
if signals != REQUIRED_ALERT_SIGNALS:
    fail("Graph freshness alert signals do not match baseline.")
for alert in freshness.get("alerts", []):
    if alert.get("status") != "pass":
        fail(f"Graph alert failed: {alert.get('name')}")
    if not alert.get("triggered_in_test"):
        fail(f"Graph alert did not trigger in validation test: {alert.get('name')}")
if len(freshness.get("routing_channels", [])) < 1:
    fail("Graph alerts must define routing channels.")


# Task 5: dependency and blast-radius queries.
if queries.get("validation_result", {}).get("status") != "pass":
    fail("Graph dependency queries validation must pass.")
query_set = queries.get("query_set", [])
if len(query_set) < 3:
    fail("Graph query set must include at least three operator queries.")
query_types = {query.get("query_type") for query in query_set}
if query_types != REQUIRED_QUERY_TYPES:
    fail("Graph query set must include dependency, blast-radius, and ownership traversal.")
for query in query_set:
    if query.get("status") != "pass":
        fail(f"Graph query failed: {query.get('name')}")
    if not query.get("incident_replay_id"):
        fail(f"Graph query is missing incident replay linkage: {query.get('name')}")
if len(queries.get("expected_dependency_paths", [])) < 1:
    fail("Graph validation must include expected dependency path outputs.")


# Task 6: graph runbook dry run.
if runbook.get("validation_result", {}).get("status") != "pass":
    fail("Graph runbook dry-run validation must pass.")
if runbook.get("dry_run", {}).get("environment") == "production":
    fail("Graph runbook dry run must execute in non-production.")
if runbook.get("dry_run", {}).get("status") != "pass":
    fail("Graph runbook dry run status must pass.")
steps = {step.get("name") for step in runbook.get("steps_executed", [])}
if steps != REQUIRED_RUNBOOK_STEPS:
    fail("Graph runbook dry-run steps are incomplete.")
for step in runbook.get("steps_executed", []):
    if step.get("status") != "pass":
        fail(f"Graph runbook dry-run step failed: {step.get('name')}")
if len(runbook.get("evidence_artifacts", [])) < 3:
    fail("Graph runbook dry run must include at least three evidence artifacts.")

print("Batch 11 graph foundation checks passed.")
PY
