# CI/CD Adapters

CI/CD adapters provide optional pipeline template integration without changing
core observability contracts. They are cloud-agnostic by construction: each
template wires an external CI/CD system to the same core validation and release
gates that the platform already requires.

## Contract Boundaries

- adapters are additive and profile-scoped
- core validation and release gates remain authoritative
- reversible disablement path is required
- fallback behavior must preserve core deployment safety
- read-only dispatch mode (no write-path targets)
- bounded validation step count per template

## Supported Templates

The full mapping lives in `CICD_ADAPTER_TEMPLATE_COMPATIBILITY_V1.yaml`. The
table below summarizes each template — the contract is open to additional
templates that conform to the same `pipeline-template` mode.

| Template          | Mode               | Supported Runners                | Bounded Steps    |
| ----------------- | ------------------ | -------------------------------- | ---------------- |
| github-actions    | pipeline-template  | github-hosted, self-hosted       | 20 validations   |
| gitlab-ci         | pipeline-template  | shared, self-managed             | 20 validations   |
| argo-workflows    | pipeline-template  | self-managed (in-cluster)        | 20 validations   |
| tekton-pipelines  | pipeline-template  | self-managed (in-cluster)        | 20 validations   |

All templates generate the same value set:
`cicd.enabled`, `cicd.mode`, `cicd.pipelineTemplateRef`.

## Adding a New Template

1. Add an entry under `cicd_templates:` in
   `CICD_ADAPTER_TEMPLATE_COMPATIBILITY_V1.yaml`.
2. Specify supported runners and required template fields.
3. Define `outputs.generated_values` (must include the three values above) and
   `outputs.bounded_steps.max_validation_steps`.
4. Run `bash scripts/ci/validate_cicd_adapter_templates.sh` to verify.

## Validation

`scripts/ci/validate_cicd_adapter_templates.sh` enforces:
- `core_contracts_unchanged: true`
- `dispatch_mode: read-only`
- per-template required fields and bounded validation-step limits
- presence of rollback/uninstall notes referencing the validator

## Rollback

See `ROLLBACK_UNINSTALL_NOTES.md` for the disable, validate, and remove
procedures. Disabling a CI/CD adapter does not affect any other adapter or any
core platform behavior.
