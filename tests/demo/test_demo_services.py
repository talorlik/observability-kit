"""Offline tests for the demo playground services (Batch 27, Task 2).

Plain python3 script - no pytest, no network, no cluster. The
emitter's HTTP transport is replaced with an in-memory capture, so
every assertion runs against the exact OTLP/HTTP JSON payloads the
services would post to the platform gateway collector.

Run: python3 tests/demo/test_demo_services.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# The demo package lives under demo/services and is installed into
# the image with pip; offline tests import it straight from the tree.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "demo" / "services"))

from demosvc import __main__ as demosvc_main  # noqa: E402
from demosvc import datastore, http_api  # noqa: E402
from demosvc.otel import (  # noqa: E402
    HISTOGRAM_BOUNDARIES_MS,
    Telemetry,
    TraceContext,
)


class CaptureTransport:
    """Captures (path, payload) pairs instead of posting them."""

    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []

    def __call__(self, path: str, payload: dict) -> None:
        # Round-trip through json to prove the payload is serializable
        # exactly as the real transport would send it.
        self.posts.append((path, json.loads(json.dumps(payload))))

    def payloads(self, path: str) -> list[dict]:
        return [payload for p, payload in self.posts if p == path]


def _capturing_telemetry(service_name: str) -> tuple[Telemetry, CaptureTransport]:
    telemetry = Telemetry(service_name)
    capture = CaptureTransport()
    telemetry.transport = capture
    return telemetry, capture


def _attr_map(encoded: list[dict]) -> dict[str, dict]:
    return {entry["key"]: entry["value"] for entry in encoded}


def _is_hex(value: str) -> bool:
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


# ----------------------------------------------------------------------
# TraceContext


def test_traceparent_roundtrip() -> None:
    ctx = TraceContext.new_root()
    assert len(ctx.trace_id) == 32 and _is_hex(ctx.trace_id)
    assert len(ctx.span_id) == 16 and _is_hex(ctx.span_id)
    header = ctx.traceparent()
    assert header == f"00-{ctx.trace_id}-{ctx.span_id}-01"
    parsed = TraceContext.from_traceparent(header)
    assert parsed is not None
    assert parsed.trace_id == ctx.trace_id
    assert parsed.span_id == ctx.span_id


def test_traceparent_rejects_malformed() -> None:
    assert TraceContext.from_traceparent(None) is None
    assert TraceContext.from_traceparent("") is None
    assert TraceContext.from_traceparent("garbage") is None
    assert TraceContext.from_traceparent("00-shorttrace-span-01") is None
    zero = "00-" + "0" * 32 + "-" + "0" * 16 + "-01"
    assert TraceContext.from_traceparent(zero) is None
    nothex = "00-" + "g" * 32 + "-" + "1234567890abcdef" + "-01"
    assert TraceContext.from_traceparent(nothex) is None


# ----------------------------------------------------------------------
# OTLP payload shapes


def test_span_payload_shape() -> None:
    telemetry, capture = _capturing_telemetry("shape-svc")
    parent = TraceContext.new_root()
    with telemetry.span(
        "GET /api/status",
        kind="SERVER",
        parent=parent,
        attributes={"http.route": "/api/status"},
    ) as span:
        span.set_attribute("http.response.status_code", 200)
    telemetry.flush()

    payloads = capture.payloads("/v1/traces")
    assert len(payloads) == 1
    resource_spans = payloads[0]["resourceSpans"]
    resource_attrs = _attr_map(resource_spans[0]["resource"]["attributes"])
    # Resource attributes on every export, including the tenant
    # routing attribute the isolation matrix filters on.
    assert resource_attrs["service.name"] == {"stringValue": "shape-svc"}
    assert resource_attrs["service.version"] == {"stringValue": "0.1.0"}
    assert resource_attrs["deployment.environment"] == {"stringValue": "dev"}
    assert resource_attrs["service.owner"] == {"stringValue": "team-demo"}
    assert resource_attrs["tenant_id"] == {"stringValue": "demo"}

    spans = resource_spans[0]["scopeSpans"][0]["spans"]
    assert len(spans) == 1
    span_json = spans[0]
    # OTLP JSON: hex ids, string nanos, numeric kind enum.
    assert len(span_json["traceId"]) == 32 and _is_hex(span_json["traceId"])
    assert len(span_json["spanId"]) == 16 and _is_hex(span_json["spanId"])
    assert span_json["traceId"] == parent.trace_id
    assert span_json["parentSpanId"] == parent.span_id
    assert span_json["kind"] == 2  # SERVER
    assert isinstance(span_json["startTimeUnixNano"], str)
    assert isinstance(span_json["endTimeUnixNano"], str)
    assert int(span_json["endTimeUnixNano"]) >= int(
        span_json["startTimeUnixNano"]
    )
    attrs = _attr_map(span_json["attributes"])
    assert attrs["http.route"] == {"stringValue": "/api/status"}
    # int64 attribute values are encoded as strings.
    assert attrs["http.response.status_code"] == {"intValue": "200"}
    assert span_json["status"] == {"code": 1}


def test_span_error_status_on_exception() -> None:
    telemetry, capture = _capturing_telemetry("err-svc")
    try:
        with telemetry.span("boom", kind="INTERNAL"):
            raise ValueError("kaput")
    except ValueError:
        pass
    else:
        raise AssertionError("span() must re-raise")
    telemetry.flush()
    span_json = capture.payloads("/v1/traces")[0]["resourceSpans"][0][
        "scopeSpans"
    ][0]["spans"][0]
    assert span_json["status"]["code"] == 2
    assert "kaput" in span_json["status"]["message"]


def test_log_payload_shape() -> None:
    telemetry, capture = _capturing_telemetry("log-svc")
    trace = TraceContext.new_root()
    telemetry.log(
        "ERROR",
        "injected fault on GET /api/orders",
        {"demo.fault_ratio": 0.5, "demo.fault_injected": True},
        trace=trace,
    )
    telemetry.flush()
    records = capture.payloads("/v1/logs")[0]["resourceLogs"][0][
        "scopeLogs"
    ][0]["logRecords"]
    assert len(records) == 1
    record = records[0]
    assert record["severityText"] == "ERROR"
    assert record["severityNumber"] == 17
    assert record["body"] == {
        "stringValue": "injected fault on GET /api/orders"
    }
    assert isinstance(record["timeUnixNano"], str)
    assert record["traceId"] == trace.trace_id
    assert record["spanId"] == trace.span_id
    attrs = _attr_map(record["attributes"])
    assert attrs["demo.fault_ratio"] == {"doubleValue": 0.5}
    # bool before int: True must encode as boolValue, not intValue.
    assert attrs["demo.fault_injected"] == {"boolValue": True}


def test_counter_payload_shape() -> None:
    telemetry, capture = _capturing_telemetry("metric-svc")
    telemetry.counter(
        "demo.http.requests",
        1,
        {"http.route": "/api/orders", "http.response.status_code": 201},
    )
    telemetry.flush()
    metrics = capture.payloads("/v1/metrics")[0]["resourceMetrics"][0][
        "scopeMetrics"
    ][0]["metrics"]
    assert metrics[0]["name"] == "demo.http.requests"
    sum_block = metrics[0]["sum"]
    assert sum_block["isMonotonic"] is True
    assert sum_block["aggregationTemporality"] == 1  # DELTA
    point = sum_block["dataPoints"][0]
    assert point["asDouble"] == 1.0
    assert isinstance(point["timeUnixNano"], str)
    attrs = _attr_map(point["attributes"])
    assert attrs["http.response.status_code"] == {"intValue": "201"}


def test_histogram_payload_shape() -> None:
    telemetry, capture = _capturing_telemetry("metric-svc")
    telemetry.histogram(
        "demo.http.server.duration", 42.0, {"http.route": "/api/orders"}
    )
    telemetry.flush()
    metrics = capture.payloads("/v1/metrics")[0]["resourceMetrics"][0][
        "scopeMetrics"
    ][0]["metrics"]
    histogram = metrics[0]["histogram"]
    assert histogram["aggregationTemporality"] == 1
    point = histogram["dataPoints"][0]
    assert point["count"] == "1"
    assert point["sum"] == 42.0
    assert point["explicitBounds"] == list(HISTOGRAM_BOUNDARIES_MS)
    # uint64 bucketCounts are strings; exactly one observation, in
    # the (25, 50] bucket for 42.0 ms -> index 5.
    assert len(point["bucketCounts"]) == len(HISTOGRAM_BOUNDARIES_MS) + 1
    assert all(isinstance(c, str) for c in point["bucketCounts"])
    assert point["bucketCounts"][5] == "1"
    assert sum(int(c) for c in point["bucketCounts"]) == 1


def test_export_failure_never_raises() -> None:
    telemetry = Telemetry("crash-svc")

    def broken_transport(path: str, payload: dict) -> None:
        raise OSError("collector unreachable")

    telemetry.transport = broken_transport
    telemetry.log("INFO", "still alive")
    telemetry.counter("demo.http.requests", 1)
    telemetry.flush()  # must not raise


# ----------------------------------------------------------------------
# Fault-injection header handling


def test_fault_ratio_parsing() -> None:
    assert http_api.parse_fault_ratio(None) == 0.0
    assert http_api.parse_fault_ratio("") == 0.0
    assert http_api.parse_fault_ratio("nonsense") == 0.0
    assert http_api.parse_fault_ratio("0.5") == 0.5
    assert http_api.parse_fault_ratio("-1") == 0.0
    assert http_api.parse_fault_ratio("7") == 1.0


def test_latency_parsing() -> None:
    assert http_api.parse_latency_ms(None) == 0
    assert http_api.parse_latency_ms("nonsense") == 0
    assert http_api.parse_latency_ms("250") == 250
    assert http_api.parse_latency_ms("250.7") == 250
    assert http_api.parse_latency_ms("-10") == 0
    assert http_api.parse_latency_ms("999999999") == 30_000


def test_should_fault() -> None:
    assert http_api.should_fault(0.0, 0.0) is False
    assert http_api.should_fault(1.0, 0.999) is True
    assert http_api.should_fault(0.5, 0.4) is True
    assert http_api.should_fault(0.5, 0.6) is False


# ----------------------------------------------------------------------
# HTTP API behavior over an ephemeral localhost server


def _request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers=dict(headers or {}), method=method
    )
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def test_http_api_fault_and_latency_headers() -> None:
    telemetry, capture = _capturing_telemetry("demo-http-api")
    state = http_api.QueueState()
    server = http_api.build_server(
        telemetry, state, "http://127.0.0.1:9", port=0
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        # Clean request succeeds and carries queue/status wiring.
        status, body = _request(f"{base}/api/status")
        assert status == 200
        assert body["pending"] == 0

        # fault-ratio 1.0 -> deterministic injected 500.
        status, body = _request(
            f"{base}/api/status",
            headers={http_api.FAULT_RATIO_HEADER: "1.0"},
        )
        assert status == 500
        assert body["error"] == "injected fault"

        # latency header delays the response measurably.
        started = time.monotonic()
        status, _ = _request(
            f"{base}/api/status",
            headers={http_api.LATENCY_HEADER: "200"},
        )
        elapsed = time.monotonic() - started
        assert status == 200
        assert elapsed >= 0.2

        # Queue poll/ack cycle: enqueue directly, poll then ack.
        item = state.enqueue("order-1", TraceContext.new_root().traceparent())
        status, body = _request(f"{base}/api/queue")
        assert status == 200
        assert [i["item_id"] for i in body["items"]] == [item["item_id"]]
        status, body = _request(
            f"{base}/api/queue",
            method="POST",
            payload={"ack": [item["item_id"]]},
        )
        assert status == 200 and body["acked"] == 1

        # /healthz stays un-instrumented probe traffic.
        status, body = _request(f"{base}/healthz")
        assert status == 200 and body == {"status": "ok"}
    finally:
        server.shutdown()
        server.server_close()

    telemetry.flush()

    # The injected fault produced an error span, an ERROR log, and a
    # 500-labelled request counter.
    spans = [
        span
        for payload in capture.payloads("/v1/traces")
        for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    ]
    fault_spans = [s for s in spans if s["status"].get("code") == 2]
    assert fault_spans, "injected fault must mark the span as error"
    assert _attr_map(fault_spans[0]["attributes"])[
        "demo.fault_injected"
    ] == {"boolValue": True}

    logs = [
        record
        for payload in capture.payloads("/v1/logs")
        for record in payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"]
    ]
    assert any(record["severityText"] == "ERROR" for record in logs)

    counters = [
        metric
        for payload in capture.payloads("/v1/metrics")
        for metric in payload["resourceMetrics"][0]["scopeMetrics"][0][
            "metrics"
        ]
        if metric["name"] == "demo.http.requests"
    ]
    statuses = {
        _attr_map(metric["sum"]["dataPoints"][0]["attributes"])[
            "http.response.status_code"
        ]["intValue"]
        for metric in counters
    }
    assert {"200", "500"} <= statuses


def test_http_api_continues_incoming_trace() -> None:
    telemetry, capture = _capturing_telemetry("demo-http-api")
    state = http_api.QueueState()
    server = http_api.build_server(
        telemetry, state, "http://127.0.0.1:9", port=0
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    upstream = TraceContext.new_root()
    try:
        status, _ = _request(
            f"{base}/api/status",
            headers={"traceparent": upstream.traceparent()},
        )
        assert status == 200
    finally:
        server.shutdown()
        server.server_close()
    telemetry.flush()
    span = capture.payloads("/v1/traces")[0]["resourceSpans"][0][
        "scopeSpans"
    ][0]["spans"][0]
    assert span["traceId"] == upstream.trace_id
    assert span["parentSpanId"] == upstream.span_id


# ----------------------------------------------------------------------
# Datastore


def test_datastore_sqlite_emits_db_spans() -> None:
    telemetry, capture = _capturing_telemetry("demo-datastore")
    with tempfile.TemporaryDirectory() as tmp:
        store = datastore.OrderStore(f"{tmp}/demo.db", telemetry)
        parent = TraceContext.new_root()
        order_id = store.insert_order("widget", 3, parent)
        assert order_id >= 1
        orders = store.list_orders(10, parent)
        assert orders[0]["item"] == "widget"
        assert orders[0]["quantity"] == 3
    telemetry.flush()

    spans = [
        span
        for payload in capture.payloads("/v1/traces")
        for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    ]
    db_spans = {
        _attr_map(s["attributes"])["db.operation.name"]["stringValue"]: s
        for s in spans
        if "db.system" in _attr_map(s["attributes"])
    }
    assert {"CREATE", "INSERT", "SELECT"} <= set(db_spans)
    insert_attrs = _attr_map(db_spans["INSERT"]["attributes"])
    assert insert_attrs["db.system"] == {"stringValue": "sqlite"}
    assert "INSERT INTO orders" in insert_attrs["db.query.text"][
        "stringValue"
    ]
    assert db_spans["INSERT"]["kind"] == 3  # CLIENT
    # Operations under a caller trace continue it.
    assert db_spans["INSERT"]["traceId"] == parent.trace_id

    counters = [
        metric
        for payload in capture.payloads("/v1/metrics")
        for metric in payload["resourceMetrics"][0]["scopeMetrics"][0][
            "metrics"
        ]
        if metric["name"] == "demo.db.operations"
    ]
    assert counters, "db operations must emit demo.db.operations"


def test_datastore_http_roundtrip() -> None:
    telemetry, capture = _capturing_telemetry("demo-datastore")
    with tempfile.TemporaryDirectory() as tmp:
        store = datastore.OrderStore(f"{tmp}/demo.db", telemetry)
        server = datastore.build_server(telemetry, store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            status, body = _request(
                f"{base}/orders",
                method="POST",
                payload={"item": "gadget", "quantity": 2},
            )
            assert status == 201 and body["order_id"] >= 1
            status, body = _request(f"{base}/orders")
            assert status == 200
            assert body["orders"][0]["item"] == "gadget"
            status, body = _request(f"{base}/status")
            assert status == 200 and body["orders"] == 1
        finally:
            server.shutdown()
            server.server_close()
    telemetry.flush()
    spans = [
        span
        for payload in capture.payloads("/v1/traces")
        for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    ]
    server_spans = [s for s in spans if s["kind"] == 2]
    assert any(s["name"] == "POST /orders" for s in server_spans)


# ----------------------------------------------------------------------
# Entrypoint dispatch


def test_dispatch_rejects_unknown_command() -> None:
    assert demosvc_main.main(["demosvc"]) == 2
    assert demosvc_main.main(["demosvc", "not-a-service"]) == 2


# ----------------------------------------------------------------------


def _run() -> int:
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok {name}")
    print(f"{len(tests) - failures}/{len(tests)} demo service tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run())
