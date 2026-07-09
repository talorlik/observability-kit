# Implementation Batch Command Sheet

Use these commands to run implementation in controlled batches aligned to
`docs/auxiliary/planning/IMPLEMENTATION_TASKS.md`.
Run one batch at a time and require validation before moving forward.

## Batch Commands

| Batch | Command To Send | Validation Step (Required) |
| ---- | ---- | ---- |
| 1 | `Do batch 1: delivery foundation.` | Validate contract tests in CI, invalid fixture failure behavior, render checks for stubs, CI rejection of seeded invalid YAML or secrets, and runbook link validation. |
| 2 | `Do batch 2: compatibility and modes.` | Validate matrix grade mapping tests, profile fixture schema checks, and deterministic mode output tests. |
| 3 | `Do batch 3: preflight and discovery engine.` | Validate preflight test coverage for all check classes, full expected file generation from sample run, and smoke bundle pass on reference cluster profile. |
| 4 | `Do batch 4: collector core topology.` | Validate helm template plus cluster dry-run apply, required collector chains and export checks, and bounded-loss simulation metrics. |
| 5 | `Do batch 5: logs pipeline.` | Validate single-line and multiline fixture tests, sensitive fixture redaction or drop behavior, and clean template and policy install with dashboard render checks. |
| 6 | `Do batch 6: metrics and traces pipelines.` | Validate opted-in workload metrics indexing, trace ingest with sampling targets matching policy, and synthetic plus pilot correlation tests. |
| 7 | `Do batch 7: onboarding and subscription model.` | Validate one-block onboarding chart rendering, non-compliant onboarding rejection with clear output, and one-block onboarding CI smoke pass. |
| 8 | `Do batch 8: security, isolation, and resilience.` | Validate expected cross-team access denials, CI security contract and audit tests, and successful non-production restore plus rollback drills. |
| 9 | `Do batch 9: operator experience and SLO operations.` | Validate saved object import on test cluster, synthetic event alert routing, and drill evidence plus alert-noise trend checks. |
| 9A | `Do batch 9A: visualization and admin access plane.` | Validate signal-to-UI ownership contract linting, core UI provisioning path rendering, admin-access profile schema checks, and admin GUI TLS plus login smoke results. |
| 10 | `Do batch 10: vector foundations.` | Validate versioned extraction snapshot bundle output, OpenSearch vector write and queryability, and quality baseline plus governance checks. |
| 11 | `Do batch 11: graph foundation.` | Validate healthy core platform behavior with graph on and off, convergent repeated sync runs, and stale-data freshness alert triggering. |
| 12 | `Do batch 12: risk scoring and assisted RCA readiness.` | Validate deterministic score reruns, backtest and evidence bundle contracts, and approval evidence before RCA suggestion release. |
| 13 | `Do batch 13: core adapter integrations.` | Validate adapter contract schema coverage, profile-driven activation safety, identity and secrets and network stub metadata, CI contract gating, CI/CD neutrality checks, and adapter operations guide completeness. |
| 14 | `Do batch 14: AI/MCP runtime validation and productization.` | Validate AI boundary, governance, and state contracts, MCP catalog and gateway discovery contracts, runtime, read-path, multi-agent, trigger, and action-gate scaffolding, AI/MCP GitOps artifacts, release readiness, and operator runbooks. |
| 15 | `Do batch 15: SaaS multi-tenancy and customer isolation.` | Validate tenant schema with seeded invalid rejection, per-tenant isolation matrix coverage, lifecycle transitions with purge evidence, per-tenant overlay generation safety, and tenancy runbook completeness. |
| 16 | `Do batch 16: unified configuration and management plane.` | Validate wrapped-system registry coverage with fork rejection, unified configuration binding completeness, GitOps-only propagation with drift detection, single-pane UI catalog auth mapping, and unified configuration runbook completeness. |
| 17 | `Do batch 17: discovery and preflight execution engine.` | Validate executor ADR and architecture contract, schema-conformant preflight and discovery reports, deterministic capability plus grading plus mode plus remediation outputs, offline fixture harness pass with read-only RBAC, and executor runbook completeness. |
| 18 | `Do batch 18: guided installation experience.` | Validate install flow contract step order, wizard answer validation with seeded invalid-answers rejection, GitOps-only render output, post-install readiness invocation with install summary, and installation guide completeness. |
| 19 | `Do batch 19: configuration rendering runtime.` | Validate renderer ADR and architecture contract, byte-identical re-render tests, generated-file header and commit trailer checks, rendered-versus-live drift diff output, rollback re-render drill in dry-run mode, and offline fixture harness pass. |
| 20 | `Do batch 20: tenant control plane service.` | Validate OpenAPI contract lifecycle semantics, idempotent replay tests per transition, isolation provisioning render fixtures, approval denial and timeout tests with tenant-scoped audit records, and seeded denial fixture rejection offline. |
| 21 | `Do batch 21: unified management portal.` | Validate portal contract schema checks, UI catalog aggregation tests, Git-commit-only config edit flow tests, SSO role mapping and tenant scoping tests, and admin GUI smoke extension for the portal endpoint. |
| 22 | `Do batch 22: metering, billing, and commercial operations.` | Validate metering contract dimension coverage, control-tenancy index write tests with tenant attribution, plan catalog quota bound checks, billing adapter stub metadata and rollback notes, and seeded rejection fixture behavior. |
| 23 | `Do batch 23: live-cluster validation and evidence.` | Validate harness ADR and contract with kind/k3d profile and teardown guarantees, installer-only install summary and readiness evidence capture, live drill and GUI smoke and SDN-B15 denial scenario evidence artifacts, additive captured-evidence references without schema renames, structural evidence-file checks without a cluster, and disabled-by-default nightly workflow wiring. |
| 24 | `Do batch 24: AI/MCP runtime activation.` | Validate model-provider adapter stub metadata and secrets-backend key resolution, live KAgent and KHook and MCP gateway deployment evidence, trigger-to-casefile-to-approval rehearsal evidence with policy and redaction and audit intact, signoff record with measured thresholds, structural activation checks without a cluster, and extended AI runbook sections. |
| 25 | `Do batch 25: production operations and release engineering.` | Validate release contract semver and changelog and OCI publication rules, concrete registry pins with fail-if rule pass and harness install evidence, N-1 upgrade evidence with data and config survival, platform SLO extension checks, SBOM and image scan and license inventory artifacts, and seeded unpinned-profile and missing-license rejections. |
| 26 | `Do batch 26: product documentation and GA readiness.` | Validate product docs index and audience map coverage, core and tenant and commercial document presence checks, generated API reference marker and contract fidelity, docs-coverage matrix with every Batch 17-25 capability mapped, link validation across the docs tree, and signed GA readiness checklist with per-item evidence links. |

## Optional Strict Commands

Use these when explicit evidence is always required.

1. `Do batch X and include validation evidence only when all checks pass.`
2. `Do batch X, stop before merge, and show failed validations first if any.`
3. `Do batch X and produce a short validation report with pass/fail per check.`

## Stop/Resume Commands

- `Stop after current task and summarize status.`
- `Pause after batch X validation and wait for approval.`
- `Proceed to next batch.`

## Example

```markdown
REFERENCE: @docs/auxiliary/planning/IMPLEMENTATION_TASKS.md
TASKS:
- Do batch 8: security, isolation, and resilience.
- Validate expected cross-team access denials, CI security contract and audit tests, and successful non-production restore plus rollback drills.
```
