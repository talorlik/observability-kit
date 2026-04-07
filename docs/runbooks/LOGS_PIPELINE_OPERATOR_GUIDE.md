# Logs Pipeline Operator Guide

This guide defines how to validate Batch 5 (`TB-05`) logs pipeline artifacts
for `TR-06` and `TR-07`.

## Inputs

Batch 5 sample artifacts are stored in:

- `contracts/logs/CRI_JSON_PARSING_VALIDATION.json`
- `contracts/logs/MULTILINE_GROUPING_VALIDATION.json`
- `contracts/logs/SENSITIVE_FIELD_REDACTION_VALIDATION.json`
- `contracts/logs/LOGS_INDEX_TEMPLATE_POLICY.json`
- `contracts/logs/TRACE_CORRELATION_VALIDATION.json`

## What Is Validated

1. CRI parsing and JSON extraction defaults produce required base log fields.
1. Multiline grouping rules combine supported stack traces into single events.
1. Sensitive fields are redacted and never-index policy fields are present.
1. `logs-*` template rules enforce strict mapping and naming policy.
1. `trace_id` and `span_id` correlation behavior supports trace-linked queries.

## Command

Run the Batch 5 validation script:

```bash
bash scripts/ci/validate_logs_pipeline.sh
```

Expected success output:

```bash
Batch 5 logs pipeline checks passed.
```

## Failure Handling

- If CRI or JSON parsing fails, inspect filelog receiver parser chain order.
- If multiline grouping fails, verify start and continuation regex definitions.
- If redaction fails, update sensitive field matchers and never-index list.
- If template checks fail, reconcile `logs-*` index pattern and strict mappings.
- If correlation checks fail, verify trace context propagation at log emitters.
