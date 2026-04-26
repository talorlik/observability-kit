#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 6 metrics and traces pipeline artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import re
import sys

base = Path("contracts") / "metrics_traces"

metrics = json.loads((base / "METRICS_COLLECTION_BASELINE_VALIDATION.json").read_text())
scrape = json.loads((base / "SCRAPE_ONBOARDING_VALIDATION.json").read_text())
otlp = json.loads((base / "OTLP_METRICS_TRACES_INGEST_VALIDATION.json").read_text())
cardinality = json.loads((base / "CARDINALITY_GUARDRAILS_VALIDATION.json").read_text())
sampling = json.loads((base / "TRACE_SAMPLING_POLICY_VALIDATION.json").read_text())
correlation = json.loads((base / "CORRELATION_PIVOT_VALIDATION.json").read_text())

METRICS_INDEX_REGEX = re.compile(r"^metrics-[a-z0-9]+-[a-z0-9-]+-\d{4}\.\d{2}\.\d{2}$")
TRACES_INDEX_REGEX = re.compile(r"^traces-[a-z0-9]+-[a-z0-9-]+-\d{4}\.\d{2}\.\d{2}$")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: infrastructure and workload metrics baseline ingestion.
if metrics.get("validation_result", {}).get("status") != "pass":
    fail("Metrics baseline validation must pass.")
required_families = set(metrics.get("required_metric_families", []))
if len(required_families) < 5:
    fail("Metrics baseline must include at least 5 required metric families.")
coverage = metrics.get("namespace_coverage", {})
if coverage.get("observed_coverage_percent", 0) < 100:
    fail("Namespace coverage must be 100 percent for test namespaces.")
if coverage.get("missing_namespaces"):
    fail("Metrics baseline cannot include missing test namespaces.")
for index_name in metrics.get("index_targets", []):
    if METRICS_INDEX_REGEX.fullmatch(index_name) is None:
        fail(f"Invalid metrics index naming example: {index_name}")


# Task 2: annotation/label scrape onboarding.
if scrape.get("validation_result", {}).get("status") != "pass":
    fail("Scrape onboarding validation must pass.")
if set(scrape.get("onboarding_modes", [])) != {"annotation", "label"}:
    fail("Scrape onboarding must include both annotation and label modes.")
controls = scrape.get("required_controls", {})
if not controls.get("annotation_key") or not controls.get("label_key"):
    fail("Scrape onboarding controls must define annotation and label keys.")
if controls.get("opt_in_value") != "true":
    fail("Scrape onboarding opt-in value must be true.")
for service_test in scrape.get("service_tests", []):
    if service_test.get("status") != "pass":
        fail(f"Scrape onboarding service test failed: {service_test.get('service')}")
    if not service_test.get("metrics_found"):
        fail(f"Scrape onboarding metrics missing: {service_test.get('service')}")
    if METRICS_INDEX_REGEX.fullmatch(service_test.get("target_index", "")) is None:
        fail(
            "Opted-in workload metrics must be indexed to metrics-* naming pattern "
            f"for service: {service_test.get('service')}"
        )


# Task 3: OTLP metrics and traces ingestion.
if otlp.get("validation_result", {}).get("status") != "pass":
    fail("OTLP ingest validation must pass.")
protocols = set(otlp.get("otlp_protocols", []))
if "grpc" not in protocols:
    fail("OTLP ingest must validate grpc protocol path.")
if "http/protobuf" not in protocols:
    fail("OTLP ingest must validate http/protobuf protocol path.")
signals = {item.get("signal") for item in otlp.get("ingest_tests", [])}
if signals != {"metrics", "traces"}:
    fail("OTLP ingest tests must include metrics and traces signals.")
for test in otlp.get("ingest_tests", []):
    if test.get("status") != "pass":
        fail(f"OTLP ingest test failed: {test.get('name')}")
    if test.get("signal") == "metrics":
        if test.get("accepted_points", 0) <= 0:
            fail("OTLP metrics ingest must include accepted points.")
        if test.get("dropped_points", -1) != 0:
            fail("OTLP metrics ingest cannot drop points in baseline test.")
        if METRICS_INDEX_REGEX.fullmatch(test.get("target_index", "")) is None:
            fail(f"Invalid OTLP metrics target index: {test.get('target_index')}")
    if test.get("signal") == "traces":
        if test.get("accepted_spans", 0) <= 0:
            fail("OTLP trace ingest must include accepted spans.")
        if test.get("dropped_spans", -1) != 0:
            fail("OTLP trace ingest cannot drop spans in baseline test.")
        if TRACES_INDEX_REGEX.fullmatch(test.get("target_index", "")) is None:
            fail(f"Invalid OTLP traces target index: {test.get('target_index')}")


# Task 4: cardinality budgets and prohibited label policy.
if cardinality.get("validation_result", {}).get("status") != "pass":
    fail("Cardinality guardrail validation must pass.")
policy = cardinality.get("cardinality_policy", {})
if policy.get("max_label_keys_per_metric", 0) <= 0:
    fail("Cardinality policy must define positive max label keys.")
if policy.get("max_unique_label_values_per_key", 0) <= 0:
    fail("Cardinality policy must define positive unique label budget.")
if not policy.get("prohibited_labels"):
    fail("Cardinality policy must include prohibited labels.")
if cardinality.get("enforcement_mode") not in {"drop", "block"}:
    fail("Cardinality guardrail enforcement mode must be drop or block.")
for case in cardinality.get("violation_tests", []):
    if case.get("status") != "pass":
        fail(f"Cardinality violation test failed: {case.get('name')}")
    if case.get("dropped_series", 0) < case.get("violating_series_seen", 0):
        fail(f"Cardinality enforcement insufficient in case: {case.get('name')}")
if cardinality.get("validation_result", {}).get("effective_block_or_drop_rate_percent", 0) < 100:
    fail("Cardinality guardrails must fully block or drop violating series.")


# Task 5: sampling default and environment overrides.
if sampling.get("validation_result", {}).get("status") != "pass":
    fail("Trace sampling validation must pass.")
default = sampling.get("default_policy", {})
if default.get("sampler") != "parentbased_traceidratio":
    fail("Default sampler must be parentbased_traceidratio.")
if not (0 < default.get("ratio", 0) <= 1):
    fail("Default sampling ratio must be in (0, 1].")
if not sampling.get("environment_overrides"):
    fail("Sampling validation must include environment overrides.")
for result in sampling.get("observed_sampling_results", []):
    if result.get("status") != "pass":
        fail(
            "Sampling result failed for "
            f"{result.get('environment')}/{result.get('tier')}"
        )
    observed = result.get("observed_ratio")
    expected_min = result.get("expected_min")
    expected_max = result.get("expected_max")
    if observed is None or expected_min is None or expected_max is None:
        fail("Sampling result is missing expected ratio boundaries.")
    if not (expected_min <= observed <= expected_max):
        fail(
            "Observed sampling ratio out of expected range for "
            f"{result.get('environment')}/{result.get('tier')}"
        )


# Task 6: metrics-traces-logs correlation pivot behavior.
if correlation.get("validation_result", {}).get("status") != "pass":
    fail("Correlation pivot validation must pass.")
required_fields = set(correlation.get("required_correlation_fields", []))
for field in {"service.name", "deployment.environment", "k8s.cluster.name", "trace_id", "span_id"}:
    if field not in required_fields:
        fail(f"Correlation fields are missing required field: {field}")
for pivot in correlation.get("pivot_tests", []):
    if pivot.get("status") != "pass":
        fail(f"Correlation pivot test failed: {pivot.get('name')}")
    if "expected_min_trace_hits" in pivot and pivot.get("observed_trace_hits", 0) < pivot.get("expected_min_trace_hits", 0):
        fail(f"Metric to trace pivot hits below expectation: {pivot.get('name')}")
    if "expected_min_log_hits" in pivot and pivot.get("observed_log_hits", 0) < pivot.get("expected_min_log_hits", 0):
        fail(f"Trace to log pivot hits below expectation: {pivot.get('name')}")
    if "expected_min_metric_points" in pivot and pivot.get("observed_metric_points", 0) < pivot.get("expected_min_metric_points", 0):
        fail(f"Log to metric pivot points below expectation: {pivot.get('name')}")

if not correlation.get("validation_result", {}).get("operator_pivot_workflow_tested"):
    fail("Correlation pivot must confirm operator pivot workflow test evidence.")

observed_sources = {pivot.get("source") for pivot in correlation.get("pivot_tests", [])}
if {"synthetic", "pilot"} - observed_sources:
    fail("Correlation pivots must include both synthetic and pilot test evidence.")

print("Batch 6 metrics and traces pipeline checks passed.")
PY
