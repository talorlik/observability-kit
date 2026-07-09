"""File-backed control-plane record store.

Holds control-plane data only, per the plane-separation rules of
contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml: tenant
contract documents, completed-transition records (the replay-detection
surface), audit records, purge evidence, and prepared GitOps commit
material. Never tenant telemetry - records may reference telemetry
(index names, counts, digests) but never embed payloads.

The layout under the store root:

- tenants/<tenant_id>.json: {"document": ..., "legal_hold": bool}
- transitions/<tenant_id>/<transition>.json: completed transitions
- audit/<audit_record_id>.json: append-only audit records
- evidence/<tenant_id>/<category>.json: purge deletion evidence
- renders/<tenant_id>/: per-tenant render manifest and prepared
  commit messages (written through the Batch 19 renderer's
  execute_plan and by tenantctl.renders)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _dump(payload: dict[str, Any]) -> str:
    # Same canonical shape as obskit.emit.canonical_json, restated here
    # so the store itself stays free of cross-package imports.
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_atomic(path: Path, text: str) -> None:
    """Atomically write text: temp file in the SAME directory, then
    os.replace. A crash mid-write leaves either the previous record or
    the new one, never a torn file. The store assumes a single writer
    process (ADR-0004); atomicity here is crash safety, not
    multi-writer coordination.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(tmp_name, path)
    finally:
        # os.replace consumed the temp file on success; only a failed
        # write or replace leaves it behind.
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


class ControlPlaneStore:
    """Control-plane records on the local filesystem."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    # -- tenant records ------------------------------------------------

    def _tenant_path(self, tenant_id: str) -> Path:
        return self.root / "tenants" / f"{tenant_id}.json"

    def tenant_exists(self, tenant_id: str) -> bool:
        return self._tenant_path(tenant_id).is_file()

    def load_tenant_record(self, tenant_id: str) -> dict[str, Any] | None:
        path = self._tenant_path(tenant_id)
        if not path.is_file():
            return None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(
                f"tenant record {path} must be a JSON object, got "
                f"{type(loaded).__name__}"
            )
        return loaded

    def save_tenant_record(
        self, tenant_id: str, record: dict[str, Any]
    ) -> None:
        _write_atomic(self._tenant_path(tenant_id), _dump(record))

    def list_tenant_ids(self) -> tuple[str, ...]:
        tenants_dir = self.root / "tenants"
        if not tenants_dir.is_dir():
            return ()
        return tuple(
            sorted(
                path.stem
                for path in tenants_dir.glob("*.json")
                if path.is_file()
            )
        )

    # -- completed-transition records (replay detection) ---------------

    def _transition_path(self, tenant_id: str, transition: str) -> Path:
        return (
            self.root / "transitions" / tenant_id / f"{transition}.json"
        )

    def load_transition_record(
        self, tenant_id: str, transition: str
    ) -> dict[str, Any] | None:
        path = self._transition_path(tenant_id, transition)
        if not path.is_file():
            return None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(
                f"transition record {path} must be a JSON object, got "
                f"{type(loaded).__name__}"
            )
        return loaded

    def save_transition_record(
        self,
        tenant_id: str,
        transition: str,
        record: dict[str, Any],
    ) -> None:
        _write_atomic(
            self._transition_path(tenant_id, transition), _dump(record)
        )

    def clear_transition_records(self, tenant_id: str) -> None:
        """Drop completed-transition records for a tenant_id.

        Used only when a purged tenant_id is reused via a new contract
        document (re-onboarding is a new provision): the previous
        incarnation's replay-detection records must not leak into the
        new lifecycle. Audit and evidence records are never cleared.
        """
        directory = self.root / "transitions" / tenant_id
        if not directory.is_dir():
            return
        for path in directory.glob("*.json"):
            path.unlink()

    # -- audit records --------------------------------------------------

    def append_audit(self, record: dict[str, Any]) -> str:
        """Persist one audit record, assigning the next record id."""
        audit_dir = self.root / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        sequence = len(list(audit_dir.glob("audit-*.json"))) + 1
        audit_record_id = f"audit-{sequence:06d}"
        stamped = {"audit_record_id": audit_record_id, **record}
        _write_atomic(audit_dir / f"{audit_record_id}.json", _dump(stamped))
        return audit_record_id

    def load_audit_records(self) -> tuple[dict[str, Any], ...]:
        audit_dir = self.root / "audit"
        if not audit_dir.is_dir():
            return ()
        records = []
        for path in sorted(audit_dir.glob("audit-*.json")):
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(
                    f"audit record {path} must be a JSON object, got "
                    f"{type(loaded).__name__}"
                )
            records.append(loaded)
        return tuple(records)

    # -- purge evidence --------------------------------------------------

    def save_evidence(
        self,
        tenant_id: str,
        category: str,
        payload: dict[str, Any],
    ) -> str:
        """Persist one deletion-evidence artifact; returns its ref."""
        path = self.root / "evidence" / tenant_id / f"{category}.json"
        _write_atomic(path, _dump(payload))
        return f"evidence/{tenant_id}/{category}.json"

    # -- prepared GitOps commit material ---------------------------------

    def render_dir(self, tenant_id: str) -> Path:
        return self.root / "renders" / tenant_id

    def render_manifest_path(self, tenant_id: str) -> Path:
        return (
            self.render_dir(tenant_id)
            / "TENANT_OVERLAY_RENDER_MANIFEST.json"
        )

    def save_prepared_commit(
        self, tenant_id: str, transition: str, message: str
    ) -> str:
        path = (
            self.render_dir(tenant_id)
            / f"prepared_commit_{transition}.txt"
        )
        _write_atomic(path, message)
        return f"renders/{tenant_id}/prepared_commit_{transition}.txt"
