"""Offline tests for the usage sinks (Batch 22 Task 2, TR-16).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 22 validator - never under pytest. Proves the
plane-separation write guard: the destination index derives from the
window day as control-tenancy-usage-v1-<YYYY.MM.DD>, and every sink
refuses any target outside control-tenancy-* (in particular tenant
data-plane indices). The OpenSearch bulk sink is exercised only
through construction and its pure payload builder - no network.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
FIXTURE = TESTS_DIR / "fixtures" / "aggregation_window_2026_07_09.json"

sys.path.insert(0, str(REPO_ROOT / "services" / "commercial"))

from commercialsvc.builder import build_usage_records  # noqa: E402
from commercialsvc.models import (  # noqa: E402
    PlaneSeparationError,
    UsageRecord,
)
from commercialsvc.sinks import (  # noqa: E402
    FileSink,
    InMemorySink,
    OpenSearchBulkSink,
    ensure_control_plane_index,
    usage_index_for,
)
from commercialsvc.sources import FixtureSource  # noqa: E402

DATA_PLANE_INDEX = "tenant-acme-corp-logs-2026.07.09"


def _records() -> tuple[UsageRecord, ...]:
    source = FixtureSource(FIXTURE)
    window = source.fixture_window()
    return build_usage_records(
        ingest_stats=source.ingest_stats(window),
        retentions=source.tenant_retention(window),
        query_stats=source.query_volume(window),
        window=window,
        collected_at="2026-07-10T01:05:00Z",
    )


def _window() -> object:
    return FixtureSource(FIXTURE).fixture_window()


def test_usage_index_derives_from_window_day() -> None:
    index = usage_index_for(FixtureSource(FIXTURE).fixture_window())
    assert index == "control-tenancy-usage-v1-2026.07.09"
    assert index.startswith("control-tenancy-")


def test_control_plane_guard_refuses_data_plane_targets() -> None:
    ensure_control_plane_index("control-tenancy-usage-v1-2026.07.09")
    for bad in (
        DATA_PLANE_INDEX,
        "tenant-acme-corp-logs-*",
        "otel-logs-2026.07.09",
        "usage-v1-2026.07.09",
    ):
        try:
            ensure_control_plane_index(bad)
        except PlaneSeparationError:
            pass
        else:
            raise AssertionError(f"index {bad!r} was not refused")


def test_in_memory_sink_writes_and_refuses() -> None:
    records = _records()
    sink = InMemorySink()
    index = usage_index_for(FixtureSource(FIXTURE).fixture_window())
    sink.write(index, records)
    assert len(sink.written[index]) == len(records)
    try:
        sink.write(DATA_PLANE_INDEX, records)
    except PlaneSeparationError:
        pass
    else:
        raise AssertionError("data-plane write was not refused")
    # The refused write left no trace.
    assert DATA_PLANE_INDEX not in sink.written


def test_file_sink_writes_and_refuses() -> None:
    records = _records()
    index = usage_index_for(FixtureSource(FIXTURE).fixture_window())
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        sink = FileSink(directory)
        sink.write(index, records)
        written = json.loads(
            (directory / f"{index}.json").read_text(encoding="utf-8")
        )
        assert len(written) == len(records)
        assert all(document["tenant_id"] for document in written)
        try:
            sink.write(DATA_PLANE_INDEX, records)
        except PlaneSeparationError:
            pass
        else:
            raise AssertionError("data-plane write was not refused")
        assert not (directory / f"{DATA_PLANE_INDEX}.json").exists()


def test_bulk_sink_constructs_and_builds_idempotent_payload() -> None:
    # Construction only - the live write path is never exercised
    # offline (ADR-0006; Batch 23 owns live evidence).
    sink = OpenSearchBulkSink("http://opensearch.example.internal")
    records = _records()
    index = usage_index_for(FixtureSource(FIXTURE).fixture_window())
    payload = sink.build_bulk_payload(index, records)
    lines = payload.strip().split("\n")
    assert len(lines) == 2 * len(records)
    action = json.loads(lines[0])
    document = json.loads(lines[1])
    # _id is the deterministic record_id so re-collection upserts.
    assert action["index"]["_index"] == index
    assert action["index"]["_id"] == document["record_id"]
    try:
        sink.build_bulk_payload(DATA_PLANE_INDEX, records)
    except PlaneSeparationError:
        pass
    else:
        raise AssertionError("data-plane payload was not refused")


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
