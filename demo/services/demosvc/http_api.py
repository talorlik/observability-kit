"""Demo HTTP API service (Batch 27, ADR-0011).

A JSON API on port 8080 that fronts the demo order flow: order
creation calls the datastore service over HTTP (CLIENT span), and a
work queue is exposed for the asynchronous worker to poll and
acknowledge. Incoming W3C traceparent headers are continued so the
load generator, this API, the datastore, and the worker share traces.

Fault injection is driven by the load generator through request
headers (ADR-0011 decision 3):

- ``x-demo-fault-ratio``: float 0..1; with that probability the
  request is answered 500, the span is marked error, and an ERROR log
  is emitted.
- ``x-demo-latency-ms``: int; sleep that many milliseconds before
  responding.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from demosvc.otel import SpanHandle, Telemetry, TraceContext

FAULT_RATIO_HEADER = "x-demo-fault-ratio"
LATENCY_HEADER = "x-demo-latency-ms"

# Upper bound on injected latency so a malformed scenario cannot park
# handler threads for minutes.
_MAX_LATENCY_MS = 30_000

_QUEUE_POLL_BATCH = 10


def parse_fault_ratio(raw: str | None) -> float:
    """Parse the fault-ratio header; malformed values mean no fault."""
    if not raw:
        return 0.0
    try:
        value = float(raw)
    except ValueError:
        return 0.0
    return min(max(value, 0.0), 1.0)


def parse_latency_ms(raw: str | None) -> int:
    """Parse the latency header; malformed values mean no delay."""
    if not raw:
        return 0
    try:
        value = int(float(raw))
    except ValueError:
        return 0
    return min(max(value, 0), _MAX_LATENCY_MS)


def should_fault(ratio: float, roll: float) -> bool:
    """Decide fault injection from a ratio and a uniform [0,1) roll."""
    return ratio > 0.0 and roll < ratio


class QueueState:
    """In-memory work queue shared between the API handler threads.

    Each queued item stores the traceparent of the request that
    enqueued it, so the worker continues the same trace.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: list[dict[str, object]] = []
        self._inflight: dict[str, dict[str, object]] = {}
        self._acked = 0
        self._sequence = 0

    def enqueue(self, order_id: object, traceparent: str) -> dict[str, object]:
        with self._lock:
            self._sequence += 1
            item: dict[str, object] = {
                "item_id": f"work-{self._sequence}",
                "order_id": order_id,
                "traceparent": traceparent,
                "enqueued_at": time.time(),
            }
            self._pending.append(item)
            return item

    def poll(self, max_items: int) -> list[dict[str, object]]:
        with self._lock:
            batch = self._pending[:max_items]
            self._pending = self._pending[max_items:]
            for item in batch:
                self._inflight[str(item["item_id"])] = item
            return batch

    def ack(self, item_ids: list[str]) -> int:
        with self._lock:
            acked = 0
            for item_id in item_ids:
                if self._inflight.pop(item_id, None) is not None:
                    acked += 1
            self._acked += acked
            return acked

    def depth(self) -> int:
        with self._lock:
            return len(self._pending)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "pending": len(self._pending),
                "inflight": len(self._inflight),
                "acked": self._acked,
            }


class DemoApiHandler(BaseHTTPRequestHandler):
    """Routes: /api/orders, /api/queue, /api/status, /healthz."""

    # Injected by main() (and by the offline tests).
    telemetry: Telemetry
    state: QueueState
    datastore_url: str

    server_version = "demo-http-api/0.1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default stderr access log; requests are logged
        as trace-correlated OTLP log records instead."""

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        self._handle("POST")

    # ------------------------------------------------------------------

    def _handle(self, method: str) -> None:
        route = self.path.split("?", 1)[0]
        if route == "/healthz":
            # Liveness probe traffic stays out of the demo telemetry.
            self._respond(200, {"status": "ok"})
            return

        telemetry = self.telemetry
        parent = TraceContext.from_traceparent(self.headers.get("traceparent"))
        fault_ratio = parse_fault_ratio(self.headers.get(FAULT_RATIO_HEADER))
        latency_ms = parse_latency_ms(self.headers.get(LATENCY_HEADER))

        started = time.monotonic()
        status = 500
        body: dict[str, object] = {"error": "internal"}
        with telemetry.span(
            f"{method} {route}",
            kind="SERVER",
            parent=parent,
            attributes={
                "http.request.method": method,
                "http.route": route,
                "url.path": self.path,
            },
        ) as span:
            if latency_ms:
                span.set_attribute("demo.injected_latency_ms", latency_ms)
                time.sleep(latency_ms / 1000.0)
            if should_fault(fault_ratio, random.random()):
                status, body = 500, {"error": "injected fault"}
                span.set_status(False, "injected fault")
                span.set_attribute("demo.fault_injected", True)
                telemetry.log(
                    "ERROR",
                    f"injected fault on {method} {route}",
                    {
                        "http.route": route,
                        "http.response.status_code": status,
                        "demo.fault_ratio": fault_ratio,
                    },
                    trace=span.context,
                )
            else:
                status, body = self._dispatch(method, route, span)
                telemetry.log(
                    "INFO",
                    f"{method} {route} -> {status}",
                    {
                        "http.route": route,
                        "http.response.status_code": status,
                    },
                    trace=span.context,
                )
            span.set_attribute("http.response.status_code", status)

        duration_ms = (time.monotonic() - started) * 1000.0
        telemetry.counter(
            "demo.http.requests",
            1,
            {
                "http.route": route,
                "http.request.method": method,
                "http.response.status_code": status,
            },
        )
        telemetry.histogram(
            "demo.http.server.duration", duration_ms, {"http.route": route}
        )
        # Gauge-style queue depth as a histogram observation, so the
        # dashboards can graph the latest depth per interval.
        telemetry.histogram("demo.queue.depth", float(self.state.depth()), {})
        self._respond(status, body)

    def _dispatch(
        self, method: str, route: str, span: SpanHandle
    ) -> tuple[int, dict[str, object]]:
        if route == "/api/status" and method == "GET":
            return 200, {"service": "demo-http-api", **self.state.stats()}
        if route == "/api/orders" and method == "POST":
            return self._create_order(span)
        if route == "/api/orders" and method == "GET":
            return self._list_orders(span)
        if route == "/api/queue" and method == "GET":
            items = self.state.poll(_QUEUE_POLL_BATCH)
            return 200, {"items": items}
        if route == "/api/queue" and method == "POST":
            payload = self._read_json()
            raw_ids = payload.get("ack", [])
            item_ids = [str(i) for i in raw_ids] if isinstance(
                raw_ids, list
            ) else []
            return 200, {"acked": self.state.ack(item_ids)}
        return 404, {"error": f"no route {method} {route}"}

    def _create_order(
        self, span: SpanHandle
    ) -> tuple[int, dict[str, object]]:
        payload = self._read_json()
        order = {
            "item": str(payload.get("item", "widget")),
            "quantity": int(payload.get("quantity", 1) or 1),
        }
        status, response = self._call_datastore(
            "POST", "/orders", order, span
        )
        if status != 201:
            return 502, {"error": "datastore unavailable", "detail": response}
        queued = self.state.enqueue(
            response.get("order_id"), span.context.traceparent()
        )
        return 201, {
            "order_id": response.get("order_id"),
            "queued_item": queued["item_id"],
        }

    def _list_orders(self, span: SpanHandle) -> tuple[int, dict[str, object]]:
        status, response = self._call_datastore("GET", "/orders", None, span)
        if status != 200:
            return 502, {"error": "datastore unavailable", "detail": response}
        return 200, response

    def _call_datastore(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        parent_span: SpanHandle,
    ) -> tuple[int, dict[str, object]]:
        """HTTP call to the datastore service under a CLIENT span,
        propagating traceparent onward."""
        telemetry = self.telemetry
        url = self.datastore_url.rstrip("/") + path
        with telemetry.span(
            f"{method} {path}",
            kind="CLIENT",
            parent=parent_span.context,
            attributes={
                "http.request.method": method,
                "url.full": url,
                "peer.service": "demo-datastore",
            },
        ) as span:
            data = (
                json.dumps(payload).encode("utf-8")
                if payload is not None
                else None
            )
            request = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "traceparent": span.context.traceparent(),
                },
                method=method,
            )
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    status = response.status
                    body = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                body = {"error": str(exc)}
                span.set_status(False, f"datastore returned {exc.code}")
            except (urllib.error.URLError, OSError, ValueError) as exc:
                status = 0
                body = {"error": str(exc)}
                span.set_status(False, f"datastore call failed: {exc}")
            span.set_attribute("http.response.status_code", status)
            return status, body

    # ------------------------------------------------------------------

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        try:
            parsed = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _respond(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def build_server(
    telemetry: Telemetry,
    state: QueueState,
    datastore_url: str,
    port: int,
) -> ThreadingHTTPServer:
    """Assemble a configured server; port 0 gives tests an ephemeral
    port with the exact production handler wiring."""
    handler = type(
        "ConfiguredDemoApiHandler",
        (DemoApiHandler,),
        {
            "telemetry": telemetry,
            "state": state,
            "datastore_url": datastore_url,
        },
    )
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def main() -> None:
    telemetry = Telemetry("demo-http-api")
    state = QueueState()
    datastore_url = os.environ.get(
        "DEMO_DATASTORE_URL", "http://demo-datastore:8081"
    )
    port = int(os.environ.get("DEMO_HTTP_PORT", "8080"))
    server = build_server(telemetry, state, datastore_url, port)
    telemetry.log(
        "INFO",
        f"demo-http-api listening on :{port}",
        {"demo.datastore_url": datastore_url},
    )
    telemetry.flush()
    try:
        server.serve_forever()
    finally:
        telemetry.flush()


if __name__ == "__main__":
    main()
