"""Vendor-neutral invoice export construction.

Executes contracts/commercial/INVOICE_EXPORT_CONTRACT_V1.yaml: one
export document per tenant per billing period, derived from validated
usage records plus the plan catalog, deterministic apart from
generated_at, with the overage semantics the contract fixes per
dimension. The document shape is exactly
contracts/commercial/INVOICE_EXPORT_SCHEMA_V1.json.

Currency never appears here: the export is currency-neutral plan
units, and currency assignment is adapter-side only (the
adapters/billing/ boundary). Stdlib-only, frozen dataclasses, no
third-party dependency (ADR-0006).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from commercialsvc.models import (
    COLLECTOR_VERSION,
    DIMENSION_BINDINGS,
    MeteringError,
    TELEMETRY_SIGNALS,
    UsageRecord,
    utc_now_timestamp,
)

# Overage units and quantities are rounded to a fixed precision so
# repeated builds are byte-identical regardless of float formatting
# drift (same posture as the metering builder's GB rounding).
_UNIT_PRECISION = 6
# query_volume block size: every started block of this many queries in
# the period is billable (ceil semantics, full-quantity basis).
QUERY_VOLUME_BLOCK = 1000

# Dotted plan catalog quota_bounds keys, verbatim from
# contracts/commercial/PLAN_CATALOG_V1.yaml.
_INGEST_BOUND_KEY = "quotas.ingest.max_gb_per_day"
_RETENTION_BOUND_KEYS = {
    signal: f"quotas.retention.{signal}_days"
    for signal in TELEMETRY_SIGNALS
}


class InvoiceExportError(MeteringError):
    """Invoice export inputs or document failed contract validation."""


@dataclass(frozen=True)
class BillingPlan:
    """One plan catalog entry, reduced to what invoicing needs.

    Bound maxima come from the plan's quota_bounds (the max side is
    the billing bound per INVOICE_EXPORT_CONTRACT_V1.yaml
    overage_semantics); rates come from billing.overage.
    """

    plan_id: str
    tier: str
    base_monthly_units: float
    ingest_gb_per_day_max: float
    retention_days_max: Mapping[str, float]
    overage_rate_units: Mapping[str, float]


def from_plan_catalog_dict(catalog: Mapping[str, Any], tier: str) -> BillingPlan:
    """Build a BillingPlan from a JSON-shaped PLAN_CATALOG_V1.yaml dict.

    The catalog dict uses the YAML's dotted quota_bounds keys as
    literal dict keys, so a CI validator can feed venv-parsed YAML (or
    the committed JSON mirror fixture) straight in.
    """
    plans = catalog.get("plans")
    if not isinstance(plans, list):
        raise InvoiceExportError("plan catalog has no plans list")
    matches = [
        plan
        for plan in plans
        if isinstance(plan, Mapping) and plan.get("tier") == tier
    ]
    if len(matches) != 1:
        raise InvoiceExportError(
            f"expected exactly one plan bound to tier {tier!r}, "
            f"found {len(matches)} (tier binding is bijective)"
        )
    plan = matches[0]
    try:
        bounds = plan["quota_bounds"]
        billing = plan["billing"]
        overage = billing["overage"]
        return BillingPlan(
            plan_id=plan["plan_id"],
            tier=plan["tier"],
            base_monthly_units=billing["base_monthly_units"],
            ingest_gb_per_day_max=bounds[_INGEST_BOUND_KEY]["max"],
            retention_days_max={
                signal: bounds[key]["max"]
                for signal, key in _RETENTION_BOUND_KEYS.items()
            },
            overage_rate_units={
                dimension: overage[dimension]["rate_units"]
                for dimension in DIMENSION_BINDINGS
            },
        )
    except (KeyError, TypeError) as error:
        raise InvoiceExportError(
            f"plan for tier {tier!r} is missing a required catalog "
            f"field: {error}"
        ) from error


@dataclass(frozen=True)
class InvoiceLineItem:
    """One (dimension, signal) aggregation over the billing period.

    Field names match INVOICE_EXPORT_SCHEMA_V1.json line_items items
    exactly.
    """

    dimension: str
    signal: str
    quantity: float
    unit: str
    overage_units: float
    source_record_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "signal": self.signal,
            "quantity": self.quantity,
            "unit": self.unit,
            "overage_units": self.overage_units,
            "source_record_count": self.source_record_count,
        }


@dataclass(frozen=True)
class InvoiceExport:
    """One invoice export document (INVOICE_EXPORT_SCHEMA_V1.json).

    Field names match the schema exactly; to_dict() emits the document
    a billing adapter consumes through the invoice-export contract.
    """

    invoice_id: str
    tenant_id: str
    plan_id: str
    tier: str
    period_start: str
    period_end: str
    line_items: tuple[InvoiceLineItem, ...]
    base_monthly_units: float
    overage_units: float
    total_units: float
    generated_at: str
    exporter_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "tenant_id": self.tenant_id,
            "plan_id": self.plan_id,
            "tier": self.tier,
            "billing_period": {
                "start": self.period_start,
                "end": self.period_end,
            },
            "line_items": [
                item.to_dict() for item in self.line_items
            ],
            "totals": {
                "base_monthly_units": self.base_monthly_units,
                "overage_units": self.overage_units,
                "total_units": self.total_units,
            },
            "generated_at": self.generated_at,
            "exporter_version": self.exporter_version,
        }


def invoice_id_for(
    tenant_id: str, period_start: str, period_end: str
) -> str:
    """Deterministic invoice id: tenant:start-date:end-date."""
    return f"{tenant_id}:{period_start[:10]}:{period_end[:10]}"


def _round_units(value: float) -> float:
    # round() keeps ints exact and normalizes float drift; +0.0 folds
    # a possible -0.0 to 0.0 so serialization stays byte-identical.
    return round(value, _UNIT_PRECISION) + 0.0


def _overage_units(
    dimension: str,
    signal: str,
    values: list[float],
    plan: BillingPlan,
) -> float:
    """Overage per INVOICE_EXPORT_CONTRACT_V1.yaml overage_semantics."""
    rate = plan.overage_rate_units[dimension]
    if dimension == "ingest_gb_per_day":
        bound = plan.ingest_gb_per_day_max
        over = sum(max(0.0, value - bound) for value in values)
        return _round_units(over * rate)
    if dimension == "retention_days":
        bound = plan.retention_days_max[signal]
        over = sum(max(0.0, value - bound) for value in values)
        return _round_units(over * rate)
    if dimension == "active_tenants":
        # full-quantity basis; rate_units is currently 0 in every
        # plan, so the line item records activity without charging.
        return _round_units(sum(values) * rate)
    # query_volume: full-quantity basis, every started block of
    # QUERY_VOLUME_BLOCK queries in the period is billable (ceil
    # semantics; implicit bound 0).
    blocks = math.ceil(sum(values) / QUERY_VOLUME_BLOCK)
    return _round_units(blocks * rate)


def _parse_timestamp(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise InvoiceExportError(
            f"{field_name} {value!r} is not a valid timestamp"
        ) from error


def build_invoice(
    tenant_id: str,
    plan: BillingPlan,
    records: tuple[UsageRecord, ...],
    period_start: str,
    period_end: str,
    exporter_version: str = COLLECTOR_VERSION,
    generated_at: str | None = None,
) -> InvoiceExport:
    """Build the one export document for one tenant and one period.

    Pure apart from the generated_at default: the same records, plan,
    and period yield a byte-identical document otherwise. Raises
    InvoiceExportError on an empty record set, a foreign tenant_id
    (an invoice is single-tenant; TR-16 attribution), a record window
    outside the period, or a non-positive period.
    """
    start = _parse_timestamp(period_start, "period_start")
    end = _parse_timestamp(period_end, "period_end")
    if end <= start:
        raise InvoiceExportError(
            "period_end must be strictly after period_start"
        )
    if not records:
        raise InvoiceExportError(
            "cannot build an invoice from an empty record set"
        )
    for record in records:
        if record.tenant_id != tenant_id:
            raise InvoiceExportError(
                f"record {record.record_id} carries foreign tenant "
                f"{record.tenant_id!r}; an invoice is single-tenant"
            )
        window_start = _parse_timestamp(
            record.window_start, "window_start"
        )
        window_end = _parse_timestamp(record.window_end, "window_end")
        if window_start < start or window_end > end:
            raise InvoiceExportError(
                f"record {record.record_id} window falls outside the "
                "billing period"
            )

    grouped: dict[tuple[str, str], list[UsageRecord]] = {}
    for record in records:
        key = (record.dimension, record.signal)
        grouped.setdefault(key, []).append(record)

    line_items = []
    for dimension, signal in sorted(grouped):
        group = grouped[(dimension, signal)]
        values = [record.value for record in group]
        line_items.append(
            InvoiceLineItem(
                dimension=dimension,
                signal=signal,
                # Aggregated metered quantity; for active_tenants the
                # 0/1 values make this the count of active days.
                quantity=_round_units(sum(values)),
                unit=DIMENSION_BINDINGS[dimension].unit,
                overage_units=_overage_units(
                    dimension, signal, values, plan
                ),
                source_record_count=len(group),
            )
        )

    overage_total = _round_units(
        sum(item.overage_units for item in line_items)
    )
    return InvoiceExport(
        invoice_id=invoice_id_for(tenant_id, period_start, period_end),
        tenant_id=tenant_id,
        plan_id=plan.plan_id,
        tier=plan.tier,
        period_start=period_start,
        period_end=period_end,
        line_items=tuple(line_items),
        base_monthly_units=plan.base_monthly_units,
        overage_units=overage_total,
        total_units=_round_units(
            plan.base_monthly_units + overage_total
        ),
        generated_at=(
            generated_at
            if generated_at is not None
            else utc_now_timestamp()
        ),
        exporter_version=exporter_version,
    )


def ensure_invoice_consistent(document: Mapping[str, Any]) -> None:
    """Raise unless totals are consistent with the line items.

    Enforces fail_if_totals_inconsistent_with_line_items and
    fail_if_invoice_missing_tenant_id for documents that arrive as
    plain dicts (e.g. contract samples); build_invoice output is
    consistent by construction.
    """
    if not document.get("tenant_id"):
        raise InvoiceExportError(
            "tenant_id is mandatory on every export document"
        )
    line_items = document.get("line_items")
    totals = document.get("totals")
    if not isinstance(line_items, list) or not line_items:
        raise InvoiceExportError("line_items must be a non-empty list")
    if not isinstance(totals, Mapping):
        raise InvoiceExportError("totals must be an object")
    # Malformed dicts (missing keys, non-numeric values) must surface
    # as InvoiceExportError, not KeyError/TypeError - this function's
    # whole purpose is validating untrusted plain-dict documents.
    try:
        overage = _round_units(
            sum(float(item["overage_units"]) for item in line_items)
        )
        totals_overage = _round_units(float(totals["overage_units"]))
        base_units = float(totals["base_monthly_units"])
        total_units = _round_units(float(totals["total_units"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise InvoiceExportError(
            f"malformed export document: {exc!r}"
        ) from exc
    if totals_overage != overage:
        raise InvoiceExportError(
            "totals.overage_units is inconsistent with line_items"
        )
    expected_total = _round_units(base_units + overage)
    if total_units != expected_total:
        raise InvoiceExportError(
            "totals.total_units must equal base_monthly_units plus "
            "overage_units"
        )
