"""Install answers loading, validation, and contract emission.

Validates an answers mapping against
contracts/install/INSTALL_CONTRACT_SCHEMA.json with a hand-rolled
stdlib validator covering exactly the JSON-Schema keywords that schema
uses: type, required, properties, additionalProperties, enum, pattern,
minLength, and allOf/if/then (ADR-0002). Any keyword outside that set
raises InstallFlowError, so schema drift is caught loudly instead of
being silently ignored.

The configuration renderer (Batch 19, ADR-0003) reuses this validator
for contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json, so the subset
additionally implements $ref/$defs (local to the schema document),
const, minimum, maximum, minItems, minProperties, and items, plus the
array, boolean, integer, and number types. The growth is additive:
schemas that do not use the new keywords validate exactly as before.

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
# $defs is a definitions container: its subschemas are validated when
# referenced through $ref, never in place, so it is annotation-like
# at the location where it appears.
_ANNOTATION_KEYWORDS: frozenset[str] = frozenset(
    {"$schema", "$id", "title", "description", "$defs"}
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
        "$ref",
        "const",
        "minimum",
        "maximum",
        "minItems",
        "minProperties",
        "items",
    }
)

# JSON type names the schemas use; each maps to its instance check.
# bool subclasses int in Python, so integer/number checks explicitly
# exclude bool in _check_type.
_TYPE_CHECKS: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "string": (str,),
    "array": (list,),
    "boolean": (bool,),
    "integer": (int,),
    "number": (int, float),
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
    matched = isinstance(instance, expected)
    # bool subclasses int: a boolean must never satisfy an
    # integer/number type constraint.
    if (
        matched
        and type_name in ("integer", "number")
        and isinstance(instance, bool)
    ):
        matched = False
    if matched:
        return True
    errors.append(
        f"{location or '$'}: expected {type_name}, "
        f"got {type(instance).__name__}"
    )
    return False


def _resolve_ref(
    ref: str, root: dict[str, Any], location: str
) -> dict[str, Any]:
    """Resolve a $ref pointer local to the schema document."""
    if not ref.startswith("#/"):
        raise InstallFlowError(
            f"schema $ref {ref!r} at {location or '$'} is not a "
            "local '#/' pointer; the subset validator only resolves "
            "references within the schema document"
        )
    node: Any = root
    for raw_token in ref[2:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            raise InstallFlowError(
                f"schema $ref {ref!r} at {location or '$'} does not "
                "resolve within the schema document"
            )
        node = node[token]
    if not isinstance(node, dict):
        raise InstallFlowError(
            f"schema $ref {ref!r} at {location or '$'} resolves to a "
            "non-object schema"
        )
    return node


def _strict_equal(instance: Any, expected: Any) -> bool:
    """Type-aware equality for const/enum.

    Python's == treats True as 1 and False as 0, so a boolean would
    otherwise satisfy a numeric const/enum (and vice versa). Booleans
    only ever equal booleans here.
    """
    if isinstance(instance, bool) != isinstance(expected, bool):
        return False
    return instance == expected


def _matches(
    instance: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    active_refs: frozenset[str] = frozenset(),
) -> bool:
    """Boolean check used by allOf/if: does instance satisfy schema?"""
    probe: list[str] = []
    _validate(instance, schema, "", probe, root, active_refs)
    return not probe


def _validate(
    instance: Any,
    schema: dict[str, Any],
    location: str,
    errors: list[str],
    root: dict[str, Any],
    active_refs: frozenset[str] = frozenset(),
) -> None:
    _assert_supported(schema, location)

    if "$ref" in schema:
        ref = schema["$ref"]
        # active_refs tracks the refs currently being expanded at
        # this same instance location; re-entering one means the
        # schema has a $ref cycle, which must fail loudly instead of
        # hitting the recursion limit. The set resets whenever
        # validation descends into a child instance (properties,
        # items), where recursion terminates on instance depth.
        if ref in active_refs:
            raise InstallFlowError(
                f"schema $ref cycle detected at {location or '$'}: "
                f"{ref!r} references itself through "
                f"{sorted(active_refs)}"
            )
        resolved = _resolve_ref(ref, root, location)
        _validate(
            instance,
            resolved,
            location,
            errors,
            root,
            active_refs | {ref},
        )

    type_ok = True
    if "type" in schema:
        type_ok = _check_type(
            instance, schema["type"], location, errors
        )

    if "enum" in schema and not any(
        _strict_equal(instance, option) for option in schema["enum"]
    ):
        errors.append(
            f"{location or '$'}: value {instance!r} not in "
            f"{schema['enum']}"
        )

    if "const" in schema and not _strict_equal(
        instance, schema["const"]
    ):
        errors.append(
            f"{location or '$'}: value {instance!r} is not the "
            f"required constant {schema['const']!r}"
        )

    if isinstance(instance, (int, float)) and not isinstance(
        instance, bool
    ):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(
                f"{location or '$'}: value {instance!r} is below "
                f"minimum {schema['minimum']}"
            )
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(
                f"{location or '$'}: value {instance!r} is above "
                f"maximum {schema['maximum']}"
            )

    if type_ok and isinstance(instance, list):
        if (
            "minItems" in schema
            and len(instance) < schema["minItems"]
        ):
            errors.append(
                f"{location or '$'}: length {len(instance)} is below "
                f"minItems {schema['minItems']}"
            )
        if "items" in schema:
            for index, element in enumerate(instance):
                _validate(
                    element,
                    schema["items"],
                    f"{location}/{index}",
                    errors,
                    root,
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
        if (
            "minProperties" in schema
            and len(instance) < schema["minProperties"]
        ):
            errors.append(
                f"{location or '$'}: property count {len(instance)} "
                f"is below minProperties {schema['minProperties']}"
            )
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
                    root,
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
            if _matches(
                instance, subschema["if"], root, active_refs
            ):
                _validate(
                    instance,
                    subschema.get("then", {}),
                    f"{location}/allOf/{index}/then",
                    errors,
                    root,
                    active_refs,
                )
        else:
            _validate(
                instance,
                subschema,
                f"{location}/allOf/{index}",
                errors,
                root,
                active_refs,
            )

    # Standalone if/then, evaluated unconditionally: guarding it
    # behind the absence of allOf would silently drop a top-level
    # conditional on a schema that carries both, contradicting the
    # fail-loudly contract of this validator.
    if "if" in schema:
        if _matches(instance, schema["if"], root, active_refs):
            _validate(
                instance,
                schema.get("then", {}),
                f"{location}/then",
                errors,
                root,
                active_refs,
            )


def validate_answers(
    mapping: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Validate an answers mapping; return all violation messages."""
    errors: list[str] = []
    _validate(mapping, schema, "", errors, schema)
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
