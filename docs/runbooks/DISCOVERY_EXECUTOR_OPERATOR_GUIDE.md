# Discovery Executor Operator Guide

This guide covers operating the Batch 17 (`TB-17`) discovery and
preflight execution engine `obskit` for `TR-04`, `TR-05`, and `TR-18`:
CLI and in-cluster runs, RBAC setup, report interpretation, and
remediation follow-up.

Section layout deviates from the standard Scope/Pre-checks/Procedure/
Verification shape deliberately: the executor is a tool operators run
repeatedly in different modes, not a one-shot procedure, so sections
are organized by mode of use instead.

The executor is read-only by design. It never mutates cluster state,
never reads Secret values, and grades exclusively through the
`contracts/compatibility/` files. Boundaries are contracted in
`contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml` and
decided in `docs/adr/ADR_0001_DISCOVERY_EXECUTOR_ARCHITECTURE.md`.

## Installation

The package lives under `tools/obskit/` with its own dependency
manifest. The core is standard-library-only; live-cluster runs need
the `k8s` extra:

```bash
python3 -m pip install "./tools/obskit"        # fixture mode only
python3 -m pip install "./tools/obskit[k8s]"   # plus live mode
```

Uninstalled checkouts work too: run `python3 -m obskit.cli` (or
`python3 -m obskit`) from `tools/obskit` with `PYTHONPATH=.`.

## CLI Runs

Three subcommands, one pipeline:

```bash
obskit preflight --live --context <ctx> --output preflight.json
obskit discover  --live --context <ctx> --output discovery.json
obskit evaluate \
  --preflight preflight.json \
  --discovery discovery.json \
  --contracts-dir contracts \
  --profiles profiles.json \
  --output-dir eval/
```

Fixture mode swaps `--live` for `--snapshot <file>` (snapshot format
is documented in `tools/obskit/obskit/reader.py`). `--profiles`
supplies the profiles discovery cannot observe (`object_storage`,
`identity`); omitting them yields a contracted
`missing_required_profile` blocked grade, not an error.

Exit codes: `preflight` exits non-zero exactly when a blocking check
fails (`summary.outcome` is `fail`); warn-only runs exit 0. `discover`
and `evaluate` exit non-zero only on execution errors - a `blocked`
grade still exits 0.

## In-Cluster Job Mode and RBAC Setup

The optional Job mode runs the same CLI in-cluster - one code path,
interchangeable reports. Apply the bundled read-only RBAC first:

```bash
kubectl apply -f tools/obskit/rbac/obskit-readonly-rbac.yaml
```

This creates the `obskit-system` namespace, the `obskit`
ServiceAccount, and a ClusterRole limited to `get`, `list`, and
`watch` with no Secret access at all - secret integrations are
detected via their CRDs and workloads. Run the Job with
`serviceAccountName: obskit`; in-cluster credentials are picked up
automatically when no kubeconfig is present.

> [!WARNING]
> Never grant the executor write verbs or Secret access. The
> `required_permissions` preflight check uses
> SelfSubjectAccessReview, which the default `system:basic-user`
> binding already permits.

## Report Interpretation

Preflight (`contracts/discovery/PREFLIGHT_REPORT_SCHEMA.json`): six
contracted check classes in stable order - `cluster_connectivity`,
`required_permissions`, `required_api_readiness`,
`required_crd_readiness`, `storage_compatibility`,
`gitops_prerequisites`. Statuses are `pass`, `warn` (non-blocking,
e.g. `default_storage_class_missing`), `fail` (blocking, carries a
`reason_code`), or `skip` (e.g. everything after a connectivity
failure). `summary.outcome` is the roll-up.

Discovery (`contracts/discovery/DISCOVERY_PROBES_SCHEMA.json`): three
probe groups - `storage_and_ingress`, `gitops_and_secrets`, and
`workload_inventory` with onboardable-candidate flags.

Evaluate writes four artifacts into `--output-dir`:
`capability_matrix.json` (candidates and defaults per profile family),
`compatibility_result.json` (grade `supported`, `conditional`, or
`blocked`, with reasons), `mode_recommendation.json` (resolved via
`contracts/compatibility/MODE_DECISION_TABLE.json`), and
`remediation_list.json`. Identical inputs produce byte-identical
outputs; reports carry no timestamps.

## Remediation Follow-Up

Every grading reason maps to actions in
`contracts/compatibility/REMEDIATION_CATALOG.json`, echoed in
`remediation_list.json`. Work the list, then re-run the full pipeline;
grades must only improve through cluster or profile changes, never by
editing reports. A reason with no catalog entry is a contract bug -
fix the catalog, not the executor.

## Validation

```bash
bash scripts/ci/validate_discovery_executor.sh   # offline, CI-gated
bash scripts/ci/validate_batch17_smoke.sh        # batch smoke wrapper
```

The live integration probe is never CI-gated (`TR-18`) and refuses
any context not starting with `kind-`:

```bash
KUBECONFIG=<isolated-kubeconfig> \
  bash scripts/validate/discovery_executor_kind_integration.sh \
  --context kind-<name>
```

## Failure Handling

- Preflight fails on `required_crd_readiness` with
  `gateway_api_crds_required`: install the Gateway API CRDs or switch
  the ingress profile, then re-run.
- Evaluate exits 1 naming `blocked_conditions`: the grading contract
  and the executor's blocked-code bindings have drifted - reconcile
  `contracts/compatibility/GRADING_RULES.json` with
  `tools/obskit/obskit/evaluate.py` in the same change.
- Live mode raises about a missing client: install the `[k8s]` extra
  per Installation above.
- Reports differ between runs against identical fixtures: that is a
  determinism regression; run
  `python3 tests/executor/test_determinism_and_boundaries.py` and fix
  before shipping.
