"""Standard-library OTLP/HTTP JSON emitter (Batch 27, ADR-0011).

Every demo service emits logs, metrics, and traces through this module
to the platform gateway collector - never to OpenSearch or Neo4j
directly (TR-02, TR-07). The OpenTelemetry SDK is deliberately not
used (ADR-0011 decision 2): this emitter keeps the demo package
stdlib-only and is pinned by tests to the OTLP JSON encoding rules.

Encoding notes (OTLP 1.x JSON mapping of the protobuf schema):

- ``traceId`` / ``spanId`` are lowercase HEX strings (32 / 16 chars),
  not base64 as naive proto3 JSON would produce.
- 64-bit integers (``timeUnixNano``, ``count``, ``bucketCounts``,
  ``intValue``) are encoded as decimal strings.
- Attributes are ``[{"key": k, "value": {"stringValue"|"intValue"|
  "doubleValue"|"boolValue": v}}]``.

Export is best-effort by contract: a short timeout, buffered
batching, and a never-raise transport. Telemetry loss must never take
a demo workload down with it; failures are written to stderr and the
batch is dropped.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from bisect import bisect_left
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator

_DEFAULT_ENDPOINT = "http://otel-gateway.observability.svc.cluster.local:4318"

# Short timeout so a slow or absent collector never stalls request
# handling for more than the flush call that hit it.
_EXPORT_TIMEOUT_SECONDS = 2.0

# Buffered batching: flush automatically once any signal buffer holds
# this many entries. Callers may flush() explicitly at natural
# boundaries (end of request, end of job run).
_FLUSH_THRESHOLD = 32

# Explicit histogram bucket boundaries tuned for request latency in
# milliseconds (sub-ms up to multi-second faults injected by the load
# generator's latency scenarios).
HISTOGRAM_BOUNDARIES_MS: tuple[float, ...] = (
    1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0,
    250.0, 500.0, 1000.0, 2500.0, 5000.0,
)

# OTLP SpanKind enum values (trace.proto).
_SPAN_KINDS: dict[str, int] = {
    "UNSPECIFIED": 0,
    "INTERNAL": 1,
    "SERVER": 2,
    "CLIENT": 3,
    "PRODUCER": 4,
    "CONSUMER": 5,
}

# OTLP SeverityNumber anchor values (logs.proto).
_SEVERITY_NUMBERS: dict[str, int] = {
    "TRACE": 1,
    "DEBUG": 5,
    "INFO": 9,
    "WARN": 13,
    "ERROR": 17,
    "FATAL": 21,
}


def _encode_value(value: object) -> dict[str, object]:
    """Encode one attribute value per the OTLP AnyValue JSON mapping.

    bool is checked before int because bool is an int subclass in
    Python; int64 is a string in proto3 JSON.
    """
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def _encode_attributes(
    attributes: dict[str, object] | None,
) -> list[dict[str, object]]:
    if not attributes:
        return []
    return [
        {"key": key, "value": _encode_value(value)}
        for key, value in attributes.items()
    ]


@dataclass
class TraceContext:
    """W3C trace-context identity of one span."""

    trace_id: str  # 32 lowercase hex chars
    span_id: str  # 16 lowercase hex chars

    def traceparent(self) -> str:
        """Render the W3C traceparent header (sampled flag set)."""
        return f"00-{self.trace_id}-{self.span_id}-01"

    @staticmethod
    def from_traceparent(value: str | None) -> "TraceContext | None":
        """Parse an incoming traceparent header; None when absent or
        malformed - the caller then starts a new root trace."""
        if not value:
            return None
        parts = value.strip().split("-")
        if len(parts) != 4:
            return None
        _, trace_id, span_id, _ = parts
        if len(trace_id) != 32 or len(span_id) != 16:
            return None
        try:
            int(trace_id, 16)
            int(span_id, 16)
        except ValueError:
            return None
        # All-zero ids are invalid per the W3C spec.
        if set(trace_id) == {"0"} or set(span_id) == {"0"}:
            return None
        return TraceContext(trace_id=trace_id.lower(), span_id=span_id.lower())

    @staticmethod
    def new_root() -> "TraceContext":
        return TraceContext(
            trace_id=secrets.token_hex(16),
            span_id=secrets.token_hex(8),
        )


@dataclass
class SpanHandle:
    """Mutable view of an in-flight span, yielded by Telemetry.span()."""

    context: TraceContext
    attributes: dict[str, object] = field(default_factory=dict)
    ok: bool = True
    status_message: str = ""

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def set_status(self, ok: bool, message: str = "") -> None:
        self.ok = ok
        self.status_message = message


class Telemetry:
    """Buffered OTLP/HTTP JSON exporter for one service instance.

    Thread-safe: the HTTP API service handles requests on multiple
    threads and all of them share one Telemetry.
    """

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self._endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", _DEFAULT_ENDPOINT
        ).rstrip("/")
        # Resource attributes stamped on every export. tenant_id is
        # the tenant routing attribute: the collector routing layer
        # stamps/propagates it into the per-tenant indices and the
        # isolation matrix's document-level security filters on the
        # tenant_id field (contracts/tenancy/
        # TENANT_ISOLATION_MATRIX_V1.yaml).
        self._resource_attributes: dict[str, object] = {
            "service.name": service_name,
            "service.version": os.environ.get(
                "DEMO_SERVICE_VERSION", "0.1.0"
            ),
            "deployment.environment": os.environ.get(
                "DEMO_ENVIRONMENT", "dev"
            ),
            "service.owner": os.environ.get("DEMO_OWNER", "team-demo"),
            "tenant_id": os.environ.get("DEMO_TENANT_ID", "demo"),
        }
        self._lock = threading.Lock()
        self._spans: list[dict[str, object]] = []
        self._logs: list[dict[str, object]] = []
        self._metrics: list[dict[str, object]] = []
        # Transport is an instance attribute so offline tests can
        # capture payloads without any network or monkeypatching of
        # urllib internals.
        self.transport: Callable[[str, dict[str, object]], None] = (
            self._http_post
        )

    # ------------------------------------------------------------------
    # Traces

    @contextmanager
    def span(
        self,
        name: str,
        kind: str = "SERVER",
        parent: TraceContext | None = None,
        attributes: dict[str, object] | None = None,
    ) -> Iterator[SpanHandle]:
        """Record one span; emits on context-manager exit.

        A parent continues the parent's trace; without one a new root
        trace starts. Exceptions mark the span as error and re-raise.
        """
        if parent is not None:
            context = TraceContext(
                trace_id=parent.trace_id, span_id=secrets.token_hex(8)
            )
            parent_span_id = parent.span_id
        else:
            context = TraceContext.new_root()
            parent_span_id = ""
        handle = SpanHandle(context=context, attributes=dict(attributes or {}))
        start_ns = time.time_ns()
        try:
            yield handle
        except Exception as exc:
            handle.set_status(False, f"{type(exc).__name__}: {exc}")
            raise
        finally:
            end_ns = time.time_ns()
            span: dict[str, object] = {
                "traceId": context.trace_id,
                "spanId": context.span_id,
                "name": name,
                "kind": _SPAN_KINDS.get(kind, 0),
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(end_ns),
                "attributes": _encode_attributes(handle.attributes),
                "status": (
                    {"code": 1}
                    if handle.ok
                    else {"code": 2, "message": handle.status_message}
                ),
            }
            if parent_span_id:
                span["parentSpanId"] = parent_span_id
            self._buffer(self._spans, span)

    # ------------------------------------------------------------------
    # Logs

    def log(
        self,
        severity: str,
        body: str,
        attributes: dict[str, object] | None = None,
        trace: TraceContext | None = None,
    ) -> None:
        severity = severity.upper()
        record: dict[str, object] = {
            "timeUnixNano": str(time.time_ns()),
            "severityText": severity,
            "severityNumber": _SEVERITY_NUMBERS.get(severity, 9),
            "body": {"stringValue": body},
            "attributes": _encode_attributes(attributes),
        }
        if trace is not None:
            record["traceId"] = trace.trace_id
            record["spanId"] = trace.span_id
        self._buffer(self._logs, record)

    # ------------------------------------------------------------------
    # Metrics

    def counter(
        self,
        name: str,
        value: float = 1.0,
        attributes: dict[str, object] | None = None,
    ) -> None:
        """Monotonic delta sum - one data point per observation."""
        now = str(time.time_ns())
        self._buffer(
            self._metrics,
            {
                "name": name,
                "sum": {
                    "dataPoints": [
                        {
                            "asDouble": float(value),
                            "startTimeUnixNano": now,
                            "timeUnixNano": now,
                            "attributes": _encode_attributes(attributes),
                        }
                    ],
                    # AGGREGATION_TEMPORALITY_DELTA = 1
                    "aggregationTemporality": 1,
                    "isMonotonic": True,
                },
            },
        )

    def histogram(
        self,
        name: str,
        value: float,
        attributes: dict[str, object] | None = None,
    ) -> None:
        """Delta histogram with explicit latency-oriented bounds."""
        bounds = HISTOGRAM_BOUNDARIES_MS
        bucket_counts = ["0"] * (len(bounds) + 1)
        # OTLP explicit bounds are upper-inclusive: bucket i covers
        # (bounds[i-1], bounds[i]], so boundary values use bisect_left.
        bucket_counts[bisect_left(bounds, float(value))] = "1"
        now = str(time.time_ns())
        self._buffer(
            self._metrics,
            {
                "name": name,
                "histogram": {
                    "dataPoints": [
                        {
                            "count": "1",
                            "sum": float(value),
                            "bucketCounts": bucket_counts,
                            "explicitBounds": list(bounds),
                            "startTimeUnixNano": now,
                            "timeUnixNano": now,
                            "attributes": _encode_attributes(attributes),
                        }
                    ],
                    "aggregationTemporality": 1,
                },
            },
        )

    # ------------------------------------------------------------------
    # Export

    def flush(self) -> None:
        """Export and clear all buffers. Never raises."""
        with self._lock:
            spans, self._spans = self._spans, []
            logs, self._logs = self._logs, []
            metrics, self._metrics = self._metrics, []
        resource = {"attributes": _encode_attributes(self._resource_attributes)}
        scope = {"name": "demosvc", "version": "0.1.0"}
        if spans:
            self._export(
                "/v1/traces",
                {
                    "resourceSpans": [
                        {
                            "resource": resource,
                            "scopeSpans": [{"scope": scope, "spans": spans}],
                        }
                    ]
                },
            )
        if logs:
            self._export(
                "/v1/logs",
                {
                    "resourceLogs": [
                        {
                            "resource": resource,
                            "scopeLogs": [
                                {"scope": scope, "logRecords": logs}
                            ],
                        }
                    ]
                },
            )
        if metrics:
            self._export(
                "/v1/metrics",
                {
                    "resourceMetrics": [
                        {
                            "resource": resource,
                            "scopeMetrics": [
                                {"scope": scope, "metrics": metrics}
                            ],
                        }
                    ]
                },
            )

    def _buffer(
        self, buffer: list[dict[str, object]], entry: dict[str, object]
    ) -> None:
        with self._lock:
            buffer.append(entry)
            should_flush = len(buffer) >= _FLUSH_THRESHOLD
        if should_flush:
            self.flush()

    def _export(self, path: str, payload: dict[str, object]) -> None:
        """Best-effort export: log to stderr and drop on any failure."""
        try:
            self.transport(path, payload)
        except Exception as exc:  # noqa: BLE001 - never crash the service
            print(
                f"demosvc otel export failed path={path} "
                f"error={type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    def _http_post(self, path: str, payload: dict[str, object]) -> None:
        request = urllib.request.Request(
            self._endpoint + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(
            request, timeout=_EXPORT_TIMEOUT_SECONDS
        ) as response:
            response.read()
