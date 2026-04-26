# Neo4j Graph Module

This directory contains the optional Neo4j graph module manifests for
Batch 11.

## Behavior

- Graph module activation is explicit through graph profile selection.
- Core telemetry collection and OpenSearch ingest continue when graph is disabled.
- Graph deployment failures must not block core observability behavior.

## Validation

- `bash scripts/ci/validate_graph_foundation.sh`
- `bash scripts/ci/validate_batch11_smoke.sh`
