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
            "adapters/storage/STORAGE_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml"
        ).read_text(encoding="utf-8")
    )
    fixtures = json.loads(
        Path(
            "tests/integration/adapters/storage/STORAGE_BACKEND_ADAPTER_FIXTURES_V1.json"
        ).read_text(encoding="utf-8")
    )

    if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
        fail("Adapter contract must explicitly keep core contracts unchanged.")
    if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
        fail("Storage adapter contract must enforce read-only dispatch mode.")
    if contract.get("constraints", {}).get("preserve_core_index_templates") is not True:
        fail("Storage adapter contract must preserve core index templates.")

    backends = contract.get("storage_backends", [])
    if len(backends) < 1:
        fail("Storage adapter contract must include at least one backend.")

    backend_map = {}
    for backend in backends:
        name = backend.get("name")
        if not name:
            fail("Storage backend entry missing name.")
        mode = backend.get("mode")
        if mode not in {"opensearch-managed", "snapshot-only"}:
            fail(f"Storage backend {name} has invalid mode: {mode}")

        required_fields = set(backend.get("required_fields", []))
        for field in ["backend", "namespace"]:
            if field not in required_fields:
                fail(f"Storage backend {name} missing required field: {field}")

        max_templates = int(
            backend.get("outputs", {}).get("bounded_policies", {}).get(
                "max_templates", 0
            )
        )
        if max_templates <= 0:
            fail(f"Storage backend {name} must define bounded max_templates.")

        backend_map[name] = {
            "profiles": set(backend.get("supported_profiles", [])),
            "max_templates": max_templates,
        }

    for fixture in fixtures.get("fixtures", []):
        backend = fixture.get("backend")
        if backend not in backend_map:
            fail(f"Fixture references unknown storage backend: {backend}")

        profile = fixture.get("profile")
        if profile not in backend_map[backend]["profiles"]:
            fail(f"Fixture profile not supported by backend {backend}: {profile}")

        if fixture.get("namespace") != "observability-system":
            fail("Storage adapter fixtures must target observability-system namespace.")

        if fixture.get("dispatch_mode") != "read-only":
            fail("Fixture dispatch_mode must be read-only.")

        template_count = int(fixture.get("template_count", 0))
        if template_count > backend_map[backend]["max_templates"]:
            fail("Fixture template count exceeds bounded max_templates.")

    for negative in fixtures.get("negative_fixtures", []):
        if negative.get("expected_result") != "rejected":
            fail("Negative fixtures must expect rejected result.")
        backend = negative.get("backend")
        if backend not in backend_map:
            continue
        if negative.get("dispatch_mode") == "approval-gated-write":
            continue
        if int(negative.get("template_count", 0)) > backend_map[backend]["max_templates"]:
            continue
        fail("Negative fixture does not violate a bounded storage adapter rule.")

    print("Storage backend adapter integration tests passed.")


if __name__ == "__main__":
    main()
