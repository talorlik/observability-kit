# ADR-0002: Guided Install Flow Architecture

**Status:** Accepted
**Date:** 2026-07-09
**Deciders:** Platform engineering (Batch 18 owner)
**Markers:** TB-18, TR-05, TR-14, TR-19

## Context

Batch 17 delivered the discovery and preflight execution engine
(`tools/obskit/`, ADR-0001): read-only, stdlib-only, contract-driven,
deterministic. Installation, however, is still hand-assembled - an
operator must run preflight, grade compatibility, pick a mode, write an
install contract, render an overlay, and bootstrap Argo CD by hand,
which `TR-19` explicitly forbids for the product. Batch 18 delivers the
guided installer that chains those stages into one contracted flow,
interactive or fully unattended.

Forces shaping the decision:

- The flow order must be contract-fixed and machine-checkable, not
  convention: preflight, grading, mode recommendation, install contract
  capture, render, Argo CD bootstrap, post-install readiness (`TR-19`).
- Captured answers must validate against
  `contracts/install/INSTALL_CONTRACT_SCHEMA.json` and fail the run
  before any render or bootstrap step executes.
- Non-interactive mode needs full parity: an answers file drives
  exactly the flow the wizard drives, and every interactive run must be
  reproducible from its recorded answers.
- Installation must be idempotent and resumable: re-running a completed
  install changes nothing; a failed run resumes from the last completed
  step.
- Rendering is GitOps-only per
  `contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`:
  the installer emits overlay and bootstrap manifests and performs no
  direct mutable API writes for persistent configuration.
- The installer never forks or patches wrapped open-source systems and
  carries no provider-specific dependency in its core (`TR-03`).
- CI stays offline: no live cluster, no PyPI, `requirements-ci.txt`
  lint-only.

## Decision

Build the installer as the `obskit.install` subpackage of the existing
`tools/obskit/` package, exposed as the `obskit install` subcommand,
with these fixed boundaries:

- Same runtime posture as ADR-0001: typed Python 3.11+, frozen
  dataclasses for structured data, standard-library-only core, no
  additions to `requirements-ci.txt`. The installer composes the
  Batch 17 executor modules (`preflight`, `discovery`, `evaluate`) as
  library calls - one engine, one code path, no re-implementation.
- The flow is a sequence of seven contracted steps fixed by
  `contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml`:
  `preflight`, `grading`, `mode-recommendation`, `contract-capture`,
  `render`, `argocd-bootstrap`, `post-install-readiness`. Step order is
  loaded from the contract at runtime and asserted against the
  implementation, so order drift fails loudly.
- Module layout under `tools/obskit/obskit/install/`:
  - `models.py` - frozen dataclasses shared by all steps
    (`InstallAnswers`, `StepResult`, `InstallState`, `RenderResult`).
  - `contract.py` - answers loading, interactive capture, and a
    stdlib validator for the exact JSON-Schema subset
    `INSTALL_CONTRACT_SCHEMA.json` uses (`type`, `required`,
    `properties`, `additionalProperties`, `enum`, `pattern`,
    `minLength`, `allOf`/`if`/`then`).
  - `wizard.py` - the interactive prompt loop; every prompt has a
    non-interactive equivalent key, and the wizard records its
    captured answers to `answers.json` so any interactive run is
    replayable with `--answers`.
  - `render.py` - deterministic emission of the environment overlay
    and the Argo CD bootstrap manifests from a validated contract.
  - `finalize.py` - post-install readiness invocation and install
    summary emission.
  - `flow.py` - the step engine: state journal, resume, halt
    conditions, and step dispatch.
- Answers are JSON (`--answers <file>`): the schema is JSON Schema and
  the core is stdlib-only, so JSON is the native, dependency-free
  interchange form. The YAML example
  (`contracts/install/INSTALL_CONTRACT.example.yaml`) remains the
  human-readable reference; the installer emits the captured contract
  as `install_contract.json`.
- State journal: `<output-dir>/install_state.json` records, per step,
  status and the SHA-256 digests of the step's inputs (answers bytes,
  snapshot bytes). A step is skipped when it is recorded complete, its
  outputs exist, and its input digests match - which yields both
  idempotency (completed install re-runs as all-skips, exit 0, no file
  changes) and resume (first incomplete or drifted step re-executes).
- Rendering writes files only, under `<output-dir>/rendered/`:
  `overlays/<environment>/platform-core-values.yaml` plus Argo CD
  bootstrap manifests (`bootstrap/argocd/kustomization.yaml`,
  `bootstrap/argocd/platform-core-application.yaml`). Every rendered
  file carries a generated-file header marker naming the guided
  installer, mirroring the propagation contract's marker convention. YAML is emitted from fixed templates with deterministic
  substitution - the stdlib cannot parse YAML, but writing it from
  templates keeps renders byte-identical without a dependency.
- The `argocd-bootstrap` step emits and verifies bootstrap manifests
  and prints the operator apply instruction; it never calls the
  cluster API. Live application of the bootstrap is the operator's
  (and Batch 23's) act, keeping the installer inside the GitOps-only
  boundary.
- The `post-install-readiness` step invokes
  `scripts/validate/post_install_readiness.sh` via subprocess and
  emits `install_summary.json` plus a human-readable summary with
  next steps; a failed readiness check makes the installer exit
  non-zero.
- Determinism follows ADR-0001: JSON via `obskit.emit.write_report`
  (sorted keys, fixed separators, trailing newline), stable ordering
  everywhere, no environment-dependent values outside `metadata`
  blocks. The state journal is the one deliberately mutable artifact
  and is excluded from determinism claims.

## Options Considered

### Option A: Standalone Installer Script (Bash)

Extend the `scripts/` bash-validator pattern into an installer.
Rejected: the flow needs structured state (journal, digests, schema
validation, prompts) that bash handles poorly; Batch 17 already proved
the typed-Python pattern; `TR-19` demands resumability that would turn
bash into an ad-hoc state machine.

### Option B: New Top-Level Installer Package

A separate `tools/installer/` package. Rejected: the installer's first
three steps are the Batch 17 executor; a second package would duplicate
the reader/emit/contract plumbing, double the dependency surface, and
split the CLI (`obskit` plus `installer`) for no gain. TASKS.md places
the installer in `tools/obskit/`.

### Option C: obskit.install Subpackage (Chosen)

One package, one CLI, one determinism regime. The installer composes
executor modules as library calls, inherits the stdlib-only posture,
and adds exactly one subcommand. This is the smallest change that
satisfies `TR-19`.

## Trade-Off Analysis

Option C couples installer releases to executor releases - acceptable,
since `TR-19` defines the installer as the executor's composition and
they version together through the same `pyproject.toml`. The
stdlib-only constraint forces a hand-rolled JSON-Schema subset
validator and template-based YAML emission; both are bounded (the
schema uses a small, fixed keyword set; rendered YAML is fully
determined by the contract) and both are cheaper than importing
`jsonschema` and `PyYAML` into a package whose contract is zero
runtime dependencies.

## Consequences

- `obskit install` is the only supported install path from Batch 18
  on; hand-assembled installs invalidate evidence (`TR-24`).
- Batch 19's configuration renderer can reuse the render conventions
  (header marker, deterministic emission) established here.
- Batch 23's live harness drives this exact CLI; anything the harness
  needs that the flow contract does not define must land as a contract
  change first.
- The JSON-Schema subset validator must grow if
  `INSTALL_CONTRACT_SCHEMA.json` ever adopts new keywords; the
  validator fails loudly on keywords it does not implement, so schema
  drift is caught in CI rather than silently ignored.

## Action Items

- Fix the step order in
  `contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml` (this batch,
  Task 1).
- Implement the wizard, render, and finalization steps (Tasks 2-4).
- Gate with `scripts/ci/validate_guided_installer.sh`, seeded
  invalid-answers rejections, and the Batch 18 smoke wrapper (Task 5).
- Publish `docs/runbooks/GUIDED_INSTALLATION_GUIDE.md` (Task 6).
