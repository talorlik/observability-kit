# CI CD Adapters

CI/CD adapters provide optional pipeline template integration without changing
core observability contracts.

## Contract Boundaries

- adapters are additive and profile-scoped
- core validation and release gates remain authoritative
- reversible disablement path is required
- fallback behavior must preserve core deployment safety
