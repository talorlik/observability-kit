# ADR-0010: Release Engineering

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 25 owner)
**Markers:** TB-25, TR-11, TR-12, TR-25

## Context

Batches 1-24 produced a validated, live-proven platform, but the
repository is not yet a releasable product: there is no version scheme,
no changelog, no packaged artifact, no publication path, no signing
posture, and no upgrade proof. Batch 25 must fix all of these as
contracts and runnable gates without violating the standing
constraints:

- Delivery stays Terraform + Helm + ArgoCD; consumers pull versioned
  charts and images and reconcile them through GitOps. No
  provider-specific service may become mandatory, including in the
  release pipeline itself (TR-03).
- Wrapped systems are never forked; the product releases only what it
  owns: the `platform-core` chart, the GitOps trees, the `obskit`
  tooling, the service images (`obskit-ai-runtime` today), and the
  contracts and documentation.
- Live claims require harness evidence (TR-24): a pinned set must
  install cleanly on the disposable kind harness before it ships, and
  the N-1 to N upgrade path must be demonstrated, not declared
  (TR-12).
- Commercial distribution requires a completed OSS license review and
  supply-chain artifacts (SBOM, image scans) per TR-25.
- The repository has no remote-registry credentials in autonomous
  runs, and no autonomous run may create billable resources; the
  release pipeline must therefore be tag-driven and operator-initiated,
  never a side effect of merges or PR CI.

TASKS.md names this record `ADR_0009_RELEASE_ENGINEERING.md`, but
Batch 24 consumed ADR-0008 and ADR-0009 (two decisions where the
backlog had budgeted one). This record is therefore ADR-0010; the
decision content is exactly the one TASKS.md Task 1 requires.

## Decision

Releases are tag-driven, semver-versioned, OCI-published, signed by
posture, and gated by the release contract
(`contracts/release/RELEASE_ENGINEERING_CONTRACT_V1.yaml`). The
decision decomposes as follows.

1. **One product version, semver 2.0.0.** The product releases as a
   single versioned unit: a Git tag `v<MAJOR>.<MINOR>.<PATCH>` on the
   integration branch. The `platform-core` chart `version`, the chart
   `appVersion`, and every product-owned image tag are set to the
   product version at release time. Component-level versions do not
   diverge from the product version; wrapped upstream systems keep
   their own upstream versions, pinned in the wrapped-system registry.
   Pre-GA releases stay in the 0.y.z range; the GA gate (Batch 26)
   cuts 1.0.0.
2. **Changelog convention: Keep a Changelog 1.1.0, curated.**
   `CHANGELOG.md` at the repository root follows Keep a Changelog
   (`Unreleased` section plus one dated section per release, with
   `Added/Changed/Fixed/Deprecated/Removed/Security` subsections).
   Entries are curated by hand at merge time from the Conventional
   Commits subjects the repo already enforces; the changelog is the
   human-facing release narrative, not a generated commit dump. A tag
   without a matching changelog section fails the release gate.
3. **Tag-driven publication, operator-initiated.** Publication runs
   from `.github/workflows/release.yaml`, triggered only by pushing a
   `v*` tag (plus manual `workflow_dispatch` for rehearsals). PR CI is
   untouched: no release step gates pull requests, and merges to the
   local `main` never publish anything. The tag is cut by a human
   operator following `docs/runbooks/PRODUCTION_RELEASE_GATE_RUNBOOK.md`
   after the release-gate checklist passes.
4. **Packaged charts and images publish as OCI artifacts.** `helm
   package` produces the versioned `platform-core` chart archive, and
   `helm push` publishes it to an OCI registry
   (`oci://<registry>/<namespace>/charts`). Product images
   (`obskit-ai-runtime`) publish to `<registry>/<namespace>/images`.
   The registry host and namespace are configuration
   (`release.publication` in the release contract with a neutral
   `REGISTRY_HOST` placeholder); GHCR is the reference deployment of
   that configuration, not a requirement - any OCI 1.1-conformant
   registry works, keeping the pipeline cloud-agnostic.
5. **Signing posture: Sigstore cosign, keyless, on publication.**
   Charts and images are signed at publication time with cosign
   keyless signing (OIDC identity of the release workflow), and
   signatures live in the same OCI registry next to the artifacts.
   Verification commands are documented in the release-gate runbook;
   consumers may enforce verification but the platform does not
   mandate an admission controller for it in v1. Until the first
   registry publication happens (a credentialed, operator-initiated
   act), the posture is contract-fixed and workflow-implemented but
   unexercised; the release gate records this honestly as
   `signing: implemented, first publication pending`.
6. **SBOM and image scanning are release artifacts.** The release
   workflow generates an SPDX 2.3 JSON SBOM per published artifact
   (syft) and runs a CVE scan (trivy) against every published image,
   failing the release on CRITICAL findings with no recorded waiver.
   Both tools are OSS and run identically on a laptop and in CI; the
   release contract fixes formats and gates, not vendor services.
7. **The wrapped-system registry is the single pin surface.** The
   three `to-be-pinned` entries (`opensearch`,
   `opensearch-dashboards`, `argocd`) resolve to the concrete
   versions the disposable harness already installs and proves,
   verified against upstream release listings. Harness pins and
   registry pins converge deliberately: the version the evidence runs
   prove is the version production profiles pin. Raising a pin is a
   GitOps change plus a fresh harness evidence run, per the runbook.
8. **Upgrade proof is harness evidence.** The N-1 to N upgrade drill
   installs the previous release state on the disposable harness,
   seeds tenant data and configuration, upgrades to the current
   state, and verifies data and configuration survive. For the
   inaugural release, N-1 is the pre-Batch-25 `main` state (there is
   no earlier tag); every subsequent release upgrades from the
   previous tag. Evidence lands under `artifacts/evidence/batch25/`
   and is validated structurally by
   `scripts/ci/validate_release_engineering.sh`.

## Alternatives Considered

- **Classic Helm chart repository (index.yaml over HTTPS/gh-pages)
  instead of OCI.** Rejected: two publication planes (charts vs
  images) with different tooling and hosting; OCI unifies charts,
  images, signatures, and SBOMs in one registry with one auth model,
  and Helm has supported OCI as a first-class path since 3.8.
- **Per-component versioning (chart, obskit, airuntime each on their
  own semver).** Rejected for v1: the product installs and upgrades
  as one unit, support and evidence claims are per product version,
  and a version matrix would multiply the upgrade-test surface
  without a consumer who needs it.
- **Generated changelog from Conventional Commits (semantic-release
  style).** Rejected: squash-merged batch commits are too coarse for
  release notes, and generated dumps bury breaking changes. The
  Conventional Commits discipline stays as the input; a curated Keep
  a Changelog file is the output.
- **GPG-signed artifacts or no signing.** Rejected: GPG key custody
  is exactly the kind of long-lived secret the repo's secrets posture
  avoids, and shipping unsigned commercial artifacts fails the
  supply-chain bar. Keyless cosign binds signatures to the workflow
  identity with short-lived certificates and needs no stored key.
- **Grype instead of trivy for scanning.** Either passes the
  requirement; trivy is chosen because one binary covers image CVE
  scanning plus license detection used by the license inventory
  cross-check, reducing the toolchain to syft + trivy.
- **Pinning wrapped systems to latest upstream instead of
  harness-proven versions.** Rejected: a pin nothing has installed is
  a declaration, not evidence; TR-25 explicitly requires the pinned
  set to install cleanly on the harness before it ships.

## Consequences

- The repository gains a root `CHANGELOG.md`, a release contract, a
  tag-driven release workflow, and a release-gate runbook; none of
  them touch PR CI latency.
- Production profiles stop being blocked by
  `fail_if_production_pin_missing` once the three pins land - the
  first time a production-environment install profile is
  contract-legal.
- Release quality gates (changelog section, pins, SBOM, scan,
  license inventory, upgrade evidence) become structurally validated
  by `validate_release_engineering.sh` in PR CI, while the acts of
  publishing and signing remain operator-initiated and credentialed.
- The product version and chart version couple; a chart-only fix
  still increments the product patch version. This is deliberate
  simplicity and can be revisited if components ever ship
  independently.
- First actual publication (registry push, signature, SBOM upload)
  requires operator credentials and is deferred to the first release
  tag; this batch delivers the pipeline, contract, and evidence, not
  a published artifact.
