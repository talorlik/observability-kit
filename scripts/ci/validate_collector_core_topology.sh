#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 4 collector core topology artifacts..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

base = Path("contracts") / "collector"

agent = json.loads((base / "AGENT_DAEMONSET_PROFILE.json").read_text())
gateway = json.loads((base / "GATEWAY_DEPLOYMENT_PROFILE.json").read_text())
attach = json.loads((base / "OTLP_EXPORT_ATTACH_TEST.json").read_text())
standalone = json.loads((base / "OTLP_EXPORT_STANDALONE_TEST.json").read_text())
self_obs = json.loads((base / "SELF_OBSERVABILITY_BASELINE.json").read_text())
failure = json.loads((base / "FAILURE_SIMULATION_EVIDENCE.json").read_text())

REQUIRED_PROCESSORS = {"k8sattributes", "resource", "memory_limiter", "batch"}
REQUIRED_SELF_OBS_METRICS = {
    "otelcol_exporter_queue_size",
    "otelcol_exporter_send_failed_log_records",
    "otelcol_exporter_send_failed_metric_points",
    "otelcol_exporter_send_failed_spans",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


# Task 1: agent health and scheduling.
agent_sched = agent.get("scheduling_validation", {})
if agent_sched.get("status") != "pass":
    fail("Agent scheduling validation must pass.")
if agent_sched.get("eligible_nodes", 0) <= 0:
    fail("Agent eligible node count must be greater than zero.")
if agent_sched.get("scheduled_pods") != agent_sched.get("eligible_nodes"):
    fail("Agent must be scheduled on all eligible nodes.")


# Task 2: gateway health.
gateway_health = gateway.get("health_validation", {})
if gateway_health.get("status") != "pass":
    fail("Gateway health validation must pass.")
if gateway_health.get("readiness_probe") != "pass":
    fail("Gateway readiness probe must pass.")
if gateway_health.get("liveness_probe") != "pass":
    fail("Gateway liveness probe must pass.")


# Task 3: required processors present.
agent_processors = set(agent.get("profile", {}).get("processors", []))
gateway_processors = set(gateway.get("profile", {}).get("processors", []))
if not REQUIRED_PROCESSORS.issubset(agent_processors):
    fail("Agent profile missing one or more required processors.")
if not REQUIRED_PROCESSORS.issubset(gateway_processors):
    fail("Gateway profile missing one or more required processors.")


# Task 4: OTLP export behavior for attach and standalone.
for mode_name, payload in [("attach", attach), ("standalone", standalone)]:
    result = payload.get("results", {})
    if result.get("status") != "pass":
        fail(f"OTLP export test failed for mode: {mode_name}")
    if result.get("export_handshake") != "pass":
        fail(f"OTLP handshake failed for mode: {mode_name}")
    if result.get("otlp_delivery") != "pass":
        fail(f"OTLP delivery failed for mode: {mode_name}")
    dropped = result.get("dropped_items_total")
    if dropped is None or dropped < 0:
        fail(f"OTLP dropped items value invalid for mode: {mode_name}")


# Task 5: self-observability metrics and dashboard baseline.
self_metrics = set(self_obs.get("required_metrics", []))
if not REQUIRED_SELF_OBS_METRICS.issubset(self_metrics):
    fail("Self-observability baseline missing required queue/retry/drop metrics.")

query_validation = self_obs.get("query_validation", {})
for key in ("queue_depth_queryable", "retries_queryable", "drops_queryable"):
    if query_validation.get(key) is not True:
        fail(f"Self-observability query validation failed for: {key}")
if query_validation.get("status") != "pass":
    fail("Self-observability status must pass.")


# Task 6: failure simulation evidence with bounded-loss behavior.
simulations = failure.get("simulations", [])
required_scenarios = {"gateway_restart", "temporary_backend_outage"}
present = {sim.get("name") for sim in simulations}
if not required_scenarios.issubset(present):
    fail("Failure evidence must include gateway restart and backend outage.")

for sim in simulations:
    if sim.get("result") != "pass":
        fail(f"Failure simulation did not pass: {sim.get('name')}")
    if sim.get("bounded_loss") is not True:
        fail(f"Failure simulation must demonstrate bounded loss: {sim.get('name')}")

print("Batch 4 collector core topology checks passed.")
PY
