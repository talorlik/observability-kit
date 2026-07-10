#!/usr/bin/env bash
#
# Batch 25 validator: release engineering (TB-25 | TR-11, TR-12,
# TR-25).
#
# Structural and offline: validates the release engineering contract
# and its gates, the changelog convention, the tag-driven release
# workflow (SBOM + CVE scan, never PR-gated), the wrapped-system
# registry pins in lockstep with the harness sources, the license
# compliance contract against the registry and THIRD_PARTY_NOTICES.md,
# the production reference architecture against the Batch 2
# compatibility artifacts, the platform product SLO tier binding, the
# committed live evidence under artifacts/evidence/batch25/
# (release-pins, upgrade-drill), and the seeded rejection fixtures
# under tests/release/ - all WITHOUT a cluster, kind, or Docker. The
# live evidence capture itself is manual through
# scripts/dev/live_cluster_harness.sh (checks release-pins,
# upgrade-drill) and never gates pull requests.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# shellcheck source=scripts/ci/setup_python_env.sh
source scripts/ci/setup_python_env.sh

echo "Validating Batch 25 release engineering..."

python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path.cwd()
ERRORS: list[str] = []


def err(message: str) -> None:
    ERRORS.append(message)


def load_yaml(path: str):
    return yaml.safe_load((ROOT / path).read_text())


def load_json(path: str):
    return json.loads((ROOT / path).read_text())


_ERR_MARK = 0


def section(number: int, title: str) -> None:
    """Report the previous section's outcome via the error ledger."""
    global _ERR_MARK
    status = "OK" if len(ERRORS) == _ERR_MARK else "FAILED"
    print(f"check {number}: {title} ... {status}")
    _ERR_MARK = len(ERRORS)


# --------------------------------------------------------------
# 1. Release engineering contract: sections and hard gates
# --------------------------------------------------------------
release = load_yaml("contracts/release/RELEASE_ENGINEERING_CONTRACT_V1.yaml")
for key in (
    "metadata",
    "versioning",
    "changelog",
    "release_process",
    "publication",
    "signing",
    "sbom_and_scanning",
    "upgrade_policy",
    "wrapped_system_pins",
    "release_gates",
):
    if key not in release:
        err(f"release contract missing top-level section: {key}")
if release["versioning"].get("scheme") != "semver-2.0.0":
    err("release contract versioning.scheme must be semver-2.0.0")
if release["release_process"].get("pull_request_gated") is not False:
    err("release contract release_process.pull_request_gated must be "
        "false: releases are tag-driven, never PR gates")
if release["metadata"].get("validated_by") != \
        "scripts/ci/validate_release_engineering.sh":
    err("release contract metadata.validated_by must name "
        "scripts/ci/validate_release_engineering.sh")
gate_ids = {g["id"] for g in release["release_gates"].get("required", [])}
for expected_gate in (
    "validators-green",
    "changelog-section",
    "pins-concrete",
    "license-inventory-complete",
    "sbom-and-scan",
    "harness-install-evidence",
    "upgrade-evidence",
):
    if expected_gate not in gate_ids:
        err(f"release contract missing required gate: {expected_gate}")
section(1, "release contract sections and gates")

# --------------------------------------------------------------
# 2. Changelog convention
# --------------------------------------------------------------
changelog_path = ROOT / "CHANGELOG.md"
if not changelog_path.is_file():
    err("CHANGELOG.md is missing")
else:
    changelog = changelog_path.read_text()
    if not re.search(r"^## \[Unreleased\]$", changelog, re.MULTILINE):
        err("CHANGELOG.md has no '## [Unreleased]' section (release "
            "contract changelog.sections_required)")
section(2, "changelog Unreleased section")

# --------------------------------------------------------------
# 3. Release workflow: tag-driven only, SBOM and scan present
# --------------------------------------------------------------
workflow = load_yaml(".github/workflows/release.yaml")
# PyYAML 1.1 parses a bare `on:` key as boolean True.
triggers = workflow.get("on", workflow.get(True))
if not isinstance(triggers, dict):
    err("release workflow: cannot read trigger block")
    triggers = {}
if set(triggers) != {"push", "workflow_dispatch"}:
    err("release workflow must trigger ONLY on push + "
        f"workflow_dispatch, found: {sorted(map(str, triggers))}")
if "pull_request" in triggers:
    err("release workflow must never trigger on pull_request")
push = triggers.get("push") or {}
if set(push) != {"tags"}:
    err("release workflow push trigger must be tag-only (no "
        f"branches), found: {sorted(map(str, push))}")
tags = push.get("tags") or []
if not tags or not all(str(t).startswith("v") for t in tags):
    err(f"release workflow must trigger on v* tags, found: {tags}")
step_runs: list[str] = []
for job in (workflow.get("jobs") or {}).values():
    for step in job.get("steps", []):
        step_runs.append(
            str(step.get("name", "")) + "\n" + str(step.get("run", "")))
steps_text = "\n".join(step_runs)
if "syft scan" not in steps_text:
    err("release workflow has no syft SBOM generation step")
if "spdx" not in steps_text.lower():
    err("release workflow SBOM step does not produce SPDX output")
if "trivy image" not in steps_text:
    err("release workflow has no trivy image scan step")
# The CVE gate must both select CRITICAL findings and actually fail
# the run on them: --severity CRITICAL and --exit-code 1 must appear
# in the SAME trivy invocation.
trivy_gates = [
    run for run in step_runs
    if "trivy image" in run and "--severity CRITICAL" in run]
if not trivy_gates:
    err("release workflow trivy scan does not gate on CRITICAL")
elif not any("--exit-code 1" in run for run in trivy_gates):
    err("release workflow trivy CRITICAL step does not fail the run "
        "(--exit-code 1 missing from the gating invocation)")
section(3, "release workflow tag-only triggers, SBOM and scan")

# --------------------------------------------------------------
# 4. Wrapped-system registry: pins concrete and in lockstep with
#    the harness sources
# --------------------------------------------------------------
registry = load_yaml("contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml")
registry_systems = registry["systems"]
registry_names = [system["system"] for system in registry_systems]
pins = {system["system"]: system.get("version_pin", {})
        for system in registry_systems}


def production_pin_violations(profile, systems) -> dict[str, list[str]]:
    """Registry rule fail_if_production_pin_missing, executable: a
    production install profile may not enable a wrapped system whose
    version_pin.status is not "pinned". Check 4 runs this gate on the
    shipped registry; the seeded rejection fixture (check 9) runs the
    SAME function, so the gate and its test cannot drift. Returns a
    map of violated rule id to the offending system names."""
    violations: dict[str, list[str]] = {}
    if profile.get("environment") != "production":
        return violations
    by_name = {system["system"]: system for system in systems}
    for name in profile.get("enabled_systems", []):
        entry = by_name.get(name)
        if entry is None:
            violations.setdefault(
                "fail_if_unregistered_system", []).append(name)
        elif entry.get("version_pin", {}).get("status") != "pinned":
            violations.setdefault(
                "fail_if_production_pin_missing", []).append(name)
    return violations


# The shipped registry must pass its own production gate: a
# production profile enabling every registered system yields no
# violations (release gate pins-concrete).
shipped_violations = production_pin_violations(
    {"environment": "production", "enabled_systems": registry_names},
    registry_systems)
for rule, offenders in sorted(shipped_violations.items()):
    err(f"shipped registry fails its own production pin gate "
        f"({rule}): {offenders}")

# Lockstep cross-check: the three formerly-open pins must match the
# exact versions the harness installs and proves.
backend = (ROOT / "scripts/dev/harness_assets/backend-opensearch.yaml")
backend_text = backend.read_text() if backend.is_file() else ""
if not backend_text:
    err("scripts/dev/harness_assets/backend-opensearch.yaml missing")


def image_tag(text: str, repo: str) -> str | None:
    match = re.search(
        rf"image:\s*{re.escape(repo)}:(\S+)", text)
    return match.group(1) if match else None


for system_name, image_repo in (
    ("opensearch", "opensearchproject/opensearch"),
    ("opensearch-dashboards", "opensearchproject/opensearch-dashboards"),
):
    expected = pins.get(system_name, {}).get("value")
    observed = image_tag(backend_text, image_repo)
    if expected is None or observed != str(expected):
        err(f"registry pin for {system_name} ({expected}) does not "
            f"match harness backend image tag ({observed})")

harness_text = (ROOT / "scripts/dev/live_cluster_harness.sh").read_text()
argocd_match = re.search(r"argo-cd/(v[0-9][^/]*)/manifests", harness_text)
argocd_observed = argocd_match.group(1) if argocd_match else None
argocd_expected = pins.get("argocd", {}).get("value")
if argocd_expected is None or argocd_observed != str(argocd_expected):
    err(f"registry pin for argocd ({argocd_expected}) does not match "
        f"harness ARGOCD_MANIFEST version ({argocd_observed})")
section(4, "registry pins concrete and lockstep with harness sources")

# --------------------------------------------------------------
# 5. License compliance: contract sections, inventory completeness,
#    bidirectional attribution cross-check
# --------------------------------------------------------------
license_contract = load_yaml(
    "contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml")
for key in (
    "metadata",
    "distribution_model",
    "license_inventory",
    "license_obligations",
    "attribution",
    "review_workflow",
):
    if key not in license_contract:
        err(f"license contract missing top-level section: {key}")
inventory = license_contract["license_inventory"]


def inventory_completeness_violations(
        registry_names, inventory_entries) -> set[str]:
    """Release gate license-inventory-complete, executable: every
    bundled system in the wrapped-system registry must appear in the
    license inventory (matched on registry_system)."""
    covered = {
        entry.get("registry_system")
        for entry in inventory_entries
        if entry.get("registry_system") is not None
    }
    if set(registry_names) - covered:
        return {"fail_if_bundled_system_missing_from_inventory"}
    return set()


live_violations = inventory_completeness_violations(
    registry_names, inventory)
if live_violations:
    missing = set(registry_names) - {
        entry.get("registry_system") for entry in inventory}
    err("license inventory is missing bundled registry systems: "
        f"{sorted(missing)}")

notices_path = ROOT / "THIRD_PARTY_NOTICES.md"
notices_text = notices_path.read_text() if notices_path.is_file() else ""
if not notices_text:
    err("THIRD_PARTY_NOTICES.md is missing")
notices_headings = set(
    re.findall(r"^### (\S+)$", notices_text, re.MULTILINE))
inventory_components = {entry["component"] for entry in inventory}
for component in sorted(inventory_components - notices_headings):
    err(f"license inventory entry {component} has no attribution "
        "heading in THIRD_PARTY_NOTICES.md")
for heading in sorted(notices_headings - inventory_components):
    err(f"THIRD_PARTY_NOTICES.md heading {heading} has no license "
        "inventory entry (the two must never drift)")
section(5, "license compliance inventory and attribution cross-check")

# --------------------------------------------------------------
# 6. Production reference architecture
# --------------------------------------------------------------
reference = load_yaml(
    "contracts/release/PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml")
for key in (
    "metadata",
    "scope",
    "ha_topology",
    "sizing_tiers",
    "storage_requirements",
    "ingress_requirements",
    "backup_and_dr",
    "prod_overlay_mapping",
    "conformance",
):
    if key not in reference:
        err(f"reference architecture missing top-level section: {key}")


def collect_ids(node, into: set[str]) -> None:
    if isinstance(node, dict):
        value = node.get("id")
        if isinstance(value, str):
            into.add(value)
        for child in node.values():
            collect_ids(child, into)
    elif isinstance(node, list):
        for child in node:
            collect_ids(child, into)


matrix_ids: set[str] = set()
collect_ids(load_json("contracts/compatibility/COMPATIBILITY_MATRIX.json"),
            matrix_ids)
for requirement_key in ("storage_requirements", "ingress_requirements"):
    accepted = reference.get(requirement_key, {}).get(
        "accepted_profiles", {})
    for family, profile_ids in accepted.items():
        for profile_id in profile_ids:
            if profile_id not in matrix_ids:
                err(f"reference architecture {requirement_key} "
                    f"references profile {profile_id!r} ({family}) "
                    "that is not in the Batch 2 compatibility matrix")
overlay_file = reference.get("prod_overlay_mapping", {}).get("file")
if not overlay_file or not (ROOT / overlay_file).is_file():
    err(f"reference architecture prod overlay file missing: "
        f"{overlay_file}")
section(6, "production reference architecture and profile bindings")

# --------------------------------------------------------------
# 7. Platform product SLO: tier binding and isolation budget
# --------------------------------------------------------------
slo = load_yaml("contracts/slo_ops/PLATFORM_PRODUCT_SLO_V1.yaml")
for key in (
    "metadata",
    "scope",
    "tier_binding",
    "alerting_conventions",
    "slo_catalog",
    "error_budget_policy",
    "operational_binding",
    "status",
):
    if key not in slo:
        err(f"product SLO contract missing top-level section: {key}")
tenant_schema = load_json("contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json")
tier_enum = set(tenant_schema["properties"]["tier"]["enum"])
isolation = None
for entry in slo.get("slo_catalog", []):
    slo_id = entry.get("id", "<missing id>")
    tiers = set(entry.get("targets_by_tier", {}))
    if tiers != tier_enum:
        err(f"SLO {slo_id} targets_by_tier keys {sorted(tiers)} do "
            f"not exactly match the tenant tier enum "
            f"{sorted(tier_enum)}")
    if slo_id == "slo-product-tenant-isolation":
        isolation = entry
if isolation is None:
    err("product SLO catalog has no slo-product-tenant-isolation")
else:
    for tier, target in isolation.get("targets_by_tier", {}).items():
        if target != 0:
            err(f"isolation SLO must carry a zero violation budget "
                f"for every tier; tier {tier} has {target!r}")
section(7, "product SLO tier binding and isolation zero budget")

# --------------------------------------------------------------
# 8. Live evidence: harness contract section and committed artifacts
# --------------------------------------------------------------
harness_contract = load_yaml(
    "contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml")
release_section = harness_contract.get("release_engineering", {})
if release_section.get("batch") != 25:
    err("harness contract release_engineering.batch must be 25")
if release_section.get("validated_by") != \
        "scripts/ci/validate_release_engineering.sh":
    err("harness contract release_engineering.validated_by must name "
        "this validator")
if release_section.get("checks") != ["release-pins", "upgrade-drill"]:
    err("harness contract release_engineering.checks must be "
        "[release-pins, upgrade-drill]")
evidence = release_section.get("evidence", {})
output_dir = evidence.get("output_dir")
if output_dir != "artifacts/evidence/batch25":
    err(f"harness contract evidence.output_dir must be "
        f"artifacts/evidence/batch25, found {output_dir!r}")
envelope_batch = evidence.get("envelope_batch")
if envelope_batch != 25:
    err("harness contract evidence.envelope_batch must be 25")
required = evidence.get("required_artifacts", {})
required_paths = [
    path for group in required.values() for path in group]
for expected_path in ("release/release_pins.json",
                      "upgrade/upgrade_drill.json"):
    if expected_path not in required_paths:
        err(f"harness contract required_artifacts missing "
            f"{expected_path}")


def check_envelope(relative: str):
    """Load one committed evidence artifact and check its envelope."""
    full = ROOT / (output_dir or "artifacts/evidence/batch25") / relative
    if not full.is_file():
        err(f"committed evidence artifact missing: {full}")
        return None
    document = json.loads(full.read_text())
    if document.get("batch") != envelope_batch:
        err(f"{relative}: envelope batch must be {envelope_batch}")
    profile = document.get("harness", {}).get("stack_profile")
    if profile != "evidence-disposable":
        err(f"{relative}: stack_profile must be evidence-disposable "
            "(the dev-persistent stack is never an evidence source)")
    if document.get("status") != "pass":
        err(f"{relative}: status must be pass, found "
            f"{document.get('status')!r}")
    return document


pins_doc = check_envelope("release/release_pins.json")
if pins_doc is not None:
    payload = pins_doc.get("payload", {})
    if payload.get("remaining_to_be_pinned") != []:
        err("release_pins evidence: remaining_to_be_pinned must be "
            "an empty list")
    pinned_set = payload.get("pinned_set", {})
    for system_name in ("opensearch", "opensearch-dashboards", "argocd"):
        entry = pinned_set.get(system_name)
        if entry is None:
            err(f"release_pins evidence: pinned_set missing "
                f"{system_name}")
            continue
        if entry.get("match") is not True:
            err(f"release_pins evidence: {system_name} live image "
                "does not match its registry pin")
        expected_pin = pins.get(system_name, {}).get("value")
        if str(entry.get("expected_pin")) != str(expected_pin):
            err(f"release_pins evidence: {system_name} expected_pin "
                f"{entry.get('expected_pin')!r} drifted from the "
                f"registry pin {expected_pin!r}")

drill_doc = check_envelope("upgrade/upgrade_drill.json")
if drill_doc is not None:
    payload = drill_doc.get("payload", {})
    survival = payload.get("survival", {})
    seeded = survival.get("seeded_document", {})
    if seeded.get("found_after_upgrade") is not True:
        err("upgrade_drill evidence: seeded OpenSearch document was "
            "not found after the upgrade")
    if survival.get("rendered_values_sha256", {}).get("unchanged") \
            is not True:
        err("upgrade_drill evidence: rendered overlay values changed "
            "across the upgrade")
    if survival.get("gateway_configmap_sha256", {}).get("unchanged") \
            is not True:
        err("upgrade_drill evidence: collector gateway ConfigMap "
            "changed across the upgrade")
    chart = load_yaml("gitops/charts/platform-core/Chart.yaml")
    chart_version = str(chart.get("version"))
    upgraded = payload.get("upgraded", {})
    if str(upgraded.get("chart_version")) != chart_version:
        err(f"upgrade_drill evidence: upgraded chart_version "
            f"{upgraded.get('chart_version')!r} does not match "
            f"Chart.yaml version {chart_version!r}")
    if upgraded.get("gateway_version_label") != \
            upgraded.get("chart_version"):
        err("upgrade_drill evidence: gateway version label did not "
            "roll to the upgraded chart version")
    application = payload.get("application", {})
    if application.get("sync") != "Synced" or \
            application.get("health") != "Healthy":
        err("upgrade_drill evidence: Application must end Synced and "
            "Healthy")
section(8, "committed live evidence (release-pins, upgrade-drill)")

# --------------------------------------------------------------
# 9. Seeded rejections: the SAME gate functions checks 4 and 5 run
#    on the shipped artifacts must reject the seeded bad inputs
# --------------------------------------------------------------
unpinned_fixture = load_json(
    "tests/release/fixtures/SEEDED_UNPINNED_PRODUCTION_PROFILE.json")
got = production_pin_violations(
    unpinned_fixture["install_profile"],
    unpinned_fixture["registry_systems"])
if unpinned_fixture["expected_rejection_rule"] not in got:
    err("seeded unpinned production profile fixture was NOT rejected "
        "by production_pin_violations (the check 4 gate)")
else:
    print("seeded rejection: unpinned production profile correctly "
          "rejected (fail_if_production_pin_missing)")

missing_fixture = load_json(
    "tests/release/fixtures/"
    "SEEDED_INVENTORY_MISSING_BUNDLED_SYSTEM.json")
got = inventory_completeness_violations(
    missing_fixture["registry_systems"],
    missing_fixture["license_inventory"])
if missing_fixture["expected_rejection_rule"] not in got:
    err("seeded incomplete license inventory fixture was NOT "
        "rejected by inventory_completeness_violations")
else:
    print("seeded rejection: license inventory missing a bundled "
          "system correctly rejected "
          "(fail_if_bundled_system_missing_from_inventory)")
section(9, "seeded rejection fixtures")

# --------------------------------------------------------------
# 10. ADR-0010
# --------------------------------------------------------------
adr = ROOT / "docs/adr/ADR_0010_RELEASE_ENGINEERING.md"
if not adr.is_file():
    err("missing ADR: docs/adr/ADR_0010_RELEASE_ENGINEERING.md")
elif "RELEASE_ENGINEERING_CONTRACT_V1.yaml" not in adr.read_text():
    err("ADR-0010 does not mention the release engineering contract")
section(10, "ADR-0010 recorded")

if ERRORS:
    print("Batch 25 release engineering validation FAILED:")
    for message in ERRORS:
        print(f"  - {message}")
    sys.exit(1)

print("Batch 25 release engineering structural checks passed.")
PY

echo "Release engineering validation passed."
