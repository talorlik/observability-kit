#!/usr/bin/env bash
#
# Batch 15 Task 5: tenancy contract validation (TB-15 | TR-16, TR-07, TR-09).
#
# Validates the four Batch 15 tenancy contracts and the seeded cross-tenant
# rejection fixtures against each other:
#   1. Tenant contract schema vs. valid/invalid samples (stdlib JSON-Schema
#      subset re-implementation, house pattern from validate_install_contract.sh;
#      every seeded invalid sample must be rejected for its seeded reason).
#   2. Isolation matrix completeness: 5 stores x 3 isolation classes,
#      deny-by-default cross-tenant posture, mandatory vector retrieval
#      filters, one Neo4j database per tenant, Batch 8 layering statement.
#   3. Seeded denial fixtures: exact 1:1 mapping between the matrix's
#      SDN-B15-* scenarios and CROSS_TENANT_DENIAL_FIXTURES_V1.json, every
#      fixture expecting a denial outcome (deny/reject, never allow).
#   4. Lifecycle contract: states confined to the schema's lifecycle_state
#      enum, idempotent transitions, provable purge evidence and retention,
#      approval-gated destructive transitions via APPROVAL_FLOW_V1.yaml.
#   5. Overlay generation contract: GitOps-only invariants, deterministic
#      regeneration, committed EXAMPLE_TENANT_OVERLAY with generated-file
#      headers, control-plane vs data-plane separation.
#
# Cloud-agnostic; runs against repository state only.

set -euo pipefail

echo "Validating Batch 15 tenancy contracts..."

# PyYAML is needed for the YAML contracts below.
# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

echo "Validating tenant contract samples against schema..."
python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

schema_path = Path("contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json")
valid_samples = [
    Path("contracts/tenancy/samples/VALID_TENANT_BASIC.json"),
    Path("contracts/tenancy/samples/VALID_TENANT_DEDICATED.json"),
]
invalid_samples_path = Path("contracts/tenancy/samples/INVALID_TENANT_SAMPLES.json")

schema = json.loads(schema_path.read_text())


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def type_ok(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def validate_node(value, node: dict, path: str, errors: list) -> None:
    """Stdlib re-implementation of the JSON-Schema subset the tenant
    contract schema uses (no jsonschema dependency, per house pattern).
    Errors are (kind, path) tuples so seeded-reason matching can inspect
    both what failed and where."""
    expected_type = node.get("type")
    if expected_type is not None and not type_ok(value, expected_type):
        errors.append(("type", path))
        return

    if isinstance(value, dict):
        for req in node.get("required", []):
            if req not in value:
                errors.append(("required", f"{path}.{req}".lstrip(".")))
        if node.get("additionalProperties") is False:
            allowed = set(node.get("properties", {}).keys())
            for extra in sorted(set(value.keys()) - allowed):
                errors.append(("additionalProperties", f"{path}.{extra}".lstrip(".")))
        for key, sub in node.get("properties", {}).items():
            if key in value:
                validate_node(value[key], sub, f"{path}.{key}".lstrip("."), errors)

    if isinstance(value, list):
        min_items = node.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(("minItems", path))
        items = node.get("items")
        if items is not None:
            for idx, item in enumerate(value):
                validate_node(item, items, f"{path}[{idx}]", errors)

    if isinstance(value, str):
        enum = node.get("enum")
        if enum is not None and value not in enum:
            errors.append(("enum", path))
        pattern = node.get("pattern")
        if pattern is not None and re.fullmatch(pattern, value) is None:
            errors.append(("pattern", path))
        min_len = node.get("minLength")
        if min_len is not None and len(value) < min_len:
            errors.append(("minLength", path))
        max_len = node.get("maxLength")
        if max_len is not None and len(value) > max_len:
            errors.append(("maxLength", path))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = node.get("minimum")
        if minimum is not None and value < minimum:
            errors.append(("minimum", path))
        maximum = node.get("maximum")
        if maximum is not None and value > maximum:
            errors.append(("maximum", path))
        exclusive_min = node.get("exclusiveMinimum")
        if exclusive_min is not None and value <= exclusive_min:
            errors.append(("exclusiveMinimum", path))


def if_condition_holds(doc: dict, if_node: dict) -> bool:
    for req in if_node.get("required", []):
        if req not in doc:
            return False
    for key, sub in if_node.get("properties", {}).items():
        if "const" in sub and doc.get(key) != sub["const"]:
            return False
    return True


def collect_const_requirements(node: dict, path: str, out: list) -> None:
    if "const" in node:
        out.append((path, node["const"]))
    for key, sub in node.get("properties", {}).items():
        collect_const_requirements(sub, f"{path}.{key}".lstrip("."), out)


def lookup(doc, path: str):
    current = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate_conditionals(doc: dict, errors: list) -> None:
    for entry in schema.get("allOf", []):
        if_node = entry.get("if", {})
        then_node = entry.get("then", {})
        if not if_condition_holds(doc, if_node):
            continue
        const_reqs: list = []
        collect_const_requirements(then_node, "", const_reqs)
        for const_path, const_value in const_reqs:
            if lookup(doc, const_path) != const_value:
                errors.append(("conditional", const_path))


def validate_doc(doc) -> list:
    errors: list = []
    if not isinstance(doc, dict):
        return [("type", "")]
    validate_node(doc, schema, "", errors)
    validate_conditionals(doc, errors)
    return errors


for sample_path in valid_samples:
    if not sample_path.is_file():
        fail(f"missing valid sample: {sample_path}")
    errors = validate_doc(json.loads(sample_path.read_text()))
    if errors:
        fail(f"{sample_path}: expected valid but got violations: {errors}")
    print(f"{sample_path} valid")

print("Ensuring seeded invalid samples are rejected for their seeded reason...")


def reason_matched(reason: str, errors: list) -> bool:
    """Seeded reasons look like '<field>.<violation-kind-slug>'. Map the
    slug to the validator error kind and require an error of that kind at
    (or under) the seeded field."""
    field = reason.split(".", 1)[0]
    if reason == "isolation_class.dedicated-stack-requires-dedicated-pool":
        return ("conditional", "residency.pool") in errors
    if "required-property-absent" in reason:
        return any(kind == "required" and path.endswith(field) for kind, path in errors)
    if "enum-violation" in reason:
        return any(kind == "enum" and path.startswith(field) for kind, path in errors)
    if "pattern-violation" in reason:
        return any(kind == "pattern" and path.startswith(field) for kind, path in errors)
    fail(f"unrecognized seeded rejection reason '{reason}'; extend the validator.")
    return False


invalid_doc = json.loads(invalid_samples_path.read_text())
invalid_cases = invalid_doc.get("invalid_tenants", {})
if not invalid_cases:
    fail(f"{invalid_samples_path}: no invalid_tenants cases found.")

for case_name, case in sorted(invalid_cases.items()):
    reason = case.get("expected_rejection_reason")
    descriptor = case.get("descriptor")
    if not reason or descriptor is None:
        fail(
            f"{invalid_samples_path}: case '{case_name}' needs "
            "expected_rejection_reason and descriptor."
        )
    errors = validate_doc(descriptor)
    if not errors:
        fail(
            f"{invalid_samples_path}: case '{case_name}' was expected to be "
            "rejected but validated cleanly."
        )
    if not reason_matched(reason, errors):
        fail(
            f"{invalid_samples_path}: case '{case_name}' was rejected, but not "
            f"for seeded reason '{reason}'; got {errors}."
        )
    print(f"invalid case '{case_name}' rejected for seeded reason '{reason}'")
PY
echo "Tenant contract schema and seeded rejection checks passed."

echo "Validating tenant isolation matrix..."
python3 - <<'PY'
import json
import sys
from pathlib import Path

import yaml

schema_path = Path("contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json")
matrix_path = Path("contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


schema = json.loads(schema_path.read_text())
matrix = yaml.safe_load(matrix_path.read_text())

schema_classes = schema["properties"]["isolation_class"]["enum"]
declared_classes = (
    matrix.get("metadata", {}).get("isolation_class_source", {}).get("classes", [])
)
if sorted(declared_classes) != sorted(schema_classes):
    fail(
        f"{matrix_path}: metadata isolation classes {declared_classes} do not "
        f"match schema enum {schema_classes}."
    )

EXPECTED_STORES = {"logs", "metrics", "traces", "vectors", "graph"}
isolation_matrix = matrix.get("isolation_matrix", {})
stores = set(isolation_matrix.keys())
if stores != EXPECTED_STORES:
    fail(
        f"{matrix_path}: isolation_matrix stores {sorted(stores)} != expected "
        f"{sorted(EXPECTED_STORES)}."
    )

for store, entry in isolation_matrix.items():
    if not entry.get("store"):
        fail(f"{matrix_path}: isolation_matrix.{store} is missing 'store'.")
    for klass in schema_classes:
        if klass not in entry:
            fail(
                f"{matrix_path}: isolation_matrix.{store} is missing isolation "
                f"class '{klass}' (matrix must be total: 5 stores x 3 classes)."
            )

# Vector tier: mandatory tenant retrieval filter in every class, fail closed.
for klass in schema_classes:
    row = isolation_matrix["vectors"][klass]
    vector_filter = row.get("mandatory_retrieval_filter", {})
    if vector_filter.get("required") is not True:
        fail(
            f"{matrix_path}: vectors.{klass} must set "
            "mandatory_retrieval_filter.required: true."
        )
    if not vector_filter.get("filter"):
        fail(f"{matrix_path}: vectors.{klass} mandatory_retrieval_filter has no filter.")
    if vector_filter.get("on_missing_filter") != "reject":
        fail(f"{matrix_path}: vectors.{klass} must reject unfiltered retrievals.")
    if vector_filter.get("on_tenant_mismatch") != "deny":
        fail(f"{matrix_path}: vectors.{klass} must deny tenant-mismatched filters.")

# Graph tier: one Neo4j database per tenant in every class.
for klass in schema_classes:
    row = isolation_matrix["graph"][klass]
    if row.get("database") != "tenant-<tenant_id>":
        fail(
            f"{matrix_path}: graph.{klass} must declare one database per tenant "
            "(database: tenant-<tenant_id>)."
        )

cross = matrix.get("cross_tenant_access", {})
if cross.get("default") != "deny":
    fail(f"{matrix_path}: cross_tenant_access.default must be 'deny'.")

rules = cross.get("rules", [])
if not rules:
    fail(f"{matrix_path}: cross_tenant_access.rules is empty.")
rule_ids = [rule.get("id") for rule in rules]
if any(not rule_id for rule_id in rule_ids):
    fail(f"{matrix_path}: every cross_tenant_access rule must have an id.")
if len(set(rule_ids)) != len(rule_ids):
    fail(f"{matrix_path}: duplicate cross_tenant_access rule ids: {rule_ids}.")

scenarios = cross.get("seeded_denial_scenarios", [])
if not scenarios:
    fail(f"{matrix_path}: seeded_denial_scenarios is empty.")
scenario_ids = [scenario.get("id") for scenario in scenarios]
if any(not scenario_id for scenario_id in scenario_ids):
    fail(f"{matrix_path}: every seeded denial scenario must have an id.")
if len(set(scenario_ids)) != len(scenario_ids):
    fail(f"{matrix_path}: duplicate seeded scenario ids: {scenario_ids}.")
for scenario in scenarios:
    if not str(scenario.get("id", "")).startswith("SDN-B15-"):
        fail(f"{matrix_path}: scenario id '{scenario.get('id')}' must be SDN-B15-*.")
    if scenario.get("expected_decision") not in {"deny", "reject"}:
        fail(
            f"{matrix_path}: scenario '{scenario.get('id')}' expected_decision "
            "must be a denial outcome (deny or reject)."
        )

layering = matrix.get("layering", {}).get("batch8_team_env_isolation", {})
statement = layering.get("statement", "")
if "Batch 8" not in statement or "never" not in statement:
    fail(
        f"{matrix_path}: layering.batch8_team_env_isolation.statement must "
        "assert Batch 8 isolation is never weakened."
    )
if not layering.get("composition"):
    fail(f"{matrix_path}: batch8_team_env_isolation.composition is missing.")

print(f"isolation matrix: {len(stores)} stores x {len(schema_classes)} classes total")
print(f"cross-tenant default deny with {len(rules)} rules, {len(scenarios)} seeded scenarios")
PY
echo "Tenant isolation matrix checks passed."

echo "Validating seeded cross-tenant denial fixtures against the matrix..."
python3 - <<'PY'
import json
import sys
from pathlib import Path

import yaml

matrix_path = Path("contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml")
fixtures_path = Path("contracts/tenancy/fixtures/CROSS_TENANT_DENIAL_FIXTURES_V1.json")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


matrix = yaml.safe_load(matrix_path.read_text())
fixtures_doc = json.loads(fixtures_path.read_text())

cross = matrix.get("cross_tenant_access", {})
scenarios = {s["id"]: s for s in cross.get("seeded_denial_scenarios", [])}
rule_ids = {rule["id"] for rule in cross.get("rules", [])}
fixtures = fixtures_doc.get("fixtures", [])

fixture_ids = [fixture.get("scenario_id") for fixture in fixtures]
if len(set(fixture_ids)) != len(fixture_ids):
    fail(f"{fixtures_path}: duplicate fixture scenario_ids: {fixture_ids}.")

missing = sorted(set(scenarios) - set(fixture_ids))
if missing:
    fail(f"{fixtures_path}: matrix scenarios without a fixture: {missing}.")
orphans = sorted(set(fixture_ids) - set(scenarios))
if orphans:
    fail(f"{fixtures_path}: orphan fixtures with no matrix scenario: {orphans}.")

DENIAL_OUTCOMES = {"deny", "reject"}
ACCESS_FIELDS = {"actor_tenant", "target_tenant", "store", "action"}

for fixture in fixtures:
    fixture_id = fixture["scenario_id"]
    scenario = scenarios[fixture_id]

    decision = fixture.get("expected_decision")
    if decision not in DENIAL_OUTCOMES:
        fail(
            f"{fixtures_path}: fixture {fixture_id} expected_decision "
            f"'{decision}' is not a denial outcome ({sorted(DENIAL_OUTCOMES)})."
        )
    if decision != scenario.get("expected_decision"):
        fail(
            f"{fixtures_path}: fixture {fixture_id} expected_decision "
            f"'{decision}' does not match the matrix scenario "
            f"('{scenario.get('expected_decision')}')."
        )

    if not fixture.get("description"):
        fail(f"{fixtures_path}: fixture {fixture_id} is missing a description.")

    if fixture.get("enforcement_point") != scenario.get("enforcement_point"):
        fail(
            f"{fixtures_path}: fixture {fixture_id} enforcement_point does not "
            "match the matrix scenario."
        )

    access = fixture.get("attempted_access", {})
    missing_fields = sorted(ACCESS_FIELDS - set(access.keys()))
    if missing_fields:
        fail(
            f"{fixtures_path}: fixture {fixture_id} attempted_access is missing "
            f"{missing_fields}."
        )
    if any(not access[field] for field in ACCESS_FIELDS):
        fail(f"{fixtures_path}: fixture {fixture_id} attempted_access has empty fields.")
    if access["actor_tenant"] == access["target_tenant"]:
        fail(
            f"{fixtures_path}: fixture {fixture_id} is not a cross-tenant "
            "attempt (actor_tenant equals target_tenant)."
        )
    if access["store"] != scenario.get("store"):
        fail(
            f"{fixtures_path}: fixture {fixture_id} store '{access['store']}' "
            f"does not match matrix scenario store '{scenario.get('store')}'."
        )

    denied_by = fixture.get("denied_by_rule")
    if denied_by is not None and denied_by not in rule_ids:
        fail(
            f"{fixtures_path}: fixture {fixture_id} cites unknown rule "
            f"'{denied_by}' (known: {sorted(rule_ids)})."
        )

print(f"{len(fixtures)} seeded denial fixtures map 1:1 onto matrix scenarios")
PY
echo "Cross-tenant denial fixture checks passed."

echo "Validating tenant lifecycle contract..."
python3 - <<'PY'
import json
import sys
from pathlib import Path

import yaml

schema_path = Path("contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json")
lifecycle_path = Path("contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml")
APPROVAL_FLOW = "contracts/policy/APPROVAL_FLOW_V1.yaml"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


schema = json.loads(schema_path.read_text())
lifecycle = yaml.safe_load(lifecycle_path.read_text())

enum_states = set(schema["properties"]["lifecycle_state"]["enum"])
machine = lifecycle.get("state_machine", {})
declared_states = set(machine.get("states", []))
if declared_states != enum_states:
    fail(
        f"{lifecycle_path}: state_machine.states {sorted(declared_states)} != "
        f"schema lifecycle_state enum {sorted(enum_states)}."
    )
if machine.get("initial_state") not in enum_states:
    fail(f"{lifecycle_path}: initial_state is outside the lifecycle_state enum.")
if not set(machine.get("terminal_states", [])) <= enum_states:
    fail(f"{lifecycle_path}: terminal_states contain unknown states.")

transitions = lifecycle.get("transitions", {})
if not transitions:
    fail(f"{lifecycle_path}: no transitions defined.")

# Destructive transitions are those entering a destructive state; each must
# delegate approval semantics to the approval flow contract.
DESTRUCTIVE_TARGETS = {"offboarding", "purged"}

for name, transition in transitions.items():
    from_states = set(transition.get("from", []))
    to_state = transition.get("to")
    if not from_states or not from_states <= enum_states:
        fail(
            f"{lifecycle_path}: transition '{name}' has from-states outside the "
            f"lifecycle_state enum: {sorted(from_states)}."
        )
    if to_state not in enum_states:
        fail(
            f"{lifecycle_path}: transition '{name}' has to-state '{to_state}' "
            "outside the lifecycle_state enum."
        )
    if transition.get("idempotent") is not True:
        fail(f"{lifecycle_path}: transition '{name}' must declare idempotent: true.")
    if not transition.get("idempotency_statement"):
        fail(f"{lifecycle_path}: transition '{name}' is missing an idempotency_statement.")
    audit = transition.get("audit", {})
    if audit.get("record_required") is not True or "tenant_id" not in audit.get(
        "required_fields", []
    ):
        fail(
            f"{lifecycle_path}: transition '{name}' must require an audit record "
            "carrying tenant_id (TR-09)."
        )
    if to_state in DESTRUCTIVE_TARGETS:
        approval = transition.get("approval", {})
        if approval.get("contract") != APPROVAL_FLOW:
            fail(
                f"{lifecycle_path}: destructive transition '{name}' must reference "
                f"{APPROVAL_FLOW} for approval semantics."
            )
        if not approval.get("risk_class"):
            fail(f"{lifecycle_path}: destructive transition '{name}' has no risk_class.")

purge = transitions.get("purge")
if purge is None:
    fail(f"{lifecycle_path}: purge transition is missing.")
evidence = purge.get("evidence_capture", {})
if not evidence:
    fail(f"{lifecycle_path}: purge must define evidence_capture artifacts.")
for store_name, proof in evidence.items():
    if not proof.get("proves") or not proof.get("artifact"):
        fail(
            f"{lifecycle_path}: purge evidence_capture.{store_name} needs both "
            "'proves' and 'artifact'."
        )
retention_rules = purge.get("retention_rules", {})
if retention_rules.get("honored_before_deletion") is not True:
    fail(f"{lifecycle_path}: purge retention_rules must honor retention before deletion.")
evidence_retention = purge.get("evidence_retention", {})
if not evidence_retention.get("retention_days_default"):
    fail(f"{lifecycle_path}: purge evidence_retention needs retention_days_default.")

print(
    f"lifecycle: {len(transitions)} idempotent transitions over "
    f"{len(enum_states)} schema states; purge evidence covers "
    f"{len(evidence)} stores"
)
PY
echo "Tenant lifecycle contract checks passed."

echo "Validating tenant overlay generation contract and committed example..."
python3 - <<'PY'
import sys
from pathlib import Path

import yaml

overlay_path = Path("contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


contract = yaml.safe_load(overlay_path.read_text())

invariants = contract.get("invariants", {})
if invariants.get("core_charts_read_only_per_tenant") is not True:
    fail(f"{overlay_path}: invariant core_charts_read_only_per_tenant must be true.")
if invariants.get("gitops_only_propagation") is not True:
    fail(f"{overlay_path}: invariant gitops_only_propagation must be true.")
if invariants.get("generated_overlays_committed_to_git") is not True:
    fail(f"{overlay_path}: invariant generated_overlays_committed_to_git must be true.")
if "byte-identical" not in str(invariants.get("deterministic_regeneration", "")):
    fail(f"{overlay_path}: deterministic_regeneration must require byte-identical output.")
if "no-diff" not in str(invariants.get("idempotent_regeneration", "")):
    fail(f"{overlay_path}: idempotent_regeneration must require no-diff regeneration.")

output = contract.get("output", {})
marker = output.get("generated_file_header_marker", "").strip()
if not marker:
    fail(f"{overlay_path}: generated_file_header_marker is missing.")
if output.get("header_marker_required_in_all_generated_files") is not True:
    fail(f"{overlay_path}: header marker must be required in all generated files.")

reserved = output.get("reserved_non_tenant_directories", [])
if "EXAMPLE_TENANT_OVERLAY" not in reserved:
    fail(f"{overlay_path}: EXAMPLE_TENANT_OVERLAY must be a reserved directory.")

overlay_root = Path(output.get("overlay_root", "gitops/overlays/tenants/"))
example_dir = overlay_root / "EXAMPLE_TENANT_OVERLAY"
if not example_dir.is_dir():
    fail(f"missing committed generator-output example: {example_dir}")

required_files = [entry["name"] for entry in output.get("required_files", [])]
if not required_files:
    fail(f"{overlay_path}: output.required_files is empty.")
for name in required_files:
    file_path = example_dir / name
    if not file_path.is_file():
        fail(f"{example_dir}: required generated file '{name}' is missing.")
    first_line = file_path.read_text().splitlines()[0] if file_path.read_text() else ""
    if marker not in first_line:
        fail(
            f"{file_path}: first line must carry the generated-file header "
            f"marker '{marker}'."
        )

planes = contract.get("plane_separation", {})
for plane in ("control_plane", "data_plane"):
    if not planes.get(plane, {}).get("owns"):
        fail(f"{overlay_path}: plane_separation.{plane} must declare what it owns.")
plane_rules = planes.get("rules", {})
if plane_rules.get("cross_plane_access") != "deny-by-default":
    fail(f"{overlay_path}: cross_plane_access must be deny-by-default.")
if plane_rules.get("control_plane_records_never_embed_telemetry_payloads") is not True:
    fail(f"{overlay_path}: control-plane records must never embed telemetry payloads.")
if plane_rules.get("telemetry_never_written_to_control_plane_stores") is not True:
    fail(f"{overlay_path}: telemetry must never be written to control-plane stores.")

print(
    f"overlay generation: invariants intact, example overlay present with "
    f"{len(required_files)} headered generated files, plane separation enforced"
)
PY
echo "Tenant overlay generation checks passed."

echo "Batch 15 tenancy contract validation checks passed."
