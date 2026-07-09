# ADR-0001: Discovery and Preflight Executor Architecture

**Status:** Accepted
**Date:** 2026-07-09
**Deciders:** Platform engineering (Batch 17 owner)
**Markers:** TB-17, TR-04, TR-05, TR-18

## Context

Batches 2 and 3 contracted the compatibility model, preflight checks,
and discovery probes: schemas, samples, grading rules, the mode
decision table, and the remediation catalog all exist and are validated
offline in CI. Nothing executes them against a live cluster. Batch 17
delivers that runtime, and Batch 18 (guided installer) composes it, so
the executor's boundaries must be fixed before any code lands.

Forces shaping the decision:

- CI stays offline and fixture-driven: `requirements-ci.txt` is
  lint-only by policy and must never grow runtime dependencies.
- The executor observes only: no cluster mutation, no reading of
  secret values, no provider-specific dependency in the core.
- Outputs must be deterministic - identical cluster state and contract
  inputs produce byte-identical reports - because Batch 18 replays
  them and Batch 23 diffs captured evidence against them.
- Grading, mode recommendation, and remediation must derive solely
  from the Batch 2 contract files, never from logic hardcoded in the
  executor.
- The CLI mode and the optional in-cluster Job mode must share one
  code path and produce interchangeable reports.

## Decision

Build the executor as a Python 3.11+ package named `obskit` under
`tools/obskit/`, with these fixed boundaries:

- Own dependency manifest: `tools/obskit/pyproject.toml` plus pinned
  `tools/obskit/requirements.txt`. Nothing is ever added to
  `requirements-ci.txt`.
- Standard-library-only core: collection, evaluation, grading, and
  report emission import only the Python standard library. The
  Kubernetes client is an optional extra (`obskit[k8s]`, pinned)
  imported lazily and only by the live-cluster reader. CI therefore
  tests the full engine offline with no pip install.
- Two input backends behind one `ClusterReader` interface: a live
  read-only Kubernetes API reader and a fixture reader that loads
  recorded cluster snapshots. Fixtures drive CI; live mode drives real
  runs. Both feed the identical evaluation path.
- Type hints are mandatory throughout; structured data uses frozen
  dataclasses, not dicts.
- CLI entry point `obskit` (subcommands `preflight`, `discover`,
  `evaluate`) built on stdlib `argparse`. The optional in-cluster Job
  mode runs the same CLI in a container with a mounted kubeconfig or
  in-cluster service account - one code path, interchangeable reports.
- A bundled RBAC manifest grants exactly `get`, `list`, and `watch`,
  and grants no Secret access at all: secret integrations are
  detected via their CRDs and workloads, so Secret values are
  structurally unreadable rather than merely unread.
- Determinism rules: stable sort order for every collection, JSON
  emitted with sorted keys and fixed separators, and no
  environment-dependent values outside the report `metadata` block.
- Grading, mode recommendation, and remediation load
  `contracts/compatibility/GRADING_RULES.json`,
  `MODE_DECISION_TABLE.json`, and `REMEDIATION_CATALOG.json` at
  runtime; the executor contains no grading constants of its own.

`contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml` captures
the same boundaries machine-readably and is enforced by
`scripts/ci/validate_discovery_executor.sh`.

## Options Considered

### Option A: Extend the Bash Validator Pattern

| Dimension | Assessment |
| ---- | ---- |
| Complexity | Low to start, high at scale |
| Cost | No new toolchain |
| Scalability | Poor - live API paging, retries, typed reports |
| Team familiarity | High |

**Pros:** Reuses the existing `scripts/ci/` idiom; zero packaging.
**Cons:** Bash cannot express typed, deterministic report generation
or a reusable library surface for the Batch 18 installer; kubectl
shelling makes read-only guarantees and fixture injection fragile.

### Option B: Go Binary

| Dimension | Assessment |
| ---- | ---- |
| Complexity | Medium |
| Cost | New toolchain in a repo with no Go today |
| Scalability | Excellent |
| Team familiarity | Medium |

**Pros:** Single static binary; first-class client-go.
**Cons:** Introduces a second runtime ecosystem for one tool; CI has
no Go toolchain; contract fixtures and validators are already
Python-idiomatic; slower iteration for a contract-driven engine.

### Option C: Python 3.11+ Package Under tools/obskit/ (Chosen)

| Dimension | Assessment |
| ---- | ---- |
| Complexity | Medium |
| Cost | Python 3.11+ present on dev and CI hosts |
| Scalability | Good - library plus CLI plus Job image |
| Team familiarity | High - repo tests are already python3 |

**Pros:** Matches the repo's existing Python validation idiom; stdlib
core keeps CI offline; dataclasses give typed contracts; the same
package later hosts the Batch 18 installer and Batch 19 renderer per
TR-19 and TR-20.
**Cons:** Needs its own dependency manifest and packaging discipline;
live mode requires an optional client dependency.

## Trade-Off Analysis

Option C is the only option that satisfies all three hard constraints
at once: offline lint-only CI (stdlib core, no `requirements-ci.txt`
growth), a reusable library surface for Batches 18-20 (TR-19 and
TR-20 mandate the same `tools/obskit/` home), and fixture-driven
determinism (dataclass models serialize identically regardless of
where they were collected). Option A fails the library-surface and
determinism constraints; Option B fails the toolchain-cost constraint
without buying anything the executor needs at this scale.

## Consequences

- Easier: Batch 18 composes `obskit` as a library instead of shelling
  out; Batch 23 captures live evidence with the same reports CI
  validates; fixture snapshots make regressions reproducible.
- Harder: two dependency surfaces (core vs `[k8s]` extra) must stay
  disciplined; the lazy import boundary needs a test guarding against
  accidental hard dependencies.
- Revisit: if the in-cluster Job mode grows scheduling or aggregation
  needs beyond one-shot runs, promote it to its own ADR; the pinned
  Kubernetes client version is re-pinned by the Batch 25 release
  process.

## Action Items

1. [x] Record boundaries in
   `contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml`.
2. [x] Implement `obskit preflight` and `obskit discover` against the
   Batch 3 schemas (Batch 17 Tasks 2-3).
3. [x] Implement `obskit evaluate` over the Batch 2 contract files
   (Batch 17 Task 4).
4. [x] Wire the offline fixture harness and validators into CI
   (Batch 17 Task 5).
