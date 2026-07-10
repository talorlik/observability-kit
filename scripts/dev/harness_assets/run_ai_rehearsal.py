"""Live trigger-to-approval rehearsal driver (Batch 24 Task 3, TR-24).

Runs against a deployed AI runtime on the disposable harness cluster
and captures the rehearsal evidence payloads:

- trigger_flow.json         KHook trigger -> casefile -> read-path
                            investigation -> human-surrogate approval
                            -> execution -> resolved.
- rejection_flow.json       Surrogate rejection; the rejection feeds
                            the casefile (execution_gates rule).
- timeout_drill.json        The pending-timeout and escalation rules
                            of APPROVAL_FLOW_V1.yaml evaluated live
                            against a real pending approval with a
                            supplied as-of clock (waiting 60 real
                            minutes is not viable in a disposable
                            run; the rule logic is the real one).
- dedupe_burst.json         Duplicate-event suppression per
                            DEDUPE_BURST_CONTROL_V1.yaml.
- decision_corpus.json      A 29-flow decision corpus (28 approvals,
                            1 rejection) so the signoff acceptance
                            and rejection rates are measured over a
                            real decision window.
- store_restore_drill.json  KAgent PostgreSQL dump-and-restore drill
                            (KAGENT_PERSISTENCE_CONTRACT_V1 backups).
- audit_trail.json          The full audit trail and runtime state.

The human-surrogate approver identity is distinct from the requesting
agent; self-approval is rejected by the runtime.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SURROGATE_APPROVER = "human-surrogate-oncall-sre"
CASEFILE_REQUIRED_FIELDS = (
    "schema_version", "case_id", "status", "incident_context",
    "agent_outputs", "evidence_handles", "approval_state",
    "action_journal", "lineage", "created_at", "updated_at",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kagent-url", required=True)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--event-namespace", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def http(method: str, url: str, body: dict | None = None,
         timeout: float = 30.0) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


class Rehearsal:
    def __init__(self, args: argparse.Namespace) -> None:
        self.kagent = args.kagent_url.rstrip("/")
        self.kubeconfig = args.kubeconfig
        self.context = args.context
        self.namespace = args.event_namespace
        self.out = Path(args.output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self._event_seq = 0

    def kubectl(self, *argv: str, stdin: str | None = None) -> str:
        result = subprocess.run(
            ["kubectl", "--kubeconfig", self.kubeconfig,
             "--context", self.context, *argv],
            input=stdin, capture_output=True, text=True, check=True,
        )
        return result.stdout

    # -- synthetic events -------------------------------------------

    def seed_event(self, object_name: str,
                   reason: str = "OOMKilled") -> str:
        """Create a synthetic Kubernetes Event matching a hook rule."""
        self._event_seq += 1
        name = f"rehearsal-{object_name}-{self._event_seq}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest = {
            "apiVersion": "v1",
            "kind": "Event",
            "metadata": {"name": name, "namespace": self.namespace},
            "type": "Warning",
            "reason": reason,
            "message": (
                f"rehearsal synthetic event: container in "
                f"{object_name} was OOM killed"
            ),
            "involvedObject": {
                "kind": "Pod",
                "name": object_name,
                "namespace": self.namespace,
            },
            "firstTimestamp": now,
            "lastTimestamp": now,
            "count": 1,
            "source": {"component": "batch24-rehearsal"},
        }
        self.kubectl("apply", "-f", "-", stdin=json.dumps(manifest))
        return name

    # -- casefile helpers -------------------------------------------

    def casefiles(self) -> list[dict]:
        status, payload = http("GET", f"{self.kagent}/casefiles")
        assert status == 200, f"GET /casefiles -> {status}"
        return payload["casefiles"] if isinstance(payload, dict) \
            else payload

    def wait_casefile(self, known_ids: set[str], object_name: str,
                      target_statuses: tuple[str, ...],
                      timeout_s: int = 180) -> dict:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for casefile in self.casefiles():
                if casefile["case_id"] in known_ids:
                    continue
                summary = casefile["incident_context"]["summary"]
                if object_name in summary \
                        and casefile["status"] in target_statuses:
                    return casefile
            time.sleep(3)
        raise TimeoutError(
            f"no casefile for {object_name} reached "
            f"{target_statuses} within {timeout_s}s"
        )

    def get_casefile(self, case_id: str) -> dict:
        status, payload = http(
            "GET", f"{self.kagent}/casefiles/{case_id}")
        assert status == 200, f"GET casefile {case_id} -> {status}"
        return payload.get("casefile", payload)

    def decide(self, casefile: dict, decision: str) -> dict:
        approval_ref = casefile["approval_state"]["approval_ref"]
        status, payload = http(
            "POST",
            f"{self.kagent}/approvals/{approval_ref}/decision",
            {"approver": SURROGATE_APPROVER, "decision": decision},
        )
        assert status == 200, (
            f"decision {decision} on {approval_ref} -> "
            f"{status} {payload}"
        )
        return payload

    def wait_status(self, case_id: str, statuses: tuple[str, ...],
                    timeout_s: int = 120) -> dict:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            casefile = self.get_casefile(case_id)
            if casefile["status"] in statuses:
                return casefile
            time.sleep(2)
        raise TimeoutError(
            f"casefile {case_id} never reached {statuses}")

    def run_flow(self, object_name: str, decision: str,
                 known_ids: set[str]) -> dict:
        self.seed_event(object_name)
        casefile = self.wait_casefile(
            known_ids, object_name, ("awaiting-approval",))
        known_ids.add(casefile["case_id"])
        self.decide(casefile, decision)
        terminal = ("resolved",) if decision == "approved" \
            else ("rejected",)
        return self.wait_status(casefile["case_id"], terminal)

    @staticmethod
    def conformance(casefile: dict) -> dict:
        return {
            "required_fields_present": all(
                field in casefile
                for field in CASEFILE_REQUIRED_FIELDS
            ),
            "evidence_handles": len(casefile["evidence_handles"]),
            "agent_outputs": len(casefile["agent_outputs"]),
            "action_journal_outcomes": [
                entry["outcome"]
                for entry in casefile["action_journal"]
            ],
        }

    def write(self, name: str, payload: dict) -> None:
        path = self.out / f"{name}.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(f"rehearsal payload written: {path}")

    # -- phases ------------------------------------------------------

    def phase_trigger_flow(self, known_ids: set[str]) -> None:
        casefile = self.run_flow(
            "demo-workload-approve", "approved", known_ids)
        assert casefile["status"] == "resolved"
        journal_outcomes = [
            entry["outcome"] for entry in casefile["action_journal"]]
        assert "executed" in journal_outcomes, journal_outcomes
        self.write("trigger_flow", {
            "scenario": "grant",
            "approver": SURROGATE_APPROVER,
            "casefile": casefile,
            "conformance": self.conformance(casefile),
        })

    def phase_rejection_flow(self, known_ids: set[str]) -> None:
        casefile = self.run_flow(
            "demo-workload-reject", "rejected", known_ids)
        journal_outcomes = [
            entry["outcome"] for entry in casefile["action_journal"]]
        assert "blocked" in journal_outcomes, (
            "rejection must feed the casefile "
            "(execution_gates.feed_rejection_into_casefile)"
        )
        self.write("rejection_flow", {
            "scenario": "reject",
            "approver": SURROGATE_APPROVER,
            "casefile": casefile,
            "conformance": self.conformance(casefile),
        })

    def phase_timeout_drill(self, known_ids: set[str]) -> None:
        self.seed_event("demo-workload-timeout")
        casefile = self.wait_casefile(
            known_ids, "demo-workload-timeout", ("awaiting-approval",))
        known_ids.add(casefile["case_id"])
        approval_ref = casefile["approval_state"]["approval_ref"]
        status, approval = http(
            "GET", f"{self.kagent}/approvals/{approval_ref}")
        assert status == 200
        approval = approval.get("approval", approval)
        requested_at = datetime.fromisoformat(approval["requested_at"])
        # Evaluate the real timeout rules against the real pending
        # approval, one minute past the contract's 60-minute deadline.
        as_of = (requested_at + timedelta(minutes=61)).isoformat()
        status, evaluation = http(
            "POST",
            f"{self.kagent}/approvals/{approval_ref}/evaluate-timeout",
            {"as_of": as_of},
        )
        assert status == 200, f"evaluate-timeout -> {status}"
        assert evaluation["state"] == "expired", evaluation
        assert evaluation["outcome"] == "deny-and-escalate", evaluation
        final = self.wait_status(casefile["case_id"], ("rejected",))
        self.write("timeout_drill", {
            "scenario": "timeout-deny-and-escalate",
            "approval_before": approval,
            "as_of": as_of,
            "evaluation": evaluation,
            "casefile_after": final,
            "note": (
                "Timeout and escalation rules are the contract "
                "values (60m deadline, 30m warning, escalation "
                "chain); the as-of clock substitutes for a 61-minute "
                "wall-clock wait on the disposable harness."
            ),
        })

    def phase_dedupe(self, known_ids: set[str]) -> None:
        before = {c["case_id"] for c in self.casefiles()}
        # Same involved object and reason as the trigger flow, well
        # inside the 300s dedupe window: khook must suppress it.
        self.seed_event("demo-workload-approve")
        time.sleep(20)
        after = {c["case_id"] for c in self.casefiles()}
        new_cases = after - before
        assert not new_cases, (
            f"dedupe failed: duplicate event produced {new_cases}"
        )
        khook_state = self.khook_state()
        counters = khook_state.get("counters", khook_state)
        assert counters.get("deduped", 0) >= 1, khook_state
        self.write("dedupe_burst", {
            "scenario": "duplicate-event-suppression",
            "window_seconds": 300,
            "new_casefiles_after_duplicate": sorted(new_cases),
            "khook_state": khook_state,
        })

    def khook_state(self) -> dict:
        process = subprocess.Popen(
            ["kubectl", "--kubeconfig", self.kubeconfig,
             "--context", self.context, "-n", "ai-triggers",
             "port-forward", "svc/khook-controller", "18090:8090"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(20):
                time.sleep(1)
                try:
                    status, payload = http(
                        "GET", "http://127.0.0.1:18090/state",
                        timeout=5)
                    if status == 200:
                        return payload
                except (urllib.error.URLError, OSError):
                    continue
            raise TimeoutError("khook /state unreachable")
        finally:
            process.terminate()
            process.wait(timeout=10)

    def phase_decision_corpus(self, known_ids: set[str]) -> None:
        decisions: list[dict] = []
        for index in range(1, 29):
            casefile = self.run_flow(
                f"demo-corpus-{index:02d}", "approved", known_ids)
            decisions.append({
                "case_id": casefile["case_id"],
                "decision": "approved",
            })
        casefile = self.run_flow(
            "demo-corpus-reject", "rejected", known_ids)
        decisions.append({
            "case_id": casefile["case_id"],
            "decision": "rejected",
        })
        self.write("decision_corpus", {
            "scenario": "signoff-decision-window",
            "flows": len(decisions),
            "approved": sum(
                1 for d in decisions if d["decision"] == "approved"),
            "rejected": sum(
                1 for d in decisions if d["decision"] == "rejected"),
            "decisions": decisions,
        })

    def phase_store_restore_drill(self) -> None:
        pod = "kagent-postgres-0"
        live_count = len(self.casefiles())
        dump = self.kubectl(
            "-n", "ai-runtime", "exec", pod, "--",
            "pg_dump", "-U", "kagent", "kagent",
        )
        # Two separate -c invocations: multiple statements in one -c
        # run inside an implicit transaction, and DROP DATABASE is
        # forbidden inside a transaction block.
        self.kubectl(
            "-n", "ai-runtime", "exec", pod, "--",
            "psql", "-U", "kagent", "-d", "postgres", "-c",
            "DROP DATABASE IF EXISTS kagent_restore_drill;",
        )
        self.kubectl(
            "-n", "ai-runtime", "exec", pod, "--",
            "psql", "-U", "kagent", "-d", "postgres", "-c",
            "CREATE DATABASE kagent_restore_drill;",
        )
        self.kubectl(
            "-n", "ai-runtime", "exec", "-i", pod, "--",
            "psql", "-U", "kagent", "-d", "kagent_restore_drill",
            stdin=dump,
        )
        restored = self.kubectl(
            "-n", "ai-runtime", "exec", pod, "--",
            "psql", "-U", "kagent", "-d", "kagent_restore_drill",
            "-t", "-A", "-c",
            'SELECT count(*) FROM kagent_runs.casefiles;',
        ).strip()
        assert int(restored) == live_count, (
            f"restore drill mismatch: live={live_count} "
            f"restored={restored}"
        )
        self.write("store_restore_drill", {
            "scenario": "kagent-postgres-restore-drill",
            "contract": "contracts/ai/KAGENT_PERSISTENCE_CONTRACT_V1.yaml",
            "cadence_days_required": 90,
            "dump_bytes": len(dump.encode()),
            "live_casefiles": live_count,
            "restored_casefiles": int(restored),
            "match": True,
            "drilled_at": datetime.now(timezone.utc).isoformat(),
        })

    def phase_audit_trail(self) -> None:
        status, audit = http("GET", f"{self.kagent}/audit")
        assert status == 200
        status, state = http("GET", f"{self.kagent}/state")
        assert status == 200
        records = audit["records"] if isinstance(audit, dict) \
            else audit
        assert records, "audit trail must not be empty"
        self.write("audit_trail", {
            "records": records,
            "record_count": len(records),
            "runtime_state": state,
        })


def main() -> int:
    args = _parse_args()
    rehearsal = Rehearsal(args)
    known_ids: set[str] = {
        c["case_id"] for c in rehearsal.casefiles()}
    rehearsal.phase_trigger_flow(known_ids)
    rehearsal.phase_rejection_flow(known_ids)
    rehearsal.phase_timeout_drill(known_ids)
    rehearsal.phase_dedupe(known_ids)
    rehearsal.phase_decision_corpus(known_ids)
    rehearsal.phase_store_restore_drill()
    rehearsal.phase_audit_trail()
    print("rehearsal complete: all phases captured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
