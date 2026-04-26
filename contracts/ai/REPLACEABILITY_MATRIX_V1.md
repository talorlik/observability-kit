# Replaceability Matrix V1

This matrix defines swappable AI runtime components and the external
behavior contracts that must remain stable to preserve compatibility.

## Compatibility Rules

- Contract versioning is semantic (`v1`, `v2`, and so on).
- Breaking behavior change requires a new major contract version.
- Component internals may change as long as all required external contracts
  remain stable.

## Swap Matrix

| Component | Swappable Scope | Required External Contract(s) | Must Not Change Across Swap |
| ---- | ---- | ---- | ---- |
| Khook controller | implementation/runtime | `BOUNDARY_CONTRACT_V1.yaml`, `PROTOCOL_EDGES_V1.yaml#/edges/khook_to_kagent` | canonical dispatch path, trigger payload edge schema, correlation semantics |
| Kagent orchestrator | implementation/runtime | `BOUNDARY_CONTRACT_V1.yaml`, `PROTOCOL_EDGES_V1.yaml#/edges/agent_to_agent`, `PROTOCOL_EDGES_V1.yaml#/edges/agent_to_mcp` | orchestrator edge behavior, tool mediation expectations, envelope compatibility |
| MCP gateway | implementation/runtime | `BOUNDARY_CONTRACT_V1.yaml`, `NAMESPACE_BOUNDARY_RULES_V1.yaml` | gateway mediation requirement, namespace enforcement, no direct datastore edge |
| MCP services | implementation/runtime | `PROTOCOL_EDGES_V1.yaml#/edges/agent_to_mcp`, `NAMESPACE_BOUNDARY_RULES_V1.yaml` | tool endpoint contract surface, tenant scoping contract, API-mediated backend access |

## Validation Hooks

- CI script: `scripts/ci/validate_ai_boundary_contracts.sh`
- Deny policy: `contracts/policy/NO_DIRECT_DATASTORE_ACCESS.rego`

## Marker Coverage

- `KK-C01`: enforced by canonical runtime path checks
- `KK-C02`: enforced by direct datastore deny checks
- `KK-C03`: enforced by replaceability + protocol + namespace contract checks
