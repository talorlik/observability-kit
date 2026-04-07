# VISUALIZATION LAYER AUGMENTATION PROMPT

## CONTEXT

I have an observability platform project with multiple existing planning and delivery
documents.
I want you to augment and align all of them so they consistently reflect the latest
intended architecture and product direction.

## REFERENCES

- @docs/auxiliary/AI_prompts/SYSTEM_INSTRUCTIONS_DOCS.md
- @docs/auxiliary/planning/OBSERVABILITY_PLATFORM_V2.plan.md
- @docs/auxiliary/planning/PRD.md
- @docs/auxiliary/planning/TECHNICAL.md
- @docs/auxiliary/planning/TASKS.md
- @docs/auxiliary/planning/IMPLEMENTATION_TASKS.md

## PRIMARY OBJECTIVE

Rewrite and augment the existing documentation set so it describes a cloud-agnostic,
open-source-first, Kubernetes-native, plug-and-play observability platform with
a much stronger and explicit visualization layer.

## IMPORTANT

- Treat SYSTEM_INSTRUCTIONS_DOCS.md as mandatory governing instructions for the
  documentation rewrite.
- Do not summarize the existing docs.
- Do not produce commentary about the changes.
- Directly update the documents so they are internally consistent, execution-ready,
  and free of contradictions.
- Preserve useful existing structure where practical, but change anything necessary
  to align the docs with the updated architecture.
- All output must remain in Markdown.

## NON-NEGOTIABLE PLATFORM DIRECTION

1. The platform must be cloud agnostic.
2. The platform must be open-source-first.
3. The platform must be Kubernetes-native.
4. The platform must be plug-and-play.
5. The platform must support guided installation and configuration.
6. The platform must auto-discover the environment and onboarding candidates.
7. Provider-specific integrations must be described as adapters, not as part of
  the core architecture.
8. The documentation must remain rigorous, implementation-oriented, phased, and
  operationally realistic.

## VISUALIZATION LAYER - REQUIRED CHANGES

The current documentation over-emphasizes OpenSearch Dashboards and treats Grafana
as optional. That must be corrected.

Update the architecture so the visualization layer is explicitly multi-tool by
design, with clear role ownership per tool and per use case.

## REQUIRED VISUALIZATION MODEL

Core visualization/admin tools:

- OpenSearch Dashboards
  - Core
  - Primary UI for log search, event analytics, OpenSearch-native observability
    workflows, trace analytics, and log-trace correlation
- Grafana
  - Core
  - Mandatory, not optional
  - Primary UI for metrics-first dashboards, operational overview dashboards,
    NOC/SRE dashboards, executive dashboards, cross-source dashboards, dashboard
    templating, annotations, and alerting workflows
- Neo4j Browser
  - Core
  - Mandatory graph admin and investigation UI
  - Primary UI for dependency exploration, blast-radius analysis, ownership traversal,
    topology understanding, and graph-backed RCA workflows

Optional specialist/admin tools:

- Jaeger UI
  - Optional
  - Specialist trace-investigation UI for deeper trace-centric troubleshooting,
    dependency graphs, and advanced trace debugging if later justified
- Neo4j Bloom
  - Optional
  - Specialist graph exploration/presentation UI for richer and lower-code graph
    navigation and broader stakeholder usability

## VISUALIZATION OWNERSHIP BY SIGNAL / USE CASE

- Logs -> OpenSearch Dashboards
- Metrics -> Grafana
- Traces -> OpenSearch Dashboards by default; Jaeger UI optional later
- Topology / dependency graph / blast radius / relationship exploration -> Neo4j
  Browser by default; Neo4j Bloom optional
- Executive summary / service health / SLO / NOC boards -> Grafana

## ADMIN GUI EXTERNALIZATION - REQUIRED CHANGES

The platform must explicitly externalize the admin GUIs of the relevant tools so
operators can navigate to them, log in, configure them, and perform platform
administration without requiring direct shell access to the cluster.

The docs must describe an admin access plane that externalizes the following GUIs:

- OpenSearch Dashboards
- Grafana
- Neo4j Browser
- Jaeger UI if enabled
- Neo4j Bloom if enabled
- ArgoCD UI
- Other approved future admin GUIs introduced by platform modules

## ADMIN ACCESS MODEL - REQUIRED CHARACTERISTICS

- Admin GUIs must be exposed via Kubernetes-native ingress mechanisms:
  - Ingress and/or Gateway API
- The platform must support both:
  - dedicated admin subdomains
  - path-based exposure where appropriate
- TLS is mandatory for every externally reachable admin GUI
- Authentication should be centralized where possible:
  - OIDC preferred
  - SAML acceptable as an adapter/integration path
- Authorization must map roles/groups into each tool’s RBAC model
- Default posture should not be public internet exposure
- Preferred access posture:
  - private/internal ingress or load balancer
  - VPN / ZTNA / corporate access path
  - tightly restricted exposure with SSO and MFA if internet-facing access is ever
    permitted
- The docs must cover:
  - reachability model
  - authn/authz model
  - auditability
  - session/security considerations
  - break-glass admin access
  - smoke tests for GUI reachability and login
- Keep the core architecture provider-neutral
- Describe cloud/provider-specific exposure patterns only as adapters

## REQUIRED DOCUMENT TRANSFORMATIONS

Apply all of the following across the entire document set.

1. Visualization Plane
Add an explicit Visualization Plane section to the architecture and make it a
first-class architectural concern rather than an implicit side effect of storage
or telemetry ingestion.

2. Grafana as Core
Remove any wording that implies Grafana is optional in the base platform.
Grafana must be a core platform component.

3. Multi-tool Visualization Strategy
Explicitly describe that visualization is multi-tool by design.
OpenSearch Dashboards is not the single universal UI.
Each tool has a role.

4. Graph Visualization/Admin
If Neo4j is part of the platform, Neo4j Browser must be part of the core admin and
investigation layer. Neo4j Bloom must be optional.

5. Externalized Admin GUIs
Add a dedicated section that defines how all admin GUIs are externally reachable
in a secure, operator-friendly way.

6. Cloud-neutral Core + Adapters

Any current AWS-centric ingress, auth, or exposure assumptions must be rewritten
into:

    - core platform behavior
    - optional provider-specific adapter patterns

7. Guided Installation and Discovery

The install and onboarding experience must mention and account for the visualization/admin
layer as part of:

    - preflight checks
    - capability detection
    - generated configuration
    - external access recommendations
    - smoke tests
    - post-install validation

8. Tasks and Implementation Work

Add all visualization/admin-access work into the tasks and implementation backlog
in the correct order. Do not leave this as vague future work.

## DOCUMENT-SPECIFIC REQUIREMENTS

### A. PLAN DOCUMENT

Update the plan so it:

- includes the visualization plane as an explicit architectural layer
- makes Grafana core
- keeps OpenSearch Dashboards core
- makes Neo4j Browser core if Neo4j is included
- makes Jaeger UI optional
- makes Neo4j Bloom optional
- introduces the external admin GUI access model
- explains the rationale for multi-tool visualization in operational terms
- includes rollout sequencing for these capabilities
- includes validation, risk, trade-offs, and rollback considerations for
  visualization/admin exposure

### B. PRD

Update the PRD so it:

- treats visualization as a product capability, not just an implementation detail
- includes operator/admin GUI usability as a product requirement
- includes secure external admin access as a product capability
- includes Grafana as a required feature, not optional
- includes graph exploration/admin capability requirements
- includes acceptance criteria for:
  - dashboard usability
  - role-based access
  - GUI reachability
  - configuration/admin workflows
  - visibility across logs, metrics, traces, and graph relationships
- includes measurable outcomes tied to reduced manual effort and operator usability

### C. TECHNICAL DOCUMENT

Update the technical document so it:

- defines a dedicated visualization plane
- clearly allocates responsibilities across OpenSearch Dashboards, Grafana, Neo4j
  Browser, Jaeger UI, and Neo4j Bloom
- defines how admin GUIs are exposed
- defines the authn/authz model for admin GUIs
- defines ingress/gateway patterns in a provider-neutral way
- defines dashboards-as-code expectations where relevant
- defines smoke tests and validation checks for UI exposure
- defines deployment/configuration patterns for each core UI
- keeps all provider-specific details in adapter sections

### D. TASKS DOCUMENT

Update the tasks document so it includes small-to-medium, logically ordered, incremental
tasks for:

- defining the visualization plane
- making Grafana mandatory
- adding/packaging Grafana dashboards
- defining OpenSearch Dashboards content/assets management
- defining Neo4j Browser operational exposure
- optionally supporting Jaeger UI
- optionally supporting Neo4j Bloom
- defining the admin access plane
- integrating authentication and authorization
- adding GUI smoke tests
- documenting operator access and troubleshooting
Group these into logical batches.

### E. IMPLEMENTATION TASKS DOCUMENT

Update the implementation tasks document so it includes concrete execution tasks
for:

- manifests / Helm values / overlays
- ingress or gateway definitions
- TLS configuration handling
- SSO integration points
- RBAC mapping
- GUI exposure configuration
- dashboards/saved objects provisioning
- admin endpoint smoke tests
- post-install validation steps
- rollback/uninstall considerations for externally exposed admin components

### REQUIRED SECTIONS TO ADD OR STRENGTHEN WHERE MISSING

Across the documents, add or strengthen these sections if they do not already exist:

- Visualization Plane
- Admin Access Plane
- Signal-to-UI ownership model
- Externalized GUI model
- Authn/Authz for admin tools
- Dashboard provisioning strategy
- GUI exposure deployment modes
- Validation and smoke testing for UIs
- Operator workflows
- Troubleshooting for admin GUI access
- Security posture for externally reachable admin tools
- Core vs optional visualization/admin components
- Adapter model for provider-specific ingress and identity integrations

### LANGUAGE / WRITING RULES

- Be precise and technical
- Be explicit about what is core vs optional
- Be explicit about what is automatic vs manual
- Keep the writing implementation-ready
- Do not leave contradictions between documents
- Remove stale wording rather than leaving competing statements
- Prefer portable abstractions over cloud-specific assumptions
- Preserve rigor
- Do not turn the docs into generic marketing language

### CONSISTENCY RULES

Make sure all revised documents consistently state:

- Grafana is core, not optional
- OpenSearch Dashboards is core
- Neo4j Browser is core if the graph module is part of the platform
- Jaeger UI is optional
- Neo4j Bloom is optional
- Admin GUIs are intentionally externalized through secure Kubernetes-native exposure
  patterns
- Visualization is multi-tool by design
- Provider-specific ingress/auth/load-balancer details are adapters, not core architecture

### EXPECTED OUTPUT

- Produce the revised content for all referenced documents.
- Keep each document separate.
- Preserve Markdown formatting.
- Do not ask clarifying questions.
- Do not output commentary.
- Directly produce the updated documents.
