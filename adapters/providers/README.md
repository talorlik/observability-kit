# Provider Adapters

Provider adapters extend integration points for cloud or infrastructure vendors
without changing core observability contracts.

## Contract Boundaries

- no mutation of core install contract fields
- explicit profile-driven activation only
- reversible disablement path required
- fallback must return to core defaults
