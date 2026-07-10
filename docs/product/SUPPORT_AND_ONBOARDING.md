# Support and Onboarding

Playbook for support engineers and commercial administrators: how a
customer moves from evaluation to a provisioned, billed tenant, how
to triage the issues they raise, the known failure modes with their
remediations, the escalation paths, and the service-level
commitments the platform makes.

Every flow here reflects delivered behavior. Deep operator detail
lives in the runbooks under `docs/runbooks/`; this playbook is the
map from a customer symptom to the right procedure. The commercial
context (plans, quotas, metering, invoicing) is in
[Pricing and Packaging](PRICING_AND_PACKAGING.md).

## Table of Contents

- [Customer Onboarding Flow](#customer-onboarding-flow)
- [Tenant Lifecycle States](#tenant-lifecycle-states)
- [SLO Commitments](#slo-commitments)
- [Triage Flows](#triage-flows)
- [Known Failure Modes and Remediation](#known-failure-modes-and-remediation)
- [Escalation Paths](#escalation-paths)
- [Rehearsing with Drills](#rehearsing-with-drills)
- [Reference Documents](#reference-documents)

## Customer Onboarding Flow

Onboarding runs in five stages, from first evaluation to a tenant
that is provisioned, isolated, ingesting, and metered.

| Stage | Outcome | Primary reference |
| ----- | ------- | ----------------- |
| 1. Evaluate | Product understood, prerequisites confirmed | [Documentation index](INDEX.md) reading paths |
| 2. Install the platform | Guided install completed, readiness green | [Guided installation guide](../runbooks/GUIDED_INSTALLATION_GUIDE.md) |
| 3. Provision the tenant | Tenant active with isolation verified | [SaaS tenancy runbook](../runbooks/SAAS_TENANCY_RUNBOOK.md) |
| 4. Onboard workloads | Customer telemetry flowing | [Onboarding examples](../onboarding/ONBOARDING_EXAMPLES.md) |
| 5. Activate commercial operations | Usage metered, invoices exportable | [Commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md) |

### Stage 1: Evaluate

Point evaluators at the documentation index and its "evaluating the
product" reading path. Confirm the target environment against the
compatibility matrix before promising anything: unsupported
Kubernetes versions and distributions are the most common
evaluation-stage blockers (see
[Known Failure Modes](#known-failure-modes-and-remediation)).

### Stage 2: Install the Platform

The guided installer (`obskit install`) executes seven contracted
steps in a fixed order: `preflight`, `grading`,
`mode-recommendation`, `contract-capture`, `render`,
`argocd-bootstrap`, and `post-install-readiness`. Delivery is
GitOps-only - the installer renders configuration and bootstraps
Argo CD; it never writes to the cluster API directly. A failed run
resumes from the first incomplete step, so "start over" is almost
never the right advice: fix the reported blocker and re-run.

The final step emits an install summary with readiness results and
next steps; ask for that summary in any install-related ticket.

### Stage 3: Provision the Tenant

Tenant provisioning follows the
[SaaS tenancy runbook](../runbooks/SAAS_TENANCY_RUNBOOK.md):

1. Author the tenant descriptor: `tenant_id`, `tier`, isolation
   class, residency, and quotas. Quotas must sit inside the bounds
   of the plan bound to the chosen tier, or admission validation
   rejects the descriptor (see
   [Pricing and Packaging](PRICING_AND_PACKAGING.md)).
2. Choose the isolation class with the customer. Enterprise-tier
   tenants may take dedicated-stack isolation; the isolation
   guarantees themselves come from the
   [tenant isolation matrix](../../contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml)
   and are identical promises at every tier.
3. Provision through the tenant control plane, which renders the
   tenant's GitOps overlay; nothing is mutated live.
4. Run post-provision verification, including the isolation checks,
   before handing credentials to the customer.

Day-2 tenant administration (transitions, approvals, purge evidence)
is the
[tenant administration runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md).

### Stage 4: Onboard Workloads

Customer teams subscribe their workloads through the one-block
onboarding values contract
([reference](../onboarding/ONBOARDING_VALUES_CONTRACT.md)). Three
worked patterns cover the usual cases, in increasing customer
effort: passive, low-touch, and instrumentation
([examples](../onboarding/ONBOARDING_EXAMPLES.md)). The operator
side of subscriptions is the
[onboarding and subscription operator guide](../runbooks/ONBOARDING_SUBSCRIPTION_OPERATOR_GUIDE.md).

### Stage 5: Activate Commercial Operations

No activation step is required for metering itself: usage is derived
from telemetry already stored in OpenSearch, keyed by the tenant's
index partitioning, from the moment data flows. Commercial
administrators verify the daily usage records exist, then run the
invoicing flow per the
[commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md).

## Tenant Lifecycle States

The
[tenant lifecycle contract](../../contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml)
fixes the state machine support engineers reason against:
`provisioning`, `active`, `suspended`, `offboarding`, and the
terminal state `purged`.

- Every transition attempt - applied, replayed, or denied - emits an
  audit record carrying the `tenant_id`. Ask for the
  `audit_record_id` when a customer reports a denied action.
- Transitions are idempotent: re-running a completed transition is a
  recorded no-op replay, not an error.
- Destructive transitions (offboard, purge) require approval per the
  [approval flow contract](../../contracts/policy/APPROVAL_FLOW_V1.yaml).
  Suspend needs no approval: it is provably non-destructive (resume
  exists) and may be operator-initiated or automated on a quota
  breach or billing signal.
- There are no transitions out of `purged`. A returning customer is
  re-onboarded through a new contract document, not by reviving the
  purged record.

## SLO Commitments

The platform's product SLOs - the promises made to paying tenants -
are declared in the
[platform product SLO contract](../../contracts/slo_ops/PLATFORM_PRODUCT_SLO_V1.yaml).
All objectives use a 28-day rolling window, and targets bind to the
same tier enum as the plans. Targets below are percentages except
tenant isolation, which is a maximum violation count.

| SLO | Starter | Standard | Premium | Enterprise |
| --- | ------- | -------- | ------- | ---------- |
| Ingest availability | 99.5 | 99.5 | 99.9 | 99.9 |
| Ingest latency within bounds | 99.0 | 99.0 | 99.5 | 99.5 |
| Query availability | 99.5 | 99.5 | 99.9 | 99.9 |
| Portal and dashboards availability | 99.0 | 99.5 | 99.5 | 99.9 |
| Control plane availability | 99.0 | 99.5 | 99.5 | 99.9 |
| AI analysis availability (degradable) | 95.0 | 97.0 | 99.0 | 99.0 |
| Tenant isolation (violations) | 0 | 0 | 0 | 0 |

What support and commercial teams must know when quoting these:

- Tenant isolation is a hard SLO with a zero violation budget at
  every tier - tiers never buy laxer isolation. Any violation is an
  immediate highest-severity incident: affected tenants are
  notified, releases freeze until root-cause analysis completes, and
  the incident review is mandatory. No waiver exists.
- AI-assisted analysis is explicitly degradable: the platform is
  fully usable without it, so its target is lower and its breach
  never freezes releases on its own.
- Ingest latency bounds are the TR-11 targets: logs under 60
  seconds, metrics under 30 seconds, traces under 60 seconds, at
  p95 per 5-minute interval.
- SLOs are measured on the production stack only (a cluster graded
  supported against the production reference architecture).
  Evaluation harnesses and developer stacks are out of scope.
- Status is declared-for-GA: targets are declared ahead of GA and
  measurement history begins with the first production deployment
  of a tagged release. Until then, release gates record the SLO
  review as "declared, not yet measured". Do not quote historical
  attainment - none exists.

How they are measured: every SLI is computed from telemetry that
already exists in OpenSearch through the sole OpenTelemetry
collector path. Budget state surfaces on the `00-platform-health`
dashboards; breaches fire the Batch 9 alert taxonomy (fast and slow
burn-rate pairs, symptom alerts for the isolation SLO) routed to the
`oncall-platform` channel, and every alert carries a runbook link.
Exhausted budgets trigger a release freeze and a mandatory blameless
incident review per the contract's error budget policy.

## Triage Flows

Collect on intake, for every ticket: the `tenant_id`, the tenant's
current lifecycle state, its tier, timestamps in UTC, and - for any
denied action - the `error_code` and `audit_record_id` from the
error response. Denied transitions always carry both.

Then classify by symptom:

| Symptom area | First check | Where to go |
| ------------ | ----------- | ----------- |
| Install fails or stalls | Preflight report and remediation list from the `preflight`/`grading` steps | [Preflight and discovery guide](../runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md) |
| No telemetry from a workload | Onboarding values block validity, then collector health | [Onboarding troubleshooting](../onboarding/TROUBLESHOOTING.md) |
| Tenant action denied | `error_code` in the API error response | [Tenant administration runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md) |
| Customer sees another tenant's data (suspected) | Treat as isolation SLO violation; escalate immediately | [Security and isolation guide](../runbooks/SECURITY_ISOLATION_RESILIENCE_OPERATOR_GUIDE.md) |
| Quota or usage dispute | Usage records for the window in `control-tenancy-usage-v1-*` | [Commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md) |
| Invoice wrong or missing | Daily usage records exist; re-run export (idempotent) | [Commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md) |
| Platform-wide degradation | `00-platform-health` dashboards and active burn-rate alerts | [SLO operations guide](../runbooks/OPERATOR_EXPERIENCE_SLO_OPERATIONS_GUIDE.md) |

## Known Failure Modes and Remediation

### Install-Time Failures

Preflight and grading failures come with a machine-generated
remediation list drawn from the
[remediation catalog](../../contracts/compatibility/REMEDIATION_CATALOG.json).
The blocking classes to recognize on a call:

- `unsupported_kubernetes_version`: upgrade or downgrade the control
  plane to a matrix-supported version, then re-run grading.
- `unsupported_distribution`: move to a supported distribution or
  open an adapter request; this is not workaround-able.
- `ingress_controller_required` and `gateway_api_crds_required`:
  install the missing ingress or Gateway API prerequisites and
  re-run preflight.
- `missing_required_profile` and `missing_prerequisite`: the
  remediation entry names exactly what to install or configure.

Conditional grades (for example `throughput_validation_required` or
`security_context_profile_adjustment`) mean the install can proceed
after the named validation - set that expectation with the customer
rather than treating the grade as a failure.

### Workload Onboarding Failures

The
[onboarding troubleshooting guide](../onboarding/TROUBLESHOOTING.md)
covers the three recurring classes: schema failures (the values
block does not validate), policy rejections (the subscription asks
for something the tenant's isolation class forbids), and runtime
issues (accepted configuration but no data). Work them in that
order; each class has a distinct fix owner (customer, commercial
administrator, platform operator respectively).

### Tenant Lifecycle Denials

The control plane returns a stable `error_code` on every denial.
The most common, with the support response:

| Error code | Support response |
| ---------- | ---------------- |
| `validation-failed` | Fix the named field in the payload; quotas outside plan bounds land here |
| `tenant-already-exists` | Ids are never reused; pick a new id or use update |
| `illegal-transition` | Read the current state and follow the state machine path |
| `precondition-failed` | Purge blocked by retention window, legal hold, or missing offboard |
| `approval-required` / `approval-invalid` | Obtain (or refresh) the approval for the bound risk class; on timeout, follow the escalation chain |
| `cross-tenant-access-denied` | Verify caller identity; repeated denials are a security signal, not a nuisance |

The full table, including replay and purge edge cases, is in the
[tenant administration runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md).

### Quota Breaches

Breach handling is evidence-based: detection compares usage records
against descriptor quotas and plan bounds, surfaces through the
standard alerting path, and enforcement (for example suspend on
sustained breach) is a control-plane lifecycle action subject to the
approval flow, with an audit record per action. Never respond to a
breach by editing tenant indices, roles, or dashboards directly -
isolation surfaces are owned by the tenancy contracts.

### Billing and Invoice Issues

- A malformed or inconsistent invoice is rejected by
  `ensure_invoice_consistent` before it leaves the platform; the fix
  is in the inputs (usage records or plan), never manual document
  edits.
- Missing invoices usually mean missing daily usage records; re-run
  the metering job for the missing days, then re-export. Both
  operations are idempotent, so re-runs are always safe.
- A failing vendor billing adapter is disabled and falls back to the
  vendor-neutral `file-export` backend with no invoice data loss;
  see the
  [billing adapter rollback notes](../../adapters/billing/ROLLBACK_UNINSTALL_NOTES.md).

## Escalation Paths

Two escalation mechanisms exist; use the right one.

### Operational Alerts

Platform alerts route to the `oncall-platform` channel with fast and
slow burn-rate severities, and every alert carries its runbook link -
follow it. A suspected tenant isolation violation skips triage
entirely: it is an immediate highest-severity incident with tenant
notification and a release freeze (see
[SLO Commitments](#slo-commitments)). Incident mechanics follow the
[incident drill runbook](../runbooks/INCIDENT_DRILL_RUNBOOK.md).

### Pending Approvals

Destructive tenant actions wait on human approval with contract-fixed
timeouts from the
[approval flow contract](../../contracts/policy/APPROVAL_FLOW_V1.yaml):
high-risk writes time out after 60 minutes (warning at 30) and
critical writes after 120 minutes (warning at 60). On timeout the
action is denied and escalated - it never silently proceeds - and an
audit event is mandatory.

The default escalation chain, with per-step response SLAs:

1. `oncall-sre` - 30 minutes.
2. `incident-commander` - 60 minutes.
3. `platform-director` - 120 minutes.

Escalations notify through the audit log, the paging service, and a
casefile comment, and every escalation itself emits an audit event.

## Rehearsing with Drills

Support confidence comes from rehearsal. The operational drills
under `scripts/ops/` are mode-parameterized with `dry-run` as the
default, so they are safe to practice with:

- `run_uninstall_validation.sh` - uninstall and cleanup validation.
- `run_rollback_drill.sh` - GitOps revision rollback.
- `run_config_rollback_drill.sh` - configuration rollback re-render.
- `run_restore_drill.sh` - OpenSearch snapshot restore; this drill
  hard-refuses to run when `ENVIRONMENT=production`, in every mode.

Live-cluster rehearsal uses the disposable evidence harness per the
[live validation runbook](../runbooks/LIVE_VALIDATION_RUNBOOK.md);
disaster recovery procedure is the
[DR restore runbook](../runbooks/DR_RESTORE_RUNBOOK.md).

## Reference Documents

- [Documentation index](INDEX.md)
- [Pricing and Packaging](PRICING_AND_PACKAGING.md)
- [SaaS tenancy runbook](../runbooks/SAAS_TENANCY_RUNBOOK.md)
- [Tenant administration runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md)
- [Commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md)
- [Guided installation guide](../runbooks/GUIDED_INSTALLATION_GUIDE.md)
- [Onboarding values contract](../onboarding/ONBOARDING_VALUES_CONTRACT.md)
- [Platform product SLO contract](../../contracts/slo_ops/PLATFORM_PRODUCT_SLO_V1.yaml)
- [Tenant lifecycle contract](../../contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml)
- [Approval flow contract](../../contracts/policy/APPROVAL_FLOW_V1.yaml)
- [Incident drill runbook](../runbooks/INCIDENT_DRILL_RUNBOOK.md)
