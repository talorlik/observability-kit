#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 5 base control plane scaffolding..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
base = root / "gitops" / "platform" / "ai" / "base"
overlays = root / "gitops" / "platform" / "ai" / "overlays"

required_files = [
    base / "kustomization.yaml",
    base / "kagent" / "deployment.yaml",
    base / "khook" / "deployment.yaml",
    base / "kmcp" / "deployment.yaml",
    base / "kmcp" / "mcpserver-sample.yaml",
    base / "gateway" / "deployment.yaml",
    base / "gateway" / "networkpolicy.yaml",
    overlays / "quickstart" / "kustomization.yaml",
    overlays / "dev" / "kustomization.yaml",
    overlays / "staging" / "kustomization.yaml",
    overlays / "prod" / "kustomization.yaml",
]
for path in required_files:
    if not path.exists():
        fail(f"Missing required Batch 5 scaffold artifact: {path}")


def load_all(path: Path):
    return [doc for doc in yaml.safe_load_all(path.read_text()) if doc]


# 1) External PostgreSQL and Kagent health
kagent_docs = load_all(base / "kagent" / "deployment.yaml")
kagent_dep = next((d for d in kagent_docs if d.get("kind") == "Deployment"), None)
if not kagent_dep:
    fail("Kagent deployment manifest missing.")
container = kagent_dep["spec"]["template"]["spec"]["containers"][0]
env_names = {item.get("name") for item in container.get("env", [])}
required_pg_env = {
    "KAGENT_POSTGRES_HOST",
    "KAGENT_POSTGRES_PORT",
    "KAGENT_POSTGRES_DB",
    "KAGENT_POSTGRES_USER",
    "KAGENT_POSTGRES_PASSWORD",
}
if not required_pg_env.issubset(env_names):
    fail("Kagent manifest missing external PostgreSQL configuration env vars.")
if "readinessProbe" not in container or "livenessProbe" not in container:
    fail("Kagent deployment must include readiness and liveness probes.")

# 2) kmcp and MCP CRD reconciliation
kmcp_docs = load_all(base / "kmcp" / "deployment.yaml")
kmcp_dep = next((d for d in kmcp_docs if d.get("kind") == "Deployment"), None)
if not kmcp_dep:
    fail("kmcp deployment manifest missing.")
kmcp_container = kmcp_dep["spec"]["template"]["spec"]["containers"][0]
if "readinessProbe" not in kmcp_container:
    fail("kmcp deployment must include readiness probe.")
mcp_sample = yaml.safe_load((base / "kmcp" / "mcpserver-sample.yaml").read_text())
if mcp_sample.get("kind") != "MCPServer":
    fail("kmcp sample must include MCPServer resource for reconciliation checks.")
if mcp_sample.get("spec", {}).get("discovery", {}).get("enabled") is not False:
    fail("MCPServer sample must disable direct discovery for gateway-fronted mode.")
if mcp_sample.get("spec", {}).get("endpoint", {}).get("mode") != "gateway":
    fail("MCPServer sample must use gateway endpoint mode.")
remote_ref = mcp_sample.get("spec", {}).get("endpoint", {}).get("remoteMCPServerRef", {})
if remote_ref.get("name") != "ai-gateway-catalog":
    fail("MCPServer sample must reference ai-gateway-catalog remote endpoint.")
if remote_ref.get("namespace") != "ai-gateway":
    fail("MCPServer sample must reference ai-gateway namespace.")
health_check = mcp_sample.get("spec", {}).get("healthCheck", {})
if health_check.get("path") != "/healthz":
    fail("MCPServer sample must define baseline health path /healthz.")
if int(health_check.get("intervalSeconds", 0)) <= 0:
    fail("MCPServer sample must define a positive health check interval.")

# 3) Khook controller readiness
khook_docs = load_all(base / "khook" / "deployment.yaml")
khook_dep = next((d for d in khook_docs if d.get("kind") == "Deployment"), None)
if not khook_dep:
    fail("Khook deployment manifest missing.")
khook_container = khook_dep["spec"]["template"]["spec"]["containers"][0]
if "readinessProbe" not in khook_container or "livenessProbe" not in khook_container:
    fail("Khook deployment must include readiness and liveness probes.")

# 4) Gateway reachability and policy controls
gateway_docs = load_all(base / "gateway" / "deployment.yaml")
gateway_dep = next((d for d in gateway_docs if d.get("kind") == "Deployment"), None)
gateway_svc = next((d for d in gateway_docs if d.get("kind") == "Service"), None)
if not gateway_dep or not gateway_svc:
    fail("Gateway deployment and service manifests are both required.")
gw_container = gateway_dep["spec"]["template"]["spec"]["containers"][0]
if "readinessProbe" not in gw_container:
    fail("Gateway deployment must include readiness probe.")
gw_readiness_path = (
    gw_container.get("readinessProbe", {})
    .get("httpGet", {})
    .get("path")
)
if gw_readiness_path != "/readyz":
    fail("Gateway readiness probe must use /readyz endpoint.")
svc_ports = gateway_svc.get("spec", {}).get("ports", [])
if not any(port.get("port") == 8082 for port in svc_ports):
    fail("Gateway service must expose baseline MCP port 8082.")
policy = yaml.safe_load((base / "gateway" / "networkpolicy.yaml").read_text())
if policy.get("kind") != "NetworkPolicy":
    fail("Gateway policy control must be represented by a NetworkPolicy.")

# 5) Baseline OpenTelemetry visibility
for dep in [kagent_dep, khook_dep, kmcp_dep, gateway_dep]:
    annotations = dep["spec"]["template"]["metadata"].get("annotations", {})
    if annotations.get("instrumentation.opentelemetry.io/inject-sdk") != "true":
        fail("All base control plane deployments must include OTEL inject annotation.")

# 6) GitOps overlay render and sync checks
for name in ["quickstart", "dev", "staging", "prod"]:
    kustomization = yaml.safe_load((overlays / name / "kustomization.yaml").read_text())
    resources = kustomization.get("resources", [])
    if "../../base" not in resources:
        fail(f"Overlay {name} must include ../../base resource link.")

print("Batch 5 base control plane scaffold checks passed.")
PY

echo "Checking overlay kustomization renderability..."
if command -v kustomize >/dev/null 2>&1; then
  for overlay in quickstart dev staging prod; do
    kustomize build "gitops/platform/ai/overlays/$overlay" >/dev/null
  done
elif command -v kubectl >/dev/null 2>&1; then
  for overlay in quickstart dev staging prod; do
    kubectl kustomize "gitops/platform/ai/overlays/$overlay" >/dev/null
  done
else
  echo "Neither kustomize nor kubectl found; skipping live render command checks."
fi

echo "Batch 5 overlay render checks passed."
