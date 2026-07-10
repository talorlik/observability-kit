# Observability Platform Technical Requirements

## 0. Cross-Reference Markers

Use these stable marker IDs to map delivery tasks in `TASKS.md` to
implementation requirements in this document.

| Marker | Section |
| ---- | ---- |
| `TR-01` | Purpose |
| `TR-02` | Required Technical Constraints |
| `TR-03` | Target Technical Architecture |
| `TR-04` | Deployment Modes and Compatibility Model |
| `TR-05` | Guided Install and Discovery Requirements |
| `TR-06` | Telemetry Subscription and Runtime Contracts |
| `TR-07` | Storage, Schema, and Backend Strategy |
| `TR-08` | Derived Graph and Intelligence Requirements |
| `TR-09` | Security and Governance Technical Requirements |
| `TR-10` | GitOps, IaC, and CI/CD Requirements |
| `TR-11` | Reliability, Performance, and Capacity Requirements |
| `TR-12` | Validation, Upgrade, Rollback, and Uninstall |
| `TR-13` | Implementation Phase Gates |
| `TR-14` | Required Technical Artifacts |
| `TR-15` | AI/MCP Runtime Layer Requirements |
| `TR-16` | SaaS Multi-Tenancy and Customer Isolation Requirements |
| `TR-17` | Unified Configuration and Management Plane Requirements |
| `TR-18` | Discovery and Preflight Execution Engine Requirements |
| `TR-19` | Guided Installation Experience Requirements |
| `TR-20` | Configuration Rendering Runtime Requirements |
| `TR-21` | Tenant Control Plane Service Requirements |
| `TR-22` | Unified Management Portal Requirements |
| `TR-23` | Metering, Billing, and Commercial Operations Requirements |
| `TR-24` | Live-Cluster Validation Evidence and Runtime Activation Requirements |
| `TR-25` | Release Engineering and Production Operations Requirements |
| `TR-26` | Product Documentation and GA Readiness Requirements |
| `TR-27` | Demo Workloads and Observability Playground Requirements |

## 0.1 Task Batch Reverse Lookup

Use this reverse lookup to jump from a technical requirement to the
corresponding execution batches in `TASKS.md`.

| Technical Marker | Primary Task Batch Markers In `TASKS.md` |
| ---- | ---- |
| `TR-01` | Reference context only |
| `TR-02` | Constraint baseline across all batches |
| `TR-03` | `TB-09A`, `TB-13` |
| `TR-04` | `TB-02`, `TB-03` |
| `TR-05` | `TB-02`, `TB-03` |
| `TR-06` | `TB-04`, `TB-05`, `TB-06`, `TB-07`, `TB-09` |
| `TR-07` | `TB-05`, `TB-06`, `TB-08` |
| `TR-08` | `TB-10`, `TB-11`, `TB-12` |
| `TR-09` | `TB-07`, `TB-08`, `TB-09A`, `TB-10`, `TB-12`, `TB-13` |
| `TR-10` | `TB-01`, `TB-03`, `TB-09`, `TB-13` |
| `TR-11` | `TB-04`, `TB-11` |
| `TR-12` | `TB-07`, `TB-08`, `TB-09`, `TB-09A` |
| `TR-13` | `TB-12`, `TB-14` |
| `TR-14` | `TB-01`, `TB-02` |
| `TR-15` | `TB-14` |
| `TR-16` | `TB-15` |
| `TR-17` | `TB-16` |
| `TR-18` | `TB-17` |
| `TR-19` | `TB-18` |
| `TR-20` | `TB-19` |
| `TR-21` | `TB-20` |
| `TR-22` | `TB-21` |
| `TR-23` | `TB-22` |
| `TR-24` | `TB-23`, `TB-24` |
| `TR-25` | `TB-25` |
| `TR-26` | `TB-26` |
| `TR-27` | `TB-27` |

## 1. Purpose [TR-01]

This document defines technical requirements for the platform described in
`OBSERVABILITY_PLATFORM_V2.plan.md` and `PRD.md`. It establishes architecture,
runtime contracts, delivery controls, and readiness criteria.

The target system is a Kubernetes-native observability platform that is:

- cloud agnostic
- open-source-first
- plug-and-play
- guided for install and configuration
- discovery-driven for environment detection and onboarding
- phased for optional vector, graph, and LLM-assisted RCA capability

## 2. Required Technical Constraints [TR-02]

- OpenTelemetry is the only baseline collector path for logs, metrics, and traces.
- The core architecture must remain valid across cloud and on-prem Kubernetes.
- OpenSearch is the default telemetry and vector store.
- Visualization is multi-tool by design:
  - OpenSearch Dashboards is core for log search, event analytics, and trace
    analytics workflows.
  - Grafana is core for metrics-first dashboards, SLO and NOC views, and
    alerting workflows.
  - Neo4j Browser is core when the graph module is enabled.
  - Jaeger UI is optional for specialist trace investigation.
  - Neo4j Bloom is optional for specialist graph exploration.
- Neo4j is an optional, derived graph module, not a raw telemetry sink.
- All in-cluster components are delivered with Helm and reconciled via GitOps.
- No provider-specific service is mandatory in the core architecture.
- Provider-specific integrations must be implemented as adapters.
- Install and runtime configuration must come from install contract inputs,
  generated overlays, and profile selections with no hard-coded environment values.
- Primary implementation languages for automation and delivery artifacts are
  Python, Bash, Terraform, and Helm. Supporting formats are allowed when needed.

## 3. Target Technical Architecture [TR-03]

### 3.1 Platform Layers

- Install and discovery plane:
  - preflight validation
  - capability detection
  - compatibility scoring
  - generated configuration
  - smoke-test orchestration
- Telemetry plane:
  - OpenTelemetry operator and collectors
  - OpenSearch
  - OpenSearch Dashboards
- Visualization plane:
  - OpenSearch Dashboards (core)
  - Grafana (core)
  - Neo4j Browser (core when graph module is enabled)
  - Jaeger UI (optional)
  - Neo4j Bloom (optional)
- Admin access plane:
  - ingress and Gateway API exposure patterns for admin GUIs
  - centralized authn via OIDC by default, SAML via adapter when needed
  - role or group to tool-RBAC mapping per UI
  - session security, audit, and break-glass access controls
- Platform services plane:
  - policy, secret, identity, certificate, storage, backup, and networking modules
    selected by profile
- Graph plane:
  - optional Neo4j derived graph for topology and impact modeling
- Intelligence plane:
  - embedding jobs
  - deterministic graph risk scoring
  - optional later-stage LLM-assisted RCA

### 3.2 Core Platform vs Adapter Model

Core platform requirements:

- Kubernetes-native install and operation model
- OpenTelemetry collection and OTLP export
- OpenSearch index families for logs, metrics, traces, and vectors
- guided install and discovery engine
- standardized onboarding contract for workloads
- validation, rollback, and uninstall workflow

Adapter categories:

- cloud/provider adapters
- secret backend adapters
- identity provider adapters
- storage and object storage adapters
- ingress/network adapters
- CI/CD adapters

Adapter requirements:

- adapters may extend capabilities but must not alter core contracts
- adapters must declare prerequisites, generated values, and fallback behavior
- adapter activation must be explicit through profile selection

### 3.3 Tenancy and Isolation Model

- environment-level isolation by namespace, overlays, and index partitioning
- team-level isolation by index patterns, roles, and dashboard spaces
- multi-cluster identity on every record via `k8s.cluster.name`
- ownership metadata required for routing, dashboards, and governance

## 4. Deployment Modes and Compatibility Model [TR-04]

### 4.1 Supported Deployment Modes

The platform must support:

- `quickstart`: low-friction evaluation mode
- `attach`: reuse compatible existing services
- `standalone`: deploy full reference stack on target cluster
- `hybrid`: in-cluster collectors with selected external shared services

### 4.2 Compatibility Matrix

The compatibility model must classify:

- supported Kubernetes versions and distributions
- supported storage profiles
- supported object storage profiles
- supported identity profiles
- supported secret profiles
- supported ingress/network profiles
- supported GitOps/controller baseline

Compatibility grading must produce:

- supported
- supported with conditions
- unsupported with remediation steps

## 5. Guided Install and Discovery Requirements [TR-05]

### 5.1 Install Contract

Required inputs per installation:

- `cluster_name`
- `environment`
- `deployment_mode`
- `gitops_repo_url`
- `gitops_path`
- `base_domain`
- `storage_profile`
- `object_storage_profile`
- `identity_profile`
- `secret_profile`
- `ingress_profile`

Required only for reuse paths:

- existing service endpoints and references for attached components
- trust material references for external secret, PKI, or identity providers

Sensitive inputs must be handled through approved secret backends and never
committed to Git.

### 5.2 Preflight Validation

The install engine must validate before install:

- cluster connectivity and permissions
- supported Kubernetes version and distribution
- required API and CRD readiness
- storage and object storage compatibility
- ingress or Gateway API capability
- GitOps prerequisites
- identity and secret profile prerequisites

### 5.3 Discovery Scope

The discovery engine must inspect at minimum:

- Kubernetes version and distribution
- node topology and scheduling model
- StorageClasses
- ingress controllers and Gateway API capability
- GitOps controllers
- cert-manager or PKI integrations
- secret-management integrations
- namespaces and workload inventory
- Deployments, StatefulSets, DaemonSets, Jobs, CronJobs
- Services, Endpoints, Ingresses, Gateways, Routes
- service ports and scrape candidates
- existing telemetry endpoints
- CRDs that affect install or onboarding

### 5.4 Discovery Outputs

The engine must generate:

- capability matrix
- compatibility report
- recommended deployment mode
- generated values, manifests, and overlays
- discovered onboarding candidates
- remediation list for missing prerequisites
- post-install readiness report

## 6. Telemetry Subscription and Runtime Contracts [TR-06]

### 6.1 Collector Topology and Controls

- Agent DaemonSet responsibilities:
  - passive container log collection from stdout and stderr
  - node and workload metric collection
  - scrape target discovery
  - local buffering and forward to gateway
- Gateway Deployment responsibilities:
  - normalization and enrichment
  - sensitive data redaction
  - batching, retry, and memory limiting
  - sampling and routing
  - export to selected backend endpoints

Required processor families include `k8sattributes`, `resource`,
`memory_limiter`, and `batch`. Sampling processors are required where traces
are enabled.

### 6.2 Subscription Model and Automatic vs Manual Boundary

Automatic by platform:

- passive logs from stdout and stderr
- infrastructure and cluster metrics
- scrape candidate discovery
- Kubernetes metadata enrichment

Low-touch, configuration-driven:

- metrics scrape opt-in via labels or annotations
- onboarding toggles via values or policy metadata
- auto-instrumentation enablement for supported runtimes

Service-team participation required:

- semantic instrumentation and custom attributes
- manual spans where auto-instrumentation is insufficient
- service ownership metadata when discovery cannot infer ownership

### 6.3 Logs Contract

Required minimum fields:

- `@timestamp`
- `message`
- `service.name`
- `deployment.environment`
- `k8s.cluster.name`
- `severity`
- `trace_id` and `span_id` when tracing is enabled

Operational controls:

- multiline parsing for supported stack-trace patterns
- redaction for prohibited sensitive fields
- mapping-safe field governance

### 6.4 Metrics Contract

Supported methods:

- scrape-based collection
- OTLP metrics export

Required controls:

- cardinality budgets and prohibited labels
- bounded histogram and dimension policy
- downsampling and lifecycle controls

### 6.5 Traces Contract

- W3C tracecontext propagation is required.
- OTLP trace export is required.
- sampling policy must be explicitly set per environment and service tier.
- trace and log correlation requires shared identifiers.

### 6.6 Signal-To-UI Ownership Model

Signal and use-case ownership must be explicit and stable:

- logs: OpenSearch Dashboards
- metrics: Grafana
- traces: OpenSearch Dashboards by default, Jaeger UI optional
- topology and blast radius: Neo4j Browser by default, Neo4j Bloom optional
- executive, SLO, and NOC boards: Grafana

Dashboards-as-code and saved-objects provisioning must be split by tool and
stored in tool-specific paths to keep delivery deterministic.

## 7. Storage, Schema, and Backend Strategy [TR-07]

### 7.1 OpenSearch Index Strategy

Required index families:

- `logs-*`
- `metrics-*`
- `traces-*`
- `vectors-*`

Recommended naming pattern:

- `logs-${env}-${team}-YYYY.MM.DD`
- `metrics-${env}-${scope}-YYYY.MM.DD`
- `traces-${env}-${scope}-YYYY.MM.DD`
- `vectors-${env}-${scope}-YYYY.MM.DD`

### 7.2 Mapping, Lifecycle, and Retention Controls

- strict mapping for known fields and controlled dynamic templates
- lifecycle policies for rollover, retention, and deletion
- snapshot policy to S3-compatible object storage with tested restore workflow
- default retention baselines:
  - logs: 30 days
  - metrics: 30 days, downsample after day 7
  - traces: 14 days with sampling enforcement

### 7.3 Backend Support Strategy

The backend strategy must document:

- default self-hostable path for core workloads
- attach and hybrid paths for existing compatible backends
- adapter-specific requirements and operational ownership
- migration and fallback strategy across backend profiles

## 8. Derived Graph and Intelligence Requirements [TR-08]

### 8.1 Neo4j Derived Graph Scope

Neo4j must remain optional and derived. Supported entity types include:

- service dependencies
- endpoint relations
- incident-service links
- ownership mappings
- change and deployment impact links

Neo4j must not duplicate raw telemetry storage responsibilities.

### 8.2 Graph Sync and Data Quality

- sync source is OpenSearch telemetry plus curated metadata inputs
- sync jobs must be idempotent and replay-safe
- late and out-of-order handling must be defined
- schema versioning and migration procedures are required

### 8.3 Intelligence Progression

- Phase 2: curated vectorization foundations in OpenSearch
- Phase 3: graph foundation and validated ETL
- Phase 4: deterministic graph risk scoring
- Phase 5: optional LLM-assisted RCA with governance controls

## 9. Security and Governance Technical Requirements [TR-09]

- enforce encryption in transit and at rest
- enforce least-privilege workload and platform identities
- no secrets in Git under any profile
- secrets must be sourced from supported secret backend profiles
- enforce never-index and redaction policy for sensitive fields
- enforce required labels and onboarding metadata via policy
- maintain audit evidence for access, configuration, and incident operations
- enforce AI governance controls before enabling LLM RCA

### 9.1 Admin GUI Authn, Authz, and Exposure Model

- externalize admin GUIs for OpenSearch Dashboards, Grafana, Neo4j Browser, and
  optional Jaeger UI and Neo4j Bloom
- expose admin GUIs through Kubernetes-native ingress and or Gateway API
- enforce TLS for every externally reachable admin endpoint
- prefer private or internal exposure with VPN or ZTNA access paths
- if internet-facing exposure is approved, require SSO and MFA controls
- centralize authentication with OIDC by default; SAML is supported via adapter
- map identity groups to each tool's RBAC model with least privilege defaults
- enforce audit logging for login, config changes, and privileged actions
- document and test break-glass access workflow and expiry controls

## 10. GitOps, IaC, and CI/CD Requirements [TR-10]

### 10.1 GitOps Delivery Model

- deploy in-cluster components via GitOps applications using Helm sources
- pin versions for charts and OCI artifacts
- commit generated overlays for environment-specific configuration
- preserve rollback path through revisioned GitOps state

Argo CD is the default reference GitOps engine. Equivalent GitOps controllers
are valid when they preserve the same delivery contract.

### 10.2 IaC Scope and Adapter Boundaries

IaC is an optional adapter layer and may be implemented with Terraform or
OpenTofu. IaC modules must support deployment modes and produce outputs that
feed generated overlays.

Reusable module categories should include:

- `attach`
- `standalone`
- `gitops_bootstrap`
- `search_lifecycle`
- `identity_binding`

### 10.3 CI/CD Controls

- CI/CD approach must remain tool-neutral
- reference implementation may use GitHub Actions
- equivalent systems are valid if they enforce:
  - lint and template validation
  - policy and schema checks
  - smoke-test execution
  - controlled promotion and rollback
  - auditable approvals

## 11. Reliability, Performance, and Capacity Requirements [TR-11]

- end-to-end ingest latency targets:
  - logs under 60 seconds
  - metrics under 30 seconds
  - traces under 60 seconds
- pipelines must tolerate transient backend failures with bounded loss behavior
- autoscaling thresholds for collectors and gateway must be defined and tested
- storage growth and shard strategy must be reviewed each phase
- multi-cluster growth model must be validated before broad production rollout

## 12. Validation, Upgrade, Rollback, and Uninstall [TR-12]

### 12.1 Mandatory Validation Suite

- post-deploy smoke tests for logs, metrics, and traces
- schema conformance checks for required fields
- trace-log correlation checks
- ingestion lag and drop-rate checks
- dashboard and alert health checks
- admin GUI reachability and login smoke tests for all enabled core UIs
- backup and restore drill evidence

### 12.2 Meta-Monitoring Requirements

- collector health:
  - queue depth
  - dropped telemetry
  - retry and failure rates
- backend health:
  - ingest errors and lag indicators
  - storage cluster health and pressure indicators
- install and discovery engine health:
  - preflight failure rate
  - discovery completeness
  - generation and apply success

### 12.3 Upgrade, Rollback, and Uninstall Requirements

- version upgrade procedure with compatibility checks must be documented and tested
- safe exporter and routing rollback controls must be documented and tested
- GitOps revision rollback must be documented and tested
- full uninstall workflow must include cleanup guidance and residual risk notes

## 13. Implementation Phase Gates [TR-13]

### Phase 1 - Core Observability

- install contract and compatibility model complete
- discovery engine and guided install operational
- OpenTelemetry agent and gateway operational
- OpenSearch ingestion and storage validated
- dashboards, alerting, and runbooks active
- rollback and uninstall tests complete

### Phase 2 - Vector and AI Foundations

- curated embedding pipelines operational
- retrieval quality and governance checks passed
- required correlation fields enforced

### Phase 3 - Core Graph

- Neo4j optional module operational
- graph schema and ETL productionized
- graph quality validation passed

### Phase 4 - Graph Risk Scoring

- deterministic scoring integrated into operational workflows
- backtesting evidence recorded against real incidents

### Phase 5 - LLM-Assisted RCA

- hybrid retrieval from OpenSearch and Neo4j operational
- human-in-the-loop and audit controls enforced

## 14. Required Technical Artifacts [TR-14]

The implementation must produce versioned artifacts:

- architecture decision records
- install contract and profile schema definitions
- compatibility matrix and support policy
- discovery engine reports and generated overlay outputs
- GitOps application manifests
- Helm charts and environment values
- OpenTelemetry collector configurations
- OpenSearch templates, mappings, and lifecycle policies
- dashboards-as-code and alerts-as-code
- Neo4j schema and sync specifications
- runbooks for install, validation, upgrade, rollback, uninstall, DR, and on-call
- security and governance evidence artifacts

## 15. AI/MCP Runtime Layer Requirements [TR-15]

The AI/MCP runtime layer (Batch 14) builds on the core platform and must
remain cloud-agnostic. It is a higher-order tier — the core platform must be
fully operational with the AI/MCP layer disabled.

- Agent boundary, governance, and shared-state contracts under `contracts/ai/`
  and `contracts/policy/` are authoritative for what agents may do, when they
  may do it, and what evidence they must capture.
- The MCP catalog under `contracts/mcp/MCP_CATALOG_V1.yaml` lists every MCP
  service exposed to agents, with every tool referencing
  `TOOL_RESPONSE_SCHEMA_V1.json` and a tenancy redaction profile.
- The gateway discovery contract enforces explicit registration, heartbeat
  health, bounded request timeouts, and a deny-on-failover posture.
- Identity, access, and tool risk classification under `contracts/policy/`
  must cover every MCP service in the catalog. The default access policy is
  deny.
- Approval flow under `contracts/policy/APPROVAL_FLOW_V1.yaml` must define
  preconditions, timeout rules, and escalation rules per risk class.
  Write-path tools may not bypass these.
- Action preconditions under `contracts/policy/ACTION_PRECONDITIONS_V1.yaml`
  must enumerate execution requirements for every write-path tool.
- KAgent persistence (`contracts/ai/KAGENT_PERSISTENCE_CONTRACT_V1.yaml`)
  is in-cluster only, with backups, point-in-time recovery, and
  restore-drill cadence.
- KHook triggers must use read-only dispatch by default and enforce dedupe
  and burst control.
- The GitOps surface for the AI/MCP layer (`gitops/platform/ai/`) must
  include namespaces, deployments, network policies, and per-environment
  overlays. Dashboards (`AI_RUNTIME_HEALTH`, `MCP_GATEWAY_HEALTH`) and
  alerts (`approval_flow_rules`, `mcp_health_rules`) are required.
- Operator runbooks for AI/MCP (approval flow, KHook troubleshooting,
  MCP gateway operations, casefile review) must accompany delivery.

## 16. SaaS Multi-Tenancy and Customer Isolation Requirements [TR-16]

The platform serves multiple customers (tenants) from one deployment.
Customer isolation is stricter than the team and environment isolation in
section 3.3: cross-tenant access or leakage is a hard failure, not a
policy preference.

- The tenant contract under `contracts/tenancy/` is authoritative for
  tenant identity: tenant id, tier, isolation class
  (`shared-partition`, `dedicated-indices`, or `dedicated-stack`),
  residency constraints, and lifecycle state.
- Every telemetry store partitions per tenant: OpenSearch index naming
  `tenant-<id>-<signal>-*` with per-tenant roles, role mappings, and
  dashboard spaces; one Neo4j database per tenant in graph-enabled mode;
  per-tenant vector indices with mandatory retrieval filters.
- Cross-tenant access is deny-by-default and must be proven by seeded
  denial fixtures in CI. The AI/MCP layer applies tenancy redaction
  profiles per `TR-15` to every tool response.
- Control plane and data plane are separated: tenant management data
  lives in the control plane; tenant telemetry never leaves the tenant's
  data-plane partition, and control-plane records never embed tenant
  telemetry payloads.
- Per-tenant delivery uses generated GitOps overlays (ApplicationSet
  style, tool-neutral per `TR-10`) rendered from the tenant contract;
  core charts are never modified per tenant.
- Onboarding and offboarding are idempotent; purge produces evidence and
  honors retention rules. Audit records (`TR-09`) carry the tenant id.
- Isolation is achieved only through native mechanisms of the wrapped
  systems (OpenSearch security roles, Neo4j multi-database, dashboard
  spaces); forking a wrapped system to achieve isolation is forbidden.

## 17. Unified Configuration and Management Plane Requirements [TR-17]

The platform wraps its bundled open-source systems so operators manage,
configure, and view everything from one place while every wrapped system
remains upgradable through its own upstream mechanism.

- The wrapped-system registry under `contracts/management/` enumerates
  every bundled system (OpenTelemetry Collector, OpenSearch, OpenSearch
  Dashboards, Grafana, Neo4j, Argo CD, and enabled adapters) with its
  upstream source, pinned version, upgrade mechanism, config surface,
  and wrap method.
- Allowed wrap methods are `helm-values`, `kubernetes-crd`,
  `provisioning-api`, and `sidecar`; `fork` is forbidden and must be
  rejected by validation.
- A single schema-validated unified configuration document is the one
  place operators change platform configuration. Every unified key maps
  to one or more propagation bindings (unified key to native config
  path); keys without bindings and bindings to unregistered systems are
  rejected.
- Propagation is GitOps-only: the unified document renders per-system
  native configs (Helm values, provisioning files, saved objects) that
  are committed and reconciled by the GitOps controller. Direct mutable
  API writes for persistent configuration are forbidden.
- Rendered configuration is the source of truth. Drift between rendered
  and live state must surface through the meta-monitoring alerts
  required by `TR-12`.
- Single-pane access: a UI catalog defines stable URLs, SSO and role
  mapping consistent with the admin access plane (`TR-03`), and tenant
  scoping consistent with `TR-16` for every wrapped UI.
- The unified configuration schema is versioned; breaking binding
  changes require documented migration notes before release.

## 18. Discovery and Preflight Execution Engine Requirements [TR-18]

The execution engine turns the preflight and discovery contracts of
`TR-04` and `TR-05` into a runtime that runs against a live cluster. It
observes only: it never mutates cluster state and never modifies a
wrapped open-source system.

- The executor is a Python 3.11+ package under `tools/obskit/` with its
  own dependency manifest (`pyproject.toml` plus pinned requirements);
  it never extends `requirements-ci.txt`, which stays lint-only.
- Cluster access is read-only. The bundled RBAC manifest grants only
  get, list, and watch verbs; secret values are never read, only
  presence and metadata.
- Every emitted report conforms to its published schema:
  `contracts/discovery/PREFLIGHT_REPORT_SCHEMA.json` for preflight and
  `contracts/discovery/DISCOVERY_PROBES_SCHEMA.json` for discovery.
- Outputs are deterministic: identical cluster state and contract
  inputs produce byte-identical reports, with stable ordering and no
  environment-dependent fields outside designated metadata.
- Grading, mode recommendation, and remediation derive exclusively from
  `contracts/compatibility/GRADING_RULES.json`,
  `MODE_DECISION_TABLE.json`, and `REMEDIATION_CATALOG.json`; no
  grading or decision rule is hardcoded in executor code.
- The CLI mode and the optional in-cluster Job mode execute the same
  code path and produce interchangeable reports.
- The executor has no provider-specific dependency; provider detection
  surfaces only through the adapter contracts of `TR-03`.
- CI validation is offline and fixture-driven; live-cluster integration
  runs (for example against kind) exist but are never CI-gated.

## 19. Guided Installation Experience Requirements [TR-19]

The guided installer drives an operator from preflight to verified
readiness in one contracted flow. It composes the `TR-18` executor, the
install contract of `TR-05`, and the required artifacts of `TR-14`.

- The install flow order is contract-fixed: preflight, grading, mode
  recommendation, install contract capture, render, Argo CD bootstrap,
  post-install readiness.
- Captured answers always validate against
  `contracts/install/INSTALL_CONTRACT_SCHEMA.json`; invalid answers
  fail the run before any render or bootstrap step executes.
- Non-interactive mode has full parity: an answers file drives exactly
  the flow the interactive wizard drives, and every interactive run is
  reproducible from its recorded answers.
- Installation is idempotent and resumable: re-running a completed
  install changes nothing, and a failed run resumes from the last
  completed step instead of restarting.
- Rendering is GitOps-only, consistent with
  `contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`
  (`TR-17`): the installer emits overlay and bootstrap manifests for
  the GitOps controller and performs no direct mutable API writes for
  persistent configuration.
- The installer never forks or patches wrapped open-source systems;
  configuration flows only through the wrap methods allowed by `TR-17`.
- The installer core has no provider-specific dependency; provider
  specifics enter only through adapters (`TR-03`).
- Readiness is evidence-based: the flow ends by invoking the
  post-install readiness checks and emitting an install summary with
  next steps.

## 20. Configuration Rendering Runtime Requirements [TR-20]

The rendering runtime executes the propagation and reconciliation
contract of `TR-17`: it turns the unified configuration document into
committed native configuration. It writes Git content only and never
performs a live configuration write.

- The renderer is a Python 3.11+ package under `tools/obskit/` with its
  own dependency manifest (`pyproject.toml` plus pinned requirements);
  it never extends `requirements-ci.txt`, which stays lint-only.
- Input is the schema-validated unified configuration document plus its
  propagation bindings
  (`contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json`); output is
  written only at each binding's `render_target` path within the
  registered config surface.
- Rendering is deterministic: identical document and binding inputs
  produce byte-identical rendered files, and re-rendering an unchanged
  document produces no diff and no commit.
- Every rendered file carries the generated-file header marker and
  every propagation commit carries the required commit trailers defined
  in `contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`.
- Drift tooling compares rendered state against live state and emits
  the rendered-versus-live diff surface consumed by the `TR-12`
  meta-monitoring drift alerts.
- Rollback is a re-render from a prior unified document revision
  through the same render-and-commit pipeline; a separate apply channel
  is forbidden. Rollback tooling follows the mode-parameterized
  conventions of `scripts/ops/run_rollback_drill.sh`.
- The renderer never forks or patches a wrapped open-source system;
  rendered output flows only through the wrap methods allowed by
  `TR-17`.
- CI validation is offline and fixture-driven; no live cluster or Git
  remote is required to prove determinism or idempotency.

## 21. Tenant Control Plane Service Requirements [TR-21]

The tenant control plane service executes the tenant lifecycle contract
of `TR-16` behind an API. Every lifecycle transition materializes as a
GitOps render; the service performs no direct mutable cluster writes
for persistent configuration.

- The service is FastAPI on typed Python 3.11+ under
  `services/tenancy/` with its own dependency manifest; it never
  extends `requirements-ci.txt`.
- The API surface is fixed by
  `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` (OpenAPI):
  tenant CRUD plus provision, suspend, resume, offboard, and purge with
  exactly the state machine and idempotent-replay semantics of
  `contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml`.
- Lifecycle execution renders per-tenant overlays per
  `contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`,
  reusing the `TR-20` renderer; core charts are never modified per
  tenant.
- Provisioning renders the isolation artifacts of
  `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`: per-tenant
  OpenSearch roles, role mappings, and dashboard spaces, one Neo4j
  database per tenant in graph-enabled mode, and per-tenant vector
  indices with mandatory retrieval filters.
- Destructive transitions are blocked without an approval record per
  `contracts/policy/APPROVAL_FLOW_V1.yaml`, honoring its timeout and
  escalation rules.
- Every transition emits an audit record (`TR-09`) carrying the tenant
  id; seeded denial fixtures prove that unapproved destructive
  transitions and cross-tenant operations are rejected.
- CI validation is offline: fixtures exercise the service logic without
  a live cluster or Git remote.

## 22. Unified Management Portal Requirements [TR-22]

The portal is the operator's single pane: one place to reach every
wrapped UI, change unified configuration, and manage tenants. It fronts
wrapped systems without forking them and writes configuration only
through Git.

- The portal backend lives under `services/portal/` in typed Python
  3.11+ with its own dependency manifest; the frontend stack is chosen
  and justified by its ADR and stays minimal in v1.
- The portal contract
  (`contracts/management/PORTAL_CONTRACT_V1.yaml`) defines views, API
  surface, and authentication; it is the single source of portal
  scope.
- Navigation derives from the UI catalog of
  `contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml`; every
  cataloged wrapped UI is reachable from the portal.
- Unified configuration edits flow through the `TR-20` renderer: an
  edit becomes a Git commit reconciled by the GitOps controller; the
  portal performs no live configuration writes.
- Tenant management is delegated to the `TR-21` control plane API; the
  portal holds no tenant lifecycle logic of its own.
- Authentication follows the admin access plane (`TR-03`) with SSO and
  role mapping; tenant scoping enforces `TR-16` so a tenant-scoped
  role sees only its tenant's views.
- The portal surfaces a platform health summary sourced from the
  meta-monitoring signals of `TR-12`.
- Portal reachability and login join the admin GUI smoke checks of
  `scripts/validate/admin_gui_smoke.sh`; contract validation in CI is
  offline.

## 23. Metering, Billing, and Commercial Operations Requirements [TR-23]

Commercial operations meter tenant usage, bind tenants to plans, and
export billing data. The core stays vendor-neutral; billing vendors
integrate only through adapters.

- Usage dimensions are contract-fixed in
  `contracts/commercial/METERING_CONTRACT_V1.yaml`: ingest GB per day
  per signal, retention days, active tenants, and query volume,
  sourced from platform telemetry already in OpenSearch with no new
  collection path.
- The metering collector writes usage records to control-plane indices
  (`control-tenancy-*`), honoring the control-plane versus data-plane
  separation of `TR-16`; every usage record carries the tenant id, and
  a record without one is rejected.
- The plan catalog binds every plan to the `tier` enum of
  `contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json`; every plan
  defines quota bounds that hook into the Batch 15 tenant quotas, and
  a plan without quota bounds is invalid.
- Quota breach handling is evidence-based: breaches surface through
  the `TR-12` alerting path and every enforcement action emits an
  audit record (`TR-09`) carrying the tenant id.
- Billing integration lives under `adapters/billing/` following the
  house adapter pattern (`*_COMPATIBILITY_V1.yaml`,
  `STUB_METADATA.json`, `ROLLBACK_UNINSTALL_NOTES.md`, `README.md`);
  the Stripe reference adapter is a stub and the invoice-export
  contract is vendor-neutral.
- A billing adapter never mutates the platform core; fork-like core
  mutation is rejected by validation.
- CI validation is offline and fixture-driven with seeded rejection
  fixtures.

## 24. Live-Cluster Validation Evidence and Runtime Activation Requirements [TR-24]

Live validation proves declared runtime behavior on a real cluster and
activates the AI/MCP runtime under the same evidence discipline.
Everything here runs on disposable clusters and never gates pull
requests.

- Live runs execute only on disposable kind/k3d clusters provisioned
  through the contracted harness
  (`contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml`)
  with a fixed profile, sizing bounds, and guaranteed teardown; a
  cluster is never reused across runs.
- The only permitted install path on the harness is the Batch 18
  guided installer (`TR-19`); a hand-assembled install invalidates the
  evidence it produces.
- Every runtime-only completion check from Batches 4-12 executes live -
  restore and rollback drills, GUI smoke including the portal, and the
  cross-tenant denial scenarios `SDN-B15-001` through `SDN-B15-009` -
  and captures an evidence artifact under `artifacts/evidence/`.
- Captured evidence is additive: affected `*_VALIDATION.json`
  contracts gain `captured_evidence` references while their declared
  blocks stay in place, and schema files are never renamed (`TR-14`).
- Live execution is manual or nightly and orchestrator-owned; the
  nightly e2e workflow ships disabled by default and is never wired
  into PR gating.
- AI runtime activation deploys KAgent, KHook, and the MCP gateway
  from `gitops/platform/ai/` with the MCP catalog and governance
  contracts (`TR-15`) enforced, not relaxed, on the live cluster.
- Model providers are pluggable through the adapter pattern; provider
  keys resolve through the secrets backend and never appear in
  configuration or Git.
- The trigger-to-approval rehearsal - KHook trigger, casefile,
  read-path investigation, action-gate approval with a human-surrogate
  step - must pass with policy, redaction, and audit intact.
- Production activation follows
  `docs/operations/PRODUCTION_ACTIVATION_SIGNOFF_WORKFLOW.md`; a
  quantitative threshold that cannot be measured counts as a failed
  gate.
- Two local stack profiles are contract-fixed: `evidence-disposable`
  (a kind or k3d cluster on the local Docker engine - OrbStack on the
  reference development machine - created and destroyed per evidence
  run) and `dev-persistent` (the OrbStack built-in Kubernetes cluster
  with the dev overlay and a documented reset procedure, for
  day-to-day development, never for evidence capture).
- The harness writes and uses an isolated kubeconfig and refuses any
  context it did not create; shared and cloud clusters (EKS, GKE,
  AKS, on-prem production) are structurally unreachable from harness
  runs.

## 25. Release Engineering and Production Operations Requirements [TR-25]

The platform ships as a versioned product. Releases are tag-driven,
supply-chain hardened, and upgrade-tested before any production claim.

- Versioning is semver; every release is a Git tag with a
  `CHANGELOG.md` entry following the convention fixed in
  `contracts/release/RELEASE_ENGINEERING_CONTRACT_V1.yaml`.
- Release artifacts are packaged Helm charts and OCI artifacts with a
  defined publication path and a stated artifact signing posture.
- The wrapped-system registry
  (`contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml`) carries
  concrete version pins for `opensearch`, `opensearch-dashboards`,
  and `argocd`, verified against upstream releases; the
  `fail_if_production_pin_missing` rule passes for production
  profiles.
- A pinned set must install cleanly on the disposable harness
  (`TR-24`) before it ships.
- An N-1 to N upgrade test installs the previous tagged state,
  upgrades to the current state, and verifies that data and
  configuration survive (`TR-12`).
- The platform's own SLOs are productionized as a `contracts/slo_ops/`
  extension so the product is operable as a service (`TR-11`).
- CI performs image scanning and SBOM generation for release
  artifacts.
- Commercial distribution requires a completed OSS license compliance
  review per `contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml`:
  a license inventory of all bundled systems, their obligations, and
  an attribution file.
- Seeded rejection fixtures - an unpinned production profile and a
  bundled system missing from the license inventory - must fail
  validation.
- A production reference architecture
  (`contracts/release/PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml`)
  defines the production-grade stack for any conformant Kubernetes
  cluster: HA topology, sizing tiers by tenant scale, storage and
  ingress requirements via the compatibility profiles, backup and DR
  posture, and the `prod` overlay mapping. Production claims require
  a cluster that grades `supported` against it.

## 26. Product Documentation and GA Readiness Requirements [TR-26]

Product documentation is a release artifact with the same gating
discipline as code. GA is a reviewed, evidence-backed state, not a
declaration.

- The product documentation tree lives under `docs/product/` with an
  `INDEX.md` and an audience map covering evaluator, installer and
  operator, tenant administrator, end user, and commercial
  administrator.
- Core guides derive from delivered flows, not aspirations: the
  installation guide from the Batch 18 install flow (`TR-19`), the
  configuration guide from the unified configuration document
  (`TR-20`), and the operations guide from the operator runbooks.
- The API reference is generated from
  `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` (`TR-21`);
  hand-written drift from the contract is a validation failure.
- Commercial documents cover pricing and packaging bound to the
  `TR-23` plan catalog and a support and onboarding playbook; the
  repository `README.md` presents the product.
- A docs-coverage matrix maps every Batch 17-25 capability to a
  product documentation section; an unmapped capability fails
  validation, and links across the tree are validated.
- GA readiness is recorded in a signed
  `docs/product/GA_READINESS_REVIEW.md` walking the definition of
  done in `docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md` with
  an evidence link for every item.

## 27. Demo Workloads and Observability Playground Requirements [TR-27]

The demo package exists so an operator can generate realistic
telemetry and exercise every product surface - dashboards, tenancy,
metering, and the AI layer - without instrumenting a real fleet. It
is a playground, never a production dependency.

- The package is optional, additive, and removable: deploying or
  tearing it down never modifies core platform charts, contracts, or
  the ArgoCD bootstrap. It lives under `demo/` and is deployed
  explicitly by the operator, never by the installer.
- Sample services cover distinct workload kinds - at minimum an HTTP
  API service, an asynchronous worker, a scheduled job, and a
  datastore-backed service - each emitting logs, metrics, and traces
  through OpenTelemetry to the platform collector. No demo component
  writes to OpenSearch or Neo4j directly (`TR-02`, `TR-07`).
- Demo workloads onboard through the Batch 7 one-block subscription
  contract; the package doubles as a conformance example of the
  onboarding path (`TR-06`).
- The package deploys tenant-scoped so isolation, per-tenant
  dashboards, and usage metering are exercised on demo data
  (`TR-16`, `TR-23`).
- Traffic simulation is scenario-driven and declarative: steady
  baseline, burst, error-injection, and latency-injection scenarios
  with a validated schema and seeded-invalid rejection. Fault
  scenarios must produce data the risk scoring and assisted RCA
  surfaces can consume (`TR-08`, `TR-13`).
- Sizing fits the development stack (OrbStack reference machine) and
  the disposable kind harness; the persistent dev stack remains
  never-an-evidence-source (`TR-24`).
- Demo dashboards are dashboards-as-code under the platform
  provisioning paths with the standard filter set - time range,
  tenant, service, namespace, and severity or status (`TR-03`).
- The AI playground is a prompt pack bound to actual MCP catalog
  tools, read-path by default; any write-path prompt goes through
  the approval flow unchanged (`TR-15`).
- The playground guide is a product document (evaluator and operator
  audiences) registered in `docs/product/INDEX.md`, so the product
  docs validator continues to gate the whole tree (`TR-26`).
- Technology choices (workload sourcing, load-generation tooling)
  are ADR-gated. Wrap-never-fork applies: an upstream demo
  application may be wrapped through its own chart or manifests,
  never forked (`TR-10`).
