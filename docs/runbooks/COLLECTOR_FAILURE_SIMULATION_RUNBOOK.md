# Collector Failure Simulation Runbook

## Purpose

Validate bounded-loss behavior for collector gateway restarts and backend
outage scenarios.

## Scenarios

- Gateway rolling restart while sustained telemetry load is active.
- Temporary backend unavailability with retry and queue drain recovery.

## Checks

- Queue depth increases and then drains to baseline.
- Dropped telemetry remains within accepted bounded-loss threshold.
- Export retry metrics return to normal after recovery.
