# Rollback Runbook

This runbook defines baseline rollback entrypoints for GitOps-managed changes.

## Triggers

- Invalid chart change reaches cluster.
- Platform application fails to reconcile.
- Policy violations are found post-merge.

## Steps

1. Identify last known-good commit in Git.
1. Revert platform changes that caused drift:

```bash
git revert <bad-commit-sha>
```

1. Push revert commit and allow GitOps reconciliation.
1. Confirm application health in Argo CD and cluster state.
1. Re-run validation checks:

```bash
bash scripts/ci/validate_install_contract.sh
bash scripts/ci/validate_gitops_structure.sh
bash scripts/ci/validate_runbook_links.sh
```

## Exit Criteria

- GitOps app returns to healthy sync status.
- Baseline validation checks pass on rollback commit.
