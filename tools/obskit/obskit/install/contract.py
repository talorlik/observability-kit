"""Install answers loading, validation, and contract emission.

Validates an answers mapping against
contracts/install/INSTALL_CONTRACT_SCHEMA.json with a hand-rolled
stdlib validator covering exactly the JSON-Schema keywords that schema
uses: type, required, properties, additionalProperties, enum, pattern,
minLength, and allOf/if/then (ADR-0002). Any keyword outside that set
raises InstallFlowError, so schema drift is caught loudly instead of
being silently ignored.

On success the canonical mapping is written to answers.json and
install_contract.json through obskit.emit.write_report, so both
artifacts are byte-identical for identical answers regardless of
whether the wizard or --answers produced them (TR-19 parity).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from obskit.emit import write_report
from obskit.install.models import (
    ANSWERS_FILENAME,
    INSTALL_CONTRACT_FILENAME,
    InstallFlowError,
)

# Keywords the validator implements, plus pure annotations it may
# safely ignore. Anything else in the schema is unimplemented and
# must fail loudly (ADR-0002 consequence: the subset validator grows
# with the schema or the run fails).
_ANNOTATION_KEYWORDS: frozenset[str] = frozenset(
    {"$schema", "$id", "title", "description"}
)
_SUPPORTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "type",
        "required",
        "properties",
        "additionalProperties",
        "enum",
        "pattern",
        "minLength",
        "allOf",
        "if",
        "then",
    }
)

# JSON type names the schema uses; each maps to its instance check.
_TYPE_CHECKS: dict[str, type] = {
    "object": dict,
    "string": str,
}


def load_schema(path: Path) -> dict[str, Any]:
    """Load the install contract JSON schema, failing loudly."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InstallFlowError(
            f"cannot read install contract schema {path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise InstallFlowError(
            f"malformed JSON in install contract schema {path}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise InstallFlowError(
            f"install contract schema {path} must be a JSON object"
        )
    return loaded


def load_answers_file(path: str) -> dict[str, Any]:
    """Load an answers JSON file into the mapping the wizard produces."""
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except OSError as exc:
        raise InstallFlowError(
            f"cannot read answers file {path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise InstallFlowError(
            f"malformed JSON in answers file {path}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise InstallFlowError(
            f"answers file {path} must contain a JSON object"
        )
    return loaded


def _assert_supported(schema: dict[str, Any], location: str) -> None:
    unknown = sorted(
        set(schema) - _SUPPORTED_KEYWORDS - _ANNOTATION_KEYWORDS
    )
    if unknown:
        raise InstallFlowError(
            "install contract schema uses keyword(s) the installer "
            f"validator does not implement at {location or '$'}: "
            f"{unknown}"
        )


def _check_type(
    instance: Any, type_name: str, location: str, errors: list[str]
) -> bool:
    """Record a type error; return whether the type matched."""
    expected = _TYPE_CHECKS.get(type_name)
    if expected is None:
        raise InstallFlowError(
            "install contract schema uses type value the installer "
            f"validator does not implement at {location or '$'}: "
            f"{type_name!r}"
        )
    # bool is an int subclass, not relevant here, but guard dict/str
    # strictly so surprising instances fail as type errors.
    if isinstance(instance, expected):
        return True
    errors.append(
        f"{location or '$'}: expected {type_name}, "
        f"got {type(instance).__name__}"
    )
    return False


def _matches(instance: Any, schema: dict[str, Any]) -> bool:
    """Boolean check used by allOf/if: does instance satisfy schema?"""
    probe: list[str] = []
    _validate(instance, schema, "", probe)
    return not probe


def _validate(
    instance: Any,
    schema: dict[str, Any],
    location: str,
    errors: list[str],
) -> None:
    _assert_supported(schema, location)

    type_ok = True
    if "type" in schema:
        type_ok = _check_type(
            instance, schema["type"], location, errors
        )

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(
            f"{location or '$'}: value {instance!r} not in "
            f"{schema['enum']}"
        )

    if type_ok and isinstance(instance, str):
        if "pattern" in schema and not re.search(
            schema["pattern"], instance
        ):
            errors.append(
                f"{location or '$'}: value {instance!r} does not "
                f"match pattern {schema['pattern']!r}"
            )
        if (
            "minLength" in schema
            and len(instance) < schema["minLength"]
        ):
            errors.append(
                f"{location or '$'}: length {len(instance)} is below "
                f"minLength {schema['minLength']}"
            )

    if type_ok and isinstance(instance, dict):
        properties: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", ()):
            if key not in instance:
                errors.append(
                    f"{location or '$'}: missing required property "
                    f"{key!r}"
                )
        for key, subschema in properties.items():
            if key in instance:
                _validate(
                    instance[key],
                    subschema,
                    f"{location}/{key}",
                    errors,
                )
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                errors.append(
                    f"{location or '$'}: additional properties not "
                    f"allowed: {extra}"
                )

    for index, subschema in enumerate(schema.get("allOf", ())):
        _assert_supported(subschema, f"{location}/allOf/{index}")
        if "if" in subschema:
            # A conditional subschema must be purely conditional:
            # sibling keywords next to if/then would be silently
            # skipped by this branch, contradicting the fail-loudly
            # contract of this validator.
            extras = sorted(set(subschema) - {"if", "then"})
            if extras:
                raise InstallFlowError(
                    f"install contract schema {location}/allOf/"
                    f"{index}: keywords {extras} are not supported "
                    "alongside if/then"
                )
            if _matches(instance, subschema["if"]):
                _validate(
                    instance,
                    subschema.get("then", {}),
                    f"{location}/allOf/{index}/then",
                    errors,
                )
        else:
            _validate(
                instance,
                subschema,
                f"{location}/allOf/{index}",
                errors,
            )

    # Standalone if/then (outside allOf), for completeness of the
    # contracted keyword set.
    if "if" in schema and "allOf" not in schema:
        if _matches(instance, schema["if"]):
            _validate(
                instance,
                schema.get("then", {}),
                f"{location}/then",
                errors,
            )


def validate_answers(
    mapping: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Validate an answers mapping; return all violation messages."""
    errors: list[str] = []
    _validate(mapping, schema, "", errors)
    return errors


def capture_contract(
    mapping: dict[str, Any],
    schema_path: Path,
    output_dir: Path,
) -> tuple[str, ...]:
    """Validate answers and emit answers.json + install_contract.json.

    Raises InstallFlowError before writing anything when the mapping
    does not validate, so invalid answers never reach the render or
    bootstrap steps (flow contract invariant
    answers_validate_before_render).
    """
    schema = load_schema(schema_path)
    errors = validate_answers(mapping, schema)
    if errors:
        raise InstallFlowError(
            "install answers failed schema validation: "
            + "; ".join(errors)
        )
    write_report(mapping, str(output_dir / ANSWERS_FILENAME))
    write_report(mapping, str(output_dir / INSTALL_CONTRACT_FILENAME))
    return (ANSWERS_FILENAME, INSTALL_CONTRACT_FILENAME)
