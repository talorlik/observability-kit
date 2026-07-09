#!/usr/bin/env python3
"""Structural schema conformance for executor reports (Batch 17, TR-18).

Validates the preflight reports (pass and fail fixtures) against
contracts/discovery/PREFLIGHT_REPORT_SCHEMA.json and the discovery
probes report against contracts/discovery/DISCOVERY_PROBES_SCHEMA.json
using a stdlib-only structural checker: required keys, enums, types,
pattern, minItems/minLength/minimum, and additionalProperties
(including the schema-level root `additionalProperties: false`).

The checker deliberately covers exactly the JSON-Schema constructs the
two contract schemas use, so an unhandled construct is a loud error
rather than a silent skip (no external jsonschema dependency, per the
stdlib-only executor contract).

Owned by scripts/ci/validate_discovery_executor.sh.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "executor" / "fixtures"
PREFLIGHT_SCHEMA = ROOT / "contracts" / "discovery" / "PREFLIGHT_REPORT_SCHEMA.json"
DISCOVERY_SCHEMA = ROOT / "contracts" / "discovery" / "DISCOVERY_PROBES_SCHEMA.json"

_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
}

# Constructs the checker understands; anything else in a schema node is
# a coverage gap and must fail the test rather than pass silently.
_HANDLED_KEYWORDS = {
    "$schema",
    "$id",
    "title",
    "description",
    "type",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "enum",
    "pattern",
    "minItems",
    "minLength",
    "minimum",
}


def check_schema(instance: object, schema: dict, path: str) -> list[str]:
    """Return a list of human-readable violations (empty means valid)."""
    errors: list[str] = []
    unhandled = set(schema) - _HANDLED_KEYWORDS
    if unhandled:
        errors.append(f"{path}: unhandled schema keywords {sorted(unhandled)}")
        return errors

    if "enum" in schema:
        if instance not in schema["enum"]:
            errors.append(
                f"{path}: {instance!r} not in enum {schema['enum']}"
            )
        return errors

    expected_type = schema.get("type")
    if expected_type is not None:
        python_type = _TYPE_MAP[expected_type]
        # bool is an int subclass; keep integer strictly integral.
        if expected_type in ("integer", "number") and isinstance(
            instance, bool
        ):
            errors.append(f"{path}: expected {expected_type}, got bool")
            return errors
        if not isinstance(instance, python_type):
            errors.append(
                f"{path}: expected {expected_type}, "
                f"got {type(instance).__name__}"
            )
            return errors

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(
                f"{path}: {instance!r} does not match {schema['pattern']!r}"
            )
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} below {schema['minimum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(instance):
                errors.extend(
                    check_schema(item, item_schema, f"{path}[{index}]")
                )

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                errors.extend(
                    check_schema(value, properties[key], f"{path}.{key}")
                )
            elif additional is False:
                errors.append(f"{path}: additional property {key!r} forbidden")
            elif isinstance(additional, dict):
                errors.extend(
                    check_schema(value, additional, f"{path}.{key}")
                )
    return errors


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "tools" / "obskit")
    return env


def generate_report(subcommand: str, snapshot: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "report.json"
        proc = subprocess.run(
            [
                "python3",
                "-m",
                "obskit.cli",
                subcommand,
                "--snapshot",
                str(snapshot),
                "--output",
                str(out_path),
            ],
            cwd=ROOT,
            env=_cli_env(),
            capture_output=True,
            text=True,
        )
        assert out_path.is_file(), (
            f"{subcommand} wrote no report; stderr: {proc.stderr}"
        )
        return json.loads(out_path.read_text())


def _assert_conformant(report: dict, schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text())
    assert schema.get("additionalProperties") is False, (
        f"{schema_path.name}: root additionalProperties must be false"
    )
    errors = check_schema(report, schema, label)
    assert not errors, "\n".join(errors)


def test_preflight_reports_conform_to_schema() -> None:
    for fixture in ("snapshot_preflight_pass.json",
                    "snapshot_preflight_fail.json"):
        report = generate_report("preflight", FIXTURES / fixture)
        _assert_conformant(report, PREFLIGHT_SCHEMA, f"preflight({fixture})")


def test_discovery_report_conforms_to_schema() -> None:
    report = generate_report(
        "discover", FIXTURES / "snapshot_discovery_reference.json"
    )
    _assert_conformant(report, DISCOVERY_SCHEMA, "discovery(reference)")


def test_checker_rejects_seeded_violations() -> None:
    """The mini checker itself must fail loudly, not vacuously pass."""
    schema = json.loads(PREFLIGHT_SCHEMA.read_text())
    good = generate_report(
        "preflight", FIXTURES / "snapshot_preflight_pass.json"
    )

    mutants: list[dict] = []
    extra_root = json.loads(json.dumps(good))
    extra_root["unexpected_root_key"] = True  # root additionalProperties
    mutants.append(extra_root)
    bad_enum = json.loads(json.dumps(good))
    bad_enum["checks"][0]["status"] = "maybe"  # enum violation
    mutants.append(bad_enum)
    missing_key = json.loads(json.dumps(good))
    del missing_key["summary"]["outcome"]  # required violation
    mutants.append(missing_key)
    bad_type = json.loads(json.dumps(good))
    bad_type["summary"]["total_checks"] = "six"  # type violation
    mutants.append(bad_type)

    for index, mutant in enumerate(mutants):
        errors = check_schema(mutant, schema, f"mutant[{index}]")
        assert errors, f"mutant {index} should have been rejected"


if __name__ == "__main__":
    test_preflight_reports_conform_to_schema()
    print("test_preflight_reports_conform_to_schema passed")
    test_discovery_report_conforms_to_schema()
    print("test_discovery_report_conforms_to_schema passed")
    test_checker_rejects_seeded_violations()
    print("test_checker_rejects_seeded_violations passed")
