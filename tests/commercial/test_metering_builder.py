"""Offline tests for the pure usage record builder (Batch 22 Task 2).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 22 validator - never under pytest. Proves the
determinism and idempotency contract of METERING_CONTRACT_V1.yaml
`record`: same source data + window -> byte-identical records apart
from collected_at, with record_id deterministic over
(tenant_id, dimension, signal, window_start).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
FIXTURE = TESTS_DIR / "fixtures" / "aggregation_window_2026_07_09.json"

sys.path.insert(0, str(REPO_ROOT / "services" / "commercial"))

from commercialsvc.builder import (  # noqa: E402
    build_usage_records,
    record_id_for,
)
from commercialsvc.models import DayWindow  # noqa: E402
from commercialsvc.sources import FixtureSource  # noqa: E402
from commercialsvc.validation import validate_record  # noqa: E402


def _build(collected_at: str) -> tuple[Any, ...]:
    source = FixtureSource(FIXTURE)
    window = source.fixture_window()
    return build_usage_records(
        ingest_stats=source.ingest_stats(window),
        retentions=source.tenant_retention(window),
        query_stats=source.query_volume(window),
        window=window,
        collected_at=collected_at,
    )


def _stripped(records: tuple[Any, ...]) -> str:
    documents = []
    for record in records:
        document = record.to_dict()
        del document["collected_at"]
        documents.append(document)
    # Serialized comparison proves byte-identical output, not just
    # structural equality.
    return json.dumps(documents, sort_keys=True)


def test_builder_is_deterministic_and_idempotent() -> None:
    first = _build("2026-07-10T01:05:00Z")
    second = _build("2026-07-10T09:30:00Z")
    assert _stripped(first) == _stripped(second)
    # collected_at is the only field allowed to differ.
    assert first[0].collected_at != second[0].collected_at


def test_record_id_is_deterministic_over_identity_tuple() -> None:
    window = DayWindow.parse("2026-07-09")
    assert (
        record_id_for("acme-corp", "ingest_gb_per_day", "logs", window)
        == "acme-corp:ingest_gb_per_day:logs:2026-07-09"
    )
    records = _build("2026-07-10T01:05:00Z")
    for record in records:
        expected = record_id_for(
            record.tenant_id,
            record.dimension,
            record.signal,
            window,
        )
        assert record.record_id == expected


def test_all_four_dimensions_are_produced() -> None:
    records = _build("2026-07-10T01:05:00Z")
    assert {record.dimension for record in records} == {
        "ingest_gb_per_day",
        "retention_days",
        "active_tenants",
        "query_volume",
    }
    # Signal-scoped dimensions cover every telemetry signal.
    for dimension in ("ingest_gb_per_day", "retention_days"):
        signals = {
            record.signal
            for record in records
            if record.dimension == dimension
        }
        assert {"logs", "metrics", "traces"} <= signals


def test_every_record_carries_tenant_id() -> None:
    records = _build("2026-07-10T01:05:00Z")
    assert records
    for record in records:
        assert record.tenant_id
        assert record.to_dict()["tenant_id"] == record.tenant_id


def test_ingest_value_is_store_derived_decimal_gb() -> None:
    records = _build("2026-07-10T01:05:00Z")
    by_id = {record.record_id: record for record in records}
    logs = by_id["acme-corp:ingest_gb_per_day:logs:2026-07-09"]
    # 12_400_000_000 bytes -> 12.4 decimal GB.
    assert logs.value == 12.4
    assert logs.unit == "gb"
    reference = logs.source_reference
    assert reference.source_type == "opensearch-aggregation"
    assert reference.indices == (
        "tenant-acme-corp-logs-2026.07.09",
    )
    assert reference.document_count == 1842211


def test_retention_is_descriptor_derived() -> None:
    records = _build("2026-07-10T01:05:00Z")
    by_id = {record.record_id: record for record in records}
    logs = by_id["acme-corp:retention_days:logs:2026-07-09"]
    assert logs.value == 30
    assert logs.source_reference.source_type == "tenant-descriptor"
    assert (
        logs.source_reference.descriptor_field
        == "quotas.retention.logs_days"
    )
    assert logs.source_reference.indices is None


def test_activity_markers_are_per_tenant_zero_or_one() -> None:
    records = _build("2026-07-10T01:05:00Z")
    activity = {
        record.tenant_id: record
        for record in records
        if record.dimension == "active_tenants"
    }
    # Active tenant with retained telemetry and queries.
    assert activity["acme-corp"].value == 1
    # Provisioned-but-idle tenant gets an explicit 0 marker; the
    # platform count is aggregated at read time, never stored as a
    # platform-scoped record (every record carries tenant_id).
    assert activity["globex"].value == 0
    for record in activity.values():
        assert record.signal == "platform"
        assert record.unit == "count"


def test_query_volume_counts_and_zero_fill() -> None:
    records = _build("2026-07-10T01:05:00Z")
    volume = {
        record.tenant_id: record
        for record in records
        if record.dimension == "query_volume"
    }
    assert volume["acme-corp"].value == 5321
    assert volume["globex"].value == 0
    assert volume["acme-corp"].source_reference.indices == (
        "control-tenancy-audit-2026.07.09",
    )


def test_built_records_are_schema_conformant() -> None:
    for record in _build("2026-07-10T01:05:00Z"):
        errors = validate_record(record.to_dict())
        assert not errors, f"{record.record_id}: {errors}"


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
