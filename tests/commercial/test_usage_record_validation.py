"""Offline tests for the usage record validator (Batch 22 Task 2).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 22 validator - never under pytest. Proves:

- every record in contracts/commercial/samples/VALID_USAGE_RECORDS
  .json passes the commercialsvc validator;
- every seeded sample in INVALID_USAGE_RECORD_SAMPLES.json is
  rejected, including the missing-tenant_id record (TR-23) and the
  embedded-telemetry-payload record (TR-16 plane separation);
- the validator's enums and required-field set stay in lockstep with
  USAGE_RECORD_SCHEMA_V1.json, so contract drift fails loudly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
CONTRACTS = REPO_ROOT / "contracts" / "commercial"
SCHEMA_PATH = CONTRACTS / "USAGE_RECORD_SCHEMA_V1.json"
VALID_SAMPLES = CONTRACTS / "samples" / "VALID_USAGE_RECORDS.json"
INVALID_SAMPLES = (
    CONTRACTS / "samples" / "INVALID_USAGE_RECORD_SAMPLES.json"
)

sys.path.insert(0, str(REPO_ROOT / "services" / "commercial"))

from commercialsvc.models import (  # noqa: E402
    DIMENSIONS,
    REQUIRED_RECORD_FIELDS,
    SIGNALS,
    SOURCE_TYPES,
    UNITS,
    RecordValidationError,
)
from commercialsvc.validation import (  # noqa: E402
    ensure_valid_record,
    validate_record,
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_valid_samples_pass() -> None:
    payload = _load(VALID_SAMPLES)
    records = payload["records"]
    assert records, "valid sample file must not be empty"
    for record in records:
        errors = validate_record(record)
        assert not errors, (
            f"valid sample {record['record_id']} rejected: {errors}"
        )
    # The valid corpus covers every contract dimension.
    covered = {record["dimension"] for record in records}
    assert covered == set(DIMENSIONS)


def test_every_invalid_sample_is_rejected() -> None:
    payload = _load(INVALID_SAMPLES)
    samples = payload["samples"]
    assert samples, "invalid sample file must not be empty"
    for sample in samples:
        errors = validate_record(sample["record"])
        assert errors, (
            f"seeded rejection sample {sample['name']!r} validated "
            "cleanly - validator failure"
        )


def _errors_for(name: str) -> tuple[str, ...]:
    payload = _load(INVALID_SAMPLES)
    for sample in payload["samples"]:
        if sample["name"] == name:
            return validate_record(sample["record"])
    raise AssertionError(f"no invalid sample named {name!r}")


def test_missing_tenant_id_rejection_names_tenant_id() -> None:
    errors = _errors_for("missing-tenant-id")
    assert any("tenant_id" in error for error in errors)


def test_embedded_telemetry_payload_rejected_as_unknown_field() -> None:
    errors = _errors_for("embedded-telemetry-payload")
    assert any("sample_documents" in error for error in errors)


def test_unknown_dimension_rejected() -> None:
    errors = _errors_for("unknown-dimension")
    assert any("dimension" in error for error in errors)


def test_window_ordering_rejected() -> None:
    errors = _errors_for("window-end-not-after-start")
    assert any(
        "window_end must be strictly after" in error
        for error in errors
    )


def test_signal_unit_binding_rejected() -> None:
    errors = _errors_for("signal-unit-mismatch")
    assert any("signal" in error for error in errors)
    assert any("unit" in error for error in errors)


def test_tenant_id_pattern_enforced() -> None:
    base = _load(VALID_SAMPLES)["records"][0]
    for bad in ("Acme-Corp", "-acme", "acme-", "a" * 33, ""):
        record = dict(base, tenant_id=bad)
        # Keep record_id consistent so only the slug rule can fail.
        record["record_id"] = (
            f"{bad}:{record['dimension']}:{record['signal']}:"
            f"{record['window_start'][:10]}"
        )
        errors = validate_record(record)
        assert any("tenant_id" in error for error in errors), (
            f"tenant_id {bad!r} accepted"
        )


def test_source_reference_shape_by_source_type() -> None:
    base = _load(VALID_SAMPLES)["records"][0]
    # Aggregation source without indices is rejected.
    record = json.loads(json.dumps(base))
    del record["source_reference"]["indices"]
    assert validate_record(record)
    # Descriptor source carrying telemetry-shaped references is
    # rejected.
    record = json.loads(json.dumps(base))
    record["source_reference"] = {
        "source_type": "tenant-descriptor",
        "descriptor_field": "quotas.retention.logs_days",
        "indices": ["tenant-acme-corp-logs-2026.07.09"],
    }
    errors = validate_record(record)
    assert any("indices" in error for error in errors)


def test_ensure_valid_record_raises() -> None:
    try:
        ensure_valid_record({"record_id": "x"})
    except RecordValidationError as error:
        assert error.errors
    else:
        raise AssertionError("expected RecordValidationError")


def test_validator_constants_match_schema() -> None:
    schema = _load(SCHEMA_PATH)
    assert set(schema["required"]) == set(REQUIRED_RECORD_FIELDS)
    properties = schema["properties"]
    assert tuple(properties["dimension"]["enum"]) == DIMENSIONS
    assert tuple(properties["signal"]["enum"]) == SIGNALS
    assert tuple(properties["unit"]["enum"]) == UNITS
    reference = properties["source_reference"]
    assert (
        tuple(reference["properties"]["source_type"]["enum"])
        == SOURCE_TYPES
    )
    assert schema["additionalProperties"] is False
    assert reference["additionalProperties"] is False


def main() -> int:
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]
    for name, func in tests:
        func()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
