# Batch 9 Incident Drill Timeline

> [!NOTE]
> This is tabletop-drill evidence (a rehearsal record) for Batch 9 Task 5.
> It documents a simulated incident response exercise in a non-production
> environment. It is not production incident data.

## Drill Summary

| Field | Value |
| --- | --- |
| Scenario | checkout-api latency regression with elevated error budget burn |
| Environment | non-production |
| Drill status | pass |
| Response timeline | 37 minutes (detection to resolution) |
| Evaluated at | 2026-04-07T00:00:00Z |

## Participants

- Incident commander: platform-observability on-call engineer
- Responder: service-checkout on-call engineer
- Observer / scribe: SLO operations reviewer (recorded this timeline)

## Timeline

All timestamps are drill-relative offsets from T+0 (alert fired). The
drill completed within the recorded 37-minute response window.

| Offset | Phase | Event |
| --- | --- | --- |
| T+0m | Detect | Latency SLO burn-rate alert fired for checkout-api |
| T+2m | Detect | Alert routed to platform-observability on-call |
| T+5m | Triage | Incident commander acknowledged and opened drill channel |
| T+9m | Triage | Dashboards confirmed p99 latency regression and burn |
| T+14m | Diagnose | Traces isolated slow dependent payment call path |
| T+19m | Diagnose | Collector drop-rate warning observed flapping (noise) |
| T+24m | Mitigate | Simulated rollback of checkout-api config initiated |
| T+31m | Verify | Latency and burn-rate panels returned to baseline |
| T+37m | Resolve | Incident commander declared drill resolved |

## Response Phases

- Detection (T+0m to T+5m): alerting and routing worked as configured;
  the on-call engineer was paged and acknowledged within the target.
- Triage and diagnosis (T+5m to T+24m): dashboards and traces were
  sufficient to localize the regression to the dependent payment call.
- Mitigation and verification (T+24m to T+37m): simulated rollback and
  dashboard verification closed the loop inside the 37-minute window.

## Outcome

The drill passed. Two follow-up actions were recorded in
`follow-up-actions.json` (collector drop-rate warning threshold flapping,
timeout budget for the dependent payment call). Alert routing events are
recorded in `alert-routing-log.json`, and dashboard evidence captured
during a live drill run is stored under `dashboard-snapshots/`.
