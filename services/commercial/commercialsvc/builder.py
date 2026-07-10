"""Pure, deterministic usage record construction.

The transformation from source data to usage records is a pure
function: the same source data and window yield byte-identical records
apart from collected_at, and record_id is deterministic over
(tenant_id, dimension, signal, window_start) so re-collection of the
same window is idempotent (METERING_CONTRACT_V1.yaml `record`).

Both the fixture-driven offline path and the live OpenSearch path run
exactly this code (ADR-0006 source/sink duality).
"""

from __future__ import annotations

from commercialsvc.models import (
    COLLECTOR_VERSION,
    DayWindow,
    IngestStat,
    QueryVolumeStat,
    SourceReference,
    TELEMETRY_SIGNALS,
    TenantRetention,
    UsageRecord,
)

# Decimal gigabytes, rounded to a fixed precision so repeated builds
# are byte-identical regardless of float formatting drift.
_BYTES_PER_GB = 1_000_000_000
_GB_PRECISION = 6


def record_id_for(
    tenant_id: str, dimension: str, signal: str, window: DayWindow
) -> str:
    """Deterministic record id: tenant:dimension:signal:YYYY-MM-DD."""
    return f"{tenant_id}:{dimension}:{signal}:{window.day.isoformat()}"


def _record(
    *,
    tenant_id: str,
    dimension: str,
    signal: str,
    value: float,
    unit: str,
    window: DayWindow,
    source_reference: SourceReference,
    collected_at: str,
    collector_version: str,
) -> UsageRecord:
    return UsageRecord(
        record_id=record_id_for(tenant_id, dimension, signal, window),
        tenant_id=tenant_id,
        dimension=dimension,
        signal=signal,
        value=value,
        unit=unit,
        window_start=window.window_start,
        window_end=window.window_end,
        source_reference=source_reference,
        collected_at=collected_at,
        collector_version=collector_version,
    )


def build_ingest_records(
    stats: tuple[IngestStat, ...],
    window: DayWindow,
    collected_at: str,
    collector_version: str = COLLECTOR_VERSION,
) -> tuple[UsageRecord, ...]:
    """ingest_gb_per_day: one record per tenant per signal.

    Value is what the store retained (index store size), the correct
    bias for billing per ADR-0006.
    """
    records = []
    for stat in sorted(
        stats, key=lambda item: (item.tenant_id, item.signal)
    ):
        records.append(
            _record(
                tenant_id=stat.tenant_id,
                dimension="ingest_gb_per_day",
                signal=stat.signal,
                value=round(
                    stat.store_size_bytes / _BYTES_PER_GB,
                    _GB_PRECISION,
                ),
                unit="gb",
                window=window,
                source_reference=SourceReference(
                    source_type="opensearch-aggregation",
                    indices=tuple(sorted(stat.indices)),
                    document_count=stat.document_count,
                    content_digest=stat.content_digest,
                ),
                collected_at=collected_at,
                collector_version=collector_version,
            )
        )
    return tuple(records)


def build_retention_records(
    retentions: tuple[TenantRetention, ...],
    window: DayWindow,
    collected_at: str,
    collector_version: str = COLLECTOR_VERSION,
) -> tuple[UsageRecord, ...]:
    """retention_days: one record per tenant per signal, read from the
    validated tenant descriptor (configured capability, not observed
    storage age)."""
    records = []
    for retention in sorted(
        retentions, key=lambda item: item.tenant_id
    ):
        for signal in TELEMETRY_SIGNALS:
            records.append(
                _record(
                    tenant_id=retention.tenant_id,
                    dimension="retention_days",
                    signal=signal,
                    value=retention.days_for(signal),
                    unit="days",
                    window=window,
                    source_reference=SourceReference(
                        source_type="tenant-descriptor",
                        descriptor_field=(
                            TenantRetention.descriptor_field_for(
                                signal
                            )
                        ),
                    ),
                    collected_at=collected_at,
                    collector_version=collector_version,
                )
            )
    return tuple(records)


def build_activity_records(
    ingest_stats: tuple[IngestStat, ...],
    retentions: tuple[TenantRetention, ...],
    query_stats: tuple[QueryVolumeStat, ...],
    window: DayWindow,
    collected_at: str,
    collector_version: str = COLLECTOR_VERSION,
) -> tuple[UsageRecord, ...]:
    """active_tenants: one per-tenant 0/1 activity marker per window.

    Every usage record must carry tenant_id, so the platform count is
    never stored as a platform-scoped record; exporters aggregate the
    count at read time (ADR-0006). A tenant is active when the window
    retained any telemetry or executed any queries.
    """
    # Tenant universe: everything any source surface knows about, so
    # provisioned-but-idle tenants still get an explicit 0 marker.
    tenants = sorted(
        {stat.tenant_id for stat in ingest_stats}
        | {retention.tenant_id for retention in retentions}
        | {stat.tenant_id for stat in query_stats}
    )
    ingest_by_tenant: dict[str, list[IngestStat]] = {}
    for stat in ingest_stats:
        ingest_by_tenant.setdefault(stat.tenant_id, []).append(stat)
    queries_by_tenant = {
        stat.tenant_id: stat for stat in query_stats
    }

    records = []
    for tenant_id in tenants:
        tenant_ingest = ingest_by_tenant.get(tenant_id, [])
        query_stat = queries_by_tenant.get(tenant_id)
        document_count = sum(
            stat.document_count for stat in tenant_ingest
        ) + (query_stat.query_count if query_stat else 0)
        indices: list[str] = sorted(
            {
                index
                for stat in tenant_ingest
                for index in stat.indices
            }
            | set(query_stat.indices if query_stat else ())
        )
        if not indices:
            # The schema requires at least one index reference; for a
            # tenant with no retained telemetry we cite the data-plane
            # pattern that was probed and found empty.
            indices = [f"tenant-{tenant_id}-*-{window.index_suffix}"]
        records.append(
            _record(
                tenant_id=tenant_id,
                dimension="active_tenants",
                signal="platform",
                value=1 if document_count > 0 else 0,
                unit="count",
                window=window,
                source_reference=SourceReference(
                    source_type="opensearch-aggregation",
                    indices=tuple(indices),
                    document_count=document_count,
                ),
                collected_at=collected_at,
                collector_version=collector_version,
            )
        )
    return tuple(records)


def build_query_volume_records(
    query_stats: tuple[QueryVolumeStat, ...],
    known_tenants: tuple[str, ...],
    window: DayWindow,
    collected_at: str,
    collector_version: str = COLLECTOR_VERSION,
) -> tuple[UsageRecord, ...]:
    """query_volume: one record per tenant per window, counted from
    the existing audit/SLO surfaces (no query interception).

    Tenants known to the platform but absent from the audit count get
    an explicit 0 record so billing windows are complete.
    """
    stats_by_tenant = {stat.tenant_id: stat for stat in query_stats}
    tenants = sorted(set(known_tenants) | set(stats_by_tenant))
    records = []
    for tenant_id in tenants:
        stat = stats_by_tenant.get(tenant_id)
        if stat is not None and stat.indices:
            indices = tuple(sorted(stat.indices))
        else:
            # Audit store surface fixed by the metering contract's
            # query_volume source (control-tenancy-audit-*).
            indices = (
                f"control-tenancy-audit-{window.index_suffix}",
            )
        query_count = stat.query_count if stat else 0
        records.append(
            _record(
                tenant_id=tenant_id,
                dimension="query_volume",
                signal="platform",
                value=query_count,
                unit="queries",
                window=window,
                source_reference=SourceReference(
                    source_type="opensearch-aggregation",
                    indices=indices,
                    document_count=query_count,
                ),
                collected_at=collected_at,
                collector_version=collector_version,
            )
        )
    return tuple(records)


def build_usage_records(
    ingest_stats: tuple[IngestStat, ...],
    retentions: tuple[TenantRetention, ...],
    query_stats: tuple[QueryVolumeStat, ...],
    window: DayWindow,
    collected_at: str,
    collector_version: str = COLLECTOR_VERSION,
) -> tuple[UsageRecord, ...]:
    """All four contract dimensions for one UTC-day window, in a
    stable deterministic order (tenant, dimension, signal)."""
    known_tenants = tuple(
        sorted(
            {stat.tenant_id for stat in ingest_stats}
            | {retention.tenant_id for retention in retentions}
            | {stat.tenant_id for stat in query_stats}
        )
    )
    records = (
        build_ingest_records(
            ingest_stats, window, collected_at, collector_version
        )
        + build_retention_records(
            retentions, window, collected_at, collector_version
        )
        + build_activity_records(
            ingest_stats,
            retentions,
            query_stats,
            window,
            collected_at,
            collector_version,
        )
        + build_query_volume_records(
            query_stats,
            known_tenants,
            window,
            collected_at,
            collector_version,
        )
    )
    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.tenant_id,
                record.dimension,
                record.signal,
            ),
        )
    )
