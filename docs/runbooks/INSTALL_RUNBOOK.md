# Install Runbook

This runbook covers the baseline install flow for the platform core.

## Preconditions

- Kubernetes cluster access is available.
- Argo CD is installed or planned as the GitOps controller.
- Install contract input file is prepared and valid.

## Steps

1. Validate install contract schema:

```bash
bash scripts/ci/validate_install_contract.sh
```

1. Validate compatibility matrix and mode logic:

```bash
bash scripts/ci/validate_compatibility_and_modes.sh
```

1. Validate GitOps baseline paths:

```bash
bash scripts/ci/validate_gitops_structure.sh
```

1. Apply or sync the default Argo CD application:

```bash
kubectl apply -f gitops/apps/platform-core-application.yaml
```

1. Confirm the platform namespace exists:

```bash
kubectl get namespace observability
```

## Exit Criteria

- The application manifest is accepted by the cluster.
- Namespace and chart resources reconcile successfully.
