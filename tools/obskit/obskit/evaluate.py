"""Evaluation stage for the obskit executor (Batch 17 Task 4).

Implements `obskit evaluate` (TR-04, TR-05, TR-18): from one
preflight-plus-discovery run, derive the four contracted artifacts -
capability matrix, compatibility result, mode recommendation, and
remediation list - and write them into --output-dir.

Contract-driven by construction: every grading rule, mode decision,
condition code, and remediation action is loaded at runtime from

- contracts/compatibility/COMPATIBILITY_MATRIX.json
- contracts/compatibility/GRADING_RULES.json
- contracts/compatibility/MODE_DECISION_TABLE.json
- contracts/compatibility/REMEDIATION_CATALOG.json
- contracts/compatibility/PROFILE_CATALOG.json

No version list, condition code, reason string, or remediation text is
hardcoded here (hardcoded_decision_rules: forbidden, per
contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml). The one
deliberate exception is the binding of the four blocked-condition
codes to the evaluation dimensions that raise them (see
BlockedCodeBindings): GRADING_RULES.json declares the codes but no
machine-readable mapping to dimensions, so the binding lives here as
dataclass field names that are validated against the contract's
blocked_conditions at load time and fail loudly on drift.

Capability matrix derivation rules (documented per Task 4)
----------------------------------------------------------

- storage: a PROFILE_CATALOG storage profile is a candidate iff the
  discovery report contains a StorageClass whose name equals the
  profile id exactly (the convention the reference contract fixtures
  use). The default is the profile of the cluster's default
  StorageClass when that profile is a candidate, else the catalog's
  default_profile when it is a candidate, else the first candidate.
- ingress_network / gitops_controller / secret: a catalog profile is
  a candidate iff the discovery probes report detects the
  same-named integration (probe names track PROFILE_CATALOG ids by
  design; see obskit.discovery). The default is the catalog's
  default_profile when it is a candidate, else the first candidate.
- Candidate lists preserve PROFILE_CATALOG declaration order - the
  contract's stated preference order - so output ordering is stable.

Compatibility grading rules
---------------------------

- Inputs: kubernetes_version and distribution from the reports (the
  two reports must describe the same cluster; a mismatch is an
  error), plus one selected profile per family enumerated by
  COMPATIBILITY_MATRIX.json "profiles". Versions are normalized to
  major.minor before matching.
- Discoverable families (storage, ingress_network, gitops_controller,
  secret) default from the capability matrix; non-discoverable ones
  (object_storage, identity) come from the --profiles JSON, which may
  also override any discoverable default. A family that is still
  unresolved, or resolved to an id absent from the matrix, raises the
  contracted missing_required_profile blocked condition.
- A matrix entry contributes its "conditions" list (empty for
  supported entries); an absent entry contributes the corresponding
  blocked-condition code. Grade selection is positional over the
  contract's grading_scale, ordered least to most restrictive: any
  blocked-condition reason selects the last grade, any reason at all
  selects the middle grade, no reasons selects the first.
- Preflight folding: a preflight check with status "fail" or "warn"
  whose reason_code is defined by REMEDIATION_CATALOG.json is folded
  into the reasons (e.g. gateway_api_crds_required). Codes the
  catalog does not define (executor-internal statuses such as
  skipped_cluster_unreachable) are not compatibility conditions and
  are not folded. Folded reasons follow matrix-derived reasons, in
  preflight check order; duplicates keep first position.
- Profile prerequisite observation is out of executor scope (most
  PROFILE_CATALOG prerequisites are not cluster-observable), so the
  pipeline passes an empty missing_prerequisites list; the parameter
  exists on grade_compatibility for contract-sample parity and for
  the Batch 18 installer, which does collect declared prerequisites.

Mode recommendation rules
-------------------------

- MODE_DECISION_TABLE.json rules are evaluated in ascending priority;
  the first rule whose "when" clause fully matches the inputs wins.
  No matching rule is a contract-coverage error, raised loudly.
- has_compatible_existing_services in "auto" derives from the
  discovery probes deterministically: true iff at least one GitOps
  controller is detected AND at least one service is an onboardable
  candidate. Rationale: a detected controller proves an attach-capable
  delivery plane exists, and onboardable services prove there are
  telemetry-producing workloads worth attaching to; both are stable
  structural facts of the snapshot (TR-18 determinism).

Determinism (TR-18): no timestamps, stable ordering everywhere, all
four artifacts serialized via obskit.emit.write_report (sorted keys,
fixed indentation, trailing newline). Identical inputs produce
byte-identical outputs.
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from obskit.emit import write_report
from obskit.models import REPORT_VERSION

GENERATED_BY = "obskit"

CAPABILITY_MATRIX_FILENAME = "capability_matrix.json"
COMPATIBILITY_RESULT_FILENAME = "compatibility_result.json"
MODE_RECOMMENDATION_FILENAME = "mode_recommendation.json"
REMEDIATION_LIST_FILENAME = "remediation_list.json"

# Contract files relative to --contracts-dir. These are the four rule
# sources named by EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml plus the
# profile catalog that drives capability-matrix derivation.
_CONTRACT_PATHS: dict[str, str] = {
    "compatibility_matrix": "compatibility/COMPATIBILITY_MATRIX.json",
    "grading_rules": "compatibility/GRADING_RULES.json",
    "mode_decision_table": "compatibility/MODE_DECISION_TABLE.json",
    "remediation_catalog": "compatibility/REMEDIATION_CATALOG.json",
    "profile_catalog": "compatibility/PROFILE_CATALOG.json",
}

# Capability-matrix key that supplies each discoverable family's
# default profile. object_storage and identity are absent by design:
# they are not cluster-observable and must come from --profiles.
_DISCOVERABLE_FAMILY_DEFAULTS: dict[str, str] = {
    "storage": "default_storage_profile",
    "ingress_network": "default_ingress_profile",
    "gitops_controller": "default_gitops_controller",
    "secret": "default_secret_profile",
}

# Preflight statuses whose reason codes are eligible for folding into
# compatibility reasons (report vocabulary, not a grading rule).
_FOLDABLE_PREFLIGHT_STATUSES: frozenset[str] = frozenset({"fail", "warn"})


class EvaluationError(RuntimeError):
    """Raised for missing inputs, malformed contracts, or rule gaps."""


@dataclass(frozen=True)
class CompatibilityContracts:
    """The five contract documents the evaluation stage interprets."""

    compatibility_matrix: dict[str, Any]
    grading_rules: dict[str, Any]
    mode_decision_table: dict[str, Any]
    remediation_catalog: dict[str, Any]
    profile_catalog: dict[str, Any]


@dataclass(frozen=True)
class BlockedCodeBindings:
    """Binding of blocked-condition codes to evaluation dimensions.

    Each field NAME is itself the contract code (the contract's codes
    are the binding key); resolve_blocked_codes fills each field with
    that same code only after proving GRADING_RULES.json still
    declares it, so contract drift fails at load time instead of
    silently emitting undeclared reasons.
    """

    unsupported_kubernetes_version: str
    unsupported_distribution: str
    missing_required_profile: str
    missing_prerequisite: str


@dataclass(frozen=True)
class GradeResult:
    """Outcome of compatibility grading."""

    grade: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ModeDecision:
    """Outcome of mode resolution: the winning rule and its mode."""

    mode: str
    rule_id: str
    rationale: str


@dataclass(frozen=True)
class ModeFlags:
    """Mode inputs taken from CLI flags.

    has_compatible_existing_services is None for "auto", which defers
    to the deterministic derivation from the discovery probes.
    """

    evaluation_only: bool
    allow_new_backend_components: bool
    require_in_cluster_collectors: bool
    has_compatible_existing_services: bool | None


@dataclass(frozen=True)
class EvaluationArtifacts:
    """The four artifact payloads emitted by one evaluate run."""

    capability_matrix: dict[str, Any]
    compatibility_result: dict[str, Any]
    mode_recommendation: dict[str, Any]
    remediation_list: dict[str, Any]


def _expect(mapping: Mapping[str, Any], key: str, context: str) -> Any:
    if not isinstance(mapping, Mapping) or key not in mapping:
        raise EvaluationError(
            f"{context}: missing required key {key!r}"
        )
    return mapping[key]


def _load_json(path: str, context: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except OSError as exc:
        raise EvaluationError(f"{context}: cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(
            f"{context}: malformed JSON in {path}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise EvaluationError(
            f"{context}: {path} must contain a JSON object"
        )
    return loaded


def load_contracts(contracts_dir: str) -> CompatibilityContracts:
    """Load and shape-check the compatibility contract set."""
    root = Path(contracts_dir)
    documents = {
        name: _load_json(str(root / relative), f"contract {name}")
        for name, relative in _CONTRACT_PATHS.items()
    }
    return CompatibilityContracts(**documents)


def resolve_blocked_codes(
    grading_rules: Mapping[str, Any],
) -> BlockedCodeBindings:
    """Validate every bound blocked code against GRADING_RULES.json."""
    declared = {
        _expect(item, "code", "grading_rules blocked_conditions entry")
        for item in _expect(
            grading_rules, "blocked_conditions", "grading_rules"
        )
    }
    bound = {binding.name for binding in fields(BlockedCodeBindings)}
    missing = sorted(bound - declared)
    if missing:
        raise EvaluationError(
            "grading_rules: blocked_conditions no longer declares "
            f"codes {missing!r}"
        )
    unbound = sorted(declared - bound)
    if unbound:
        raise EvaluationError(
            "grading_rules: blocked_conditions declares codes with no "
            f"executor binding: {unbound!r}; extend BlockedCodeBindings "
            "before shipping the contract change"
        )
    return BlockedCodeBindings(**{name: name for name in sorted(bound)})


def _normalize_version(value: str, context: str) -> str:
    """Reduce a Kubernetes version to the matrix's major.minor form."""
    parts = value.removeprefix("v").split(".")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise EvaluationError(
            f"{context}: unparseable kubernetes version {value!r}"
        )
    return ".".join(parts[:2])


def _matrix_entry(
    entries: Sequence[Mapping[str, Any]],
    key_field: str,
    value: str,
) -> Mapping[str, Any] | None:
    for entry in entries:
        if entry.get(key_field) == value:
            return entry
    return None


def _dedupe(reasons: Sequence[str]) -> tuple[str, ...]:
    """Drop duplicates, keeping each reason's first position."""
    seen: set[str] = set()
    ordered: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            ordered.append(reason)
    return tuple(ordered)


def _cluster_identity(
    report: Mapping[str, Any], context: str
) -> tuple[str, str, str]:
    cluster = _expect(report, "cluster", context)
    return (
        _expect(cluster, "name", f"{context} cluster"),
        _expect(cluster, "kubernetes_version", f"{context} cluster"),
        _expect(cluster, "distribution", f"{context} cluster"),
    )


def _candidates(
    catalog_family: Mapping[str, Any],
    observed: Sequence[str],
    family: str,
) -> list[str]:
    """Catalog profiles observed in the cluster, in catalog order."""
    observed_set = set(observed)
    profiles = _expect(
        catalog_family, "profiles", f"profile_catalog {family}"
    )
    return [pid for pid in profiles if pid in observed_set]


def _default_from_candidates(
    catalog_family: Mapping[str, Any],
    candidates: Sequence[str],
    preferred: str | None = None,
) -> str | None:
    """Pick a family default: observed preference, catalog, first."""
    if preferred is not None and preferred in candidates:
        return preferred
    catalog_default = catalog_family.get("default_profile")
    if catalog_default in candidates:
        return catalog_default
    return candidates[0] if candidates else None


def _detected_names(probe_items: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        item["name"]
        for item in probe_items
        if item.get("detected") is True
    ]


def build_capability_matrix(
    discovery_report: Mapping[str, Any],
    profile_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive the capability matrix from one discovery probes report.

    Shape follows contracts/discovery/GENERATED_CAPABILITY_MATRIX.json.
    Derivation rules are documented in the module docstring.
    """
    cluster_name, _, _ = _cluster_identity(
        discovery_report, "discovery report"
    )
    probes = _expect(discovery_report, "probes", "discovery report")
    storage_and_ingress = _expect(
        probes, "storage_and_ingress", "discovery probes"
    )
    gitops_and_secrets = _expect(
        probes, "gitops_and_secrets", "discovery probes"
    )

    storage_catalog = _expect(profile_catalog, "storage", "profile_catalog")
    storage_classes = _expect(
        storage_and_ingress, "storage_classes", "storage_and_ingress probe"
    )
    storage_candidates = _candidates(
        storage_catalog,
        [item["name"] for item in storage_classes],
        "storage",
    )
    default_class = next(
        (
            item["name"]
            for item in storage_classes
            if item.get("default") is True
        ),
        None,
    )
    default_storage = _default_from_candidates(
        storage_catalog, storage_candidates, preferred=default_class
    )

    ingress_catalog = _expect(
        profile_catalog, "ingress_network", "profile_catalog"
    )
    ingress_candidates = _candidates(
        ingress_catalog,
        _detected_names(
            _expect(
                storage_and_ingress,
                "ingress_controllers",
                "storage_and_ingress probe",
            )
        ),
        "ingress_network",
    )

    gitops_catalog = _expect(
        profile_catalog, "gitops_controller", "profile_catalog"
    )
    gitops_candidates = _candidates(
        gitops_catalog,
        _detected_names(
            _expect(
                gitops_and_secrets,
                "gitops_controllers",
                "gitops_and_secrets probe",
            )
        ),
        "gitops_controller",
    )

    secret_catalog = _expect(profile_catalog, "secret", "profile_catalog")
    secret_candidates = _candidates(
        secret_catalog,
        _detected_names(
            _expect(
                gitops_and_secrets,
                "secret_integrations",
                "gitops_and_secrets probe",
            )
        ),
        "secret",
    )

    return {
        "metadata": _artifact_metadata(cluster_name),
        "capabilities": {
            "storage_profile_candidates": storage_candidates,
            "default_storage_profile": default_storage,
            "ingress_profile_candidates": ingress_candidates,
            "default_ingress_profile": _default_from_candidates(
                ingress_catalog, ingress_candidates
            ),
            "gitops_controller_candidates": gitops_candidates,
            "default_gitops_controller": _default_from_candidates(
                gitops_catalog, gitops_candidates
            ),
            "secret_profile_candidates": secret_candidates,
            "default_secret_profile": _default_from_candidates(
                secret_catalog, secret_candidates
            ),
        },
    }


def resolve_profiles(
    required_families: Sequence[str],
    capabilities: Mapping[str, Any],
    overrides: Mapping[str, str],
) -> dict[str, str | None]:
    """Resolve one selected profile per required family.

    Overrides (--profiles) win; discoverable families then default
    from the capability matrix; anything else stays None and grades
    as the contracted missing_required_profile condition.
    """
    unknown = sorted(set(overrides) - set(required_families))
    if unknown:
        raise EvaluationError(
            "profiles file names unknown profile families: "
            + ", ".join(unknown)
        )
    for family, value in overrides.items():
        if not isinstance(value, str):
            raise EvaluationError(
                f"profiles file: {family} must map to a string profile id"
            )
    resolved: dict[str, str | None] = {}
    for family in required_families:
        if family in overrides:
            resolved[family] = overrides[family]
            continue
        capability_key = _DISCOVERABLE_FAMILY_DEFAULTS.get(family)
        resolved[family] = (
            capabilities.get(capability_key)
            if capability_key is not None
            else None
        )
    return resolved


def grade_compatibility(
    kubernetes_version: str,
    distribution: str,
    profiles: Mapping[str, str | None],
    missing_prerequisites: Sequence[str],
    extra_conditions: Sequence[str],
    compatibility_matrix: Mapping[str, Any],
    grading_rules: Mapping[str, Any],
) -> GradeResult:
    """Grade one cluster evaluation strictly from contract data.

    Reason order is the evaluation order: kubernetes version
    conditions, distribution conditions, profile conditions per the
    matrix's "profiles" key order, missing-prerequisite code, then
    extra (preflight-folded) conditions; duplicates keep their first
    position. This reproduces the GRADING_RULES.json
    sample_cluster_evaluations exactly.
    """
    codes = resolve_blocked_codes(grading_rules)
    kubernetes = _expect(
        compatibility_matrix, "kubernetes", "compatibility_matrix"
    )
    raw_reasons: list[str] = []

    version_entry = _matrix_entry(
        _expect(kubernetes, "versions", "compatibility_matrix kubernetes"),
        "version",
        _normalize_version(kubernetes_version, "grading input"),
    )
    if version_entry is None:
        raw_reasons.append(codes.unsupported_kubernetes_version)
    else:
        raw_reasons.extend(version_entry.get("conditions", ()))

    distribution_entry = _matrix_entry(
        _expect(
            kubernetes, "distributions", "compatibility_matrix kubernetes"
        ),
        "name",
        distribution,
    )
    if distribution_entry is None:
        raw_reasons.append(codes.unsupported_distribution)
    else:
        raw_reasons.extend(distribution_entry.get("conditions", ()))

    matrix_profiles = _expect(
        compatibility_matrix, "profiles", "compatibility_matrix"
    )
    for family, entries in matrix_profiles.items():
        selected = profiles.get(family)
        entry = (
            _matrix_entry(entries, "id", selected)
            if selected is not None
            else None
        )
        if entry is None:
            raw_reasons.append(codes.missing_required_profile)
        else:
            raw_reasons.extend(entry.get("conditions", ()))

    if missing_prerequisites:
        raw_reasons.append(codes.missing_prerequisite)
    raw_reasons.extend(extra_conditions)

    reasons = _dedupe(raw_reasons)
    scale = _expect(grading_rules, "grading_scale", "grading_rules")
    if len(scale) != 3:
        raise EvaluationError(
            "grading_rules: grading_scale must declare exactly three "
            "grades, least to most restrictive"
        )
    supported_grade, conditional_grade, blocked_grade = scale
    blocked_codes = {
        item["code"]
        for item in _expect(
            grading_rules, "blocked_conditions", "grading_rules"
        )
    }
    if any(reason in blocked_codes for reason in reasons):
        grade = blocked_grade
    elif reasons:
        grade = conditional_grade
    else:
        grade = supported_grade
    return GradeResult(grade=grade, reasons=reasons)


def preflight_conditions(
    preflight_report: Mapping[str, Any],
    remediation_catalog: Mapping[str, Any],
) -> tuple[str, ...]:
    """Fold preflight failures into contract-defined condition codes.

    Only reason codes REMEDIATION_CATALOG.json defines participate in
    compatibility grading; executor-internal codes do not.
    """
    known = set(
        _expect(remediation_catalog, "remediations", "remediation_catalog")
    )
    folded = [
        check["reason_code"]
        for check in _expect(preflight_report, "checks", "preflight report")
        if check.get("status") in _FOLDABLE_PREFLIGHT_STATUSES
        and check.get("reason_code") in known
    ]
    return _dedupe(folded)


def derive_has_compatible_existing_services(
    discovery_report: Mapping[str, Any],
) -> bool:
    """Deterministic "auto" input for the mode decision table.

    True iff a GitOps controller is detected AND at least one service
    is an onboardable candidate (see module docstring for rationale).
    """
    probes = _expect(discovery_report, "probes", "discovery report")
    gitops_and_secrets = _expect(
        probes, "gitops_and_secrets", "discovery probes"
    )
    controller_detected = any(
        item.get("detected") is True
        for item in _expect(
            gitops_and_secrets,
            "gitops_controllers",
            "gitops_and_secrets probe",
        )
    )
    inventory = _expect(
        probes, "workload_inventory", "discovery probes"
    )
    onboardable = any(
        item.get("onboardable_candidate") is True
        for item in _expect(inventory, "services", "workload_inventory")
    )
    return controller_detected and onboardable


def resolve_mode(
    inputs: Mapping[str, bool],
    mode_decision_table: Mapping[str, Any],
) -> ModeDecision:
    """First matching rule in ascending priority order wins."""
    rules = sorted(
        _expect(mode_decision_table, "rules", "mode_decision_table"),
        key=lambda rule: (rule["priority"], rule["id"]),
    )
    supported_modes = mode_decision_table.get("metadata", {}).get(
        "supported_modes"
    )
    for rule in rules:
        when = _expect(rule, "when", f"mode rule {rule.get('id')!r}")
        unknown = sorted(set(when) - set(inputs))
        if unknown:
            raise EvaluationError(
                f"mode rule {rule.get('id')!r} references inputs the "
                "executor does not supply: " + ", ".join(unknown)
            )
        if all(inputs[key] == value for key, value in when.items()):
            mode = _expect(
                rule, "recommend", f"mode rule {rule.get('id')!r}"
            )
            if supported_modes is not None and mode not in supported_modes:
                raise EvaluationError(
                    f"mode rule {rule.get('id')!r} recommends "
                    f"{mode!r}, not a declared supported mode"
                )
            return ModeDecision(
                mode=mode,
                rule_id=_expect(rule, "id", "mode rule"),
                rationale=rule.get("rationale", ""),
            )
    raise EvaluationError(
        "mode decision table has no rule matching inputs: "
        + json.dumps(dict(sorted(inputs.items())), sort_keys=True)
    )


def build_remediation_entries(
    reasons: Sequence[str],
    remediation_catalog: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """One catalog-sourced entry per reason, in reason order."""
    remediations = _expect(
        remediation_catalog, "remediations", "remediation_catalog"
    )
    entries: list[dict[str, Any]] = []
    for reason in reasons:
        if reason not in remediations:
            raise EvaluationError(
                f"remediation_catalog defines no entry for reason "
                f"{reason!r}"
            )
        item = remediations[reason]
        entries.append(
            {
                "reason": reason,
                "severity": _expect(
                    item, "severity", f"remediation {reason}"
                ),
                "actions": list(
                    _expect(item, "actions", f"remediation {reason}")
                ),
            }
        )
    return entries


def _artifact_metadata(cluster_name: str) -> dict[str, str]:
    """Metadata block shared by all four artifacts.

    Deliberately timestamp-free (TR-18 byte-identical outputs); shape
    follows contracts/discovery/GENERATED_CAPABILITY_MATRIX.json.
    """
    return {
        "version": REPORT_VERSION,
        "generated_by": GENERATED_BY,
        "cluster_name": cluster_name,
    }


def evaluate_reports(
    preflight_report: Mapping[str, Any],
    discovery_report: Mapping[str, Any],
    contracts: CompatibilityContracts,
    profile_overrides: Mapping[str, str],
    mode_flags: ModeFlags,
    input_refs: Mapping[str, str],
) -> EvaluationArtifacts:
    """Pure evaluation pipeline: reports plus contracts in, four
    artifact payloads out. No I/O, no clock, no environment reads."""
    preflight_cluster = _cluster_identity(
        preflight_report, "preflight report"
    )
    discovery_cluster = _cluster_identity(
        discovery_report, "discovery report"
    )
    if preflight_cluster != discovery_cluster:
        raise EvaluationError(
            "preflight and discovery reports describe different "
            f"clusters: {preflight_cluster!r} vs {discovery_cluster!r}"
        )
    cluster_name, kubernetes_version, distribution = discovery_cluster

    capability_matrix = build_capability_matrix(
        discovery_report, contracts.profile_catalog
    )
    required_families = list(
        _expect(
            contracts.compatibility_matrix,
            "profiles",
            "compatibility_matrix",
        )
    )
    profiles = resolve_profiles(
        required_families,
        capability_matrix["capabilities"],
        profile_overrides,
    )
    grade_result = grade_compatibility(
        kubernetes_version=kubernetes_version,
        distribution=distribution,
        profiles=profiles,
        missing_prerequisites=(),
        extra_conditions=preflight_conditions(
            preflight_report, contracts.remediation_catalog
        ),
        compatibility_matrix=contracts.compatibility_matrix,
        grading_rules=contracts.grading_rules,
    )

    if mode_flags.has_compatible_existing_services is None:
        has_compatible = derive_has_compatible_existing_services(
            discovery_report
        )
        compatible_source = "derived"
    else:
        has_compatible = mode_flags.has_compatible_existing_services
        compatible_source = "flag"
    mode_inputs: dict[str, bool] = {
        "evaluation_only": mode_flags.evaluation_only,
        "allow_new_backend_components": (
            mode_flags.allow_new_backend_components
        ),
        "require_in_cluster_collectors": (
            mode_flags.require_in_cluster_collectors
        ),
        "has_compatible_existing_services": has_compatible,
    }
    decision = resolve_mode(mode_inputs, contracts.mode_decision_table)

    remediation_entries = build_remediation_entries(
        grade_result.reasons, contracts.remediation_catalog
    )
    flat_actions = [
        action
        for entry in remediation_entries
        for action in entry["actions"]
    ]

    metadata = _artifact_metadata(cluster_name)
    compatibility_result = {
        "metadata": metadata,
        "input_refs": dict(input_refs),
        "compatibility_result": {
            "grade": grade_result.grade,
            "reasons": list(grade_result.reasons),
            "recommended_deployment_mode": decision.mode,
            "remediation_list": flat_actions,
        },
    }
    mode_recommendation = {
        "metadata": metadata,
        "inputs": {
            **mode_inputs,
            "has_compatible_existing_services_source": compatible_source,
        },
        "decision": {
            "rule_id": decision.rule_id,
            "recommended_mode": decision.mode,
            "rationale": decision.rationale,
        },
    }
    remediation_list = {
        "metadata": metadata,
        "remediations": remediation_entries,
    }
    return EvaluationArtifacts(
        capability_matrix=capability_matrix,
        compatibility_result=compatibility_result,
        mode_recommendation=mode_recommendation,
        remediation_list=remediation_list,
    )


def _mode_flags_from_args(args: Namespace) -> ModeFlags:
    tri_state = args.has_compatible_existing_services
    return ModeFlags(
        evaluation_only=bool(args.evaluation_only),
        allow_new_backend_components=(
            args.allow_new_backend_components == "true"
        ),
        require_in_cluster_collectors=(
            args.require_in_cluster_collectors == "true"
        ),
        has_compatible_existing_services=(
            None if tri_state == "auto" else tri_state == "true"
        ),
    )


def run(args: Namespace) -> int:
    """CLI entry point for `obskit evaluate` (routed from obskit.cli).

    Exit 0 on success regardless of grade; non-zero on errors
    (missing inputs, malformed contracts, mode-rule gaps).
    """
    try:
        preflight_report = _load_json(args.preflight, "preflight report")
        discovery_report = _load_json(args.discovery, "discovery report")
        contracts = load_contracts(args.contracts_dir)
        profile_overrides: Mapping[str, str] = (
            _load_json(args.profiles, "profiles file")
            if args.profiles
            else {}
        )
        output_dir = Path(args.output_dir)
        # input_refs record the input paths exactly as passed. The
        # capability matrix is not a passed input - it is the sibling
        # artifact this same run emits - so it is referenced relative
        # to the artifact's own directory. This keeps outputs
        # byte-identical across different --output-dir values for
        # identical inputs (TR-18).
        input_refs = {
            "preflight_report": args.preflight,
            "discovery_probes": args.discovery,
            "capability_matrix": CAPABILITY_MATRIX_FILENAME,
        }
        artifacts = evaluate_reports(
            preflight_report=preflight_report,
            discovery_report=discovery_report,
            contracts=contracts,
            profile_overrides=profile_overrides,
            mode_flags=_mode_flags_from_args(args),
            input_refs=input_refs,
        )
        for filename, payload in (
            (CAPABILITY_MATRIX_FILENAME, artifacts.capability_matrix),
            (
                COMPATIBILITY_RESULT_FILENAME,
                artifacts.compatibility_result,
            ),
            (
                MODE_RECOMMENDATION_FILENAME,
                artifacts.mode_recommendation,
            ),
            (REMEDIATION_LIST_FILENAME, artifacts.remediation_list),
        ):
            write_report(payload, str(output_dir / filename))
    except (EvaluationError, KeyError, TypeError, ValueError) as exc:
        print(f"obskit evaluate: error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"obskit evaluate: error: {exc}", file=sys.stderr)
        return 1
    return 0
