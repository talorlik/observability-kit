# Product Documentation Runbook

Operator guide for maintaining the customer-facing documentation tree
under `docs/product/` (Batch 26, TR-26). Documentation is a release
artifact with the same gating discipline as code: every change is
validated structurally, and drift between docs and delivered behavior
fails CI.

## Scope

This runbook covers:

- How the `docs/product/` tree is organized and indexed.
- How to edit a product guide safely.
- How to regenerate the API reference from its governing contract.
- How to update the docs-coverage matrix when a capability ships.
- How to run the Batch 26 validators.
- How the GA readiness review is maintained.
- Rollback of a bad documentation change.

It does not cover the operator runbooks in `docs/runbooks/` or the
planning documents in `docs/auxiliary/planning/`; those are internal
engineering surfaces outside the product tree.

## Pre-checks

- You are at the repository root on a feature branch, never on `main`.
- The Python venv exists or can be created:

  ```bash
  bash scripts/ci/setup_python_env.sh
  ```

- `git status` is clean apart from the documentation change you are
  about to make, so validator failures are attributable.

## Procedure

### How the tree is organized

`docs/product/INDEX.md` is the single entry point. It maps every
document to one or more of the five audiences (evaluator, installer
and operator, tenant administrator, end user, commercial
administrator) and links every file in the tree. A document that is
not linked from `INDEX.md` fails validation, so adding a document
always means adding an index row too.

### Editing a guide safely

Product guides document delivered behavior only. Every statement must
derive from a contract under `contracts/`, a runtime under `tools/` or
`services/`, or committed evidence under `artifacts/evidence/`. Never
document planned or aspirational behavior; the guide would then drift
from the product and mislead customers.

When editing:

1. Keep file names `UPPERCASE_WITH_UNDERSCORES.md` and prose at 80
   columns.
2. Keep section headings stable. The docs-coverage matrix
   (`contracts/docs/DOCS_COVERAGE_MATRIX_V1.yaml`) references headings
   verbatim, so renaming a heading breaks the matrix check until the
   matrix is updated in the same commit.
3. Use relative links. The validator resolves every relative link and
   every in-tree anchor, so a moved file or renamed heading surfaces
   immediately.

### Regenerating the API reference

`docs/product/API_REFERENCE.md` is generated from
`contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml`. Never edit it by
hand; the generated-file marker plus the generator's `--check` mode
turn hand edits into a validation failure. To change the reference,
change the contract, then regenerate:

```bash
bash scripts/ci/setup_python_env.sh
.venv/bin/python scripts/dev/generate_api_reference.py
```

The generator requires PyYAML, which lives in the repo venv; running
it with the system interpreter fails on machines without PyYAML.
Commit the contract and the regenerated reference together.

### Updating the coverage matrix when a capability ships

`contracts/docs/DOCS_COVERAGE_MATRIX_V1.yaml` maps every Batch 17-25
capability to a product doc section. When a batch ships a new
customer-visible capability:

1. Document the capability in the appropriate guide under
   `docs/product/`.
2. Add a capability entry to the matrix under the owning batch: a
   unique `id`, a one-sentence `summary`, the `doc` path relative to
   the repository root (must be under `docs/product/`), and the
   `section` heading text exactly as it appears in the doc.
3. Run the validator (below). An unmapped batch, a dangling doc path,
   or a section heading that does not exist verbatim all fail.

### Running the validators

```bash
bash scripts/ci/validate_product_docs.sh
bash scripts/ci/validate_batch26_smoke.sh
```

The validator sources `scripts/ci/setup_python_env.sh` itself and runs
six numbered checks: required documents, INDEX audience map and tree
linkage, API reference marker and freshness, docs-coverage matrix,
link and anchor integrity, and GA readiness review structure. All
checks run to completion before the script fails, so one run reports
every problem.

### Maintaining the GA readiness review

`docs/product/GA_READINESS_REVIEW.md` walks the definition of done in
`docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md` as a checklist.
The validator enforces its structure:

- Every checklist item is a `- [x]` line; an unchecked `- [ ]` item
  fails validation. Items that cannot be checked stay out of the file
  until they can, with the gap tracked in the plan instead.
- Every item carries an evidence link on the same item: a markdown
  link or a repository path (wrapped continuation lines indented under
  the item count as part of it).
- A `Signed` section (any heading containing "Sign") closes the
  review with a named reviewer and a `YYYY-MM-DD` date.

Re-execute the review whenever the definition of done changes:
re-verify each item's evidence, update links, and re-sign with the new
date.

## Verification

After any documentation change:

```bash
bash scripts/ci/validate_product_docs.sh
bash scripts/ci/validate_markdown.sh
bash scripts/ci/validate_runbook_links.sh
```

All three must pass before the change merges. For a full regression
sweep, `bash scripts/ci/validate_all_batches_with_report.sh` includes
the Batch 26 smoke wrapper.

## Rollback

Documentation has no runtime surface: nothing deploys, renders, or
reconciles from `docs/product/`. Rollback is a plain Git revert of the
documentation commit, followed by the same verification commands
above. If the revert removes a capability's section while the
capability remains in the coverage matrix, revert the matching matrix
entry in the same commit so the validator stays green.
