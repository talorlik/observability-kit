# Graph Foundation Operator Guide

This guide defines the Batch 11 operator flow for the optional derived graph
intelligence tier.

## Scope

Batch 11 validates:

- optional graph module enable and disable behavior without core disruption
- versioned graph schema for services, dependencies, ownership, and incidents
- idempotent sync jobs that converge across replay-safe runs
- graph freshness and sync quality alerts with routing
- dependency and blast-radius query coverage for incident replay
- graph operations runbook dry run for rebuild, repair, and fallback

## Artifacts

- `contracts/graph/GRAPH_MODULE_PROFILE_VALIDATION.json`
- `contracts/graph/GRAPH_SCHEMA_VERSIONING_VALIDATION.json`
- `contracts/graph/GRAPH_IDEMPOTENT_SYNC_VALIDATION.json`
- `contracts/graph/GRAPH_FRESHNESS_ALERTS_VALIDATION.json`
- `contracts/graph/GRAPH_DEPENDENCY_QUERIES_VALIDATION.json`
- `contracts/graph/GRAPH_RUNBOOK_DRY_RUN_VALIDATION.json`

## Validation Entry Points

Run focused Batch 11 validation:

```bash
bash scripts/ci/validate_graph_foundation.sh
```

Run focused Batch 11 smoke validation:

```bash
bash scripts/ci/validate_batch11_smoke.sh
```

Render platform core with graph enabled using profile values:

```bash
helm template platform-core gitops/charts/platform-core \
  -f gitops/platform/observability/values/graph-pipeline.yaml
```

## Expected Outcomes

- graph module can toggle on or off with core telemetry path health preserved
- schema versioning and migration controls are documented and approved
- repeated sync jobs converge with no duplicate graph relationships
- stale graph conditions trigger expected alerts and route correctly
- operator query set returns expected dependency and blast-radius paths
- graph runbook dry-run validates rebuild, repair, and fallback steps

## Neo4j Browser Access and RBAC

This section defines the graph-enabled UI exposure contract for Neo4j
Browser. It uses the admin access plane terminology from
`docs/runbooks/VISUALIZATION_ADMIN_ACCESS_PLANE_GUIDE.md` and the admin
access profile contract in
`install/profiles/admin-access/PROFILE.schema.json`.

### Endpoint

- Neo4j Browser is published only in graph-enabled mode through
  `gitops/platform/graph/neo4j/browser-access.yaml`, synced by the
  graph-stack Application after graph profile selection.
- The exposure targets the dedicated `neo4j-browser` Service on port
  7474. The bolt port (7687) stays cluster-internal for sync jobs and
  is never routed through the admin access plane.
- The published endpoint is recorded as the optional `neo4j_browser`
  entry in the admin access profile `endpoints` block.
- Both admin access plane modes are covered: `ingress` applies the
  Ingress variant, `gateway` applies the HTTPRoute variant attached to
  the shared `admin-ui-gateway`. Apply the variant matching the
  selected admin access profile mode.

### TLS

- TLS is mandatory and terminates at the admin access plane, matching
  the profile constraint `tls.enabled: true`.
- The `graph-admin-ui-tls` certificate secret is provisioned per the
  profile `tls.source` value (`cert-manager` or `external-secret`).
- No plain HTTP path to port 7474 is provisioned outside the cluster.

### Authentication

- The admin access plane authn provider (`oidc` or `saml-adapter`,
  with `mfa_required` per profile) gates who reaches the endpoint.
- Neo4j database login is a second, independent layer. Credentials
  live in the `graph-neo4j-auth` Kubernetes Secret (`NEO4J_AUTH`,
  `username`, and `password` keys), provisioned by the selected
  secrets backend adapter. Manifests never carry literal credentials,
  and the sync-job secret refs in
  `contracts/graph/GRAPH_MODULE_PROFILE_VALIDATION.json` use the same
  Secret.

### Role Plan

- Read-only analyst: members of `role_mapping.readonly_group`. Runs
  dependency, blast-radius, and ownership queries. Where the deployed
  Neo4j edition supports native role assignment, map these sessions to
  the built-in `reader` role.
- Graph admin: members of `role_mapping.admin_group`. Performs schema
  migrations, sync repair, and credential rotation. Map these sessions
  to the built-in `admin` role.
- Access plane group mapping is the enforced baseline: only members of
  the two mapped groups reach the Browser endpoint at all. If the
  deployed edition lacks native RBAC, treat the single
  `graph-neo4j-auth` credential as graph-admin scoped and issue it to
  graph admins only; analysts then work through curated dashboards
  instead of direct Browser sessions.

### Break-Glass

> [!WARNING]
> Break-glass bypasses the identity provider, not Neo4j login. The
> `graph-neo4j-auth` Secret remains required for any database session.

- Break-glass access follows the admin access profile `break_glass`
  contract: explicitly enabled and time-boxed by `expiry_minutes`
  (15 to 240 minutes).
- After a break-glass window closes, rotate the `graph-neo4j-auth`
  Secret and confirm sync jobs pick up the new credential before
  declaring the incident access closed.
