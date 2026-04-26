# Contracts Naming Convention

This document captures the file-naming conventions used across `contracts/`
and `install/profiles/`. The two directories use **different conventions on
purpose**; neither is a bug. New contributors should follow the convention
of the directory they are adding to.

## Convention 1 — `contracts/`

Schemas, validation artifacts, and contract YAML files in `contracts/` use
`UPPERCASE_SNAKE_CASE`, with an explicit version suffix where versioning
applies.

| Pattern                     | Example                                           |
| --------------------------- | ------------------------------------------------- |
| `*_SCHEMA.json`             | `contracts/onboarding/ONBOARDING_SCHEMA.json`     |
| `*_SCHEMA_V<N>.json`        | `contracts/policy/POLICY_DECISION_SCHEMA_V1.json` |
| `*_VALIDATION.json`         | `contracts/onboarding/CI_SCHEMA_VALIDATION.json`  |
| `*_V<N>.yaml`               | `contracts/policy/APPROVAL_FLOW_V1.yaml`          |
| `*_V<N>.json`               | `contracts/ai/AGENT_ENVELOPE_V1.json`             |

Why: `contracts/` is the source of truth for batch correctness. Loud,
versioned filenames make drift visible and grep-friendly across batches.

## Convention 2 — `install/profiles/`

Schemas under `install/profiles/` use the lowercase, dotted
`<title>.schema.json` form that matches JSON Schema's own self-referencing
style (`$id`).

| Pattern              | Example                                                   |
| -------------------- | --------------------------------------------------------- |
| `*.schema.json`      | `install/profiles/cluster/PROFILE.schema.json`            |
| `<topic>.schema.json` | `install/profiles/compatibility/COMPATIBILITY_RULES.schema.json` |

Why: install profiles are consumed by JSON Schema tooling that prefers the
dotted form. Keeping these schemas isomorphic with their `$id` simplifies
external consumption.

## The Three Intentional Aliases

`contracts/install/` is the one place where both conventions coexist by
design:

| Canonical                                            | Alias (for consumers expecting `.schema.json`)        |
| ---------------------------------------------------- | ----------------------------------------------------- |
| `contracts/install/INSTALL_CONTRACT_SCHEMA.json`     | `contracts/install/INSTALL_CONTRACT.schema.json`      |
| `contracts/install/ADMIN_GUI_READINESS.schema.json`  | (canonical — no alias)                                |
| `contracts/install/POST_INSTALL_READINESS.schema.json` | (canonical — no alias)                              |

Where an alias exists, it is a thin wrapper using `$schema` + `allOf`
referencing the canonical `_SCHEMA.json` (see
`INSTALL_CONTRACT.schema.json`). The alias exists so that any tooling that
expects the dotted form can resolve a valid JSON Schema document; the
authoritative content lives only in the `_SCHEMA.json` file.

## Adding new schemas

- Adding a schema under `contracts/` → use `*_SCHEMA[_V<N>].json` or
  `*_VALIDATION.json` (UPPERCASE_SNAKE_CASE).
- Adding a schema under `install/profiles/` → use `<title>.schema.json`
  (dotted, lowercase).
- Bridging consumers that expect the dotted form for a `_SCHEMA.json`
  file → add a thin alias next to the canonical (as
  `INSTALL_CONTRACT.schema.json` does).

Do **not** rename existing schemas. Validators, CI scripts, and runbooks
reference these paths by name; renames are a breaking change.
