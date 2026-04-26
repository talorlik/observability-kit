#!/usr/bin/env bash
#
# Batch 14 smoke wrapper: AI/MCP runtime validation and productization.
#
# Aggregates the AI agent boundary, governance, and state contract checks plus
# the MCP catalog/gateway checks and the runtime/scaffolding/release validators.
# Run separately from Batches 1-13 because the AI/MCP layer is a higher-order
# tier that depends on (but is not part of) the core observability platform.
#
# Cloud-agnostic: every script invoked here validates only Kubernetes-resident
# components and contract artifacts.

set -euo pipefail

echo "Running Batch 14 (AI/MCP) smoke validation suite..."

bash scripts/ci/validate_ai_boundary_contracts.sh
bash scripts/ci/validate_ai_governance_contracts.sh
bash scripts/ci/validate_ai_state_contracts.sh
bash scripts/ci/validate_mcp_contracts.sh
bash scripts/ci/validate_ai_runtime_base_scaffolding.sh
bash scripts/ci/validate_mcp_read_path_scaffolding.sh
bash scripts/ci/validate_multi_agent_scaffolding.sh
bash scripts/ci/validate_khook_trigger_scaffolding.sh
bash scripts/ci/validate_action_gate_scaffolding.sh
bash scripts/ci/validate_kagent_khook_release.sh

echo "Batch 14 smoke validation complete."
