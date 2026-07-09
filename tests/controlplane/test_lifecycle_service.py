"""Offline tests for the tenant control plane service (Batch 20
Task 2).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 20 validator - never under pytest. Every run
uses temp directories for both the control-plane store and the render
target repo root; the repository's own gitops/ tree is never touched.

Covers the Task 2 completion check:

- the service executes provision, suspend, resume, offboard, and
  purge as GitOps renders, generating per-tenant overlays per
  TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml through the Batch 19
  renderer (execute_plan / changed_paths);
- re-running a completed transition is an audited no-op replay
  (HTTP-200 semantics, replay=true, render_action replayed-no-diff,
  audit record marked replay) - never an error;
- illegal transitions and unapproved destructive transitions are
  denied with contract-fixed error codes and denial audit records;
- no direct mutable API writes for persistent configuration: side
  effects are rendered overlay files, control-plane records, and
  audit records only.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
CONTRACTS = REPO_ROOT / "contracts"
LIFECYCLE_CONTRACT = (
    CONTRACTS / "tenancy" / "TENANT_LIFECYCLE_CONTRACT_V1.yaml"
)

sys.path.insert(0, str(REPO_ROOT / "services" / "tenancy"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from tenantctl.models import (  # noqa: E402
    ApprovalInvalid,
    ApprovalRequired,
    ControlPlaneError,
    ForbiddenFieldUpdate,
    IllegalTransition,
    PreconditionFailed,
    TenantConflict,
    ValidationFailed,
)
from tenantctl.renders import (  # noqa: E402
    OVERLAY_MARKER_COMMENT,
    overlay_dir,
)
from tenantctl.service import TenantControlPlaneService  # noqa: E402
from tenantctl.store import ControlPlaneStore  # noqa: E402


@dataclass
class FakeClock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now

    def advance_days(self, days: int) -> None:
        self.now = self.now + timedelta(days=days)


def dedicated_stack_document(tenant_id: str = "acme") -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "display_name": "Acme Corp",
        "tier": "enterprise",
        "isolation_class": "dedicated-stack",
        "residency": {
            "region": "region-a",
            "data_residency_required": True,
            "pool": "dedicated",
            "allowed_regions": ["region-a"],
        },
        "lifecycle_state": "provisioning",
        "owner": {"name": "Platform Team", "email": "owner@example.com"},
        "contacts": [
            {"role": "technical", "email": "tech@example.com"},
        ],
        "quotas": {
            "ingest": {
                "max_gb_per_day": 50,
                "max_events_per_second": 1000,
            },
            "retention": {
                "logs_days": 30,
                "metrics_days": 90,
                "traces_days": 14,
            },
        },
        "created_at": "2026-07-01T00:00:00Z",
    }


def shared_partition_document(
    tenant_id: str = "shared1",
) -> dict[str, Any]:
    document = dedicated_stack_document(tenant_id)
    document["isolation_class"] = "shared-partition"
    document["residency"]["pool"] = "shared"
    return document


HIGH_RISK_APPROVAL = {
    "approval_id": "apr-001",
    "approver": "approver@example.com",
    "decision": "approved",
    # Freshly dated at import so the APPROVAL_FLOW_V1 pending-timeout
    # windows (60/120 minutes against the wall clock) never expire the
    # fixture mid-suite.
    "decided_at": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
}
CRITICAL_APPROVAL = {**HIGH_RISK_APPROVAL, "change_ticket": "chg-777"}


class Env:
    """One isolated service instance over temp store and repo roots."""

    def __init__(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="tenantctl-test-"))
        self.repo_root = self._tmp / "repo"
        self.repo_root.mkdir()
        self.store = ControlPlaneStore(self._tmp / "store")
        self.clock = FakeClock(
            datetime(2026, 7, 10, 0, 0, 0, tzinfo=timezone.utc)
        )
        self.service = TenantControlPlaneService(
            store=self.store,
            repo_root=self.repo_root,
            lifecycle_contract_path=LIFECYCLE_CONTRACT,
            clock=self.clock,
        )

    def cleanup(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def overlay_path(self, tenant_id: str) -> Path:
        return self.repo_root / overlay_dir(tenant_id)

    def tree_digest(self, tenant_id: str) -> str:
        """Digest of every byte under the tenant overlay directory."""
        digest = hashlib.sha256()
        directory = self.overlay_path(tenant_id)
        if not directory.is_dir():
            return "absent"
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(directory).as_posix()
                              .encode("utf-8"))
                digest.update(path.read_bytes())
        return digest.hexdigest()


def expect_error(
    env: Env,
    transition: str,
    tenant_id: str,
    payload: dict[str, Any],
    error_type: type[ControlPlaneError],
) -> ControlPlaneError:
    try:
        env.service.transition(transition, tenant_id, payload)
    except error_type as error:
        return error
    raise AssertionError(
        f"expected {error_type.__name__} for {transition} on "
        f"{tenant_id}"
    )


def provisioned_env(tenant_id: str = "acme") -> Env:
    env = Env()
    env.service.create_tenant(dedicated_stack_document(tenant_id))
    env.service.transition(
        "provision", tenant_id, {"actor": "op@example.com"}
    )
    return env


def test_full_lifecycle_as_gitops_renders() -> None:
    env = Env()
    try:
        document = dedicated_stack_document()
        created = env.service.create_tenant(document)
        assert created["lifecycle_state"] == "provisioning"

        result = env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        assert result.lifecycle_state == "active"
        assert result.replay is False
        assert result.gitops_render.render_action == "rendered"
        assert result.gitops_render.overlay_path == (
            "gitops/overlays/tenants/acme/"
        )
        assert result.gitops_render.commit_ref is not None
        assert result.gitops_render.commit_ref.startswith(
            "prepared:sha256:"
        )
        assert result.audit["replay"] is False
        assert result.audit["requested_at"]
        assert result.audit["completed_at"]

        result = env.service.transition(
            "suspend",
            "acme",
            {
                "actor": "op@example.com",
                "trigger_type": "operator",
                "reason": "billing overdue",
            },
        )
        assert result.lifecycle_state == "suspended"
        assert result.gitops_render.render_action == "retained"
        assert env.overlay_path("acme").is_dir()
        assert result.audit["trigger_type"] == "operator"

        result = env.service.transition(
            "resume",
            "acme",
            {"actor": "op@example.com", "reason": "billing settled"},
        )
        assert result.lifecycle_state == "active"
        assert result.gitops_render.render_action == "retained"

        result = env.service.transition(
            "offboard",
            "acme",
            {
                "actor": "op@example.com",
                "reason": "contract ended",
                "approval": HIGH_RISK_APPROVAL,
            },
        )
        assert result.lifecycle_state == "offboarding"
        assert result.gitops_render.render_action == "retained"
        # Data (and the overlay) are retained during offboarding.
        assert env.overlay_path("acme").is_dir()
        ends_at = result.audit["retention_window_ends_at"]
        # Longest retention is metrics_days=90.
        assert ends_at == "2026-10-08T00:00:00Z"

        env.clock.advance_days(91)
        result = env.service.transition(
            "purge",
            "acme",
            {"actor": "op@example.com", "approval": CRITICAL_APPROVAL},
        )
        assert result.lifecycle_state == "purged"
        assert result.gitops_render.render_action == "removed"
        assert not env.overlay_path("acme").exists()
        assert result.audit["change_ticket"] == "chg-777"
        assert result.audit["purged_at"]
        refs = result.audit["evidence_artifact_refs"]
        assert len(refs) == 6
        assert "evidence/acme/gitops_overlay.json" in refs
        assert env.service.get_tenant("acme")["lifecycle_state"] == (
            "purged"
        )
    finally:
        env.cleanup()


def test_idempotent_replay_of_every_transition() -> None:
    env = Env()
    try:
        env.service.create_tenant(dedicated_stack_document())
        steps: list[tuple[str, dict[str, Any]]] = [
            ("provision", {"actor": "op@example.com"}),
            (
                "suspend",
                {
                    "actor": "op@example.com",
                    "trigger_type": "operator",
                    "reason": "maintenance",
                },
            ),
            (
                "resume",
                {"actor": "op@example.com", "reason": "resolved"},
            ),
            (
                "offboard",
                {
                    "actor": "op@example.com",
                    "reason": "contract ended",
                    "approval": HIGH_RISK_APPROVAL,
                },
            ),
            (
                "purge",
                {
                    "actor": "op@example.com",
                    "approval": CRITICAL_APPROVAL,
                },
            ),
        ]
        for name, payload in steps:
            if name == "purge":
                env.clock.advance_days(91)
            first = env.service.transition(name, "acme", payload)
            assert first.replay is False
            before = env.tree_digest("acme")
            replayed = env.service.transition(name, "acme", payload)
            assert replayed.replay is True
            assert replayed.lifecycle_state == first.lifecycle_state
            assert replayed.gitops_render.render_action == (
                "replayed-no-diff"
            )
            assert replayed.gitops_render.commit_ref is None
            assert replayed.audit["replay"] is True
            assert replayed.audit["outcome"] == "replayed"
            # A replay changes zero bytes under the overlay tree.
            assert env.tree_digest("acme") == before
            if name == "offboard":
                # The retention clock is never reset by a replay.
                assert replayed.audit["retention_window_ends_at"] == (
                    first.audit["retention_window_ends_at"]
                )
            if name == "purge":
                assert replayed.audit["purged_at"] == (
                    first.audit["purged_at"]
                )
    finally:
        env.cleanup()


def test_illegal_transitions_denied_with_audit() -> None:
    env = Env()
    try:
        env.service.create_tenant(dedicated_stack_document())
        # suspend from provisioning: not in the from set.
        error = expect_error(
            env,
            "suspend",
            "acme",
            {
                "actor": "op@example.com",
                "trigger_type": "operator",
                "reason": "x",
            },
            IllegalTransition,
        )
        assert error.error_code == "illegal-transition"
        assert error.audit_record_id is not None
        assert error.details == {
            "current_state": "provisioning",
            "allowed_from": ["active"],
        }
        # resume on a tenant that was never suspended is not a replay
        # (no completed resume record): it is illegal.
        env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        expect_error(
            env,
            "resume",
            "acme",
            {"actor": "op@example.com", "reason": "x"},
            IllegalTransition,
        )
        # purge from active (offboard never ran) is illegal.
        expect_error(
            env,
            "purge",
            "acme",
            {"actor": "op@example.com", "approval": CRITICAL_APPROVAL},
            IllegalTransition,
        )
        assert (
            env.service.get_tenant("acme")["lifecycle_state"] == "active"
        )
        # Denials were audited (execution gate
        # emit_audit_record_on_denial).
        denials = [
            record
            for record in env.store.load_audit_records()
            if record["outcome"] == "denied"
        ]
        assert len(denials) == 3
        assert all(record["tenant_id"] == "acme" for record in denials)
    finally:
        env.cleanup()


def test_overlay_rendered_per_contract() -> None:
    env = Env()
    try:
        env.service.create_tenant(dedicated_stack_document())
        env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        directory = env.overlay_path("acme")
        files = sorted(
            path.name for path in directory.iterdir() if path.is_file()
        )
        # Exactly the contract's two required files, in a directory
        # named exactly after the tenant_id.
        assert files == [
            "applicationset-element.yaml",
            "tenant-values.yaml",
        ]
        for name in files:
            text = (directory / name).read_text(encoding="utf-8")
            first_line = text.splitlines()[0]
            assert first_line == OVERLAY_MARKER_COMMENT
            # Only descriptor-derived values: no environment names,
            # endpoints, or repo URLs in generated output.
            assert "repoURL" not in text
            assert "server" not in text
            assert "targetRevision" not in text
        values = (directory / "tenant-values.yaml").read_text(
            encoding="utf-8"
        )
        assert "max_gb_per_day: 50" in values
        assert "logs_days: 30" in values
        # lifecycle_state must not leak into the overlay: retained
        # overlays would otherwise drift on suspend/resume.
        assert "lifecycle_state" not in values
        # Deterministic regeneration: replay is byte-identical.
        before = env.tree_digest("acme")
        env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        assert env.tree_digest("acme") == before
        # Overlay files live under gitops/overlays/tenants/ only; the
        # renderer never touched anything else in the repo root.
        rendered = [
            path
            for path in env.repo_root.rglob("*")
            if path.is_file()
        ]
        assert all(
            path.is_relative_to(env.repo_root / "gitops/overlays/tenants")
            for path in rendered
        )
    finally:
        env.cleanup()


def test_shared_partition_overlay_not_applicable() -> None:
    env = Env()
    try:
        env.service.create_tenant(shared_partition_document())
        result = env.service.transition(
            "provision", "shared1", {"actor": "op@example.com"}
        )
        assert result.lifecycle_state == "active"
        assert result.gitops_render.render_action == "not-applicable"
        assert result.gitops_render.overlay_path is None
        assert not env.overlay_path("shared1").exists()
    finally:
        env.cleanup()


def test_destructive_without_approval_blocked() -> None:
    env = provisioned_env()
    try:
        # Missing approval block entirely.
        error = expect_error(
            env,
            "offboard",
            "acme",
            {"actor": "op@example.com", "reason": "bye"},
            ApprovalRequired,
        )
        assert error.error_code == "approval-required"
        assert error.audit_record_id is not None
        # Approval present but not an approval decision.
        expect_error(
            env,
            "offboard",
            "acme",
            {
                "actor": "op@example.com",
                "reason": "bye",
                "approval": {**HIGH_RISK_APPROVAL, "decision": "denied"},
            },
            ApprovalInvalid,
        )
        # State is unchanged and nothing was rendered or removed.
        assert (
            env.service.get_tenant("acme")["lifecycle_state"] == "active"
        )
        assert env.overlay_path("acme").is_dir()
        # Purge approval at write.critical requires change_ticket.
        env.service.transition(
            "offboard",
            "acme",
            {
                "actor": "op@example.com",
                "reason": "bye",
                "approval": HIGH_RISK_APPROVAL,
            },
        )
        env.clock.advance_days(91)
        error = expect_error(
            env,
            "purge",
            "acme",
            {"actor": "op@example.com", "approval": HIGH_RISK_APPROVAL},
            ApprovalInvalid,
        )
        assert error.error_code == "approval-invalid"
        expect_error(
            env,
            "purge",
            "acme",
            {"actor": "op@example.com"},
            ApprovalRequired,
        )
        assert env.overlay_path("acme").is_dir()
    finally:
        env.cleanup()


def test_purge_before_retention_window_blocked() -> None:
    env = provisioned_env()
    try:
        env.service.transition(
            "offboard",
            "acme",
            {
                "actor": "op@example.com",
                "reason": "bye",
                "approval": HIGH_RISK_APPROVAL,
            },
        )
        error = expect_error(
            env,
            "purge",
            "acme",
            {"actor": "op@example.com", "approval": CRITICAL_APPROVAL},
            PreconditionFailed,
        )
        assert error.error_code == "precondition-failed"
        assert error.audit_record_id is not None
        assert env.overlay_path("acme").is_dir()
        assert env.service.get_tenant("acme")["lifecycle_state"] == (
            "offboarding"
        )
    finally:
        env.cleanup()


def test_create_conflict_and_forbidden_update() -> None:
    env = Env()
    try:
        env.service.create_tenant(dedicated_stack_document())
        try:
            env.service.create_tenant(dedicated_stack_document())
        except TenantConflict as error:
            assert error.error_code == "tenant-already-exists"
        else:
            raise AssertionError("expected TenantConflict")
        # lifecycle_state is never writable through CRUD.
        mutated = dedicated_stack_document()
        mutated["lifecycle_state"] = "active"
        try:
            env.service.update_tenant("acme", mutated)
        except ForbiddenFieldUpdate as error:
            assert error.error_code == "update-forbidden-field"
        else:
            raise AssertionError("expected ForbiddenFieldUpdate")
        # Mutable fields update fine and the result is re-validated.
        renamed = dedicated_stack_document()
        renamed["display_name"] = "Acme Corporation"
        updated = env.service.update_tenant("acme", renamed)
        assert updated["display_name"] == "Acme Corporation"
    finally:
        env.cleanup()


def test_hostile_tenant_ids_rejected_before_store_use() -> None:
    """Path-parameter tenant ids failing the contract pattern are
    rejected with validation-failed before any store path is derived
    from them (they are filesystem path segments in the store)."""
    env = provisioned_env()
    try:
        def store_files() -> set[str]:
            return {
                path.relative_to(env.store.root).as_posix()
                for path in env.store.root.rglob("*")
                if path.is_file()
            }

        overlay_before = env.tree_digest("acme")
        hostile_ids = [
            "../tenants/acme",  # traversal into the real record
            "",  # empty path segment
            "acmé",  # unicode outside the contract pattern
            "acme/../../store",  # hostile nested traversal
        ]
        for tenant_id in hostile_ids:
            before = store_files()
            for attempt in (
                lambda: env.service.get_tenant(tenant_id),
                lambda: env.service.update_tenant(
                    tenant_id, dedicated_stack_document()
                ),
                lambda: env.service.set_legal_hold(tenant_id, True),
            ):
                try:
                    attempt()
                except ValidationFailed as error:
                    assert error.error_code == "validation-failed"
                else:
                    raise AssertionError(
                        f"hostile tenant_id {tenant_id!r} was accepted"
                    )
            # CRUD rejections derived no store path: nothing changed.
            assert store_files() == before
            error = expect_error(
                env,
                "provision",
                tenant_id,
                {"actor": "op@example.com"},
                ValidationFailed,
            )
            assert error.error_code == "validation-failed"
            # Path-parameter rejection is request validation, before
            # the audited transition attempt: no store path (audit
            # included) is touched at all.
            assert error.audit_record_id is None
            assert store_files() == before
        # The real tenant's rendered tree is untouched throughout.
        assert env.tree_digest("acme") == overlay_before
    finally:
        env.cleanup()


def test_document_identity_mismatch_rejected() -> None:
    """A stored document whose tenant_id differs from the addressed
    tenant_id (store corruption/tampering) is refused with
    validation-failed by transitions and updates."""
    env = provisioned_env()
    try:
        record = env.store.load_tenant_record("acme")
        assert record is not None
        # "mallory" passes the tenant-id pattern, so only the
        # document-identity check can catch the mismatch.
        record["document"]["tenant_id"] = "mallory"
        env.store.save_tenant_record("acme", record)
        error = expect_error(
            env,
            "suspend",
            "acme",
            {
                "actor": "op@example.com",
                "trigger_type": "operator",
                "reason": "x",
            },
            ValidationFailed,
        )
        assert error.error_code == "validation-failed"
        assert "does not match the addressed tenant_id" in error.message
        try:
            env.service.update_tenant("acme", dedicated_stack_document())
        except ValidationFailed as update_error:
            assert "does not match the addressed tenant_id" in (
                update_error.message
            )
        else:
            raise AssertionError(
                "expected ValidationFailed for mismatched document"
            )
    finally:
        env.cleanup()


def test_provision_replay_sources_timestamps_from_record() -> None:
    """Provision replays never reset requested_at/completed_at: both
    come from the transition record saved at first completion."""
    env = Env()
    try:
        env.service.create_tenant(dedicated_stack_document())
        first = env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        env.clock.advance_days(3)
        replayed = env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        assert replayed.replay is True
        assert replayed.audit["requested_at"] == (
            first.audit["requested_at"]
        )
        assert replayed.audit["completed_at"] == (
            first.audit["completed_at"]
        )
    finally:
        env.cleanup()


def test_api_module_importable_without_fastapi() -> None:
    import tenantctl.api as api

    if api._FASTAPI_AVAILABLE:
        # Environment happens to have FastAPI; the guard is not
        # exercisable, but the import path above already proves the
        # module loads through the guard.
        return
    env = Env()
    try:
        try:
            api.build_app(env.service)
        except RuntimeError as error:
            assert "[api]" in str(error)
        else:
            raise AssertionError(
                "expected build_app to fail without FastAPI"
            )
    finally:
        env.cleanup()


def main() -> int:
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]
    for name, func in tests:
        func()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
