# Kagent Khook Implementation Batch Command Sheet

Use these commands to run implementation in controlled batches aligned to
`docs/auxiliary/planning/kagent_khook/KAGENT_KHOOK_IMPLEMENTATION_TASKS.md`.
Run one batch at a time and require validation before moving forward.

## Batch Commands

| Batch | Command To Send | Validation Step (Required) |
| ---- | ---- | ---- |
| 1 | `Do batch 1: boundary and protocol contracts.` | Validate boundary and protocol contract schema lint, compatibility matrix coverage, and CI policy gate rejection for direct AI-to-datastore paths. |
| 2 | `Do batch 2: security and governance contracts.` | Validate identity access matrix allow/deny tests, complete tool risk classification coverage, and approval plus audit contract path tests. |
| 3 | `Do batch 3: shared state and inter-agent envelope.` | Validate case-file schema fixtures and lifecycle transitions, envelope schema conformance, and forbidden communication-edge policy denials. |
| 4 | `Do batch 4: MCP catalog and tool contracts.` | Validate MCP catalog completeness against required services, response schema binding for all catalog tools, and tenancy/redaction boundary test pass. |
| 5 | `Do batch 5: base runtime and GitOps scaffolding.` | Validate `kustomize build` for all overlays, runtime base component readiness checks, and gatewayed MCP endpoint baseline health verification. |
| 6 | `Do batch 6: read-only MCP services.` | Validate gateway contract integration for all read-only services, timeout and quota behavior checks, and case-file service lifecycle plus resume tests. |
| 7 | `Do batch 7: multi-agent topology and prompt controls.` | Validate role-based tool binding allow/deny tests, catalog-to-policy conformance, and end-to-end read-only orchestration flow with evidence persistence. |
| 8 | `Do batch 8: khook triggered investigation flows.` | Validate hook catalog schema and enrichment payload correctness, dedupe and burst-control policy behavior, and trigger-to-summary integration reliability tests. |
| 9 | `Do batch 9: approval-gated action plane.` | Validate high-risk action rejection without approval, action precondition policy enforcement, complete action journal lineage, and rollback branch test pass. |
| 10 | `Do batch 10: productization and release gates.` | Validate discovery preflight and deterministic overlay generation across modes, full release gate script pass, and operator runbook coverage for install, rollback, and uninstall. |

## Optional Adapter Extension Commands

Use these only after core batches `IKTB-01` to `IKTB-10` are complete.

1. `Do optional adapter batch IKAD-01: provider event-source adapters.`
2. `Do optional adapter batch IKAD-02: identity backend adapters.`
3. `Do optional adapter batch IKAD-03: secrets backend adapters.`
4. `Do optional adapter batch IKAD-04: storage backend adapters.`
5. `Do optional adapter batch IKAD-05: network and ingress adapters.`
6. `Do optional adapter batch IKAD-06: CI/CD adapter templates.`

## Optional Strict Commands

Use these when explicit evidence is always required.

1. `Do batch X and include validation evidence only when all checks pass.`
2. `Do batch X, stop before merge, and show failed validations first if any.`
3. `Do batch X and produce a short validation report with pass/fail per check.`

## Stop/Resume Commands

- `Stop after current task and summarize status.`
- `Pause after batch X validation and wait for approval.`
- `Proceed to next batch.`

## Example

```markdown
REFERENCE: @docs/auxiliary/planning/kagent_khook/KAGENT_KHOOK_IMPLEMENTATION_TASKS.md
TASKS:
- Do batch 8: khook triggered investigation flows.
- Validate hook catalog schema and enrichment payload correctness, dedupe and burst-control policy behavior, and trigger-to-summary integration reliability tests.
```
