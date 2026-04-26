# Storage Adapters

Storage adapters provide optional backend-specific storage integration while
retaining the core OpenSearch default index and lifecycle contracts as
authoritative. Storage adapters are cloud-agnostic: they layer over any
conformant Kubernetes-resident OpenSearch deployment, and snapshot backends
are object-storage-API agnostic (S3 API, Azure Blob, GCS).

## Contract Boundaries

- adapters are additive and profile-scoped
- OpenSearch templates and ILM contracts remain authoritative
- fallback behavior must preserve core data-plane stability
- read-only dispatch mode (no write-path targets)
- core index templates may not be deleted
- direct datastore access is denied

## Supported Backends

The full mapping lives in `STORAGE_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml`. The
table below summarizes each backend.

| Backend                          | Mode                | Profiles                                  | Generated Values                                            | Bounded `max_templates` |
| -------------------------------- | ------------------- | ----------------------------------------- | ----------------------------------------------------------- | ----------------------- |
| opensearch-hot-warm              | opensearch-managed  | quickstart, dev, staging, prod            | storage.enabled, storage.mode, storage.indexTemplateOverride | 6                       |
| s3-snapshot-repository           | snapshot-only       | staging, prod                             | storage.enabled, storage.mode, storage.snapshotRepositoryRef | 2                       |
| azure-blob-snapshot-repository   | snapshot-only       | staging, prod                             | storage.enabled, storage.mode, storage.snapshotRepositoryRef | 2                       |
| gcs-snapshot-repository          | snapshot-only       | staging, prod                             | storage.enabled, storage.mode, storage.snapshotRepositoryRef | 2                       |

## Adding a New Backend

1. Add an entry under `storage_backends:` in
   `STORAGE_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml`.
2. Set `mode` (e.g., `opensearch-managed`, `snapshot-only`).
3. List `supported_profiles` and `required_fields`.
4. Set `outputs.generated_values` (must include `storage.enabled` and
   `storage.mode`) and `outputs.bounded_policies.max_templates`.
5. Run `bash scripts/ci/validate_storage_backend_adapters.sh` to verify.

## Validation

`scripts/ci/validate_storage_backend_adapters.sh` enforces:
- `core_contracts_unchanged: true`
- `dispatch_mode: read-only`
- `preserve_core_index_templates: true`
- per-backend `storage.enabled` and `storage.mode` generated values
- per-backend `bounded_policies.max_templates > 0`
- presence of rollback/uninstall notes referencing the validator

## Rollback

See `ROLLBACK_UNINSTALL_NOTES.md` for the disable, validate, and remove
procedures. Disabling a storage adapter must restore the core OpenSearch
template and ILM contracts unchanged.
