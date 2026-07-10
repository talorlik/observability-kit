# Production Release Gate Runbook

Operate a product release: run the release-gate checklist, cut the
tag, drive the publication workflow, and handle wrapped-system pin
bumps and upgrade testing. Contract:
`contracts/release/RELEASE_ENGINEERING_CONTRACT_V1.yaml` (TR-25);
decision record: `docs/adr/ADR_0010_RELEASE_ENGINEERING.md`.

## Scope

- Releases are tag-driven and operator-initiated. Merges to `main`
  never publish; autonomous batch runs never tag, push, or publish.
- One product version: the Git tag `v<MAJOR>.<MINOR>.<PATCH>` sets
  the `platform-core` chart version, `appVersion`, and every
  product-owned image tag. Pre-GA releases stay in `0.y.z`; `1.0.0`
  is cut only by the Batch 26 GA readiness review.
- Repository CI validates the release surfaces structurally via
  `scripts/ci/validate_release_engineering.sh`; nothing in this
  runbook gates pull requests.

## Release-Gate Checklist

Execute in order. Every item must pass before the tag is cut; the
gate ids are fixed by `release_gates.required` in the release
contract.

1. `validators-green`: run
   `bash scripts/ci/validate_all_batches_with_report.sh` and confirm
   the report under `docs/reports/validation/` is green for every
   registered batch.
2. `changelog-section`: `CHANGELOG.md` carries a dated
   `## [<version>] - <YYYY-MM-DD>` section for the release version,
   curated from the `Unreleased` section per Keep a Changelog 1.1.0.
3. `pins-concrete`: no enabled wrapped system in
   `contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml` has
   `version_pin.status: to-be-pinned`
   (`bash scripts/ci/validate_management_plane_contracts.sh` plus the
   pin lockstep check inside
   `bash scripts/ci/validate_release_engineering.sh`).
4. `license-inventory-complete`: every bundled system appears in
   `contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml` with
   obligations reviewed, and `THIRD_PARTY_NOTICES.md` matches the
   inventory (cross-checked by the release validator).
5. `sbom-and-scan`: SBOMs and image scans are produced by the
   publication workflow (below); a CRITICAL finding without a dated
   waiver entry in this checklist run fails the release. Record any
   waiver here with CVE id, reason, and remediation deadline.
6. `harness-install-evidence`: the pinned set installed cleanly on
   the disposable harness with committed evidence
   (`artifacts/evidence/batch25/release/release_pins.json`,
   `status: pass`). Re-capture on any pin bump (see below).
7. `upgrade-evidence`: the N-1 to N upgrade drill passed with
   committed evidence
   (`artifacts/evidence/batch25/upgrade/upgrade_drill.json`,
   `status: pass`).
8. `slo-budget-state`: product SLO error budgets per
   `contracts/slo_ops/PLATFORM_PRODUCT_SLO_V1.yaml` are reviewed; an
   exhausted budget freezes the release unless the release itself is
   the corrective action.

## Tag-to-Publication Flow

1. Confirm the checklist above is fully green.
2. Move the curated `Unreleased` entries into the new dated section
   in `CHANGELOG.md`; set the chart `version` and `appVersion` in
   `gitops/charts/platform-core/Chart.yaml` to the release version.
   Land both through the normal branch and review flow.
3. Cut the tag on the release commit: `git tag v<version>` and push
   the tag to the repository remote. Pushing the tag (not any
   branch) triggers `.github/workflows/release.yaml`.
4. The workflow runs its stages per the release contract: verify
   (validators, changelog section), package (`helm package` of
   `platform-core`, `docker build` of `obskit-ai-runtime` at the tag
   version), sbom-and-scan (syft SPDX 2.3 JSON per artifact; trivy
   scan failing on CRITICAL), publish (chart and image push to the
   configured OCI registry, cosign keyless signing).
5. Publication requires registry credentials
   (`RELEASE_REGISTRY_USERNAME` / `RELEASE_REGISTRY_PASSWORD`
   secrets and the `RELEASE_REGISTRY_HOST` variable, default GHCR).
   Without them the publish stage no-ops with an explanatory log -
   packaging, SBOM, and scan still run and upload their artifacts.
6. Verify signatures after the first publication:
   `cosign verify` against the workflow OIDC identity, as recorded
   in the workflow logs. Consumer-side enforcement stays optional in
   v1 per the signing posture.
7. Attach the SBOMs and scan reports to the release record and
   confirm the changelog section, evidence paths, and artifact
   digests are consistent.

## Wrapped-System Pin Bumps

Pins converge on harness-proven versions (ADR-0010). To bump
`opensearch`, `opensearch-dashboards`, or `argocd`:

1. Update the harness source of truth first:
   `scripts/dev/harness_assets/backend-opensearch.yaml` (both
   OpenSearch images) or the `ARGOCD_MANIFEST` pin in
   `scripts/dev/live_cluster_harness.sh`, plus the matching values
   in `contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml`.
2. Update `version_pin.value` (and the verification note) in
   `contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml`; verify
   the tag exists upstream before pinning.
3. Re-capture evidence on a fresh harness:
   `create`, `run --only install`, `run --only release-pins`,
   `run --only upgrade-drill`, `teardown` via
   `scripts/dev/live_cluster_harness.sh` (see
   `docs/runbooks/LIVE_VALIDATION_RUNBOOK.md` for harness
   operation).
4. Run `bash scripts/ci/validate_release_engineering.sh`; the pin
   lockstep check fails loudly if registry, harness, and evidence
   disagree.
5. A pin bump is a MINOR version increment per the release
   contract's increment rules.

## Upgrade Testing

The N-1 to N upgrade drill runs on the disposable harness:

1. `bash scripts/dev/live_cluster_harness.sh create` and
   `run --only install` (the harness publishes committed state
   only - commit release work before capturing evidence).
2. `bash scripts/dev/live_cluster_harness.sh run --only
   upgrade-drill`. The drill installs the previous release state
   (the newest `v*` tag; for the inaugural release the pre-Batch-25
   `main` state; `UPGRADE_BASELINE_REF` overrides for rehearsals),
   seeds an OpenSearch document, records configuration checksums,
   upgrades to the current state through GitOps only, and asserts
   data and configuration survive and the collectors roll to the new
   chart version label.
3. Evidence lands in
   `artifacts/evidence/batch25/upgrade/upgrade_drill.json` and is
   committed; `run --only release-pins` refreshes the pinned-set
   evidence alongside it.
4. `bash scripts/dev/live_cluster_harness.sh teardown` when done.

## License and SBOM Gates

- The license review workflow, per-license obligations, and the
  attribution requirement are fixed by
  `contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml`. Re-review
  on: a new bundled system, a pin bump, or an upstream license
  change. Commercial distribution is blocked while a review is
  incomplete.
- Notable obligations: Grafana is AGPL-3.0 (referenced upstream
  image, never redistributed or modified); Neo4j multi-database
  isolation requires the customer's own Enterprise license in
  production (the harness uses the evaluation license on disposable
  clusters only); Terraform is operator-supplied tooling under
  BUSL-1.1 and is not bundled.
- SBOMs are SPDX 2.3 JSON via syft, one per published artifact;
  scans are trivy with a CRITICAL gate. Both run in the release
  workflow and their reports are release artifacts.

## Production Deployment Reference

Production installs follow
`contracts/release/PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml` (HA
topology, sizing tiers, storage and ingress profiles, backup and DR
posture, `prod` overlay mapping) with the same guided installer -
the stack differs by profile, never by code path. A production
cluster must grade `supported` in the compatibility matrix and pass
preflight before any release is deployed to it.

## Rollback

- A published release is never unpublished; a bad release is
  superseded by a patch release through the same gate flow.
- Cluster-level rollback of a deployed upgrade is the GitOps
  revision rollback drill (`docs/runbooks/ROLLBACK_RUNBOOK.md`); the
  restore path is `docs/runbooks/DR_RESTORE_RUNBOOK.md`.
