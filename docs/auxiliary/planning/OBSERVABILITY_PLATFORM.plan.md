# Observability Platform Plan

**Target**: A portable, plug-and-play observability intelligence platform for
any existing EKS cluster in any AWS account, deployable from a personal machine
or GitHub Actions, using Terraform + Helm + ArgoCD Capability, with
OpenTelemetry as the sole collector, Amazon OpenSearch as the single telemetry
store, and Neo4j as the derived graph intelligence layer.

## 1. Executive Summary

- Deliverable is a portable "observability kit" that installs on any existing
  EKS cluster in any AWS account with minimal inputs, using Terraform for
  AWS-side resources and ArgoCD Capability + Helm for all in-cluster resources.
- OpenTelemetry Collector is the only collector/agent for logs, metrics, and
  traces. No parallel agents (no Fluent Bit, no Prometheus server, no vendor
  agents).
- Amazon OpenSearch is the single telemetry store for logs, metrics, and traces.
  Amazon OpenSearch Ingestion (OSI) is the managed ingestion layer receiving
  OTLP and writing into OpenSearch indices aligned to SS4O/SSFO schemas.
- Neo4j is the derived relationship and reasoning store for dependency graphs,
  incident graphs, change graphs, risk graphs, and GraphRAG context. It
  complements OpenSearch - raw telemetry stays in OpenSearch; Neo4j holds
  curated, derived, relationship-rich entities and aggregates.
- Plug-in model for workloads is standardized and low-touch:
  - Logs: cluster-wide collection from stdout/stderr via a structured JSON
    contract.
  - Metrics: scrape opt-in via a single values block (annotations) or OTLP
    metrics.
  - Traces: "one toggle" per service via Helm library injection + language
    auto-instrumentation.
- No hard-coded environment values in templates. All configuration via Terraform
  variables and Helm values overlays. Sensitive data via GitHub
  Secrets/Variables and/or AWS Secrets Manager, materialized into Kubernetes
  Secrets only when unavoidable.
- Deployable from a personal machine or GitHub Actions with identical outcomes:
  Terraform applies AWS/K8s bootstrap, ArgoCD reconciles all Kubernetes
  resources, and a post-deploy smoke test validates logs/metrics/traces
  end-to-end.
- Operations-ready: dashboards/alerts-as-code, runbooks, on-call routing, SLO
  program, DR snapshots/restore drills, and meta-monitoring for collector, OSI,
  and OpenSearch health.
- AI roadmap is staged across five phases: core observability, then
  vectorization and semantic retrieval, then Neo4j graph construction, then
  graph ML risk scoring, then LLM-assisted RCA copilot with governance controls
  over PII and prompt-injection risk.
- The platform is not only an observability system. It is a staged operational
  intelligence platform with a clean separation between raw telemetry
  (OpenSearch), graph intelligence (Neo4j), and AI reasoning (hybrid retrieval +
  LLM).

## 2. Assumptions

- Base infrastructure already exists: VPC, EKS Auto Mode cluster (v1.35), ArgoCD
  Capability, ECR, AWS Secrets Manager, required endpoints/connectivity, and
  baseline security posture.
- Default deployment mode is `attach`:
  - OpenSearch and OSI may already exist, or will be provisioned by a separate
    platform process.
  - This kit deploys all in-cluster observability components and can optionally
    provision OpenSearch/OSI if `standalone` is enabled.
- AWS account model: AWS Organizations with at least one "observability
  platform" account and workload accounts. Private connectivity
  (TGW/PrivateLink) for cross-account ingest.
- Regions: us-east-1, us-east-2.
- OpenSearch deployment model: Managed Amazon OpenSearch Service (provisioned
  domain) as default. OpenSearch Serverless and self-managed-on-EKS are treated
  as alternatives.
- Network: VPC-only access to OpenSearch (no public endpoints). OSI pipelines
  configured to run with private connectivity.
- Environment model: dev/stage/prod (can be any string). Prefer hard isolation
  per environment (separate OpenSearch domain/collection per env).
- Multi-cluster supported: each cluster runs its own collectors; all clusters in
  an env write to the env's OSI endpoint and OpenSearch store with cluster
  identity tags for routing and analysis.
- Primary visualization is OpenSearch Dashboards for all signals to minimize
  overhead. Grafana is optional and only as a UI on top of OpenSearch if
  mandated.
- Retention defaults (can be overridden):
  - Logs: 30 days
  - Metrics: 30 days with downsampling after 7 days
  - Traces: 14 days with tail sampling
- Compliance: SOC2/PCI/HIPAA/GDPR aware. Treat all telemetry as potentially
  sensitive; default deny indexing of secrets/credentials; implement redaction
  and field-level access controls.
- Incident tooling: PagerDuty/Opsgenie optional; baseline uses OpenSearch
  Alerting + existing enterprise paging integration.
- CI/CD: GitHub Actions (Terraform plan/apply, gates). ArgoCD already deployed -
  add Application(s) + Helm for EKS workloads.
- IaC: Terraform for AWS resources.
- Secrets: AWS Secrets Manager, GitHub Repo Secrets.
- Neo4j deployment: Neo4j AuraDB (managed) preferred for low ops overhead.
  Self-managed on EKS only if strict self-hosting is required.

## 3. Clarification Q&amp;A + Resulting Decisions

No clarification questions asked. The plan proceeds with default decisions
consistent with the constraints and the "base infra exists" statement.

Resulting default decisions:

- OpenSearch model: Managed OpenSearch (domain/collection) in each environment,
  with OSI pipelines per environment.
- Tenancy model: environment isolation first; within env, per-team index
  prefixes + fine-grained roles + Dashboards tenants/spaces.
- Collector topology: mixed Agent DaemonSet + Gateway Deployment.
- Deployment: Terraform bootstraps ArgoCD apps; ArgoCD owns Helm releases and
  Kubernetes objects.
- Neo4j model: AuraDB managed; Aura Graph Analytics for GDS workloads.
- Vector strategy: OpenSearch evidence vectors for telemetry-derived documents;
  Neo4j graph/entity vectors for graph-native objects; no indiscriminate raw
  telemetry vectorization.

## 4. Architecture Variations + Decision Matrix

### Variations (all store logs/metrics/traces in OpenSearch)

- V1 (Recommended): OpenTelemetry Agent DS + OpenTelemetry Gateway ->
  OSI (OTLP) -> Managed
  OpenSearch -> OpenSearch Dashboards
- V2: OpenTelemetry Agent DS only (no gateway) -> OSI -> OpenSearch
- V3: OpenTelemetry Agent DS + Gateway -> Self-managed Data Prepper on EKS -> OpenSearch
- V4: OpenTelemetry Agent DS + Gateway -> OSI -> OpenSearch Serverless (collection)

In all variations, Neo4j is a derived graph tier with a defined sync model fed
by derivation from OpenSearch telemetry.

### Decision Matrix

| Dimension | V1 DS+GW+OSI+AOS | V2 DS-only+OSI | V3 DS+GW+DP+OS | V4 DS+GW+OSI+Serverless |
| ---- | ---- | ---- | ---- | ---- |
| Delivery effort | Medium | Low | High | Medium |
| Ops overhead | Low | Low | High | Low-Medium |
| Failure isolation | High | Medium | Medium | Medium |
| Sampling control | High (tail) | Low-Medium | High | High |
| Transform/enrichment | High | Medium | High | Medium |
| Scalability | High | Medium | Medium | Medium |
| Feature maturity | High | High | Medium | Medium (subset) |
| Compliance controls | High | High | Depends | High |
| Cost control levers | High | Medium | Medium | Medium |
| Recommendation | Primary | Very small clusters only | Managed not allowed | Serverless mandated |

**Selection**: V1.

**Rationale**: Best balance of portability, strong backpressure/sampling
control, and low ops burden while preserving OpenTelemetry-only collection and
OpenSearch-only storage. Aligns with AWS guidance that telemetry is collected
(OpenTelemetry Collector) then sent to OSI (managed serverless pipeline) for
filtering/enrichment, then stored in OpenSearch for unified analysis.

## 5. Recommended Target Architecture

### Platform Layers

The platform is organized into three planes:

- **Telemetry plane**: OpenTelemetry Collectors, OSI, OpenSearch, Dashboards.
- **Graph plane**: Neo4j for dependency, blast-radius, incident, change, and
  ownership graphs.
- **Intelligence plane**: embedding jobs, graph analytics jobs, risk scoring,
  and LLM-assisted RCA.

### Components

#### In-cluster (per EKS cluster)

- `otel-agent` DaemonSet
  - filelog receiver for container logs
  - kubelet/node/pod metrics collection + optional scrape for annotated services
  - forwards OTLP to gateway
- `otel-gateway` Deployment + HPA
  - enrichment, redaction, routing, tail sampling, batching, retry/backpressure
  - single egress to OSI OTLP endpoint
- Optional onboarding primitives
  - namespace labels/quotas
  - policy-as-code (Kyverno/Gatekeeper) to enforce telemetry labels and prevent
    unsafe label usage

#### AWS-side (per environment)

- OSI pipeline(s)
  - single OTLP ingest endpoint per env
  - minimal transforms (enrichment pushed to collector)
  - writes to OpenSearch indices for logs/metrics/traces
- OpenSearch (domain/collection)
  - index templates/mappings aligned to SS4O/SSFO
  - ISM policies for rollover/tiering/retention
  - vector indices (k-NN) for evidence embeddings (Phase 2+)
  - snapshots to S3 and restore drill procedure
- IAM/KMS
  - least privilege for OSI and platform operators
  - encryption at rest and in transit

#### Graph tier (Phase 3+)

- Neo4j AuraDB (or self-managed on EKS)
  - property graph for services, dependencies, incidents, changes, teams,
    infrastructure
  - vector indexes for graph entity embeddings
- Graph ETL / streaming derivation jobs
  - read from OpenSearch, write derived entities to Neo4j
- Neo4j GDS / Aura Graph Analytics (Phase 4+)
  - centrality, community detection, link prediction, graph ML

### Data Flows

1. Workloads emit logs to stdout/stderr (JSON recommended).
2. `otel-agent` tails `/var/log/containers/*`, enriches with k8s metadata, and
   forwards OTLP to `otel-gateway`.
3. Workloads emit OTLP traces/metrics (if instrumented) to `otel-gateway` (or to
   agent which forwards).
4. `otel-gateway` applies redaction, resource normalization, tail sampling,
   batching, and exports OTLP to OSI endpoint.
5. OSI ingests OTLP and writes to OpenSearch index families: `logs-*`,
   `metrics-*`, `traces-*` (plus trace analytics/service-map indices if
   configured).
6. OpenSearch Dashboards provides unified query, correlation, and operational
   views.
7. (Phase 2+) Embedding generation jobs produce evidence vectors stored in
   OpenSearch k-NN indices.
8. (Phase 3+) Graph ETL reads from OpenSearch and derives service topology,
   incident graphs, change graphs, and ownership relationships into Neo4j.
9. (Phase 4+) Graph analytics jobs compute risk scores, centrality, community
   structure.
10. (Phase 5) Hybrid retrieval orchestrator queries OpenSearch (evidence
    vectors) + Neo4j (graph traversal + entity vectors) to feed context to LLM
    for RCA.

### Tenancy Boundaries

- Environment isolation: separate OpenSearch and OSI per env (preferred).
- Within env:
  - Index patterns: `logs-${env}-${team}-*`, `metrics-${env}-*`,
    `traces-${env}-*`
  - Dashboards tenants/spaces per team
  - Role mappings for least privilege
- Multi-cluster:
  - All events carry `k8s.cluster.name` (or equivalent attribute) to
    filter/analyze per cluster.
- Multi-account ingestion:
  - Workload VPCs connect to platform VPC (TGW/PrivateLink patterns)
  - Authenticate using IAM-signed requests/roles scoped to OSI ingest only
  - No direct OpenSearch write from workloads

### Install Contract (Minimum Configuration Surface)

**Required inputs per cluster/environment:**

- `cluster_name`
- `aws_region`
- `environment` (dev/stage/prod or free-form)
- `mode`:
  - `attach` (default): uses existing OpenSearch/OSI endpoints
  - `standalone`: creates OpenSearch/OSI in the target account
- `gitops_repo_url`
- `gitops_path`

**Required inputs only in `attach` mode:**

- `opensearch_endpoint`
- `osi_otlp_endpoint`

**Sensitive inputs (never committed):**

- Private Git credentials (only if ArgoCD cannot use an existing trust path)
- Dashboards auth integration secrets (OIDC/SAML/Cognito)

Everything else is either discovered via AWS APIs (VPC/subnets/OIDC) or
defaulted via sane module defaults.

### Secrets and Configuration Policy

- No secrets in Git.
- No hard-coded endpoints or account identifiers inside chart templates.
- Prefer IAM- and network-based auth over static secrets.
- Canonical secret paths:
  - **GitHub Secrets/Variables**: CI-only values (AWS role to assume, env
    selectors)
  - **AWS Secrets Manager**: long-lived secrets (OIDC client secret, private
    repo tokens)
  - **Kubernetes Secrets**: only when a workload must read it at runtime,
    created via CI templating at deploy time, or External Secrets (if already
    present), or ArgoCD-managed sealed/encrypted secrets
- Terraform state hygiene: do not pass raw secrets as Terraform variables. Store
  in Secrets Manager and reference by ARN.

### Plug-in Model for Workloads (Standard Onboarding Contract)

#### Logs (default, zero-code)

- Emit structured JSON to stdout/stderr.
- Required fields (minimum): `service.name`, `deployment.environment`,
  `severity`, `message`.
- Correlation: include `trace_id` and `span_id` when tracing is enabled.
- Result: OpenTelemetry filelog receiver tails container logs cluster-wide. No per-app
  agent.

#### Metrics (one toggle)

- Mode A (recommended): expose `/metrics` Prometheus endpoint and enable scrape
  annotations via Helm values.
  - Standard annotations: `prometheus.io/scrape: "true"`, `prometheus.io/port`,
    `prometheus.io/path`
- Mode B: OTLP metrics from SDKs to gateway.

#### Traces (one toggle plus instrumentation)

- W3C tracecontext propagation.
- Export: OTLP to gateway service.
- Auto-instrumentation patterns supported by Helm library chart injection where
  viable.

#### Helm library chart: `observability-lib`

Every application chart can include:

- Standard labels/annotations
- Standard OTEL env vars (`OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
  `OTEL_PROPAGATORS`)
- Optional scrape annotations
- Standard resource attributes

Example values fragment per app:

```yaml
observability:
  enabled: true
  serviceName: checkout
  environment: prod
  metrics:
    scrape:
      enabled: true
      port: 8080
      path: /metrics
  traces:
    enabled: true
```

## 6. Step-by-Step Roadmap

The program is split into five major phases. Phase 1 (core observability)
contains internal sub-phases for PoC -> pilot -> production -> hardening. Phases
2-5 build progressively on the telemetry foundation.

### Phase 1: Core Observability Stack

#### Phase 1.0: Kit Foundation (Productization for Portability)

##### Goals

- Turn the implementation into an installable kit for any existing EKS cluster.

##### Tasks (step-by-step)

1. Define the Install Contract (variables) and defaults.
2. Build Terraform root module with `attach` and `standalone` modes.
3. Implement Terraform modules:
   - `attach`: IRSA, Kubernetes bootstrap, ArgoCD Applications
   - `standalone`: OpenSearch, OSI, KMS, ISM, networking bindings + everything
     in attach
   - `argocd_bootstrap`: Application/ApplicationSet definitions and repo
     integration
   - `ism_templates`: index templates, ISM policies, snapshot policies
   - `iam_irsa`: gateway service account role
4. Implement ArgoCD bootstrap module:
   - Creates ArgoCD `Application`/`ApplicationSet` pointing to
     `gitops/bootstrap`.
5. Build Helm chart `observability-platform`:
   - Agent DS, gateway, RBAC, NetworkPolicies, PDBs, resource requests/limits,
     ConfigMaps.
6. Build Helm library chart `observability-lib` for application plug-in:
   - Standard labels/annotations
   - OTEL env vars
   - Metrics scrape annotations toggles
7. Create dashboards/alerts packages as versioned artifacts in Git.
8. Implement GitHub Actions workflows:
   - `plan.yml` (PR): fmt/validate, plan, policy checks
   - `apply.yml` (merge): apply Terraform, render env overlay values, commit
     overlay changes to GitOps path
   - `validate.yml` (post-deploy): deploy telemetry generator, assert
     logs/metrics/traces present, cleanup
9. Create a telemetry generator for smoke testing.

##### Dependencies

- Access to cluster and ability to deploy ArgoCD resources.
- OSI/OpenSearch endpoints (for attach) or permissions to provision them
  (standalone).

##### Acceptance Criteria

- Install on two distinct existing EKS clusters with only Install Contract
  inputs and no manual edits.

##### Definition of Done

- Versioned module release + chart release + documented runbooks + CI parity
  (local and GitHub Actions produce identical state).

##### Validation

- CI runs apply in a test environment and passes smoke tests.
- Local run reproduces identical state.

##### Rollback

- Revert ArgoCD application to prior Git revision.
- Disable gateway export (values switch) to stop data egress immediately.

##### Risks + Mitigations

- Hidden environment coupling: enforce "no hard-coded values" policy via CI
  linting on chart templates and Terraform.

#### Phase 1.1: PoC on One Existing Cluster (Attach Mode)

##### Goals

- Prove end-to-end ingestion of logs, metrics, traces into OpenSearch and basic
  correlation in Dashboards.

##### Tasks

1. Configure `attach` mode with env overlay values:
   - `osi_otlp_endpoint`
   - index prefixes
   - env/cluster identity
2. Deploy platform chart via ArgoCD (agent + gateway).
3. Instrument 1-2 demo/pilot services with OTLP exporters and W3C tracecontext.
4. Implement log JSON schema and ensure `trace_id`/`span_id` are present in
   logs.
5. Configure index templates and ISM policies (Terraform-managed or OpenSearch
   API-managed via controlled pipeline).
6. Install baseline dashboards:
   - Cluster health
   - Collector health
   - Logs search
   - Traces view (Trace Analytics)
   - Metrics overview

##### Dependencies

- Dev EKS cluster access; AWS IAM approvals for OpenSearch/OSI.
- OSI endpoint reachable from cluster (private routing).
- OpenSearch accessible from Dashboards.

##### Acceptance Criteria

- 95%+ of generated traces visible in Trace Analytics.
- Trace-to-log pivot works for instrumented requests.
- Metrics time series can be queried and charted.
- Logs from multiple namespaces visible with correct k8s enrichment.

##### Definition of Done

- Documented configs in Git.
- PoC runbook.
- PoC report: ingestion latency, drop behavior under stress, required
  configuration inventory.

##### Validation

- Generate synthetic load; confirm end-to-end latency (target: <60s logs, <30s
  metrics, <60s traces).
- Chaos tests:
  - Restart gateway
  - Temporarily block OSI endpoint
  - Verify backpressure and recovery behavior
- Index sanity:
  - Correct mappings for core fields
  - No runaway dynamic field creation

##### Rollback

- Disable exporters in gateway config and resync.
- Delete PoC indices or reduce retention to near-zero.

##### Risks + Mitigations

- OSI plugin subset constraints: keep pipelines minimal; push enrichment to OpenTelemetry
  Collector processors.
- Metrics cardinality: implement label budget controls early (drop/rename
  attributes in gateway).
- SS4O/SSFO maturity gaps: constrain schema to supported fields first, adopt
  phased enrichment, maintain backward compatible mappings.

#### Phase 1.2: Pilot Services + Onboarding Contract Hardening

##### Goals

- Validate reliability, scale, and operational processes with a small cohort of
  real services.
- Make service onboarding low-touch and consistent.

##### Tasks

1. Select pilot services (criticality medium, representative languages).
2. Onboard 3-5 services using `observability-lib`:
   - Enable scrape annotations
   - Enable tracing toggle per service
3. Establish telemetry contracts:
   - Required fields and resource attributes
   - Label cardinality budgets
   - Prohibited labels/fields list (PII)
4. Production-grade security hardening: least privilege roles, network policies,
   secrets handling, audit evidence pack.
5. Implement redaction processor and test suite.
6. Implement tail sampling policy defaults:
   - 100% errors
   - Slow requests above threshold
   - Low-rate baseline sampling for normal traffic
7. Build service overview dashboards:
   - Golden signals (latency, traffic, errors, saturation)
   - Dependency views (derived from traces)
8. Define SLOs and implement burn-rate alerting for pilot services.
9. Implement ISM rollover + tiering + deletion policies per signal.
10. Create runbooks and on-call handover (triage, dashboards, query patterns).
11. Integrate paging/routing tool (if present).
12. Load test ingestion and OpenSearch indexing; tune shard counts, bulk sizes,
    refresh intervals.

##### Dependencies

- Service team buy-in for instrumentation.
- Agreement on team ownership labels.
- On-call tooling integration.

##### Acceptance Criteria

- "One block" Helm values onboarding works.
- Pilot SLO dashboards accurate.
- Alert noise controlled (target: <2 pages/week/service).
- Platform SLOs met.
- Pilot services have dashboards + alerts + runbooks and pass incident
  simulation drills.

##### Definition of Done

- Operational readiness: runbooks, paging, escalation, DR plan draft,
  meta-monitoring in place.
- Documented onboarding playbook + templates + automated checks.

##### Validation

- Simulated failure injection:
  - Elevated errors
  - Increased latency
  - Dependency failure
- Verify:
  - Alert triggers with correct routing
  - Dashboards show correlated evidence
  - Trace-to-log navigation works
- Chaos tests: collector pod restarts, OSI throttling, OpenSearch node failover;
  verify data loss bounds and recovery.

##### Rollback

- Disable per-service toggles (tracing/scrape) without touching the platform.
- Per-service instrumentation can be disabled (env var) and gateway route
  disabled per namespace.

##### Risks + Mitigations

- Log schema inconsistency: provide schema lint guidance and enforce minimal
  required fields via app library and docs.
- Metrics cardinality explosion: label budgets, drop high-cardinality labels,
  aggressive downsampling.

#### Phase 1.3: Production Rollout (Env-by-Env, Cluster-by-Cluster)

##### Goals

- Operationalize across dev/stage/prod with tenancy isolation and compliance
  readiness.

##### Tasks

1. Deploy per-env OSI/OpenSearch or attach endpoints per env.
2. Stand up prod OpenSearch domain + prod OSI pipelines and separate IAM roles.
3. Apply tenancy model:
   - Per-team indices + roles + Dashboards tenants
4. Roll out collectors to all clusters in the env with canary:
   - One cluster first, then remaining clusters
5. Instrument services by cohort (language owners), enforce propagation and
   required attributes.
6. Roll out dashboards/alerts-as-code to all envs.
7. Alerting rollout with SLO-based alerts and symptom-based alerts.
8. Implement change management:
   - Release tags for chart/config
   - Controlled promotion between envs
9. Compliance evidence: audit logs, access reviews, data retention proofs,
   redaction tests.

##### Dependencies

- Security review approval.
- Network approvals for private connectivity.
- Change management windows.

##### Acceptance Criteria

- Coverage:
  - 90%+ services emitting traces
  - 100% cluster/node metrics
  - 95%+ logs structured JSON for onboarded services
  - Logs cluster-wide
  - Infra metrics complete
  - Tracing enabled for target service subset
- Operational readiness:
  - On-call trained
  - Runbooks published
  - Incident workflow validated

##### Definition of Done

- Production support model live: ownership matrix, runbooks, training, on-call
  schedules, quarterly access reviews.
- Production support handover signed.

##### Validation

- Compare known incident timelines against telemetry; verify correlation reduces
  MTTR baseline.
- DR simulation: snapshot restore drill in a non-prod environment.
- Performance: peak-load ingestion test and OpenSearch indexing health.

##### Rollback

- Disable export at gateway.
- Revert ArgoCD to previous release tag.
- Reduce ingest volume via sampling and drop processors.
- Fall back to minimal logs-only ingestion if needed.

##### Risks + Mitigations

- Storage growth and cost: ISM tiering, shorter trace retention, sampling,
  rollups/downsampling.

#### Phase 1.4: Scale Hardening and Optimization

##### Goals

- Maintain stability, resilience, and cost predictability as telemetry volume
  grows.

##### Tasks

1. OpenSearch capacity planning:
   - Shard strategy
   - Index rollover sizing
   - Hot/warm/cold policies (if applicable)
2. Metrics downsampling and rollups.
3. Tail sampling tuning based on incident learnings.
4. Index template hardening: mappings for common fields, strict types,
   keyword/text strategy, dynamic mapping limits.
5. Meta-monitoring expansion:
   - Ingestion lag dashboards
   - Dropped telemetry alerts
   - OSI pipeline alarms (CloudWatch)
6. Query performance optimization: optimize common queries, index sorting, force
   merge schedules, rollups.
7. Cost reduction: reduce cardinality, adjust refresh intervals, consolidate
   dashboards, tighten retention.
8. Governance: onboarding automation, linting rules for telemetry schemas,
   service ownership metadata.
9. Security posture: ongoing IAM least-privilege, rotation, audit dashboards.
10. Quarterly restore drills and access reviews.

##### Acceptance Criteria

- Sustains peak ingestion with bounded loss.
- RTO/RPO targets met in drills.
- Query performance meets defined SLOs.
- Cost per workload stabilizes within budget envelope.

##### Definition of Done

- Quarterly DR restore drill performed; documented and signed.

##### Validation

- Restore drill: snapshot restore into a test domain; validate dashboards and
  queries.
- Load tests at expected peak volumes; confirm index growth projections.

##### Rollback

- Adjust sampling/retention; revert index template versions.
- Scale down retention and sampling; disable expensive dashboards/queries;
  throttle at OSI or gateway.

### Phase 2: Vectorization and AI Foundations

#### Goals

- Convert observability data into semantically searchable operational knowledge.
- Establish the correlation foundations that later phases depend on.

#### Objective

- Make incidents, traces, logs, and summaries retrievable not only by exact
  filters but also by semantic similarity.

#### Tasks

1. Enforce required correlation fields across all telemetry:
   - `service.name`, `deployment.environment`, `team`, `k8s.cluster.name`
   - Logs contain `trace_id` and `span_id` when traces exist
2. Build and maintain a service catalog and ownership metadata:
   - Map service to team/on-call and criticality tier
3. Normalize schemas and index mappings to prevent model features from drifting
   per team.
4. Build extraction pipeline from OpenSearch for curated operational objects:
   - Incident summaries
   - Trace-group summaries / trace exemplars
   - Grouped/clustered error logs (exception clusters)
   - Alert context documents
   - Deployment summaries / change records
   - Remediation notes / runbook chunks
   - Service time-window summaries
5. Generate embeddings for selected entities using an embedding model.
6. Store embeddings in OpenSearch k-NN vector indices:
   - `incident_vectors`: embeddings of incident summaries/alert contexts
   - `log_pattern_vectors`: embeddings of clustered log patterns
   - `span_vectors` (optional): embeddings of trace-group summaries
   - `remediation_vectors`: embeddings of runbook/remediation content
7. Build semantic retrieval service for initial use cases:
   - "Find incidents similar to this one"
   - "Find similar exception patterns in the last 90 days"
   - "Find prior remediation steps for this failure mode"
8. Build curated prompt context builder for later LLM use.
9. Implement data classification and PII controls before any LLM access.
10. Implement OpenSearch anomaly detection for low-risk targets:
    - Ingest lag anomalies
    - Error rate anomalies
    - Latency distribution shifts
    - Resource saturation trends

> [!IMPORTANT] Do not vectorize everything. Vectorize curated operational
> objects, not raw exhaust. Weak candidates for vectorization include single raw
> metric points, every individual span, every single log line, and raw
> Kubernetes event spam.

#### Dependencies

- Phase 1 complete with stable telemetry flow.
- Embedding model selection (consider AWS Bedrock or SageMaker hosted models
  within data boundaries).

#### Acceptance Criteria

- Similar incidents and related telemetry can be retrieved semantically.
- Retrieval quality is measurable and versioned.
- Data classification and PII controls in place before any LLM access.
- Anomaly detectors running with evaluation report.

#### Definition of Done

- Embedding generation jobs operational.
- Semantic retrieval service deployed and tested.
- Governance controls in place.

#### Validation

- Evaluate retrieval quality against known incidents.
- Measure false positive rates for anomaly detectors.
- Measure time-to-detect improvements.

#### Rollback

- Disable embedding jobs; delete vector indices.
- Disable anomaly detectors.
- No impact on core telemetry flow.

#### Risks + Mitigations

- Embedding quality: start with well-scoped domains (incidents, runbooks) before
  expanding.
- Cost of embedding model: use batch processing, not real-time embedding of all
  data.
- PII in embeddings: apply redaction before embedding generation.

### Phase 3: Core Graph Stack (Neo4j)

#### Goals

- Build a continuously refreshed operational knowledge graph in Neo4j.

#### Objective

- Represent services, infrastructure, teams, incidents, changes, and
  telemetry-derived dependencies as an explicit graph.

#### Tasks

1. Deploy Neo4j (AuraDB preferred, or self-managed on EKS via Helm + ArgoCD if
   self-hosting required).
2. Design and implement the graph schema.
3. Build graph ETL or streaming derivation jobs.
4. Create graph freshness and lineage controls.
5. Build time-window graph snapshot model for drift detection.
6. Implement graph monitoring and health checks.

#### Recommended Graph Schema

Nodes:

- `Service`, `Endpoint`, `Namespace`, `Cluster`, `Node`, `Pod`
- `Database`, `Queue`, `ExternalDependency`
- `Incident`, `Alert`, `Deployment`, `Version`
- `Team`, `Runbook`, `SLO`
- `TraceGroup`, `MetricSignal`, `LogPattern`

Relationships:

- `CALLS`, `DEPENDS_ON`, `RUNS_IN`, `HOSTED_ON`
- `OWNS`, `ALERTED_ON`, `AFFECTS`, `TRIGGERED_BY`
- `DEPLOYED`, `VIOLATES`, `RELATED_TO`
- `MITIGATED_BY`, `NEIGHBOR_OF`, `OBSERVED_DURING`

> [!TIP] Build the first version of the graph primarily from traces, not logs.
> The OpenTelemetry `servicegraph` connector generates service relationship
> metrics from
> traces, and the `spanmetrics` connector derives request, error, and duration
> aggregates from spans. Traces give you both topology and high-value edge
> attributes at once. Logs and metrics should enrich the graph after the initial
> skeleton is built.

#### Graph Update Modes

- Near-real-time stream for topology and incident edges.
- Scheduled batch jobs for deeper enrichment, drift detection, and graph
  snapshots over time.

#### Neo4j Vector Indexes

Store embeddings on graph entities for GraphRAG:

- Service descriptions
- Endpoint descriptions
- Incident nodes
- Deployment nodes
- Runbook nodes
- Topology snapshots
- Dependency edge summaries
- Graph neighborhood summaries

#### Dependencies

- Phase 1 complete with stable trace data.
- Phase 2 embedding infrastructure available for graph entity vectorization.

#### Acceptance Criteria

- Service topology can be traversed upstream and downstream.
- Incident blast radius can be computed from graph relationships.
- Graph freshness SLAs are defined and monitored.

#### Definition of Done

- Neo4j deployed and operational.
- Graph ETL pipelines running.
- Graph schema documented with naming standards.
- Service dependency, incident, change/deployment, and ownership graphs
  populated.

#### Validation

- Query known service dependencies and verify against trace data.
- Compute blast radius for a known incident and compare to actual impact.
- Verify graph freshness meets SLA.

#### Rollback

- Disable graph ETL jobs.
- Neo4j can be decommissioned without affecting core telemetry.
- No impact on OpenSearch or collector pipelines.

#### Risks + Mitigations

- Graph staleness: implement freshness monitoring and alerting.
- Graph schema drift: version schema, review changes.
- ETL failures: idempotent jobs with retry and dead-letter handling.

### Phase 4: Graph ML Risk Scoring

#### Goals

- Use graph algorithms and graph ML to quantify operational risk and detect
  likely failure propagation paths.

#### Objective

- Move from descriptive topology to predictive scoring.

#### Tasks

1. Build graph feature engineering jobs to derive composite features per node
   and edge:
   - Topology criticality (centrality metrics)
   - Historical incident count
   - Error propagation frequency
   - Latency amplification
   - Deployment churn
   - Ownership maturity
   - SLO burn patterns
   - Anomaly adjacency
   - Undocumented dependency likelihood
2. Implement graph algorithms:
   - Centrality: PageRank, betweenness, degree
   - Community: Louvain or related community detection
   - Path: shortest path / weighted path for blast radius
   - Prediction: link prediction for hidden dependencies
   - Classification: node classification/regression for service risk tier
   - Representation: node embeddings for downstream models
3. Build risk scoring model and scoring service.
4. Build validation framework with offline and incident-backtest evaluation.
5. Build risk dashboards and pre-deployment impact queries.
6. Integrate scoring into operational workflows:
   - Alert tuning based on risk scores
   - Pre-deployment risk gates
   - Capacity planning inputs

#### Dependencies

- Phase 3 complete with populated graph.
- Neo4j GDS or Aura Graph Analytics available.

#### Acceptance Criteria

- Risk scores explainable by features and traversals.
- Backtesting shows predictive value against historical incidents.
- Scoring is integrated into operational workflows, not only research notebooks.

#### Definition of Done

- Graph feature engineering jobs operational.
- Risk scoring model deployed and evaluated.
- Risk dashboards available.
- Pre-deployment impact queries available.

#### Validation

- Backtest risk scores against historical incidents.
- Validate that high-risk nodes correlate with actual failure patterns.
- Evaluate scoring stability over time.

#### Rollback

- Disable scoring service and dashboards.
- No impact on graph data or core telemetry.

#### Risks + Mitigations

- Model accuracy: start with deterministic graph metrics (centrality, path
  analysis) before adding ML models.
- Feature drift: monitor feature distributions over time.
- Operational trust: validate against real incidents before using for automated
  decisions.

### Phase 5: LLM-Based RCA on the Graph

#### Goals

- Build an RCA copilot that reasons over topology, telemetry, prior incidents,
  and operational knowledge.

#### Objective

- Make the RCA assistant graph-aware instead of only vector-aware, using
  GraphRAG for hybrid retrieval.

#### Tasks

1. Build RCA retrieval orchestrator with three paths:
   - **Path A - OpenSearch evidence retrieval**: semantic similarity from
     evidence vectors + standard filtered search over time, environment,
     service, namespace, severity
   - **Path B - Neo4j graph retrieval**: graph traversal for neighborhood, blast
     radius, and change context + optionally combined with Neo4j vector
     similarity over nodes/subgraphs
   - **Path C - Fusion layer**: get graph neighborhood from Neo4j, use it to
     constrain or rerank OpenSearch retrieval, pull semantically similar
     incidents from OpenSearch, pull semantically similar graph entities from
     Neo4j, feed combined result to LLM
2. Implement RCA trigger flow:
   - Trigger from alert or incident
   - Pull affected services, edges, and neighborhood from Neo4j
   - Pull recent raw evidence from OpenSearch for that neighborhood and time
     window
   - Pull semantically similar prior incidents and remediation notes
   - Generate: likely root cause candidates, blast radius, confidence estimate,
     recommended next checks, recommended mitigations
3. Build copilot UI or API.
4. Build evaluation dataset based on historical incidents.
5. Implement governance and audit controls:
   - PII filtering before retrieval into prompts
   - Audit log of prompts, evidence, and model outputs
   - Human-in-the-loop approval before action recommendations become automated
   - Prompt-injection defenses for log content and external text sources

#### Dependencies

- Phases 2-4 complete (evidence vectors, graph, risk scores).
- LLM service available (AWS Bedrock or SageMaker within data boundaries).

#### Acceptance Criteria

- Copilot can reconstruct incident context from graph + telemetry.
- Recommendations are explainable and evidence-backed.
- Evaluation shows measurable MTTR improvement potential.

#### Definition of Done

- RCA retrieval orchestrator deployed.
- Hybrid retrieval API operational.
- Copilot UI or API available.
- Governance and audit controls in place.

#### Validation

- Evaluate against historical incidents.
- Measure recommendation quality and coverage.
- Verify governance controls (audit trail, PII filtering).

#### Rollback

- Disable copilot service.
- No impact on graph, vectors, or core telemetry.

#### Risks + Mitigations

- LLM hallucination: evidence-backed recommendations only, human-in-the-loop.
- Prompt injection: sanitize all log content and external text before including
  in prompts.
- PII leakage: apply redaction pipeline before retrieval into LLM context.
- Model cost: use batch/async processing where possible; constrain prompt sizes.

## 7. Detailed Technical Runbook

### 7.1 EKS Prerequisites

- Namespace strategy:
  - `observability` for collectors
  - `observability-system` for policies and meta-monitoring
- RBAC:
  - Least privilege to read required Kubernetes metadata (pods/namespaces/nodes)
    limited to what k8sattributes needs
- Pod Security Standards:
  - DS requires hostPath for log access; tightly scoped mounts only for
    `/var/log/containers`
  - baseline/restricted for all other pods
- IRSA:
  - Gateway service account bound to role that can reach OSI/OpenSearch as
    needed (prefer OSI endpoint with network restrictions to avoid credentials
    in cluster)
  - Collectors: only to call OSI ingest endpoint (no OpenSearch write)
- Resource governance:
  - Quotas/limits for observability namespaces
- ArgoCD wiring:
  - Application/ApplicationSet with `spec.source.helm` (chart, values, or value
    files per env)
  - Chart provenance and version pinning documented
  - GitHub Actions or PR workflow promotes chart/version changes

### 7.2 Collector Topology and Baseline Configuration

**Agent DaemonSet responsibilities:**

- Container logs tailing (`filelog` receiver with hostPath mounts for
  `/var/log/containers`)
- Node/pod/container metrics (`kubeletstats` receiver)
- Optional Prometheus scrape for annotated services (Kubernetes service
  discovery + relabeling to scrape only annotated targets)
- kube-state-metrics scrape (deploy if not present)
- Forward all to gateway over OTLP

**Gateway responsibilities:**

- k8s enrichment normalization (`k8sattributes` processor)
- Redaction transforms
- Routing to index families
- Tail sampling for traces
- Batching and retries with backpressure
- Single export path to OSI

**Sizing/backpressure:**

- DS: requests sized for log tailing + scraping (start small, measure).
- Gateway: HPA on CPU + queue size; use `memory_limiter` + `batch` processors;
  use bounded sending queues.

**Gateway config snippet (baseline):**

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
    extract:
      metadata:
        - k8s.namespace.name
        - k8s.pod.name
        - k8s.node.name
        - k8s.container.name
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
  otlphttp/osi:
    endpoint: ${OSI_OTLP_ENDPOINT}
    compression: gzip

service:
  pipelines:
    logs:
      receivers: [otlp]
      processors:
        - memory_limiter
        - k8sattributes
        - resource
        - batch
      exporters: [otlphttp/osi]
    metrics:
      receivers: [otlp]
      processors:
        - memory_limiter
        - k8sattributes
        - resource
        - batch
      exporters: [otlphttp/osi]
    traces:
      receivers: [otlp]
      processors:
        - memory_limiter
        - k8sattributes
        - resource
        - tail_sampling
        - batch
      exporters: [otlphttp/osi]
```

**ArgoCD Application snippet (observability platform):**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: observability-platform
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: ${GITOPS_REPO_URL}
    targetRevision: HEAD
    path: gitops/platform/observability/chart
    helm:
      valueFiles:
        - ../values/${ENVIRONMENT}.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: observability
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 7.3 Logs

**Collection:**

- Agent DS uses `filelog` receiver tailing `/var/log/containers/*.log`.
- Parse CRI/container runtime formats and JSON payload when present.

**Standard schema (required minimum):**

- `@timestamp`
- `message`
- `severity_text` or `severity_number`
- `service.name`
- `deployment.environment`
- `k8s.namespace.name`, `k8s.pod.name`, `k8s.container.name`, `k8s.node.name`
- `trace_id`, `span_id` when tracing is enabled
- `http.method`, `http.route`, `http.status_code` (where applicable)

**Multiline:**

- Enable multiline rules for known patterns (Java stack traces, Python
  tracebacks) at filelog receiver to avoid fragmented events.

**Redaction:**

- Enforce removal/masking of:
  - Authorization headers
  - Tokens/secrets
  - Cookies
  - PII fields per policy (account numbers, email addresses)
- Apply redaction in gateway before export (primary) and optionally in OSI
  pipeline (defense-in-depth).
- Enforce "never index" fields at ingestion pipeline too.

**Index strategy:**

- `logs-${env}-${team}-YYYY.MM.DD` (preferred for tenancy)
- If team unknown, route to `logs-${env}-misc-*` and require onboarding to add
  `team` label.

### 7.4 Metrics

**Collection approaches:**

- Infrastructure metrics (always on):
  - kubelet/pod/container metrics (kubeletstats receiver)
  - kube-state-metrics (deploy if not present)
  - Control plane metrics endpoints if accessible
- Application metrics (plug-in):
  - Mode A: Prometheus scrape by annotations (only annotated targets to reduce
    noise and cardinality)
  - Mode B: OTLP metrics from SDKs

**Cardinality controls:**

- Label budget policy:
  - Forbid high-cardinality identifiers (user_id, request_id, session_id) as
    labels
  - Cap label count per metric family (target: max 10 labels)
  - Enforce histogram bucket limits
- Drop/rename attributes in gateway to enforce policy.

**Storage in OpenSearch:**

- Metrics stored as documents aligned with SS4O/SSFO schema.
- Use strict mappings for numeric fields and standardized field names.
- Disable uncontrolled dynamic mappings.
- Downsampling:
  - Hot: 1-minute granularity for 7d
  - Downsampled: 5/15-minute resolution for 30d/90d
- ISM enforces rollover and retention.

**OSI pipeline snippet (metrics):**

```yaml
otel-metrics-pipeline:
  source:
    otel_metrics_source:
      health_check_service: true
  processor:
    - otel_metrics:
        calculate_histogram_buckets: true
  sink:
    - opensearch:
        index: ss4o_metrics-%{yyyy.MM.dd}
```

### 7.5 Traces

**Instrumentation plan:**

- Start with auto-instrumentation where stable (Java, .NET, Node.js) and manual
  spans for critical business transactions.
- Standard propagation: W3C tracecontext.
- Ensure ingress/gateway layers propagate headers.
- Enforce resource attributes: `service.name`, `service.version`,
  `deployment.environment`.
- Export: OTLP to gateway (cluster-local service).

**Sampling:**

- Tail sampling at gateway:
  - Always keep errors
  - Keep slow spans above threshold
  - Baseline probabilistic sampling for normal traffic
- Policy differs by service tier:
  - Tier-0 services get higher sampling budgets

**Storage:**

- Trace Analytics pipelines in Data Prepper/OpenSearch create indices for
  service-map and trace group analytics.
- Span documents with standardized fields: trace_id, span_id, parent_span_id,
  service.name, duration, status, attributes.
- Retention shorter than logs by default (14d).

### 7.6 OSI and OpenSearch Configuration

**OSI pipeline design:**

- Single OTLP ingest endpoint per environment.
- Keep OSI transforms minimal; do enrichment and policy enforcement in gateway
  to reduce OSI coupling.
- Use separate sinks or routed indices for logs/metrics/traces.
- Monitor OSI pipelines using CloudWatch metrics and alarms.

**OpenSearch index templates:**

- Enforce strict mappings for:
  - Timestamps
  - Numeric fields (duration, sizes)
  - Keyword vs text for high-cardinality fields
- Disable uncontrolled dynamic mappings where practical to prevent mapping
  explosions.

**ISM policies:**

- Logs:
  - Rollover by size and/or daily
  - Retention 30d default
- Metrics:
  - Rollover daily
  - Downsample after 7d
  - Retention 30d+ as required
- Traces:
  - Rollover daily
  - Retention 14d default
- Snapshots:
  - Scheduled snapshots to S3
  - Restore drill runbook

### 7.7 Visualization

**Default:**

- OpenSearch Dashboards for logs/metrics/traces:
  - Service overview dashboards (golden signals)
  - Trace Analytics views (service map, trace correlation)
  - Platform health dashboards
  - Log search with trace pivot

**Optional:**

- Grafana as a UI on OpenSearch only if mandated (does not violate
  "OpenSearch-only storage"). Use it as a query UI only, with OpenSearch as the
  data source.

**Dashboard taxonomy:**

- `platform/cluster/*`
- `platform/collectors/*`
- `services/<team>/<service>/*`
- `security/audit/*`

**Dashboard conventions:**

- Golden signals per service: latency, traffic, errors, saturation.
- "Service overview" pages link to: logs (filtered by service.name), traces
  (trace groups), metrics (p95 latency, error rate, CPU/mem).

### 7.8 Alerting and On-Call

**Alert philosophy:**

- SLO-based (burn-rate) where possible.
- Symptom-based alerts kept minimal:
  - High error rate spikes
  - Latency spikes
  - Crash loops and restart storms
  - Ingestion lag and dropped telemetry

**Noise controls:**

- Multi-window confirmation
- Dedup by service/team
- Maintenance windows
- Runbook link in every alert

**Routing:**

- Route by `team` label and service catalog mapping.
- Map services to owning team via service catalog metadata.

### 7.9 SLO Program (5 Example SLIs Measured from OpenSearch)

- **SLI 1: Availability**
  - Source: trace spans or access logs
  - Measure: successful requests / total requests (filter by service.name and
    status)
- **SLI 2: Latency p95**
  - Source: trace spans
  - Measure: p95 of span duration for server spans per service/route
- **SLI 3: Error rate**
  - Source: spans with ERROR status or logs with 5xx severity mapping
  - Measure: error requests / total requests
- **SLI 4: Saturation**
  - Source: pod/container CPU throttling or memory pressure metrics stored in
    OpenSearch
  - Measure: throttle ratio and memory utilization thresholds
- **SLI 5: Dependency health**
  - Source: traces (downstream spans) plus logs
  - Measure: downstream error rate and latency for critical dependencies

**Error budgets:**

- Define per service tier.
- Tie burn-rate alert thresholds to paging policy (fast burn pages, slow burn
  tickets).

### 7.10 Security Hardening

- Encryption:
  - TLS in transit everywhere
  - KMS at rest for OpenSearch and snapshots
- IAM:
  - Least privilege for OSI to write to OpenSearch
  - Collectors: only to call OSI ingest endpoint (no OpenSearch write)
  - Least privilege roles for platform operators and team viewers
  - Platform operators: index templates, ISM, Dashboards admin scoped to env
- Network:
  - VPC-only OpenSearch access
  - Private routing from cluster to OSI/OpenSearch
  - Network policies in cluster to restrict egress from collectors to only
    required endpoints
  - OSI VPC access configuration for pipelines
- Tenant isolation:
  - Index patterns per team
  - Dashboards tenant/space isolation
  - Fine-grained access control in OpenSearch: roles per team mapped to index
    patterns
  - Audit logs and access review cadence
- Data classification and "never index":
  - Explicit denylist of fields and patterns (tokens, secrets, credentials)
  - Automated redaction tests

### 7.11 DR and Backups

- Snapshots:
  - Scheduled snapshots to S3 via ISM policies
- Restore drill:
  - Quarterly restore into test domain/collection
  - Validate: indices, mappings, dashboards, and representative queries
- RTO/RPO assumptions:
  - Define per environment and document (defaults until finalized)
- Failure modes:
  - OSI ingestion failure: collector backpressure + bounded loss policy
  - OpenSearch incident: snapshot restore and/or cross-AZ resilience

### 7.12 Meta-Monitoring (Monitor the Observability System)

- Collector health dashboards:
  - Queue depth, exporter errors, dropped telemetry counts
  - OpenTelemetry Collector internal metrics and logs
- OSI pipeline health:
  - Ingestion errors, latency, throughput alarms
  - CloudWatch metrics for pipeline lag and errors
- OpenSearch health:
  - Cluster status, JVM pressure, indexing latency, shard health
- Index growth and cost signals:
  - Daily index size deltas per signal and team

### 7.13 Neo4j Technical Details (Phase 3+)

**Deployment:**

- Preferred: Neo4j AuraDB (managed) for low operational overhead.
- Alternative: self-managed on EKS via official Neo4j Helm chart + ArgoCD
  Application.
- Aura Graph Analytics for GDS workloads (on-demand managed compute for graph
  data science).

**Graph ETL design:**

- Source: OpenSearch indices (traces primary, supplemented by logs and metrics
  aggregates).
- Primary derivation from traces using OpenTelemetry `servicegraph` connector semantics
  (service-to-service edges, request/error/ duration attributes).
- Idempotent job design with retry and dead-letter handling.
- Near-real-time stream for topology and incident edges.
- Scheduled batch for enrichment, drift detection, and graph snapshots.

**Vector indexes in Neo4j:**

- Store embeddings on `Service`, `Incident`, `Deployment`, `Runbook`, `Endpoint`
  nodes.
- Used by GraphRAG retrieval in Phase 5.

### 7.14 Vector Strategy (Phase 2+)

**OpenSearch evidence vector corpus:**

Embeddings for observability evidence documents:

- Incident summaries
- Grouped/clustered error logs
- Trace-group summaries
- Deployment summaries
- Alert context documents
- Remediation notes
- Runbook chunks
- Service time-window summaries

**Neo4j graph/entity vector corpus:**

Embeddings for graph-native objects:

- Service nodes
- Endpoint nodes
- Incident nodes
- Deployment nodes
- Runbook nodes
- Graph neighborhood summaries
- Learned node embeddings from graph ML

**Hybrid retrieval architecture (Phase 5):**

- Path A: OpenSearch evidence retrieval (semantic similarity + filtered search)
- Path B: Neo4j graph retrieval (traversal + graph vector similarity)
- Path C: Fusion layer (graph neighborhood constrains OpenSearch retrieval,
  results combined for LLM context)

## 8. CI/CD, IaC, GitOps

### Repository Structure

```text
observability-kit/
  infra/terraform/
    main.tf
    variables.tf
    outputs.tf
    envs/{dev,stage,prod}/
    modules/
      attach/
      standalone/
      argocd_bootstrap/
      osi/
      opensearch/
      ism_templates/
      iam_irsa/
  gitops/
    bootstrap/
      app-of-apps.yaml
    platform/observability/
      chart/
      values/{dev,stage,prod}.yaml
    platform/dashboards/
      saved-objects/
    platform/alerts/
      definitions/
    libraries/helm/observability-lib/
  .github/workflows/
    plan.yml
    apply.yml
    validate.yml
  Makefile
```

### Terraform Modules

- `attach`: IRSA, Kubernetes bootstrap, ArgoCD Applications
- `standalone`: OpenSearch, OSI, KMS, ISM, networking bindings, and everything
  in attach
- `argocd_bootstrap`: Application/ApplicationSet definitions and repo
  integration
- `ism_templates`: index templates, ISM policies, snapshot policies
- `iam_irsa`: gateway service account role

Terraform uses `cluster_name` to discover endpoint/OIDC/VPC context. Outputs
become GitOps inputs (endpoints, index prefixes, tenancy identifiers) via
CI-generated values files.

### ArgoCD Scope

- Register one Application per logical component (or use ApplicationSet for
  multi-cluster/env).
- Each Application with `spec.source.helm` (chart + values or value files).
- Document chart provenance, version pinning, and how GitHub Actions or PR
  workflow promotes chart/version changes.
- Separate Applications for: platform chart, dashboards saved objects, alert
  definitions.

### GitHub Actions Workflows

- `plan.yml` (PR):
  - fmt/validate
  - plan
  - policy checks (no hard-coded values, no secrets in repo)
  - Helm template lint
- `apply.yml` (merge):
  - Apply Terraform
  - Render env overlay values from non-sensitive outputs (endpoints, prefixes)
  - Commit overlay changes to GitOps path
  - ArgoCD auto-sync deploys updated configs
- `validate.yml` (post-deploy):
  - Deploy telemetry generator
  - Assert logs/metrics/traces present in OpenSearch
  - Cleanup

### Testing Strategy

- Config validation:
  - Helm template lint
  - OpenTelemetry config schema validation
  - Policy-as-code checks (OPA/Gatekeeper/Kyverno)
- Smoke tests:
  - Telemetry generator
- Load tests:
  - Synthetic load for ingest volume and index performance
- Security tests:
  - Redaction test corpus
  - RBAC/tenant isolation verification

### Ownership Model

- Platform/SRE:
  - Collectors, configs, routing, schema, dashboards, alerts
  - OpenSearch/OSI capacity, retention, lifecycle policies
  - Onboarding templates and enforcement policies
  - Neo4j deployment and graph ETL (Phase 3+)
- Service teams:
  - Trace instrumentation quality and adoption
  - Metrics label discipline
  - Log structure compliance

## 9. Backlog Breakdown (Epics to Stories/Tasks)

### Phase 1: Core Observability

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E0 Productize kit | Install Contract, module skeleton, repo layout, docs | Install on 2 clusters with only contract inputs |
| E1 AWS attach path | Variables for endpoints, overlay rendering, CI wiring | No hard-coded endpoints; attach deploy succeeds |
| E2 Standalone path | OpenSearch + OSI modules, KMS, policies | Standalone deploy passes smoke tests |
| E3 Collector platform | DS + gateway chart, RBAC, PSS, NP, PDB | Collectors healthy; export stable under restart |
| E4 Logs | File tailing, parsing, schema, multiline, redaction | Cluster logs visible with required fields; PII tests pass |
| E5 Metrics | Infra metrics + scrape opt-in + cardinality guards | Node/pod metrics complete; app scrape works |
| E6 Traces | Gateway OTLP, sampling policy, app plug-in lib | Telemetry generator traces visible; pivot works |
| E7 OpenSearch configs | Templates, ISM, retention, snapshots | Rollover/retention verified; snapshot created |
| E8 Dashboards-as-code | Baseline dashboards + saved objects pipeline | Dashboards deployed by ArgoCD; versioned |
| E9 Alerting + SLO | Burn-rate alerts + symptom alerts + routing | Alert noise targets met; runbooks linked |
| E10 Meta-monitoring | Collector/OSI/OpenSearch health alerts | Lag and drops detected with actionable alerts |
| E11 DR drills | Restore runbook + quarterly drill automation | Successful restore drill evidence recorded |
| E12 Onboarding lib | Helm library chart + onboarding templates | One-block onboarding works for 3+ services |

### Phase 2: Vectorization and AI Foundations

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E13 Correlation enforcement | Required fields validation, schema normalization | Required fields enforced across all telemetry |
| E14 Service catalog | Service-to-team/on-call/tier mapping | Catalog in place and queryable |
| E15 Embedding pipeline | Extraction jobs, embedding model, vector indices | Evidence vectors stored; semantic search works |
| E16 Semantic retrieval | Retrieval service, similarity API | Similar incidents retrievable with quality metrics |
| E17 Anomaly detection | OpenSearch detectors for key signals | Detectors running; evaluation report complete |
| E18 AI governance | PII controls, data classification, audit | Governance controls in place before LLM access |

### Phase 3: Core Graph Stack

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E19 Neo4j deployment | AuraDB setup or EKS Helm deployment | Neo4j operational and monitored |
| E20 Graph schema | Node/relationship types, naming standards | Schema documented and versioned |
| E21 Graph ETL | Trace-derived topology, batch enrichment | Service dependency graph populated from traces |
| E22 Incident graph | Incident/alert/change nodes and edges | Blast radius computable from graph |
| E23 Ownership graph | Team/service/SLO relationships | Ownership queryable for alert routing |
| E24 Graph monitoring | Freshness SLAs, ETL health checks | Graph freshness meets SLA |
| E25 Graph vectors | Vector indexes on graph entities | GraphRAG retrieval works |

### Phase 4: Graph ML Risk Scoring

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E26 Feature engineering | Graph features per node/edge | Features derived and versioned |
| E27 Graph algorithms | Centrality, community, path analysis | Algorithm results available |
| E28 Risk scoring model | Scoring service, composite risk metric | Scores explainable; backtest shows value |
| E29 Risk dashboards | Operational risk views, pre-deploy queries | Risk integrated into workflows |
| E30 Scoring validation | Offline evaluation, incident backtesting | Predictive value demonstrated |

### Phase 5: LLM-Based RCA

| Epic | Stories / Tasks | Acceptance Criteria |
| ---- | ---- | ---- |
| E31 Retrieval orchestrator | Hybrid retrieval API (OpenSearch + Neo4j) | Retrieval quality metrics met |
| E32 RCA trigger flow | Alert-to-RCA pipeline, context assembly | Incident context reconstructed automatically |
| E33 Copilot UI/API | User-facing RCA interface | Recommendations evidence-backed |
| E34 Evaluation | Historical incident dataset, MTTR measurement | Measurable MTTR improvement potential |
| E35 Governance | Audit logging, PII filtering, prompt defenses | Full audit trail; prompt injection mitigated |

## 10. Risk Register

| Risk | Impact | Likelihood | Mitigation | Owner |
| ---- | ---- | ---- | ---- | ---- |
| Metrics cardinality overwhelms OpenSearch | High | High | Label budgets, drop rules, downsampling, shorter retention | Observability lead |
| SS4O/SSFO schema maturity gaps | Medium-High | Medium | Phase schema adoption; strict mappings; controlled upgrades | Platform team |
| OSI plugin subset limits needed transforms | Medium | Medium | Move transforms to OpenTelemetry processors; keep OSI pipelines minimal | Platform team |
| Traces volume and cost | High | Medium | Tail sampling defaults, tiered sampling by service tier | SRE lead |
| Log mapping explosion (dynamic fields) | High | Medium | Strict mappings, schema contract, field allowlist | Platform team |
| PII/secret leakage into telemetry | High | Medium | Redaction processor, tests, access controls | Security |
| OpenSearch query performance degrades | High | Medium | Shard strategy, bulk sizing, refresh tuning | Platform team |
| OSI throttling/ingest lag | Medium | Medium | Backpressure settings, HPA, alarms, capacity planning | Platform team |
| Multi-account connectivity delays | Medium | Medium | Standard TGW/PrivateLink patterns, staged onboarding | Network team |
| Hard-coded values drift into templates | Medium | Medium | CI checks for prohibited patterns; mandatory overlays | DevOps lead |
| Over-alerting increases on-call load | Medium | Medium | Burn-rate alerts, dedup, routing, runbooks | SRE manager |
| DR not practiced | High | Medium | Quarterly restore drills with evidence | Platform lead |
| Neo4j graph staleness | Medium | Medium | Freshness monitoring, alerting, idempotent ETL | Platform team |
| Graph ETL failures lose topology accuracy | Medium | Medium | Idempotent jobs, dead-letter handling, reconciliation | Platform team |
| Embedding quality insufficient for retrieval | Medium | Medium | Start with well-scoped domains; iterative quality evaluation | AI/ML team |
| PII leakage into LLM prompts | High | Medium | Redaction pipeline before retrieval into LLM context | Security |
| LLM hallucination in RCA recommendations | High | Medium | Evidence-backed only; human-in-the-loop; audit logging | AI/ML team |
| Prompt injection via log content | High | Low | Sanitize log content before prompt inclusion; input validation | Security |
| Model cost escalation | Medium | Medium | Batch processing; constrain prompt sizes; usage monitoring | Platform lead |

## 11. Cost &amp; Capacity Notes

### Main Drivers

- Log ingest GB/day (largest contributor in most systems).
- Metrics cardinality (unique time series), driving document volume and index
  size.
- Trace span volume and retention.
- Index shard count and segment churn (affects CPU/IO).
- OSI pipeline throughput requirements.
- OpenSearch hot storage footprint.
- Neo4j node/relationship count and query volume (Phase 3+).
- Embedding generation compute (Phase 2+).
- LLM API usage (Phase 5).

### Control Levers

- Logs:
  - Retention by index pattern/team
  - Drop noisy namespaces
  - Enforce structured logs to reduce parsing overhead
- Metrics:
  - Strict label budgets
  - Downsampling after short hot window
  - Drop high-cardinality labels at gateway
- Traces:
  - Tail sampling with error/slow priority
  - Shorten trace retention vs logs
  - Store only high-value traces (errors/slow)
- OpenSearch:
  - Rollover sizing and shard strategy tuned per signal
  - Tiering (hot/warm/cold) if available/needed
  - Tune bulk sizes and indexing performance
- Operational controls:
  - Daily index growth dashboards by team
  - Per-team budgets and chargeback/showback readiness
- AI/Graph:
  - Vectorize curated objects only, not raw exhaust
  - Batch embedding generation, not real-time
  - Graph ETL batch windows sized to balance freshness and cost
  - LLM usage metering and budget alerts

## 12. Go-Live Checklist

### Phase 1 Go-Live

- [ ] Install Contract documented and validated on 2 distinct existing EKS
  clusters.
- [ ] Terraform `attach` deploy works from laptop and GitHub Actions with
  identical results.
- [ ] ArgoCD bootstrap is fully automated (no manual sync steps required beyond
  standard ArgoCD operation).
- [ ] Logs:
  - [ ] Cluster-wide container logs ingested
  - [ ] Required schema fields present
  - [ ] Redaction verified via test corpus
- [ ] Metrics:
  - [ ] Infra metrics complete
  - [ ] Scrape opt-in works via a single values block
  - [ ] Cardinality guards verified
- [ ] Traces:
  - [ ] Telemetry generator traces visible
  - [ ] At least one real service per language family instrumented
  - [ ] Tail sampling policy validated
- [ ] OpenSearch:
  - [ ] Index templates and ISM policies applied and verified
  - [ ] Retention and rollover observed in test
  - [ ] Snapshots configured and first snapshot created
- [ ] Tenancy:
  - [ ] Team role cannot query other team indices
  - [ ] Dashboards tenants/spaces configured
- [ ] Meta-monitoring:
  - [ ] Collector drops and exporter errors alerting
  - [ ] OSI ingest lag alerting
  - [ ] OpenSearch health alerting
- [ ] DR:
  - [ ] Restore drill completed in non-prod and evidence recorded
- [ ] Rollback:
  - [ ] Gateway export disable tested
  - [ ] ArgoCD revert to previous release tag tested
- [ ] Operational handover:
  - [ ] Runbooks published
  - [ ] On-call routing and escalation tested
- [ ] Security:
  - [ ] Architecture ADRs approved
  - [ ] Security review complete: threat model, PII policy, least privilege IAM,
    VPC-only access, audit logging
  - [ ] Compliance evidence pack prepared

### Phase 2 Go-Live

- [ ] Required correlation fields enforced across all telemetry.
- [ ] Service catalog operational with team/tier mappings.
- [ ] Embedding generation jobs operational and monitored.
- [ ] OpenSearch vector indices created and populated.
- [ ] Semantic retrieval service deployed and tested.
- [ ] Anomaly detectors running with evaluation report.
- [ ] Data classification and PII controls verified.

### Phase 3 Go-Live

- [ ] Neo4j deployed and operational.
- [ ] Graph schema documented and versioned.
- [ ] Graph ETL pipelines running and monitored.
- [ ] Service dependency graph populated and verified.
- [ ] Incident and change graphs populated.
- [ ] Ownership graph populated.
- [ ] Graph freshness SLAs defined and monitored.
- [ ] Vector indexes on graph entities operational.

### Phase 4 Go-Live

- [ ] Graph feature engineering jobs operational.
- [ ] Risk scoring model deployed and evaluated.
- [ ] Backtesting shows predictive value.
- [ ] Risk dashboards available.
- [ ] Pre-deployment impact queries integrated.

### Phase 5 Go-Live

- [ ] Hybrid retrieval orchestrator deployed and tested.
- [ ] Copilot UI or API available.
- [ ] Governance controls in place:
  - [ ] PII filtering verified
  - [ ] Audit logging operational
  - [ ] Human-in-the-loop approval flow tested
  - [ ] Prompt injection defenses tested
- [ ] Evaluation shows measurable MTTR improvement potential.

## 13. Deliverables (Concrete Artifacts)

### Architecture and Decisions

- Reference architecture diagram (text spec + diagram source)
- ADRs:
  - Attach vs standalone
  - Tenancy model
  - Index strategy and retention
  - Sampling strategy
  - Neo4j deployment model (AuraDB vs self-managed)
  - Vector strategy (OpenSearch evidence vs Neo4j graph)
  - AI governance model

### Infrastructure as Code

- Terraform modules:
  - `attach` module
  - `standalone` module
  - `argocd_bootstrap` module
  - `ism_templates` module
  - `iam_irsa` module

### GitOps Packages

- ArgoCD app-of-apps bootstrap
- Helm chart `observability-platform`
- Helm library chart `observability-lib`
- Dashboards saved objects package
- Alerts-as-code package

### OpenSearch Configuration

- Index templates/mappings (logs, metrics, traces, vectors)
- ISM policies
- Snapshot policy configuration

### Neo4j Configuration (Phase 3+)

- Graph schema documentation
- Graph ETL pipeline definitions
- Vector index configurations
- Graph freshness monitoring

### Dashboards and Alerts

- Dashboards-as-code packages
- Alerts-as-code definitions

### AI/ML Artifacts (Phase 2+)

- Embedding generation job definitions
- Semantic retrieval service
- Risk scoring model and service (Phase 4+)
- RCA retrieval orchestrator (Phase 5)
- Copilot UI/API (Phase 5)

### Runbooks and Operational Docs

- Install/upgrade/rollback
- Triage playbooks for ingestion, OpenSearch health, collector drops
- DR restore drill runbook
- Capacity and cost control notes
- Graph ETL troubleshooting (Phase 3+)
- AI/ML operational procedures (Phase 2+)

### Security Evidence Pack

- IAM policies
- Encryption settings
- Access review procedure
- Redaction test results
- AI governance documentation (Phase 5)
