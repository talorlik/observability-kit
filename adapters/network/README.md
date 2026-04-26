# Network Adapters

Network adapters provide optional ingress and traffic policy integration without
changing core observability contracts.

## Contract Boundaries

- adapters are additive and profile-scoped
- core namespace and network policy boundaries remain authoritative
- reversible disablement path is required
- fallback behavior must preserve core control-plane reachability
