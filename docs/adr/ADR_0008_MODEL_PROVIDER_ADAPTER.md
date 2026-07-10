# ADR-0008: Model Provider Adapter

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 24 owner)
**Markers:** TB-24, TR-13, TR-15, TR-24

## Context

Batch 24 activates the AI/MCP runtime live. Every reasoning step in the
runtime ultimately calls a large language model, and until now no
contract said which provider that is, how its credentials reach the
runtime, or how a deployment swaps providers. The platform invariants
constrain the answer:

- The core is cloud-agnostic and vendor-neutral. No provider-specific
  service is mandatory; provider integrations live under
  `adapters/providers/` only (repository hard constraint).
- Wrapped systems are configured, never forked. The `fork` wrap method
  is rejected across every adapter domain
  (`contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml`).
- Secrets resolve through the secrets backend adapter
  (`adapters/secrets/`); a credential literal in configuration or Git
  is a validation failure (TR-24).
- Live rehearsals run on the disposable kind harness (ADR-0007) and
  must never create billable resources or depend on external paid
  services; autonomous runs cannot hold a production LLM key.
- The AI boundary contract (`contracts/ai/BOUNDARY_CONTRACT_V1.yaml`)
  and the governance contracts under `contracts/policy/` stay
  authoritative for what agents may do. The model provider is a
  reasoning backend, never a data plane: no telemetry store access, no
  tool execution, no bypass of the MCP gateway.

The house adapter pattern is already proven four times (identity,
secrets, storage, network, billing): a compatibility contract, a stub
metadata file, rollback and uninstall notes, and a README per adapter
domain, with vendor-specific mapping isolated in adapter-scoped stub
files (`adapters/billing/STRIPE_REFERENCE_ADAPTER_STUB_V1.yaml` is the
closest exemplar).

## Decision

The LLM provider is pluggable behind a model-provider adapter under
`adapters/providers/model/`, following the house adapter pattern:

- `MODEL_PROVIDER_ADAPTER_COMPATIBILITY_V1.yaml` - the adapter domain
  contract entry: provider catalog, profile support, wrap methods.
- `STUB_METADATA.json` - adapter class, prerequisites, generated
  values, fallback behavior.
- `ROLLBACK_UNINSTALL_NOTES.md` - reversible activation semantics.
- `README.md` - operator-facing adapter documentation.

The runtime-facing interface is fixed by
`contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml`: a provider-
neutral invocation envelope (request and response), mandatory audit
fields, and key-resolution rules. The AI runtime (KAgent) consumes
providers only through that envelope; it never imports a vendor SDK
into the core and never names a vendor outside the adapter subtree.

The **Anthropic API is the reference adapter**
(`ANTHROPIC_REFERENCE_ADAPTER_STUB_V1.yaml`): a declarative mapping
stub from the neutral invocation envelope onto the Anthropic Messages
API, with the reference default model pinned as `claude-sonnet-5`
(overridable per profile through `model_ref` indirection, never
hardcoded in the runtime).

A **deterministic `local-stub` provider** ships alongside it for the
disposable harness: canned, contract-shaped completions keyed by
request intent, zero external calls, zero credentials. Live rehearsals
(TR-24) and CI never depend on a paid provider; production profiles
reject `local-stub` by contract.

**Provider keys resolve exclusively through the secrets backend
adapter.** Adapter entries carry `api_key_ref: secretref:...`
references; the secrets backend materializes them as Kubernetes
Secrets consumed via `secretKeyRef`. A literal key in any
configuration file, values file, or Git-tracked artifact is a seeded
rejection (`fail_if_inline_credential`,
`fail_if_git_tracked_credential`).

## Alternatives Considered

- **Hardcode one provider in the runtime.** Rejected: violates
  vendor-neutrality and the adapter boundary; any provider outage or
  commercial change would require a core release.
- **Wrap an upstream multi-provider proxy (LiteLLM-style) as a
  bundled system.** Rejected for now: adds a wrapped system with its
  own pin, upgrade, and security surface before any production demand
  exists; the envelope contract already isolates the runtime, so a
  proxy can be introduced later adapter-side without core changes.
- **Provider keys as ArgoCD-managed sealed values.** Rejected: the
  platform already has one secrets path (the secrets backend
  adapter); a second path weakens the deny-by-default posture and
  the TR-24 requirement that keys never appear in Git.

## Consequences

- The AI runtime carries a provider registry keyed by adapter name;
  adding a vendor is an adapter-subtree change plus a secrets backend
  entry - no core release, no contract mutation.
- The disposable harness rehearses the full trigger-to-approval flow
  with `local-stub`, so live evidence (Batch 24) is deterministic and
  free of external spend; production activation swaps to
  `anthropic-reference` by profile with keys via the secrets backend.
- The signoff workflow gains a measurable gate: the activation
  validator rejects any provider entry whose credentials do not
  resolve through `secretref:` indirection.
- `validate_ai_activation.sh` (Batch 24 Task 5) owns the structural
  enforcement of this ADR and its contract.
