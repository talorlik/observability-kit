# Batch Command Sheet

Use these commands to control delivery pace with the agent. Run one batch at a
time and require validation before moving forward.

All batches should be judged against the same end-state objective described in
the plan and PRD: cloud-agnostic Kubernetes deployment, open-source-first
components, guided install and discovery, provider-adapter extensibility, and
phased delivery toward optional assisted RCA.

## Batch Commands

| Batch | Command To Send | Validation Step (Required) |
| ---- | ---- | ---- |
| 1 | `Do batch 1: delivery foundation.` | Validate install contract schema samples, GitOps structure, CI checks, secret scanning, and baseline runbooks. |
| 2 | `Do batch 2: compatibility and modes.` | Validate compatibility matrix coverage, profile catalogs, grading outputs, mode decision table behavior, and remediation mappings. |
| 3 | `Do batch 3: preflight and discovery engine.` | Validate preflight pass or fail reporting, discovery probes, generated capability and compatibility outputs, and readiness report scaffold emission. |
| 4 | `Do batch 4: collector core topology.` | Validate agent and gateway health, required processors, OTLP export behavior in attach and standalone tests, and failure simulation evidence. |
| 5 | `Do batch 5: logs pipeline.` | Validate CRI and JSON parsing, multiline grouping, sensitive field redaction, `logs-*` template rules, and trace correlation behavior. |
| 6 | `Do batch 6: metrics and traces pipelines.` | Validate infrastructure and app metrics ingestion, scrape onboarding, OTLP ingest, cardinality guardrails, sampling policy behavior, and correlation pivots. |
| 7 | `Do batch 7: onboarding and subscription model.` | Validate one-block onboarding flow, passive and low-touch and instrumentation modes, metadata policy checks, CI schema checks, and onboarding lead-time measurement. |
| 8 | `Do batch 8: security, isolation, and resilience.` | Validate team and environment isolation, encryption controls, audit logs, backup and restore drills, rollback drills, and hardening checklist completion. |
| 9 | `Do batch 9: operator experience and SLO operations.` | Validate dashboard taxonomy, platform health alerts, SLI and SLO query stability, burn-rate and symptom alerts, drill evidence, and alert-noise reduction tracking. |
| 9A | `Do batch 9A: visualization and admin access plane.` | Validate signal-to-UI ownership publication, Grafana mandatory-core rollout, OpenSearch Dashboards and Grafana provisioning paths, admin access profile contracts, and admin GUI reachability/login smoke checks. |
| 10 | `Do batch 10: vector foundations.` | Validate curated artifact ownership, extraction snapshots, `vectors-*` writes, retrieval quality baseline, governance controls, and vector operations playbook rehearsal. |
| 11 | `Do batch 11: graph foundation.` | Validate optional graph module enable and disable behavior, schema versioning, idempotent sync jobs, freshness alerts, dependency queries, and graph runbook dry run. |
| 12 | `Do batch 12: risk scoring and assisted RCA readiness.` | Validate deterministic feature definitions, risk scoring outputs, backtesting evidence, hybrid retrieval evidence bundles, human approval workflow, and pilot go or hold record. |
| 13 | `Do batch 13: core adapter integrations.` | Validate adapter contract schema coverage, profile-driven activation safety, identity/secrets/network stub metadata, CI contract gating, CI/CD neutrality checks, and adapter operations guide completeness. |

## Optional Strict Commands

Use these if you want the agent to always include explicit evidence.

1. `Do batch X and include validation evidence only when all checks pass.`
2. `Do batch X, stop before merge, and show failed validations first if any.`
3. `Do batch X and produce a short validation report with pass/fail per check.`

## Stop/Resume Commands

- `Stop after current task and summarize status.`
- `Pause after batch X validation and wait for approval.`
- `Proceed to next batch.`

## Example

```markdown
REFERENCE: @docs/auxiliary/planning/TECHNICAL.md
CONTEXT: @docs/auxiliary/planning/TASKS.md
TASKS:
- Do batch 1: delivery foundation.
- Validate install contract schema samples, GitOps structure, CI checks, secret scanning, and baseline runbooks.
```
