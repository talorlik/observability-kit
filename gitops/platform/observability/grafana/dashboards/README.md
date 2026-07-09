# Grafana Dashboards

This path stores Grafana dashboard JSON. Grafana itself is installed as
a mandatory baseline component by `gitops/apps/grafana-application.yaml`,
an ArgoCD Application that wraps the upstream Grafana Helm chart (pinned
`targetRevision`) with values from
`gitops/platform/observability/grafana/values/grafana-values.yaml`.

## How Dashboards Are Delivered

The chart values enable the Grafana dashboard sidecar. Dashboard JSON
placed here is packaged as ConfigMaps in the `observability` namespace
and must carry the discovery label the sidecar watches:

- Label `grafana_dashboard: "1"` on each dashboard ConfigMap.
- Optional annotation `grafana_folder` to place the dashboard in a
  Grafana folder; folder structure otherwise follows the file layout
  (`foldersFromFilesStructure: true`).
- The sidecar hot-loads matching ConfigMaps; no chart fork and no image
  rebuild is required.

## Conventions

- One JSON file per dashboard, exported via the Grafana share/export
  flow with `Export for sharing externally` enabled.
- Dashboards query OpenSearch (the platform's single telemetry store)
  through the `grafana-opensearch-datasource` plugin installed by the
  baseline values.
- Datasource and provider provisioning lives in the sibling
  `../provisioning/` directory, not here.
