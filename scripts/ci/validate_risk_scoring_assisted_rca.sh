#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 12 risk scoring and assisted RCA artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

base = Path("contracts") / "risk_rca"

features = json.loads((base / "DETERMINISTIC_RISK_FEATURES_VALIDATION.json").read_text())
outputs = json.loads((base / "RISK_SCORING_OUTPUTS_VALIDATION.json").read_text())
backtest = json.loads((base / "BACKTESTING_EVIDENCE_VALIDATION.json").read_text())
hybrid = json.loads((base / "HYBRID_RETRIEVAL_EVIDENCE_BUNDLES_VALIDATION.json").read_text())
approval = json.loads((base / "HUMAN_APPROVAL_WORKFLOW_VALIDATION.json").read_text())
pilot = json.loads((base / "PILOT_GO_HOLD_DECISION_VALIDATION.json").read_text())

REQUIRED_FEATURES = {
    "incident_frequency_30d",
    "dependency_blast_radius_score",
    "error_budget_burn_rate_6h",
    "change_failure_rate_14d",
}
REQUIRED_FEATURE_SOURCES = {"opensearch", "neo4j"}
REQUIRED_DASHBOARD_VIEWS = {
    "risk-overview-by-service",
    "highest-risk-dependency-clusters",
    "risk-score-trend-by-environment",
}
REQUIRED_RETRIEVAL_SOURCES = {"opensearch_vectors", "neo4j_graph"}
REQUIRED_APPROVAL_STAGES = {
    "generate_recommendation",
    "security_and_governance_gate",
    "human_reviewer_approval",
    "operator_action_execution",
}
REQUIRED_AUDIT_FIELDS = {
    "@timestamp",
    "recommendation_id",
    "reviewer",
    "approval_decision",
    "reason_code",
}
ALLOWED_DECISIONS = {"go", "hold"}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: deterministic feature definitions.
if features.get("validation_result", {}).get("status") != "pass":
    fail("Deterministic risk feature validation must pass.")
definitions = features.get("feature_definitions", [])
if len(definitions) < 4:
    fail("At least four deterministic risk features are required.")
feature_names = {feature.get("name") for feature in definitions}
if feature_names != REQUIRED_FEATURES:
    fail("Risk feature set does not match required deterministic baseline.")
feature_sources = {feature.get("source") for feature in definitions}
if feature_sources != REQUIRED_FEATURE_SOURCES:
    fail("Risk feature sources must include OpenSearch and Neo4j.")
for feature in definitions:
    if not feature.get("deterministic"):
        fail(f"Feature must be deterministic: {feature.get('name')}")
    if not feature.get("calculation"):
        fail(f"Feature calculation is missing: {feature.get('name')}")
if not features.get("reproducibility_checks", {}).get("seed_locked"):
    fail("Risk feature reproducibility requires a locked seed.")
if not features.get("reproducibility_checks", {}).get("windowing_rules_versioned"):
    fail("Risk feature windowing rules must be versioned.")
if not features.get("reproducibility_checks", {}).get("run_to_run_hash_match"):
    fail("Risk feature output hashes must match across runs.")


# Task 2: risk scoring outputs.
if outputs.get("validation_result", {}).get("status") != "pass":
    fail("Risk scoring output validation must pass.")
if outputs.get("scoring_job", {}).get("status") != "pass":
    fail("Risk scoring job status must pass.")
if not outputs.get("scoring_job", {}).get("job_name"):
    fail("Risk scoring job name is required.")
if not outputs.get("scoring_job", {}).get("schedule"):
    fail("Risk scoring schedule is required.")
views = set(outputs.get("risk_dashboard_views", []))
if views != REQUIRED_DASHBOARD_VIEWS:
    fail("Risk dashboard views do not match baseline.")
scores = outputs.get("service_scores", [])
if len(scores) < 3:
    fail("At least three service risk scores must be validated.")
for score in scores:
    if score.get("status") != "pass":
        fail(f"Risk score validation failed for service: {score.get('service')}")
    if not score.get("service"):
        fail("Service name is required in risk score output.")
    value = score.get("risk_score", -1)
    if not isinstance(value, int) or value < 0 or value > 100:
        fail(f"Risk score must be an integer between 0 and 100: {score.get('service')}")
    if score.get("risk_level") not in {"low", "medium", "high"}:
        fail(f"Risk level must be low, medium, or high: {score.get('service')}")


# Task 3: backtesting evidence.
if backtest.get("validation_result", {}).get("status") != "pass":
    fail("Backtesting validation must pass.")
if backtest.get("backtest_window", {}).get("incident_set_size", 0) < 10:
    fail("Backtesting must include at least 10 incidents.")
metrics = backtest.get("metrics", {})
thresholds = backtest.get("minimum_thresholds", {})
for metric in ("precision", "recall", "f1_score"):
    if metric not in metrics or metric not in thresholds:
        fail(f"Backtesting metric is missing: {metric}")
    if metrics[metric] < thresholds[metric]:
        fail(f"Backtesting metric below minimum threshold: {metric}")
iterations = backtest.get("threshold_tuning_iterations", [])
if len(iterations) < 2:
    fail("Backtesting must include threshold tuning iterations.")
for item in iterations:
    if item.get("precision", 0) <= 0 or item.get("recall", 0) <= 0:
        fail("Backtesting threshold iterations must include valid precision and recall.")


# Task 4: hybrid retrieval evidence bundles.
if hybrid.get("validation_result", {}).get("status") != "pass":
    fail("Hybrid retrieval validation must pass.")
if hybrid.get("orchestrator", {}).get("status") != "pass":
    fail("Hybrid retrieval orchestrator status must pass.")
source_set = set(hybrid.get("orchestrator", {}).get("sources", []))
if source_set != REQUIRED_RETRIEVAL_SOURCES:
    fail("Hybrid retrieval must combine vector and graph sources.")
bundles = hybrid.get("evidence_bundles", [])
if len(bundles) < 2:
    fail("At least two hybrid evidence bundles are required.")
for bundle in bundles:
    if bundle.get("status") != "pass":
        fail(f"Hybrid evidence bundle failed: {bundle.get('bundle_id')}")
    if not bundle.get("bundle_id") or not bundle.get("incident_id"):
        fail("Hybrid evidence bundles require bundle and incident IDs.")
    if len(bundle.get("vector_evidence_links", [])) < 1:
        fail(f"Hybrid evidence bundle missing vector links: {bundle.get('bundle_id')}")
    if len(bundle.get("graph_evidence_links", [])) < 1:
        fail(f"Hybrid evidence bundle missing graph links: {bundle.get('bundle_id')}")
    if not bundle.get("traceable_lineage"):
        fail(f"Hybrid evidence bundle must be traceable: {bundle.get('bundle_id')}")


# Task 5: human approval workflow.
if approval.get("validation_result", {}).get("status") != "pass":
    fail("Human approval workflow validation must pass.")
workflow = approval.get("workflow", {})
if workflow.get("status") != "pass":
    fail("Human approval workflow status must pass.")
if not workflow.get("approval_required"):
    fail("Approval must be required for assisted RCA recommendations.")
if workflow.get("auto_execute_without_approval"):
    fail("Recommendations must not execute without approval.")
stages = {stage.get("stage") for stage in approval.get("approval_stages", [])}
if stages != REQUIRED_APPROVAL_STAGES:
    fail("Approval stages are incomplete.")
for stage in approval.get("approval_stages", []):
    if stage.get("status") != "pass":
        fail(f"Approval stage failed: {stage.get('stage')}")
audit_controls = approval.get("audit_controls", {})
if audit_controls.get("status") != "pass":
    fail("Approval audit controls must pass.")
fields = set(audit_controls.get("decision_log_required_fields", []))
if fields != REQUIRED_AUDIT_FIELDS:
    fail("Approval audit required fields do not match baseline.")
if not audit_controls.get("tamper_evident_log_storage"):
    fail("Approval decision logs must be tamper-evident.")


# Task 6: pilot go or hold record.
if pilot.get("validation_result", {}).get("status") != "pass":
    fail("Pilot decision validation must pass.")
if pilot.get("pilot", {}).get("status") != "pass":
    fail("Pilot status must pass.")
decision = pilot.get("decision_record", {})
if decision.get("decision") not in ALLOWED_DECISIONS:
    fail("Pilot decision must be either go or hold.")
if not decision.get("signed_off"):
    fail("Pilot decision must be signed off by stakeholders.")
if len(decision.get("signatories", [])) < 2:
    fail("Pilot decision must include at least two signatories.")
for risk in decision.get("open_risks", []):
    if not risk.get("risk_id") or not risk.get("owner") or not risk.get("due_date"):
        fail("Open risks must include risk_id, owner, and due_date.")

print("Batch 12 risk scoring and assisted RCA checks passed.")
PY
