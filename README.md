# Observability Kit

A portable, plug-and-play observability intelligence platform for existing
AWS EKS clusters.

## Ultimate Goal

Deliver one repeatable platform that can be installed from a personal machine
or GitHub Actions with consistent outcomes, while enforcing these constraints:

- OpenTelemetry is the sole collector for logs, metrics, and traces
- Amazon OpenSearch is the single telemetry and vector store
- Amazon OpenSearch Ingestion (OSI) is the managed ingest path
- Neo4j is a derived graph tier, not a raw telemetry store
- Delivery is Terraform plus Helm plus ArgoCD Applications

The platform also provides a phased path from core observability to
AI-assisted incident analysis, with deterministic graph and risk capabilities
before optional LLM-assisted RCA.

## Primary Planning Documents

- `docs/auxiliary/planning/OBSERVABILITY_PLATFORM.plan.md`
- `docs/auxiliary/planning/PRD.md`
- `docs/auxiliary/planning/TECHNICAL.md`
- `docs/auxiliary/planning/TASKS.md`

## Batch 1 Delivery Foundation

Batch 1 establishes delivery controls and baseline artifacts mapped to
`TR-10` and `TR-14`.

- Install contract schema:
  `contracts/install/INSTALL_CONTRACT_SCHEMA.json`
- Install contract samples:
  `contracts/install/samples/`
- GitOps baseline:
  `gitops/README.md`
- Default Argo CD application:
  `gitops/apps/platform-core-application.yaml`
- CI workflow:
  `.github/workflows/ci.yml`

## Batch 2 Compatibility And Modes

Batch 2 defines environment compatibility, profile catalogs, grading behavior,
mode selection logic, and remediation mappings for `TR-04`, `TR-05`, and
`TR-14`.

- Compatibility and profile artifacts:
  `contracts/compatibility/`
- Batch 2 validation script:
  `scripts/ci/validate_compatibility_and_modes.sh`
- Operator guide:
  `docs/runbooks/COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md`

## Batch 3 Preflight And Discovery Engine

Batch 3 adds guided preflight checks, discovery probe outputs, generated
capability and compatibility artifacts, and a readiness scaffold contract for
`TR-04`, `TR-05`, and `TR-10`.

- Preflight and discovery artifacts:
  `contracts/discovery/`
- Batch 3 validation script:
  `scripts/ci/validate_preflight_and_discovery.sh`
- Batch 3 smoke wrapper:
  `scripts/ci/validate_batch3_smoke.sh`
- Operator guide:
  `docs/runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md`

## Baseline Runbooks

- `docs/runbooks/INSTALL_RUNBOOK.md`
- `docs/runbooks/VALIDATION_RUNBOOK.md`
- `docs/runbooks/ROLLBACK_RUNBOOK.md`
- `docs/runbooks/COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md`
- `docs/runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md`
