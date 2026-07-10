# Third-Party Notices

This file is the attribution record required by
`contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml` (Batch 25,
TR-25). It lists every third-party system and dependency in the
license inventory with its SPDX license identifier and upstream
source. `scripts/ci/validate_release_engineering.sh` cross-checks this
file against the inventory; the two must never drift.

The product redistributes no upstream software. Wrapped systems are
consumed unmodified through Helm values, Kubernetes manifests, and CRD
instances; consumer clusters pull upstream charts and images directly
from their upstream sources. Product-distributed third-party content
is limited to the Python dependencies vendored into product-owned
artifacts (the `obskit-ai-runtime` image and optional extras of the
product Python packages).

## Wrapped and Referenced Systems

### opentelemetry-collector

- License: Apache-2.0
- Distribution mode: referenced-image
- Upstream source: [open-telemetry/opentelemetry-collector][otel]

### opensearch

- License: Apache-2.0
- Distribution mode: wrapped-chart
- Upstream source: [opensearch-project/OpenSearch][opensearch]

### opensearch-dashboards

- License: Apache-2.0
- Distribution mode: wrapped-chart
- Upstream source: [opensearch-project/OpenSearch-Dashboards][osd]

### grafana

- License: AGPL-3.0-only
- Distribution mode: wrapped-chart
- Upstream source: [grafana/grafana][grafana]

Grafana is deployed unmodified from the upstream chart and image. The
AGPL section 13 corresponding-source obligation for the deployed
version is satisfied by upstream's published source tree at the pinned
release tag. The product never patches or forks Grafana; any future
modification would trigger source-publication obligations and
requires legal review first, per the license compliance contract.

### neo4j

- License: GPL-3.0-only (Community edition); commercial (Enterprise
  edition)
- Distribution mode: referenced-image
- Upstream source: [neo4j/neo4j][neo4j]

The product references the unmodified upstream Neo4j image and
distributes no Neo4j code. Production multi-tenant deployments require
Neo4j Enterprise for the multi-database isolation floor set by the
tenant isolation matrix; the Enterprise license is customer-supplied
and never redistributed or embedded by the product. The disposable
evidence harness uses the upstream Enterprise evaluation license on
disposable clusters only.

### argocd

- License: Apache-2.0
- Distribution mode: wrapped-chart
- Upstream source: [argoproj/argo-cd][argocd]

### ingress-nginx

- License: Apache-2.0
- Distribution mode: wrapped-chart
- Upstream source: [kubernetes/ingress-nginx][ingress]

### external-secrets

- License: Apache-2.0
- Distribution mode: wrapped-chart
- Upstream source: [external-secrets/external-secrets][eso]

### postgresql

- License: PostgreSQL
- Distribution mode: referenced-image
- Upstream source: [PostgreSQL Global Development Group][postgres]

## Operator-Supplied Tooling

### terraform

- License: BUSL-1.1
- Distribution mode: operator-supplied-tool
- Upstream source: [hashicorp/terraform][terraform]

Terraform is operator-supplied tooling, never bundled or
redistributed by the product. Its Business Source License permits use
as a deployment tool for this platform; operators who cannot accept
BUSL terms can substitute OpenTofu (MPL-2.0).

## Product-Owned Dependencies

### fastapi

- License: MIT
- Distribution mode: vendored-code
- Upstream source: [fastapi/fastapi][fastapi]

### uvicorn

- License: BSD-3-Clause
- Distribution mode: vendored-code
- Upstream source: [encode/uvicorn][uvicorn]

### pg8000

- License: BSD-3-Clause
- Distribution mode: vendored-code
- Upstream source: [tlocke/pg8000][pg8000]

### pyyaml

- License: MIT
- Distribution mode: vendored-code
- Upstream source: [yaml/pyyaml][pyyaml]

### kubernetes-python-client

- License: Apache-2.0
- Distribution mode: vendored-code
- Upstream source: [kubernetes-client/python][k8sclient]

## Maintenance

Add, update, or remove entries here in the same change that updates
the license inventory in
`contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml`. A mismatch
between the two fails validation and blocks the release gate.

[otel]: https://github.com/open-telemetry/opentelemetry-collector
[opensearch]: https://github.com/opensearch-project/OpenSearch
[osd]: https://github.com/opensearch-project/OpenSearch-Dashboards
[grafana]: https://github.com/grafana/grafana
[neo4j]: https://github.com/neo4j/neo4j
[argocd]: https://github.com/argoproj/argo-cd
[ingress]: https://github.com/kubernetes/ingress-nginx
[eso]: https://github.com/external-secrets/external-secrets
[postgres]: https://www.postgresql.org/
[terraform]: https://github.com/hashicorp/terraform
[fastapi]: https://github.com/fastapi/fastapi
[uvicorn]: https://github.com/encode/uvicorn
[pg8000]: https://github.com/tlocke/pg8000
[pyyaml]: https://github.com/yaml/pyyaml
[k8sclient]: https://github.com/kubernetes-client/python
