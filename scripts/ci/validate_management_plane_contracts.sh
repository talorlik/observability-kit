#!/usr/bin/env bash
#
# Batch 16 Task 5: management-plane contract validation
# (TB-16 | TR-17, TR-03, TR-09, TR-10).
#
# Validates the four Batch 16 management-plane contracts and the seeded
# rejection fixtures against each other:
#   1. Wrapped-system registry: all six bundled systems present with the
#      required fields (upstream_source, version_pin, upgrade_mechanism,
#      config_surface, wrap_method, ui), every wrap_method inside the
#      closed policy enum, `fork` forbidden with its fail_if rule, and
#      every seeded INVALID_REGISTRY_SAMPLES.json case rejected for its
#      seeded reason (the fork-method case among them).
#   2. Unified configuration document vs. schema (stdlib JSON-Schema
#      subset re-implementation, house pattern from
#      validate_tenancy_contracts.sh) plus the validator-enforced
#      cross-file rules: every config leaf key bound, every binding
#      targeting a registered system, every unified_key resolving to a
#      config key, every native_path.repo_path under the target system's
#      registered config surface and present in the repository, every
#      render_target under gitops/. Every seeded
#      INVALID_UNIFIED_CONFIG_SAMPLES.json case rejected for its seeded
#      reason (the unbound-key case among them).
#   3. Propagation and reconciliation contract: the five ordered
#      pipeline stages, drift detection surfacing via the TR-12
#      meta-monitoring alert path, the rollback block with its drill
#      script, the direct-API-write prohibition rule, and the
#      generated-file header rule.
#   4. Single-pane access contract: 1:1 catalog coverage of every
#      registry system with ui.exposed true, SSO role mapping for both
#      plane groups plus tenant scoping on every entry, profile_key
#      references resolving to admin-access profile endpoints (null only
#      with the documented exception note), and the fail_if consistency
#      rules present.
#
# Cloud-agnostic; runs against repository state only.

set -euo pipefail

echo "Validating Batch 16 management-plane contracts..."

# PyYAML is needed for the YAML contracts below.
# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

echo "Validating wrapped-system registry and seeded rejection fixtures..."
python3 - <<'PY'
import json
import sys
from pathlib import Path

import yaml

registry_path = Path("contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml")
invalid_samples_path = Path("contracts/management/samples/INVALID_REGISTRY_SAMPLES.json")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


registry = yaml.safe_load(registry_path.read_text())
policy = registry.get("policy", {})
allowed = policy.get("allowed_wrap_methods", [])
forbidden = policy.get("forbidden_wrap_methods", [])
mechanisms = set(policy.get("upgrade_mechanisms", {}).keys())

EXPECTED_ALLOWED = {"helm-values", "kubernetes-crd", "provisioning-api", "sidecar"}
if set(allowed) != EXPECTED_ALLOWED:
    fail(
        f"{registry_path}: allowed_wrap_methods {sorted(allowed)} != TR-17 enum "
        f"{sorted(EXPECTED_ALLOWED)}."
    )
if "fork" not in forbidden:
    fail(f"{registry_path}: 'fork' must be listed in policy.forbidden_wrap_methods.")
if set(allowed) & set(forbidden):
    fail(f"{registry_path}: allowed and forbidden wrap methods overlap.")
if not mechanisms:
    fail(f"{registry_path}: policy.upgrade_mechanisms is empty.")

policy_rules = {rule.get("id"): rule for rule in policy.get("rules", [])}
fork_rule = policy_rules.get("fail_if_wrap_method_fork")
if fork_rule is None:
    fail(f"{registry_path}: policy rule fail_if_wrap_method_fork is missing.")
if fork_rule.get("severity") != "error":
    fail(f"{registry_path}: fail_if_wrap_method_fork severity must be 'error'.")
if "fork" not in str(fork_rule.get("fail_if", "")):
    fail(f"{registry_path}: fail_if_wrap_method_fork fail_if text must name 'fork'.")

REQUIRED_FIELDS = (
    "system",
    "upstream_source",
    "version_pin",
    "upgrade_mechanism",
    "config_surface",
    "wrap_method",
    "ui",
)
PIN_STATUSES = {"pinned", "to-be-pinned"}


def validate_entry(entry) -> list:
    """Registry-entry validation shared by the real registry and the seeded
    rejection fixtures. Errors are (kind, path) tuples so seeded-reason
    matching can inspect both what failed and where (house pattern from
    validate_tenancy_contracts.sh)."""
    if not isinstance(entry, dict):
        return [("type", "")]
    errors: list = []
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(("required", field))

    wrap = entry.get("wrap_method")
    if wrap is not None:
        # The fork prohibition is its own error kind: TR-17 rejects fork
        # explicitly, not merely as an unknown enum value.
        if wrap in forbidden:
            errors.append(("fork-forbidden", "wrap_method"))
        elif wrap not in allowed:
            errors.append(("enum", "wrap_method"))

    mechanism = entry.get("upgrade_mechanism")
    if mechanism is not None and mechanism not in mechanisms:
        errors.append(("enum", "upgrade_mechanism"))

    pin = entry.get("version_pin")
    if pin is not None:
        if not isinstance(pin, dict):
            errors.append(("type", "version_pin"))
        else:
            if not pin.get("value"):
                errors.append(("required", "version_pin.value"))
            if pin.get("status") not in PIN_STATUSES:
                errors.append(("enum", "version_pin.status"))
            elif pin["status"] == "pinned" and not pin.get("pinned_in"):
                errors.append(("required", "version_pin.pinned_in"))

    surfaces = entry.get("config_surface")
    if surfaces is not None:
        if not isinstance(surfaces, list) or not surfaces:
            errors.append(("minItems", "config_surface"))
        else:
            for idx, surface in enumerate(surfaces):
                if (
                    not isinstance(surface, dict)
                    or not surface.get("surface")
                    or not surface.get("paths")
                ):
                    errors.append(("required", f"config_surface[{idx}]"))

    ui = entry.get("ui")
    if ui is not None:
        if not isinstance(ui, dict) or not isinstance(ui.get("exposed"), bool):
            errors.append(("type", "ui.exposed"))
        elif ui["exposed"] and not ui.get("name"):
            errors.append(("required", "ui.name"))
    return errors


systems = registry.get("systems", [])
system_ids = [entry.get("system") for entry in systems]
if len(set(system_ids)) != len(system_ids):
    fail(f"{registry_path}: duplicate system ids: {system_ids}.")

EXPECTED_SYSTEMS = {
    "opentelemetry-collector",
    "opensearch",
    "opensearch-dashboards",
    "grafana",
    "neo4j",
    "argocd",
}
missing_systems = sorted(EXPECTED_SYSTEMS - set(system_ids))
if missing_systems:
    fail(f"{registry_path}: TR-17 bundled systems missing: {missing_systems}.")

for entry in systems:
    errors = validate_entry(entry)
    if errors:
        fail(f"{registry_path}: entry '{entry.get('system')}' invalid: {errors}.")
    # Registered pins and config surfaces must point at real repository
    # paths; fixtures skip this pass because they model hypothetical entries.
    pinned_in = entry["version_pin"].get("pinned_in")
    if pinned_in and not Path(pinned_in).exists():
        fail(
            f"{registry_path}: entry '{entry['system']}' version_pin.pinned_in "
            f"path does not exist: {pinned_in}."
        )
    for surface in entry["config_surface"]:
        for path in surface["paths"]:
            if not Path(path).exists():
                fail(
                    f"{registry_path}: entry '{entry['system']}' config_surface "
                    f"path does not exist: {path}."
                )

exposed_uis = sum(1 for entry in systems if entry["ui"].get("exposed") is True)
print(
    f"registry: {len(systems)} wrapped systems (all {len(EXPECTED_SYSTEMS)} "
    f"bundled systems present), {exposed_uis} exposed UIs, fork forbidden"
)

print("Ensuring seeded invalid registry entries are rejected for their seeded reason...")


def reason_matched(reason: str, errors: list) -> bool:
    """Seeded reasons look like '<field>.<violation-kind-slug>'. Map the
    slug to the validator error kind and require an error of that kind at
    (or under) the seeded field."""
    field = reason.split(".", 1)[0]
    if "fork-forbidden" in reason:
        return ("fork-forbidden", field) in errors
    if "enum-violation" in reason:
        return any(kind == "enum" and path.startswith(field) for kind, path in errors)
    if "required-property-absent" in reason:
        return any(kind == "required" and path.endswith(field) for kind, path in errors)
    fail(f"unrecognized seeded rejection reason '{reason}'; extend the validator.")
    return False


invalid_doc = json.loads(invalid_samples_path.read_text())
invalid_cases = invalid_doc.get("invalid_systems", {})
if not invalid_cases:
    fail(f"{invalid_samples_path}: no invalid_systems cases found.")
if "fork_wrap_method" not in invalid_cases:
    fail(f"{invalid_samples_path}: the seeded fork-method case is missing.")

for case_name, case in sorted(invalid_cases.items()):
    reason = case.get("expected_rejection_reason")
    entry = case.get("entry")
    if not reason or entry is None:
        fail(
            f"{invalid_samples_path}: case '{case_name}' needs "
            "expected_rejection_reason and entry."
        )
    errors = validate_entry(entry)
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
echo "Wrapped-system registry checks passed."

echo "Validating unified configuration document, bindings, and seeded rejection fixtures..."
python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

import yaml

schema_path = Path("contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json")
registry_path = Path("contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml")
valid_doc_path = Path("contracts/management/samples/VALID_UNIFIED_CONFIG.yaml")
invalid_samples_path = Path(
    "contracts/management/samples/INVALID_UNIFIED_CONFIG_SAMPLES.json"
)


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


schema = json.loads(schema_path.read_text())
registry = yaml.safe_load(registry_path.read_text())


def resolve_ref(node: dict) -> dict:
    """Resolve local '#/...' $ref pointers (the schema only refs $defs)."""
    ref = node.get("$ref")
    if ref is None:
        return node
    if not ref.startswith("#/"):
        fail(f"{schema_path}: unsupported non-local $ref '{ref}'.")
    target = schema
    for part in ref[2:].split("/"):
        target = target[part]
    return target


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
    """Stdlib re-implementation of the JSON-Schema subset the unified
    config schema uses (no jsonschema dependency, per house pattern),
    extended with $ref, const, and minProperties which this schema needs.
    Errors are (kind, path) tuples so seeded-reason matching can inspect
    both what failed and where."""
    node = resolve_ref(node)

    if "const" in node and value != node["const"]:
        errors.append(("const", path))
        return

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
        min_props = node.get("minProperties")
        if min_props is not None and len(value) < min_props:
            errors.append(("minProperties", path))
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

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = node.get("minimum")
        if minimum is not None and value < minimum:
            errors.append(("minimum", path))
        maximum = node.get("maximum")
        if maximum is not None and value > maximum:
            errors.append(("maximum", path))


def schema_errors(doc) -> list:
    errors: list = []
    if not isinstance(doc, dict):
        return [("type", "")]
    validate_node(doc, schema, "", errors)
    return errors


# Registry-derived cross-file facts: registered system ids and the flat
# list of config-surface paths each system may be bound to.
registry_ids = set()
surfaces_by_system = {}
for entry in registry.get("systems", []):
    system_id = entry.get("system")
    registry_ids.add(system_id)
    paths = []
    for surface in entry.get("config_surface", []):
        paths.extend(surface.get("paths", []))
    surfaces_by_system[system_id] = paths


def config_leaf_keys(config: dict) -> set:
    """Dotted paths of every leaf key under config. Arrays are leaves
    (for example alerting.notification_channels)."""
    leaves = set()

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            dotted = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                walk(value, dotted)
            else:
                leaves.add(dotted)

    walk(config, "")
    return leaves


def under_surface(repo_path: str, surface_paths: list) -> bool:
    for surface_path in surface_paths:
        base = surface_path.rstrip("/")
        if repo_path == base or repo_path.startswith(base + "/"):
            return True
    return False


def cross_rule_errors(doc: dict) -> list:
    """The three validator-enforced cross-file rules from the schema
    description plus the config-surface, repo-existence, and GitOps-only
    render_target rules."""
    errors: list = []
    config = doc.get("config")
    bindings = doc.get("bindings")
    leaves = config_leaf_keys(config) if isinstance(config, dict) else set()
    bound = set()
    for idx, binding in enumerate(bindings if isinstance(bindings, list) else []):
        if not isinstance(binding, dict):
            continue  # the schema pass reports the type violation
        where = f"bindings[{idx}]"
        unified_key = binding.get("unified_key")
        system = binding.get("system")
        native = binding.get("native_path")
        native = native if isinstance(native, dict) else {}
        repo_path = str(native.get("repo_path") or "").strip()
        render_target = str(binding.get("render_target") or "").strip()

        if unified_key is not None:
            if unified_key in leaves:
                bound.add(unified_key)
            else:
                errors.append(("unknown-config-key", f"{where}.unified_key={unified_key}"))

        if system is not None:
            if system not in registry_ids:
                errors.append(("unregistered-target", f"{where}.system={system}"))
            elif repo_path:
                # Surface containment is only decidable for registered
                # systems; the unregistered-target error already covers
                # the rest.
                if not under_surface(repo_path, surfaces_by_system[system]):
                    errors.append(
                        ("outside-config-surface", f"{where}.repo_path={repo_path}")
                    )
                if not Path(repo_path).exists():
                    errors.append(("repo-path-missing", f"{where}.repo_path={repo_path}"))

        if render_target and not render_target.startswith("gitops/"):
            errors.append(
                ("render-target-outside-gitops", f"{where}.render_target={render_target}")
            )

    for leaf in sorted(leaves - bound):
        errors.append(("config-key-unbound", leaf))
    return errors


valid_doc = yaml.safe_load(valid_doc_path.read_text())
errors = schema_errors(valid_doc) + cross_rule_errors(valid_doc)
if errors:
    fail(f"{valid_doc_path}: expected valid but got violations: {errors}.")

leaves = config_leaf_keys(valid_doc["config"])
bound_systems = {binding["system"] for binding in valid_doc["bindings"]}
print(
    f"unified config: {len(valid_doc['bindings'])} bindings cover "
    f"{len(leaves)} config keys across {len(bound_systems)} registered systems"
)

print("Ensuring seeded invalid unified documents are rejected for their seeded reason...")

REASON_KINDS = {
    "bindings.config-key-unbound": "config-key-unbound",
    "bindings.system.unregistered-target": "unregistered-target",
    "bindings.unified_key.unknown-config-key": "unknown-config-key",
    "document.additional-property-forbidden": "additionalProperties",
}


def reason_matched(reason: str, errors: list) -> bool:
    kind = REASON_KINDS.get(reason)
    if kind is None:
        fail(f"unrecognized seeded rejection reason '{reason}'; extend the validator.")
    return any(error_kind == kind for error_kind, _ in errors)


invalid_doc = json.loads(invalid_samples_path.read_text())
invalid_cases = invalid_doc.get("invalid_documents", {})
if not invalid_cases:
    fail(f"{invalid_samples_path}: no invalid_documents cases found.")
if "unbound_config_key" not in invalid_cases:
    fail(f"{invalid_samples_path}: the seeded unbound-key case is missing.")

for case_name, case in sorted(invalid_cases.items()):
    reason = case.get("expected_rejection_reason")
    document = case.get("document")
    if not reason or document is None:
        fail(
            f"{invalid_samples_path}: case '{case_name}' needs "
            "expected_rejection_reason and document."
        )
    errors = schema_errors(document) + cross_rule_errors(document)
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
echo "Unified configuration checks passed."

echo "Validating propagation and reconciliation contract..."
python3 - <<'PY'
import sys
from pathlib import Path

import yaml

contract_path = Path("contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


contract = yaml.safe_load(contract_path.read_text())

EXPECTED_STAGES = ["render", "commit", "reconcile", "verify", "drift_detection"]
stages = contract.get("pipeline", {}).get("stages", [])
stage_ids = [stage.get("id") for stage in stages]
if stage_ids != EXPECTED_STAGES:
    fail(f"{contract_path}: pipeline stages {stage_ids} != expected {EXPECTED_STAGES}.")
stage_orders = [stage.get("order") for stage in stages]
if stage_orders != [1, 2, 3, 4, 5]:
    fail(f"{contract_path}: stage orders {stage_orders} must be 1..5 in order.")

# Generated-file header rule: the render stage declares the marker and
# requires it in every rendered file; the prohibitions block re-asserts it.
render = stages[0]
marker = str(render.get("generated_file_header_marker", "")).strip()
if "GENERATED" not in marker or "DO NOT EDIT" not in marker:
    fail(f"{contract_path}: render stage generated_file_header_marker is missing or weak.")
if render.get("header_marker_required_in_all_rendered_files") is not True:
    fail(f"{contract_path}: header marker must be required in all rendered files.")
pre_commit = render.get("pre_commit_validation", {})
if "UNIFIED_CONFIG_SCHEMA_V1.json" not in str(
    pre_commit.get("document_validates_against_schema", "")
):
    fail(f"{contract_path}: render pre-commit validation must cite the unified schema.")
if "WRAPPED_SYSTEM_REGISTRY_V1.yaml" not in str(
    pre_commit.get("binding_targets_registered_in", "")
):
    fail(f"{contract_path}: render pre-commit validation must cite the registry.")

drift = contract.get("drift_detection", {})
if drift.get("source_of_truth") != "rendered-state-committed-in-git":
    fail(f"{contract_path}: drift source_of_truth must be the rendered Git state.")
alerting = drift.get("alerting", {})
if alerting.get("surfaces_via") != "tr12-meta-monitoring-alert-path":
    fail(f"{contract_path}: drift must surface via the TR-12 meta-monitoring path.")
alert_dir = str(alerting.get("alert_rules_dir", "")).strip()
if alert_dir != "gitops/platform/search/dashboards/alerts/":
    fail(f"{contract_path}: alert_rules_dir '{alert_dir}' is not the meta-monitoring path.")
if not Path(alert_dir).is_dir():
    fail(f"{contract_path}: alert_rules_dir does not exist: {alert_dir}.")
bundle = str(alerting.get("alert_rule_bundle", "")).strip()
if not bundle or not Path(bundle).is_file():
    fail(f"{contract_path}: alert_rule_bundle missing or absent from repo: '{bundle}'.")
if "config-drift-detected-per-system" not in alerting.get("required_alert_signals", []):
    fail(f"{contract_path}: required_alert_signals must include per-system drift.")

rollback = contract.get("rollback", {})
mechanisms = rollback.get("mechanisms", [])
if not mechanisms:
    fail(f"{contract_path}: rollback.mechanisms is empty.")
if not any(mechanism.get("preferred") is True for mechanism in mechanisms):
    fail(f"{contract_path}: no rollback mechanism is marked preferred.")
drills = rollback.get("drills", {})
drill_script = str(drills.get("script", "")).strip()
if drill_script != "scripts/ops/run_rollback_drill.sh":
    fail(f"{contract_path}: rollback drill script '{drill_script}' is not the ops drill.")
if not Path(drill_script).is_file():
    fail(f"{contract_path}: rollback drill script does not exist: {drill_script}.")
if drills.get("default_mode") != "dry-run":
    fail(f"{contract_path}: rollback drill default_mode must be 'dry-run'.")

prohibitions = contract.get("prohibitions", {})
if not prohibitions.get("direct_api_writes", {}).get("statement"):
    fail(f"{contract_path}: prohibitions.direct_api_writes.statement is missing.")
manual_edits = prohibitions.get("manual_render_target_edits", {})
if manual_edits.get("hand_edits_forbidden_in_render_targets") is not True:
    fail(f"{contract_path}: hand edits to render targets must be forbidden.")
if manual_edits.get("header_marker_required") is not True:
    fail(f"{contract_path}: prohibitions must require the generated-file header marker.")

compliance_rules = {
    rule.get("id"): rule for rule in contract.get("compliance", {}).get("rules", [])
}
for required_id in (
    "fail_if_direct_api_write_persistent_config",
    "fail_if_render_target_hand_edited",
):
    rule = compliance_rules.get(required_id)
    if rule is None:
        fail(f"{contract_path}: compliance rule {required_id} is missing.")
    if rule.get("severity") != "error" or not rule.get("fail_if"):
        fail(f"{contract_path}: compliance rule {required_id} needs severity error and fail_if.")

print(
    f"propagation: {len(stages)} ordered pipeline stages, drift surfaces via "
    f"TR-12 meta-monitoring, rollback drill wired, "
    f"{len(compliance_rules)} compliance rules"
)
PY
echo "Propagation and reconciliation checks passed."

echo "Validating single-pane access contract against the registry..."
python3 - <<'PY'
import json
import sys
from pathlib import Path

import yaml

contract_path = Path("contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml")
registry_path = Path("contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml")
profile_path = Path("install/profiles/admin-access/PROFILE.schema.json")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


contract = yaml.safe_load(contract_path.read_text())
registry = yaml.safe_load(registry_path.read_text())
profile = json.loads(profile_path.read_text())

profile_endpoint_keys = set(
    profile.get("properties", {}).get("endpoints", {}).get("properties", {}).keys()
)
if not profile_endpoint_keys:
    fail(f"{profile_path}: no endpoints keys found in the admin-access profile schema.")

exposed_systems = {
    entry["system"]
    for entry in registry.get("systems", [])
    if entry.get("ui", {}).get("exposed") is True
}

catalog = contract.get("ui_catalog", [])
catalog_systems = [entry.get("system") for entry in catalog]
if len(set(catalog_systems)) != len(catalog_systems):
    fail(f"{contract_path}: duplicate ui_catalog systems: {catalog_systems}.")
missing = sorted(exposed_systems - set(catalog_systems))
if missing:
    fail(f"{contract_path}: registry systems with ui.exposed true lack a catalog entry: {missing}.")
extra = sorted(set(catalog_systems) - exposed_systems)
if extra:
    fail(
        f"{contract_path}: catalog entries name systems that are unregistered or "
        f"not ui-exposed: {extra}."
    )

catalog_ids = [entry.get("id") for entry in catalog]
if any(not catalog_id for catalog_id in catalog_ids):
    fail(f"{contract_path}: every ui_catalog entry must have a stable id.")
if len(set(catalog_ids)) != len(catalog_ids):
    fail(f"{contract_path}: duplicate ui_catalog ids: {catalog_ids}.")

PLANE_GROUPS = {"role_mapping.readonly_group", "role_mapping.admin_group"}

for entry in catalog:
    entry_id = entry["id"]

    sso = entry.get("sso_role_mapping")
    if not isinstance(sso, dict):
        fail(f"{contract_path}: entry '{entry_id}' omits the sso_role_mapping block.")
    if not sso.get("identity_provider") or not sso.get("native_mechanism"):
        fail(
            f"{contract_path}: entry '{entry_id}' sso_role_mapping needs "
            "identity_provider and native_mechanism."
        )
    mapped_groups = {mapping.get("plane_group") for mapping in sso.get("mappings", [])}
    if not PLANE_GROUPS <= mapped_groups:
        fail(
            f"{contract_path}: entry '{entry_id}' must map both plane groups "
            f"{sorted(PLANE_GROUPS)}; got {sorted(mapped_groups)}."
        )

    scoping = entry.get("tenant_scoping")
    if not isinstance(scoping, dict) or not scoping.get("mechanism") or not scoping.get("rules"):
        fail(
            f"{contract_path}: entry '{entry_id}' omits tenant_scoping (mechanism "
            "and rules are required)."
        )

    endpoint = entry.get("endpoint")
    if not isinstance(endpoint, dict) or "profile_key" not in endpoint:
        fail(f"{contract_path}: entry '{entry_id}' omits endpoint.profile_key.")
    profile_key = endpoint.get("profile_key")
    if profile_key is None:
        # Null profile_key is allowed only with the documented exception
        # note (the bring-your-own Argo CD install).
        if "exception" not in str(endpoint.get("note", "")).lower():
            fail(
                f"{contract_path}: entry '{entry_id}' has a null profile_key "
                "without a documented-exception note."
            )
    elif profile_key not in profile_endpoint_keys:
        fail(
            f"{contract_path}: entry '{entry_id}' profile_key '{profile_key}' is "
            f"not an admin-access profile endpoints key {sorted(profile_endpoint_keys)}."
        )

    if entry.get("tls", {}).get("required") is not True:
        fail(f"{contract_path}: entry '{entry_id}' must require TLS.")

    # fail_if_hardcoded_endpoint enforcement: catalog entries reference
    # endpoints, never literal URLs.
    if "http://" in json.dumps(entry) or "https://" in json.dumps(entry):
        fail(f"{contract_path}: entry '{entry_id}' carries a hardcoded URL.")

REQUIRED_RULES = {
    "fail_if_registry_ui_missing_from_catalog",
    "fail_if_catalog_system_unregistered",
    "fail_if_missing_auth_or_tenancy_block",
    "fail_if_bespoke_ui_auth",
    "fail_if_hardcoded_endpoint",
}
consistency_rules = {
    rule.get("id"): rule
    for rule in contract.get("consistency_policy", {}).get("rules", [])
}
for rule_id in sorted(REQUIRED_RULES):
    rule = consistency_rules.get(rule_id)
    if rule is None:
        fail(f"{contract_path}: consistency rule {rule_id} is missing.")
    if rule.get("severity") != "error" or not rule.get("fail_if"):
        fail(f"{contract_path}: consistency rule {rule_id} needs severity error and fail_if.")

print(
    f"single-pane: {len(catalog)} cataloged UIs cover {len(exposed_systems)} "
    f"exposed registry systems 1:1, both plane groups mapped, "
    f"{len(consistency_rules)} consistency rules intact"
)
PY
echo "Single-pane access checks passed."

echo "Batch 16 management-plane contract validation checks passed."
