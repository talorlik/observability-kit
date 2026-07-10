#!/usr/bin/env bash
#
# Batch 22 validator: metering, billing, and commercial operations.
#
# Repository-only and offline (TB-22 composed with TR-23 and TR-16):
# CI validation is fixture-driven; nothing here touches a live
# cluster, calls a billing vendor, or installs anything beyond the
# shared CI venv. Referenced by the Batch 22 smoke wrapper
# validate_batch22_smoke.sh.
#
# Checks, in order:
#
#  1. the offline commercial test suites under tests/commercial/, run
#     with plain system python3 - the commercialsvc package is
#     stdlib-only and must never need the CI venv:
#       - test_usage_record_validation.py (usage record schema rules,
#         tenant_id mandatory, TR-16 payload-embedding rejection)
#       - test_metering_builder.py (deterministic, idempotent record
#         construction for all four TR-23 dimensions)
#       - test_usage_sinks.py (control-tenancy-usage-v1-* index
#         naming; plane-separation refusal of data-plane targets)
#       - test_metering_job.py (fixture source -> builder ->
#         validator -> sink end to end)
#       - test_invoice_export.py (vendor-neutral invoice export math
#         and consistency)
#  2. seeded rejection and sample-consistency checks (system
#     python3): every INVALID_USAGE_RECORD_SAMPLES.json record is
#     rejected by commercialsvc.validation.validate_record (including
#     the record without tenant_id and the embedded telemetry
#     payload), every VALID_USAGE_RECORDS.json record is accepted,
#     the VALID_INVOICE_EXPORT.json sample is arithmetically
#     consistent, and stripping its tenant_id makes it rejected;
#  3. vendor-neutrality and hygiene guards (greps): no billing vendor
#     name in contracts/commercial/ (outside the sanctioned
#     INVALID_BILLING_ADAPTER_SAMPLES.json payloads) or anywhere in
#     services/commercial/; no literal vendor API key material under
#     adapters/billing/; requirements-ci.txt stays lint-only;
#  4. structural validation of the commercial contracts (venv PyYAML;
#     a validator-side dependency only): METERING_CONTRACT_V1.yaml
#     (exactly the four TR-23 dimensions, the three TR-16 telemetry
#     reference forms, control-plane destination, compliance flags),
#     PLAN_CATALOG_V1.yaml (bijective tier binding against the tenant
#     schema enum, all five Batch 15 quota bound fields per plan,
#     bounds inside schema ranges and monotonic across tiers,
#     metered_dimensions inside the metering catalog),
#     INVOICE_EXPORT_CONTRACT_V1.yaml (fail_if catalog), and the
#     adapters/billing/ house pattern (four required files, the
#     Stripe reference stub, fork forbidden, export-only dispatch);
#  5. mechanical execution of the seeded rejection fixtures (venv
#     PyYAML): every INVALID_PLAN_SAMPLES.json payload (including the
#     plan without quota bounds) and every
#     INVALID_BILLING_ADAPTER_SAMPLES.json payload (including the
#     fork-like core mutation) must be rejected by the same check
#     logic that passes the real catalog and adapter files, and the
#     VALID_PLAN_BINDINGS.json pairings must be accepted; the
#     tests/commercial/fixtures/plan_catalog_v1.json mirror must be
#     drift-free against PLAN_CATALOG_V1.yaml.
#
# Markers: TB-22, TR-23, TR-16.
#
# Invoke from the repository root. Exit 0 on pass, non-zero on failure.

set -euo pipefail

echo "Running offline commercial test suites (system python3)..."
for suite in tests/commercial/test_*.py; do
  python3 "$suite"
done

echo "Running seeded usage-record rejections and invoice consistency (system python3)..."
python3 - <<'PY'
import json
import sys

sys.path.insert(0, "services/commercial")

from commercialsvc.invoicing import (  # noqa: E402
    InvoiceExportError,
    ensure_invoice_consistent,
)
from commercialsvc.validation import validate_record  # noqa: E402


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


with open(
    "contracts/commercial/samples/INVALID_USAGE_RECORD_SAMPLES.json",
    encoding="utf-8",
) as handle:
    invalid = json.load(handle)
for sample in invalid["samples"]:
    errors = validate_record(sample["record"])
    if not errors:
        fail(
            "seeded invalid usage record "
            f"{sample['name']!r} was accepted"
        )
names = [sample["name"] for sample in invalid["samples"]]
if "missing-tenant-id" not in names:
    fail("seeded set must include the record without tenant_id")
print(
    f"Seeded usage-record rejections: {len(names)} rejected "
    f"({', '.join(names)})"
)

with open(
    "contracts/commercial/samples/VALID_USAGE_RECORDS.json",
    encoding="utf-8",
) as handle:
    valid = json.load(handle)
for record in valid["records"]:
    errors = validate_record(record)
    if errors:
        fail(f"valid usage record {record['record_id']!r}: {errors}")
print(f"Valid usage-record samples accepted: {len(valid['records'])}")

with open(
    "contracts/commercial/samples/VALID_INVOICE_EXPORT.json",
    encoding="utf-8",
) as handle:
    invoice = json.load(handle)
ensure_invoice_consistent(invoice)
print("VALID_INVOICE_EXPORT.json is arithmetically consistent")

stripped = {k: v for k, v in invoice.items() if k != "tenant_id"}
try:
    ensure_invoice_consistent(stripped)
except InvoiceExportError:
    print("Invoice without tenant_id rejected as required")
else:
    fail("invoice export without tenant_id was accepted")
PY

echo "Checking vendor neutrality and dependency hygiene..."
vendor_hits=$(grep -ril "stripe" contracts/commercial/ services/commercial/ \
  | grep -v "contracts/commercial/samples/INVALID_BILLING_ADAPTER_SAMPLES.json" \
  || true)
if [ -n "${vendor_hits}" ]; then
  echo "ERROR: vendor name leaked into the vendor-neutral core:"
  echo "${vendor_hits}"
  exit 1
fi
if grep -riE "sk_(live|test)_[A-Za-z0-9]" adapters/billing/ >/dev/null; then
  echo "ERROR: literal vendor API key material under adapters/billing/"
  exit 1
fi
if grep -viE '^(yamllint|pymarkdownlnt)([=<>~!].*)?$' requirements-ci.txt \
  | grep -vE '^\s*(#.*)?$' >/dev/null; then
  echo "ERROR: requirements-ci.txt must stay lint-only (yamllint,"
  echo "pymarkdownlnt); the commercial service owns its own manifest."
  exit 1
fi
echo "Vendor neutrality and hygiene guards passed."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

echo "Validating commercial contract structure and seeded rejections (venv)..."
python3 - <<'PY'
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def assert_named_rule_fired(
    sample_name: str, expected_rejection: str, problems: list[str]
) -> None:
    """Pin each seeded rejection to its named fail_if_* rule.

    A fixture rejected only for an incidental reason means its named
    rule silently lost coverage - exactly the regression this gate
    exists to prevent. Samples whose expected_rejection names no
    fail_if_* token are covered by the non-empty problems check alone.
    """
    tokens = re.findall(r"fail_if_[a-z_]+", expected_rejection)
    if not tokens:
        return
    blob = " ".join(problems)
    if tokens[0] not in blob:
        fail(
            f"seeded sample {sample_name!r} was rejected, but not by "
            f"its named rule {tokens[0]} (got: {problems})"
        )


root = Path(".")
commercial = root / "contracts" / "commercial"
billing = root / "adapters" / "billing"

# --- files exist -----------------------------------------------------
required_files = [
    commercial / "METERING_CONTRACT_V1.yaml",
    commercial / "USAGE_RECORD_SCHEMA_V1.json",
    commercial / "PLAN_CATALOG_V1.yaml",
    commercial / "INVOICE_EXPORT_CONTRACT_V1.yaml",
    commercial / "INVOICE_EXPORT_SCHEMA_V1.json",
    commercial / "README.md",
    commercial / "samples" / "VALID_USAGE_RECORDS.json",
    commercial / "samples" / "INVALID_USAGE_RECORD_SAMPLES.json",
    commercial / "samples" / "VALID_PLAN_BINDINGS.json",
    commercial / "samples" / "INVALID_PLAN_SAMPLES.json",
    commercial / "samples" / "VALID_INVOICE_EXPORT.json",
    commercial / "samples" / "INVALID_BILLING_ADAPTER_SAMPLES.json",
    billing / "BILLING_ADAPTER_COMPATIBILITY_V1.yaml",
    billing / "STRIPE_REFERENCE_ADAPTER_STUB_V1.yaml",
    billing / "STUB_METADATA.json",
    billing / "ROLLBACK_UNINSTALL_NOTES.md",
    billing / "README.md",
]
for path in required_files:
    if not path.exists():
        fail(f"missing required Batch 22 artifact: {path}")

# --- metering contract ------------------------------------------------
metering = yaml.safe_load(
    (commercial / "METERING_CONTRACT_V1.yaml").read_text(encoding="utf-8")
)
if metering["metadata"]["contract"] != "metering":
    fail("metering contract metadata.contract must be 'metering'")
for marker in ("TR-23", "TR-16"):
    if marker not in metering["metadata"]["technical_requirements"]:
        fail(f"metering contract must carry marker {marker}")

expected_dims = {
    "ingest_gb_per_day",
    "retention_days",
    "active_tenants",
    "query_volume",
}
dims = {d["id"] for d in metering["dimensions"]}
if dims != expected_dims:
    fail(f"metering dimensions {sorted(dims)} != {sorted(expected_dims)}")

principles = metering["principles"]
if principles.get("no_new_collection_path") is not True:
    fail("metering contract must fix no_new_collection_path: true")
forms = principles.get("telemetry_reference_forms_allowed", [])
if forms != ["index-name", "document-count", "content-digest"]:
    fail(
        "telemetry_reference_forms_allowed must be exactly the three "
        f"plane-separation forms, got {forms}"
    )
destination = metering["destination"]
if destination.get("plane") != "control-plane":
    fail("metering destination plane must be control-plane")
if not str(destination.get("index_naming", "")).startswith(
    "control-tenancy-"
):
    fail("metering destination must be a control-tenancy-* index")
if metering["collector"].get("extends_requirements_ci") is not False:
    fail("metering collector must never extend requirements-ci.txt")
for flag in (
    "fail_if_usage_record_missing_tenant_id",
    "fail_if_telemetry_payload_embedded_in_usage_record",
    "fail_if_unknown_dimension",
    "fail_if_unknown_signal_for_dimension",
    "fail_if_usage_written_outside_control_plane_indices",
    "fail_if_window_end_not_after_window_start",
    "fail_if_new_collection_path_introduced",
    "fail_if_collector_added_to_requirements_ci",
):
    if metering["compliance"].get(flag) is not True:
        fail(f"metering compliance flag {flag} must be true")
print("METERING_CONTRACT_V1.yaml structural checks passed.")

# --- usage record schema ----------------------------------------------
usage_schema = json.loads(
    (commercial / "USAGE_RECORD_SCHEMA_V1.json").read_text(encoding="utf-8")
)
if "tenant_id" not in usage_schema["required"]:
    fail("usage record schema must require tenant_id")
if usage_schema.get("additionalProperties") is not False:
    fail("usage record schema must set additionalProperties: false")
schema_dims = set(
    usage_schema["properties"]["dimension"]["enum"]
)
if schema_dims != expected_dims:
    fail("usage record schema dimension enum drifted from contract")
print("USAGE_RECORD_SCHEMA_V1.json structural checks passed.")

# --- plan catalog -----------------------------------------------------
tenant_schema = json.loads(
    (root / "contracts" / "tenancy" / "TENANT_CONTRACT_SCHEMA_V1.json")
    .read_text(encoding="utf-8")
)
tier_enum = list(tenant_schema["properties"]["tier"]["enum"])

catalog = yaml.safe_load(
    (commercial / "PLAN_CATALOG_V1.yaml").read_text(encoding="utf-8")
)

BOUND_FIELDS = (
    "quotas.ingest.max_gb_per_day",
    "quotas.ingest.max_events_per_second",
    "quotas.retention.logs_days",
    "quotas.retention.metrics_days",
    "quotas.retention.traces_days",
)


def bound_range_violations(field: str, bound: dict) -> list[str]:
    problems: list[str] = []
    low = bound.get("min")
    high = bound.get("max")
    if low is None or high is None:
        return [f"{field}: bound must define min and max"]
    if low > high:
        problems.append(f"{field}: min {low} > max {high}")
    if field == "quotas.ingest.max_gb_per_day":
        if low <= 0:
            problems.append(
                f"{field}: min must be > 0 "
                "(fail_if_quota_bound_outside_tenant_schema_range)"
            )
    elif field == "quotas.ingest.max_events_per_second":
        if low < 1:
            problems.append(
                f"{field}: min must be >= 1 "
                "(fail_if_quota_bound_outside_tenant_schema_range)"
            )
    else:
        if low < 1 or high > 3650:
            problems.append(
                f"{field}: bounds must stay within 1..3650 "
                "(fail_if_quota_bound_outside_tenant_schema_range)"
            )
    return problems


def plan_violations(plan: dict) -> list[str]:
    problems: list[str] = []
    bounds = plan.get("quota_bounds")
    if not isinstance(bounds, dict) or not bounds:
        problems.append(
            f"plan {plan.get('plan_id')!r} has no quota_bounds "
            "(fail_if_plan_missing_quota_bounds)"
        )
        bounds = {}
    for field in BOUND_FIELDS:
        if field not in bounds:
            problems.append(
                f"plan {plan.get('plan_id')!r} missing bound {field}"
            )
        else:
            problems.extend(
                bound_range_violations(field, bounds[field])
            )
    if plan.get("tier") not in tier_enum:
        problems.append(
            f"plan {plan.get('plan_id')!r} tier {plan.get('tier')!r} "
            "outside the tenant schema enum "
            "(fail_if_plan_tier_not_in_tenant_schema_enum)"
        )
    for dim in plan.get("metered_dimensions", []):
        if dim not in expected_dims:
            problems.append(
                f"plan {plan.get('plan_id')!r} meters unknown "
                f"dimension {dim!r} "
                "(fail_if_metered_dimension_not_in_metering_contract)"
            )
    return problems


def catalog_violations(plans: list[dict]) -> list[str]:
    problems: list[str] = []
    tiers = [plan.get("tier") for plan in plans]
    for tier in set(tiers):
        if tiers.count(tier) > 1:
            problems.append(
                f"tier {tier!r} bound to more than one plan "
                "(fail_if_duplicate_tier_binding)"
            )
    for plan in plans:
        problems.extend(plan_violations(plan))
    return problems


plans = catalog["plans"]
problems = catalog_violations(plans)
if set(p.get("tier") for p in plans) != set(tier_enum):
    problems.append(
        "plan catalog does not cover every tenant tier exactly once"
    )
if problems:
    fail("PLAN_CATALOG_V1.yaml violations: " + "; ".join(problems))

# Monotonic non-decreasing bounds from starter to enterprise.
by_tier = {plan["tier"]: plan for plan in plans}
order = [t for t in tier_enum if t in by_tier]
for field in BOUND_FIELDS:
    previous_max = -math.inf
    for tier in order:
        current = by_tier[tier]["quota_bounds"][field]["max"]
        if current < previous_max:
            fail(
                f"plan bounds for {field} are not monotonic across "
                f"tiers at {tier!r}"
            )
        previous_max = current
print("PLAN_CATALOG_V1.yaml structural checks passed.")

# --- plan fixture drift guard ------------------------------------------
fixture = json.loads(
    (root / "tests" / "commercial" / "fixtures" / "plan_catalog_v1.json")
    .read_text(encoding="utf-8")
)
if json.dumps(fixture, sort_keys=True) != json.dumps(
    catalog, sort_keys=True
):
    fail(
        "tests/commercial/fixtures/plan_catalog_v1.json drifted from "
        "contracts/commercial/PLAN_CATALOG_V1.yaml"
    )
print("Plan catalog JSON fixture is drift-free.")

# --- tenant-vs-plan admission checks ------------------------------------
def tenant_quota_value(wrapper: dict, field: str) -> object:
    # field is a dotted path rooted at the tenant descriptor, e.g.
    # quotas.ingest.max_gb_per_day; walk every segment.
    node: object = wrapper
    for part in field.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def binding_violations(tenant: dict, plan: dict) -> list[str]:
    problems: list[str] = []
    if tenant.get("tier") != plan.get("tier"):
        problems.append(
            f"tenant tier {tenant.get('tier')!r} is not the tier "
            f"bound to plan {plan.get('plan_id')!r}"
        )
    quotas = {"quotas": tenant.get("quotas", {})}
    resolved = 0
    for field, bound in plan.get("quota_bounds", {}).items():
        value = tenant_quota_value(quotas, field)
        if value is None:
            continue
        resolved += 1
        if value < bound["min"] or value > bound["max"]:
            problems.append(
                f"tenant {field} value {value} outside plan bound "
                f"[{bound['min']}, {bound['max']}] "
                "(fail_if_tenant_quota_exceeds_plan_bound)"
            )
    if resolved == 0:
        # A binding check that resolves no quota field checks nothing;
        # treat it as a violation so path bugs cannot silently accept.
        problems.append(
            "no tenant quota field resolved against the plan bounds"
        )
    return problems


with open(
    commercial / "samples" / "VALID_PLAN_BINDINGS.json", encoding="utf-8"
) as handle:
    bindings = json.load(handle)
plans_by_id = {plan["plan_id"]: plan for plan in plans}
for entry in bindings["bindings"]:
    plan = plans_by_id.get(entry["plan_id"])
    if plan is None:
        fail(f"binding sample names unknown plan {entry['plan_id']!r}")
    problems = binding_violations(entry["tenant"], plan)
    if entry["expected_result"] == "accepted" and problems:
        fail(
            f"binding sample {entry['tenant']['tenant_id']!r} should "
            f"be accepted but was rejected: {problems}"
        )
print(
    f"VALID_PLAN_BINDINGS.json: {len(bindings['bindings'])} bindings "
    "accepted."
)

# --- seeded plan rejections ---------------------------------------------
with open(
    commercial / "samples" / "INVALID_PLAN_SAMPLES.json", encoding="utf-8"
) as handle:
    invalid_plans = json.load(handle)
rejected = 0
for sample in invalid_plans["samples"]:
    payload = sample["payload"]
    if "plans" in payload:
        problems = catalog_violations(payload["plans"])
    elif "tenant" in payload:
        plan = plans_by_id.get(payload["plan_id"])
        if plan is None:
            fail(
                f"seeded sample {sample['name']!r} names unknown plan "
                f"{payload['plan_id']!r}"
            )
        problems = binding_violations(payload["tenant"], plan)
    else:
        problems = plan_violations(payload)
    if not problems:
        fail(f"seeded invalid plan sample {sample['name']!r} accepted")
    assert_named_rule_fired(
        sample["name"], sample["expected_rejection"], problems
    )
    rejected += 1
names = [sample["name"] for sample in invalid_plans["samples"]]
if "plan-missing-quota-bounds" not in names:
    fail("seeded plan set must include a plan without quota bounds")
print(f"Seeded plan rejections: {rejected} rejected ({', '.join(names)})")

# --- invoice export contract and schema ----------------------------------
invoice_contract = yaml.safe_load(
    (commercial / "INVOICE_EXPORT_CONTRACT_V1.yaml").read_text(
        encoding="utf-8"
    )
)
for rule in (
    "fail_if_invoice_missing_tenant_id",
    "fail_if_vendor_field_in_export_document",
    "fail_if_currency_in_core_export_document",
    "fail_if_adapter_core_mutation",
    "fail_if_totals_inconsistent_with_line_items",
    "fail_if_period_end_not_after_period_start",
    "fail_if_line_item_dimension_not_in_metering_contract",
):
    if rule not in invoice_contract["compliance"]:
        fail(f"invoice export contract missing compliance rule {rule}")

invoice_schema = json.loads(
    (commercial / "INVOICE_EXPORT_SCHEMA_V1.json").read_text(
        encoding="utf-8"
    )
)
if invoice_schema.get("additionalProperties") is not False:
    fail("invoice export schema must set additionalProperties: false")
schema_props = set(invoice_schema["properties"])
if "currency" in schema_props:
    fail("invoice export schema must not define a currency field")
if "tenant_id" not in invoice_schema["required"]:
    fail("invoice export schema must require tenant_id")
print("INVOICE_EXPORT_CONTRACT_V1.yaml and schema checks passed.")

# --- billing adapter house pattern ----------------------------------------
compat = yaml.safe_load(
    (billing / "BILLING_ADAPTER_COMPATIBILITY_V1.yaml").read_text(
        encoding="utf-8"
    )
)
if compat["scope"].get("core_contracts_unchanged") is not True:
    fail("billing adapter must state core contracts remain unchanged")
constraints = compat["constraints"]
allowed = list(constraints.get("allowed_wrap_methods", []))
forbidden = list(constraints.get("forbidden_wrap_methods", []))
if "fork" not in forbidden:
    fail("billing adapter constraints must forbid the fork wrap method")
if "fork" in allowed:
    fail("fork must never be an allowed wrap method")
if constraints.get("dispatch_mode") != "export-only":
    fail("billing adapter dispatch_mode must be export-only")
if constraints.get("secrets_via_secrets_backend_only") is not True:
    fail("billing adapter credentials must resolve via secrets backend")
backends = compat.get("billing_backends", [])
if not backends:
    fail("billing adapter must define at least one backend")
stub_backends = [b for b in backends if b.get("status") == "stub"]
if not any(b.get("name") == "stripe-reference" for b in stub_backends):
    fail("the Stripe reference adapter stub backend is required")

stub = yaml.safe_load(
    (billing / "STRIPE_REFERENCE_ADAPTER_STUB_V1.yaml").read_text(
        encoding="utf-8"
    )
)
stub_wrap = stub.get("compliance", {}).get("wrap_method")
if stub_wrap not in allowed:
    fail(
        f"Stripe stub wrap_method {stub_wrap!r} is not in the allowed "
        f"wrap methods {allowed}"
    )

stub_meta = json.loads(
    (billing / "STUB_METADATA.json").read_text(encoding="utf-8")
)
if stub_meta.get("adapter_class") != "billing":
    fail("STUB_METADATA.json adapter_class must be 'billing'")
if (
    stub_meta.get("fallback_behavior", {}).get("strategy")
    != "disable_adapter_keep_core"
):
    fail("billing stub fallback must be disable_adapter_keep_core")
print("adapters/billing/ house pattern checks passed.")

# --- seeded billing adapter and invoice rejections -------------------------
metering_line_dims = expected_dims


def adapter_violations(adapter: dict) -> list[str]:
    problems: list[str] = []
    wrap = adapter.get("wrap_method")
    if wrap in forbidden or wrap not in allowed:
        problems.append(
            f"wrap_method {wrap!r} is fork-like or unsanctioned "
            "(fail_if_adapter_core_mutation)"
        )
    if adapter.get("core_contract_mutations"):
        problems.append(
            "adapter declares core contract mutations "
            "(fail_if_adapter_core_mutation)"
        )
    return problems


def invoice_violations(document: dict) -> list[str]:
    problems: list[str] = []
    unknown = set(document) - schema_props
    if unknown:
        problems.append(
            f"unknown top-level fields {sorted(unknown)} "
            "(fail_if_vendor_field_in_export_document; vendor and "
            "currency fields are adapter-side only)"
        )
    if "currency" in document:
        problems.append(
            "currency in core export document "
            "(fail_if_currency_in_core_export_document)"
        )
    if not document.get("tenant_id"):
        problems.append(
            "missing tenant_id (fail_if_invoice_missing_tenant_id)"
        )
    period = document.get("billing_period", {})
    try:
        start = datetime.fromisoformat(
            str(period.get("start", "")).replace("Z", "+00:00")
        )
        end = datetime.fromisoformat(
            str(period.get("end", "")).replace("Z", "+00:00")
        )
        ordered = end > start
    except ValueError:
        ordered = False
    if not ordered:
        problems.append(
            "billing period end not after start "
            "(fail_if_period_end_not_after_period_start)"
        )
    items = document.get("line_items", [])
    for item in items:
        if item.get("dimension") not in metering_line_dims:
            problems.append(
                f"line item dimension {item.get('dimension')!r} not "
                "in the metering catalog "
                "(fail_if_line_item_dimension_not_in_metering_contract)"
            )
    totals = document.get("totals", {})
    overage = round(
        sum(float(item.get("overage_units", 0)) for item in items), 6
    )
    if round(float(totals.get("overage_units", -1)), 6) != overage:
        problems.append(
            "totals.overage_units inconsistent with line items "
            "(fail_if_totals_inconsistent_with_line_items)"
        )
    expected_total = round(
        float(totals.get("base_monthly_units", 0)) + overage, 6
    )
    if round(float(totals.get("total_units", -1)), 6) != expected_total:
        problems.append(
            "totals.total_units inconsistent "
            "(fail_if_totals_inconsistent_with_line_items)"
        )
    return problems


with open(
    commercial / "samples" / "VALID_INVOICE_EXPORT.json", encoding="utf-8"
) as handle:
    valid_invoice = json.load(handle)
problems = invoice_violations(valid_invoice)
if problems:
    fail(f"VALID_INVOICE_EXPORT.json rejected: {problems}")

with open(
    commercial / "samples" / "INVALID_BILLING_ADAPTER_SAMPLES.json",
    encoding="utf-8",
) as handle:
    invalid_billing = json.load(handle)
rejected = 0
for sample in invalid_billing["samples"]:
    if "adapter" in sample:
        problems = adapter_violations(sample["adapter"])
    elif "invoice" in sample:
        problems = invoice_violations(sample["invoice"])
    else:
        fail(
            f"sample {sample['name']!r} carries neither an adapter "
            "nor an invoice payload"
        )
    if not problems:
        fail(
            f"seeded invalid billing sample {sample['name']!r} was "
            "accepted"
        )
    assert_named_rule_fired(
        sample["name"], sample["expected_rejection"], problems
    )
    rejected += 1
names = [sample["name"] for sample in invalid_billing["samples"]]
if "fork-like-core-mutation" not in names:
    fail("seeded billing set must include the fork-like core mutation")
print(
    f"Seeded billing rejections: {rejected} rejected "
    f"({', '.join(names)})"
)
PY

echo "Commercial contracts validation passed."
