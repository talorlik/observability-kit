# Batch 9 Drill Dashboard Snapshots

> [!NOTE]
> This directory is tabletop-drill evidence (a rehearsal record) for
> Batch 9 Task 5. It holds dashboard snapshots captured during incident
> drill runs, not production incident data.

## Purpose

During a live run of the Batch 9 incident drill (checkout-api latency
regression with elevated error budget burn, non-production), the scribe
captures dashboard snapshots at key phases and stores them here as
evidence alongside `../INCIDENT_TIMELINE.md`.

## Snapshots Captured During a Live Drill

- Detection: SLO burn-rate panel showing the fired
  checkout-api-latency-slo-burn-rate alert at drill offset T+0m.
- Triage: checkout-api p99 latency panel confirming the regression
  (around T+9m).
- Diagnosis: trace view isolating the slow dependent payment call
  (around T+14m).
- Verification: latency and burn-rate panels returned to baseline after
  the simulated rollback (around T+31m).

## Conventions

- Name files `<offset>-<phase>-<panel>.png`, for example
  `t09m-triage-checkout-p99-latency.png`.
- Snapshots come from the non-production drill environment only. Never
  place production incident screenshots in this directory.
- This tabletop iteration of the drill recorded its evidence textually
  in `../INCIDENT_TIMELINE.md`; image snapshots are added when the drill
  is executed against a live non-production deployment.
