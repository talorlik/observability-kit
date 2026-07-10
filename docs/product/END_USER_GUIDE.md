# End User Guide

This guide is for tenant end users of the Observability Kit platform:
engineers and analysts who explore logs, metrics, and traces, use
dashboards, respond to alerts, and review AI-assisted incident
analysis. Platform installation and tenant administration are covered
elsewhere; see the [index](INDEX.md) for the full documentation map.

## Table of Contents

- [Signing In](#signing-in)
- [The Portal](#the-portal)
- [The Wrapped UIs](#the-wrapped-uis)
- [Your Tenant Scope](#your-tenant-scope)
- [Dashboards](#dashboards)
- [Querying Logs, Metrics, and Traces](#querying-logs-metrics-and-traces)
- [Alerts](#alerts)
- [AI-Assisted Incident Analysis](#ai-assisted-incident-analysis)
- [Related Documents](#related-documents)

## Signing In

Access goes through your organization's single sign-on. The admin
access plane authenticates your session against the deployed identity
provider (OIDC by default, SAML via an adapter) and forwards your
identity to the portal; there are no separate platform passwords. Your
identity provider groups map to portal roles:

- `portal-readonly`: read-only access to every view within your
  scope. This is the typical end-user role.
- `portal-admin`: adds configuration editing and tenant lifecycle
  requests; intended for operators and tenant administrators.

Your deployment publishes the portal and UI endpoints; ask your
platform operator for the URLs used in your environment. Endpoints
are deployment-specific and never hardcoded in the product.

## The Portal

The management portal is the single pane over the platform. It is
server-rendered HTML and works without JavaScript. It serves four
views:

- Navigation (home): the catalog of wrapped UIs available in your
  deployment, with links to each. This is the recommended entry
  point.
- Tenants: tenant listing and detail (what you see is bounded by your
  scope; lifecycle actions require `portal-admin`).
- Health: a platform health summary built from the platform's own
  meta-monitoring signals.
- Config: the unified configuration editor (`portal-admin` only; all
  edits flow through Git, never directly into the cluster).

The same data is available as JSON under `/api/v1/...` routes for
machine consumption; the portal's contract fixes these paths. See the
[Management Portal Guide](../runbooks/MANAGEMENT_PORTAL_GUIDE.md) for
a walkthrough.

## The Wrapped UIs

The platform wraps best-of-breed UIs rather than replacing them. The
portal's navigation view lists exactly the UIs present in your
deployment, per the platform's UI catalog:

| UI | What it is for |
| ---- | ---- |
| OpenSearch Dashboards | Primary telemetry exploration surface: logs and (by default) traces, over the OpenSearch store. Your work happens inside your tenant's dashboard space. |
| Grafana | Metrics, plus the executive, SLO, and NOC views. Always present. Your tenant's content lives in a dedicated organization or folder. |
| Neo4j Browser | Dependency, blast-radius, and ownership queries over the derived service topology graph. Present only in graph-enabled deployments; sessions run against your tenant's own database. |
| Argo CD UI | GitOps delivery state (sync status, drift). An operator-facing surface; end users normally do not need it. |

All UIs are reached through the same SSO plane as the portal, so one
login covers the set.

## Your Tenant Scope

Everything you see is scoped to your tenant. Isolation is enforced in
the stores themselves, not just in the UI:

- Log, metric, and trace queries return only your tenant's documents.
- Your dashboard space, Grafana folder or organization, and graph
  database are per tenant.
- Cross-tenant access is denied by default and every denied attempt
  is audited. There is no setting that grants one tenant visibility
  into another.
- Telemetry writes are performed by the platform's collector
  pipelines, never by user accounts. You cannot (and do not need to)
  push documents into the stores directly.

If a query or dashboard unexpectedly returns nothing, confirm with
your tenant administrator that your user is mapped to the right
tenant roles, before suspecting data loss.

## Dashboards

Dashboards ship as code with the platform and are delivered into your
tenant's dashboard space; the saved objects, spaces, and alert
definitions live under `gitops/platform/search/dashboards/` in the
platform repository. Because dashboards are delivered by GitOps,
edits made ad hoc in the UI can be reconciled away; treat in-UI edits
as scratch work and ask your operator to promote anything you want to
keep into the dashboards-as-code tree.

Grafana carries the metric, SLO, executive, and NOC views; OpenSearch
Dashboards carries log and trace exploration views.

## Querying Logs, Metrics, and Traces

All telemetry is collected by OpenTelemetry and stored in OpenSearch,
so the query experience is uniform:

- Logs: query in OpenSearch Dashboards (Discover or saved searches)
  against your tenant's log indices.
- Traces: query in OpenSearch Dashboards; spans carry OpenTelemetry
  attributes, so you can pivot from a log line's trace id to the full
  trace.
- Metrics: query in Grafana against the metric indices.

Retention is set by your tenant's quotas (per signal: logs, metrics,
traces); data older than the retention window ages out. Your tenant
administrator owns quota and retention settings.

## Alerts

Alert rules are delivered as code alongside the dashboards (the
`alerts` definitions under `gitops/platform/search/dashboards/`) and
evaluate inside the telemetry store. Notification destinations are
configured by your platform operator. When an alert fires, start from
the dashboard the alert references, then pivot to logs and traces for
the affected service and time window.

## AI-Assisted Incident Analysis

Deployments with the AI runtime enabled add an analysis layer on top
of the same telemetry:

- Risk scoring and assisted root-cause analysis enrich incidents with
  ranked likely causes, built from the telemetry and the service
  topology graph.
- Findings are recorded in casefiles: structured incident records
  that accumulate evidence, hypotheses, and contradictions over the
  incident's life. Reviewing a casefile is the primary human surface;
  see the
  [Casefile Review Runbook](../runbooks/CASEFILE_REVIEW_RUNBOOK.md).
- The AI layer reads through governed, read-only tool paths. Any
  action beyond reading requires explicit human approval under the
  platform's approval flow, with timeouts and escalation; nothing
  destructive happens autonomously.

If your deployment does not include the AI runtime, none of these
surfaces appear; the rest of this guide is unaffected.

## Related Documents

- [Management Portal Guide](../runbooks/MANAGEMENT_PORTAL_GUIDE.md) -
  portal walkthrough.
- [Tenant Admin Guide](TENANT_ADMIN_GUIDE.md) - lifecycle, quotas, and
  isolation, for your tenant administrator.
- [Casefile Review Runbook](../runbooks/CASEFILE_REVIEW_RUNBOOK.md) -
  reviewing AI-assisted incident analysis.
- [Getting Started](GETTING_STARTED.md) - what the product is and how
  a platform gets stood up.
