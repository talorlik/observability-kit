# Case File Lifecycle V1

This lifecycle defines deterministic state transitions for workflow-safe
incident case files.

## Allowed States

- `open`
- `triaging`
- `investigating`
- `awaiting-approval`
- `executing`
- `resolved`
- `closed`
- `rejected`

## Allowed Transitions

| From | To |
| ---- | ---- |
| `open` | `triaging` |
| `triaging` | `investigating` |
| `investigating` | `awaiting-approval` |
| `investigating` | `resolved` |
| `awaiting-approval` | `executing` |
| `awaiting-approval` | `rejected` |
| `executing` | `resolved` |
| `resolved` | `closed` |

## Resume Rules

- Resume source of truth is persistent case file state only.
- Resume MUST NOT use transient in-memory agent state.
- If persisted state is unknown, transition MUST fail closed.
- Replay from `awaiting-approval` and `executing` requires latest
  `approval_state` and `action_journal` consistency checks.
