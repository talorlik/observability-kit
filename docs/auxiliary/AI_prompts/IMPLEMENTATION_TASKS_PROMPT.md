# IMPLEMENTATION TASKS DOCUMENT CREATION PROMPT

## REFERENCES

- @docs/auxiliary/planning/OBSERVABILITY_PLATFORM_V2.plan.md
- @docs/auxiliary/planning/PRD.md
- @docs/auxiliary/planning/TECHNICAL.md
- @docs/auxiliary/planning/TASKS.md

## ROLE

You are a senior platform architect, observability engineer, staff-level implementation
planner, and delivery lead.

## OBJECTIVE

Create a new Markdown document named `IMPLEMENTATION_TASKS.md` whose purpose is
to drive the actual creation of the full observability platform defined in the
reference documents.

This is NOT a generic planning backlog.
This is NOT a rewrite of the existing high-level backlog.
This MUST be an execution backlog that can be used to actually build the platform
in the repository, batch by batch.

## PRIMARY GOAL

Convert the existing planning artifacts into a concrete, incremental,
implementation-grade task document that:

- creates the actual platform components
- connects all existing deliverables together
- preserves logical sequencing and dependencies
- is small enough to execute batch-by-batch
- is precise enough that an AI coding agent can start implementing from it with
  minimal ambiguity

## SOURCE-OF-TRUTH PRIORITY

1. `SYSTEM_INSTRUCTIONS_DOCS.md` style and architectural posture if available in
  context
2. `OBSERVABILITY_PLATFORM_V2.plan.md`
3. `PRD.md`
4. `TECHNICAL.md`
5. `TASKS.md`

## MANDATORY ARCHITECTURAL POSTURE

- Cloud agnostic
- Kubernetes-native
- Open-source-first
- Plug-and-play
- Guided installation and configuration
- Discovery-led install and onboarding
- Core platform separated from adapters
- No cloud-vendor lock-in in the core backlog
- OpenTelemetry is the only baseline collector path
- OpenSearch is the default telemetry and vector backend
- OpenSearch Dashboards is the default UI
- Neo4j is an optional derived graph module, not the raw telemetry store
- Argo CD is the default GitOps reference, but tasks must preserve CI/CD neutrality
  where the docs require it

## CRITICAL INSTRUCTION

Use the existing `TASKS.md` as the execution backbone and preserve its batch-oriented
operating model, but transform it into a more concrete implementation backlog that
actually creates the platform artifacts, code, configuration, tests, policies,
dashboards, and runbooks.

This means:

- keep the incremental and batched structure
- keep logical ordering from foundation upward
- keep the marker cross-reference mindset
- but replace vague task wording with build-oriented implementation tasks

## DO NOT

- output a generic roadmap
- output another PRD
- output another technical requirements document
- produce large ambiguous epics without actionable implementation detail
- start with cloud-provider-specific integrations
- duplicate existing text unless needed
- leave tasks disconnected from actual repository artifacts

## INSTEAD, PRODUCE

A new implementation document that decomposes the platform into executable batches
and tasks that will create the real system.

## THE NEW DOCUMENT MUST

1. Reuse and refine the existing batch model from `TASKS.md`
2. Map every batch back to the relevant reference markers when applicable:
   - `TB-*`
   - `TR-*`
   - `FR-*`
   - any relevant phase/epic references from the plan
3. Translate backlog items into actual implementation work
4. Name concrete repository paths, modules, charts, configs, scripts, tests, and
  runbooks to be created or modified
5. Make the dependencies explicit
6. Keep tasks small to medium sized
7. Group tasks into logical batches that can be executed one batch at a time
8. Include validation and rollback expectations
9. Cover the whole platform, not only Phase 1
10. Distinguish clearly between:

    - core platform implementation tasks
    - adapter extension tasks
    - validation and operational readiness tasks

ASSUME THE REPOSITORY SHOULD EVOLVE TOWARD THE REFERENCE STRUCTURE BELOW UNLESS
THE REFERENCE DOCS IMPLY A BETTER EQUIVALENT:

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
  scripts/
  tests/
  docs/
````

## IMPLEMENTATION DOCUMENT DESIGN RULES

- Every batch must have a clear goal
- Every task must be implementation-oriented
- Every task must identify the expected artifact(s) to create or change
- Every task must be independently understandable
- Every task must be small or medium in size only
- No task should represent a multi-week opaque stream of work
- Tasks must be ordered so that later tasks build on earlier outputs
- Tasks must reflect the guided-install and discovery-first architecture
- Tasks must preserve the automatic vs low-touch vs manual onboarding boundary
- Tasks must account for validation, rollback, uninstall, and DR evidence

### FOR EACH TASK, USE THIS FORMAT

- Task ID
- Title
- Why it exists
- Depends on
- Reference links

  - relevant `TB-*`
  - relevant `TR-*`
  - relevant `FR-*`
  - relevant plan phase/epic if applicable
- Implementation targets

  - exact or proposed repo paths
  - files/directories/modules/charts/scripts/tests/docs to create or modify
- Execution details

  - 3 to 7 concrete implementation steps
- Expected outputs

  - code/config/docs/tests/manifests generated
- Validation

  - what proves the task is correct
- Rollback / safe failure note
- Completion criteria

### MANDATORY CONTENT THE DOCUMENT MUST COVER

#### A. FOUNDATION AND PRODUCTIZATION

Include implementation tasks for:

- install contract schema
- profile schema definitions
- compatibility matrix artifacts
- support policy artifacts
- repo structure bootstrapping
- GitOps application structure
- CI validation
- policy checks
- secret scanning
- runbook skeletons

#### B. GUIDED INSTALL AND DISCOVERY

Include implementation tasks for:

- preflight engine
- capability detection
- discovery report generation
- mode recommendation logic
- generated overlays
- remediation generation
- post-install readiness report
- smoke-test bundle

#### C. CORE TELEMETRY PLATFORM

Include implementation tasks for:

- OpenTelemetry Operator packaging
- agent DaemonSet config
- gateway Deployment config
- baseline processor chains
- OTLP paths
- collector health telemetry
- failure simulations
- scaling controls

#### D. STORAGE AND SEARCH

Include implementation tasks for:

- OpenSearch deployment profile
- index templates
- lifecycle policies
- mappings
- retention controls
- snapshot configuration
- restore validation
- OpenSearch Dashboards packaging and saved objects

#### E. LOGS, METRICS, TRACES

Include implementation tasks for:

- log parsing
- multiline rules
- redaction
- never-index rules
- metric scrape onboarding
- OTLP metrics support
- trace ingestion
- trace-log correlation
- sampling defaults
- dashboards for all three signals

#### F. WORKLOAD ONBOARDING MODEL

Include implementation tasks for:

- `observability-lib`
- onboarding values contract
- required labels and metadata checks
- policy enforcement
- onboarding examples
- onboarding troubleshooting
- one-block onboarding validation

#### G. SECURITY, GOVERNANCE, AND ISOLATION

Include implementation tasks for:

- environment and team isolation
- RBAC or role modeling where applicable
- encryption controls
- audit logging
- secret handling integration points
- governance checks
- AI governance prerequisites
- compliance evidence artifacts

#### H. RESILIENCE AND OPERATIONS

Include implementation tasks for:

- backup and restore flows
- rollback controls
- uninstall path
- meta-monitoring
- platform health alerts
- SLOs
- burn-rate alerts
- runbooks
- incident drill support

#### I. VECTOR FOUNDATIONS

Include implementation tasks for:

- curated evidence extraction
- embedding pipeline
- vector indices
- semantic retrieval service
- retrieval quality checks
- governance controls for vector data

#### J. GRAPH FOUNDATIONS

Include implementation tasks for:

- Neo4j deployment profile
- graph schema
- ETL or sync jobs
- freshness monitoring
- topology queries
- blast-radius queries
- graph ops runbooks

#### K. RISK SCORING AND RCA READINESS

Include implementation tasks for:

- deterministic feature definitions
- scoring jobs
- dashboards
- backtesting
- hybrid retrieval orchestration
- human approval controls
- auditability for assisted RCA

#### L. ADAPTER MODEL

Include tasks that explicitly separate optional adapters from the core platform,
including:

- provider adapters
- secret backend adapters
- identity adapters
- storage adapters
- ingress/network adapters
- CI/CD adapters

IMPORTANT:
Adapter tasks must be clearly marked as optional extension work and must not
pollute the core platform batches.

## OUTPUT STRUCTURE REQUIRED

The generated `IMPLEMENTATION_TASKS.md` must contain these sections:

1. Title
2. Purpose
3. How to use this document
4. Source-of-truth hierarchy
5. Implementation principles
6. Batch-to-reference mapping table
7. Repository artifact map
8. Implementation batches
9. Batch completion gate
10. Global definition of done
11. Global validation gate
12. Global rollback and uninstall gate
13. Open questions and blocked decisions
14. Suggested first execution order

## QUALITY BAR

The final document must be good enough that:

- I can tell Cursor "do batch 1" and it can begin real implementation work
- each batch creates actual repository artifacts
- the batches connect cleanly to the plan, PRD, technical requirements, and existing
  tasks
- the document is execution-ready, not advisory
- it is obvious what files, modules, charts, policies, tests, and docs need to be
  created
- it preserves the architecture and constraints from the references
- it does not reintroduce cloud lock-in

## IMPORTANT STYLE RULES

- Output Markdown only
- Be concrete, not vague
- Be technically rigorous
- Do not output commentary
- Do not explain what you are about to do
- Do not summarize the input docs
- Output only the final `IMPLEMENTATION_TASKS.md` content
- Preserve clear headings and numbering
- Prefer deterministic wording over aspirational wording

## FINAL REQUIREMENT

- Where the existing `TASKS.md` is still too high-level, decompose it.
- Where the existing `TASKS.md` already has good batch structure, preserve it.
- Where the plan, PRD, and technical requirements contain implementation-critical
  details missing from `TASKS.md`, inject them into the new document so that all
  existing deliverables are connected into one execution-ready implementation backlog.
