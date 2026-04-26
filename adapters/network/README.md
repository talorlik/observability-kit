# Network Adapters

Network adapters provide optional ingress and traffic policy integration without
changing core observability contracts. They are cloud-agnostic by construction:
each backend maps an external ingress controller into the same
`network.ingressClassName` shape that the core platform consumes.

## Contract Boundaries

- adapters are additive and profile-scoped
- core namespace and network policy boundaries remain authoritative
- reversible disablement path is required
- fallback behavior must preserve core control-plane reachability
- read-only dispatch mode (no write-path targets)
- bounded route count per backend

## Supported Backends

The full mapping lives in `NETWORK_INGRESS_ADAPTER_COMPATIBILITY_V1.yaml`. The
table below summarizes each backend — the contract is open to additional
ingress backends that conform to the same `ingress-managed` mode.

| Backend                  | Mode             | Supported Clusters | Bounded Routes |
| ------------------------ | ---------------- | ------------------ | -------------- |
| cilium-gateway-api       | ingress-managed  | any                | 20 routes      |
| nginx-ingress            | ingress-managed  | any                | 20 routes      |
| istio-ingress-gateway    | ingress-managed  | any                | 20 routes      |
| aws-alb-controller       | ingress-managed  | eks                | 20 routes      |

All backends generate the same value set:
`network.enabled`, `network.mode`, `network.ingressClassName`.

## Adding a New Backend

1. Add an entry under `network_ingress_backends:` in
   `NETWORK_INGRESS_ADAPTER_COMPATIBILITY_V1.yaml`.
2. Specify supported clusters and required ingress fields.
3. Define `outputs.generated_values` (must include the three values above) and
   `outputs.bounded_rules.max_routes`.
4. Run `bash scripts/ci/validate_network_ingress_adapters.sh` to verify.

## Validation

`scripts/ci/validate_network_ingress_adapters.sh` enforces:
- `core_contracts_unchanged: true`
- `dispatch_mode: read-only`
- per-backend required fields and bounded route limits
- presence of rollback/uninstall notes referencing the validator

## Rollback

See `ROLLBACK_UNINSTALL_NOTES.md` for the disable, validate, and remove
procedures. Disabling a network adapter does not affect any other adapter or
any core platform behavior.
