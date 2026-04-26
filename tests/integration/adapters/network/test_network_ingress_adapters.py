#!/usr/bin/env python3

import json
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def main() -> None:
    contract = yaml.safe_load(
        Path(
            "adapters/network/NETWORK_INGRESS_ADAPTER_COMPATIBILITY_V1.yaml"
        ).read_text(encoding="utf-8")
    )
    fixtures = json.loads(
        Path(
            "tests/integration/adapters/network/NETWORK_INGRESS_ADAPTER_FIXTURES_V1.json"
        ).read_text(encoding="utf-8")
    )

    if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
        fail("Adapter contract must explicitly keep core contracts unchanged.")
    if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
        fail("Network adapter contract must enforce read-only dispatch mode.")
    if contract.get("constraints", {}).get("requires_network_policy") is not True:
        fail("Network adapter contract must enforce network policy requirement.")

    backends = contract.get("network_ingress_backends", [])
    if len(backends) < 1:
        fail("Network adapter contract must include at least one backend.")

    backend_map = {}
    for backend in backends:
        name = backend.get("name")
        if not name:
            fail("Network backend entry missing name.")
        mode = backend.get("mode")
        if mode not in {"ingress-managed", "mesh-ingress-managed"}:
            fail(f"Network backend {name} has invalid mode: {mode}")

        required_fields = set(backend.get("required_fields", []))
        for field in ["backend", "namespace", "tls_ref"]:
            if field not in required_fields:
                fail(f"Network backend {name} missing required field: {field}")

        max_routes = int(
            backend.get("outputs", {}).get("bounded_rules", {}).get("max_routes", 0)
        )
        if max_routes <= 0:
            fail(f"Network backend {name} must define bounded max_routes.")

        backend_map[name] = {
            "clusters": set(backend.get("supported_clusters", [])),
            "max_routes": max_routes,
        }

    allowed_namespaces = {"ai-gateway", "ai-runtime"}

    for fixture in fixtures.get("fixtures", []):
        backend = fixture.get("backend")
        if backend not in backend_map:
            fail(f"Fixture references unknown network backend: {backend}")

        cluster = fixture.get("cluster")
        allowed_clusters = backend_map[backend]["clusters"]
        if "any" not in allowed_clusters and cluster not in allowed_clusters:
            fail(f"Fixture cluster not supported by backend {backend}: {cluster}")

        namespace = fixture.get("namespace")
        if namespace not in allowed_namespaces:
            fail(f"Fixture namespace is out of adapter scope: {namespace}")

        if fixture.get("dispatch_mode") != "read-only":
            fail("Fixture dispatch_mode must be read-only.")

        route_count = int(fixture.get("route_count", 0))
        if route_count > backend_map[backend]["max_routes"]:
            fail("Fixture route count exceeds bounded max_routes.")

    for negative in fixtures.get("negative_fixtures", []):
        if negative.get("expected_result") != "rejected":
            fail("Negative fixtures must expect rejected result.")
        backend = negative.get("backend")
        if backend not in backend_map:
            continue
        if negative.get("dispatch_mode") == "approval-gated-write":
            continue
        if negative.get("namespace") not in allowed_namespaces:
            continue
        if int(negative.get("route_count", 0)) > backend_map[backend]["max_routes"]:
            continue
        fail("Negative fixture does not violate a bounded network adapter rule.")

    print("Network and ingress adapter integration tests passed.")


if __name__ == "__main__":
    main()
