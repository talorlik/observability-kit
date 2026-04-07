# Prompt - Rewrite Observability Docs for a Plug-and-Play K8s Platform

> Reference - Cloud-Agnostic and Open-Source Scope

## Role

You are adapting an existing observability project document set.

The current documents are only partially aligned with the target direction because
they are still too cloud-provider-specific and too dependent on manually wired
infrastructure assumptions.

Your task is to **rewrite the full document set** so it accurately describes a
**cloud-agnostic**, **open-source-first**, **plug-and-play** observability platform
installed on **Kubernetes**, whether on-premises or in any cloud.

## Objective

Transform the existing documents so the project is described as:

- cloud agnostic
- open-source first
- Kubernetes-native
- plug-and-play
- guided for installation and configuration
- capable of automatically discovering infrastructure and services
- capable of subscribing discovered workloads to observability with minimal manual
  work
- modular through provider-specific adapters rather than hard-coded provider assumptions

The rewritten output must still be technically rigorous, phased, testable, and
operationally realistic.

## Mandatory Guardrails

- Cloud agnostic
- Based on open-source tools
- Plug-and-play
- Easy guided installation and configuration
- Auto-discovery of infrastructure and services
- Installed on a Kubernetes cluster
- Valid for on-prem and cloud
- Markdown only

When there is conflict between the current documents and these guardrails, the
guardrails win.

## What Must Change

### 1. Remove cloud lock-in from the core architecture

Any current language that assumes a specific provider, managed service, or
provider-native prerequisite as part of the core design must be rewritten into
one of these forms:

- portable core platform capability
- optional provider adapter
- example deployment target
- reference implementation only

Do not leave the core architecture tied to:

- AWS
- EKS
- IAM/IRSA-only identity assumptions
- OSI as the only mandatory ingest path
- provider-native secret stores as the only supported option
- GitHub Actions as the only CI/CD mechanism
- provider-native networking as a universal requirement

### 2. Reframe the platform around Kubernetes

The main platform boundary is the Kubernetes cluster.

The rewritten documents must treat Kubernetes as the place where the platform:

- installs
- discovers capabilities
- discovers workloads
- subscribes services
- enforces onboarding policy
- runs collection and control-plane components

### 3. Make installation guided and productized

The documents must describe a guided install process, not just manual implementation
steps.

The rewritten documents must include:

- prerequisite validation
- preflight checks
- discovery of cluster capabilities
- compatibility assessment
- recommended install mode
- generated configuration or values
- post-install smoke tests
- rollback/uninstall path

### 4. Make discovery a first-class feature

The platform must automatically detect as much as reasonably possible.

The rewritten documents must explicitly define discovery for at least:

- cluster version and distribution
- node topology
- storage classes
- ingress/gateway capabilities
- GitOps controller presence
- secret management integrations
- namespaces and workload inventory
- services and endpoints
- scrape candidates
- telemetry-ready workloads
- ownership labels or metadata when available
- platform prerequisites already present vs missing

The documents must also define the outputs of discovery, such as:

- capability matrix
- discovery report
- install recommendation
- generated defaults
- list of candidate workloads for subscription/onboarding
- remediation list for missing prerequisites

### 5. Make "subscription" explicit

The platform should be able to subscribe workloads to observability with minimal
friction.

The rewritten documents must distinguish between:

- passive zero-code onboarding
- annotation/values-based onboarding
- instrumentation-required onboarding

They must define which signals can be discovered automatically and which still
require explicit application participation.

### 6. Use open-source-first component choices

The rewritten documents must default to open-source components and self-hostable
patterns.

Acceptable default categories include:

- OpenTelemetry Collector
- Helm
- Argo CD or Flux
- OpenSearch
- OpenSearch Dashboards
- Grafana as a core visualization component
- Kyverno or OPA Gatekeeper
- External Secrets Operator / Sealed Secrets / CSI secret integrations
- open-source graph module if graph capability remains in scope

Managed services may be mentioned only as optional adapters or deployment targets.

### 7. Introduce a provider adapter model

The rewritten documents must describe a **portable platform core** plus
**optional adapters**.

At minimum, define this split:

- core platform
- cloud/provider adapters
- secrets adapters
- identity adapters
- storage adapters
- ingress/network adapters
- CI/CD adapters

Provider adapters must not be mixed into the core architecture narrative.

## Required Rewrites by Document Type

### A. Plan / Executive Architecture documents

Rewrite them so they:

- describe a Kubernetes-native platform product
- present cloud-neutral architecture variants
- compare variants by portability, lock-in, operator burden, and install complexity
- add deployment modes such as quickstart, attach, standalone, and hybrid
- define a discovery engine and guided install flow
- define a provider adapter model
- keep the same level of technical detail, validation rigor, and rollout logic

### B. PRD documents

Rewrite them so they:

- make guided installation a product feature
- make discovery a product feature
- make compatibility reporting a product feature
- make self-service onboarding a product feature
- make provider neutrality an explicit product requirement
- define measurable outcomes such as reduced manual inputs, reduced onboarding
  effort, and install success across different Kubernetes environments

### C. Technical requirements documents

Rewrite them so they:

- separate platform core from adapters
- define discovery architecture and subscription flow
- define portable identity, secrets, storage, and networking patterns
- define deployment modes and compatibility model
- define onboarding controls, policy enforcement, and validation
- describe open-source-first backend and visualization choices
- keep detailed runtime contracts and operational controls

### D. Task / backlog documents

Rewrite them so the early batches focus on:

1. install contract redesign
2. capability matrix
3. preflight framework
4. discovery engine
5. guided install/config generation
6. provider adapter abstraction
7. subscription/onboarding framework
8. validation, smoke tests, rollback, uninstall
9. storage/search/graph backend implementation details
10. advanced AI or graph phases later

Do not start the backlog with one cloud provider's attach mode unless the source
explicitly needs a provider adapter backlog section.

### E. Prompts and instruction documents

Rewrite them so future generations also stay aligned with this direction.

They must explicitly instruct the model to:

- avoid provider lock-in
- prefer open-source defaults
- preserve Kubernetes-first thinking
- require discovery-led install and onboarding
- maintain technical rigor

## Preserve and Improve

While rewriting, preserve what is still useful from the existing documents,
including where applicable:

- phased rollout logic
- validation requirements
- rollback expectations
- operational readiness
- backlog discipline
- acceptance criteria
- risk management
- AI/graph roadmap ordering
- onboarding contract concepts

But adapt them so they now serve a cloud-neutral, open-source, Kubernetes-first
platform.

## Architecture Direction to Prefer

Use this as the default direction unless the existing source clearly requires
another justified variant:

### Core platform

- Kubernetes-native runtime
- Helm-delivered components
- GitOps support through Argo CD or Flux
- OpenTelemetry Collector as the sole collector path
- agent and/or gateway topology as justified
- OpenSearch as the default open-source search/analytics backend
- OpenSearch Dashboards as core UI for logs and trace analytics
- Grafana as core UI for metrics-first, SLO, NOC, and executive dashboards
- optional graph layer as a derived module
- installer/discovery/control layer for guided setup
- smoke-test and validation bundle

### Deployment modes

Define at least:

- Quickstart
- Attach
- Standalone
- Hybrid

### Discovery engine responsibilities

Define at least:

- environment detection
- prerequisite checks
- compatibility scoring
- generated recommendations
- default values generation
- candidate workload discovery
- install report
- post-install verification

### Subscription model

Define at least:

- logs: passive stdout/stderr collection
- metrics: discovered scrape targets and opt-in configuration
- traces: explicit instrumentation or auto-instrumentation where supported

## Required New Sections to Add When Missing

If the source documents do not already contain them, add sections for:

- compatibility goals
- deployment modes
- discovery scope
- discovery outputs
- guided installation flow
- subscription model
- provider adapters
- backend support strategy
- self-service onboarding
- uninstall and rollback
- upgrade compatibility
- extension model
- operator troubleshooting and support boundaries

## Output Requirements

- Rewrite the documents directly
- Keep everything in Markdown
- Preserve the original document names where possible
- Preserve numbering and cross-reference markers where practical
- Remove stale provider-specific contradictions
- State assumptions explicitly
- Include validation steps and rollback guidance
- Keep the output ready for real project use

Do not output analysis about the rewrite process.
Do not output a summary of what you changed unless explicitly asked.
Do not leave TODO-style placeholders unless the source genuinely lacks information.

## Priority Order for Decisions

When choosing how to rewrite, use this priority order:

1. Cloud agnostic
2. Open-source first
3. Plug-and-play usability
4. Guided installation and configuration
5. Auto-discovery and self-service onboarding
6. Kubernetes-native portability
7. Clear separation between core platform and adapters
8. Preservation of useful existing project intent

## Final Instruction

Rewrite the current document set so that a reader would conclude all of the following:

- The platform runs on Kubernetes in cloud or on-prem.
- The design does not depend on one provider.
- The default architecture is based on open-source tooling.
- Installation is guided and practical.
- The system auto-discovers infrastructure and workloads.
- The platform can subscribe workloads to observability with minimal manual work.
- Provider-specific integrations are optional adapters.
- The documents remain concrete, testable, and implementation-ready.
