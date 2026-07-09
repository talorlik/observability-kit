# Grafana Provisioning

This path stores Grafana provisioning configs for datasources and
dashboard providers. Grafana itself is installed as a mandatory baseline
component by `gitops/apps/grafana-application.yaml`, an ArgoCD
Application that wraps the upstream Grafana Helm chart (pinned
`targetRevision`) with values from
`gitops/platform/observability/grafana/values/grafana-values.yaml`.
There is no optional enable flag - `grafana_mandatory_core: true` in
`contracts/visualization/SIGNAL_UI_OWNERSHIP.yaml` makes it baseline.

## How Provisioning Configs Are Delivered

The chart values enable the Grafana datasource sidecar. Provisioning
sources placed here are packaged as ConfigMaps in the `observability`
namespace and must carry the discovery label the sidecar watches:

- Label `grafana_datasource: "1"` on each datasource ConfigMap.
- The sidecar hot-loads matching ConfigMaps; no chart fork and no image
  rebuild is required.

The primary datasource is OpenSearch (the platform's single telemetry
store), served through the `grafana-opensearch-datasource` plugin that
the baseline values install. Endpoint URLs are environment-specific and
belong in per-environment provisioning sources, not in the baseline
values file.

## Conventions

- One YAML file per datasource or provider definition.
- No credentials in files here; reference Kubernetes Secrets provisioned
  via the secrets adapter (`adapters/secrets/`).
- Dashboard JSON lives in the sibling `../dashboards/` directory, not
  here.
