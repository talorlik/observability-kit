# Neo4j Graph Module

This directory contains the optional Neo4j graph module manifests for
Batch 11.

## Behavior

- Graph module activation is explicit through graph profile selection.
- Core telemetry collection and OpenSearch ingest continue when graph is disabled.
- Graph deployment failures must not block core observability behavior.

## Browser Access

- `browser-access.yaml` exposes the Neo4j Browser (port 7474) through the
  admin access plane, in graph-enabled mode only. The bolt port (7687)
  stays cluster-internal.
- Database credentials come from the `graph-neo4j-auth` Secret; manifests
  carry no literal credentials.
- Endpoint, TLS, authn mapping, role plan, and break-glass policy are
  documented in `docs/runbooks/GRAPH_FOUNDATION_OPERATOR_GUIDE.md` under
  "Neo4j Browser Access and RBAC".

## Validation

- `bash scripts/ci/validate_graph_foundation.sh`
- `bash scripts/ci/validate_batch11_smoke.sh`
