# Casefile Review Runbook

This runbook covers operations for incident casefiles produced by the
AI/MCP layer (Batch 14). Casefiles are the structured, append-only record
of an investigation: who looked at what, what evidence was collected,
which approvals were granted, and what action was taken.

## Scope

A casefile follows the schema in `contracts/ai/CASEFILE_SCHEMA_V1.yaml`.
Sample fixtures (including invalid rejection paths) are in
`contracts/ai/CASEFILE_FIXTURES_V1.json`.

Related contracts:

- `contracts/ai/CASEFILE_SCHEMA_V1.yaml`
- `contracts/ai/CASEFILE_FIXTURES_V1.json`
- `contracts/ai/REPLAY_RESUME_RULES_V1.yaml`
- `contracts/policy/APPROVAL_FLOW_V1.yaml`
- `contracts/policy/AUDIT_EVENT_SCHEMA_V1.json`

Related dashboards:

- `gitops/platform/search/dashboards/saved-objects/AI_RUNTIME_HEALTH.ndjson`
  (casefile state transitions panel)

## Casefile State Machine

Valid state transitions:

- `open` → `triaging` → `investigating` → `awaiting-approval` → `executing`
  → `resolved` → `closed`
- `open` → `triaging` → `investigating` → `resolved` → `closed`
- `open` → `triaging` → `investigating` → `awaiting-approval` → `rejected`

Anything else is rejected per `CASEFILE_FIXTURES_V1.json.invalid_transition_samples`.

## Review Procedure

1. **Pull the casefile by `case_id`** via the casefile MCP service.
2. **Confirm lineage block** is populated: `lineage.correlation_id` and
   `lineage.workflow_id` must be present. Missing lineage triggers a
   rejection per `CASEFILE_FIXTURES_V1.invalid_fixtures.missing_lineage`.
3. **Verify evidence handles** use a supported scheme: `ev://`, `out://`,
   or other allow-listed URIs. HTTP URLs to untrusted hosts are rejected.
4. **Inspect approval state** for consistency with status:
   - `executing` requires `approval_state.status == "approved"`
   - `awaiting-approval` requires `approval_state.status == "pending"`
   - `resolved` permits either approved or not-required
5. **Validate schema_version** matches a supported version (currently
   `v1`).
6. **Walk action_journal** to confirm every state-changing action emitted
   an audit event matching `AUDIT_EVENT_SCHEMA_V1.json` required fields.

## Resuming an Interrupted Case

Per `REPLAY_RESUME_RULES_V1.yaml`, a casefile may be resumed when:

1. Its lineage block is intact.
2. All evidence handles still resolve.
3. The approval state is consistent with its status.

To resume:

1. Re-load the casefile via the MCP casefile service.
2. Trigger the multi-agent pipeline with `--resume <case_id>`.
3. The investigation manager will re-dispatch from the last known
   investigating state without overwriting prior outputs.

## Casefile Archival and Cleanup

1. Closed casefiles are retained for 730 days per the
   `kagent_audit` namespace retention in
   `contracts/ai/KAGENT_PERSISTENCE_CONTRACT_V1.yaml`.
2. Archival to long-term storage uses the snapshot path defined in
   `adapters/storage/STORAGE_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml`.
3. Casefile data is not deleted before retention; it is moved to the
   `delete` ILM state via `metrics-ilm-policy.json`-style rollover only
   after retention has elapsed.

## Validation Commands

```bash
bash scripts/ci/validate_ai_state_contracts.sh
bash scripts/ci/validate_action_gate_scaffolding.sh
bash scripts/ci/validate_batch14_smoke.sh
```

## Common Rejection Reasons

From `CASEFILE_FIXTURES_V1.invalid_fixtures.expected_rejection_reason`:

- `lineage.required-block-absent`
- `approval-state.invariant-violated`
- `evidence-handle.unsupported-scheme`
- `schema-version.unsupported`
