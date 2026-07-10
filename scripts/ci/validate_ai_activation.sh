#!/usr/bin/env bash
#
# Batch 24 validator: AI/MCP runtime activation (TB-24 | TR-13,
# TR-15, TR-24).
#
# Structural and offline: validates the model-provider ADR and
# adapter contract, the house-pattern adapter subtree with seeded
# rejections, the runtime's embedded contract constants against the
# governing YAML contracts (the runtime imports no YAML), the
# committed live evidence chain under artifacts/evidence/batch24/
# (deployment, rehearsal, signoff), and the extended AI runbooks -
# all WITHOUT a cluster, kind, or Docker. The live run itself is
# manual through scripts/dev/live_cluster_harness.sh (checks
# ai-deploy, ai-rehearsal, ai-signoff) and never gates pull requests.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# shellcheck source=scripts/ci/setup_python_env.sh
source scripts/ci/setup_python_env.sh

echo "Validating Batch 24 AI/MCP runtime activation..."

python3 - <<'PY'
import hashlib
import json
import sys
from datetime import datetime
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


# --------------------------------------------------------------
# 1. ADR and adapter contract
# --------------------------------------------------------------
adr8 = ROOT / "docs/adr/ADR_0008_MODEL_PROVIDER_ADAPTER.md"
adr9 = ROOT / "docs/adr/ADR_0009_AI_RUNTIME_ACTIVATION_STRATEGY.md"
for adr in (adr8, adr9):
    if not adr.is_file():
        err(f"missing ADR: {adr}")
if adr8.is_file():
    text = adr8.read_text()
    for needle in (
        "adapters/providers/",
        "Anthropic",
        "secrets backend",
        "MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml",
    ):
        if needle not in text:
            err(f"ADR-0008 does not record: {needle}")

contract = load_yaml("contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml")
if contract["key_resolution"]["secrets_backend_only"] is not True:
    err("adapter contract: key_resolution.secrets_backend_only must "
        "be true")
if "fork" not in contract["constraints"]["forbidden_wrap_methods"]:
    err("adapter contract must forbid the fork wrap method")
rule_names = {rule["rule"] for rule in contract["rejection_rules"]}
for expected in (
    "fail_if_inline_credential",
    "fail_if_git_tracked_credential",
    "fail_if_stub_in_production",
    "fail_if_fork_wrap",
):
    if expected not in rule_names:
        err(f"adapter contract missing rejection rule {expected}")

# --------------------------------------------------------------
# 2. House-pattern adapter subtree and catalog rules
# --------------------------------------------------------------
adapter_root = ROOT / "contracts" / ".."  # placeholder, replaced below
adapter_root = ROOT / contract["adapter_boundary"]["adapter_root"]
for name in contract["adapter_boundary"]["house_pattern_files"]:
    if not (adapter_root / name).is_file():
        err(f"adapter house pattern file missing: {name}")

catalog = load_yaml(
    "adapters/providers/model/"
    "MODEL_PROVIDER_ADAPTER_COMPATIBILITY_V1.yaml")
providers = {p["name"]: p for p in catalog["model_providers"]}


def catalog_violations(document) -> set[str]:
    """The rejection rules of the adapter contract, executable."""
    violations: set[str] = set()
    for provider in document.get("model_providers", []):
        for key, value in provider.items():
            if key in ("api_key", "token", "secret") and isinstance(
                    value, str) and not value.startswith("secretref:"):
                violations.add("fail_if_inline_credential")
        if provider.get("name") == "local-stub":
            profiles = set(provider.get("supported_profiles", []))
            if profiles & {"staging", "prod"}:
                violations.add("fail_if_stub_in_production")
    constraints = document.get("constraints", {})
    if "fork" in constraints.get("allowed_wrap_methods", []):
        violations.add("fail_if_fork_wrap")
    return violations


live_violations = catalog_violations(catalog)
if live_violations:
    err(f"shipped provider catalog violates: {sorted(live_violations)}")
if "local-stub" not in providers or "anthropic-reference" not in providers:
    err("provider catalog must carry local-stub and "
        "anthropic-reference")
anthropic = providers.get("anthropic-reference", {})
if "api_key_ref" not in anthropic.get("required_fields", []):
    err("anthropic-reference must require api_key_ref")

stub = load_yaml(
    "adapters/providers/model/ANTHROPIC_REFERENCE_ADAPTER_STUB_V1.yaml")
if stub["metadata"].get("contains_code") is not False \
        or stub["metadata"].get("performs_live_calls") is not False:
    err("Anthropic stub must declare contains_code/performs_live_calls "
        "false")
if not str(stub["auth"]["api_key_ref"]).startswith("secretref:"):
    err("Anthropic stub api_key_ref must be a secretref: reference")

# Seeded rejections, pinned to their named rule.
for fixture_name in (
    "SEEDED_INLINE_CREDENTIAL_CATALOG.json",
    "SEEDED_STUB_IN_PRODUCTION.json",
    "SEEDED_FORK_WRAP.json",
):
    fixture = load_json(f"tests/ai_activation/fixtures/{fixture_name}")
    expected_rule = fixture["expected_rejection_rule"]
    got = catalog_violations(fixture)
    if expected_rule not in got:
        err(f"seeded fixture {fixture_name} was not rejected by "
            f"{expected_rule} (got {sorted(got)})")

# --------------------------------------------------------------
# 3. Runtime constants vs governing contracts (no YAML at runtime)
# --------------------------------------------------------------
sys.path.insert(0, str(ROOT / "services" / "ai"))
from airuntime import contracts as rt  # noqa: E402

mcp_catalog = load_yaml("contracts/mcp/MCP_CATALOG_V1.yaml")
declared_services = {
    service["service"]: service["tools"][0]["name"]
    for service in mcp_catalog["services"]
}
runtime_services = {
    name: spec["tool"] for name, spec in rt.MCP_CATALOG.items()
}
if declared_services != runtime_services:
    err(f"runtime MCP catalog drift: contract={declared_services} "
        f"runtime={runtime_services}")

schema = load_json("contracts/mcp/TOOL_RESPONSE_SCHEMA_V1.json")
if tuple(schema["required"]) != rt.TOOL_RESPONSE_REQUIRED_FIELDS:
    err("runtime tool response required fields drift from "
        "TOOL_RESPONSE_SCHEMA_V1.json")

discovery = load_yaml("contracts/mcp/GATEWAY_DISCOVERY_CONTRACT_V1.yaml")
heartbeat = discovery["heartbeat_policy"]
timeout = discovery["timeout_policy"]
failover = discovery["failover_policy"]
checks = (
    (heartbeat["default_interval_seconds"],
     rt.HEARTBEAT_INTERVAL_SECONDS, "heartbeat interval"),
    (heartbeat["unhealthy_threshold_missed_heartbeats"],
     rt.UNHEALTHY_THRESHOLD_MISSED_HEARTBEATS, "unhealthy threshold"),
    (timeout["default_request_timeout_ms"],
     rt.DEFAULT_REQUEST_TIMEOUT_MS, "default timeout"),
    (timeout["upper_bound_request_timeout_ms"],
     rt.UPPER_BOUND_REQUEST_TIMEOUT_MS, "timeout upper bound"),
    (failover["fallback_mode"], rt.FAILOVER_FALLBACK_MODE,
     "failover mode"),
    (failover["retry_attempts"], rt.RETRY_ATTEMPTS, "retry attempts"),
)
for declared, embedded, label in checks:
    if declared != embedded:
        err(f"gateway {label} drift: contract={declared} "
            f"runtime={embedded}")

risk = load_yaml("contracts/policy/TOOL_RISK_CLASSIFICATION_V1.yaml")
declared_risk = {
    entry["tool"]: entry["risk_class"]
    for entry in risk["tool_mappings"]
}
if declared_risk != dict(rt.TOOL_RISK_CLASSES):
    err(f"tool risk classification drift: contract={declared_risk} "
        f"runtime={dict(rt.TOOL_RISK_CLASSES)}")

approval_flow = load_yaml("contracts/policy/APPROVAL_FLOW_V1.yaml")
for risk_class, embedded_rule in rt.APPROVAL_TIMEOUT_RULES.items():
    declared_rule = approval_flow["timeout_rules"][risk_class]
    for key in ("pending_timeout_minutes", "warning_threshold_minutes",
                "on_timeout"):
        if declared_rule[key] != embedded_rule[key]:
            err(f"approval timeout drift for {risk_class}.{key}")
declared_chain = tuple(
    (step["role"], step["sla_minutes"])
    for step in approval_flow["escalation_rules"]
    ["default_escalation_chain"]
)
if declared_chain != rt.ESCALATION_CHAIN:
    err("escalation chain drift between contract and runtime")

dedupe = load_yaml("triggers/khook/policies/DEDUPE_BURST_CONTROL_V1.yaml")
if dedupe["deduplication"]["window_seconds"] != rt.DEDUPE_WINDOW_SECONDS:
    err("dedupe window drift")
if dedupe["burst_control"]["per_key_max_events_per_window"] \
        != rt.BURST_MAX_PER_WINDOW:
    err("burst max drift")

hooks = load_yaml("triggers/khook/hooks/HOOK_CATALOG_V1.yaml")
declared_hooks = {
    hook["id"]: (hook["event_kind"], hook["event_reason"],
                 hook["severity"])
    for hook in hooks["hooks"]
}
if declared_hooks != {k: tuple(v) for k, v in rt.HOOKS.items()}:
    err("hook catalog drift between contract and runtime")

redaction = load_yaml("contracts/mcp/TENANCY_REDACTION_RULES_V1.yaml")
if tuple(redaction["scope_enforcement"]["required_scopes"]) \
        != rt.REQUIRED_SCOPES:
    err("required scopes drift")
if tuple(redaction["redaction_controls"]
         ["restricted_domain_deny_list"]) \
        != rt.RESTRICTED_DOMAIN_DENY_LIST:
    err("restricted domain deny list drift")

casefile_schema = load_json("contracts/ai/CASEFILE_SCHEMA_V1.json")
if tuple(casefile_schema["required"]) != rt.CASEFILE_REQUIRED_FIELDS:
    err("casefile required fields drift")

audit_schema = load_json("contracts/policy/AUDIT_EVENT_SCHEMA_V1.json")
if tuple(audit_schema["required"]) != rt.AUDIT_REQUIRED_FIELDS:
    err("audit event required fields drift")

bindings = load_yaml("agents/policies/TOOL_BINDINGS_V1.yaml")
if bindings["metadata"]["default_tool_policy"] != rt.DEFAULT_TOOL_POLICY:
    err("default tool policy drift")
declared_roles = {
    name: (set(spec.get("allow_risk_classes", [])),
           set(spec.get("deny_risk_classes", [])))
    for name, spec in bindings["role_bindings"].items()
}
runtime_roles = {
    name: (set(spec.get("allow_risk_classes", ())),
           set(spec.get("deny_risk_classes", ())))
    for name, spec in rt.ROLE_BINDINGS.items()
}
if declared_roles != runtime_roles:
    err(f"role bindings drift: contract={declared_roles} "
        f"runtime={runtime_roles}")
declared_agents = {
    name: (spec["class"], set(spec["tools"]))
    for name, spec in bindings["agent_tool_bindings"].items()
}
runtime_agents = {
    name: (spec["class"], set(spec["tools"]))
    for name, spec in rt.AGENT_TOOL_BINDINGS.items()
}
if declared_agents != runtime_agents:
    err(f"agent tool bindings drift: contract={declared_agents} "
        f"runtime={runtime_agents}")

action_contract = load_yaml("contracts/policy/ACTION_PRECONDITIONS_V1.yaml")
declared_actions = {
    entry["tool"]: {
        "approval": entry["execution_requirements"]
        ["requires_approval_status"],
        "requires_rollback_plan": entry["execution_requirements"].get(
            "requires_rollback_plan", False),
        "requires_change_ticket": entry["execution_requirements"].get(
            "requires_change_ticket", False),
    }
    for entry in action_contract["write_path_tools"]
}
runtime_actions = {
    tool: {
        "approval": spec["approval"],
        "requires_rollback_plan": spec.get("requires_rollback_plan", False),
        "requires_change_ticket": spec.get("requires_change_ticket", False),
    }
    for tool, spec in rt.ACTION_PRECONDITIONS.items()
}
if declared_actions != runtime_actions:
    err(f"action preconditions drift: contract={declared_actions} "
        f"runtime={runtime_actions}")
if action_contract["failure_behavior"] \
        != dict(rt.PRECONDITION_FAILURE_BEHAVIOR):
    err("action precondition failure behavior drift")

for risk_class, embedded_fields in rt.REQUIRED_APPROVAL_FIELDS.items():
    declared_fields = approval_flow["preconditions"][risk_class] \
        ["required_approval_fields"]
    if tuple(declared_fields) != tuple(embedded_fields):
        err(f"required approval fields drift for {risk_class}")

# --------------------------------------------------------------
# 4. Live evidence chain (deploy, rehearsal, signoff)
# --------------------------------------------------------------
harness_contract = load_yaml(
    "contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml")
activation = harness_contract["ai_activation"]
if activation["checks"] != ["ai-deploy", "ai-rehearsal", "ai-signoff"]:
    err("harness contract ai_activation.checks drift")
evidence_root = ROOT / activation["evidence"]["output_dir"]

required_artifacts = [
    artifact
    for group in activation["evidence"]["required_artifacts"].values()
    for artifact in group
]
for artifact in required_artifacts:
    if not (evidence_root / artifact).is_file():
        err(f"missing evidence artifact: {artifact}")

if ERRORS:
    # Evidence is missing or fundamentals are broken: report early,
    # the envelope checks below would only cascade.
    print("Batch 24 AI activation validation FAILED:")
    for message in ERRORS:
        print(f"  - {message}")
    sys.exit(1)


def load_envelope(relative: str):
    envelope = load_json(str(evidence_root.relative_to(ROOT)
                             / relative))
    if envelope.get("batch") != 24:
        err(f"{relative}: envelope batch is not 24")
    harness = envelope.get("harness", {})
    if harness.get("stack_profile") != "evidence-disposable":
        err(f"{relative}: stack_profile is not evidence-disposable")
    for key in ("artifact_kind", "captured_at", "status"):
        if key not in envelope:
            err(f"{relative}: envelope missing {key}")
    if envelope.get("status") != "pass":
        err(f"{relative}: status is not pass")
    return envelope


# Deploy evidence.
app_state = load_json(
    "artifacts/evidence/batch24/deploy/application_state.json")
if app_state["status"]["sync"]["status"] != "Synced" \
        or app_state["status"]["health"]["status"] != "Healthy":
    err("ai-runtime Application evidence is not Synced/Healthy")
if app_state["spec"]["source"]["path"] \
        != activation["gitops_source"]["path"]:
    err("ai-runtime Application path drift from harness contract")

pods = load_json(
    "artifacts/evidence/batch24/deploy/pod_inventory.json")["pods"]
expected_workloads = {
    "kagent-controller", "khook-controller", "kmcp-controller",
    "ai-gateway", "kagent-postgres", "incident-search-mcp",
    "graph-analysis-mcp", "trace-investigation-mcp",
    "metrics-correlation-mcp", "change-intelligence-mcp",
    "incident-casefile-mcp", "runbook-execution-mcp",
}
for workload in expected_workloads:
    matching = [p for p in pods if p["name"].startswith(workload)]
    if not matching:
        err(f"pod inventory missing workload {workload}")
    elif not any(p["ready"] and p["phase"] == "Running"
                 for p in matching):
        err(f"workload {workload} has no ready pod in evidence")
image = (f"{activation['runtime_image']['name']}:"
         f"{activation['runtime_image']['tag']}")
runtime_pods = [p for p in pods
                if not p["name"].startswith("kagent-postgres")]
for pod in runtime_pods:
    if not any(image in i for i in pod["images"]):
        err(f"pod {pod['name']} does not run {image}")

gateway_catalog = load_json(
    "artifacts/evidence/batch24/deploy/gateway_catalog.json")
services = {entry["service"]: entry
            for entry in gateway_catalog["services"]}
if set(services) != set(declared_services):
    err("gateway catalog evidence does not cover the MCP catalog")
for name, entry in services.items():
    if not entry.get("healthy") or not entry.get("registered"):
        err(f"gateway catalog: service {name} not healthy/registered")
if not gateway_catalog.get("contract_fingerprint"):
    err("gateway catalog evidence missing contract_fingerprint")

fingerprints = load_json(
    "artifacts/evidence/batch24/deploy/contract_fingerprints.json")
drifted = []
for relative, digest in fingerprints["sha256"].items():
    path = ROOT / relative
    if not path.is_file():
        drifted.append(f"{relative} (deleted)")
    elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        drifted.append(relative)
if drifted:
    err("governance surfaces changed since evidence capture "
        f"(re-run the live activation): {sorted(drifted)[:5]}")

load_envelope("deploy/evidence_manifest.json")

# Rehearsal evidence.
trigger_flow = load_envelope("rehearsal/trigger_flow.json")["payload"]
casefile = trigger_flow["casefile"]
missing = [field for field in rt.CASEFILE_REQUIRED_FIELDS
           if field not in casefile]
if missing:
    err(f"rehearsal casefile missing fields: {missing}")
if casefile["status"] != "resolved":
    err("rehearsal grant casefile did not resolve")
outcomes = [entry["outcome"] for entry in casefile["action_journal"]]
if "executed" not in outcomes:
    err("rehearsal grant casefile has no executed action")
approval_state = casefile["approval_state"]
if approval_state.get("status") != "approved":
    err("rehearsal grant approval_state is not approved")
if trigger_flow["approver"] == "ops-ceo-agent":
    err("rehearsal approver must be a human surrogate, not the "
        "requesting agent")

rejection = load_envelope("rehearsal/rejection_flow.json")["payload"]
if rejection["casefile"]["status"] != "rejected" \
        or "blocked" not in [
            entry["outcome"]
            for entry in rejection["casefile"]["action_journal"]]:
    err("rehearsal rejection did not feed the casefile as blocked")

timeout_drill = load_envelope(
    "rehearsal/timeout_drill.json")["payload"]
evaluation = timeout_drill["evaluation"]
if evaluation.get("state") != "expired" \
        or evaluation.get("outcome") != "deny-and-escalate":
    err("timeout drill did not enforce deny-and-escalate")
if not evaluation.get("escalation_events"):
    err("timeout drill produced no escalation events")

dedupe_evidence = load_envelope(
    "rehearsal/dedupe_burst.json")["payload"]
if dedupe_evidence["new_casefiles_after_duplicate"]:
    err("dedupe evidence shows a duplicate investigation")
khook_state = dedupe_evidence["khook_state"]
khook_counters = khook_state.get("counters", khook_state)
if khook_counters.get("deduped", 0) < 1:
    err("khook state shows no deduped events")

corpus = load_envelope("rehearsal/decision_corpus.json")["payload"]
if corpus["flows"] < 20:
    err("decision corpus smaller than 20 flows")

restore = load_envelope(
    "rehearsal/store_restore_drill.json")["payload"]
if restore.get("match") is not True:
    err("kagent store restore drill did not verify")

audit_trail = load_envelope("rehearsal/audit_trail.json")["payload"]
if not audit_trail["records"]:
    err("audit trail is empty")
# AUDIT_EVENT_SCHEMA_V1 governs tool-call and approval audit events;
# lightweight lifecycle records (status transitions, delegations)
# are casefile-trail entries, not AuditEventV1 instances. Every
# event of the governed classes must carry the full envelope, and
# each governed class must actually occur in the rehearsal.
GOVERNED_EVENT_TYPES = (
    "specialist-finding", "approval-decision", "action-executed",
    "approval-timeout-deny",
)
governed_counts = {event_type: 0 for event_type in GOVERNED_EVENT_TYPES}
for record in audit_trail["records"]:
    if record["event_type"] not in GOVERNED_EVENT_TYPES:
        continue
    governed_counts[record["event_type"]] += 1
    event = record["payload"]
    missing = [field for field in rt.AUDIT_REQUIRED_FIELDS
               if field not in event]
    if missing:
        err(f"audit record {record.get('record_id')} "
            f"({record['event_type']}) missing {missing}")
        break
for event_type, count in governed_counts.items():
    if count == 0:
        err(f"audit trail has no {event_type} events")
present_types = {r["event_type"] for r in audit_trail["records"]}
for required_type in ("approval-requested", "approval-escalation"):
    # timeout_rules.requires_audit_event and
    # escalation_audit_event_required (APPROVAL_FLOW_V1.yaml).
    if required_type not in present_types:
        err(f"audit trail has no {required_type} records")

# Signoff record.
signoff_envelope = load_envelope("signoff/signoff_record.json")
record = signoff_envelope["payload"]
expected_gates = {
    "mcp_tool_latency_p95", "mcp_tool_latency_p99",
    "approval_acceptance_rate", "approval_rejection_rate",
    "approval_p95_latency", "backtesting_evidence_pass_rate",
    "action_gate_scenario_coverage", "staging_action_gate_pass_rate",
    "release_validation_suite_pass_rate", "restore_drill_recency",
    "approval_flow_contract_presence",
}
recorded_gates = {gate["gate"] for gate in record["gates"]}
if recorded_gates != expected_gates:
    err(f"signoff gates drift: missing "
        f"{sorted(expected_gates - recorded_gates)}, unexpected "
        f"{sorted(recorded_gates - expected_gates)}")


def signoff_violations(candidate) -> set[str]:
    violations: set[str] = set()
    for gate_record in candidate.get("gates", []):
        if not gate_record.get("measurable", True) \
                and gate_record.get("status") == "pass":
            violations.add("fail_if_unmeasured_gate_approved")
        if gate_record.get("status") != "pass" \
                and candidate.get("decision") == "approved":
            violations.add("fail_if_failed_gate_approved")
    if candidate.get("decision") == "approved" and any(
            not g.get("measurable", True)
            for g in candidate.get("gates", [])):
        violations.add("fail_if_unmeasured_gate_approved")
    return violations


if signoff_violations(record):
    err("committed signoff record violates the unmeasurable-gate "
        "rule (TR-24)")
for gate_record in record["gates"]:
    if gate_record["status"] != "pass":
        err(f"signoff gate failed: {gate_record['gate']}")
if record["decision"] != "approved":
    err(f"signoff decision is {record['decision']}, not approved")
for key in ("release_version", "approver", "signed_at",
            "residual_risk", "evidence_links"):
    if not record.get(key):
        err(f"signoff record missing {key}")
datetime.fromisoformat(record["signed_at"])

seeded_signoff = load_json(
    "tests/ai_activation/fixtures/"
    "SEEDED_UNMEASURED_APPROVED_SIGNOFF.json")
if "fail_if_unmeasured_gate_approved" not in signoff_violations(
        seeded_signoff["signoff_record"]):
    err("seeded unmeasured-approved signoff fixture was not rejected")

# --------------------------------------------------------------
# 5. Extended runbooks (Task 6)
# --------------------------------------------------------------
operator_guide = (ROOT / "docs/runbooks/AI_MCP_LAYER_OPERATOR_GUIDE.md")
approval_runbook = (ROOT / "docs/runbooks/AI_APPROVAL_FLOW_RUNBOOK.md")
guide_text = operator_guide.read_text() \
    if operator_guide.is_file() else ""
approval_text = approval_runbook.read_text() \
    if approval_runbook.is_file() else ""
for needle, where in (
    ("## Live Activation", "AI_MCP_LAYER_OPERATOR_GUIDE.md"),
    ("## Rollback to Scaffolding", "AI_MCP_LAYER_OPERATOR_GUIDE.md"),
    ("## Live Rehearsal", "AI_APPROVAL_FLOW_RUNBOOK.md"),
):
    text = guide_text if "OPERATOR" in where else approval_text
    if needle not in text:
        err(f"{where} missing section: {needle}")

if ERRORS:
    print("Batch 24 AI activation validation FAILED:")
    for message in ERRORS:
        print(f"  - {message}")
    sys.exit(1)

print("Batch 24 AI activation structural checks passed.")
PY

echo "Running AI runtime offline tests..."
python3 tests/ai_activation/test_runtime_offline.py > /dev/null
python3 tests/ai_activation/test_store_roundtrip.py > /dev/null
echo "AI runtime offline tests passed."

echo "AI activation validation passed."
