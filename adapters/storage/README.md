# Storage Adapters

Storage adapters provide optional backend-specific storage integration while
retaining OpenSearch default index and lifecycle contracts.

## Contract Boundaries

- adapters are additive and profile-scoped
- OpenSearch templates and ILM contracts remain authoritative
- fallback behavior must preserve core data-plane stability
