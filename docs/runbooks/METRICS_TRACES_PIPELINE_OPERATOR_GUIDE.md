# Metrics Traces Pipeline Operator Guide

This guide defines how to validate Batch 6 (`TB-06`) metrics and traces
pipeline artifacts for `TR-06` and `TR-07`.

## Inputs

Batch 6 sample artifacts are stored in:

- `contracts/metrics_traces/METRICS_COLLECTION_BASELINE_VALIDATION.json`
- `contracts/metrics_traces/SCRAPE_ONBOARDING_VALIDATION.json`
- `contracts/metrics_traces/OTLP_METRICS_TRACES_INGEST_VALIDATION.json`
- `contracts/metrics_traces/CARDINALITY_GUARDRAILS_VALIDATION.json`
- `contracts/metrics_traces/TRACE_SAMPLING_POLICY_VALIDATION.json`
- `contracts/metrics_traces/CORRELATION_PIVOT_VALIDATION.json`

## What Is Validated

1. Infrastructure and workload metrics ingestion baseline across test namespaces.
1. Annotation and label based scrape onboarding for opted-in services.
1. OTLP metrics and traces ingest path behavior for instrumented services.
1. Cardinality guardrails and prohibited label policy enforcement.
1. Trace sampling defaults with environment and service-tier overrides.
1. Metrics to traces to logs correlation pivot workflows.

## Command

Run the Batch 6 validation script:

```bash
bash scripts/ci/validate_metrics_traces_pipeline.sh
```

Expected success output:

```bash
Batch 6 metrics and traces pipeline checks passed.
```

## Failure Handling

- If metrics baseline fails, verify receiver and processor routing in agent
  and gateway pipelines.
- If scrape onboarding fails, verify annotation and label keys and
  service-discovery relabeling.
- If OTLP ingest fails, verify protocol listeners and exporter route
  configuration.
- If cardinality checks fail, tighten label-drop and block rules in the
  metrics pipeline policy.
- If sampling checks fail, verify environment or tier overrides at gateway
  trace processor configuration.
- If correlation pivots fail, verify `trace_id` and `span_id` propagation
  and index mappings for logs and traces.
