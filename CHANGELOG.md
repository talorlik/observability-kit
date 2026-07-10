# Changelog

All notable changes to the Observability Kit are documented in this
file. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and
the project adheres to
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) as
fixed by `contracts/release/RELEASE_ENGINEERING_CONTRACT_V1.yaml`.
Releases are tag-driven (`v<MAJOR>.<MINOR>.<PATCH>`); a tag without a
matching dated section here fails the release gate.

## [Unreleased]

### Added

- Guided installer (`obskit install`) executing the seven-step install
  flow contract, with preflight, compatibility grading, and GitOps-only
  rendered output (Batches 17-18).
- Configuration rendering runtime (`obskit render`, `obskit drift`,
  `obskit rollback`) executing the unified-configuration propagation
  contract deterministically (Batch 19).
- Tenant control plane service (`tenantctl`) executing the tenant
  lifecycle contract with approval flow and audit integration
  (Batch 20).
- Unified management portal (`portalsvc`) with SSO via the admin
  access plane, unified config editing, tenant management, and health
  overview (Batch 21).
- Usage metering, plan catalog, billing adapter boundary, and invoice
  export (Batch 22).
- Disposable live-cluster evidence harness with committed install,
  drill, GUI smoke, and cross-tenant denial evidence (Batch 23).
- Live AI/MCP runtime activation: `obskit-ai-runtime` image, model
  provider adapter boundary, rehearsal and signoff evidence
  (Batch 24).
- Release engineering: this changelog, the release engineering
  contract, tag-driven release workflow with SBOM generation and
  image scanning, license compliance contract, production reference
  architecture, platform product SLOs, and resolved wrapped-system
  version pins (Batch 25).

### Changed

- Wrapped-system registry entries for `opensearch`,
  `opensearch-dashboards`, and `argocd` moved from `to-be-pinned`
  placeholders to concrete harness-proven version pins (Batch 25).
