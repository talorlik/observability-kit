# Provider Adapters

Provider adapters extend integration points for external event sources without
mutating core observability contracts. They are cloud-agnostic by construction:
adapters normalize provider-native events into a single hook event schema that
the platform consumes the same way regardless of where the events came from.

## Contract Boundaries

- no mutation of core install contract fields
- explicit profile-driven activation only
- reversible disablement path required
- fallback must return to core defaults
- read-only dispatch mode (no write-path targets)
- bounded payload size per provider

## Supported Providers

The full mapping lives in `EVENT_SOURCE_ADAPTER_COMPATIBILITY_V1.yaml`. The
table below summarizes each provider class — these are not the only valid event
source providers; the contract is open to additional providers that conform to
the same normalization rules.

| Provider | Event Sources                  | Normalized Hook IDs                                    | Bounded Payload |
| -------- | ------------------------------ | ------------------------------------------------------ | --------------- |
| aws      | eventbridge, cloudwatch        | pod-restart, oom-kill, probe-failed, pod-pending, node-not-ready | 16 KiB |
| gcp      | eventarc, cloud_monitoring     | pod-restart, probe-failed, node-not-ready              | 16 KiB |
| azure    | event_grid, azure_monitor      | pod-restart, oom-kill, probe-failed, pod-pending       | 16 KiB |

All providers must populate the same normalized event envelope:
`provider`, `source`, `event_timestamp`, `cluster`, `namespace`, `object_kind`,
`object_name`, `reason`, `message`.

## Adding a New Provider

1. Add an entry under `providers:` in `EVENT_SOURCE_ADAPTER_COMPATIBILITY_V1.yaml`.
2. Specify supported event sources and the normalized hook IDs they map to.
3. Define `normalization.required_fields` and `normalization.bounded_payload`.
4. Run `bash scripts/ci/validate_provider_event_source_adapters.sh` to verify.

## Validation

`scripts/ci/validate_provider_event_source_adapters.sh` enforces:
- `core_contracts_unchanged: true`
- `dispatch_mode: read-only`
- `deny_write_path_targets: true`
- per-provider required fields and bounded payload size
- presence of rollback/uninstall notes referencing the validator

## Rollback

See `ROLLBACK_UNINSTALL_NOTES.md` for the disable, validate, and remove
procedures. Disabling a provider adapter does not affect any other provider
or any core platform behavior.
