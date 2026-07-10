"""Declarative scenario-driven load generator for the demo package.

Executes one scenario document conforming to
``contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json`` (ADR-0011 decision 3):
steady baseline, burst, error-injection, or latency-injection. Fault
injection reaches the demo HTTP API exclusively through the
``x-demo-fault-ratio`` and ``x-demo-latency-ms`` request headers derived
from the scenario's ``fault`` block; the load generator itself never
fabricates failures.

The module is import-safe without ``demosvc.otel``: ``validate_scenario``
and the scenario dataclasses have no telemetry dependency, so the offline
test suite can exercise validation while the emitter is built in
parallel. ``main()`` imports the emitter lazily.
"""

from __future__ import annotations

import json
import os
import random
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_SCENARIO = "steady-baseline"
DEFAULT_SCENARIO_DIR = "/etc/demo/scenarios"
DEFAULT_BASE_URL_ENV = "DEMO_TARGET_BASE_URL"
DEFAULT_BASE_URL = "http://demo-http-api:8080"

# Interval between periodic INFO heartbeat logs, in seconds.
LOG_INTERVAL_SECONDS = 30.0
REQUEST_TIMEOUT_SECONDS = 10.0

SCENARIO_KINDS = (
    "steady-baseline",
    "burst",
    "error-injection",
    "latency-injection",
)
FAULT_KINDS = ("error-injection", "latency-injection")
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _is_number(value: object) -> bool:
    """True for int/float but not bool (bool is an int subclass)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: object) -> bool:
    """True for int but not bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_keys(
    obj: dict[str, Any], allowed: set[str], where: str, errors: list[str]
) -> None:
    """Reject unknown keys, mirroring additionalProperties: false."""
    for key in sorted(set(obj) - allowed):
        errors.append(f"{where}: unknown field '{key}' is not allowed")


def _validate_target(target: object, errors: list[str]) -> None:
    if not isinstance(target, dict):
        errors.append("target: must be an object")
        return
    _check_keys(target, {"base_url_env", "route", "method"}, "target", errors)
    route = target.get("route")
    if not isinstance(route, str) or not route.startswith("/"):
        errors.append("target.route: required string starting with '/'")
    method = target.get("method")
    if method not in HTTP_METHODS:
        errors.append(
            "target.method: required, one of " + ", ".join(HTTP_METHODS)
        )
    base_url_env = target.get("base_url_env")
    if base_url_env is not None and (
        not isinstance(base_url_env, str)
        or not _ENV_NAME_RE.match(base_url_env)
    ):
        errors.append(
            "target.base_url_env: must be an UPPERCASE environment "
            "variable name"
        )


def _validate_load(load: object, errors: list[str]) -> None:
    if not isinstance(load, dict):
        errors.append("load: must be an object")
        return
    _check_keys(
        load,
        {"requests_per_second", "concurrency", "duration_seconds"},
        "load",
        errors,
    )
    rps = load.get("requests_per_second")
    if not _is_number(rps) or rps <= 0:
        errors.append(
            "load.requests_per_second: required number strictly "
            "greater than 0"
        )
    concurrency = load.get("concurrency")
    if not _is_int(concurrency) or concurrency < 1:
        errors.append("load.concurrency: required integer >= 1")
    duration = load.get("duration_seconds")
    if not _is_int(duration) or duration < 0:
        errors.append(
            "load.duration_seconds: required integer >= 0 "
            "(0 means run forever)"
        )


def _validate_burst(doc: dict[str, Any], errors: list[str]) -> None:
    kind = doc.get("kind")
    burst = doc.get("burst")
    if kind != "burst":
        if burst is not None:
            errors.append(
                f"burst: only allowed for kind 'burst', not '{kind}'"
            )
        return
    if not isinstance(burst, dict):
        errors.append("burst: required object for kind 'burst'")
        return
    _check_keys(
        burst,
        {"interval_seconds", "burst_seconds", "burst_multiplier"},
        "burst",
        errors,
    )
    interval = burst.get("interval_seconds")
    if not _is_int(interval) or interval < 1:
        errors.append("burst.interval_seconds: required integer >= 1")
    window = burst.get("burst_seconds")
    if not _is_int(window) or window < 1:
        errors.append("burst.burst_seconds: required integer >= 1")
    multiplier = burst.get("burst_multiplier")
    if not _is_number(multiplier) or multiplier <= 1:
        errors.append(
            "burst.burst_multiplier: required number strictly "
            "greater than 1"
        )


def _validate_fault(doc: dict[str, Any], errors: list[str]) -> None:
    kind = doc.get("kind")
    fault = doc.get("fault")
    if kind not in FAULT_KINDS:
        if fault is not None:
            errors.append(
                "fault: only allowed for error-injection and "
                f"latency-injection kinds, not '{kind}'"
            )
        return
    if not isinstance(fault, dict):
        errors.append(f"fault: required object for kind '{kind}'")
        return
    _check_keys(fault, {"error_ratio", "latency_ms"}, "fault", errors)
    if kind == "error-injection":
        ratio = fault.get("error_ratio")
        if not _is_number(ratio) or not 0 < ratio <= 1:
            errors.append(
                "fault.error_ratio: required number in (0, 1] for "
                "kind 'error-injection'"
            )
        if "latency_ms" in fault:
            errors.append(
                "fault.latency_ms: not allowed for kind 'error-injection'"
            )
    else:
        latency = fault.get("latency_ms")
        if not _is_int(latency) or latency < 1:
            errors.append(
                "fault.latency_ms: required integer >= 1 for kind "
                "'latency-injection'"
            )
        if "error_ratio" in fault:
            errors.append(
                "fault.error_ratio: not allowed for kind "
                "'latency-injection'"
            )


def _validate_expectations(doc: dict[str, Any], errors: list[str]) -> None:
    kind = doc.get("kind")
    expectations = doc.get("expectations")
    if kind not in FAULT_KINDS:
        if expectations is not None:
            errors.append(
                "expectations: only allowed for error-injection and "
                f"latency-injection kinds, not '{kind}'"
            )
        return
    if not isinstance(expectations, dict):
        errors.append(f"expectations: required object for kind '{kind}'")
        return
    _check_keys(
        expectations, {"dashboards", "ai_surfaces"}, "expectations", errors
    )
    for key in ("dashboards", "ai_surfaces"):
        value = expectations.get(key)
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(item, str) and item for item in value)
        ):
            errors.append(
                f"expectations.{key}: required non-empty array of "
                "non-empty strings"
            )


def validate_scenario(doc: dict) -> list[str]:
    """Validate a scenario document against the V1 scenario contract.

    Hand-rolled mirror of contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json
    (the jsonschema library is not available: the demo image and the
    offline test suite are stdlib-only by ADR-0011). Returns
    human-readable error strings; an empty list means the document is
    valid.
    """
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["scenario document must be a JSON object"]

    allowed = {
        "schema_version",
        "name",
        "kind",
        "description",
        "target",
        "load",
        "burst",
        "fault",
        "expectations",
    }
    _check_keys(doc, allowed, "scenario", errors)

    if doc.get("schema_version") != "v1":
        errors.append("schema_version: required, must be the string 'v1'")
    name = doc.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        errors.append(
            "name: required string matching ^[a-z0-9][a-z0-9-]*$"
        )
    kind = doc.get("kind")
    if kind not in SCENARIO_KINDS:
        errors.append("kind: required, one of " + ", ".join(SCENARIO_KINDS))
    description = doc.get("description")
    if not isinstance(description, str) or len(description) < 10:
        errors.append(
            "description: required string of at least 10 characters"
        )

    if "target" not in doc:
        errors.append("target: required object")
    else:
        _validate_target(doc["target"], errors)
    if "load" not in doc:
        errors.append("load: required object")
    else:
        _validate_load(doc["load"], errors)

    # Kind-conditional blocks only make sense once the kind is known;
    # an unknown kind already produced an error above.
    if kind in SCENARIO_KINDS:
        _validate_burst(doc, errors)
        _validate_fault(doc, errors)
        _validate_expectations(doc, errors)
    return errors


@dataclass(frozen=True)
class Target:
    """Resolved request target."""

    base_url: str
    route: str
    method: str

    @property
    def url(self) -> str:
        return self.base_url.rstrip("/") + self.route


@dataclass(frozen=True)
class Burst:
    """Burst cycle parameters for kind 'burst'."""

    interval_seconds: int
    burst_seconds: int
    burst_multiplier: float


@dataclass(frozen=True)
class Scenario:
    """A validated, resolved scenario ready to execute."""

    name: str
    kind: str
    target: Target
    requests_per_second: float
    concurrency: int
    duration_seconds: int
    burst: Burst | None = None
    fault_headers: dict[str, str] = field(default_factory=dict)

    def rate_at(self, elapsed: float) -> float:
        """Current target rate, honoring the burst window when present."""
        if self.burst is None:
            return self.requests_per_second
        in_burst = (
            elapsed % self.burst.interval_seconds
        ) < self.burst.burst_seconds
        if in_burst:
            return self.requests_per_second * self.burst.burst_multiplier
        return self.requests_per_second


def _build_scenario(doc: dict[str, Any]) -> Scenario:
    """Turn a validated document into a resolved Scenario."""
    target_doc: dict[str, Any] = doc["target"]
    base_url_env = target_doc.get("base_url_env", DEFAULT_BASE_URL_ENV)
    base_url = os.environ.get(base_url_env, DEFAULT_BASE_URL)
    load_doc: dict[str, Any] = doc["load"]

    burst: Burst | None = None
    if doc["kind"] == "burst":
        burst_doc: dict[str, Any] = doc["burst"]
        burst = Burst(
            interval_seconds=burst_doc["interval_seconds"],
            burst_seconds=burst_doc["burst_seconds"],
            burst_multiplier=float(burst_doc["burst_multiplier"]),
        )

    # Fault injection travels only as request headers honored by the
    # demo HTTP API; the generator never synthesizes failures itself.
    fault_headers: dict[str, str] = {}
    fault_doc = doc.get("fault") or {}
    if "error_ratio" in fault_doc:
        fault_headers["x-demo-fault-ratio"] = str(fault_doc["error_ratio"])
    if "latency_ms" in fault_doc:
        fault_headers["x-demo-latency-ms"] = str(fault_doc["latency_ms"])

    return Scenario(
        name=doc["name"],
        kind=doc["kind"],
        target=Target(
            base_url=base_url,
            route=target_doc["route"],
            method=target_doc["method"],
        ),
        requests_per_second=float(load_doc["requests_per_second"]),
        concurrency=load_doc["concurrency"],
        duration_seconds=load_doc["duration_seconds"],
        burst=burst,
        fault_headers=fault_headers,
    )


def load_scenario_document(name: str, directory: str) -> dict[str, Any]:
    """Read a scenario document from the mounted scenarios directory."""
    path = os.path.join(directory, f"{name}.json")
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return doc


def _issue_request(
    telemetry: Any, scenario: Scenario, stats: dict[str, int]
) -> None:
    """Send one request under a fresh root CLIENT span; never raises."""
    started = time.monotonic()
    attributes: dict[str, object] = {
        "demo.scenario": scenario.name,
        "demo.scenario.kind": scenario.kind,
        "http.request.method": scenario.target.method,
        "url.full": scenario.target.url,
    }
    with telemetry.span(
        "demo.loadgen.request", kind="CLIENT", attributes=attributes
    ) as span:
        headers = {"traceparent": span.context.traceparent()}
        headers.update(scenario.fault_headers)
        outcome = "success"
        try:
            request = urllib.request.Request(
                scenario.target.url,
                headers=headers,
                method=scenario.target.method,
            )
            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            # 4xx/5xx are expected under fault injection; record and
            # continue.
            status = exc.code
        except Exception as exc:  # noqa: BLE001 - loop must never crash
            status = 0
            outcome = "error"
            span.set_status(False, f"{type(exc).__name__}: {exc}")
        if status:
            span.set_attribute("http.response.status_code", status)
            if status >= 500:
                outcome = "server_error"
                span.set_status(False, f"HTTP {status}")
            else:
                span.set_status(True)

    elapsed_ms = (time.monotonic() - started) * 1000.0
    metric_attributes: dict[str, object] = {
        "demo.scenario": scenario.name,
        "demo.outcome": outcome,
        "http.response.status_code": status,
    }
    try:
        telemetry.counter(
            "demo.loadgen.requests", 1.0, attributes=metric_attributes
        )
        telemetry.histogram(
            "demo.loadgen.duration", elapsed_ms, attributes=metric_attributes
        )
    except Exception:  # noqa: BLE001 - telemetry must never crash the loop
        pass
    stats["total"] += 1
    if outcome != "success":
        stats["failed"] += 1


def _worker(
    telemetry: Any,
    scenario: Scenario,
    stop: threading.Event,
    started_at: float,
    stats: dict[str, int],
) -> None:
    """Drive requests at the per-worker share of the scenario rate."""
    # Jitter the start so concurrent workers do not fire in lockstep.
    if not stop.wait(random.uniform(0, 1.0 / scenario.requests_per_second)):
        while not stop.is_set():
            _issue_request(telemetry, scenario, stats)
            rate = scenario.rate_at(time.monotonic() - started_at)
            interval = scenario.concurrency / rate
            if stop.wait(interval):
                break


def run(scenario: Scenario, telemetry: Any) -> int:
    """Execute the scenario until its duration elapses or SIGTERM."""
    stop = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        telemetry.log(
            "INFO",
            f"signal {signum} received, stopping scenario {scenario.name}",
            attributes={"demo.scenario": scenario.name},
        )
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    started_at = time.monotonic()
    stats: dict[str, int] = {"total": 0, "failed": 0}
    threads = [
        threading.Thread(
            target=_worker,
            args=(telemetry, scenario, stop, started_at, stats),
            daemon=True,
            name=f"loadgen-{index}",
        )
        for index in range(scenario.concurrency)
    ]
    for thread in threads:
        thread.start()

    telemetry.log(
        "INFO",
        f"scenario {scenario.name} started",
        attributes={
            "demo.scenario": scenario.name,
            "demo.scenario.kind": scenario.kind,
            "demo.target.url": scenario.target.url,
            "demo.load.requests_per_second": scenario.requests_per_second,
            "demo.load.concurrency": scenario.concurrency,
            "demo.load.duration_seconds": scenario.duration_seconds,
        },
    )

    deadline = (
        started_at + scenario.duration_seconds
        if scenario.duration_seconds > 0
        else None
    )
    while not stop.is_set():
        if deadline is not None and time.monotonic() >= deadline:
            stop.set()
            break
        stop.wait(
            min(
                LOG_INTERVAL_SECONDS,
                max(deadline - time.monotonic(), 0.1)
                if deadline is not None
                else LOG_INTERVAL_SECONDS,
            )
        )
        telemetry.log(
            "INFO",
            f"scenario {scenario.name} running: "
            f"{stats['total']} requests, {stats['failed']} failed",
            attributes={
                "demo.scenario": scenario.name,
                "demo.requests.total": stats["total"],
                "demo.requests.failed": stats["failed"],
            },
        )
        try:
            telemetry.flush()
        except Exception:  # noqa: BLE001 - flush failures are non-fatal
            pass

    for thread in threads:
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS + 5.0)
    telemetry.log(
        "INFO",
        f"scenario {scenario.name} finished: "
        f"{stats['total']} requests, {stats['failed']} failed",
        attributes={"demo.scenario": scenario.name},
    )
    telemetry.flush()
    return 0


def _import_telemetry() -> Any:
    """Import the OTLP emitter lazily.

    Deferred so that validate_scenario stays importable without
    demosvc.otel (the emitter is owned by the sample-services task and
    the offline validator only needs validation).
    """
    try:
        from demosvc.otel import Telemetry
    except ImportError:
        from otel import Telemetry  # type: ignore[no-redef]
    return Telemetry


def main() -> int:
    """Entry point for the ``loadgen`` container arg."""
    scenario_name = os.environ.get("DEMO_SCENARIO", DEFAULT_SCENARIO)
    scenario_dir = os.environ.get("DEMO_SCENARIO_DIR", DEFAULT_SCENARIO_DIR)

    try:
        doc = load_scenario_document(scenario_name, scenario_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"loadgen: cannot load scenario '{scenario_name}' from "
            f"{scenario_dir}: {exc}",
            file=sys.stderr,
        )
        return 1

    errors = validate_scenario(doc)
    if errors:
        print(
            f"loadgen: scenario '{scenario_name}' failed validation "
            "against DEMO_SCENARIO_SCHEMA_V1:",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    telemetry_cls = _import_telemetry()
    telemetry = telemetry_cls("demo-loadgen")
    return run(_build_scenario(doc), telemetry)


if __name__ == "__main__":
    sys.exit(main())
