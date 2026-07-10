# ADR-0007: Disposable Cluster Harness

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 23 owner)
**Markers:** TB-23, TR-12, TR-24

## Context

Batches 1-22 produced a validated blueprint: every capability is proven
by contracts, fixtures, and offline CI validators. Nothing has run on a
real cluster. Batch 23 must prove every declared runtime behavior live
and replace declared fixture evidence with captured evidence, without
ever gating pull requests on a live cluster (TR-24).

The environment constraints are fixed by the SaaS productization plan:

- Live validation runs on the reference development machine (OrbStack
  2.x, 24 GB RAM, 8 CPUs, `kind` installed). No batch provisions cloud
  infrastructure; autonomous runs must never create billable resources.
- The OrbStack built-in Kubernetes cluster is the persistent dev stack
  and is never an evidence source.
- The compatibility matrix (`TR-04`) lists Kubernetes 1.28-1.30 and the
  distributions eks/gke/aks (supported) and kubeadm/openshift
  (conditional). `kind` was deliberately absent, so a live kind cluster
  graded `blocked` and the guided installer halted on it by contract.
- The only permitted install path on the harness is the Batch 18 guided
  installer; a hand-assembled install invalidates the evidence it
  produces (TR-24). The installer performs no cluster API writes: it
  renders GitOps output, and the contracted operator actions are to
  commit `rendered/` into the GitOps repository and apply the rendered
  Argo CD bootstrap kustomization.

## Decision

Live validation runs only on disposable `kind` clusters created on the
local Docker engine (OrbStack on the reference development machine),
never on shared or long-lived clusters, and is never CI-gated on pull
requests. The decision decomposes as follows.

1. **kind over k3d.** kind is installed on the reference machine, is
   the tool the Batch 17 live probe
   (`scripts/validate/discovery_executor_kind_integration.sh`) already
   gates on (`kind-` context prefix refusal), and its node image is a
   pinned, multi-arch artifact. k3d is not installed and k3s deviates
   further from upstream Kubernetes than kind does. The contract keeps
   k3d as an allowed future profile extension but fixes kind for v1.
2. **Two local stack profiles**, fixed by
   `contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml`:
   `evidence-disposable` (a kind cluster created and destroyed per
   evidence run; the only profile evidence may come from) and
   `dev-persistent` (the OrbStack built-in Kubernetes cluster with the
   dev overlay and a documented reset procedure, for day-to-day
   iteration, never for evidence capture).
3. **Isolated kubeconfig, structurally unreachable foreign clusters.**
   The harness writes its own kubeconfig file under its scratch
   directory and never reads or writes `~/.kube/config` or the ambient
   `KUBECONFIG`. Every kubectl/helm/obskit invocation the harness makes
   uses that file explicitly. The harness refuses to operate on any
   context it did not create: context names must match
   `kind-obskit-evidence` and must be recorded in the harness
   provenance file from the same run. Cloud and shared contexts
   (EKS/GKE/AKS ARNs, the OrbStack built-in cluster) are structurally
   unreachable. The harness also refuses a remote `DOCKER_HOST` and
   refuses to run when `ENVIRONMENT=production`.
4. **Kubernetes version pinned to the matrix, not to kind's default.**
   The harness pins `kindest/node:v1.29.14` because 1.29 grades
   `supported` in the compatibility matrix. The product's version
   support claim is the matrix; the harness follows it rather than
   silently widening it. Raising the matrix ceiling is release
   engineering work (Batch 25), not harness work.
5. **`kind` becomes a `conditional` distribution by contract change
   first.** `contracts/compatibility/COMPATIBILITY_MATRIX.json` gains
   `{"name": "kind", "status": "conditional", "conditions":
   ["disposable_evidence_harness_only"]}`, with the matching
   remediation entry in `REMEDIATION_CATALOG.json` and a sample
   evaluation in `GRADING_RULES.json` exercised by the Batch 2
   validator. The grade is honest: kind is fit for disposable evidence
   runs, not for production; the condition string says exactly that.
6. **Conformance baseline is provisioned by the harness, then the
   installer runs.** Preflight and grading assume a conformant cluster
   (ingress controller, secrets operator CRDs, GitOps controller, a
   storage class matching a catalog profile). On a customer cluster
   these preexist; on a fresh kind cluster the harness `create` phase
   provisions them from pinned upstream manifests (ingress-nginx,
   external-secrets, Argo CD) plus a `standard-rwo` StorageClass
   backed by kind's local-path provisioner. This is cluster
   conformance preparation, not installation: the platform itself
   still arrives only through the guided installer.
7. **Attach mode with a harness-managed OpenSearch backend.** The
   platform-core chart treats OpenSearch as an attached backend, so
   the harness deploys a single-node OpenSearch and Dashboards (with
   the security plugin active) as simulated provider-managed services
   and passes their endpoints through the install contract's
   `attached_services` answers. Neo4j Enterprise runs as tenant
   isolation fixture infrastructure only, because the tenant isolation
   matrix floor for the graph tier is one native database per tenant,
   which Neo4j community does not support; the enterprise image runs
   under its evaluation license acceptance on the disposable cluster
   only, and commercial licensing remains a Batch 25 release-gate
   concern.
8. **GitOps reconciliation is real.** The harness commits the
   installer's `rendered/` output into a disposable clone of the
   GitOps tree, serves that clone from an in-cluster git daemon, and
   applies the rendered Argo CD bootstrap kustomization - exactly the
   two operator actions the install contract prescribes. Argo CD then
   syncs platform-core from git. No manifest is hand-applied outside
   that path.
9. **Single entry point.** `scripts/dev/live_cluster_harness.sh` is
   the mode-parameterized entry point for `create`, `run`, and
   `teardown` (plus `status`), following the repo's ops-script
   conventions. Teardown deletes the kind cluster, verifies deletion
   against both kind and Docker, and removes the scratch kubeconfig.
10. **Harness-scoped pins are not registry pins.** The harness
    contract pins exact upstream versions for reproducibility of
    evidence runs. These pins deliberately do not resolve the three
    `to-be-pinned` entries in the Batch 16 wrapped-system registry
    (`opensearch`, `opensearch-dashboards`, `argocd`); those remain
    open until Batch 25 and keep blocking production profiles.

## Alternatives Considered

- **k3d/k3s harness.** Rejected for v1: not installed on the reference
  machine, and k3s replaces enough upstream components (storage,
  ingress defaults) that evidence would be less transferable. The
  contract leaves room to add a k3d profile later.
- **Reusing the OrbStack built-in cluster for evidence.** Rejected:
  it is persistent, accumulates dev state, and violates the
  disposable-per-run guarantee that makes evidence reproducible.
- **Grading kind by adding it as `supported`.** Rejected: kind is a
  test harness, not a production target. `conditional` with an
  explicit harness-only condition keeps the compatibility claim
  truthful.
- **Applying rendered manifests directly instead of running Argo CD.**
  Rejected: TR-24 invalidates hand-assembled installs, and the
  GitOps-only propagation contract is itself a runtime claim the
  evidence must cover.
- **Neo4j community with per-tenant instances for the graph denial
  scenario.** Rejected: the isolation matrix floor is native
  multi-database isolation in every class; community cannot express
  it, so the evidence would not test the contracted mechanism.

## Consequences

- Live evidence becomes reproducible: same pins, same profile, same
  flow, on any machine with Docker, kind, and network access.
- PR CI is untouched. The live path stays manual or nightly
  (`.github/workflows/e2e-nightly.yaml` ships disabled by default);
  the repo-only validators check captured evidence structurally.
- The compatibility matrix now names kind, so the installer proceeds
  on the harness; the `disposable_evidence_harness_only` condition
  surfaces in every graded artifact captured from the harness.
- Evidence runs pull pinned upstream images; a fully air-gapped
  evidence run is out of scope for v1 and would need a local registry
  mirror profile added to the harness contract.
- The harness adds a scratch directory (`.live-harness/`, gitignored)
  and a committed evidence tree (`artifacts/evidence/`).
