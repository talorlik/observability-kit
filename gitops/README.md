# GitOps Baseline

This directory defines the Batch 1 baseline structure for GitOps delivery.

## Structure

- `apps/` contains Argo CD applications.
- `charts/` contains Helm chart sources.
- `overlays/` contains environment overlays and generated values.
- `dashboards/` contains dashboard-as-code bundles.
- `alerts/` contains alert and rule definitions.

## Default Application

The default core application is:

- `apps/platform-core-application.yaml`

It points to:

- `charts/platform-core`
- `overlays/base/platform-core-values.yaml`
