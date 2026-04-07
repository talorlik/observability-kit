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

## 0.1 Task Batch Reverse Lookup

Use this reverse lookup to jump from a technical requirement to the
corresponding execution batches in `TASKS.md`.

| Technical Marker | Primary Task Batch Markers In `TASKS.md` |
| ---- | ---- |
| `TR-01` | Reference context only |
| `TR-02` | Constraint baseline across all batches |
| `TR-03` | Architecture baseline across all batches |
| `TR-04` | `TB-02`, `TB-03` |
| `TR-05` | `TB-02`, `TB-03` |
| `TR-06` | `TB-04`, `TB-05`, `TB-06`, `TB-07`, `TB-09` |
| `TR-07` | `TB-05`, `TB-06`, `TB-08` |
| `TR-08` | `TB-10`, `TB-11`, `TB-12` |
| `TR-09` | `TB-07`, `TB-08`, `TB-10`, `TB-12` |
| `TR-10` | `TB-01`, `TB-03`, `TB-09` |
| `TR-11` | `TB-04`, `TB-11` |
| `TR-12` | `TB-07`, `TB-08`, `TB-09` |
| `TR-13` | `TB-12` |
| `TR-14` | `TB-01`, `TB-02` |

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
- OpenSearch Dashboards is the default visualization tier.
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
