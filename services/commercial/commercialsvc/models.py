"""Typed models and contract-fixed constants for the metering collector.

Pins the vocabulary fixed by contracts/commercial/METERING_CONTRACT_V1
.yaml and contracts/commercial/USAGE_RECORD_SCHEMA_V1.json: dimensions,
signals, units, dimension bindings, source reference forms, the
control-plane destination naming, and the UsageRecord document shape.
Stdlib-only, frozen dataclasses, no third-party dependency (ADR-0006).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

# Version stamped into every usage record's collector_version. Kept in
# lockstep with [project].version in services/commercial/pyproject.toml
# and with the samples in contracts/commercial/samples/.
COLLECTOR_VERSION = "commercialsvc-0.1.0"

# TR-16 plane separation: usage records are control-plane documents.
# Any write target that does not match the control-plane store pattern
# is refused (PlaneSeparationError), so telemetry data-plane indices
# (tenant-<id>-<signal>-*) can never receive usage records.
CONTROL_PLANE_INDEX_PREFIX = "control-tenancy-"
# Destination naming fixed by METERING_CONTRACT_V1.yaml `destination`.
USAGE_INDEX_PREFIX = "control-tenancy-usage-v1-"

# Enums, verbatim from USAGE_RECORD_SCHEMA_V1.json.
DIMENSIONS = (
    "ingest_gb_per_day",
    "retention_days",
    "active_tenants",
    "query_volume",
)
SIGNALS = ("logs", "metrics", "traces", "platform")
UNITS = ("gb", "days", "count", "queries")
SOURCE_TYPES = ("opensearch-aggregation", "tenant-descriptor")

# Signal-scoped telemetry signals (everything except the literal
# 'platform' used by tenant-level dimensions).
TELEMETRY_SIGNALS = ("logs", "metrics", "traces")

# Required top-level fields, verbatim from the schema's `required`.
REQUIRED_RECORD_FIELDS = (
    "record_id",
    "tenant_id",
    "dimension",
    "signal",
    "value",
    "unit",
    "window_start",
    "window_end",
    "source_reference",
    "collected_at",
    "collector_version",
)
# additionalProperties: false - the full known key set.
KNOWN_RECORD_FIELDS = frozenset(REQUIRED_RECORD_FIELDS)
KNOWN_SOURCE_REFERENCE_FIELDS = frozenset(
    (
        "source_type",
        "indices",
        "document_count",
        "content_digest",
        "descriptor_field",
    )
)

# Same slug rules as contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json.
TENANT_ID_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
CONTENT_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


@dataclass(frozen=True)
class DimensionBinding:
    """The schema's allOf binding for one dimension.

    Fixes which signals a dimension may carry, the single legal unit,
    and (for active_tenants) the legal value set.
    """

    signals: tuple[str, ...]
    unit: str
    value_enum: tuple[float, ...] | None = None


# Dimension/signal/unit bindings, verbatim from the schema's allOf.
DIMENSION_BINDINGS: Mapping[str, DimensionBinding] = {
    "ingest_gb_per_day": DimensionBinding(TELEMETRY_SIGNALS, "gb"),
    "retention_days": DimensionBinding(TELEMETRY_SIGNALS, "days"),
    "active_tenants": DimensionBinding(("platform",), "count", (0, 1)),
    "query_volume": DimensionBinding(("platform",), "queries"),
}


class MeteringError(Exception):
    """Base error for the metering collector."""


class PlaneSeparationError(MeteringError):
    """A usage record write targeted a non-control-plane index."""


class RecordValidationError(MeteringError):
    """One or more usage records failed contract validation."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class SourceDataError(MeteringError):
    """Source data (fixture or live response) is malformed."""


@dataclass(frozen=True)
class DayWindow:
    """One UTC-day metering window (start inclusive, end exclusive).

    METERING_CONTRACT_V1.yaml fixes utc-day granularity; deriving both
    boundaries from a single date keeps record construction
    deterministic and idempotent.
    """

    day: date

    @property
    def window_start(self) -> str:
        return f"{self.day.isoformat()}T00:00:00Z"

    @property
    def window_end(self) -> str:
        return f"{(self.day + timedelta(days=1)).isoformat()}T00:00:00Z"

    @property
    def index_suffix(self) -> str:
        """Daily index suffix in OpenSearch dotted form (YYYY.MM.DD)."""
        return self.day.strftime("%Y.%m.%d")

    @staticmethod
    def parse(day: str) -> "DayWindow":
        try:
            return DayWindow(date.fromisoformat(day))
        except ValueError as error:
            raise SourceDataError(
                f"invalid UTC day {day!r}: {error}"
            ) from error


@dataclass(frozen=True)
class SourceReference:
    """Plane-separation-safe derivation reference (TR-16).

    Only the reference forms the plane-separation contract allows are
    representable: index names, a document count, a content digest,
    and the descriptor field for descriptor-sourced dimensions.
    """

    source_type: str
    indices: tuple[str, ...] | None = None
    document_count: int | None = None
    content_digest: str | None = None
    descriptor_field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Omit unset optionals: the schema forbids null values and
        # additionalProperties, so absent means absent.
        document: dict[str, Any] = {"source_type": self.source_type}
        if self.indices is not None:
            document["indices"] = list(self.indices)
        if self.document_count is not None:
            document["document_count"] = self.document_count
        if self.content_digest is not None:
            document["content_digest"] = self.content_digest
        if self.descriptor_field is not None:
            document["descriptor_field"] = self.descriptor_field
        return document


@dataclass(frozen=True)
class UsageRecord:
    """One metered usage measurement (USAGE_RECORD_SCHEMA_V1.json).

    Field names match the schema exactly; to_dict() emits the document
    written to control-tenancy-usage-v1-* indices.
    """

    record_id: str
    tenant_id: str
    dimension: str
    signal: str
    value: float
    unit: str
    window_start: str
    window_end: str
    source_reference: SourceReference
    collected_at: str
    collector_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "tenant_id": self.tenant_id,
            "dimension": self.dimension,
            "signal": self.signal,
            "value": self.value,
            "unit": self.unit,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "source_reference": self.source_reference.to_dict(),
            "collected_at": self.collected_at,
            "collector_version": self.collector_version,
        }


# --- Source-side input models (what a UsageSource yields) -----------


@dataclass(frozen=True)
class IngestStat:
    """Store-derived ingest statistics for one tenant and one signal.

    Values come from OpenSearch index stats over the tenant's
    per-signal daily indices; store_size_bytes reflects what the store
    retained (ADR-0006: never charge for data the platform failed to
    keep).
    """

    tenant_id: str
    signal: str
    store_size_bytes: int
    document_count: int
    indices: tuple[str, ...]
    content_digest: str | None = None


@dataclass(frozen=True)
class TenantRetention:
    """Configured retention days from a validated tenant descriptor.

    retention_days is descriptor-derived (billed as configured
    capability, not observed storage age) per METERING_CONTRACT_V1.
    """

    tenant_id: str
    logs_days: int
    metrics_days: int
    traces_days: int

    def days_for(self, signal: str) -> int:
        values = {
            "logs": self.logs_days,
            "metrics": self.metrics_days,
            "traces": self.traces_days,
        }
        return values[signal]

    @staticmethod
    def descriptor_field_for(signal: str) -> str:
        # Dotted quota fields fixed by the tenant contract schema and
        # echoed in the metering contract's retention_days source.
        return f"quotas.retention.{signal}_days"


@dataclass(frozen=True)
class QueryVolumeStat:
    """Query count for one tenant over the window, from the existing
    audit/SLO surfaces (no query interception is added)."""

    tenant_id: str
    query_count: int
    indices: tuple[str, ...] = field(default_factory=tuple)


def utc_now_timestamp() -> str:
    """Schema-conformant collected_at timestamp for 'now' in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
