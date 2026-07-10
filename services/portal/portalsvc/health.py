"""Platform health summary over the TR-12 meta-monitoring signals.

The portal's health view summarizes the three TR-12 signal families
as a per-plane status grid with a worst-of overall rollup:

- collector health: export queue depth, dropped telemetry, and
  retry-failure signals of the OpenTelemetry collector tier;
- backend health: ingest errors/lag and storage pressure of the
  OpenSearch telemetry store;
- install-discovery engine health: preflight failure rate, discovery
  completeness, and generation-apply success of the install and
  discovery engine.

The summary is computed from a typed snapshot input: the deployment
provides the live feed (a mapping shaped like the fixture JSON the
offline tests use); the portal itself scrapes nothing and stores
nothing. A missing or unrecognized reading degrades to `unknown`
rather than failing the view - the health page must stay up when the
meta-monitoring feed is not (its absence IS the signal).
"""

from __future__ import annotations

from typing import Any, Mapping

from portalsvc.models import (
    HealthSignal,
    HealthStatus,
    HealthSummary,
    PlaneHealth,
)

# Signal families per plane (TR-12). Keys are the snapshot's plane
# and signal identifiers; the portal reads exactly these and nothing
# more.
SIGNAL_FAMILIES: Mapping[str, tuple[str, ...]] = {
    "collector": (
        "queue_depth",
        "dropped_telemetry",
        "retry_failure",
    ),
    "backend": (
        "ingest_errors_lag",
        "storage_pressure",
    ),
    "install_discovery": (
        "preflight_failure_rate",
        "discovery_completeness",
        "generation_apply_success",
    ),
}

# Worst-of ordering: degraded dominates, unknown dominates ok. An
# unknown plane is worse than a healthy one (missing meta-monitoring
# is itself a finding) but never masks a known degradation.
_SEVERITY: Mapping[HealthStatus, int] = {
    HealthStatus.OK: 0,
    HealthStatus.UNKNOWN: 1,
    HealthStatus.DEGRADED: 2,
}


def worst_of(statuses: tuple[HealthStatus, ...]) -> HealthStatus:
    """Worst-of rollup; an empty input is unknown by definition."""
    if not statuses:
        return HealthStatus.UNKNOWN
    return max(statuses, key=lambda status: _SEVERITY[status])


def _signal_from(
    plane_snapshot: Mapping[str, Any], name: str
) -> HealthSignal:
    reading = plane_snapshot.get(name)
    if reading is None:
        return HealthSignal(
            name=name,
            status=HealthStatus.UNKNOWN,
            detail="no reading in snapshot",
        )
    if isinstance(reading, str):
        raw_status: Any = reading
        detail: str | None = None
    elif isinstance(reading, Mapping):
        raw_status = reading.get("status")
        raw_detail = reading.get("detail")
        detail = str(raw_detail) if raw_detail is not None else None
    else:
        return HealthSignal(
            name=name,
            status=HealthStatus.UNKNOWN,
            detail=f"unreadable reading of type "
            f"{type(reading).__name__}",
        )
    try:
        status = HealthStatus(raw_status)
    except ValueError:
        return HealthSignal(
            name=name,
            status=HealthStatus.UNKNOWN,
            detail=f"unrecognized status {raw_status!r}",
        )
    return HealthSignal(name=name, status=status, detail=detail)


def summarize_health(
    snapshot: Mapping[str, Any]
) -> HealthSummary:
    """Roll a snapshot up into the per-plane health summary.

    Every contracted plane and signal appears in the result exactly
    once, regardless of what the snapshot carries; extra snapshot
    keys are ignored (the portal reads only the TR-12 families).
    """
    planes: list[PlaneHealth] = []
    for plane, signal_names in SIGNAL_FAMILIES.items():
        raw = snapshot.get(plane)
        plane_snapshot: Mapping[str, Any] = (
            raw if isinstance(raw, Mapping) else {}
        )
        signals = tuple(
            _signal_from(plane_snapshot, name)
            for name in signal_names
        )
        planes.append(
            PlaneHealth(
                plane=plane,
                status=worst_of(
                    tuple(signal.status for signal in signals)
                ),
                signals=signals,
            )
        )
    return HealthSummary(
        overall=worst_of(
            tuple(plane.status for plane in planes)
        ),
        planes=tuple(planes),
    )
