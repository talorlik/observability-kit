# Collector Core Topology Operator Guide

This guide defines how to validate Batch 4 (`TB-04`) collector core topology
artifacts for `TR-06` and `TR-11`.

## Inputs

Batch 4 sample artifacts are stored in:

- `contracts/collector/AGENT_DAEMONSET_PROFILE.json`
- `contracts/collector/GATEWAY_DEPLOYMENT_PROFILE.json`
- `contracts/collector/OTLP_EXPORT_ATTACH_TEST.json`
- `contracts/collector/OTLP_EXPORT_STANDALONE_TEST.json`
- `contracts/collector/SELF_OBSERVABILITY_BASELINE.json`
- `contracts/collector/FAILURE_SIMULATION_EVIDENCE.json`

## What Is Validated

1. Agent DaemonSet health and scheduling coverage on eligible nodes.
1. Gateway deployment health including readiness and liveness status.
1. Mandatory processors in collector profiles:
   - `k8sattributes`
   - `resource`
   - `memory_limiter`
   - `batch`
1. OTLP export behavior in both deployment modes:
   - attach
   - standalone
1. Collector self-observability metrics and baseline dashboard queryability:
   - queue depth
   - retries
   - drops
1. Failure simulation evidence for:
   - gateway restart
   - temporary backend outage

## Command

Run the Batch 4 validation script:

```bash
bash scripts/ci/validate_collector_core_topology.sh
```

Expected success output:

```bash
Batch 4 collector core topology checks passed.
```

## Failure Handling

- If agent scheduling fails, inspect DaemonSet tolerations and node selectors.
- If gateway probes fail, verify resource limits and receiver or exporter config.
- If required processors are missing, update collector processor chains.
- If OTLP export fails in attach mode, verify external endpoint and TLS trust.
- If OTLP export fails in standalone mode, verify in-cluster service endpoint.
- If bounded-loss evidence fails, tune queue, retry, and memory limits.
