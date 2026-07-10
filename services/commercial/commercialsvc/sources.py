"""Usage sources: where the collector reads derivation inputs from.

ADR-0006 source/sink duality: the collector reads through the
UsageSource protocol so offline CI (FixtureSource over committed
aggregation-result JSON) and the live cluster (OpenSearchSource over
stdlib urllib) exercise the exact same pure record-building code.

Metering adds no collection path: both sources only read surfaces the
platform already operates (OpenSearch stats/aggregations and validated
tenant descriptors). OpenTelemetry remains the sole collector.
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Protocol

from commercialsvc.models import (
    DayWindow,
    IngestStat,
    QueryVolumeStat,
    SourceDataError,
    TELEMETRY_SIGNALS,
    TENANT_ID_PATTERN,
    TenantRetention,
)

# Data-plane index naming fixed by the isolation matrix:
# tenant-<tenant_id>-<signal>-<suffix>. Attribution is derived from
# index naming, never from telemetry payloads.
_TENANT_INDEX_RE = re.compile(
    r"^tenant-(?P<tenant_id>[a-z0-9][a-z0-9-]*?)"
    r"-(?P<signal>logs|metrics|traces)-(?P<suffix>.+)$"
)


class UsageSource(Protocol):
    """Read-side derivation surface for one UTC-day window."""

    def ingest_stats(
        self, window: DayWindow
    ) -> tuple[IngestStat, ...]: ...

    def tenant_retention(
        self, window: DayWindow
    ) -> tuple[TenantRetention, ...]: ...

    def query_volume(
        self, window: DayWindow
    ) -> tuple[QueryVolumeStat, ...]: ...


def _require(
    mapping: Mapping[str, Any], key: str, context: str
) -> Any:
    if key not in mapping:
        raise SourceDataError(f"{context}: missing key {key!r}")
    return mapping[key]


def _tenant_slug(value: object, context: str) -> str:
    if not isinstance(value, str) or not TENANT_ID_PATTERN.match(
        value
    ):
        raise SourceDataError(
            f"{context}: invalid tenant_id {value!r}"
        )
    return value


class FixtureSource:
    """Reads committed aggregation-result JSON fixtures.

    Fixture shape (see tests/commercial/fixtures/): a `window` day,
    `ingest` stats per tenant/signal, `tenant_descriptors` carrying
    quotas.retention, and `query_volume` audit counts. The fixture is
    validated on load so malformed fixtures fail loudly, not as
    silently-empty windows.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SourceDataError(
                f"fixture {path}: unreadable ({error})"
            ) from error
        if not isinstance(payload, Mapping):
            raise SourceDataError(
                f"fixture {path}: top level must be an object"
            )
        self._payload: Mapping[str, Any] = payload

    def fixture_window(self) -> DayWindow:
        window = _require(self._payload, "window", "fixture")
        day = _require(window, "day", "fixture window")
        return DayWindow.parse(str(day))

    def ingest_stats(
        self, window: DayWindow
    ) -> tuple[IngestStat, ...]:
        del window  # fixture data is already window-scoped
        stats = []
        for entry in self._payload.get("ingest", ()):
            context = "fixture ingest entry"
            signal = _require(entry, "signal", context)
            if signal not in TELEMETRY_SIGNALS:
                raise SourceDataError(
                    f"{context}: unknown signal {signal!r}"
                )
            stats.append(
                IngestStat(
                    tenant_id=_tenant_slug(
                        _require(entry, "tenant_id", context),
                        context,
                    ),
                    signal=signal,
                    store_size_bytes=int(
                        _require(entry, "store_size_bytes", context)
                    ),
                    document_count=int(
                        _require(entry, "document_count", context)
                    ),
                    indices=tuple(
                        _require(entry, "indices", context)
                    ),
                    content_digest=entry.get("content_digest"),
                )
            )
        return tuple(stats)

    def tenant_retention(
        self, window: DayWindow
    ) -> tuple[TenantRetention, ...]:
        del window
        retentions = []
        for entry in self._payload.get("tenant_descriptors", ()):
            context = "fixture tenant descriptor"
            tenant_id = _tenant_slug(
                _require(entry, "tenant_id", context), context
            )
            quotas = _require(entry, "quotas", context)
            retention = _require(
                quotas, "retention", f"{context} quotas"
            )
            retentions.append(
                TenantRetention(
                    tenant_id=tenant_id,
                    logs_days=int(
                        _require(retention, "logs_days", context)
                    ),
                    metrics_days=int(
                        _require(retention, "metrics_days", context)
                    ),
                    traces_days=int(
                        _require(retention, "traces_days", context)
                    ),
                )
            )
        return tuple(retentions)

    def query_volume(
        self, window: DayWindow
    ) -> tuple[QueryVolumeStat, ...]:
        del window
        stats = []
        for entry in self._payload.get("query_volume", ()):
            context = "fixture query_volume entry"
            stats.append(
                QueryVolumeStat(
                    tenant_id=_tenant_slug(
                        _require(entry, "tenant_id", context),
                        context,
                    ),
                    query_count=int(
                        _require(entry, "query_count", context)
                    ),
                    indices=tuple(entry.get("indices", ())),
                )
            )
        return tuple(stats)


class OpenSearchSource:
    """Live derivation source over stdlib urllib (no third-party
    client, ADR-0006).

    Never exercised by offline tests beyond construction; the live
    probe evidence lands with the Batch 23 harness. The base URL comes
    from deployment configuration - nothing is hardcoded here.
    """

    def __init__(self, base_url: str, timeout_seconds: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def _get_json(self, path: str) -> Mapping[str, Any]:
        request = urllib.request.Request(
            f"{self._base_url}/{path.lstrip('/')}",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(
            request, timeout=self._timeout
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise SourceDataError(
                f"OpenSearch response for {path}: not an object"
            )
        return payload

    def _post_json(
        self, path: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        request = urllib.request.Request(
            f"{self._base_url}/{path.lstrip('/')}",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            request, timeout=self._timeout
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise SourceDataError(
                f"OpenSearch response for {path}: not an object"
            )
        return payload

    def ingest_stats(
        self, window: DayWindow
    ) -> tuple[IngestStat, ...]:
        # Index stats over the tenant's per-signal daily indices
        # (isolation-matrix partitioning); tenant_id is parsed from
        # the index name, never from document payloads.
        stats: list[IngestStat] = []
        for signal in TELEMETRY_SIGNALS:
            pattern = f"tenant-*-{signal}-{window.index_suffix}"
            payload = self._get_json(f"{pattern}/_stats/store,docs")
            indices = payload.get("indices")
            if not isinstance(indices, Mapping):
                continue
            for index_name, index_stats in sorted(indices.items()):
                match = _TENANT_INDEX_RE.match(index_name)
                if match is None or match["signal"] != signal:
                    continue
                primaries = index_stats.get("primaries", {})
                stats.append(
                    IngestStat(
                        tenant_id=match["tenant_id"],
                        signal=signal,
                        store_size_bytes=int(
                            primaries.get("store", {}).get(
                                "size_in_bytes", 0
                            )
                        ),
                        document_count=int(
                            primaries.get("docs", {}).get("count", 0)
                        ),
                        indices=(index_name,),
                    )
                )
        return tuple(stats)

    def tenant_retention(
        self, window: DayWindow
    ) -> tuple[TenantRetention, ...]:
        del window  # retention is billed as currently configured
        # Validated tenant descriptors live in the Batch 20
        # control-plane store (control-tenancy-*).
        payload = self._post_json(
            "control-tenancy-tenants/_search",
            {"size": 10000, "query": {"match_all": {}}},
        )
        retentions: list[TenantRetention] = []
        hits = payload.get("hits", {}).get("hits", [])
        for hit in hits:
            source = hit.get("_source", {})
            retention = source.get("quotas", {}).get("retention", {})
            tenant_id = source.get("tenant_id")
            if not isinstance(
                tenant_id, str
            ) or not TENANT_ID_PATTERN.match(tenant_id):
                continue
            retentions.append(
                TenantRetention(
                    tenant_id=tenant_id,
                    logs_days=int(retention.get("logs_days", 0)),
                    metrics_days=int(
                        retention.get("metrics_days", 0)
                    ),
                    traces_days=int(retention.get("traces_days", 0)),
                )
            )
        return tuple(retentions)

    def query_volume(
        self, window: DayWindow
    ) -> tuple[QueryVolumeStat, ...]:
        # Counted from the existing audit surface
        # (control-tenancy-audit-*, METERING_CONTRACT_V1 query_volume
        # source); a terms aggregation keeps this one round trip.
        index = f"control-tenancy-audit-{window.index_suffix}"
        payload = self._post_json(
            f"{index}/_search",
            {
                "size": 0,
                "aggs": {
                    "per_tenant": {
                        "terms": {
                            "field": "tenant_id",
                            "size": 10000,
                        }
                    }
                },
            },
        )
        buckets = (
            payload.get("aggregations", {})
            .get("per_tenant", {})
            .get("buckets", [])
        )
        return tuple(
            QueryVolumeStat(
                tenant_id=str(bucket.get("key")),
                query_count=int(bucket.get("doc_count", 0)),
                indices=(index,),
            )
            for bucket in buckets
        )
