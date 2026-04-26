# Rollback And Uninstall Runbook

## Purpose

Provide deterministic rollback and uninstall workflow for platform releases.

## Rollback

- Identify last known good GitOps revision.
- Reconcile Argo CD application to that revision.
- Verify collector, search, and dashboard components recover to healthy state.

### Rollback Procedure

1. Validate release gates before rollback:

```bash
bash scripts/ci/validate_kagent_khook_release.sh
```

1. Capture current application revision:

```bash
kubectl -n argocd get application platform-core -o jsonpath='{.status.sync.revision}'
```

1. Sync to the last known good revision:

```bash
argocd app rollback platform-core <REVISION_ID>
```

1. Re-run baseline checks:

```bash
bash scripts/ci/validate_all_batches_with_report.sh
```

## Uninstall

- Remove platform applications from GitOps control.
- Delete platform namespace-scoped resources.
- Verify no orphaned cluster-scoped resources remain.

### Uninstall Procedure

1. Remove GitOps application:

```bash
kubectl -n argocd delete application platform-core
```

1. Delete platform runtime namespaces:

```bash
kubectl delete namespace observability-system ai-runtime ai-triggers mcp-system mcp-services ai-gateway ai-policy --ignore-not-found
```

1. Verify uninstall completion:

```bash
kubectl get namespace | grep -E 'observability-system|ai-runtime|ai-triggers|mcp-system|mcp-services|ai-gateway|ai-policy' || true
```

## Verification

- Confirm no crash-looping workloads remain.
- Confirm readiness smoke checks are green or intentionally disabled.
- Confirm uninstall left no active platform namespaces or managed applications.
