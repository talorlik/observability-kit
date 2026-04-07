# Visualization Admin Access Plane Guide

This guide defines Batch 9A implementation and validation scope.

## Scope

- signal-to-UI ownership contract publication
- Grafana mandatory-core baseline posture
- OpenSearch Dashboards and Grafana provisioning paths as code
- admin access profile contract for ingress or gateway, TLS, and authn
- admin GUI endpoint reachability and login smoke checks

## Artifacts

- `contracts/visualization/SIGNAL_UI_OWNERSHIP.yaml`
- `contracts/visualization/UI_PROVISIONING_CONTRACT.json`
- `contracts/visualization/ADMIN_GUI_TLS_LOGIN_SMOKE_VALIDATION.json`
- `install/profiles/admin-access/PROFILE.schema.json`
- `contracts/install/ADMIN_GUI_READINESS.schema.json`

## Validation Entry Points

```bash
bash scripts/ci/validate_visualization_admin_access.sh
```

```bash
bash scripts/ci/validate_batch9a_smoke.sh
```

## Expected Outcomes

- signal ownership contract includes logs, metrics, traces, topology, and
  executive views
- Grafana is marked mandatory core in ownership controls
- core UI provisioning paths exist for OpenSearch Dashboards and Grafana
- admin access profile schema validates ingress and gateway mode inputs
- smoke validation reports TLS and login pass for enabled admin UIs
