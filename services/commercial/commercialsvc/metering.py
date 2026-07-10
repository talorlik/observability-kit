"""Metering collector job entrypoint (Batch 22 Task 2, TR-23).

Wires source -> builder -> validator -> sink for one UTC-day window:

    python -m commercialsvc.metering --fixture <aggregation.json>
    python -m commercialsvc.metering --opensearch-url <url> \
        --day 2026-07-09

Records are validated against USAGE_RECORD_SCHEMA_V1.json semantics
before any sink write; a validation failure aborts the run with a
non-zero exit and nothing is written. The destination index is derived
from the window day (control-tenancy-usage-v1-<YYYY.MM.DD>) and the
sink refuses any non-control-plane target (TR-16).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from commercialsvc.builder import build_usage_records
from commercialsvc.models import (
    COLLECTOR_VERSION,
    DayWindow,
    MeteringError,
    UsageRecord,
    utc_now_timestamp,
)
from commercialsvc.sinks import (
    FileSink,
    InMemorySink,
    OpenSearchBulkSink,
    UsageSink,
    usage_index_for,
)
from commercialsvc.sources import (
    FixtureSource,
    OpenSearchSource,
    UsageSource,
)
from commercialsvc.validation import ensure_valid_records


def run_job(
    source: UsageSource,
    sink: UsageSink,
    window: DayWindow,
    collected_at: str | None = None,
    collector_version: str = COLLECTOR_VERSION,
) -> tuple[UsageRecord, ...]:
    """Collect, validate, and write one window; return the records.

    Pure apart from collected_at defaulting and the sink write, so
    tests drive it directly with fixture sources and in-memory sinks.
    """
    stamp = collected_at or utc_now_timestamp()
    records = build_usage_records(
        ingest_stats=source.ingest_stats(window),
        retentions=source.tenant_retention(window),
        query_stats=source.query_volume(window),
        window=window,
        collected_at=stamp,
        collector_version=collector_version,
    )
    # Validation gates the sink: no record reaches a store unless the
    # whole window is contract-conformant (fail loudly, write nothing).
    ensure_valid_records(records)
    sink.write(usage_index_for(window), records)
    return records


def _default_day() -> str:
    # A metering window must be a complete UTC day, so the default is
    # yesterday, the most recent finished window.
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    return yesterday.isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m commercialsvc.metering",
        description=(
            "Metering collector: derives per-tenant usage records "
            "for one UTC-day window and writes them to "
            "control-tenancy-usage-v1-* (TR-23, ADR-0006)."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--fixture",
        type=Path,
        help=(
            "read derivation inputs from a committed "
            "aggregation-result JSON fixture (offline mode)"
        ),
    )
    mode.add_argument(
        "--opensearch-url",
        help=(
            "base URL of the OpenSearch control/data plane endpoint "
            "(live mode; supplied by deployment configuration)"
        ),
    )
    parser.add_argument(
        "--day",
        help=(
            "UTC day to meter (YYYY-MM-DD); defaults to the fixture "
            "window in fixture mode, else yesterday"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "write records as JSON files per index instead of the "
            "mode's default sink"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        source: UsageSource
        if args.fixture is not None:
            fixture_source = FixtureSource(args.fixture)
            source = fixture_source
            window = (
                DayWindow.parse(args.day)
                if args.day
                else fixture_source.fixture_window()
            )
        else:
            source = OpenSearchSource(args.opensearch_url)
            window = DayWindow.parse(args.day or _default_day())

        sink: UsageSink
        if args.output_dir is not None:
            sink = FileSink(args.output_dir)
        elif args.opensearch_url is not None:
            sink = OpenSearchBulkSink(args.opensearch_url)
        else:
            # Fixture mode without an output directory: dry run
            # through the in-memory sink, still fully validated.
            sink = InMemorySink()

        records = run_job(source, sink, window)
    except MeteringError as error:
        print(f"metering failed: {error}", file=sys.stderr)
        return 1

    by_dimension: dict[str, int] = {}
    for record in records:
        by_dimension[record.dimension] = (
            by_dimension.get(record.dimension, 0) + 1
        )
    print(
        f"metered window {window.window_start} -> "
        f"{window.window_end} into {usage_index_for(window)}: "
        f"{len(records)} records"
    )
    for dimension in sorted(by_dimension):
        print(f"  {dimension}: {by_dimension[dimension]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
