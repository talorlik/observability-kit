"""commercialsvc: the Observability Kit metering collector.

Batch 22 (TB-22, TR-23, TR-16), architecture fixed by
docs/adr/ADR_0006_METERING_ARCHITECTURE.md; contract surface fixed by
contracts/commercial/METERING_CONTRACT_V1.yaml and
contracts/commercial/USAGE_RECORD_SCHEMA_V1.json.
"""

from __future__ import annotations

# commercialsvc.metering (run_job, main) is deliberately not
# re-exported here: importing the entrypoint module from the package
# init trips runpy's double-import warning under
# `python -m commercialsvc.metering`.
from commercialsvc.builder import build_usage_records, record_id_for
from commercialsvc.models import (
    COLLECTOR_VERSION,
    CONTROL_PLANE_INDEX_PREFIX,
    USAGE_INDEX_PREFIX,
    DayWindow,
    IngestStat,
    MeteringError,
    PlaneSeparationError,
    QueryVolumeStat,
    RecordValidationError,
    SourceDataError,
    SourceReference,
    TenantRetention,
    UsageRecord,
)
from commercialsvc.sinks import (
    FileSink,
    InMemorySink,
    OpenSearchBulkSink,
    UsageSink,
    ensure_control_plane_index,
    usage_index_for,
)
from commercialsvc.sources import (
    FixtureSource,
    OpenSearchSource,
    UsageSource,
)
from commercialsvc.validation import (
    ensure_valid_record,
    ensure_valid_records,
    validate_record,
)

__version__ = "0.1.0"

__all__ = [
    "COLLECTOR_VERSION",
    "CONTROL_PLANE_INDEX_PREFIX",
    "USAGE_INDEX_PREFIX",
    "DayWindow",
    "FileSink",
    "FixtureSource",
    "InMemorySink",
    "IngestStat",
    "MeteringError",
    "OpenSearchBulkSink",
    "OpenSearchSource",
    "PlaneSeparationError",
    "QueryVolumeStat",
    "RecordValidationError",
    "SourceDataError",
    "SourceReference",
    "TenantRetention",
    "UsageRecord",
    "UsageSink",
    "UsageSource",
    "build_usage_records",
    "ensure_control_plane_index",
    "ensure_valid_record",
    "ensure_valid_records",
    "record_id_for",
    "usage_index_for",
    "validate_record",
]
