# Operations Guide

This guide covers day-2 operation of an installed Observability Kit
platform: routine health, drills, drift response, live validation and
evidence capture, upgrades, and releases. It is the product-level map
of the operator runbooks under `docs/runbooks/`; each section links
to the runbook that carries the step-by-step procedure.

## Table of Contents

- [The Operating Model](#the-operating-model)
- [Health and Product SLOs](#health-and-product-slos)
- [Configuration Changes and Drift](#configuration-changes-and-drift)
- [Operational Drills](#operational-drills)
- [Live Validation and Evidence Capture](#live-validation-and-evidence-capture)
- [Upgrades](#upgrades)
- [Releases](#releases)
- [Production Reference Architecture](#production-reference-architecture)
- [Backup, Restore, and Uninstall](#backup-restore-and-uninstall)
- [Runbook Directory](#runbook-directory)

## The Operating Model

Three facts shape every operational procedure:

- Git is the source of truth. Persistent configuration reaches the
  cluster only as rendered commits reconciled by Argo CD. Operational
  changes are therefore commits, and operational rollback is a path
  back through the same pipeline (see the
  [Configuration Guide](CONFIGURATION_GUIDE.md)).
- Everything destructive rehearses first. Every drill script under
  `scripts/ops/` defaults to `dry-run`; live drill modes run only
  against local harness clusters and refuse anything else.
- Evidence is committed. Live validation writes evidence artifacts
  under `artifacts/evidence/`, and CI validates that evidence
  structurally without needing a cluster.

## Health and Product SLOs

The management portal serves a health summary aggregating platform
component status; the
[management portal guide](../runbooks/MANAGEMENT_PORTAL_GUIDE.md)
covers reading it and the
[SLO operations guide](../runbooks/OPERATOR_EXPERIENCE_SLO_OPERATIONS_GUIDE.md)
covers the alerting surface behind it.

The platform declares its own product SLOs in
[PLATFORM_PRODUCT_SLO_V1.yaml](../../contracts/slo_ops/PLATFORM_PRODUCT_SLO_V1.yaml):
ingest availability, ingest latency, query availability, portal
availability, control plane availability, AI analysis availability,
and tenant isolation. Targets are set per tenant tier (`starter`,
`standard`, `premium`, `enterprise`); the isolation SLO carries a
zero violation budget, because cross-tenant leakage is a hard
failure, not an error budget expense. These product SLOs are
operator-owned promises about the platform itself and are distinct
from the customer workload SLO machinery the platform provides to
tenants. Alerting reuses the standard taxonomy: burn-rate alert pairs
(fast and slow) plus symptom alerts, each carrying a runbook link.

## Configuration Changes and Drift

Configuration operations, rendering, drift detection, and rollback,
are covered in the [Configuration Guide](CONFIGURATION_GUIDE.md). The
operational summary:

- Change configuration by editing the unified document and rendering;
  never edit rendered files or live systems directly.
- The `config-drift-detected-per-system` alert fires from the same
  diff surface as `obskit drift`, so reproduce any drift alert
  locally with one read-only command.
- Respond to drift by re-rendering intent, never by editing rendered
  files to match live state.

## Operational Drills

Four drill scripts under `scripts/ops/` keep failure response
rehearsed. All default to `dry-run`, which simulates the drill steps
with no cluster access; live modes exist for harness-based evidence
runs.

| Drill | Script | Live-mode behavior |
| ---- | ---- | ---- |
| GitOps rollback | `scripts/ops/run_rollback_drill.sh` | Commits a config change to a GitOps clone, watches Argo CD converge, reverts, and verifies return to the prior state. Refuses any kube context that is not a local `kind-*` harness context. |
| Restore | `scripts/ops/run_restore_drill.sh` | Executes a real OpenSearch snapshot and restore cycle against a harness cluster. Refuses `ENVIRONMENT=production` in every mode, including dry-run. |
| Config rollback | `scripts/ops/run_config_rollback_drill.sh` | Exercises the `obskit rollback` path end to end. |
| Uninstall validation | `scripts/ops/run_uninstall_validation.sh` | Verifies namespace cleanup and cluster-scoped residual checks. |

Run drills on a schedule, not only when capturing evidence. The
[rollback runbook](../runbooks/ROLLBACK_RUNBOOK.md),
[DR restore runbook](../runbooks/DR_RESTORE_RUNBOOK.md), and
[rollback and uninstall runbook](../runbooks/ROLLBACK_UNINSTALL_RUNBOOK.md)
carry the full procedures and verification points.

## Live Validation and Evidence Capture

Live validation runs on a disposable kind cluster created per run by
the harness, `scripts/dev/live_cluster_harness.sh`, governed by
[DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml](../../contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml)
and decided by
[ADR-0007](../adr/ADR_0007_DISPOSABLE_CLUSTER_HARNESS.md):

```bash
bash scripts/dev/live_cluster_harness.sh create
bash scripts/dev/live_cluster_harness.sh run
bash scripts/dev/live_cluster_harness.sh teardown
```

The default `run` executes the installer end to end, the live drills,
a GUI smoke test, and the cross-tenant denial scenarios, writing
evidence under `artifacts/evidence/batch23/`. Individual checks
re-run with `--only <check-id>`; the base checks are `install`,
`restore-drill`, `rollback-drill`, `config-rollback-drill`,
`gui-smoke`, and `denials`. Two check families compose on top of a
completed `install` check and are never in the default run: the AI
activation checks (`ai-deploy`, `ai-rehearsal`, `ai-signoff`, writing
under `artifacts/evidence/batch24/`) and the release engineering
checks (`release-pins`, `upgrade-drill`, writing under
`artifacts/evidence/batch25/`).

Safety is layered and mandatory: the harness refuses
`ENVIRONMENT=production` and remote Docker hosts, writes and uses an
isolated kubeconfig (never your `~/.kube/config`), and operates only
on the harness context it created. The harness publishes committed
repository state only, so commit your work before capturing evidence.
The persistent developer cluster is never an evidence source.

Live runs are manual or nightly and never gate pull requests;
repository CI validates the captured evidence structurally instead.
The full procedure is the
[live validation runbook](../runbooks/LIVE_VALIDATION_RUNBOOK.md).

### AI Model Provider

The AI runtime's LLM provider is pluggable behind the model provider
adapter boundary (`adapters/providers/model/`), governed by
[MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml](../../contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml).
An Anthropic reference adapter ships with the product, and the
harness uses a `local-stub` provider so live rehearsals never depend
on an external service. Provider credentials resolve through the
platform secrets backend only; API keys are never stored in Git or
rendered into GitOps output. Switching providers is an adapter
selection, not a code change, and follows the adapter's own rollback
notes.

## Upgrades

Platform upgrades are GitOps operations: a new chart version lands as
a rendered commit and Argo CD rolls it out. Pod templates carry the
`app.kubernetes.io/version` label, so a version bump is an observable
rolling update, not a silent mutation.

Before upgrading a production profile:

- Rehearse with the harness `upgrade-drill` check, which exercises
  the version bump path on a disposable cluster on top of a completed
  install and captures evidence under `artifacts/evidence/batch25/`.
- Verify wrapped-system pins. Production profiles require pinned
  wrapped-system versions; the `release-pins` harness check proves
  the pinned set deploys, and the release gate fails production
  profiles with missing pins.
- Upgrade wrapped systems (OpenSearch, Argo CD, Neo4j, and the rest)
  through their own upstream mechanisms per the per-system procedure
  in the
  [unified configuration runbook](../runbooks/UNIFIED_CONFIGURATION_RUNBOOK.md);
  the platform wraps these systems and never forks them.

The gate sequence for production upgrades is the
[production release gate runbook](../runbooks/PRODUCTION_RELEASE_GATE_RUNBOOK.md).

## Releases

Release engineering is fixed by
[RELEASE_ENGINEERING_CONTRACT_V1.yaml](../../contracts/release/RELEASE_ENGINEERING_CONTRACT_V1.yaml)
and decided by
[ADR-0010](../adr/ADR_0010_RELEASE_ENGINEERING.md):

- Versioning is semver 2.0.0 with tags of the form
  `v<MAJOR>.<MINOR>.<PATCH>`, and the chart version equals the
  product version at release time.
- The [changelog](../../CHANGELOG.md) follows Keep a Changelog; a tag
  whose version has no matching dated changelog section fails the
  release gate before anything is packaged.
- Publication is tag-driven and operator-initiated through the
  release workflow (tag push and manual dispatch only; it never gates
  pull requests, and autonomous runs never tag or publish).
- The workflow packages the chart and images and publishes to an OCI
  registry. The registry host is deliberately a neutral placeholder;
  any OCI 1.1 registry works.
- Supply-chain gates run in the pipeline: an SBOM is generated for
  every artifact, a vulnerability scan gates on CRITICAL findings,
  and signing follows the keyless posture.
- OSS license compliance is inventoried per
  [LICENSE_COMPLIANCE_CONTRACT_V1.yaml](../../contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml),
  bijective with the wrapped-system registry.

The operator flow, checklist, and rollback path are the
[production release gate runbook](../runbooks/PRODUCTION_RELEASE_GATE_RUNBOOK.md).

## Production Reference Architecture

Production deployments conform to
[PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml](../../contracts/release/PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml):
a multi-node HA topology with anti-affinity and zone spread, sizing
tiers (`starter`, `standard`, `premium`, `enterprise`) bound one to
one to the tenant tier enum and the commercial plan catalog, storage
and ingress selected through the standard compatibility profiles, and
a defined backup and DR posture. A cluster is sized for the largest
tier it hosts. Production installs use the same guided installer with
the `prod` overlay; the stack differs by profile, never by code path.

Key floors worth internalizing: OpenSearch index replica counts of at
least one so any single node can be lost; non-ephemeral storage
classes only; and a snapshot-capable object storage profile reachable
from the cluster, because snapshots are the restore path.

## Backup, Restore, and Uninstall

- Backups are OpenSearch snapshots to the configured object storage
  profile. The Neo4j graph tier is derived from OpenSearch content
  and can be rebuilt from it, which relaxes its backup posture at
  lower tiers.
- Restore is rehearsed by the restore drill and documented in the
  [DR restore runbook](../runbooks/DR_RESTORE_RUNBOOK.md). The drill
  refuses to run when `ENVIRONMENT=production`; production restores
  follow the runbook deliberately, not through the drill script.
- Uninstall follows the
  [rollback and uninstall runbook](../runbooks/ROLLBACK_UNINSTALL_RUNBOOK.md),
  with `scripts/ops/run_uninstall_validation.sh` verifying that
  namespaces and cluster-scoped resources are actually gone.

## Runbook Directory

The runbooks referenced most in day-2 operation:

- [Live validation runbook](../runbooks/LIVE_VALIDATION_RUNBOOK.md)
- [Production release gate runbook](../runbooks/PRODUCTION_RELEASE_GATE_RUNBOOK.md)
- [Unified configuration runbook](../runbooks/UNIFIED_CONFIGURATION_RUNBOOK.md)
- [Commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md)
- [Validation runbook](../runbooks/VALIDATION_RUNBOOK.md)
- [Rollback runbook](../runbooks/ROLLBACK_RUNBOOK.md)
- [DR restore runbook](../runbooks/DR_RESTORE_RUNBOOK.md)
- [Management portal guide](../runbooks/MANAGEMENT_PORTAL_GUIDE.md)

The complete capability-to-document mapping is the docs-coverage
matrix at `contracts/docs/DOCS_COVERAGE_MATRIX_V1.yaml`, enforced in
CI by `scripts/ci/validate_product_docs.sh`.
