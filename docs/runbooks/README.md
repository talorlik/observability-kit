# Operator Runbooks

This directory holds the operator guides and runbooks for every batch
delivered by the platform, plus the cross-cutting incident, rollback, and
validation runbooks that operators rely on.

If you do not know which runbook you need, start at
`VALIDATION_RUNBOOK.md` for the per-batch verification entrypoints, or at
the install entrypoint below.

## Cross-cutting runbooks

| Runbook                                  | Purpose                                                          |
| ---------------------------------------- | ---------------------------------------------------------------- |
| `INSTALL_RUNBOOK.md`                     | Platform install entrypoint and pre-flight checklist             |
| `VALIDATION_RUNBOOK.md`                  | Per-batch verification commands and CI gate documentation        |
| `ROLLBACK_RUNBOOK.md`                    | Standard rollback procedure for any batch                        |
| `ROLLBACK_UNINSTALL_RUNBOOK.md`          | Full uninstall procedure (rare; preserves audit evidence)        |
| `DR_RESTORE_RUNBOOK.md`                  | Disaster-recovery restore from backup                            |
| `INCIDENT_DRILL_RUNBOOK.md`              | Incident-drill scenarios and exit criteria                       |

## Per-batch operator guides

| Batch | Runbook                                                  | Scope                                                              |
| ----- | -------------------------------------------------------- | ------------------------------------------------------------------ |
| 1     | `INSTALL_RUNBOOK.md`                                     | Foundation install, contract gates                                 |
| 2     | `COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md`               | Compatibility matrix, mode selection                               |
| 3     | `PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md`              | Cluster preflight, capability discovery                            |
| 4     | `COLLECTOR_CORE_TOPOLOGY_OPERATOR_GUIDE.md`              | OpenTelemetry agent + gateway topology                             |
| 4     | `COLLECTOR_FAILURE_SIMULATION_RUNBOOK.md`                | Collector failure-mode drills                                      |
| 5     | `LOGS_PIPELINE_OPERATOR_GUIDE.md`                        | Logs ingest, parsing, redaction, retention                         |
| 6     | `METRICS_TRACES_PIPELINE_OPERATOR_GUIDE.md`              | Metrics + traces pipelines, sampling, correlation                  |
| 7     | `ONBOARDING_SUBSCRIPTION_OPERATOR_GUIDE.md`              | Workload onboarding, subscription model                            |
| 8     | `SECURITY_ISOLATION_RESILIENCE_OPERATOR_GUIDE.md`        | Isolation, encryption, audit, restore drills                       |
| 9     | `OPERATOR_EXPERIENCE_SLO_OPERATIONS_GUIDE.md`            | Dashboards, SLOs, alert response                                   |
| 9A    | `VISUALIZATION_ADMIN_ACCESS_PLANE_GUIDE.md`              | Admin GUI provisioning, signal-to-UI ownership                     |
| 10    | `VECTOR_FOUNDATIONS_OPERATOR_GUIDE.md`                   | Vector index governance, recall, retrieval controls                |
| 11    | `GRAPH_FOUNDATION_OPERATOR_GUIDE.md`                     | Neo4j sync quality, schema, freshness                              |
| 12    | `RISK_SCORING_ASSISTED_RCA_READINESS_GUIDE.md`           | Risk scoring, assisted-RCA readiness, approval evidence            |
| 13    | `CORE_ADAPTER_INTEGRATIONS_OPERATOR_GUIDE.md`            | Adapter activation, neutrality, rollback                           |
| 14    | `AI_MCP_LAYER_OPERATOR_GUIDE.md`                         | Parent guide for the AI/MCP runtime layer                          |
| 14    | `AI_APPROVAL_FLOW_RUNBOOK.md`                            | Approval-gated action flow, timeout / escalation                   |
| 14    | `MCP_GATEWAY_OPERATIONS_RUNBOOK.md`                      | MCP gateway health, per-tool quota, failover                       |
| 14    | `CASEFILE_REVIEW_RUNBOOK.md`                             | Case-file lifecycle review and replay                              |
| 14    | `KHOOK_TROUBLESHOOTING_RUNBOOK.md`                       | KHook trigger dedupe / burst-control diagnosis                     |

## Conventions

- Every per-batch runbook starts with a `Scope`, `Pre-checks`, `Procedure`,
  and `Verification` section. Deviations are explicitly justified at the
  top of the runbook.
- Alert rules under `gitops/platform/search/dashboards/alerts/` carry a
  `runbook:<path>` tag pointing at the matching guide here.
- Validation reports under `docs/reports/validation/` reference these
  runbooks by their canonical filename. When a runbook is renamed, update
  every reference in `scripts/ci/validate_runbook_links.sh` and in
  `docs/runbooks/README.md` (this file).
