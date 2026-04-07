# Vector Foundations Operator Guide

This guide defines the Batch 10 operator flow for governed vector
foundations on curated operational evidence.

## Scope

Batch 10 validates:

- curated artifact ownership and refresh rules
- extraction pipeline snapshot versioning
- embedding generation and `vectors-*` index writes
- retrieval quality baseline with relevance scoring
- governance controls for PII filtering and retrieval audit events
- vector operations playbook rehearsal for quality checks, reindex, and rollback

## Artifacts

- `contracts/vector/CURATED_ARTIFACT_OWNERSHIP_VALIDATION.json`
- `contracts/vector/EXTRACTION_SNAPSHOTS_VALIDATION.json`
- `contracts/vector/VECTORS_INDEX_WRITE_VALIDATION.json`
- `contracts/vector/RETRIEVAL_QUALITY_BASELINE_VALIDATION.json`
- `contracts/vector/GOVERNANCE_CONTROLS_VALIDATION.json`
- `contracts/vector/VECTOR_PLAYBOOK_REHEARSAL_VALIDATION.json`

## Validation Entry Points

Run focused Batch 10 validation:

```bash
bash scripts/ci/validate_vector_foundations.sh
```

Run focused Batch 10 smoke validation:

```bash
bash scripts/ci/validate_batch10_smoke.sh
```

## Expected Outcomes

- curated artifacts always include an accountable owner and refresh rule
- extraction snapshots are immutable, versioned, and lineage-tracked
- `vectors-*` indices stay writable and queryable with valid vector mappings
- retrieval baseline metrics stay above minimum quality thresholds
- PII filtering and audit events enforce governance controls
- operators can run a controlled reindex and rollback rehearsal successfully
