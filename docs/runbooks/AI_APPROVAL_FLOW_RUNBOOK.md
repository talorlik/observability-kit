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

## Exit Criteria

- Action decision and lineage are persisted.
- Case file and action journal remain consistent.
