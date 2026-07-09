"""Tenant control plane orchestration (Batch 20 Task 2, TR-21).

TenantControlPlaneService executes the lifecycle contract verbatim:
it validates transition legality against the contract-loaded state
machine, enforces the approval gate on destructive transitions,
executes every transition as a GitOps render through the Batch 19
renderer (tenantctl.renders), emits a TR-09 audit record for every
attempt (applied, replayed, or denied), and detects idempotent
replays - re-running a completed transition is an audited no-op that
produces no new render (render_action replayed-no-diff), never an
error.

Persistent side effects are exactly: rendered overlay files under the
repository root, control-plane records, and audit records. No kubectl,
no store APIs, no live-cluster writes (TR-10).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from tenantctl import approval as approval_mod
from tenantctl import audit as audit_mod
from tenantctl import isolation, renders
from tenantctl.models import (
    ApprovalRecord,
    ControlPlaneError,
    CrossTenantAccessDenied,
    ForbiddenFieldUpdate,
    GitOpsRenderReference,
    IMMUTABLE_TENANT_FIELDS,
    ISOLATION_DEDICATED_STACK,
    IllegalTransition,
    OffboardRequest,
    PreconditionFailed,
    ProvisionRequest,
    PurgeRequest,
    RENDER_NOT_APPLICABLE,
    RENDER_REMOVED,
    RENDER_RENDERED,
    RENDER_REPLAYED_NO_DIFF,
    RENDER_RETAINED,
    ResumeRequest,
    SuspendRequest,
    TENANT_ID_PATTERN,
    TenantConflict,
    TenantNotFound,
    TransitionRequest,
    TransitionResult,
    ValidationFailed,
    parse_transition_request,
    validate_tenant_document,
)
from tenantctl.state_machine import (
    LifecycleStateMachine,
    TransitionSpec,
    load_state_machine,
)
from tenantctl.store import ControlPlaneStore

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Evidence categories, verbatim from the lifecycle contract's
# evidence_capture block; one control-plane evidence artifact per
# store proves deletion.
_EVIDENCE_CATEGORIES = (
    "opensearch_indices",
    "security_roles_and_mappings",
    "dashboard_spaces",
    "vector_indices",
    "graph_database",
    "gitops_overlay",
)


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class TenantControlPlaneService:
    """Contract-conformant tenant lifecycle executor."""

    def __init__(
        self,
        store: ControlPlaneStore,
        repo_root: Path,
        lifecycle_contract_path: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._repo_root = repo_root
        self._machine: LifecycleStateMachine = load_state_machine(
            lifecycle_contract_path
        )
        self._clock = clock if clock is not None else _default_clock

    # -- time helpers ---------------------------------------------------

    def _now_iso(self) -> str:
        return self._clock().astimezone(timezone.utc).strftime(
            _TIMESTAMP_FORMAT
        )

    @staticmethod
    def _parse_iso(value: str) -> datetime:
        return datetime.strptime(value, _TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )

    # -- CRUD -------------------------------------------------------------

    def create_tenant(
        self,
        document: Mapping[str, Any],
        *,
        caller_scope: str | None = None,
    ) -> dict[str, Any]:
        """Register a tenant contract document (enters the machine)."""
        validate_tenant_document(document)
        tenant_id = str(document["tenant_id"])
        self._check_scope(caller_scope, tenant_id)
        if document["lifecycle_state"] != self._machine.initial_state:
            raise ValidationFailed(
                "tenant creation requires lifecycle_state "
                f"{self._machine.initial_state!r}",
                tenant_id=tenant_id,
            )
        existing = self._store.load_tenant_record(tenant_id)
        if existing is not None:
            state = existing["document"]["lifecycle_state"]
            if state not in self._machine.terminal_states:
                raise TenantConflict(
                    f"tenant {tenant_id!r} already exists in lifecycle "
                    f"state {state!r}",
                    tenant_id=tenant_id,
                )
            # A purged tenant_id is reused only via a new contract
            # document (lifecycle invariant): the previous
            # incarnation's replay-detection records must not apply.
            self._store.clear_transition_records(tenant_id)
        self._store.save_tenant_record(
            tenant_id,
            {"document": dict(document), "legal_hold": False},
        )
        return dict(document)

    def get_tenant(
        self,
        tenant_id: str,
        *,
        caller_scope: str | None = None,
    ) -> dict[str, Any]:
        self._check_tenant_id(tenant_id)
        self._check_scope(caller_scope, tenant_id)
        record = self._store.load_tenant_record(tenant_id)
        if record is None:
            raise TenantNotFound(
                f"no tenant contract document for {tenant_id!r}",
                tenant_id=tenant_id,
            )
        document = record["document"]
        assert isinstance(document, dict)
        return document

    def list_tenants(
        self,
        lifecycle_state: str | None = None,
        *,
        caller_scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """Tenant documents visible to the caller (deny-by-default:
        a tenant-scoped caller sees only its own tenant)."""
        documents: list[dict[str, Any]] = []
        for tenant_id in self._store.list_tenant_ids():
            if caller_scope is not None and tenant_id != caller_scope:
                continue
            record = self._store.load_tenant_record(tenant_id)
            if record is None:
                continue
            document = record["document"]
            if (
                lifecycle_state is not None
                and document["lifecycle_state"] != lifecycle_state
            ):
                continue
            documents.append(document)
        return documents

    def update_tenant(
        self,
        tenant_id: str,
        document: Mapping[str, Any],
        *,
        caller_scope: str | None = None,
    ) -> dict[str, Any]:
        """Replace mutable descriptor fields (never lifecycle_state)."""
        self._check_tenant_id(tenant_id)
        self._check_scope(caller_scope, tenant_id)
        record = self._store.load_tenant_record(tenant_id)
        if record is None:
            raise TenantNotFound(
                f"no tenant contract document for {tenant_id!r}",
                tenant_id=tenant_id,
            )
        stored = record["document"]
        self._check_document_identity(tenant_id, stored)
        for field_name in IMMUTABLE_TENANT_FIELDS:
            if document.get(field_name) != stored.get(field_name):
                raise ForbiddenFieldUpdate(
                    f"field {field_name!r} is immutable through CRUD; "
                    "lifecycle_state changes only through transition "
                    "operations",
                    tenant_id=tenant_id,
                )
        validate_tenant_document(document)
        record["document"] = dict(document)
        self._store.save_tenant_record(tenant_id, record)
        return dict(document)

    def set_legal_hold(self, tenant_id: str, hold: bool) -> None:
        """Set the legal/residency hold flag (purge precondition)."""
        self._check_tenant_id(tenant_id)
        record = self._store.load_tenant_record(tenant_id)
        if record is None:
            raise TenantNotFound(
                f"no tenant contract document for {tenant_id!r}",
                tenant_id=tenant_id,
            )
        record["legal_hold"] = hold
        self._store.save_tenant_record(tenant_id, record)

    # -- transitions ------------------------------------------------------

    def transition(
        self,
        name: str,
        tenant_id: str,
        payload: Mapping[str, Any],
        *,
        caller_scope: str | None = None,
    ) -> TransitionResult:
        """Execute (or replay, or deny) one lifecycle transition."""
        # Path-parameter validation precedes the audited attempt: a
        # tenant_id failing the contract pattern is request-shape
        # validation (like a malformed create), and the audit contract
        # itself requires a well-formed tenant_id, so no denial record
        # is emitted for it.
        self._check_tenant_id(tenant_id)
        actor = "unknown"
        if isinstance(payload, Mapping):
            raw_actor = payload.get("actor")
            if isinstance(raw_actor, str) and raw_actor:
                actor = raw_actor
        try:
            return self._transition_inner(
                name, tenant_id, payload, caller_scope, actor
            )
        except ControlPlaneError as error:
            # Execution gate emit_audit_record_on_denial: every denied
            # attempt is audited, and the error carries the record id
            # so the API layer can populate audit_record_id.
            denial = audit_mod.emit_audit(
                self._store,
                tenant_id=tenant_id,
                transition=name,
                actor=actor,
                replay=False,
                outcome=audit_mod.OUTCOME_DENIED,
                recorded_at=self._now_iso(),
                extra_fields={
                    "error_code": error.error_code,
                    "message": error.message,
                },
            )
            error.audit_record_id = denial["audit_record_id"]
            if error.tenant_id is None:
                error.tenant_id = tenant_id
            raise

    def _transition_inner(
        self,
        name: str,
        tenant_id: str,
        payload: Mapping[str, Any],
        caller_scope: str | None,
        actor: str,
    ) -> TransitionResult:
        self._check_scope(caller_scope, tenant_id)
        spec = self._machine.spec(name)
        if spec is None:
            # deny_on_unknown_transition_or_state; the fixed API paths
            # make this unroutable over HTTP but the core guards it.
            raise IllegalTransition(
                f"unknown transition {name!r}", tenant_id=tenant_id
            )
        request = parse_transition_request(name, payload)
        record = self._store.load_tenant_record(tenant_id)
        if record is None:
            raise TenantNotFound(
                f"no tenant contract document for {tenant_id!r}",
                tenant_id=tenant_id,
            )
        document = record["document"]
        self._check_document_identity(tenant_id, document)
        # Approval gate first: an unapproved destructive request is
        # always denied, replay or not.
        approval_record: ApprovalRecord | None = None
        if spec.destructive:
            approval_payload = getattr(request, "approval", None)
            approval_record = approval_mod.validate_approval(
                approval_payload, spec.approval_risk_class or ""
            )
        # Execution gate validate_contract_document_before_transition.
        validate_tenant_document(document)
        current_state = document["lifecycle_state"]
        if not self._machine.is_state(current_state):
            raise TenantNotFound(
                f"tenant {tenant_id!r} is in unknown lifecycle state "
                f"{current_state!r}",
                tenant_id=tenant_id,
            )
        completed = self._store.load_transition_record(tenant_id, name)
        if current_state == spec.to_state and completed is not None:
            return self._replay(
                spec, tenant_id, document, request, approval_record,
                completed,
            )
        if current_state not in spec.from_states:
            raise IllegalTransition(
                f"transition {name!r} is not legal from state "
                f"{current_state!r}",
                tenant_id=tenant_id,
                details={
                    "current_state": current_state,
                    "allowed_from": list(spec.from_states),
                },
            )
        return self._apply(
            spec, tenant_id, record, document, request, approval_record,
            current_state,
        )

    # -- replay path ------------------------------------------------------

    def _replay(
        self,
        spec: TransitionSpec,
        tenant_id: str,
        document: dict[str, Any],
        request: TransitionRequest,
        approval_record: ApprovalRecord | None,
        completed: dict[str, Any],
    ) -> TransitionResult:
        """Audited no-op replay of a completed transition.

        Provision replays additionally converge drifted overlays
        (create-if-absent, converge-if-drifted per the lifecycle
        contract); every other replay leaves the tree untouched.
        """
        now = self._now_iso()
        dedicated = (
            document["isolation_class"] == ISOLATION_DEDICATED_STACK
        )
        render_ref = GitOpsRenderReference(
            render_action=RENDER_REPLAYED_NO_DIFF,
            overlay_path=(
                renders.overlay_dir(tenant_id)
                if dedicated and spec.name != "purge"
                else None
            ),
        )
        if spec.name == "provision":
            if dedicated:
                plan = renders.plan_overlay_render(
                    document,
                    self._store.render_manifest_path(tenant_id),
                )
                if renders.overlay_changed(plan, self._repo_root):
                    renders.execute_overlay_render(
                        plan, self._repo_root
                    )
                    self._store.save_prepared_commit(
                        tenant_id, spec.name, plan.commit_message
                    )
                    render_ref = GitOpsRenderReference(
                        render_action=RENDER_RENDERED,
                        overlay_path=renders.overlay_dir(tenant_id),
                        commit_ref=renders.commit_ref_for(plan),
                    )
            # Isolation artifacts converge on provision replay for
            # every isolation class (create-if-absent,
            # converge-if-drifted): execute_isolation_renders is
            # idempotent via the Batch 19 execute_plan and reports
            # which paths actually differed before the write.
            isolation_changed = isolation.execute_isolation_renders(
                isolation.plan_isolation_renders(
                    document, mode="provision"
                ),
                repo_root=self._repo_root,
                tenant_id=tenant_id,
            )
            if isolation_changed and (
                render_ref.render_action == RENDER_REPLAYED_NO_DIFF
            ):
                render_ref = GitOpsRenderReference(
                    render_action=RENDER_RENDERED,
                    overlay_path=(
                        renders.overlay_dir(tenant_id)
                        if dedicated
                        else None
                    ),
                )
        if spec.name == "purge":
            # delete-if-present: a leftover overlay from a partially
            # failed purge is removed on replay.
            if dedicated and renders.remove_overlay(
                self._repo_root, tenant_id
            ):
                render_ref = GitOpsRenderReference(
                    render_action=RENDER_REMOVED,
                    overlay_path=renders.overlay_dir(tenant_id),
                    commit_ref=f"prepared:removal:{tenant_id}",
                )
        extra = self._audit_extras(
            spec, request, approval_record, completed, now, replay=True
        )
        audit_record = audit_mod.emit_audit(
            self._store,
            tenant_id=tenant_id,
            transition=spec.name,
            actor=request.actor,
            replay=True,
            outcome=audit_mod.OUTCOME_REPLAYED,
            recorded_at=now,
            extra_fields=extra,
            required_fields=spec.audit_required_fields,
        )
        return TransitionResult(
            tenant_id=tenant_id,
            transition=spec.name,
            from_state=spec.to_state,
            lifecycle_state=spec.to_state,
            replay=True,
            audit=audit_record,
            gitops_render=render_ref,
        )

    # -- apply path -------------------------------------------------------

    def _apply(
        self,
        spec: TransitionSpec,
        tenant_id: str,
        record: dict[str, Any],
        document: dict[str, Any],
        request: TransitionRequest,
        approval_record: ApprovalRecord | None,
        from_state: str,
    ) -> TransitionResult:
        now = self._now_iso()
        dedicated = (
            document["isolation_class"] == ISOLATION_DEDICATED_STACK
        )
        self._check_preconditions(spec, tenant_id, record, document)
        transition_record: dict[str, Any] = {
            "transition": spec.name,
            "applied_at": now,
            "actor": request.actor,
        }
        if spec.name == "provision":
            render_ref = self._execute_provision(
                tenant_id, document, dedicated
            )
            transition_record["requested_at"] = now
            transition_record["completed_at"] = now
        elif spec.name in ("suspend", "resume", "offboard"):
            # The overlay is deliberately kept unchanged: suspension is
            # a sync toggle owned by the delivery ApplicationSet, and
            # offboarding retains the overlay until purge evidence is
            # recorded (overlay generation contract).
            render_ref = GitOpsRenderReference(
                render_action=(
                    RENDER_RETAINED if dedicated
                    else RENDER_NOT_APPLICABLE
                ),
                overlay_path=(
                    renders.overlay_dir(tenant_id) if dedicated else None
                ),
            )
            if spec.name == "offboard":
                ends_at = self._retention_window_end(document)
                transition_record["retention_window_ends_at"] = ends_at
            if isinstance(request, SuspendRequest):
                transition_record["trigger_type"] = request.trigger_type
        else:  # purge
            render_ref, evidence_refs = self._execute_purge(
                tenant_id, document, dedicated, now
            )
            transition_record["purged_at"] = now
            transition_record["evidence_artifact_refs"] = evidence_refs
        if approval_record is not None:
            transition_record["approval_id"] = (
                approval_record.approval_id
            )
            if approval_record.change_ticket is not None:
                transition_record["change_ticket"] = (
                    approval_record.change_ticket
                )
        document["lifecycle_state"] = spec.to_state
        record["document"] = document
        self._store.save_tenant_record(tenant_id, record)
        self._store.save_transition_record(
            tenant_id, spec.name, transition_record
        )
        extra = self._audit_extras(
            spec, request, approval_record, transition_record, now,
            replay=False,
        )
        audit_record = audit_mod.emit_audit(
            self._store,
            tenant_id=tenant_id,
            transition=spec.name,
            actor=request.actor,
            replay=False,
            outcome=audit_mod.OUTCOME_APPLIED,
            recorded_at=now,
            extra_fields=extra,
            required_fields=spec.audit_required_fields,
        )
        return TransitionResult(
            tenant_id=tenant_id,
            transition=spec.name,
            from_state=from_state,
            lifecycle_state=spec.to_state,
            replay=False,
            audit=audit_record,
            gitops_render=render_ref,
        )

    def _execute_provision(
        self,
        tenant_id: str,
        document: dict[str, Any],
        dedicated: bool,
    ) -> GitOpsRenderReference:
        # Task 3 replaces the stubs with the isolation-matrix renders;
        # the call sites are already wired so Task 3 is core-only.
        isolation_artifacts = isolation.plan_isolation_renders(
            document, mode="provision"
        )
        isolation.execute_isolation_renders(
            isolation_artifacts,
            repo_root=self._repo_root,
            tenant_id=tenant_id,
        )
        if not dedicated:
            return GitOpsRenderReference(
                render_action=RENDER_NOT_APPLICABLE
            )
        plan = renders.plan_overlay_render(
            document, self._store.render_manifest_path(tenant_id)
        )
        renders.execute_overlay_render(plan, self._repo_root)
        self._store.save_prepared_commit(
            tenant_id, "provision", plan.commit_message
        )
        return GitOpsRenderReference(
            render_action=RENDER_RENDERED,
            overlay_path=renders.overlay_dir(tenant_id),
            commit_ref=renders.commit_ref_for(plan),
        )

    def _execute_purge(
        self,
        tenant_id: str,
        document: dict[str, Any],
        dedicated: bool,
        now: str,
    ) -> tuple[GitOpsRenderReference, list[str]]:
        if dedicated:
            renders.remove_overlay(self._repo_root, tenant_id)
            commit_message = renders.removal_commit_message(tenant_id)
            self._store.save_prepared_commit(
                tenant_id, "purge", commit_message
            )
            render_ref = GitOpsRenderReference(
                render_action=RENDER_REMOVED,
                overlay_path=renders.overlay_dir(tenant_id),
                commit_ref=f"prepared:removal:{tenant_id}",
            )
        else:
            render_ref = GitOpsRenderReference(
                render_action=RENDER_NOT_APPLICABLE
            )
        evidence_refs: list[str] = []
        for category in _EVIDENCE_CATEGORIES:
            applicable = category != "gitops_overlay" or dedicated
            payload: dict[str, Any] = {
                "category": category,
                "tenant_id": tenant_id,
                "captured_at": now,
                "status": (
                    "recorded" if applicable else "not-applicable"
                ),
            }
            if category == "gitops_overlay" and dedicated:
                payload["overlay_path"] = renders.overlay_dir(tenant_id)
                payload["commit_ref"] = f"prepared:removal:{tenant_id}"
            evidence_refs.append(
                self._store.save_evidence(tenant_id, category, payload)
            )
        return render_ref, evidence_refs

    # -- gates and helpers -------------------------------------------------

    def _check_tenant_id(self, tenant_id: str) -> None:
        """Reject path-parameter tenant ids that fail the contract
        pattern (TENANT_CONTRACT_SCHEMA_V1.json) before any store or
        render path is derived from them: the store and the renderer
        use tenant_id as a filesystem path segment, so traversal
        sequences, empty ids, and hostile unicode must never reach a
        path constructor."""
        if not isinstance(tenant_id, str) or not TENANT_ID_PATTERN.match(
            tenant_id
        ):
            raise ValidationFailed(
                "tenant_id does not match the tenant_id pattern of "
                "TENANT_CONTRACT_SCHEMA_V1.json"
            )

    def _check_document_identity(
        self, tenant_id: str, document: Mapping[str, Any]
    ) -> None:
        """A stored document whose tenant_id differs from the
        addressed tenant_id is store corruption or tampering; refuse
        to act on it."""
        if document.get("tenant_id") != tenant_id:
            raise ValidationFailed(
                "stored tenant document tenant_id "
                f"{document.get('tenant_id')!r} does not match the "
                f"addressed tenant_id {tenant_id!r}",
                tenant_id=tenant_id,
            )

    def _check_scope(
        self, caller_scope: str | None, tenant_id: str
    ) -> None:
        # Deny-by-default cross-tenant rule (TR-16): a tenant-scoped
        # caller may only address its own tenant_id.
        if caller_scope is not None and caller_scope != tenant_id:
            raise CrossTenantAccessDenied(
                "caller is not authorized for the addressed tenant",
                tenant_id=tenant_id,
            )

    def _retention_window_end(self, document: dict[str, Any]) -> str:
        retention = document["quotas"]["retention"]
        days = max(
            retention["logs_days"],
            retention["metrics_days"],
            retention["traces_days"],
        )
        ends = self._clock().astimezone(timezone.utc) + timedelta(
            days=days
        )
        return ends.strftime(_TIMESTAMP_FORMAT)

    def _check_preconditions(
        self,
        spec: TransitionSpec,
        tenant_id: str,
        record: dict[str, Any],
        document: dict[str, Any],
    ) -> None:
        if spec.name == "provision":
            residency = document["residency"]
            allowed = residency.get("allowed_regions")
            if allowed is not None and residency["region"] not in allowed:
                # The schema documents allowed_regions membership as a
                # procedural check; provisioning is where residency
                # must be satisfiable before any partition is created.
                raise PreconditionFailed(
                    "residency.region is not in "
                    "residency.allowed_regions; residency constraints "
                    "must be satisfiable before provisioning",
                    tenant_id=tenant_id,
                )
        if spec.name == "purge":
            offboarded = self._store.load_transition_record(
                tenant_id, "offboard"
            )
            if offboarded is None:
                raise PreconditionFailed(
                    "purge requires a completed offboard transition "
                    "with its audit record present",
                    tenant_id=tenant_id,
                )
            ends_at = offboarded.get("retention_window_ends_at")
            if not isinstance(ends_at, str):
                raise PreconditionFailed(
                    "offboard record lacks retention_window_ends_at",
                    tenant_id=tenant_id,
                )
            if self._clock().astimezone(timezone.utc) < self._parse_iso(
                ends_at
            ):
                raise PreconditionFailed(
                    "the retention window recorded at offboarding has "
                    f"not elapsed (ends {ends_at})",
                    tenant_id=tenant_id,
                    details={"retention_window_ends_at": ends_at},
                )
            if record.get("legal_hold"):
                raise PreconditionFailed(
                    "a legal or residency hold is set on the tenant",
                    tenant_id=tenant_id,
                )

    def _audit_extras(
        self,
        spec: TransitionSpec,
        request: TransitionRequest,
        approval_record: ApprovalRecord | None,
        transition_record: dict[str, Any],
        now: str,
        *,
        replay: bool,
    ) -> dict[str, Any]:
        """Per-transition audit fields (lifecycle required_fields).

        Replays source time-anchored fields from the completed
        transition record: provisioning timestamps, the retention
        clock, purge evidence, and purged_at are never reset by a
        replay.
        """
        extra: dict[str, Any] = {}
        if isinstance(request, ProvisionRequest):
            if replay:
                # The record saved at first completion carries the
                # original timestamps; fall back to now only for
                # records predating that field (defensive, never
                # expected for stores written by this service).
                extra["requested_at"] = transition_record.get(
                    "requested_at", now
                )
                extra["completed_at"] = transition_record.get(
                    "completed_at", now
                )
            else:
                extra["requested_at"] = now
                extra["completed_at"] = now
        elif isinstance(request, SuspendRequest):
            extra["trigger_type"] = request.trigger_type
            extra["reason"] = request.reason
        elif isinstance(request, ResumeRequest):
            extra["reason"] = request.reason
        elif isinstance(request, OffboardRequest):
            assert approval_record is not None
            extra["approval_id"] = approval_record.approval_id
            extra["reason"] = request.reason
            extra["retention_window_ends_at"] = transition_record[
                "retention_window_ends_at"
            ]
        elif isinstance(request, PurgeRequest):
            assert approval_record is not None
            assert approval_record.change_ticket is not None
            extra["approval_id"] = approval_record.approval_id
            extra["change_ticket"] = approval_record.change_ticket
            extra["evidence_artifact_refs"] = list(
                transition_record["evidence_artifact_refs"]
            )
            extra["purged_at"] = transition_record["purged_at"]
        del spec
        return extra
