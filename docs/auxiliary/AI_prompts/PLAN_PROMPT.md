# OBSERVABILITY PROJECT PLAN

## ROLE

You are a Staff SRE / Observability Architect and DevOps delivery lead with deep
AWS + EKS experience. You design pragmatic, low-ops solutions, produce execution-ready
plans, and think in phases (design → build → validate → rollout → operate).

## CONTEXT

We are implementing an Observability platform on AWS with most resources deployed
on EKS. Base platform pieces (VPC, EKS including Auto Mode where applicable, ECR,
Secrets Manager, endpoints, etc.) may already exist; the plan should assume
attach/extend patterns where that reduces rework.

The ultimate project goal is a portable observability intelligence platform for
existing EKS clusters, using OpenTelemetry-only collection and OSI to
OpenSearch as the single telemetry path, with Neo4j as a derived graph tier
and a phased path to
optional LLM-assisted RCA.

The **ArgoCD EKS Capability is already deployed and operational**. Do **not** scope
installation, bootstrap, or upgrade of ArgoCD itself unless explicitly asked.
New work registers **ArgoCD `Application` resources** (or `ApplicationSet` patterns
where appropriate) so each deployable observability component is a normal Application
in the cluster.

### HARD CONSTRAINTS

- OpenTelemetry must be the SOLE collector for logs, metrics, and traces
  (no parallel collectors/agents such as a separate Fluent Bit/Datadog agent for
  the same signals).
- Amazon OpenSearch Service is the single store for logs, metrics, traces, and
  observability-oriented vector indices (k-NN / Vector Engine) for semantic search,
  RAG, and similar workloads.
- Ingestion should target the managed path **OpenTelemetry Collectors → Amazon
  OpenSearch Ingestion (OSI)** (Data Prepper-compatible pipelines) **→ OpenSearch**,
  with schema alignment to **Simple Schema for Observability / SS4O and SSFO** where
  applicable. Call out **OSI’s supported plugin subset** and mitigate gaps
  (e.g. push transforms to the Collector) rather than inventing unsupported pipeline
  steps.
- **Neo4j** holds the **property-graph** view of services, dependencies, and topology
  (and optional graph-aligned embeddings for graph-RAG). It complements OpenSearch:
  correlation across logs/metrics/traces still relies on **shared IDs and resource
  attributes** (e.g. `trace_id`, `span_id`, `service.name`); the graph DB is for
  multi-hop analytics, risk scoring, and advanced topology workloads - not a substitute
  for storing raw telemetry. If both stores carry vectors, the plan must justify
  roles and avoid redundant pipelines.
- Use the most appropriate visualization tools for each signal while keeping
  operational overhead low (default: **OpenSearch Dashboards** with Observability
  and Trace Analytics; **Grafana** only when clearly justified as a UI on top of
  OpenSearch).
- We want to later add ML and AI capabilities to correlate signals, predict issues,
  and accelerate RCA, with a **practical ordering**: deterministic graph construction
  and **risk/topology scoring** before heavy **LLM-assisted RCA** on top of that
  substrate.
- **In-cluster delivery via Helm + ArgoCD**: Anything that should run on EKS under
  GitOps (OpenTelemetry Collectors, optional in-cluster agents or sync
  workers, policy bundles,
  Neo4j or other stateful workloads if hosted on-cluster, etc.) is deployed by an
  ArgoCD Application whose **source is a Helm chart** (vendor chart, wrapped chart,
  or first-party chart in Git). Prefer this over one-off `kubectl apply` or unmanaged
  imperative flows unless a component is inherently non-Helm and you document why.

Assume standard enterprise needs: multi-env (dev/stage/prod), security reviews,
IaC, CI/CD, on-call, runbooks, and compliance-ready controls.

### PROJECT INPUTS

> Fill if known; otherwise treat as TBD and make explicit assumptions.
> Make suggestions where possible.

- OpenSearch deployment model: [Managed Amazon OpenSearch Service domain OR OpenSearch
  Serverless OR Self-managed on EKS]  <<<<< IMPORTANT (default assumption in reference
  plan: **managed domain + OSI**)
- AWS account model: AWS Organizations (consider a central observability platform
  account plus workload accounts; private connectivity e.g. TGW/PrivateLink for
  cross-account ingest)
- Regions: us-east-1, us-east-2
- EKS clusters (count, versions, nodegroups/Fargate/Auto Mode, add-ons): 1, 1.35,
  unsure, unsure
- Workloads (#services, critical services, languages): TBD
- Compliance/security (SOC2/PCI/HIPAA/GDPR, data residency): Yes
- Existing tooling (Grafana, CloudWatch, etc.): None
- CI/CD (GitHub/GitLab, ArgoCD/Flux/Jenkins): GitHub Actions (Terraform plan/apply,
  gates); **ArgoCD already deployed** - add **Application(s)** + **Helm** for
  EKS workloads
- IaC (Terraform/CDK/CloudFormation): Terraform
- Secrets (AWS Secrets Manager / External Secrets / Vault): AWS Secrets Manager,
  GitHub Repo Secrets
- Retention requirements (logs/metrics/traces): All
- Budget constraints: None
- Incident tooling (PagerDuty/Opsgenie/none): Unsure

## TASKS

Produce a detailed, step-by-step technical plan to implement end-to-end observability
for AWS + EKS using:

- OpenTelemetry collection everywhere (metrics/logs/traces) and standardized context
  propagation/correlation IDs.
- **OpenTelemetry → OSI → OpenSearch** as the single write path for telemetry,
  with OpenSearch
  also hosting **vector indices** for AI/RAG; index design, ISM, and cardinality
  controls called out explicitly.
- **Neo4j** for the **operational dependency / topology graph** (synced or derived
  from traces and metadata), plus any **graph-native ML or graph-RAG** vectors the
  architecture requires - without duplicating the "system of record" for raw logs,
  metrics, or spans.
- A clear **workload "plug-in" contract**: JSON logs to stdout, Prometheus scrape
  annotations and/or OTLP metrics, OTLP traces with W3C propagation - so any future
  EKS deployment can onboard uniformly.
- Appropriate visualization per signal (and explain the tool choices + trade-offs).
- A future roadmap for AI: **anomaly detection / graph risk scoring foundations
  first**,
  then **LLM-assisted RCA and copilots** with governance, aligned with
  OpenSearch ML features and optional AWS AI services (e.g. Bedrock) within data
  boundaries.

## BEFORE WRITING

1. Ask up to 5 clarification questions ONLY if they materially change the
  architecture/execution plan.
2. If anything is TBD or "unsure", list explicit assumptions and proceed
  (do NOT stop).
3. Make suggestions where possible.

## NON-NEGOTIABLES

- Provide real-world software delivery mechanics: General Project Plan, PRD
  (In the form of Product Requirements), Technical Requirements, Tasks broken into
  epics/stories, acceptance criteria, Definition of Done, CI/CD, IaC, rollout,
  validation, rollback, change management, security review, and operational handover.
- Do not hand-wave. Every phase must have concrete steps and "how to validate".
- If any part of the "OpenTelemetry-only + OpenSearch (+ OSI) + Neo4j"
  constraint is technically
  risky or has gaps (e.g. **SS4O/SSFO** maturity, **OSI plugin limits**, metrics
  cardinality in OpenSearch), call it out explicitly and provide mitigations that
  still respect the constraint (or a staged plan).

## REQUIRED SCOPE (must include all sections)

A) Discovery &amp; Requirements

- Stakeholders, goals, non-goals, success criteria
- Current state checklist (clusters, networking, IAM, telemetry maturity)
- Observability requirements: SLIs/SLOs, alerting philosophy, retention, sampling,
  privacy/PII redaction
- Threat model + data classification (what must never be indexed)

B) Architecture &amp; Design (within constraints)

- End-to-end reference architecture: logs/metrics/traces via
  **OpenTelemetry (DaemonSet +
  Gateway recommended)** → **OSI** → **OpenSearch**; **Neo4j** fed by **deterministic**
  sync/ETL from traces, service catalog, or curated events (not as the primary
  OTLP sink).
- Ingestion pipeline design (buffering/queueing, transformation, enrichment, routing);
  note **collectors must not require OpenSearch write credentials** when using
  OSI - **IRSA** scoped to ingest endpoint only.
- Explicitly address:
  - How metrics will be represented/stored in OpenSearch (index strategy, mappings,
    rollups/downsampling, cardinality controls)
  - How traces will be ingested/stored (service map needs, trace/span indexes, retention)
  - How logs will be standardized (JSON schema, trace_id/span_id correlation,
    multiline rules, redaction)
  - Multi-cluster / multi-account ingestion patterns and tenancy isolation
    (e.g. per-env domains/collections, index prefixes, FGAC)
  - Network and security (VPC-only OpenSearch, OSI VPC access, private egress,
    encryption in transit/at rest, KMS)
- Provide **2–3 viable architecture variations** that respect the constraints, e.g.:
  - **V1:** Managed OpenSearch domain + **OSI** + Dashboards
  - **V2:** OpenSearch Serverless collection + **OSI**
  - **V3:** Self-managed **Data Prepper** on EKS + self-managed OpenSearch on EKS
  In each case telemetry lands in OpenSearch; Neo4j is an **adjacent** graph tier
  with a defined sync model. Choose one with rationale and a decision matrix.
- Decision matrix (effort, cost, lock-in, scalability, security/compliance,
  ops overhead)

C) Implementation Plan (real-world delivery lifecycle)

- Phased roadmap: PoC → pilot → production rollout → scale hardening → optimization
- Each phase must include:
  - Goals
  - Exact tasks (step-by-step)
  - Dependencies/prereqs
  - Acceptance criteria
  - Definition of Done
  - Validation steps (how to prove telemetry correctness, completeness, performance)
  - Rollback plan
  - Risks + mitigations

D) Detailed Technical Steps (AWS + EKS)

- EKS prerequisites: IAM/OIDC/IRSA, RBAC, namespaces, Pod Security Standards,
  resource quotas; **ArgoCD Capability present** - prerequisites focus on
  **Application** + **Helm release** wiring (repo URLs, chart versions, value
  overlays per env), not installing ArgoCD
- OpenTelemetry Collector deployment patterns:
  - DaemonSet vs Gateway vs **mixed (reference default)**: node-level collection,
    gateway for tail sampling/redaction/single egress to **OSI**
  - Sizing, autoscaling, backpressure, retry/buffering
  - Processors (k8sattributes, resource, batch, memory limiter, tail sampling where
    applicable)
  - Exporters: **OTLP/HTTP(S) to OSI** as the controlled egress pattern; document
    failure modes (OSI throttling, OpenSearch backpressure)
- Metrics:
  - Collection approach (Prometheus receiver / OTLP metrics)
  - Scrape/service discovery strategy
  - kube-state-metrics / node metrics
  - Custom app metrics standards (naming, labels, cardinality budget)
  - Export via **OSI** into OpenSearch (SS4O/SSFO-oriented index templates/mappings,
    downsampling/rollups, ISM)
- Logs:
  - Collection of container logs via OpenTelemetry (**filelog** receiver, CRI parsing);
    cluster-wide coverage without per-app agents
  - JSON schema and required fields (service.name, environment, trace_id, span_id,
    severity, message, k8s metadata)
  - Multiline handling, sensitive data redaction, routing by index
- Traces:
  - Instrumentation plan by language (auto/manual)
  - Propagation standard (W3C tracecontext), correlation with logs
  - Sampling strategy (head vs tail), and how it impacts storage/AI
- Visualization:
  - Recommend tools given OpenSearch storage (**OpenSearch Dashboards**
    Observability + Trace Analytics as default; **Amazon Managed Grafana** or
    self-managed Grafana only if justified as query UI on OpenSearch)
  - Explain trade-offs and minimal-overhead path
  - Dashboard structure, naming conventions, golden signals, service overview pages
- **Neo4j operational slice** (if in scope): sync cadence, idempotency, graph schema
  (services, endpoints, dependencies), and how it stays consistent with trace-derived
  topology; separate from Dashboards UX.
- Alerting &amp; On-call:
  - Alert rules (SLO-based + symptom-based)
  - Routing/paging policies, noise reduction, runbooks
- SLO Program:
  - Define at least 5 example SLIs (availability, latency, error rate, saturation,
    dependency health)
  - How each SLI is measured from OpenSearch-stored telemetry
  - Error budgets and alert ties
- Security hardening:
  - Encryption, KMS, IAM least privilege, audit logging, secret handling
  - Tenant isolation strategy (indices, roles, spaces)
- DR/Backups:
  - Backups/snapshots, restore drills, RTO/RPO assumptions
- Meta-monitoring:
  - Collector health, dropped telemetry, queue depth
  - **OSI** pipeline metrics (e.g. CloudWatch) for lag and errors
  - OpenSearch cluster health, JVM pressure, indexing latency, index growth

E) CI/CD, IaC, GitOps

- Repo structure proposal (e.g. `infra/terraform` for AWS; Git repo(s) holding **Helm
  charts**, **ArgoCD Application** manifests or ApplicationSets, and optional
  **Helmfile** or similar if the org uses it)
- **Terraform** for AWS: OpenSearch domain/collection, **OSI pipelines**, IAM, KMS,
  networking, snapshot configuration. **Kubernetes-deliverable** observability
  components default to **ArgoCD `Application`** resources with **Helm** sources,
  not Terraform `kubernetes_*` or `helm_release` resources, unless a written platform
  standard explicitly requires otherwise.
- **ArgoCD**: Register one Application per logical component (or use ApplicationSet
  for multi-cluster/env), each with `spec.source.helm` (chart + `values` or value
  files).
  Document chart provenance, version pinning, and how GitHub Actions or PR workflow
  promotes chart/version changes.
- **GitHub Actions**: Terraform plan/apply with environment gates; PR checks on
  Helm chart lint/tests where applicable; promotion of chart and Application changes.
- Onboarding templates for workload teams (**plug-in** contract) aligned with how
  ArgoCD consumes Helm (e.g. library subcharts, standard values schema).
- Testing: config validation, policy-as-code (OPA/Gatekeeper/Kyverno), smoke tests,
  load tests

F) AI Roadmap (phase-based, practical)

- Phase 1: **Correlation foundations** (mandatory fields, trace/log linking, service
  catalog, ownership metadata); **vector index design** in OpenSearch for incidents,
  log patterns, or span summaries as needed
- Phase 2: **Topology graph in Neo4j** (from traces/metadata), **deterministic risk
  scoring** (centrality, blast radius, error/latency-weighted edges), and **anomaly
  detection** (OpenSearch detectors and/or forecasting) with evaluation and alerting
  hooks - **before** relying on LLMs for RCA
- Phase 3: **Assisted RCA** (retrieval + **graph-RAG** over subgraph + vectors,
  incident timelines, hypotheses, recommended actions) using OpenSearch hybrid search
  and, if used, Bedrock/SageMaker with strict data boundaries
- Phase 4 (optional): deeper **graph ML** (GNNs, link prediction) where justified
  by scale and team skills
- Explain how to implement with minimal ops: OpenSearch k-NN, anomaly detection,
  PPL/DSL patterns; AWS AI integration with governance
- Governance: human-in-the-loop, auditability, PII controls, prompt injection
  risks (if LLM is used)

G) Deliverables

List concrete artifacts to produce:

- Architecture diagrams (describe in text), ADRs
- **ArgoCD `Application` (or ApplicationSet) YAML** referencing **Helm** charts;
  Helm charts and values for OpenTelemetry Collectors and other in-cluster
  components; OpenTelemetry
  Collector configs; **OSI pipeline** definitions (as applicable); index
  templates/mappings
- **Neo4j** sync job specs or streaming design, graph schema documentation
  (if in scope)
- Dashboards/alerts-as-code, runbooks, onboarding docs
- Security evidence (IAM policies, encryption settings, audit trails)
- Operational docs (capacity plan, cost controls, DR runbook)

## OUTPUT FORMAT (STRICT)

1. Executive Summary (5–10 bullets)
2. Assumptions
3. Clarification Q&amp;A (only if you asked questions) + resulting decisions
4. Architecture Variations + Decision Matrix (table)
5. Recommended Target Architecture (components + data flows + tenancy boundaries)
6. Step-by-Step Roadmap (phases with tasks, acceptance criteria, DoD, validation,
  rollback)
7. Detailed Technical Runbook (organized by metrics/logs/traces/security/GitOps;
  include small snippets, e.g. **ArgoCD Application** + **Helm** `values` for collectors)
8. Backlog Breakdown (Epics → Stories/Tasks table with acceptance criteria)
9. Risk Register (table: risk, impact, likelihood, mitigation, owner)
10. Cost &amp; Capacity Notes (drivers + levers)
11. Go-Live Checklist
