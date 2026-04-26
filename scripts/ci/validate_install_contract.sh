#!/usr/bin/env bash

set -euo pipefail

SCHEMA="contracts/install/INSTALL_CONTRACT_SCHEMA.json"
VALID_GLOB="contracts/install/samples/valid/*.json"
INVALID_GLOB="contracts/install/samples/invalid/*.json"

echo "Validating install contract samples against schema..."
python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

schema_path = Path("contracts/install/INSTALL_CONTRACT_SCHEMA.json")
valid_dir = Path("contracts/install/samples/valid")
invalid_dir = Path("contracts/install/samples/invalid")

schema = json.loads(schema_path.read_text())
required_fields = set(schema.get("required", []))
properties = schema.get("properties", {})


class ValidationError(Exception):
    pass


def fail(msg: str) -> None:
    raise ValidationError(msg)


def validate_string_constraints(key: str, value, rules: dict, file_path: Path) -> None:
    if rules.get("type") == "string":
        if not isinstance(value, str):
            fail(f"{file_path}: field '{key}' must be a string.")
        min_len = rules.get("minLength")
        if min_len is not None and len(value) < min_len:
            fail(f"{file_path}: field '{key}' must have minLength {min_len}.")
        enum = rules.get("enum")
        if enum is not None and value not in enum:
            fail(f"{file_path}: field '{key}' value '{value}' is not in enum {enum}.")
        pattern = rules.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            fail(f"{file_path}: field '{key}' does not match required pattern.")


def validate_object_constraints(key: str, value, rules: dict, file_path: Path) -> None:
    if rules.get("type") != "object":
        return
    if not isinstance(value, dict):
        fail(f"{file_path}: field '{key}' must be an object.")
    if rules.get("additionalProperties") is False:
        allowed = set(rules.get("properties", {}).keys())
        extras = set(value.keys()) - allowed
        if extras:
            fail(f"{file_path}: field '{key}' contains unsupported keys: {sorted(extras)}")
    for nested_key, nested_rules in rules.get("properties", {}).items():
        if nested_key in value:
            validate_string_constraints(
                f"{key}.{nested_key}", value[nested_key], nested_rules, file_path
            )


def validate_doc(file_path: Path) -> None:
    doc = json.loads(file_path.read_text())
    if not isinstance(doc, dict):
        fail(f"{file_path}: document root must be an object.")
    if schema.get("additionalProperties") is False:
        allowed_top = set(properties.keys())
        extras = set(doc.keys()) - allowed_top
        if extras:
            fail(f"{file_path}: unsupported top-level keys: {sorted(extras)}")

    missing = sorted(required_fields - set(doc.keys()))
    if missing:
        fail(f"{file_path}: missing required fields: {missing}")

    for key, rules in properties.items():
        if key not in doc:
            continue
        value = doc[key]
        validate_string_constraints(key, value, rules, file_path)
        validate_object_constraints(key, value, rules, file_path)

    deployment_mode = doc.get("deployment_mode")
    if deployment_mode in {"attach", "hybrid"} and "attached_services" not in doc:
        fail(
            f"{file_path}: attached_services is required when "
            f"deployment_mode is {deployment_mode}."
        )


for valid_file in sorted(valid_dir.glob("*.json")):
    try:
        validate_doc(valid_file)
    except ValidationError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    print(f"{valid_file} valid")

print("Ensuring invalid samples are rejected...")
for invalid_file in sorted(invalid_dir.glob("*.json")):
    try:
        validate_doc(invalid_file)
    except ValidationError:
        continue
    fail(f"Expected invalid sample validation to fail, but it passed: {invalid_file}")

print("Invalid sample checks passed.")
PY

echo "Install contract schema validation checks passed."
