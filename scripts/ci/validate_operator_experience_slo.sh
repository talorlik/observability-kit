#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 9 operator experience and SLO operations artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

base = Path("contracts") / "slo_ops"

taxonomy = json.loads((base / "DASHBOARD_TAXONOMY_VALIDATION.json").read_text())
platform_alerts = json.loads(
    (base / "PLATFORM_HEALTH_ALERTS_VALIDATION.json").read_text()
)
sli_slo = json.loads((base / "SLI_SLO_QUERY_STABILITY_VALIDATION.json").read_text())
burn_symptom = json.loads(
    (base / "BURN_RATE_SYMPTOM_ALERTS_VALIDATION.json").read_text()
)
drill = json.loads((base / "INCIDENT_DRILL_EVIDENCE_VALIDATION.json").read_text())
noise = json.loads((base / "ALERT_NOISE_REDUCTION_VALIDATION.json").read_text())

REQUIRED_DOMAINS = {"platform", "service", "governance"}
REQUIRED_PREFIXES = {"platform-", "service-", "governance-"}
REQUIRED_PLATFORM_SIGNALS = {
    "otelcol_receiver_dropped_metric_points",
    "opensearch_ingest_lag_seconds",
    "opensearch_cluster_health_status",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: dashboard taxonomy.
if taxonomy.get("validation_result", {}).get("status") != "pass":
    fail("Dashboard taxonomy validation must pass.")
if set(taxonomy.get("taxonomy_domains", [])) != REQUIRED_DOMAINS:
    fail("Dashboard taxonomy domains must include platform, service, governance.")
if set(taxonomy.get("required_prefixes", [])) != REQUIRED_PREFIXES:
    fail("Dashboard naming prefixes must include platform, service, governance.")
for dashboard in taxonomy.get("dashboards", []):
    if dashboard.get("status") != "pass":
        fail(f"Dashboard taxonomy check failed: {dashboard.get('name')}")


# Task 2: platform health alerts.
if platform_alerts.get("validation_result", {}).get("status") != "pass":
    fail("Platform health alerts validation must pass.")
if len(platform_alerts.get("routing_channels", [])) < 1:
    fail("Platform health alerts must define at least one routing channel.")
signals = {alert.get("signal") for alert in platform_alerts.get("alerts", [])}
if signals != REQUIRED_PLATFORM_SIGNALS:
    fail("Platform health alert signals do not match expected baseline.")
for alert in platform_alerts.get("alerts", []):
    if alert.get("status") != "pass":
        fail(f"Platform alert check failed: {alert.get('name')}")
    if not alert.get("routed_to_expected_channel"):
        fail(f"Platform alert did not route as expected: {alert.get('name')}")


# Task 3: SLI and SLO query stability.
if sli_slo.get("validation_result", {}).get("status") != "pass":
    fail("SLI and SLO query stability validation must pass.")
if len(sli_slo.get("pilot_services", [])) < 1:
    fail("SLI and SLO validation must include pilot services.")
for query in sli_slo.get("sli_queries", []):
    runs = query.get("evaluation_runs", 0)
    success = query.get("success_runs", 0)
    if runs < 3:
        fail(f"SLI query has insufficient evaluation runs: {query.get('name')}")
    if success != runs:
        fail(f"SLI query is not stable across runs: {query.get('name')}")
if len(sli_slo.get("slo_targets", [])) < 1:
    fail("At least one SLO target is required.")


# Task 4: burn-rate and symptom alerts.
if burn_symptom.get("validation_result", {}).get("status") != "pass":
    fail("Burn-rate and symptom alert validation must pass.")
for alert in burn_symptom.get("alerts", []):
    if alert.get("status") != "pass":
        fail(f"Burn-rate or symptom alert failed: {alert.get('name')}")
    runbook = alert.get("runbook_link", "")
    if not runbook.startswith("docs/runbooks/"):
        fail(f"Alert is missing valid runbook link: {alert.get('name')}")


# Task 5: incident drill evidence.
if drill.get("validation_result", {}).get("status") != "pass":
    fail("Incident drill evidence validation must pass.")
if drill.get("drill", {}).get("environment") == "production":
    fail("Incident drill must run in non-production.")
if drill.get("drill", {}).get("response_timeline_minutes", 0) <= 0:
    fail("Incident drill response timeline must be a positive value.")
if len(drill.get("evidence_artifacts", [])) < 3:
    fail("Incident drill must include evidence artifacts.")
if len(drill.get("follow_ups", [])) < 1:
    fail("Incident drill must include follow-up actions.")


# Task 6: alert-noise reduction.
if noise.get("validation_result", {}).get("status") != "pass":
    fail("Alert-noise reduction validation must pass.")
cycles = noise.get("review_cycles", [])
if len(cycles) < noise.get("improvement_checks", {}).get("minimum_review_cycles", 2):
    fail("Alert-noise tracking must include at least two review cycles.")
for i in range(1, len(cycles)):
    if cycles[i]["false_positive_rate_percent"] >= cycles[i - 1]["false_positive_rate_percent"]:
        fail("False-positive rate must improve across review cycles.")
    if cycles[i]["alerts_per_day"] >= cycles[i - 1]["alerts_per_day"]:
        fail("Alerts per day must improve across review cycles.")
if not noise.get("improvement_checks", {}).get("false_positive_trend_improving"):
    fail("False-positive trend flag must be true.")
if not noise.get("improvement_checks", {}).get("alerts_per_day_trend_improving"):
    fail("Alert volume trend flag must be true.")

print("Batch 9 operator experience and SLO operations checks passed.")
PY
