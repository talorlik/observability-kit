# Kagent Khook Batch Command Sheet

Use these commands to control delivery pace for the Kagent Khook backlog.
Run one batch at a time and require validation before moving forward.

All batches should be judged against the same end-state objective described in
the Kagent Khook planning set: contract-first delivery, cloud-agnostic and
Kubernetes-native runtime behavior, open-source-first components, strict
governance and approval controls, and release readiness across install modes.

## Batch Commands

| Batch | Command To Send | Validation Step (Required) |
| ---- | ---- | ---- |
| 1 | `Do batch 1: boundary and protocol contracts.` | Validate architecture boundary contract, no direct AI-to-datastore deny rules, replaceability matrix, versioned protocol edge schemas, namespace boundary rules, and CI contract gating. |
| 2 | `Do batch 2: security and governance contracts.` | Validate identity matrix coverage, tool risk classification mapping, approval policy preconditions, policy decision schema behavior, audit field contract coverage, and CI governance gate enforcement. |
| 3 | `Do batch 3: shared state and envelope contracts.` | Validate case-file schema lifecycle coverage, inter-agent envelope compatibility, contradiction handling and confidence rollup determinism, restart-safe replay behavior, communication graph policy enforcement, and CI schema gate results. |
| 4 | `Do batch 4: MCP catalog and tool contracts.` | Validate versioned MCP catalog completeness, common response schema compliance, tenancy and redaction boundaries, gateway registration and discovery constraints, semantic versioning policy checks, and CI MCP contract gating. |
| 5 | `Do batch 5: base control plane scaffolding.` | Validate external PostgreSQL and Kagent health, kmcp and MCP CRD reconciliation, Khook controller readiness, MCP/A2A gateway reachability and policy controls, baseline OpenTelemetry visibility, and GitOps overlay render and sync checks. |
| 6 | `Do batch 6: read-only MCP service scaffolding.` | Validate gateway-served schema-valid responses for incident, graph, trace, metrics, and change services, case-file persistence and retrieval contracts, redaction and scope controls, and full read-path smoke plus contract suite pass status. |
| 7 | `Do batch 7: multi-agent scaffolding.` | Validate CEO and manager invocation policy alignment, specialist read-only tool binding restrictions, action specialist approval blocks, required prompt-fragment coverage, end-to-end read-only orchestration synthesis with evidence handles, and CI topology policy checks. |
| 8 | `Do batch 8: Khook trigger scaffolding.` | Validate hook schema deployment for restart and health events, enrichment field completeness, deduplication and burst-control behavior, read-only dispatch restrictions, case-file and operator channel output attachment, and functional plus resilience smoke outcomes. |
| 9 | `Do batch 9: approval-gated action scaffolding.` | Validate write-path tool exposure by risk class, policy engine and approval service enforcement, remediation executor precondition gating, action journaling and evidence capture completeness, rejected-action and rollback determinism, and CI plus staging action-gate tests. |
| 10 | `Do batch 10: productization and release scaffolding.` | Validate install mode contract schemas, capability discovery-to-overlay determinism, compatibility matrix state definitions, release validation suite coverage (functional, safety, performance, upgrade), operator runbook completeness, and final production activation gate sign-off workflow. |

## Optional Strict Commands

Use these if you want the agent to always include explicit evidence.

1. `Do batch X and include validation evidence only when all checks pass.`
2. `Do batch X, stop before merge, and show failed validations first if any.`
3. `Do batch X and produce a short validation report with pass/fail per check.`

## Stop/Resume Commands

- `Stop after current task and summarize status.`
- `Pause after batch X validation and wait for approval.`
- `Proceed to next batch.`

## Example

```markdown
REFERENCE: @docs/auxiliary/planning/kagent_khook/KAGENT_KHOOK_TASKS.md
TASKS:
- Do batch 1: boundary and protocol contracts.
- Validate architecture boundary contract, protocol schemas, namespace policy,
  and CI contract gates before continuing.
```
