# Product Documentation Index

This index establishes the `docs/product/` tree: the customer-facing
documentation set for the Observability Kit SaaS platform. Every
document in the tree is listed here with its audience and scope. The
tree is validated by `scripts/ci/validate_product_docs.sh`, which
fails when a listed document is missing, when a shipped capability
lacks a product doc section, or when a link in the tree is broken.

Operator-facing runbooks (per-batch, under `docs/runbooks/`) and
planning documents (under `docs/auxiliary/planning/`) are internal
engineering surfaces and are deliberately outside this tree.

## Audience Map

The product recognizes five audiences. Every document below serves at
least one of them; every audience has at least one document.

| Audience | Who they are | Primary documents |
| ---- | ---- | ---- |
| Evaluator | Assessing the product before adopting it | [Getting Started](GETTING_STARTED.md), [Demo Playground Guide](PLAYGROUND_GUIDE.md) |
| Installer and operator | Platform operators and SREs who install, configure, and run the platform | [Installation Guide](INSTALLATION_GUIDE.md), [Configuration Guide](CONFIGURATION_GUIDE.md), [Operations Guide](OPERATIONS_GUIDE.md), [Demo Playground Guide](PLAYGROUND_GUIDE.md) |
| Tenant administrator | SaaS operators and tenant administrators managing tenant lifecycles | [Tenant Admin Guide](TENANT_ADMIN_GUIDE.md), [API Reference](API_REFERENCE.md) |
| End user | Tenant end users consuming dashboards, queries, and alerts | [End User Guide](END_USER_GUIDE.md) |
| Commercial administrator | Commercial, sales, and support teams operating plans, billing, and onboarding | [Pricing and Packaging](PRICING_AND_PACKAGING.md), [Support and Onboarding](SUPPORT_AND_ONBOARDING.md) |

## Document Tree

| Document | Audience | Scope |
| ---- | ---- | ---- |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Evaluator; first-time installer and operator | What the product is, prerequisites, and the quickstart path to a running platform |
| [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) | Installer and operator | Full guided-installer reference: interactive and non-interactive flows, modes, preflight remediation |
| [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) | Installer and operator | Unified configuration document reference, propagation model, drift handling, rollback |
| [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md) | Installer and operator | Day-2 operations: upgrades, drills, drift response, evidence capture, releases |
| [TENANT_ADMIN_GUIDE.md](TENANT_ADMIN_GUIDE.md) | Tenant administrator | Tenant lifecycle, isolation classes, quotas, overlays, offboarding and purge |
| [END_USER_GUIDE.md](END_USER_GUIDE.md) | End user | Using the portal and wrapped UIs: dashboards, queries, alerts, AI-assisted analysis |
| [API_REFERENCE.md](API_REFERENCE.md) | Tenant administrator; integration engineers | Control-plane API reference, generated from the tenant control plane OpenAPI contract |
| [PRICING_AND_PACKAGING.md](PRICING_AND_PACKAGING.md) | Commercial administrator | Plan and tier catalog, metering dimensions, billing adapter options, invoice export |
| [SUPPORT_AND_ONBOARDING.md](SUPPORT_AND_ONBOARDING.md) | Commercial administrator; support engineers | Triage flows, known failure modes, escalation paths, customer onboarding |
| [GA_READINESS_REVIEW.md](GA_READINESS_REVIEW.md) | Installer and operator; commercial administrator | Signed, evidence-backed GA readiness review against the productization definition of done |
| [PLAYGROUND_GUIDE.md](PLAYGROUND_GUIDE.md) | Evaluator; installer and operator | Demo playground walkthrough: platform install or dev-stack reuse, demo deploy, traffic scenarios, dashboards, AI prompts, teardown |

## Reading Paths

- Evaluating the product: start with
  [Getting Started](GETTING_STARTED.md), then skim
  [Pricing and Packaging](PRICING_AND_PACKAGING.md).
- Evaluating with live data: the
  [Demo Playground Guide](PLAYGROUND_GUIDE.md).
- Standing up a platform: [Getting Started](GETTING_STARTED.md), then
  the [Installation Guide](INSTALLATION_GUIDE.md), then the
  [Configuration Guide](CONFIGURATION_GUIDE.md).
- Running the platform day 2: the
  [Operations Guide](OPERATIONS_GUIDE.md).
- Serving tenants: the [Tenant Admin Guide](TENANT_ADMIN_GUIDE.md)
  and the [API Reference](API_REFERENCE.md) for automation.
- Using the platform as a tenant: the
  [End User Guide](END_USER_GUIDE.md).
- Charging for the platform:
  [Pricing and Packaging](PRICING_AND_PACKAGING.md), then
  [Support and Onboarding](SUPPORT_AND_ONBOARDING.md).

## Conventions

- File names are `UPPERCASE_WITH_UNDERSCORES.md` per the repository
  markdown standard, and every file passes
  `scripts/ci/validate_markdown.sh`.
- Guides document delivered behavior only. Statements derive from the
  contracts under `contracts/`, the runtimes under `tools/` and
  `services/`, and captured evidence under `artifacts/evidence/` -
  never from aspirations.
- The [API Reference](API_REFERENCE.md) is generated from
  `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` and carries a
  generated-file marker; edit the contract, not the reference.
