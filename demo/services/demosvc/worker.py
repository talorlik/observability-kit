"""Demo asynchronous worker (Batch 27, ADR-0011).

Polls the HTTP API's work queue over HTTP, processes each item with
simulated jittered work, and acknowledges the batch. Each queue item
carries the traceparent of the request that enqueued it, so the
processing span (CONSUMER) continues the producer's trace and the
cross-service demo traces read end to end in the trace views.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request

from demosvc.otel import Telemetry, TraceContext

_DEFAULT_API_URL = "http://demo-http-api:8080"

# Simulated per-item work: base plus uniform jitter, in seconds.
_WORK_BASE_SECONDS = 0.05
_WORK_JITTER_SECONDS = 0.20


def _api_request(
    telemetry: Telemetry,
    api_url: str,
    method: str,
    path: str,
    payload: dict[str, object] | None,
    parent: TraceContext | None,
) -> dict[str, object]:
    """One HTTP call to the demo API under a CLIENT span. Raises on
    transport errors; callers convert that into telemetry."""
    url = api_url.rstrip("/") + path
    with telemetry.span(
        f"{method} {path}",
        kind="CLIENT",
        parent=parent,
        attributes={
            "http.request.method": method,
            "url.full": url,
            "peer.service": "demo-http-api",
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
        with urllib.request.urlopen(request, timeout=5) as response:
            span.set_attribute("http.response.status_code", response.status)
            return json.loads(response.read().decode("utf-8"))


def process_item(telemetry: Telemetry, item: dict[str, object]) -> None:
    """Process one queue item under a CONSUMER span that continues the
    trace stored with the item."""
    parent = TraceContext.from_traceparent(
        str(item.get("traceparent") or "") or None
    )
    started = time.monotonic()
    with telemetry.span(
        "demo.worker.process",
        kind="CONSUMER",
        parent=parent,
        attributes={
            "demo.queue.item_id": str(item.get("item_id")),
            "demo.order_id": str(item.get("order_id")),
        },
    ) as span:
        # Simulated work with jitter, so worker duration histograms
        # show a realistic spread on the dashboards.
        time.sleep(_WORK_BASE_SECONDS + random.random() * _WORK_JITTER_SECONDS)
        duration_ms = (time.monotonic() - started) * 1000.0
        telemetry.counter(
            "demo.worker.processed", 1, {"worker.outcome": "ok"}
        )
        telemetry.histogram("demo.worker.duration", duration_ms, {})
        telemetry.log(
            "INFO",
            f"processed queue item {item.get('item_id')}",
            {"demo.queue.item_id": str(item.get("item_id"))},
            trace=span.context,
        )


def run_once(telemetry: Telemetry, api_url: str) -> int:
    """One poll-process-ack cycle. Returns the number of processed
    items; transport failures are recorded and counted as zero."""
    try:
        response = _api_request(
            telemetry, api_url, "GET", "/api/queue", None, None
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        telemetry.counter(
            "demo.worker.processed", 0, {"worker.outcome": "poll-error"}
        )
        telemetry.log(
            "ERROR", f"queue poll failed: {exc}", {"worker.phase": "poll"}
        )
        return 0

    raw_items = response.get("items", [])
    items = [item for item in raw_items if isinstance(item, dict)] if (
        isinstance(raw_items, list)
    ) else []
    for item in items:
        process_item(telemetry, item)

    if items:
        item_ids = [str(item.get("item_id")) for item in items]
        try:
            _api_request(
                telemetry,
                api_url,
                "POST",
                "/api/queue",
                {"ack": item_ids},
                None,
            )
        except (urllib.error.URLError, OSError, ValueError) as exc:
            telemetry.log(
                "ERROR", f"queue ack failed: {exc}", {"worker.phase": "ack"}
            )
    return len(items)


def main() -> None:
    telemetry = Telemetry("demo-worker")
    api_url = os.environ.get("DEMO_HTTP_API_URL", _DEFAULT_API_URL)
    poll_seconds = float(os.environ.get("DEMO_WORKER_POLL_SECONDS", "5"))
    telemetry.log(
        "INFO",
        "demo-worker started",
        {"demo.api_url": api_url, "demo.poll_seconds": poll_seconds},
    )
    telemetry.flush()
    while True:
        processed = run_once(telemetry, api_url)
        telemetry.flush()
        # Busy queues are drained without waiting a full interval.
        if processed == 0:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
