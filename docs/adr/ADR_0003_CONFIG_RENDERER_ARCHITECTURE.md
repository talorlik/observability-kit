# ADR-0003: Configuration Renderer Architecture

**Status:** Accepted
**Date:** 2026-07-09
**Deciders:** Platform engineering (Batch 19 owner)
**Markers:** TB-19, TR-10, TR-17, TR-20

## Context

Batch 16 fixed the propagation and reconciliation contract
(`contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`):
every persistent configuration change travels render, commit,
reconcile, verify, with continuous drift detection, and the unified
configuration document
(`contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json`) is the single
place operators change platform configuration. Nothing executes that
contract yet: there is no renderer, so a unified config edit cannot
reach a native config without hand-assembly, which the contract itself
classifies as drift. Batch 19 delivers the rendering runtime.

Forces shaping the decision:

- Rendering must be deterministic (byte-identical for identical
  document bytes) and idempotent (re-rendering an unchanged document
  produces no diff and no commit), because determinism is what makes
  drift detection and Git-revert rollback sound.
- Output is GitOps-only: rendered files land at each binding's
  `render_target` repository path; live endpoints and mutable API
  writes are forbidden (`TR-17`, `TR-10`).
- Every rendered file carries the generated-file header marker; for
  formats that cannot carry comments, the marker lives in a sibling
  manifest listing rendered artifacts and content digests (per the
  propagation contract's `header_marker_notes`).
- Every propagation commit carries the `Unified-Config-Schema-Version`
  and `Unified-Config-Document-Digest` trailers.
- Rollback is a re-render from a prior unified document revision
  through the same pipeline, never a separate apply channel, exercised
  via the mode-parameterized `scripts/ops` drill conventions with
  `dry-run` as the default mode.
- CI validation is offline and fixture-driven: no live cluster, no Git
  remote, no PyPI, `requirements-ci.txt` stays lint-only (`TR-20`).
- The renderer never forks or patches a wrapped system; it writes
  only under registered `config_surface` paths and never under
  `gitops/charts/` (the propagation contract's read-only path).

## Decision

Build the renderer as the `obskit.configrender` subpackage of the
existing `tools/obskit/` package, exposed as the `obskit render`,
`obskit drift`, and `obskit rollback` subcommands, with these fixed
boundaries:

- Same runtime posture as ADR-0001 and ADR-0002: typed Python 3.11+,
  frozen dataclasses for structured data, standard-library-only core,
  its own dependency manifest (`tools/obskit/pyproject.toml`), never
  added to `requirements-ci.txt`.
- The unified document is consumed as JSON. JSON is the native,
  dependency-free interchange form (ADR-0002 precedent: the stdlib
  cannot parse YAML). The canonical YAML sample
  (`contracts/management/samples/VALID_UNIFIED_CONFIG.yaml`) gains a
  byte-stable JSON twin
  (`contracts/management/samples/VALID_UNIFIED_CONFIG.json`) that is
  the renderer's reference fixture; the twins are kept semantically
  identical by the Batch 19 validator.
- Document validation reuses and extends the hand-rolled JSON-Schema
  subset validator from `obskit.install.contract` (adding `$ref` /
  `$defs`, `const`, `minimum` / `maximum`, `minItems`,
  `minProperties`, `items`) rather than re-rolling one. The three
  cross-file rules the schema cannot express are renderer-enforced
  before any file is written: every binding's `system` is registered
  in `WRAPPED_SYSTEM_REGISTRY_V1.yaml`, every present config leaf key
  has at least one binding, every binding resolves to a present leaf
  key, and every binding's `repo_path` falls under a registered
  `config_surface` path. Registry facts (system ids, config-surface
  paths) are extracted with the line-based, stdlib-only YAML technique
  established by `obskit.install.flow.load_contract_step_ids`.
- Rendering is target-preserving patching, not whole-file templating:
  - `json-path-patch`: JSON targets (ILM policies) are parsed with the
    stdlib, the locator path is set, and the file is re-emitted
    canonically (sorted keys, two-space indent, trailing newline).
  - `yaml-line-patch`: YAML targets (Helm values files, Application
    specs) are patched line-based - indentation-aware scalar
    replacement at the locator's dotted path, with block insertion or
    removal only for contract-fixed blocks (for example
    `spec.syncPolicy.automated`). All other bytes, including comments,
    are preserved. This avoids duplicating native files as templates
    (dual maintenance the contract exists to prevent) and avoids a
    full YAML parser in a zero-dependency package.
  - `owned-artifact`: directory targets (alert-rule bundles,
    saved-object bundles, security defaults) receive a renderer-owned
    deterministic artifact derived from the unified value; existing
    hand-authored files in those directories are recorded by digest in
    the render manifest, never rewritten by v1.
  - `presence-gated`: manifests documented as "rendered only when
    enabled" (graph module, browser access) render only when their
    gate key is true; when false the manifest records the skip.
  The strategy for every (unified key, system) binding pair is fixed
  machine-readably in
  `contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml`; a
  binding without a cataloged strategy fails the render.
- Every render emits `gitops/UNIFIED_CONFIG_RENDER_MANIFEST.json`
  under the render root: schema version, document digest (SHA-256 of
  the document bytes), and every rendered or recorded artifact with
  its content digest. The manifest is the sibling marker carrier for
  comment-carrying-incapable formats and the input surface for drift
  detection.
- `obskit render` writes files under `--repo-root` (default: the
  current working tree) and emits a prepared commit message
  (`--commit-message-out`) carrying the two required trailers. The
  renderer itself never runs Git commands: the commit is the
  operator's (or pipeline's) act, which keeps the runtime pure and
  offline-testable. `--check` renders to an in-memory plan and exits
  non-zero if any target would change - the render-idempotency check.
- `obskit drift` compares expected rendered bytes against a target
  tree (live-exported or checked-out) and emits the
  rendered-versus-live diff surface as JSON, using the propagation
  contract's alert signal names (`config-drift-detected-per-system`,
  `render-idempotency-violation`) for the `TR-12` alert path.
- `obskit rollback` re-renders from a prior unified document revision
  (a document file retrieved from Git history) through the identical
  render-and-commit pipeline. The operational drill wrapper
  `scripts/ops/run_config_rollback_drill.sh` is mode-parameterized
  (`dry-run` default, `real` opt-in) following
  `scripts/ops/run_rollback_drill.sh` conventions.

## Options Considered

### Option A: Whole-File Template Ownership

Duplicate every render target as a template inside the renderer (the
ADR-0002 install-render approach) and emit complete files. Rejected:
the install renderer owns files that exist only as its outputs, but
Batch 19's targets are pre-existing native configs maintained by their
owning batches; templating them creates dual maintenance and silent
fork risk - exactly the drift the propagation contract forbids.

### Option B: PyYAML-Based Structural Rewrite

Parse and re-emit YAML targets with PyYAML as a new runtime
dependency. Rejected: breaks the package's zero-dependency contract
(ADR-0001), destroys comments and formatting on every adopted file,
and makes first-render diffs maximal. The line-based patch technique
is already proven in this package and in the `scripts/ci` validators.

### Option C: obskit.configrender Subpackage With Target-Preserving Patching (Chosen)

One package, one CLI, one determinism regime; bounded line-based
patching for YAML, stdlib parsing for JSON, owned artifacts for
directory surfaces; strategies cataloged in a machine-readable
contract. The smallest change that satisfies `TR-20`.

## Trade-Off Analysis

Line-based YAML patching handles a bounded structural subset (plain
block mappings, fixed insertable blocks); it fails loudly on
structures it does not understand rather than guessing. Concretely it
replaces plain scalars only: block and folded scalars, flow
collections, anchors and aliases, and quoted values that could hide a
comment character are rejected loudly, never rewritten. That bound is
acceptable because every YAML target is a small, repo-owned values
file whose shape the fixtures pin, and failing loudly is the contract
posture (a render that cannot prove its output is discarded, never
committed). JSON targets are canonically re-emitted, so the first
adoption render may reformat a hand-authored JSON file once; after
adoption the renderer is the only writer and output is stable.
Consuming the document as JSON pushes YAML-to-JSON conversion to the
operator surface (portal, installer, or `python -c` with PyYAML
outside the package), which is the same trade ADR-0002 accepted for
answers files.

## Consequences

- `obskit render` is the only writer of render targets from Batch 19
  on; hand edits to rendered files are drift by contract.
- Batch 20 (tenant control plane) and Batch 21 (portal) call this
  renderer as a library or CLI; they must not re-implement rendering.
- Batch 23 captures live evidence by running this exact CLI against
  the harness cluster's Git checkout.
- The repository's own `gitops/` tree is not adopted (re-rendered and
  committed) by Batch 19: adoption happens when the first canonical
  unified document for a platform instance is committed (installer or
  portal flow), so v1 proves rendering on fixtures without churning
  hand-authored native files that earlier batches own.
- The JSON-Schema subset validator grows keywords here; it still
  fails loudly on keywords it does not implement.

## Action Items

- Publish `contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml`
  (this batch, Task 1).
- Implement `obskit.configrender` and the three subcommands (Tasks
  2-4).
- Gate with `scripts/ci/validate_config_renderer.sh`, the idempotency
  and drift fixtures, and the Batch 19 smoke wrapper (Task 5).
- Extend `docs/runbooks/UNIFIED_CONFIGURATION_RUNBOOK.md` to
  executable renderer steps (Task 6).
