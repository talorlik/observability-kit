"""Demo scheduled job (Batch 27, ADR-0011).

A run-to-completion batch deployed as a CronJob. Each run starts a new
root trace, checks the HTTP API's status and order list under CLIENT
spans, emits a run counter and a summary INFO log, and exits 0 - the
CronJob cadence itself is the signal, so a degraded run is telemetry,
not a pod failure.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request

from demosvc.otel import SpanHandle, Telemetry

_DEFAULT_API_URL = "http://demo-http-api:8080"

_CHECKS = ("/api/status", "/api/orders")


def _check(
    telemetry: Telemetry, api_url: str, path: str, root: SpanHandle
) -> bool:
    """One GET check as a CLIENT span child of the run's root span."""
    url = api_url.rstrip("/") + path
    with telemetry.span(
        f"GET {path}",
        kind="CLIENT",
        parent=root.context,
        attributes={
            "http.request.method": "GET",
            "url.full": url,
            "peer.service": "demo-http-api",
        },
    ) as span:
        request = urllib.request.Request(
            url,
            headers={"traceparent": span.context.traceparent()},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                span.set_attribute(
                    "http.response.status_code", response.status
                )
                json.loads(response.read().decode("utf-8"))
                return 200 <= response.status < 300
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            OSError,
            ValueError,
        ) as exc:
            span.set_status(False, f"check failed: {exc}")
            telemetry.log(
                "ERROR",
                f"scheduled check {path} failed: {exc}",
                {"job.check": path},
                trace=span.context,
            )
            return False


def run(telemetry: Telemetry, api_url: str) -> str:
    """Execute one job run; returns the outcome label."""
    started = time.monotonic()
    passed = 0
    with telemetry.span(
        "demo.job.run",
        kind="INTERNAL",
        attributes={"job.name": "demo-scheduled-job"},
    ) as root:
        for path in _CHECKS:
            if _check(telemetry, api_url, path, root):
                passed += 1
        outcome = "ok" if passed == len(_CHECKS) else "degraded"
        root.set_attribute("job.outcome", outcome)
        if outcome != "ok":
            root.set_status(False, "one or more checks failed")
        duration_ms = (time.monotonic() - started) * 1000.0
        telemetry.counter("demo.job.runs", 1, {"job.outcome": outcome})
        telemetry.log(
            "INFO",
            f"demo-scheduled-job run complete: {passed}/{len(_CHECKS)} "
            f"checks passed in {duration_ms:.0f}ms",
            {"job.outcome": outcome, "job.checks_passed": passed},
            trace=root.context,
        )
    return outcome


def main() -> None:
    telemetry = Telemetry("demo-scheduled-job")
    api_url = os.environ.get("DEMO_HTTP_API_URL", _DEFAULT_API_URL)
    run(telemetry, api_url)
    telemetry.flush()
    # Always exit 0: a degraded run is demo telemetry for the risk and
    # RCA surfaces, not a CronJob failure to page on.
    sys.exit(0)


if __name__ == "__main__":
    main()
