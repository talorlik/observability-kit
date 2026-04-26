# Identity Adapters

Identity adapters extend backend identity integration without changing core
observability contracts.

## Contract Boundaries

- no mutation of core identity access matrix fields
- explicit profile-driven activation only
- reversible disablement path required
- fallback must return to core defaults
