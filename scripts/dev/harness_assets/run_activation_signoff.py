"""Production activation go/no-go signoff execution (Batch 24 Task 4).

Executes docs/operations/PRODUCTION_ACTIVATION_SIGNOFF_WORKFLOW.md
against the live AI runtime on the disposable harness: every
quantitative threshold in the workflow's Go/No-Go table is measured
and recorded; a threshold that cannot be measured is recorded as a
FAILED gate (TR-24). The decision is `approved` only when every gate
passes; any failed gate forces `hold`.

Measurement sources, per gate:
- MCP tool latency: measured live (60 gateway invocations), against
  the criteria of tests/perf/ai_runtime/PERF_UPGRADE_SUITE_V1.json.
- Approval rates and latency: the live decision trail from the
  rehearsal (kagent audit store), the same trail the
  rca-approval-decision-trail dashboard panel reads in production.
- Backtesting: contracts/risk_rca/BACKTESTING_EVIDENCE_VALIDATION.json
  metrics against their minimum thresholds.
- Action-gate scenario coverage: the declared scenarios of
  tests/safety/action_gates/ACTION_GATE_SCENARIOS_V1.json replayed
  against the LIVE gateway policy enforcement.
- Staging action gates, release suite, restore recency, approval flow
  contract presence: their named fixture and contract sources.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SURROGATE_SIGNOFF_APPROVER = "release-approver-surrogate"
RESTORE_DRILL_CADENCE_DAYS = 90  # KAGENT_PERSISTENCE_CONTRACT_V1.yaml


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kagent-url", required=True)
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def http(method: str, url: str, body: dict | None = None,
         timeout: float = 35.0) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def percentile(samples: list[float], pct: float) -> float:
    ordered = sorted(samples)
    index = max(
        0, min(len(ordered) - 1,
               round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def gate(name: str, source: str, threshold: str,
         measured: Any, passed: bool | None,
         notes: str = "") -> dict:
    # passed=None means the gate could not be measured: per TR-24
    # an unmeasurable threshold is a FAILED gate.
    return {
        "gate": name,
        "source": source,
        "threshold": threshold,
        "measured": measured,
        "status": "pass" if passed else "fail",
        "measurable": passed is not None,
        "notes": notes,
    }


class Signoff:
    def __init__(self, args: argparse.Namespace) -> None:
        self.kagent = args.kagent_url.rstrip("/")
        self.gateway = args.gateway_url.rstrip("/")
        self.root = Path(args.repo_root)
        self.gates: list[dict] = []

    # -- gates -------------------------------------------------------

    def gate_mcp_latency(self) -> None:
        envelope = {
            "edge_version": "v1",
            "caller_agent": "incident-investigator",
            # agent_to_mcp envelopes carry the bare tool name; the
            # gateway derives the classified id as <tool>.<version>.
            "tool": "incident-search",
            "tool_version": "v1",
            "tenant_scope": {
                "namespace": "observability",
                "tenant": "tenant-demo",
                "team": "sre",
            },
            "input": {"query": "signoff latency probe"},
        }
        samples: list[float] = []
        failures = 0
        for _ in range(60):
            started = time.monotonic()
            status, _ = http(
                "POST", f"{self.gateway}/invoke", envelope)
            elapsed_ms = (time.monotonic() - started) * 1000
            if status == 200:
                samples.append(elapsed_ms)
            else:
                failures += 1
        source = ("live measurement (60 invocations); criteria: "
                  "tests/perf/ai_runtime/PERF_UPGRADE_SUITE_V1.json")
        if not samples:
            self.gates.append(gate(
                "mcp_tool_latency_p95", source, "<= 750 ms",
                None, None, "no successful invocations"))
            self.gates.append(gate(
                "mcp_tool_latency_p99", source, "<= 1500 ms",
                None, None, "no successful invocations"))
            return
        p95 = round(percentile(samples, 95), 2)
        p99 = round(percentile(samples, 99), 2)
        notes = f"{len(samples)} ok, {failures} failed"
        self.gates.append(gate(
            "mcp_tool_latency_p95", source, "<= 750 ms", p95,
            p95 <= 750 and failures == 0, notes))
        self.gates.append(gate(
            "mcp_tool_latency_p99", source, "<= 1500 ms", p99,
            p99 <= 1500 and failures == 0, notes))
        self.latency_samples = samples

    def gate_approval_rates(self) -> None:
        status, payload = http("GET", f"{self.kagent}/approvals")
        source = ("live decision trail (kagent audit store; the "
                  "rca-approval-decision-trail panel source)")
        if status != 200:
            self.gates.append(gate(
                "approval_acceptance_rate", source,
                ">= 90 % over the last 100 decisions", None, None,
                "approvals endpoint unreachable"))
            self.gates.append(gate(
                "approval_rejection_rate", source,
                "<= 25 % over the last 100 decisions", None, None,
                "approvals endpoint unreachable"))
            self.gates.append(gate(
                "approval_p95_latency", source,
                "<= 30 minutes for write.high-risk", None, None,
                "approvals endpoint unreachable"))
            return
        approvals = payload["approvals"] if isinstance(payload, dict) \
            else payload
        decided = [
            a for a in approvals
            if a.get("decision") in ("approved", "rejected")
            and a.get("decided_at")
        ]
        decided.sort(key=lambda a: a["decided_at"])
        window = decided[-100:]
        window_note = (
            f"window={len(window)} decisions (contract window is the "
            f"last 100; every decision of this activation run is "
            f"included)"
        )
        if not window:
            self.gates.append(gate(
                "approval_acceptance_rate", source,
                ">= 90 % over the last 100 decisions", None, None,
                "no decided approvals"))
            self.gates.append(gate(
                "approval_rejection_rate", source,
                "<= 25 % over the last 100 decisions", None, None,
                "no decided approvals"))
            self.gates.append(gate(
                "approval_p95_latency", source,
                "<= 30 minutes for write.high-risk", None, None,
                "no decided approvals"))
            return
        approved = sum(
            1 for a in window if a["decision"] == "approved")
        acceptance = round(100 * approved / len(window), 1)
        rejection = round(100 - acceptance, 1)
        self.gates.append(gate(
            "approval_acceptance_rate", source,
            ">= 90 % over the last 100 decisions", acceptance,
            acceptance >= 90, window_note))
        self.gates.append(gate(
            "approval_rejection_rate", source,
            "<= 25 % over the last 100 decisions", rejection,
            rejection <= 25, window_note))
        latencies_min = [
            (datetime.fromisoformat(a["decided_at"])
             - datetime.fromisoformat(a["requested_at"])
             ).total_seconds() / 60
            for a in window
            if a.get("risk_class") == "write.high-risk"
        ]
        if latencies_min:
            p95_min = round(percentile(latencies_min, 95), 3)
            self.gates.append(gate(
                "approval_p95_latency", source,
                "<= 30 minutes for write.high-risk", p95_min,
                p95_min <= 30,
                f"{len(latencies_min)} write.high-risk decisions"))
        else:
            self.gates.append(gate(
                "approval_p95_latency", source,
                "<= 30 minutes for write.high-risk", None, None,
                "no write.high-risk decisions in the window"))

    def gate_backtesting(self) -> None:
        path = (self.root / "contracts" / "risk_rca"
                / "BACKTESTING_EVIDENCE_VALIDATION.json")
        source = str(path.relative_to(self.root))
        try:
            payload = json.loads(path.read_text())
            metrics = payload["metrics"]
            minimums = payload["minimum_thresholds"]
            met = sum(
                1 for key, minimum in minimums.items()
                if metrics.get(key, 0) >= minimum
            )
            rate = round(100 * met / len(minimums), 1)
            passed = (rate >= 95
                      and payload["validation_result"]["status"]
                      == "pass")
            self.gates.append(gate(
                "backtesting_evidence_pass_rate", source, ">= 95 %",
                rate, passed,
                f"{met}/{len(minimums)} metrics at or above their "
                f"minimum thresholds"))
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            self.gates.append(gate(
                "backtesting_evidence_pass_rate", source, ">= 95 %",
                None, None, f"unmeasurable: {exc}"))

    def gate_action_gate_scenarios(self) -> None:
        path = (self.root / "tests" / "safety" / "action_gates"
                / "ACTION_GATE_SCENARIOS_V1.json")
        source = (f"{path.relative_to(self.root)} replayed against "
                  f"the live gateway")
        scenarios = json.loads(path.read_text())["scenarios"]
        results = []
        for scenario in scenarios:
            outcome = self._replay_scenario(scenario)
            results.append({
                "id": scenario["id"],
                "expected": scenario["expected_outcome"],
                "observed": outcome,
                "matched": outcome == scenario["expected_outcome"],
            })
        matched = sum(1 for r in results if r["matched"])
        self.gates.append(gate(
            "action_gate_scenario_coverage", source,
            "all declared scenarios expected_outcome matched",
            {"matched": matched, "total": len(results),
             "results": results},
            matched == len(results)))

    def _replay_scenario(self, scenario: dict) -> str:
        # Scenario tool ids are the classified form (<tool>.v1); the
        # envelope carries the bare tool name plus tool_version.
        tool_id = scenario.get("tool", "runbook-plan.v1")
        tool = tool_id.removesuffix(".v1")
        approval_status = scenario.get("approval_status")
        approval = None
        if approval_status and approval_status != "absent":
            approval = {
                "approval_id": f"signoff-replay-{scenario['id']}",
                "state": approval_status,
                "decision": approval_status
                if approval_status in ("approved", "rejected")
                else None,
                "approver": SURROGATE_SIGNOFF_APPROVER,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }
        rollback_plan = (
            {"steps": ["revert to previous revision", "verify health"]}
            if scenario.get("rollback_plan_present", True) else None
        )
        # Caller identity follows the agent tool bindings
        # (TOOL_BINDINGS_V1.yaml): each write-path tool is bound to
        # exactly one approval-gated agent.
        caller = ("runbook-planner" if tool == "runbook-plan"
                  else "remediation-executor")
        envelope = {
            "edge_version": "v1",
            "caller_agent": caller,
            "tool": tool,
            "tool_version": "v1",
            "tenant_scope": {
                "namespace": "observability",
                "tenant": "tenant-demo",
                "team": "sre",
            },
            "input": {
                "runbook": f"signoff-replay-{scenario['id']}",
                "approval": approval,
                "rollback_plan": rollback_plan,
                "simulate_runtime_failure": scenario.get(
                    "simulate_runtime_failure", False),
            },
            "approval_context": {
                "policy_decision": scenario.get(
                    "policy_decision", "allow"),
                "approval": approval,
                "rollback_plan_present": scenario.get(
                    "rollback_plan_present", True),
                "change_ticket_present": scenario.get(
                    "change_ticket_present", True),
                "valid_target": scenario.get("valid_target", True),
            },
        }
        status, payload = http(
            "POST", f"{self.gateway}/invoke", envelope)
        if status != 200:
            return "blocked"
        structured = payload.get("structured_data", {})
        return structured.get("outcome", "executed")

    def gate_staging_action_gates(self) -> None:
        path = (self.root / "tests" / "staging" / "action_gates"
                / "STAGING_ACTION_GATE_RESULTS_V1.json")
        source = str(path.relative_to(self.root))
        try:
            results = json.loads(path.read_text())["results"]
            passed = sum(
                1 for r in results if r["status"] == "pass")
            rate = round(100 * passed / len(results), 1)
            self.gates.append(gate(
                "staging_action_gate_pass_rate", source,
                "100 % (>= 5 results, all pass)", rate,
                rate == 100 and len(results) >= 5,
                f"{passed}/{len(results)} pass"))
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            self.gates.append(gate(
                "staging_action_gate_pass_rate", source,
                "100 % (>= 5 results, all pass)", None, None,
                f"unmeasurable: {exc}"))

    def gate_release_suite(self) -> None:
        source = "tests/safety/RELEASE_VALIDATION_SUITE_V1.json"
        suite = json.loads(
            (self.root / source).read_text())
        validators = sorted({
            entry
            for section in suite["coverage"].values()
            for entry in section
            if str(entry).endswith(".sh")
        })
        results = {}
        for validator in validators:
            completed = subprocess.run(
                ["bash", f"scripts/ci/{Path(validator).name}"],
                cwd=self.root, capture_output=True, text=True,
            )
            results[Path(validator).name] = completed.returncode
        passed = sum(1 for code in results.values() if code == 0)
        rate = round(100 * passed / len(results), 1) \
            if results else None
        self.gates.append(gate(
            "release_validation_suite_pass_rate", source, "100 %",
            rate, bool(results) and rate == 100,
            json.dumps(results, sort_keys=True)))

    def gate_restore_recency(self) -> None:
        path = (self.root / "artifacts" / "evidence" / "batch24"
                / "rehearsal" / "store_restore_drill.json")
        source = ("KAGENT_PERSISTENCE_CONTRACT_V1.yaml "
                  "restore_drill_cadence_days vs the live drill of "
                  "this activation run")
        try:
            envelope = json.loads(path.read_text())
            drilled_at = datetime.fromisoformat(
                envelope["payload"]["drilled_at"])
            age_days = (
                datetime.now(timezone.utc) - drilled_at
            ).total_seconds() / 86400
            self.gates.append(gate(
                "restore_drill_recency", source,
                f"<= {RESTORE_DRILL_CADENCE_DAYS} days",
                round(age_days, 4),
                age_days <= RESTORE_DRILL_CADENCE_DAYS
                and envelope["payload"]["match"] is True))
        except (OSError, KeyError, json.JSONDecodeError,
                ValueError) as exc:
            self.gates.append(gate(
                "restore_drill_recency", source,
                f"<= {RESTORE_DRILL_CADENCE_DAYS} days", None, None,
                f"unmeasurable: {exc}"))

    def gate_approval_contract_presence(self) -> None:
        path = (self.root / "contracts" / "policy"
                / "APPROVAL_FLOW_V1.yaml")
        source = str(path.relative_to(self.root))
        text = path.read_text()
        present = ("timeout_rules:" in text
                   and "escalation_rules:" in text)
        self.gates.append(gate(
            "approval_flow_contract_presence", source,
            "timeout_rules and escalation_rules present",
            {"timeout_rules": "timeout_rules:" in text,
             "escalation_rules": "escalation_rules:" in text},
            present))

    # -- record ------------------------------------------------------

    def record(self) -> dict:
        all_pass = all(g["status"] == "pass" for g in self.gates)
        release_version = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=self.root, capture_output=True, text=True,
        ).stdout.strip()
        return {
            "schema": "activation-signoff-record-v1",
            "workflow":
                "docs/operations/PRODUCTION_ACTIVATION_SIGNOFF_WORKFLOW.md",
            "release_version": release_version,
            "approver": SURROGATE_SIGNOFF_APPROVER,
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "gates": self.gates,
            "decision": "approved" if all_pass else "hold",
            "evidence_links": [
                "artifacts/evidence/batch24/deploy/",
                "artifacts/evidence/batch24/rehearsal/",
            ],
            "residual_risk": [
                "Decision window smaller than 100 (every decision of "
                "this activation run is included; the window grows "
                "with production operation).",
                "Model provider is local-stub on the harness "
                "(ADR-0008); production activation swaps to a "
                "credentialed provider through the secrets backend.",
                "KAgent PostgreSQL runs single-node on the harness; "
                "production HA arrives with the Batch 25 reference "
                "architecture.",
            ],
        }


def main() -> int:
    args = _parse_args()
    signoff = Signoff(args)
    signoff.gate_mcp_latency()
    signoff.gate_approval_rates()
    signoff.gate_backtesting()
    signoff.gate_action_gate_scenarios()
    signoff.gate_staging_action_gates()
    signoff.gate_release_suite()
    signoff.gate_restore_recency()
    signoff.gate_approval_contract_presence()
    record = signoff.record()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")
    failed = [g["gate"] for g in record["gates"]
              if g["status"] != "pass"]
    print(f"signoff decision: {record['decision']}"
          + (f" (failed gates: {', '.join(failed)})" if failed else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
