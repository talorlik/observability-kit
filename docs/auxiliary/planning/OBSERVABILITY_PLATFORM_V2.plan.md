# Observability Platform Plan

**Target**: A portable, plug-and-play observability intelligence platform for any
existing Kubernetes cluster, deployable from a personal machine or CI/CD pipeline,
using Helm + self-hosted Argo CD as the default delivery path, OpenTelemetry as
the sole collector, self-managed OpenSearch as the primary telemetry and search
backend, and Neo4j as the derived graph intelligence layer. The default reference
stack is Talos Linux + kubeadm for the cluster, Cilium + Gateway API for networking,
Vault + External Secrets Operator for secrets, SPIFFE/SPIRE + Kubernetes RBAC for
workload identity and authorization, cert-manager for TLS, Harbor for registry,
Longhorn for persistent storage, MinIO for S3-compatible object storage, Velero
for backup/restore, and Kyverno for policy enforcement. Optional adapters may
integrate with cloud-native services, but the core platform remains Kubernetes-native
and open-source-first.

## 1. Executive Summary

- Deliverable is an installable observability platform product for existing Kubernetes
  clusters, not an AWS-only deployment pattern.
- Kubernetes is the platform boundary. The platform must run on-premises or in any
  cloud where a conformant cluster and compatible storage/network primitives exist.
- OpenTelemetry Collector is the only collector/agent for logs, metrics, and traces.
  No parallel log agents, metrics agents, or vendor-specific side collectors are
  part of the default design.
- OpenTelemetry Operator is the default control plane for collector lifecycle and
  zero-code/low-code auto-instrumentation where supported.
- OpenSearch is the default telemetry and search backend for logs, metrics, traces,
  evidence vectors, and semantic retrieval.
- Neo4j is the derived relationship and reasoning store for service dependency graphs,
  incident graphs, change graphs, risk graphs, and GraphRAG context.
- Plug-in model for workloads is standardized and low-touch:
  - Logs: passive collection from stdout/stderr
  - Metrics: scrape opt-in via annotations/labels or OTLP metrics
  - Traces: auto-instrumentation or SDK-based OTLP
- Secrets and PKI are platform-native:
  - Vault for secret storage, transit encryption workflows, and optional PKI
  - External Secrets Operator for Kubernetes materialization
  - cert-manager for certificate issuance/renewal
- Identity and access are provider-neutral:
  - SPIFFE/SPIRE for workload identity
  - Kubernetes RBAC for cluster authorization
  - Keycloak or Dex for human/OIDC identity integration
- Networking is provider-neutral:
  - Gateway API as the north-south control model
  - Cilium as the default implementation for networking, network policy, and
    Gateway support
- Operations-ready scope includes dashboards/alerts-as-code, runbooks, SLOs,
  backup/restore drills, and meta-monitoring for collectors, OpenSearch, storage,
  ingress, and the discovery/install engine.
- AI roadmap remains staged across five phases: core observability, vectorization
  and semantic retrieval, Neo4j graph construction, graph analytics/risk scoring,
  and LLM-assisted RCA with governance controls.
- The platform is not only an observability stack. It is a staged operational
  intelligence platform with a clean separation between raw telemetry and evidence
  retrieval (OpenSearch), graph intelligence (Neo4j), and reasoning orchestration
  (hybrid retrieval + LLM).

## 2. Assumptions

- The product is deployable onto an existing Kubernetes cluster.
- Default reference cluster stack:
  - Talos Linux + kubeadm
- Additional supported cluster variants:
  - RKE2
  - upstream kubeadm on generic Linux
  - K3s for quickstart/lab mode only
- Default deployment mode is `attach`:
  - attach to an existing compatible Kubernetes cluster and reuse existing compatible
    platform services where present
  - install only missing platform components where discovery shows gaps
- Additional deployment modes:
  - `quickstart`: evaluation or lab installation, lowest friction, smallest footprint
  - `standalone`: deploy the full reference stack on the target cluster
  - `hybrid`: deploy in-cluster collectors and selected components while attaching
    to existing compatible external services
- Environment model:
  - `dev`, `stage`, `prod` by default, but any environment label is allowed
- Multi-cluster is supported:
  - each cluster runs its own agents and local platform components where required
  - environments may aggregate multiple clusters into one OpenSearch and/or Neo4j
    topology if capacity and governance permit
- Visualization is multi-tool by design with explicit ownership:
  - OpenSearch Dashboards is core for logs, event analytics, and trace analytics.
  - Grafana is core for metrics-first, SLO, NOC, and executive dashboards.
  - Neo4j Browser is core when the graph module is enabled.
  - Jaeger UI is optional for specialist trace investigation.
  - Neo4j Bloom is optional for specialist graph exploration.
- Retention defaults:
  - Logs: 30 days
  - Metrics: 30 days with downsampling after 7 days
  - Traces: 14 days with tail sampling
- Compliance posture:
  - treat all telemetry as potentially sensitive
  - deny indexing of secrets/credentials by default
  - enforce redaction, field controls, and policy validation
- Incident tooling:
  - OpenSearch alerting is the default baseline
  - PagerDuty, Opsgenie, Slack, email, or other integrations are optional adapters
- CI/CD posture:
  - self-hosted Argo CD is the default GitOps engine
  - GitHub Actions is the reference CI example, not a mandatory dependency
  - other CI/CD systems are supported if they can render config, package charts,
    and update GitOps state
- Infrastructure provisioning posture:
  - Helm and Argo CD are mandatory for in-cluster delivery
  - Terraform or OpenTofu are optional for underlying infrastructure or external
    dependency provisioning
- Secret posture:
  - Vault is the default secrets system
  - ESO is the default Kubernetes sync layer
  - SOPS is recommended for encrypted Git material when needed
- Neo4j deployment posture:
  - self-managed on Kubernetes is the default
  - managed Neo4j is an optional adapter, not the baseline

## 3. Clarification Q&A + Resulting Decisions

No additional clarification questions were required for this rewrite.

Resulting default decisions:

- Platform boundary: Kubernetes-first, cloud-agnostic, open-source-first.
- Cluster baseline: Talos Linux + kubeadm.
- GitOps baseline: self-hosted Argo CD.
- Collector topology: OpenTelemetry Operator + Agent DaemonSet + Gateway Deployment.
- Storage baseline:
  - OpenSearch for telemetry and vectors
  - Neo4j for graph intelligence
  - Longhorn for persistent volumes
  - MinIO for S3-compatible snapshot and artifact storage
- Secret baseline:
  - Vault + External Secrets Operator
- Identity baseline:
  - SPIFFE/SPIRE for workload identity
  - Kubernetes RBAC for authorization
  - Keycloak as the default human identity broker
- TLS baseline:
  - cert-manager with Vault or another supported issuer
- Networking baseline:
  - Gateway API + Cilium
- Policy baseline:
  - Kyverno
- Backup baseline:
  - Velero
- Vector strategy:
  - OpenSearch evidence vectors for telemetry-derived documents
  - Neo4j graph/entity vectors for graph-native objects
  - no indiscriminate vectorization of raw exhaust

## 4. Architecture Variations + Decision Matrix

### Variations

- **V1 (Recommended)**
  - OpenTelemetry Agent DS + OpenTelemetry Gateway
  - self-managed OpenSearch
  - OpenSearch Dashboards
  - Neo4j
  - Argo CD
  - Vault + ESO
  - Cilium + Gateway API
  - Longhorn + MinIO + Velero

- **V2 (Attach Mode)**
  - OpenTelemetry Agent DS + OpenTelemetry Gateway
  - attach to an existing compatible OpenSearch backend and/or existing compatible
    secrets, ingress, or GitOps services
  - deploy only missing components required by the compatibility report

- **V3 (Quickstart)**
  - K3s single-cluster or small lab cluster
  - reduced replica counts
  - reduced retention
  - no HA guarantees
  - intended only for evaluation, demos, and early PoC

- **V4 (Hybrid)**
  - in-cluster telemetry collection and policy enforcement
  - external or shared OpenSearch and/or Neo4j services
  - useful for enterprises with centralized search/graph platforms

### Decision Matrix

| Dimension | V1 Full OSS Reference | V2 Attach | V3 Quickstart | V4 Hybrid |
| ---- | ---- | ---- | ---- | ---- |
| Portability | High | High | Medium | High |
| Operator burden | Medium | Low-Medium | Low | Medium |
| Production suitability | High | High | Low | High |
| Guided install complexity | Medium | Medium | Low | Medium |
| Cost efficiency | Medium | High | High | Medium |
| Self-containment | High | Medium | High | Low-Medium |
| Policy consistency | High | Medium-High | Medium | Medium-High |
| Failure isolation | High | Medium-High | Low | Medium |
| Recommendation | Primary | Secondary | Labs only | Enterprise option |

**Selection**: V1.

**Rationale**: Best balance of portability, control, product consistency, and
open-source-first delivery. It avoids cloud lock-in while preserving strong operational
boundaries, clear backup/restore paths, and consistent onboarding behavior across
cloud and on-premises clusters.

## 5. Recommended Target Architecture

### Platform Layers

The platform is organized into five planes:

- **Install and discovery plane**
  - preflight checks
  - capability detection
  - compatibility report
  - generated configuration
  - smoke tests
- **Telemetry plane**
  - OpenTelemetry Operator
  - OpenTelemetry collectors
  - OpenSearch
  - OpenSearch Dashboards
- **Platform services plane**
  - Vault
  - External Secrets Operator
  - SPIFFE/SPIRE
  - cert-manager
  - Cilium + Gateway API
  - Harbor
  - Longhorn
  - MinIO
  - Velero
  - Kyverno
- **Graph plane**
  - Neo4j for dependency, blast-radius, incident, change, and ownership graphs
- **Intelligence plane**
  - embedding jobs
  - graph analytics jobs
  - risk scoring
  - LLM-assisted RCA orchestration

### Guided Install and Discovery Engine

The platform must include a discovery-driven installer or orchestration layer
implemented as a CLI, Kubernetes Job bundle, controller, operator, or hybrid approach.

#### Discovery scope

The engine must inspect and report on:

- Kubernetes version and distribution
- node topology and scheduling model
- existing StorageClasses
- existing ingress controllers and Gateway API support
- existing GitOps controllers
- existing cert-manager or PKI integrations
- existing secret-management integrations
- existing observability-relevant components
- namespaces and workload inventory
- Deployments, StatefulSets, DaemonSets, Jobs, CronJobs
- Services, Endpoints, Ingresses, Gateways, Routes
- service ports and scrape candidates
- existing telemetry endpoints
- existing CRDs that affect installation or onboarding

#### Discovery outputs

The engine must produce:

- capability matrix
- compatibility report
- recommended deployment mode
- generated values/manifests/overlays
- discovered onboarding candidates
- detected gaps and remediation steps

### Components

#### In-cluster core components

- `install-discovery-engine`
  - preflight validation
  - capability detection
  - generated config overlays
  - smoke test orchestration
- `argocd`
  - default GitOps engine
- `otel-operator`
  - manages collector lifecycle
  - manages auto-instrumentation resources
- `otel-agent` DaemonSet
  - passive log collection
  - node/pod/container metrics
  - scrape discovery for annotated targets
  - forwards OTLP to gateway
- `otel-gateway` Deployment + HPA
  - enrichment
  - redaction
  - routing
  - batching
  - retry/backpressure
  - sampling
  - export to storage backends
- `opensearch`
  - primary telemetry/search store
- `opensearch-dashboards`
  - default UI for logs, metrics, traces, alerting, and evidence search
- `neo4j`
  - derived graph intelligence module
- `vault`
  - default secrets and transit backend
- `external-secrets-operator`
  - syncs secrets into Kubernetes when runtime materialization is required
- `spire-server` and `spire-agent`
  - workload identity issuance and attestation
- `cert-manager`
  - issues/renews cluster and ingress certificates
- `cilium`
  - networking, network policy, Gateway API implementation
- `kyverno`
  - policy enforcement and onboarding guardrails
- `longhorn`
  - default persistent block storage for platform stateful services
- `minio`
  - S3-compatible object store for snapshots, backups, and artifacts
- `velero`
  - backup and restore of Kubernetes resources and persistent data
- `harbor`
  - registry for images and OCI artifacts, if not already present externally

### Data Flows

1. The install/discovery engine runs preflight checks and inspects cluster capabilities.
2. The engine generates a compatibility report and proposes `quickstart`, `attach`,
  `standalone`, or `hybrid`.
3. Argo CD deploys platform components using generated overlays and environment
  defaults.
4. Workloads emit logs to stdout/stderr.
5. `otel-agent` tails container logs, enriches with Kubernetes metadata, and forwards
  OTLP to `otel-gateway`.
6. Workloads emit OTLP traces and metrics directly to `otel-gateway` or to an agent
  which forwards them.
7. `otel-gateway` applies redaction, normalization, batching, routing, and trace
  sampling.
8. OpenSearch receives and stores telemetry in dedicated index families for logs,
  metrics, traces, and evidence vectors.
9. OpenSearch Dashboards provides unified analysis, search, alerting, and operational
  views.
10. Embedding jobs generate evidence vectors and store them in OpenSearch vector
  indices.
11. Graph ETL jobs derive services, dependencies, incidents, changes, and ownership
  entities into Neo4j.
12. Graph analytics compute risk signals and structural insights.
13. Hybrid retrieval queries OpenSearch and Neo4j to feed RCA and operational
  intelligence workflows.

### Tenancy Boundaries

- Environment isolation:
  - separate logical deployments or namespaces by environment
  - separate OpenSearch index families per environment
  - separate Neo4j databases or graph partitions where required
- Within environment:
  - team-scoped index patterns and roles
  - dashboard spaces/tenants by team
  - service ownership labels as mandatory metadata
- Multi-cluster:
  - every record carries `k8s.cluster.name` or equivalent cluster identity attribute
- Identity:
  - workload identity via SPIFFE/SPIRE
  - user identity via Keycloak or Dex
  - authorization via Kubernetes RBAC and platform roles

### Install Contract (Minimum Configuration Surface)

**Required inputs per installation:**

- `cluster_name`
- `environment`
- `deployment_mode`
  - `quickstart`
  - `attach`
  - `standalone`
  - `hybrid`
- `gitops_repo_url`
- `gitops_path`
- `base_domain`
- `storage_profile`
  - `longhorn`
  - `rook-ceph`
  - `existing`
- `object_storage_profile`
  - `minio`
  - `existing`
- `identity_profile`
  - `spire-keycloak`
  - `spire-dex`
  - `existing`
- `secret_profile`
  - `vault-eso`
  - `existing`
- `ingress_profile`
  - `cilium-gateway`
  - `existing`

**Required inputs only when reusing existing services:**

- existing service endpoints or references for reused components
- trust material references for any reused secret, PKI, or identity backend

**Sensitive inputs:**

- Git repository credentials or tokens if required
- Keycloak/Dex client secrets
- Vault initialization or unseal references if not externally managed
- any human identity federation secrets

Everything else should be detected or defaulted by the guided install engine.

### Secrets and Configuration Policy

- No secrets in Git.
- No hard-coded endpoints, account identifiers, or provider-specific constructs
  inside chart templates.
- Vault is the canonical long-lived secret backend.
- ESO is the default sync mechanism for runtime materialization into Kubernetes
  Secrets.
- SOPS is recommended when encrypted Git material is required.
- Kubernetes Secrets are only used when a workload must read a secret at runtime.
- Non-sensitive configuration goes into ConfigMaps or generated values overlays.
- Vault Transit is the preferred encryption-as-a-service pattern for application
  flows that need payload encryption without embedding static keys.
- cert-manager may use Vault as an issuer when internal PKI is required.

### Plug-in Model for Workloads (Standard Onboarding Contract)

#### Automatic vs manual boundary

**Automatic by platform:**

- cluster-wide container log collection from stdout/stderr
- node and kube-state metrics
- discovery of scrape candidates based on workload and service metadata
- Kubernetes metadata enrichment
- policy enforcement on required labels/annotations

**Low-touch / configuration-driven:**

- metrics scrape enablement by annotations or a Helm values block
- namespace or application-level onboarding labels
- auto-instrumentation enablement annotations for supported languages

**Manual / service-team participation required:**

- application semantic conventions and custom attributes
- code-level instrumentation where auto-instrumentation is insufficient
- correlation-friendly log fields
- service ownership metadata if discovery cannot infer it

#### Logs (default, zero-code)

- Emit structured JSON to stdout/stderr where possible.
- Required minimum fields:
  - `service.name`
  - `deployment.environment`
  - `severity`
  - `message`
- Correlation:
  - include `trace_id` and `span_id` when tracing is enabled
- Result:
  - OpenTelemetry filelog receiver collects logs cluster-wide with no per-app
    log agent

#### Metrics (one toggle)

- Mode A (recommended):
  - expose `/metrics`
  - enable scrape annotations or labels through a Helm values block
- Mode B:
  - emit OTLP metrics from SDKs

#### Traces (one toggle plus instrumentation)

- W3C tracecontext propagation
- export via OTLP to gateway
- OpenTelemetry Operator-based auto-instrumentation where supported
- manual instrumentation for business-critical spans where required

#### Helm library chart: `observability-lib`

Every application chart can include:

- standard labels/annotations
- standard OTEL environment variables
- optional scrape annotations
- standard resource attributes
- standard onboarding policy toggles

Example values fragment per app:

```yaml
observability:
  enabled: true
  serviceName: checkout
  environment: prod
  ownerTeam: commerce
  metrics:
    scrape:
      enabled: true
      port: 8080
      path: /metrics
  traces:
    enabled: true
    autoInstrumentation: true
```

## 6. Step-by-Step Roadmap

The program is split into five major phases. Phase 1 contains internal sub-phases
for foundation, PoC, pilot, production, and hardening. Phases 2-5 build progressively
on the telemetry foundation.

### Phase 1: Core Observability Stack

#### Phase 1.0: Product Foundation, Guided Install, and Discovery

##### Goals

- Turn the implementation into a cluster product, not a one-off environment deployment.
- Make guided installation and discovery first-class capabilities.
- Build the open-source platform baseline.

##### Tasks (step-by-step)

1. Define the Install Contract and portable defaults.
2. Define the compatibility model:
    - supported Kubernetes distributions
    - supported storage profiles
    - supported object storage profiles
    - supported identity, secret, and ingress profiles
3. Implement the install/discovery engine:
    - preflight checks
    - capability detection
    - compatibility report
    - generated overlays
    - smoke test runner
4. Build the GitOps bootstrap package for self-hosted Argo CD.
5. Build Helm chart `observability-platform`:
    - operator
    - agent
    - gateway
    - dashboards
    - policy pack
    - RBAC
    - NetworkPolicies
    - PDBs
    - resource requests/limits
6. Build Helm library chart `observability-lib` for workload plug-in.
7. Package platform services:
    - Vault
    - ESO
    - SPIRE
    - cert-manager
    - Kyverno
    - Longhorn
    - MinIO
    - Velero
8. Package reference networking profile:
    - Cilium + Gateway API
9. Package reference storage/search profile:
    - OpenSearch + OpenSearch Dashboards
10. Package reference graph profile
    - Neo4j
11. Create dashboards/alerts packages as versioned artifacts in Git.
12. Implement CI examples
    - lint/validate
    - package/build
    - update GitOps state
    - post-deploy validation
13. Create a telemetry generator for smoke testing.
14. Create uninstall and rollback procedures.

##### Dependencies

- access to a Kubernetes cluster
- a supported storage class
- a supported ingress or Gateway API implementation, or ability to install one
- image registry access, preferably Harbor or another OCI-compatible registry

##### Acceptance Criteria

- Install on two distinct Kubernetes distributions using only Install Contract
  inputs and no manual YAML edits.
- Discovery engine produces a compatibility report and recommended mode.
- Generated overlays are deterministic and GitOps-safe.

##### Definition of Done

- versioned install/discovery release
- chart release
- documented runbooks
- CI example parity with local install path
- uninstall path documented and tested

##### Validation

- CI deploy succeeds into a test cluster and passes smoke tests.
- Local guided install produces equivalent GitOps state.
- Compatibility report matches actual cluster conditions.

##### Rollback

- revert Argo CD application to prior revision
- disable gateway export or isolate egress through values switch
- uninstall platform release through documented teardown

##### Risks + Mitigations

- hidden environment coupling:
  - block hard-coded values through lint and policy
- discovery false positives:
  - classify detections as `confirmed`, `assumed`, or `user-confirm-required`
- incompatible clusters:
  - fail early with compatibility report and remediation steps

#### Phase 1.1: PoC on One Existing Cluster

##### Goals

- Prove end-to-end ingestion of logs, metrics, and traces into OpenSearch.
- Validate guided install, onboarding flow, and default dashboards.

##### Tasks

1. Run discovery engine against one target cluster.
2. Select recommended install mode and generate overlays.
3. Deploy platform chart via Argo CD.
4. Instrument 1-2 demo or pilot services with OTLP exporters and tracecontext.
5. Implement log JSON schema and confirm `trace_id`/`span_id` correlation.
6. Apply OpenSearch templates, rollover policies, and baseline retention.
7. Install baseline dashboards:
    - cluster health
    - collector health
    - logs search
    - traces view
    - metrics overview
8. Validate backup targets:
    - MinIO bucket provisioning
    - Velero connectivity
9. Validate secret flow:
    - Vault + ESO sync for one representative runtime secret
10. Validate workload identity:
    - SPIFFE/SPIRE issuance for one representative workload

##### Dependencies

- development cluster access
- supported persistent storage
- supported ingress/Gateway capability
- registry access for platform images

##### Acceptance Criteria

- 95%+ of generated traces visible in trace views.
- Trace-to-log pivot works for instrumented requests.
- Metrics are queryable and chartable.
- Logs from multiple namespaces are visible with correct Kubernetes enrichment.
- Backup and secret flows are validated end-to-end.

##### Definition of Done

- documented PoC overlays
- PoC runbook
- PoC report with install findings, drop behavior, latency, and compatibility results

##### Validation

- synthetic load against demo services
- restart gateway
- temporarily isolate storage backend or exporter path
- verify backpressure and recovery behavior
- verify no uncontrolled field explosion in OpenSearch

##### Rollback

- disable exporters in gateway config and resync
- delete PoC indices and nonessential state
- uninstall the platform package cleanly

##### Risks + Mitigations

- incompatible storage profile:
  - use compatibility gating before install
- insufficient trace correlation:
  - require trace/log field contract in pilot services
- identity or secret bootstrap friction:
  - include guided validation steps and sample manifests

#### Phase 1.2: Pilot Services + Onboarding Contract Hardening

##### Goals

- Validate reliability, scale, and operator workflows with real services.
- Make service onboarding low-touch and consistent.

##### Tasks

1. Select 3-5 representative pilot services.
2. Onboard services using `observability-lib`.
3. Establish telemetry contracts:
   - required fields
   - required ownership metadata
   - label cardinality budgets
   - prohibited fields list
4. Implement Kyverno policies for:
   - required labels
   - scrape annotation shape
   - unsafe field and secret patterns
5. Harden secret flows:
   - Vault policies
   - ESO mappings
   - service-specific least privilege
6. Harden SPIFFE/SPIRE registration entries and trust domains.
7. Implement redaction processors and test suite.
8. Implement trace sampling defaults:
   - keep errors
   - keep slow requests
   - baseline sampling for normal traffic
9. Build service overview dashboards:
   - golden signals
   - dependency views
10. Define SLOs and burn-rate alerting.
11. Implement rollover, downsampling, and deletion policies.
12. Build runbooks and on-call handover.
13. Load test ingestion and indexing.
14. Test restore of one pilot namespace and one representative stateful component.

##### Dependencies

- service team participation
- agreement on ownership metadata
- alerting destination integrations if needed

##### Acceptance Criteria

- one-block Helm onboarding works
- pilot SLO dashboards are accurate
- alert noise remains controlled
- restore drill for representative pilot data succeeds
- service teams can self-onboard with minimal platform intervention

##### Definition of Done

- onboarding playbook published
- policy pack enforced
- operational readiness artifacts complete
- restore evidence recorded

##### Validation

- failure injection:
  - elevated errors
  - latency spike
  - dependency failure
- chaos tests:
  - collector pod restart
  - temporary storage pressure
  - secret refresh cycle
- verify:
  - alert routing
  - correlated dashboards
  - trace-to-log navigation
  - policy enforcement behavior

##### Rollback

- disable per-service tracing or scrape toggles
- disable auto-instrumentation annotations
- isolate one service without affecting the platform

##### Risks + Mitigations

- log schema inconsistency:
  - schema lint guidance + policy enforcement
- metrics cardinality explosion:
  - budgets + drop rules + downsampling
- ownership metadata gaps:
  - fail onboarding or mark as provisional until resolved

#### Phase 1.3: Production Rollout (Env-by-Env, Cluster-by-Cluster)

##### Goals

- Operationalize across dev, stage, and prod with tenancy isolation and compliance
  readiness.

##### Tasks

1. Run discovery and compatibility checks per target environment.
2. Decide mode per cluster:
    - attach
    - standalone
    - hybrid
3. Roll out collectors and platform components cluster-by-cluster with canary ordering.
4. Roll out OpenSearch, Vault, SPIRE, and supporting services according to the
  selected topology.
5. Apply tenancy model:
    - per-team index patterns
    - per-team roles
    - dashboard spaces
6. Instrument services by cohort.
7. Roll out dashboards and alerts-as-code to all environments.
8. Roll out backup schedules and restore drills.
9. Finalize security evidence:
    - access reviews
    - retention proofs
    - redaction tests
    - policy conformance reports
10. Publish support model and escalation matrix.

##### Dependencies

- security review approval
- capacity planning
- change windows
- confirmed storage and object storage capacity

##### Acceptance Criteria

- 90%+ target services emit traces
- 100% cluster/node metrics coverage
- 95%+ structured logs for onboarded services
- backup and restore posture active in every production environment
- on-call readiness complete

##### Definition of Done

- production support model live
- ownership matrix complete
- runbooks published
- quarterly restore schedule established

##### Validation

- compare known incident timelines against telemetry
- execute restore drill in non-prod
- peak-load ingestion test
- policy conformance test against production release candidates

##### Rollback

- disable export at gateway
- revert Argo CD to previous release tag
- reduce ingest through sampling/drop policies
- switch to logs-only minimum mode if required

##### Risks + Mitigations

- storage growth:
  - tiered retention and downsampling
- restore gaps:
  - scheduled drill evidence
- policy drift:
  - Kyverno conformance in CI and cluster

#### Phase 1.4: Scale Hardening and Optimization

##### Goals

- Maintain stability, resilience, and predictable cost as telemetry volume grows.

##### Tasks

1. OpenSearch capacity planning:
    - shard strategy
    - rollover sizing
    - index template hardening
2. Metrics downsampling and rollups.
3. Tail sampling tuning.
4. Meta-monitoring expansion:
    - ingestion lag
    - dropped telemetry
    - storage utilization
    - Longhorn health
    - MinIO health
5. Query optimization and dashboard cost hygiene.
6. Governance:
    - onboarding linting
    - required metadata conformance
7. Security hardening:
    - Vault policy reviews
    - SPIRE trust review
    - cert rotation tests
8. Quarterly restore drills and access reviews.

##### Acceptance Criteria

- peak ingestion sustained with bounded loss
- query performance meets defined SLOs
- restore objectives met in drills
- platform cost per workload stabilizes within target envelope

##### Definition of Done

- hardening checklist complete
- quarterly drill evidence captured
- optimization backlog created from measured findings

##### Validation

- restore drill into isolated environment
- load tests at projected peak volume
- certificate rotation test
- ESO refresh and secret rotation test

##### Rollback

- revert sampling and index template changes
- reduce retention
- disable high-cost dashboards or noncritical jobs
- scale back optional intelligence features

### Phase 2: Vectorization and AI Foundations

#### Goals

- Convert observability data into semantically searchable operational knowledge.
- Establish correlation foundations for later intelligence features.

#### Objective

- Make incidents, traces, logs, and summaries retrievable by semantic similarity,
  not only exact filtering.

#### Tasks

1. Enforce required correlation fields across telemetry:
    - `service.name`
    - `deployment.environment`
    - `team`
    - `k8s.cluster.name`
2. Build and maintain a service catalog and ownership map.
3. Normalize schemas and index mappings.
4. Build extraction pipelines for curated operational objects:
    - incident summaries
    - trace-group summaries
    - grouped error logs
    - alert context documents
    - deployment summaries
    - remediation notes
    - runbook chunks
    - service time-window summaries
5. Generate embeddings for selected entities.
6. Store embeddings in OpenSearch vector indices.
7. Build semantic retrieval service.
8. Build prompt context builder for later RCA features.
9. Implement PII and classification controls before any LLM access.
10. Implement anomaly detection on low-risk targets:
    - ingest lag
    - error rate anomalies
    - latency shifts
    - saturation trends

> Do not vectorize everything. Vectorize curated operational objects, not every
> raw data point.

##### Dependencies

- Phase 1 complete with stable telemetry flow.
- chosen embedding model and execution environment.

##### Acceptance Criteria

- similar incidents and telemetry can be retrieved semantically
- retrieval quality is measurable
- governance controls are enforced before LLM usage

##### Definition of Done

- embedding jobs operational
- semantic retrieval service deployed
- governance controls active

##### Validation

- retrieval evaluation against known incidents
- anomaly detector evaluation
- PII redaction validation before embedding generation

##### Rollback

- disable embedding jobs
- delete vector indices
- no impact on core telemetry path

##### Risks + Mitigations

- embedding quality:
  - start with incidents and runbooks
- model cost:
  - batch generation only
- PII in embeddings:
  - redact before embedding

### Phase 3: Core Graph Stack (Neo4j)

#### Goals

- Build a continuously refreshed operational knowledge graph in Neo4j.

#### Objective

- Represent services, infrastructure, teams, incidents, changes, and telemetry-derived
  dependencies as an explicit graph.

#### Tasks

1. Deploy Neo4j on Kubernetes using the platform delivery model.
2. Design and implement graph schema.
3. Build graph ETL and/or streaming derivation jobs.
4. Create graph freshness and lineage controls.
5. Build time-window graph snapshots for drift detection.
6. Implement graph health monitoring.
7. Add vector indexes for graph-native objects.

#### Recommended Graph Schema

Nodes:

- `Service`
- `Endpoint`
- `Namespace`
- `Cluster`
- `Node`
- `Pod`
- `Database`
- `Queue`
- `ExternalDependency`
- `Incident`
- `Alert`
- `Deployment`
- `Version`
- `Team`
- `Runbook`
- `SLO`
- `TraceGroup`
- `MetricSignal`
- `LogPattern`

Relationships:

- `CALLS`
- `DEPENDS_ON`
- `RUNS_IN`
- `HOSTED_ON`
- `OWNS`
- `ALERTED_ON`
- `AFFECTS`
- `TRIGGERED_BY`
- `DEPLOYED`
- `VIOLATES`
- `RELATED_TO`
- `MITIGATED_BY`
- `OBSERVED_DURING`

##### Graph update modes

- near-real-time stream for topology and incident edges
- scheduled batch for enrichment, drift detection, and graph snapshots

##### Dependencies

- stable trace data from Phase 1
- vector foundation from Phase 2 for graph-native retrieval

##### Acceptance Criteria

- service topology traversable upstream and downstream
- incident blast radius computable
- graph freshness SLA defined and monitored

##### Definition of Done

- Neo4j operational
- graph ETL pipelines running
- schema versioned and documented
- service dependency, incident, ownership, and change graphs populated

##### Validation

- verify dependencies against known trace flows
- verify blast radius against known incidents
- verify freshness targets

##### Rollback

- disable graph ETL jobs
- decommission Neo4j without affecting core telemetry path

##### Risks + Mitigations

- graph staleness:
  - freshness monitoring and alerting
- schema drift:
  - version schema and review changes
- ETL failures:
  - idempotent jobs with retries

### Phase 4: Graph Analytics and Risk Scoring

#### Goals

- Use graph algorithms and graph-derived features to quantify operational risk and
  detect likely failure propagation paths.

#### Objective

- Move from descriptive topology to predictive scoring.

#### Tasks

1. Build feature engineering jobs:
    - topology criticality
    - historical incident count
    - error propagation frequency
    - latency amplification
    - deployment churn
    - ownership maturity
    - SLO burn patterns
    - anomaly adjacency
2. Implement graph algorithms:
    - centrality
    - community detection
    - path analysis
    - link prediction
    - node embeddings
3. Build risk scoring model and service.
4. Build validation framework and backtesting.
5. Build risk dashboards and pre-deployment impact queries.
6. Integrate scoring into workflows.

##### Dependencies

- Phase 3 complete with populated graph

##### Acceptance Criteria

- risk scores explainable by features and traversals
- backtesting shows predictive value
- scoring is integrated into workflows

##### Definition of Done

- feature jobs operational
- scoring service deployed
- risk dashboards available

##### Validation

- backtest against historical incidents
- validate stability over time

##### Rollback

- disable scoring service
- no impact on graph or telemetry data

##### Risks + Mitigations

- model accuracy:
  - start with deterministic graph metrics first
- feature drift:
  - monitor distributions
- operator trust:
  - keep scoring advisory until validated

### Phase 5: LLM-Based RCA on the Graph

#### Goals

- Build an RCA copilot that reasons over topology, telemetry, prior incidents,
  and operational knowledge.

#### Objective

- Make the RCA assistant graph-aware and evidence-backed.

#### Tasks

1. Build retrieval orchestrator with three paths:
    - OpenSearch evidence retrieval
    - Neo4j graph retrieval
    - fusion layer
2. Implement RCA trigger flow from alert or incident.
3. Build copilot UI or API.
4. Build evaluation dataset from historical incidents.
5. Implement governance:
    - PII filtering
    - audit logs
    - human-in-the-loop approval
    - prompt-injection defenses

##### Dependencies

- Phases 2-4 complete
- chosen LLM execution model

##### Acceptance Criteria

- copilot reconstructs incident context from graph + telemetry
- recommendations are evidence-backed
- evaluation shows measurable MTTR improvement potential

##### Definition of Done

- retrieval orchestrator deployed
- API or UI available
- governance controls active

##### Validation

- evaluate against historical incidents
- verify audit and PII controls
- measure recommendation quality and coverage

##### Rollback

- disable copilot service
- no impact on graph or telemetry platform

##### Risks + Mitigations

- hallucination:
  - evidence-backed responses only
- prompt injection:
  - sanitize retrieved text
- PII leakage:
  - pre-retrieval redaction
- model cost:
  - bounded prompt size and async workflows

## 7. Detailed Technical Runbook

### 7.1 Cluster Prerequisites

- Supported cluster profiles:
  - Talos + kubeadm (reference)
  - RKE2
  - upstream kubeadm
  - K3s for quickstart only
- Namespace strategy:
  - `observability`
  - `observability-system`
  - `platform-security`
- RBAC:
  - least privilege for required Kubernetes metadata
- Pod security:
  - hostPath only where log collection requires it
  - restricted defaults for all other pods
- Storage:
  - Longhorn default StorageClass or compatible existing profile
- Object storage:
  - MinIO or compatible S3 endpoint
- Ingress:
  - Gateway API + Cilium preferred
- Certificates:
  - cert-manager required
- Identity:
  - SPIRE required for workload identity profile
- Secrets:
  - Vault + ESO required for default secret profile
- GitOps:
  - self-hosted Argo CD required for default delivery mode

### 7.2 Collector Topology and Baseline Configuration

**Agent DaemonSet responsibilities:**

- container logs tailing
- node/pod/container metrics
- optional scrape discovery for annotated services
- forward telemetry to gateway over OTLP

**Gateway responsibilities:**

- Kubernetes enrichment
- redaction transforms
- routing
- tail sampling
- batching and retries
- export to storage backends

**Sizing/backpressure:**

- DS sized for log tailing and scraping
- gateway uses HPA, memory limiter, queues, and bounded batch settings

**Baseline gateway config sketch:**

```yaml
receivers:
  otlp:
    protocols:
      grpc: {}
      http: {}

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 15
  k8sattributes:
    auth_type: serviceAccount
    passthrough: false
  resource:
    attributes:
      - key: deployment.environment
        action: upsert
        value: ${ENVIRONMENT}
      - key: k8s.cluster.name
        action: upsert
        value: ${CLUSTER_NAME}
  batch:
    timeout: 5s
    send_batch_size: 8192
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: slow
        type: latency
        latency:
          threshold_ms: 1000

exporters:
  opensearch:
    endpoints: ["${OPENSEARCH_ENDPOINT}"]

service:
  pipelines:
    logs:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [opensearch]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [opensearch]
    traces:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, resource, tail_sampling, batch]
      exporters: [opensearch]
```

### 7.3 Logs

**Collection:**

- agent uses file-based container log collection
- parse container runtime format and JSON payload where present

**Standard schema (required minimum):**

- `@timestamp`
- `message`
- `severity_text` or `severity_number`
- `service.name`
- `deployment.environment`
- `k8s.namespace.name`
- `k8s.pod.name`
- `k8s.container.name`
- `k8s.node.name`
- `trace_id` and `span_id` when tracing is enabled

**Multiline:**

- enable multiline rules for known stack trace patterns

**Redaction:**

- remove or mask:
  - authorization headers
  - tokens
  - cookies
  - PII fields per policy

**Index strategy:**

- `logs-${env}-${team}-*`

### 7.4 Metrics

**Collection approaches:**

- infrastructure metrics:
  - kubelet/pod/container metrics
  - kube-state metrics
- application metrics:
  - scrape annotations/labels
  - OTLP metrics from SDKs

**Cardinality controls:**

- forbid high-cardinality labels
- cap label count per metric family
- enforce histogram budget
- drop or rename unsafe labels in gateway

**Storage in OpenSearch:**

- metrics stored in controlled index families
- standardized field names
- downsampling after hot window
- retention enforced by lifecycle policy

### 7.5 Traces

**Instrumentation plan:**

- auto-instrumentation first where stable
- manual spans for critical business flows
- W3C tracecontext
- OTLP export to gateway

**Sampling:**

- keep errors
- keep slow requests
- baseline sampling for normal traffic
- higher budgets for tier-0 services

**Storage:**

- traces in dedicated OpenSearch index families
- shorter default retention than logs

### 7.6 OpenSearch Configuration

**Index templates:**

- strict mappings where possible
- controlled dynamic fields
- dedicated index families for logs, metrics, traces, vectors

**Lifecycle policies:**

- logs:
  - daily or size-based rollover
  - 30-day default retention
- metrics:
  - rollover + downsampling
  - 30-day default retention
- traces:
  - daily rollover
  - 14-day default retention
- vectors:
  - retention tied to use case and evidence lifecycle

**Snapshots:**

- snapshots to MinIO or compatible S3 storage
- restore drill runbook mandatory

### 7.7 Visualization

**Default:**

- OpenSearch Dashboards for logs, event analytics, trace analytics, alerting,
  and evidence views
- Grafana for metrics-first dashboards, SLO and NOC operations, and executive
  health boards
- Neo4j Browser for dependency traversal and blast-radius investigation when the
  graph module is enabled

**Optional:**

- Jaeger UI for specialist deep trace troubleshooting
- Neo4j Bloom for richer graph exploration and presentation workflows

**Signal-to-UI ownership:**

- Logs -> OpenSearch Dashboards
- Metrics -> Grafana
- Traces -> OpenSearch Dashboards by default; Jaeger UI optional
- Topology and dependency graph -> Neo4j Browser by default; Neo4j Bloom optional
- Executive service health and SLO views -> Grafana

### 7.7.1 Admin Access Plane and Externalized GUIs

The platform must externalize admin GUIs so operators can perform day-two
operations without direct shell access to cluster nodes.

Externally reachable admin GUIs include:

- OpenSearch Dashboards
- Grafana
- Neo4j Browser
- Jaeger UI when enabled
- Neo4j Bloom when enabled
- Argo CD UI

Access requirements:

- ingress and or Gateway API exposure modes
- TLS mandatory on all endpoints
- OIDC preferred for centralized authn
- SAML supported as an adapter path when required
- role and group to tool-RBAC mapping
- private or internal exposure as default posture
- internet-facing access allowed only with strict SSO and MFA controls
- audit logging and break-glass workflows documented and tested

**Dashboard taxonomy:**

- `platform/cluster/*`
- `platform/collectors/*`
- `platform/storage/*`
- `services/<team>/<service>/*`
- `security/audit/*`

### 7.8 Alerting and On-Call

**Alert philosophy:**

- SLO-based where possible
- minimal symptom-based alerts:
  - high error rate
  - latency spike
  - restart storms
  - dropped telemetry
  - backup failure
  - certificate expiry risk

**Noise controls:**

- deduplication
- multi-window confirmation
- maintenance windows
- runbook links in every alert

**Routing:**

- route by `team` label and service catalog ownership

### 7.9 SLO Program (Examples)

- availability
- latency p95
- error rate
- saturation
- dependency health

Error budgets must be defined by service tier and linked to alert policy.

### 7.10 Security Hardening

- encryption:
  - TLS everywhere
  - Vault Transit where payload encryption workflows are needed
- secrets:
  - Vault + ESO
- identity:
  - SPIFFE/SPIRE for workloads
  - Keycloak or Dex for humans
- authorization:
  - Kubernetes RBAC
  - platform-level role mappings
- network:
  - Cilium NetworkPolicies
  - Gateway API exposure only where justified
- tenancy:
  - per-team roles and index boundaries
- policy:
  - Kyverno enforcement for labels, annotations, and baseline safeguards
- data classification:
  - explicit denylist and redaction tests

### 7.11 DR and Backups

- Velero for Kubernetes resource backup and restore
- MinIO or compatible S3 target for backup storage
- snapshots for OpenSearch and stateful stores
- quarterly restore drills
- documented RTO/RPO per environment

### 7.12 Meta-Monitoring

- collector health:
  - queue depth
  - exporter errors
  - dropped telemetry
- storage health:
  - OpenSearch cluster status
  - Longhorn health
  - MinIO health
- security/control plane health:
  - Vault seal and readiness state
  - ESO sync failures
  - SPIRE health
  - cert-manager issuance failures
- platform growth:
  - daily index growth
  - storage consumption
  - backup success rates

### 7.13 Neo4j Technical Details

**Deployment:**

- self-managed on Kubernetes by default
- persistent storage on Longhorn or compatible backend

**Graph ETL design:**

- source:
  - OpenSearch indices
- primary derivation from traces first
- logs and metrics enrich later
- idempotent jobs with retry behavior

**Vector indexes in Neo4j:**

- embeddings on `Service`, `Incident`, `Deployment`, `Runbook`, `Endpoint` nodes

### 7.14 Vector Strategy

**OpenSearch evidence vectors:**

- incident summaries
- grouped error logs
- trace-group summaries
- deployment summaries
- alert context
- remediation notes
- runbook chunks
- service time-window summaries

**Neo4j graph/entity vectors:**

- service nodes
- endpoint nodes
- incident nodes
- deployment nodes
- runbook nodes
- neighborhood summaries
- learned node embeddings

**Hybrid retrieval:**

- OpenSearch evidence retrieval
- Neo4j graph retrieval
- fusion layer for RCA context assembly

## 8. CI/CD, IaC, GitOps

### Repository Structure

```text
observability-kit/
  install/
    discovery-engine/
    profiles/
      cluster/
      storage/
      identity/
      secrets/
      ingress/
  gitops/
    bootstrap/
      argocd/
    platform/observability/
      chart/
      values/
    platform/security/
      vault/
      eso/
      spire/
      cert-manager/
      kyverno/
    platform/network/
      cilium/
      gateway-api/
    platform/storage/
      longhorn/
      minio/
      velero/
    platform/search/
      opensearch/
      dashboards/
    platform/graph/
      neo4j/
    libraries/helm/observability-lib/
  infra/
    terraform-or-opentofu/
      optional/
  .github/workflows/
    validate.yaml
    package.yaml
    gitops-update.yaml
  Makefile
```

### IaC Modules (Optional Adapter Layer)

- IaC is optional, but when used it should expose reusable modules for:
  - `attach`
  - `standalone`
  - `gitops_bootstrap`
  - `search_lifecycle`
  - `identity_binding`
- Terraform or OpenTofu can implement these modules with equivalent contracts.
- Module outputs should feed generated GitOps overlays (endpoints, prefixes,
  tenancy identifiers, and profile selections).
- The installer and discovery engine remain the source of truth for generated
  defaults.

### GitOps Scope

- one Application or ApplicationSet per logical component group
- version pinning for charts and OCI artifacts
- generated overlays committed to GitOps repo
- Argo CD reconciles platform state

### CI/CD Strategy

- CI/CD-neutral by design
- reference example uses GitHub Actions for:
  - validate (lint, policy, schema checks)
  - package
  - update GitOps state
  - run post-deploy checks
- Jenkins, GitLab CI, Tekton, or others are valid if they preserve the same
  delivery contract

### Testing Strategy

- Helm lint and template validation
- OpenTelemetry config validation
- policy-as-code checks
- smoke tests
- load tests
- security tests
- restore tests

### Ownership Model

- platform/SRE:
  - collectors
  - platform services
  - OpenSearch/Neo4j operations
  - onboarding templates and enforcement
- service teams:
  - instrumentation quality
  - metrics label discipline
  - log structure compliance
- security/platform security:
  - Vault, SPIRE, cert-manager, policy baselines

## 9. Backlog Breakdown (Epics to Stories/Tasks)

### Phase 1: Core Observability

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E0 Productize platform | install contract, compatibility model, discovery engine, uninstall path | install on 2 cluster types with generated overlays |
| E1 GitOps foundation | self-hosted Argo CD bootstrap, repo layout, promotion flow | GitOps bootstrap works with no manual drift |
| E2 Collector platform | operator, agent, gateway, RBAC, NP, PDB | collectors healthy and stable |
| E3 Platform security | Vault, ESO, SPIRE, cert-manager, Kyverno | secret, identity, and PKI flows validated |
| E4 Storage platform | Longhorn, MinIO, backup paths | persistent services and backups validated |
| E5 Search platform | OpenSearch, Dashboards, index templates, lifecycle | logs/metrics/traces queryable and retained correctly |
| E6 Networking profile | Cilium + Gateway API baseline | ingress/gateway profile validated |
| E7 Logs | file tailing, parsing, schema, redaction | cluster logs visible, PII tests pass |
| E8 Metrics | infra metrics, scrape opt-in, cardinality guards | infra and app metrics available |
| E9 Traces | OTLP, sampling, app plug-in lib | trace visibility and pivots work |
| E10 Dashboards-as-code | baseline dashboards, saved objects, release flow | dashboards deployed and versioned |
| E11 Alerting + SLO | burn-rate alerts, routing, runbooks | alert noise targets met |
| E12 Meta-monitoring | health dashboards and alerts for platform services | lag, drops, storage issues detected |
| E13 DR drills | Velero, snapshots, restore automation | restore drill evidence recorded |
| E14 Onboarding lib | `observability-lib`, policy templates | one-block onboarding works for 3+ services |

### Phase 2: Vectorization and AI Foundations

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E15 Correlation enforcement | required field validation, schema normalization | required fields enforced |
| E16 Service catalog | service/team/tier mapping | catalog queryable |
| E17 Embedding pipeline | extraction jobs, embeddings, vector indices | semantic search works |
| E18 Semantic retrieval | retrieval API, ranking, evaluation | retrieval quality measurable |
| E19 Anomaly detection | anomaly jobs for key signals | detectors running and evaluated |
| E20 AI governance | classification, PII controls, audit | controls active before LLM usage |

### Phase 3: Core Graph Stack

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E21 Neo4j deployment | Helm deployment, persistence, monitoring | Neo4j operational |
| E22 Graph schema | node/relationship model, standards | schema documented and versioned |
| E23 Graph ETL | topology and enrichment jobs | service graph populated |
| E24 Incident graph | incident/alert/change nodes and edges | blast radius computable |
| E25 Ownership graph | team/service/SLO relationships | ownership queryable |
| E26 Graph monitoring | freshness SLAs and ETL health | graph freshness meets SLA |
| E27 Graph vectors | vector indexes on graph entities | graph retrieval works |

### Phase 4: Graph Analytics and Risk Scoring

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E28 Feature engineering | graph-derived features | features versioned |
| E29 Graph algorithms | centrality, community, path analysis | algorithm outputs available |
| E30 Risk scoring model | scoring service, explanations | scores explainable |
| E31 Risk dashboards | views and pre-deployment queries | workflows use scores |
| E32 Scoring validation | offline evaluation, backtesting | predictive value shown |

### Phase 5: LLM-Based RCA

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E33 Retrieval orchestrator | OpenSearch + Neo4j hybrid retrieval | quality metrics met |
| E34 RCA trigger flow | alert-to-context pipeline | context reconstruction works |
| E35 Copilot UI/API | operator-facing RCA interface | evidence-backed output |
| E36 Evaluation | historical incident benchmark | MTTR improvement potential shown |
| E37 Governance | audit, PII filtering, prompt defenses | audit trail and controls complete |

## 10. Risk Register

| Risk | Impact | Likelihood | Mitigation | Owner |
| ---- | ---- | ---- | ---- | ---- |
| Metrics cardinality overwhelms OpenSearch | High | High | label budgets, drop rules, downsampling | Observability lead |
| Log mapping explosion | High | Medium | strict mappings, schema contracts | Platform team |
| PII leakage into telemetry | High | Medium | redaction processors, policy, tests | Security |
| Hidden environment coupling | Medium | Medium | discovery engine + generated overlays | DevOps lead |
| Backup not actually restorable | High | Medium | quarterly restore drills | Platform lead |
| Vault or ESO misconfiguration breaks runtime secrets | High | Medium | staged rollout, policy tests, rotation drills | Platform security |
| SPIRE trust or registration errors break workload identity | Medium | Medium | staged registration, health monitoring | Platform security |
| Storage profile incompatibility | High | Medium | capability detection and supported profiles | Platform team |
| OpenSearch query performance degrades | High | Medium | shard strategy, lifecycle tuning, query hygiene | Platform team |
| Over-alerting increases on-call load | Medium | Medium | burn-rate alerts, dedup, runbooks | SRE manager |
| Neo4j graph staleness | Medium | Medium | freshness monitoring, idempotent ETL | Platform team |
| Embedding quality insufficient | Medium | Medium | start with narrow domains, iterative evaluation | AI/ML team |
| PII leakage into LLM prompts | High | Medium | pre-retrieval redaction and audit | Security |
| LLM hallucination in RCA | High | Medium | evidence-backed responses, human approval | AI/ML team |
| Prompt injection via logs | High | Low | sanitize text before prompt inclusion | Security |
| Model cost escalation | Medium | Medium | batch processing, limits, budget alerts | Platform lead |

## 11. Cost and Capacity Notes

### Main Drivers

- log ingest volume
- metrics cardinality
- trace volume and retention
- OpenSearch shard and storage growth
- Longhorn volume footprint
- MinIO object storage consumption
- Neo4j graph size and query rate
- embedding generation compute
- LLM inference cost in later phases

### Control Levers

- retention by signal and team
- downsampling after hot window
- label/cardinality budgets
- trace sampling
- daily index growth dashboards
- vectorizing curated objects only
- batching embedding jobs
- staged enablement of graph and RCA features

## 12. Go-Live Checklist

### Phase 1 Go-Live

- [ ] Install Contract documented and validated on 2 cluster types.
- [ ] Discovery engine produces a compatibility report and generated overlays.
- [ ] Argo CD bootstrap is fully automated.
- [ ] Vault + ESO flow validated.
- [ ] SPIFFE/SPIRE workload identity validated.
- [ ] cert-manager issuance and renewal validated.
- [ ] Cilium + Gateway API exposure validated.
- [ ] Longhorn persistent volumes validated.
- [ ] MinIO object storage validated.
- [ ] Velero backup and restore drill completed.
- [ ] Logs, metrics, and traces visible and correlated.
- [ ] Redaction verified.
- [ ] Dashboards and alerts deployed by GitOps.
- [ ] Meta-monitoring active.
- [ ] Rollback tested.
- [ ] Operational handover complete.
- [ ] Security review complete.
- [ ] Compliance evidence pack prepared and versioned.

### Phase 2 Go-Live

- [ ] Correlation fields enforced.
- [ ] Service catalog operational.
- [ ] Embedding jobs operational.
- [ ] Vector indices populated.
- [ ] Semantic retrieval service deployed.
- [ ] Governance controls verified.

### Phase 3 Go-Live

- [ ] Neo4j operational.
- [ ] Graph schema versioned.
- [ ] Graph ETL running and monitored.
- [ ] Dependency graph verified.
- [ ] Incident and ownership graphs populated.
- [ ] Graph freshness SLA monitored.

### Phase 4 Go-Live

- [ ] Feature jobs operational.
- [ ] Risk scoring evaluated.
- [ ] Risk dashboards available.
- [ ] Backtesting shows value.

### Phase 5 Go-Live

- [ ] Hybrid retrieval orchestrator deployed.
- [ ] Copilot API or UI available.
- [ ] PII filtering verified.
- [ ] Audit logging operational.
- [ ] Human-in-the-loop flow tested.
- [ ] Prompt-injection defenses tested.
- [ ] Evaluation shows MTTR improvement potential.

## 13. Deliverables (Concrete Artifacts)

### Architecture and Decisions

- reference architecture diagram
- ADRs:
  - deployment modes
  - compatibility model
  - identity model
  - secrets model
  - storage model
  - sampling strategy
  - Neo4j deployment model
  - vector strategy
  - AI governance model

### Infrastructure as Code

- optional IaC modules:
  - `attach`
  - `standalone`
  - `gitops_bootstrap`
  - `search_lifecycle`
  - `identity_binding`
- environment overlays generated from discovered capabilities and module
  outputs
- policy checks for no hard-coded endpoints and no secrets committed to Git

### Platform Packages

- install/discovery engine
- Argo CD bootstrap package
- Helm chart `observability-platform`
- Helm library chart `observability-lib`
- Vault/ESO package
- SPIRE package
- cert-manager package
- Kyverno package
- Cilium + Gateway API package
- Longhorn package
- MinIO package
- Velero package
- OpenSearch + Dashboards package
- Neo4j package

### OpenSearch Configuration

- index templates and mappings
- lifecycle policies
- snapshot configuration
- dashboard objects

### Neo4j Configuration

- graph schema docs
- ETL definitions
- vector index configuration
- freshness monitoring

### Dashboards and Alerts

- dashboards-as-code
- alerts-as-code
- SLO definitions
- runbooks

### AI/ML Artifacts

- embedding jobs
- retrieval service
- risk scoring service
- RCA orchestrator
- copilot API/UI

### Operational Docs

- install
- upgrade
- rollback
- uninstall
- restore drill runbook
- onboarding guide
- troubleshooting guides
- security operations procedures

### Security Evidence Pack

- policy baselines and admission-control evidence
- encryption and key-management settings
- access review procedure and tenant isolation validation
- redaction and sensitive-data test results
- AI governance documentation for RCA phases
