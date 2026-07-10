"""Typed models, contract-fixed error shapes, and document validation.

Pins the values fixed by contracts/tenancy/TENANT_CONTROL_PLANE_API_V1
.yaml (error codes, transition request/response shapes, the GitOps
render reference enum) and validates tenant contract documents against
contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json with a bespoke
stdlib-only validator, mirroring the repo-wide no-pytest, no-PyPI CI
posture (ADR-0004).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

# Enums, verbatim from TENANT_CONTRACT_SCHEMA_V1.json.
TENANT_ID_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
TIERS = ("starter", "standard", "premium", "enterprise")
ISOLATION_CLASSES = (
    "shared-partition",
    "dedicated-indices",
    "dedicated-stack",
)
LIFECYCLE_STATES = (
    "provisioning",
    "active",
    "suspended",
    "offboarding",
    "purged",
)
CONTACT_ROLES = ("technical", "billing", "security", "operations")
POOLS = ("shared", "dedicated")
ISOLATION_DEDICATED_STACK = "dedicated-stack"

# Immutable fields of TenantUpdateRequest (x-immutable-fields).
IMMUTABLE_TENANT_FIELDS = ("tenant_id", "lifecycle_state", "created_at")

# GitOpsRenderReference.render_action enum, verbatim from the API
# contract.
RENDER_RENDERED = "rendered"
RENDER_RETAINED = "retained"
RENDER_REMOVED = "removed"
RENDER_NOT_APPLICABLE = "not-applicable"
RENDER_REPLAYED_NO_DIFF = "replayed-no-diff"

TRANSITION_NAMES = ("provision", "suspend", "resume", "offboard", "purge")


class ControlPlaneError(Exception):
    """Base of every contract-fixed error (ErrorResponse shape).

    audit_record_id is populated by the service for transition denials
    (execution gate emit_audit_record_on_denial) before the error
    propagates to the API layer.
    """

    error_code: str = "validation-failed"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        tenant_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.tenant_id = tenant_id
        self.details = details
        self.audit_record_id: str | None = None

    def to_response(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.audit_record_id is not None:
            payload["audit_record_id"] = self.audit_record_id
        if self.details is not None:
            payload["details"] = self.details
        return payload


class ValidationFailed(ControlPlaneError):
    error_code = "validation-failed"
    http_status = 400


class TenantNotFound(ControlPlaneError):
    error_code = "tenant-not-found"
    http_status = 404


class TenantConflict(ControlPlaneError):
    error_code = "tenant-already-exists"
    http_status = 409


class ForbiddenFieldUpdate(ControlPlaneError):
    error_code = "update-forbidden-field"
    http_status = 409


class IllegalTransition(ControlPlaneError):
    error_code = "illegal-transition"
    http_status = 409


class PreconditionFailed(ControlPlaneError):
    error_code = "precondition-failed"
    http_status = 409


class ApprovalRequired(ControlPlaneError):
    error_code = "approval-required"
    http_status = 403


class ApprovalInvalid(ControlPlaneError):
    error_code = "approval-invalid"
    http_status = 403


class CrossTenantAccessDenied(ControlPlaneError):
    error_code = "cross-tenant-access-denied"
    http_status = 403


@dataclass(frozen=True)
class ApprovalRecord:
    """A validated approval record (APPROVAL_FLOW_V1.yaml fields)."""

    approval_id: str
    approver: str
    decision: str
    decided_at: str
    change_ticket: str | None = None


@dataclass(frozen=True)
class ProvisionRequest:
    actor: str
    reason: str | None = None


@dataclass(frozen=True)
class SuspendRequest:
    actor: str
    trigger_type: str
    reason: str


@dataclass(frozen=True)
class ResumeRequest:
    actor: str
    reason: str


@dataclass(frozen=True)
class OffboardRequest:
    actor: str
    reason: str
    # None means the contract-required approval block was absent; the
    # approval gate turns that into approval-required (403), not a 400,
    # matching the AccessDenied wording of the API contract.
    approval: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class PurgeRequest:
    actor: str
    approval: Mapping[str, Any] | None = None
    reason: str | None = None


TransitionRequest = (
    ProvisionRequest
    | SuspendRequest
    | ResumeRequest
    | OffboardRequest
    | PurgeRequest
)


@dataclass(frozen=True)
class GitOpsRenderReference:
    """GitOps materialization of a transition (TR-10)."""

    render_action: str
    overlay_path: str | None = None
    commit_ref: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {"render_action": self.render_action}
        if self.overlay_path is not None:
            payload["overlay_path"] = self.overlay_path
        if self.commit_ref is not None:
            payload["commit_ref"] = self.commit_ref
        return payload


@dataclass(frozen=True)
class TransitionResult:
    """Common shape of every successful transition response."""

    tenant_id: str
    transition: str
    from_state: str
    lifecycle_state: str
    replay: bool
    audit: dict[str, Any]
    gitops_render: GitOpsRenderReference

    def to_response(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "transition": self.transition,
            "from_state": self.from_state,
            "lifecycle_state": self.lifecycle_state,
            "replay": self.replay,
            "audit": dict(self.audit),
            "gitops_render": self.gitops_render.to_dict(),
        }


def _require_str(
    payload: Mapping[str, Any],
    key: str,
    errors: list[str],
    *,
    context: str,
    min_length: int = 0,
    max_length: int | None = None,
    pattern: re.Pattern[str] | None = None,
    enum: tuple[str, ...] | None = None,
) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        errors.append(f"{context}.{key} must be a string")
        return None
    if len(value) < min_length:
        errors.append(
            f"{context}.{key} must be at least {min_length} chars"
        )
    if max_length is not None and len(value) > max_length:
        errors.append(
            f"{context}.{key} must be at most {max_length} chars"
        )
    if pattern is not None and not pattern.match(value):
        errors.append(f"{context}.{key} does not match {pattern.pattern}")
    if enum is not None and value not in enum:
        errors.append(f"{context}.{key} must be one of {list(enum)}")
    return value


def _check_keys(
    payload: Mapping[str, Any],
    required: tuple[str, ...],
    optional: tuple[str, ...],
    errors: list[str],
    *,
    context: str,
) -> bool:
    ok = True
    for key in required:
        if key not in payload:
            errors.append(f"{context} is missing required field {key!r}")
            ok = False
    allowed = set(required) | set(optional)
    for key in payload:
        if key not in allowed:
            errors.append(f"{context} has unknown field {key!r}")
            ok = False
    return ok


def _validate_residency(
    residency: Any, errors: list[str]
) -> None:
    if not isinstance(residency, Mapping):
        errors.append("residency must be an object")
        return
    _check_keys(
        residency,
        ("region", "data_residency_required", "pool"),
        ("allowed_regions",),
        errors,
        context="residency",
    )
    _require_str(
        residency, "region", errors, context="residency", min_length=1
    )
    if not isinstance(residency.get("data_residency_required"), bool):
        errors.append("residency.data_residency_required must be boolean")
    _require_str(residency, "pool", errors, context="residency", enum=POOLS)
    allowed_regions = residency.get("allowed_regions")
    if allowed_regions is not None:
        if (
            not isinstance(allowed_regions, list)
            or not allowed_regions
            or not all(
                isinstance(region, str) and region
                for region in allowed_regions
            )
        ):
            errors.append(
                "residency.allowed_regions must be a non-empty list of "
                "non-empty strings"
            )


def _validate_quotas(quotas: Any, errors: list[str]) -> None:
    if not isinstance(quotas, Mapping):
        errors.append("quotas must be an object")
        return
    _check_keys(
        quotas, ("ingest", "retention"), (), errors, context="quotas"
    )
    ingest = quotas.get("ingest")
    if isinstance(ingest, Mapping):
        _check_keys(
            ingest,
            ("max_gb_per_day",),
            ("max_events_per_second",),
            errors,
            context="quotas.ingest",
        )
        max_gb = ingest.get("max_gb_per_day")
        if (
            not isinstance(max_gb, (int, float))
            or isinstance(max_gb, bool)
            or max_gb <= 0
        ):
            errors.append(
                "quotas.ingest.max_gb_per_day must be a number > 0"
            )
        max_eps = ingest.get("max_events_per_second")
        if max_eps is not None and (
            not isinstance(max_eps, int)
            or isinstance(max_eps, bool)
            or max_eps < 1
        ):
            errors.append(
                "quotas.ingest.max_events_per_second must be an "
                "integer >= 1"
            )
    else:
        errors.append("quotas.ingest must be an object")
    retention = quotas.get("retention")
    if isinstance(retention, Mapping):
        _check_keys(
            retention,
            ("logs_days", "metrics_days", "traces_days"),
            (),
            errors,
            context="quotas.retention",
        )
        for key in ("logs_days", "metrics_days", "traces_days"):
            days = retention.get(key)
            if (
                not isinstance(days, int)
                or isinstance(days, bool)
                or not 1 <= days <= 3650
            ):
                errors.append(
                    f"quotas.retention.{key} must be an integer in "
                    "[1, 3650]"
                )
    else:
        errors.append("quotas.retention must be an object")


def validate_tenant_document(document: Any) -> None:
    """Validate one tenant contract document.

    Bespoke check for every constraint TENANT_CONTRACT_SCHEMA_V1.json
    declares, including the dedicated-stack => residency.pool ==
    dedicated conditional. Raises ValidationFailed listing every
    violation found; a valid document returns None.
    """
    if not isinstance(document, Mapping):
        raise ValidationFailed("tenant document must be a JSON object")
    errors: list[str] = []
    _check_keys(
        document,
        (
            "tenant_id",
            "display_name",
            "tier",
            "isolation_class",
            "residency",
            "lifecycle_state",
            "owner",
            "contacts",
            "quotas",
            "created_at",
        ),
        (),
        errors,
        context="tenant document",
    )
    _require_str(
        document,
        "tenant_id",
        errors,
        context="tenant",
        pattern=TENANT_ID_PATTERN,
    )
    _require_str(
        document,
        "display_name",
        errors,
        context="tenant",
        min_length=1,
        max_length=128,
    )
    _require_str(document, "tier", errors, context="tenant", enum=TIERS)
    _require_str(
        document,
        "isolation_class",
        errors,
        context="tenant",
        enum=ISOLATION_CLASSES,
    )
    _require_str(
        document,
        "lifecycle_state",
        errors,
        context="tenant",
        enum=LIFECYCLE_STATES,
    )
    _require_str(
        document,
        "created_at",
        errors,
        context="tenant",
        pattern=DATETIME_PATTERN,
    )
    _validate_residency(document.get("residency"), errors)
    owner = document.get("owner")
    if isinstance(owner, Mapping):
        _check_keys(
            owner, ("name", "email"), ("team",), errors, context="owner"
        )
        _require_str(owner, "name", errors, context="owner", min_length=1)
        _require_str(
            owner, "email", errors, context="owner", pattern=EMAIL_PATTERN
        )
        if "team" in owner:
            _require_str(
                owner, "team", errors, context="owner", min_length=1
            )
    else:
        errors.append("owner must be an object")
    contacts = document.get("contacts")
    if isinstance(contacts, list) and contacts:
        for index, contact in enumerate(contacts):
            context = f"contacts[{index}]"
            if not isinstance(contact, Mapping):
                errors.append(f"{context} must be an object")
                continue
            _check_keys(
                contact, ("role", "email"), (), errors, context=context
            )
            _require_str(
                contact, "role", errors, context=context, enum=CONTACT_ROLES
            )
            _require_str(
                contact,
                "email",
                errors,
                context=context,
                pattern=EMAIL_PATTERN,
            )
    else:
        errors.append("contacts must be a non-empty array")
    _validate_quotas(document.get("quotas"), errors)
    residency = document.get("residency")
    if (
        document.get("isolation_class") == ISOLATION_DEDICATED_STACK
        and isinstance(residency, Mapping)
        and residency.get("pool") != "dedicated"
    ):
        errors.append(
            "isolation_class dedicated-stack requires residency.pool "
            "dedicated"
        )
    if errors:
        raise ValidationFailed(
            "tenant document fails "
            "TENANT_CONTRACT_SCHEMA_V1.json validation: "
            + "; ".join(errors)
        )


def _parse_common(
    payload: Any,
    required: tuple[str, ...],
    optional: tuple[str, ...],
    *,
    transition: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValidationFailed(
            f"{transition} request body must be a JSON object"
        )
    errors: list[str] = []
    _check_keys(
        payload, required, optional, errors, context=f"{transition} request"
    )
    if errors:
        raise ValidationFailed("; ".join(errors))
    for key in required:
        value = payload[key]
        # approval blocks are validated separately by tenantctl.approval;
        # every other required field of the request schemas is a
        # minLength-1 string (or the trigger_type enum, checked below).
        if key == "approval":
            continue
        if not isinstance(value, str) or not value:
            raise ValidationFailed(
                f"{transition} request field {key!r} must be a "
                "non-empty string"
            )
    return dict(payload)


def parse_transition_request(
    transition: str, payload: Any
) -> TransitionRequest:
    """Validate a raw request body against the API request schemas."""
    if transition == "provision":
        data = _parse_common(
            payload, ("actor",), ("reason",), transition=transition
        )
        return ProvisionRequest(
            actor=data["actor"], reason=data.get("reason")
        )
    if transition == "suspend":
        data = _parse_common(
            payload,
            ("actor", "trigger_type", "reason"),
            (),
            transition=transition,
        )
        if data["trigger_type"] not in ("operator", "automated"):
            raise ValidationFailed(
                "suspend request trigger_type must be 'operator' or "
                "'automated'"
            )
        return SuspendRequest(
            actor=data["actor"],
            trigger_type=data["trigger_type"],
            reason=data["reason"],
        )
    if transition == "resume":
        data = _parse_common(
            payload, ("actor", "reason"), (), transition=transition
        )
        return ResumeRequest(actor=data["actor"], reason=data["reason"])
    if transition == "offboard":
        data = _parse_common(
            payload,
            ("actor", "reason"),
            ("approval",),
            transition=transition,
        )
        return OffboardRequest(
            actor=data["actor"],
            reason=data["reason"],
            approval=data.get("approval"),
        )
    if transition == "purge":
        data = _parse_common(
            payload,
            ("actor",),
            ("reason", "approval"),
            transition=transition,
        )
        reason = data.get("reason")
        if reason is not None and (
            not isinstance(reason, str) or not reason
        ):
            raise ValidationFailed(
                "purge request field 'reason' must be a non-empty string"
            )
        return PurgeRequest(
            actor=data["actor"],
            approval=data.get("approval"),
            reason=reason,
        )
    raise ValidationFailed(f"unknown transition {transition!r}")
