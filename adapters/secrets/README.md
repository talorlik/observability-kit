# Secrets Adapters

Secrets adapters extend backend secret-store integration without changing core
observability contracts.

## Contract Boundaries

- no mutation of core identity or boundary contract fields
- explicit profile-driven activation only
- reversible disablement path required
- fallback must return to core defaults
