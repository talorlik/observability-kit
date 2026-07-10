"""Bespoke stdlib validator for usage record documents.

Enforces USAGE_RECORD_SCHEMA_V1.json plus the compliance rules of
METERING_CONTRACT_V1.yaml that plain JSON Schema cannot express
(window ordering, deterministic record_id form, source_reference shape
by source_type). Mirrors the repo-wide no-pytest, no-PyPI CI posture:
validation runs with system python3 alone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from commercialsvc.models import (
    CONTENT_DIGEST_PATTERN,
    DATETIME_PATTERN,
    DIMENSION_BINDINGS,
    DIMENSIONS,
    KNOWN_RECORD_FIELDS,
    KNOWN_SOURCE_REFERENCE_FIELDS,
    RecordValidationError,
    REQUIRED_RECORD_FIELDS,
    SIGNALS,
    SOURCE_TYPES,
    TENANT_ID_PATTERN,
    UNITS,
    UsageRecord,
)


def _is_number(value: object) -> bool:
    # bool is an int subclass; a boolean is never a legal measurement.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_timestamp(value: str) -> datetime | None:
    try:
        # Python 3.11+ fromisoformat accepts the trailing Z directly.
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _validate_source_reference(
    reference: object, errors: list[str]
) -> None:
    if not isinstance(reference, Mapping):
        errors.append("source_reference: must be an object")
        return
    unknown = sorted(
        set(reference) - KNOWN_SOURCE_REFERENCE_FIELDS
    )
    if unknown:
        errors.append(
            "source_reference: unknown fields "
            f"{unknown} (additionalProperties: false)"
        )
    source_type = reference.get("source_type")
    if source_type is None:
        errors.append("source_reference: source_type is required")
        return
    if source_type not in SOURCE_TYPES:
        errors.append(
            f"source_reference: unknown source_type {source_type!r}"
        )
        return

    indices = reference.get("indices")
    if indices is not None:
        if (
            not isinstance(indices, list)
            or not indices
            or not all(
                isinstance(item, str) and item for item in indices
            )
        ):
            errors.append(
                "source_reference: indices must be a non-empty list "
                "of non-empty strings"
            )
    document_count = reference.get("document_count")
    if document_count is not None and (
        not isinstance(document_count, int)
        or isinstance(document_count, bool)
        or document_count < 0
    ):
        errors.append(
            "source_reference: document_count must be an integer >= 0"
        )
    content_digest = reference.get("content_digest")
    if content_digest is not None and (
        not isinstance(content_digest, str)
        or not CONTENT_DIGEST_PATTERN.match(content_digest)
    ):
        errors.append(
            "source_reference: content_digest must match "
            "sha256:<64 hex chars>"
        )
    descriptor_field = reference.get("descriptor_field")
    if descriptor_field is not None and (
        not isinstance(descriptor_field, str) or not descriptor_field
    ):
        errors.append(
            "source_reference: descriptor_field must be a non-empty "
            "string"
        )

    # Shape by source_type: aggregation references cite the telemetry
    # indices they derived from; descriptor references cite exactly
    # the dotted quota field and nothing telemetry-shaped.
    if source_type == "opensearch-aggregation":
        if indices is None:
            errors.append(
                "source_reference: opensearch-aggregation requires "
                "indices"
            )
        if descriptor_field is not None:
            errors.append(
                "source_reference: descriptor_field is only legal for "
                "tenant-descriptor sources"
            )
    else:  # tenant-descriptor
        if descriptor_field is None:
            errors.append(
                "source_reference: tenant-descriptor requires "
                "descriptor_field"
            )
        for illegal in ("indices", "document_count", "content_digest"):
            if reference.get(illegal) is not None:
                errors.append(
                    f"source_reference: {illegal} is only legal for "
                    "opensearch-aggregation sources"
                )


# Sentinel distinguishing "key absent" (covered by the required-fields
# check) from "key present with JSON null". A present-but-null required
# field must fail its type check - tenant_id: null is NOT attribution
# (TR-23), and null anywhere else is not schema-conformant either.
_MISSING: Any = object()


def validate_record(document: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate one usage record document; return all errors found.

    An empty tuple means the record is contract-conformant.
    """
    errors: list[str] = []

    # additionalProperties: false. This is the TR-16 guard that
    # rejects embedded telemetry payloads riding on a usage record.
    unknown = sorted(set(document) - KNOWN_RECORD_FIELDS)
    if unknown:
        errors.append(
            f"unknown fields {unknown} rejected "
            "(additionalProperties: false; telemetry payloads must "
            "never be embedded in control-plane usage records)"
        )

    missing = [
        name
        for name in REQUIRED_RECORD_FIELDS
        if name not in document
    ]
    if missing:
        errors.append(f"missing required fields {missing}")
    if "tenant_id" not in document:
        # Called out separately: TR-23 fixes that a record without
        # tenant attribution is rejected outright.
        errors.append("tenant_id is mandatory on every usage record")

    tenant_id = document.get("tenant_id", _MISSING)
    if tenant_id is not _MISSING and (
        not isinstance(tenant_id, str)
        or not TENANT_ID_PATTERN.match(tenant_id)
    ):
        errors.append(
            f"tenant_id {tenant_id!r} does not match the tenant slug "
            "pattern"
        )

    record_id = document.get("record_id", _MISSING)
    if record_id is not _MISSING and (
        not isinstance(record_id, str)
        or not record_id
        or len(record_id) > 256
    ):
        errors.append("record_id must be a string of 1..256 chars")

    dimension = document.get("dimension", _MISSING)
    if dimension is not _MISSING and dimension not in DIMENSIONS:
        errors.append(
            f"unknown dimension {dimension!r} (catalog: "
            f"{list(DIMENSIONS)})"
        )
    signal = document.get("signal", _MISSING)
    if signal is not _MISSING and signal not in SIGNALS:
        errors.append(f"unknown signal {signal!r}")
    unit = document.get("unit", _MISSING)
    if unit is not _MISSING and unit not in UNITS:
        errors.append(f"unknown unit {unit!r}")

    value = document.get("value", _MISSING)
    if value is not _MISSING and (not _is_number(value) or value < 0):
        errors.append("value must be a number >= 0")

    for name in ("window_start", "window_end", "collected_at"):
        timestamp = document.get(name, _MISSING)
        if timestamp is not _MISSING and (
            not isinstance(timestamp, str)
            or not DATETIME_PATTERN.match(timestamp)
        ):
            errors.append(
                f"{name} must be an RFC 3339 UTC timestamp"
            )

    collector_version = document.get("collector_version", _MISSING)
    if collector_version is not _MISSING and (
        not isinstance(collector_version, str) or not collector_version
    ):
        errors.append("collector_version must be a non-empty string")

    # Dimension binding rules (the schema's allOf blocks).
    if isinstance(dimension, str) and dimension in DIMENSION_BINDINGS:
        binding = DIMENSION_BINDINGS[dimension]
        if signal is not _MISSING and signal not in binding.signals:
            errors.append(
                f"dimension {dimension} does not allow signal "
                f"{signal!r} (allowed: {list(binding.signals)})"
            )
        if unit is not _MISSING and unit != binding.unit:
            errors.append(
                f"dimension {dimension} requires unit "
                f"{binding.unit!r}, got {unit!r}"
            )
        if (
            binding.value_enum is not None
            and _is_number(value)
            and value not in binding.value_enum
        ):
            errors.append(
                f"dimension {dimension} requires value in "
                f"{list(binding.value_enum)}"
            )

    # Window ordering: end strictly after start (contract compliance
    # rule fail_if_window_end_not_after_window_start).
    window_start = document.get("window_start")
    window_end = document.get("window_end")
    if (
        isinstance(window_start, str)
        and isinstance(window_end, str)
        and DATETIME_PATTERN.match(window_start)
        and DATETIME_PATTERN.match(window_end)
    ):
        start = _parse_timestamp(window_start)
        end = _parse_timestamp(window_end)
        if start is not None and end is not None and end <= start:
            errors.append(
                "window_end must be strictly after window_start"
            )

    # Deterministic record_id form: re-collecting the same window must
    # be idempotent, so the id is a pure function of the identity
    # tuple. Only checked once the identity fields are individually
    # valid, to avoid cascading noise.
    if (
        isinstance(record_id, str)
        and isinstance(tenant_id, str)
        and TENANT_ID_PATTERN.match(tenant_id)
        and dimension in DIMENSIONS
        and signal in SIGNALS
        and isinstance(window_start, str)
        and DATETIME_PATTERN.match(window_start)
    ):
        expected = (
            f"{tenant_id}:{dimension}:{signal}:{window_start[:10]}"
        )
        if record_id != expected:
            errors.append(
                f"record_id {record_id!r} is not the deterministic "
                f"form {expected!r}"
            )

    if "source_reference" in document:
        _validate_source_reference(
            document["source_reference"], errors
        )

    return tuple(errors)


def ensure_valid_record(document: Mapping[str, Any]) -> None:
    """Raise RecordValidationError if the document is non-conformant."""
    errors = validate_record(document)
    if errors:
        raise RecordValidationError(errors)


def ensure_valid_records(records: tuple[UsageRecord, ...]) -> None:
    """Validate built records before they may reach any sink."""
    errors: list[str] = []
    for record in records:
        for error in validate_record(record.to_dict()):
            errors.append(f"{record.record_id}: {error}")
    if errors:
        raise RecordValidationError(tuple(errors))
