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
            "adapters/secrets/SECRETS_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml"
        ).read_text(encoding="utf-8")
    )
    fixtures = json.loads(
        Path(
            "tests/integration/adapters/secrets/SECRETS_BACKEND_ADAPTER_FIXTURES_V1.json"
        ).read_text(encoding="utf-8")
    )

    if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
        fail("Adapter contract must explicitly keep core contracts unchanged.")
    if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
        fail("Secrets adapter contract must enforce read-only dispatch mode.")
    if contract.get("constraints", {}).get("requires_secret_store_refs_only") is not True:
        fail("Secrets adapter contract must require secret-store references only.")

    backends = contract.get("secrets_backends", [])
    if len(backends) < 1:
        fail("Secrets adapter contract must include at least one backend.")

    backend_map = {}
    for backend in backends:
        name = backend.get("name")
        if not name:
            fail("Secrets backend entry missing name.")
        mode = backend.get("mode")
        if mode != "secret-store-ref":
            fail(f"Secrets backend {name} must use mode secret-store-ref.")

        required_fields = set(backend.get("required_fields", []))
        for field in ["backend", "namespace", "secret_ref", "auth_ref"]:
            if field not in required_fields:
                fail(f"Secrets backend {name} missing required field: {field}")

        max_entries = int(
            backend.get("outputs", {}).get("bounded_mappings", {}).get(
                "max_entries", 0
            )
        )
        if max_entries <= 0:
            fail(f"Secrets backend {name} must define bounded mapping entries.")

        backend_map[name] = {
            "clusters": set(backend.get("supported_clusters", [])),
            "max_entries": max_entries,
        }

    allowed_namespaces = {"ai-runtime", "mcp-services"}

    for fixture in fixtures.get("fixtures", []):
        backend = fixture.get("backend")
        if backend not in backend_map:
            fail(f"Fixture references unknown secrets backend: {backend}")

        cluster = fixture.get("cluster")
        allowed_clusters = backend_map[backend]["clusters"]
        if "any" not in allowed_clusters and cluster not in allowed_clusters:
            fail(f"Fixture cluster not supported by backend {backend}: {cluster}")

        namespace = fixture.get("namespace")
        if namespace not in allowed_namespaces:
            fail(f"Fixture namespace is out of adapter scope: {namespace}")

        if fixture.get("dispatch_mode") != "read-only":
            fail("Fixture dispatch_mode must be read-only.")

        mapping_count = int(fixture.get("mapping_count", 0))
        if mapping_count > backend_map[backend]["max_entries"]:
            fail("Fixture mapping count exceeds bounded_mappings max_entries.")

    for negative in fixtures.get("negative_fixtures", []):
        if negative.get("expected_result") != "rejected":
            fail("Negative fixtures must expect rejected result.")
        backend = negative.get("backend")
        if backend not in backend_map:
            continue
        if negative.get("dispatch_mode") == "approval-gated-write":
            continue
        if int(negative.get("mapping_count", 0)) > backend_map[backend]["max_entries"]:
            continue
        fail("Negative fixture does not violate a bounded secrets adapter rule.")

    print("Secrets backend adapter integration tests passed.")


if __name__ == "__main__":
    main()
