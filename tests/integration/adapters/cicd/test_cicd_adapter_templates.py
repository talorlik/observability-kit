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
            "adapters/cicd/CICD_ADAPTER_TEMPLATE_COMPATIBILITY_V1.yaml"
        ).read_text(encoding="utf-8")
    )
    fixtures = json.loads(
        Path(
            "tests/integration/adapters/cicd/CICD_ADAPTER_TEMPLATE_FIXTURES_V1.json"
        ).read_text(encoding="utf-8")
    )

    if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
        fail("Adapter contract must explicitly keep core contracts unchanged.")
    if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
        fail("CI/CD adapter contract must enforce read-only dispatch mode.")
    if contract.get("constraints", {}).get("requires_validation_before_deploy") is not True:
        fail("CI/CD adapter contract must enforce validation before deploy.")

    templates = contract.get("cicd_templates", [])
    if len(templates) < 1:
        fail("CI/CD adapter contract must include at least one template provider.")

    template_map = {}
    for item in templates:
        name = item.get("name")
        if not name:
            fail("CI/CD template entry missing name.")
        mode = item.get("mode")
        if mode != "pipeline-template":
            fail(f"CI/CD provider {name} has invalid mode: {mode}")

        required_fields = set(item.get("required_fields", []))
        for field in [
            "provider",
            "trigger",
            "validation_steps",
            "artifact_path",
            "deployment_mode",
        ]:
            if field not in required_fields:
                fail(f"CI/CD provider {name} missing required field: {field}")

        max_steps = int(
            item.get("outputs", {}).get("bounded_steps", {}).get(
                "max_validation_steps", 0
            )
        )
        if max_steps <= 0:
            fail(f"CI/CD provider {name} must define bounded max_validation_steps.")

        template_map[name] = {
            "runners": set(item.get("supported_runners", [])),
            "max_steps": max_steps,
        }

    allowed_modes = {"quickstart", "dev", "staging", "prod"}

    for fixture in fixtures.get("fixtures", []):
        provider = fixture.get("provider")
        if provider not in template_map:
            fail(f"Fixture references unknown CI/CD provider: {provider}")

        runner = fixture.get("runner")
        if runner not in template_map[provider]["runners"]:
            fail(f"Fixture runner not supported by {provider}: {runner}")

        deployment_mode = fixture.get("deployment_mode")
        if deployment_mode not in allowed_modes:
            fail(f"Fixture deployment mode is out of scope: {deployment_mode}")

        if fixture.get("dispatch_mode") != "read-only":
            fail("Fixture dispatch_mode must be read-only.")

        step_count = int(fixture.get("validation_step_count", 0))
        if step_count > template_map[provider]["max_steps"]:
            fail("Fixture validation step count exceeds bounded max_validation_steps.")

    for negative in fixtures.get("negative_fixtures", []):
        if negative.get("expected_result") != "rejected":
            fail("Negative fixtures must expect rejected result.")
        provider = negative.get("provider")
        if provider not in template_map:
            continue
        if negative.get("dispatch_mode") == "approval-gated-write":
            continue
        if int(negative.get("validation_step_count", 0)) > template_map[provider]["max_steps"]:
            continue
        fail("Negative fixture does not violate a bounded CI/CD adapter rule.")

    print("CI/CD adapter template integration tests passed.")


if __name__ == "__main__":
    main()
