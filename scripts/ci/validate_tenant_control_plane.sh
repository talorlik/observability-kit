#!/usr/bin/env bash
#
# Batch 20 validator: tenant control plane service (tenantctl).
#
# Repository-only and offline (TR-20 composed with TR-18: CI
# validation is fixture-driven; nothing here touches a live cluster,
# runs Git, or serves HTTP). Referenced by the Batch 20 smoke wrapper
# validate_batch20_smoke.sh.
#
# Checks, in order:
#
#   1. the offline control plane test suites under tests/controlplane/
#      (lifecycle service, isolation renders, approval and audit), run
#      with plain system python3 - the service core is stdlib-only and
#      must never need the CI venv;
#   2. the seeded denial fixture sweep: every fixture under
#      tests/controlplane/fixtures/seeded_denials/ is replayed against
#      real service instances on temp directories and must be denied
#      with its seeded error_code, a denial audit record carrying
#      tenant_id (TR-09, execution gate emit_audit_record_on_denial),
#      and zero state mutation (TR-16 deny-by-default);
#   3. OpenAPI structural validation of
#      contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml: openapi 3.x
#      version present, every path operation carries a unique
#      operationId and non-empty responses, and every $ref resolves -
#      including the external ./TENANT_CONTRACT_SCHEMA_V1.json
#      document (venv PyYAML; a validator-side dependency only);
#   4. the mechanical cross-check of the API contract's
#      x-lifecycle-binding block against
#      contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml: same
#      states, initial and terminal states, per-transition from/to
#      sets, idempotent and destructive flags, approval risk classes,
#      audit required_fields, and execution gates - any drift fails.
#
# Invoke from the repository root. Exit 0 on pass, non-zero on failure.

set -euo pipefail

echo "Running the offline control plane test suites (system python3)..."
python3 tests/controlplane/test_lifecycle_service.py
python3 tests/controlplane/test_isolation_renders.py
python3 tests/controlplane/test_approval_audit.py
echo "Offline control plane test suites passed."

echo "Exercising seeded denial fixtures against the service logic..."
python3 tests/controlplane/test_seeded_denials.py
echo "Seeded denial fixture checks passed."

# PyYAML is needed for the OpenAPI document checks below; the service
# core itself stays stdlib-only, so the venv is a validator-side
# dependency exactly as in the sibling YAML-consuming validators.
# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

echo "Validating the OpenAPI document structurally (refs, operations)..."
python - <<'PY'
"""Structural validation of TENANT_CONTROL_PLANE_API_V1.yaml."""
import json
import sys
from pathlib import Path
from typing import Any

import yaml

API_PATH = Path("contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml")
EXTERNAL_SCHEMA_REF = "./TENANT_CONTRACT_SCHEMA_V1.json"
HTTP_METHODS = (
    "get", "put", "post", "delete", "options", "head", "patch", "trace",
)


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


doc = yaml.safe_load(API_PATH.read_text(encoding="utf-8"))

version = doc.get("openapi")
if not isinstance(version, str) or not version.startswith("3."):
    fail(f"{API_PATH}: openapi version missing or not 3.x: {version!r}")
info = doc.get("info", {})
if not info.get("title") or not info.get("version"):
    fail(f"{API_PATH}: info.title and info.version are required")

paths = doc.get("paths")
if not isinstance(paths, dict) or not paths:
    fail(f"{API_PATH}: paths must be a non-empty mapping")

operation_ids: dict[str, str] = {}
for path_name, path_item in paths.items():
    if not isinstance(path_item, dict):
        fail(f"{API_PATH}: path {path_name} is not a mapping")
    for method in HTTP_METHODS:
        operation = path_item.get(method)
        if operation is None:
            continue
        where = f"{method.upper()} {path_name}"
        operation_id = operation.get("operationId")
        if not isinstance(operation_id, str) or not operation_id:
            fail(f"{API_PATH}: {where} has no operationId")
        if operation_id in operation_ids:
            fail(
                f"{API_PATH}: operationId {operation_id!r} duplicated "
                f"across {operation_ids[operation_id]} and {where}"
            )
        operation_ids[operation_id] = where
        responses = operation.get("responses")
        if not isinstance(responses, dict) or not responses:
            fail(f"{API_PATH}: {where} has no responses")


def collect_refs(node: Any, refs: list[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            refs.append(ref)
        for value in node.values():
            collect_refs(value, refs)
    elif isinstance(node, list):
        for item in node:
            collect_refs(item, refs)


def resolve_pointer(root: Any, pointer: str, ref: str) -> None:
    """Resolve one JSON pointer fragment; fail on a dangling ref."""
    if pointer in ("", "/"):
        return
    if not pointer.startswith("/"):
        fail(f"{API_PATH}: $ref {ref!r} has a non-pointer fragment")
    node = root
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            fail(f"{API_PATH}: unresolvable $ref {ref!r} (at {token!r})")


refs: list[str] = []
collect_refs(doc, refs)
if not refs:
    fail(f"{API_PATH}: no $refs found; document shape is unexpected")

external_docs: dict[Path, Any] = {}
for ref in refs:
    if ref.startswith("#"):
        resolve_pointer(doc, ref[1:], ref)
        continue
    file_part, _, fragment = ref.partition("#")
    target = (API_PATH.parent / file_part).resolve()
    if not target.is_file():
        fail(f"{API_PATH}: $ref {ref!r} points at a missing file")
    if target not in external_docs:
        external_docs[target] = json.loads(
            target.read_text(encoding="utf-8")
        )
    resolve_pointer(external_docs[target], fragment, ref)

if EXTERNAL_SCHEMA_REF not in {r.partition("#")[0] for r in refs}:
    fail(
        f"{API_PATH}: expected a $ref to {EXTERNAL_SCHEMA_REF} binding "
        "the API to the authoritative tenant contract schema"
    )

print(
    f"openapi {version}: {len(paths)} paths, "
    f"{len(operation_ids)} operations with unique operationIds, "
    f"{len(refs)} $refs resolve ({len(external_docs)} external file)"
)
PY
echo "OpenAPI structural checks passed."

echo "Cross-checking x-lifecycle-binding against the lifecycle contract..."
python - <<'PY'
"""x-lifecycle-binding must equal TENANT_LIFECYCLE_CONTRACT_V1.yaml.

Mechanical, by name: same states, same initial and terminal states,
same from/to sets per transition, same idempotency, destructive
exactly where the lifecycle contract gates on approval, same approval
risk classes, same audit required_fields, same execution gates. Any
drift on either side fails CI.
"""
import sys
from pathlib import Path

import yaml

API_PATH = Path("contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml")
LIFECYCLE_PATH = Path(
    "contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml"
)
APPROVAL_FLOW = "contracts/policy/APPROVAL_FLOW_V1.yaml"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


api = yaml.safe_load(API_PATH.read_text(encoding="utf-8"))
lifecycle = yaml.safe_load(LIFECYCLE_PATH.read_text(encoding="utf-8"))

binding = api.get("x-lifecycle-binding")
if not isinstance(binding, dict):
    fail(f"{API_PATH}: x-lifecycle-binding block is missing")
if binding.get("contract") != str(LIFECYCLE_PATH):
    fail(
        f"{API_PATH}: x-lifecycle-binding.contract must name "
        f"{LIFECYCLE_PATH}"
    )

machine = lifecycle.get("state_machine", {})
for key, binding_key in (
    ("states", "states"),
    ("initial_state", "initial_state"),
    ("terminal_states", "terminal_states"),
):
    if binding.get(binding_key) != machine.get(key):
        fail(
            f"binding.{binding_key} {binding.get(binding_key)!r} != "
            f"lifecycle state_machine.{key} {machine.get(key)!r}"
        )

binding_transitions = binding.get("transitions", {})
lifecycle_transitions = lifecycle.get("transitions", {})
if set(binding_transitions) != set(lifecycle_transitions):
    fail(
        f"transition name drift: binding "
        f"{sorted(binding_transitions)} != lifecycle "
        f"{sorted(lifecycle_transitions)}"
    )

# Path operationIds, for the per-transition operation cross-check.
operation_ids = {
    operation.get("operationId")
    for path_item in api.get("paths", {}).values()
    for method, operation in path_item.items()
    if method in ("get", "put", "post", "delete", "patch")
}

for name, spec in binding_transitions.items():
    life = lifecycle_transitions[name]
    if spec.get("from") != life.get("from"):
        fail(
            f"transition {name!r}: from {spec.get('from')!r} != "
            f"lifecycle {life.get('from')!r}"
        )
    if spec.get("to") != life.get("to"):
        fail(
            f"transition {name!r}: to {spec.get('to')!r} != "
            f"lifecycle {life.get('to')!r}"
        )
    if spec.get("idempotent") != life.get("idempotent"):
        fail(
            f"transition {name!r}: idempotent flag drift "
            f"({spec.get('idempotent')!r} != {life.get('idempotent')!r})"
        )
    # The lifecycle contract expresses destructiveness by gating the
    # transition on the approval flow contract; the binding restates
    # it as an explicit flag. The two must agree.
    life_approval = life.get("approval")
    if spec.get("destructive") is not (life_approval is not None):
        fail(
            f"transition {name!r}: destructive flag "
            f"{spec.get('destructive')!r} does not match the lifecycle "
            f"contract's approval gating"
        )
    binding_approval = spec.get("approval")
    if life_approval is None:
        if binding_approval is not None:
            fail(
                f"transition {name!r}: binding declares an approval "
                "but the lifecycle contract has none"
            )
    else:
        if not isinstance(binding_approval, dict):
            fail(
                f"transition {name!r}: lifecycle requires approval but "
                "the binding declares none"
            )
        if binding_approval.get("contract") != APPROVAL_FLOW or (
            life_approval.get("contract") != APPROVAL_FLOW
        ):
            fail(
                f"transition {name!r}: approval contract must be "
                f"{APPROVAL_FLOW} on both sides"
            )
        if binding_approval.get("risk_class") != life_approval.get(
            "risk_class"
        ):
            fail(
                f"transition {name!r}: approval risk_class drift "
                f"({binding_approval.get('risk_class')!r} != "
                f"{life_approval.get('risk_class')!r})"
            )
    life_audit = life.get("audit", {})
    if life_audit.get("record_required") is not True:
        fail(
            f"lifecycle transition {name!r} must require an audit "
            "record"
        )
    if spec.get("audit_required_fields") != life_audit.get(
        "required_fields"
    ):
        fail(
            f"transition {name!r}: audit required_fields drift "
            f"({spec.get('audit_required_fields')!r} != "
            f"{life_audit.get('required_fields')!r})"
        )
    operation = spec.get("operation")
    if operation not in operation_ids:
        fail(
            f"transition {name!r}: binding operation {operation!r} is "
            "not an operationId in the API paths"
        )

if binding.get("execution_gates") != lifecycle.get("execution_gates"):
    fail(
        "execution_gates drift between the binding and the lifecycle "
        "contract"
    )

replay = binding.get("idempotent_replay", {})
if replay.get("replay_is_error") is not False:
    fail(
        "x-lifecycle-binding.idempotent_replay must declare "
        "replay_is_error: false (replays are never errors)"
    )

print(
    f"x-lifecycle-binding matches {LIFECYCLE_PATH}: "
    f"{len(binding_transitions)} transitions over "
    f"{len(binding.get('states', []))} states, approval risk classes "
    "and audit field lists identical"
)
PY
echo "Lifecycle binding cross-checks passed."

echo "Tenant control plane validation passed."
