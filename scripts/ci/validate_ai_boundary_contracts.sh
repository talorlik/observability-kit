#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 1 AI boundary and protocol contracts..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
boundary_path = root / "contracts" / "ai" / "BOUNDARY_CONTRACT_V1.yaml"
protocol_path = root / "contracts" / "ai" / "PROTOCOL_EDGES_V1.yaml"
replaceability_path = root / "contracts" / "ai" / "REPLACEABILITY_MATRIX_V1.md"
namespace_path = root / "contracts" / "ai" / "NAMESPACE_BOUNDARY_RULES_V1.yaml"
deny_policy_path = root / "contracts" / "policy" / "NO_DIRECT_DATASTORE_ACCESS.rego"

for required in [
    boundary_path,
    protocol_path,
    replaceability_path,
    namespace_path,
    deny_policy_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 1 contract artifact: {required}")

boundary = yaml.safe_load(boundary_path.read_text())
protocol = yaml.safe_load(protocol_path.read_text())
namespace_rules = yaml.safe_load(namespace_path.read_text())
replaceability = replaceability_path.read_text()
deny_policy = deny_policy_path.read_text()


def find_forbidden_markers(scan_roots: list[Path], patterns: list[str]) -> list[str]:
    violations: list[str] = []
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for file_path in scan_root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".go",
                ".java",
                ".yaml",
                ".yml",
                ".json",
                ".rego",
                ".md",
                ".sh",
            }:
                continue
            text = file_path.read_text(errors="ignore")
            for pattern in patterns:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    violations.append(
                        "Detected potential direct datastore access marker in "
                        f"{file_path}: pattern {pattern}"
                    )
    return violations

expected_path = [
    "khook",
    "kagent",
    "gatewayed_mcp",
    "platform_apis",
    "platform_backends",
]
actual_path = boundary.get("runtime_boundary", {}).get("canonical_path", [])
if actual_path != expected_path:
    fail("Boundary canonical path does not match required architecture path.")

prohibited = {
    (entry.get("from"), entry.get("to"))
    for entry in boundary.get("runtime_boundary", {}).get("prohibited_direct_paths", [])
}
for edge in [
    ("ai_components", "opensearch_native"),
    ("ai_components", "neo4j_native"),
    ("ai_components", "sql_native"),
]:
    if edge not in prohibited:
        fail(f"Boundary contract missing prohibited direct path: {edge[0]} -> {edge[1]}")

for token in [
    "opensearch_native",
    "neo4j_native",
    "sql_native",
    "direct datastore access denied",
]:
    if token not in deny_policy:
        fail(f"Deny policy missing required token: {token}")

required_headings = [
    "# Replaceability Matrix V1",
    "## Compatibility Rules",
    "## Swap Matrix",
]
for heading in required_headings:
    if heading not in replaceability:
        fail(f"Replaceability matrix missing section: {heading}")

expected_replaceability_components = [
    "Khook controller",
    "Kagent orchestrator",
    "MCP gateway",
    "MCP services",
]
for component in expected_replaceability_components:
    if f"| {component} |" not in replaceability:
        fail(f"Replaceability matrix missing required component row: {component}")

required_contract_refs = [
    "BOUNDARY_CONTRACT_V1.yaml",
    "PROTOCOL_EDGES_V1.yaml#/edges/khook_to_kagent",
    "PROTOCOL_EDGES_V1.yaml#/edges/agent_to_agent",
    "PROTOCOL_EDGES_V1.yaml#/edges/agent_to_mcp",
]
for contract_ref in required_contract_refs:
    if contract_ref not in replaceability:
        fail(
            "Replaceability matrix missing required compatibility contract reference: "
            f"{contract_ref}"
        )

edge_map = protocol.get("edges", {})
for edge_name in ["khook_to_kagent", "agent_to_agent", "agent_to_mcp"]:
    edge = edge_map.get(edge_name)
    if not edge:
        fail(f"Protocol contract missing edge definition: {edge_name}")
    if edge.get("version") != "v1":
        fail(f"Protocol edge {edge_name} must be versioned as v1.")
    sample = edge.get("sample")
    schema = edge.get("schema", {})
    if not sample or not schema:
        fail(f"Protocol edge {edge_name} requires both schema and sample payload.")
    required_fields = schema.get("required", [])
    missing_fields = [field for field in required_fields if field not in sample]
    if missing_fields:
        fail(
            f"Protocol edge {edge_name} sample is missing required fields: {missing_fields}"
        )

declared_namespaces = set(namespace_rules.get("namespaces", []))
required_namespaces = {
    "observability-system",
    "ai-runtime",
    "ai-triggers",
    "mcp-system",
    "mcp-services",
    "ai-gateway",
    "ai-policy",
}
if required_namespaces != declared_namespaces:
    fail("Namespace boundary rules must define the expected namespace segmentation set.")

allow_list = namespace_rules.get("cross_namespace_allow_list", [])
if not allow_list:
    fail("Namespace boundary rules must include explicit cross-namespace allow-list.")

for row in allow_list:
    src = row.get("from")
    targets = row.get("to", [])
    if src not in declared_namespaces:
        fail(f"Allow-list source namespace is not declared: {src}")
    if not targets:
        fail(f"Allow-list entry for {src} must include at least one target namespace.")
    for dst in targets:
        if dst not in declared_namespaces:
            fail(f"Allow-list target namespace is not declared: {dst}")

allowed_namespace_rules = namespace_rules.get("allowed_namespaces_rules", {})
if allowed_namespace_rules.get("required_field") != "allowedNamespaces":
    fail("Namespace boundary rules must require allowedNamespaces field.")
constraints = set(allowed_namespace_rules.get("constraints", []))
for expected_constraint in [
    "values_must_exist_in_declared_namespaces",
    "wildcard_forbidden",
    "empty_list_forbidden",
]:
    if expected_constraint not in constraints:
        fail(
            f"Namespace boundary rules missing constraint: {expected_constraint}"
        )

scan_roots = [
    root / "agents",
    root / "services",
    root / "triggers",
    root / "gitops" / "platform" / "ai",
]
forbidden_patterns = [
    r"https?://[^\"'\s]*(opensearch|elasticsearch)",
    r"neo4j\+s?://",
    r"\b(neo4j|opensearchpy|elasticsearch|psycopg2|sqlalchemy)\b",
    r"\b(BoltDriver|GraphDatabase|Cypher)\b",
]

violations = find_forbidden_markers(scan_roots, forbidden_patterns)
if violations:
    fail(violations[0])

with TemporaryDirectory() as tmp_dir:
    seeded_file = Path(tmp_dir) / "seeded_direct_datastore_violation.py"
    seeded_file.write_text(
        "from neo4j import GraphDatabase\n"
        "url = 'https://example-opensearch.internal:9200'\n"
    )
    seeded_violations = find_forbidden_markers([Path(tmp_dir)], forbidden_patterns)
    if not seeded_violations:
        fail(
            "Seeded rejection check failed: forbidden direct datastore path marker "
            "was not detected."
        )

print("Batch 1 AI boundary and protocol contract checks passed.")
PY
