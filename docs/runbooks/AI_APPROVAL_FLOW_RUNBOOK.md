# AI Approval Flow Runbook

This runbook defines the operator workflow for approval-gated actions in the
Kagent + Khook control plane.

## Preconditions

- Action request is recorded in the case file.
- Policy engine evaluation is complete.
- Approval service is reachable.
- Required evidence handles are attached.

## Approval Workflow

1. Confirm policy decision:

```bash
bash scripts/ci/validate_action_gate_scaffolding.sh
```

1. Confirm the action risk class:

- `write.high-risk` requires explicit human approval.
- `write.critical` requires explicit human approval and change ticket linkage.

1. Validate preconditions in the case file:

- `approval_state.status == approved`
- `policy_decision == allow`
- target resource references are valid
- rollback plan is present

1. Approve or reject:

- Approve only if evidence and rollback plan are complete.
- Reject if any precondition is missing.

1. Record action decision and lineage:

- decision (`approved` or `rejected`)
- approver identity
- timestamp
- linked evidence handles

## Rejection Handling

- Rejections remain deterministic and must set outcome to `blocked`.
- Rejection details must be written to action journal and case file.
- Executor is not invoked on rejected requests.

## Live Rehearsal

Batch 24 rehearses this flow live on the disposable evidence harness
(`bash scripts/dev/live_cluster_harness.sh run --only ai-rehearsal`),
with evidence under `artifacts/evidence/batch24/rehearsal/`:

- A synthetic Kubernetes event matches a hook of
  `triggers/khook/hooks/HOOK_CATALOG_V1.yaml`; KHook dedupes,
  enriches, and dispatches read-only; KAgent opens a casefile and
  runs the read-path investigation through the MCP gateway.
- The proposed `runbook-plan.v1` action (write.high-risk) creates an
  approval request carrying the contract deadline (60 minutes),
  warning threshold (30 minutes), and escalation chain.
- A **human-surrogate approver** (a distinct identity from the
  requesting agent; self-approval is rejected) grants one flow and
  rejects another; the rejection feeds the casefile as `blocked`.
- The timeout path evaluates the real
  `contracts/policy/APPROVAL_FLOW_V1.yaml` rules against a pending
  approval with a supplied as-of clock one minute past the deadline:
  outcome `deny-and-escalate`, escalation audit events per chain
  role, casefile `rejected`. The as-of clock substitutes for a
  61-minute wall-clock wait on a disposable cluster; the rule logic
  is the production logic.
- Policy, redaction, and audit stay intact throughout: every tool
  response passes the gateway's envelope validation and tenancy
  redaction, and every step writes an
  `AUDIT_EVENT_SCHEMA_V1.json`-conformant record.

Structural verification of the captured rehearsal evidence:

```bash
bash scripts/ci/validate_ai_activation.sh
```

## Exit Criteria

- Action decision and lineage are persisted.
- Case file and action journal remain consistent.
