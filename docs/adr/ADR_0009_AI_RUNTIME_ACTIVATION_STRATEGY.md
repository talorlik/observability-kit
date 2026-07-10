# ADR-0009: AI Runtime Activation Strategy

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 24 owner)
**Markers:** TB-24, TR-15, TR-24

## Context

Batch 24 Task 2 requires KAgent, KHook, and the MCP gateway to deploy
from `gitops/platform/ai/` onto a Batch 23 harness cluster with the
MCP catalog and governance contracts enforced unmodified. The Batch 14
scaffolding manifests reference container images that were placeholders
(`ghcr.io/kagent-dev/{kagent,khook,kmcp,agentgateway}:v0.1.0`); none of
those tags exist in any public registry, and for KHook no public image
exists at all under any tag. Activation therefore forces a real
technology choice that Batch 14 deferred: what actually runs inside the
AI runtime pods.

Facts that bound the decision:

- The wrapped-system registry
  (`contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml`)
  deliberately does not list KAgent, KHook, or the MCP gateway. They
  are not wrapped upstream systems; the AI/MCP sub-plan
  (`docs/auxiliary/planning/kagent_khook/`) scopes them as the
  product's own control plane, with "replaceability by contract at
  every layer" as a product principle.
- The upstream `kagent-dev` open-source ecosystem exists and publishes
  images for some components (`kagent/controller`, `kmcp/controller`,
  `agentgateway`), but not KHook, and its runtime requires its own
  CRDs, its own configuration model, and a live LLM provider - none of
  which our governance contracts (`contracts/policy/`,
  `contracts/mcp/`) would then enforce. Our contracts are the product;
  an upstream controller does not execute them.
- Batches 17-23 established the runtime pattern: typed, stdlib-core
  Python services owned by this repository (`obskit`, `tenantctl`,
  `portalsvc`, `commercialsvc`) that execute the contracts verbatim.
- Live evidence must be deterministic, free of billable external
  calls, and produced only on the disposable harness (ADR-0007,
  ADR-0008).

## Decision

The AI runtime tier is activated as an **in-house, contract-executing
runtime**: one typed Python package (`airuntime`) under
`services/ai/`, built into a single container image
(`obskit-ai-runtime`) with four entrypoints - `kagent` (controller and
casefile orchestrator), `khook` (event trigger dispatcher), `gateway`
(MCP gateway), and `mcpserver` (read-path MCP tool host). The
`gitops/platform/ai/` base deployments keep their names, namespaces,
service accounts, and network policies; their image references move to
the product-owned image, pinned per overlay. On the disposable
harness the image is built locally and side-loaded with
`kind load docker-image`; no registry publication happens before Batch
25 release engineering.

The runtime executes the existing contracts without reinterpretation:
the MCP catalog and tool response envelope (`contracts/mcp/`), the
governance contracts (`contracts/policy/`: identity-access,
tool risk classification, action preconditions, approval flow with its
timeout and escalation rules, audit), the casefile and boundary
contracts (`contracts/ai/`), the KHook trigger catalog with dedupe and
burst control (`triggers/khook/`), and the model provider adapter
contract (ADR-0008, `local-stub` on the harness).

Persistence follows `contracts/ai/KAGENT_PERSISTENCE_CONTRACT_V1.yaml`:
PostgreSQL in-cluster, reached through the contract's
`kagent-postgres-credentials` secret. The store driver is behind a
`[postgres]` optional extra (pure-Python `pg8000`), mirroring the
`[api]`/`[k8s]` extra pattern of the other services; offline CI tests
run against an interface-identical SQLite store and never install the
extra. The scaffolding deployment's secret reference is corrected to
the contract's secret name (the contract wins over scaffolding).

Upstream `kagent-dev` remains the designated replacement candidate:
the replaceability matrix (`contracts/ai/REPLACEABILITY_MATRIX_V1.md`)
already frames every layer as swappable behind its contract, and the
in-house runtime adds no contract surface an upstream adoption would
not also have to satisfy.

## Alternatives Considered

- **Pin the real upstream kagent-dev images.** Rejected for
  activation: KHook has no published image; the upstream controllers
  require their own CRD surface and configuration model that our
  governance contracts do not cover, so catalog and policy enforcement
  would be claimed but not real; and upstream kagent requires a live
  LLM provider, which the harness forbids. Revisit behind the
  replaceability matrix once upstream ships a complete, pinnable set.
- **Build upstream KHook from source into a private image.** Rejected:
  wraps a moving, unreleased codebase the product would have to
  maintain a build pipeline for, without gaining contract enforcement.
- **Declare activation done with fixtures (no live deployment).**
  Rejected: TR-24 explicitly replaces declared fixtures with captured
  live evidence; that is the entire point of Batches 23-24.

## Consequences

- The four placeholder image references in `gitops/platform/ai/base/`
  change to product-owned references; scaffolding validators are
  unaffected (none assert image strings - verified before this ADR).
- `services/ai/` joins the AI-boundary scan surface of
  `validate_ai_boundary_contracts.sh` so datastore-coupling rules
  apply to the runtime code itself.
- The platform gains a runnable AI tier with zero external
  dependencies on the harness, and a contracted seam (ADR-0008 model
  provider adapter) where production deployments plug a real LLM.
- Batch 25 release engineering inherits an image build target for
  `obskit-ai-runtime` alongside chart packaging.
- Production-activation scope, deliberately not closed by the
  harness activation: the logical agents of the catalog run inside
  the single kagent-controller pod under `sa-agent-ceo` (the
  identity matrix's per-agent service accounts gain runtime
  counterparts when agents split into their own workloads), and
  component-to-component calls trust the envelope's `caller_agent`
  behind network policies rather than authenticated identities. The
  gateway enforces the agent tool bindings (default deny) on every
  invocation regardless.
