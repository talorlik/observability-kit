"""Offline tests for the vendor-neutral invoice exporter (Batch 22
Task 4).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 22 validator - never under pytest. Proves the
INVOICE_EXPORT_CONTRACT_V1.yaml surface: one document per tenant per
period, byte-identical apart from generated_at, overage math exactly
as the contract fixes it per dimension, and single-tenant enforcement
(TR-16 attribution).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
FIXTURE = TESTS_DIR / "fixtures" / "aggregation_window_2026_07_09.json"
PLAN_CATALOG_FIXTURE = TESTS_DIR / "fixtures" / "plan_catalog_v1.json"
SCHEMA = (
    REPO_ROOT
    / "contracts"
    / "commercial"
    / "INVOICE_EXPORT_SCHEMA_V1.json"
)
VALID_SAMPLE = (
    REPO_ROOT
    / "contracts"
    / "commercial"
    / "samples"
    / "VALID_INVOICE_EXPORT.json"
)

sys.path.insert(0, str(REPO_ROOT / "services" / "commercial"))

from commercialsvc.builder import build_usage_records  # noqa: E402
from commercialsvc.invoicing import (  # noqa: E402
    BillingPlan,
    InvoiceExportError,
    build_invoice,
    ensure_invoice_consistent,
    from_plan_catalog_dict,
    invoice_id_for,
)
from commercialsvc.models import (  # noqa: E402
    DayWindow,
    SourceReference,
    UsageRecord,
)
from commercialsvc.sources import FixtureSource  # noqa: E402

PERIOD_START = "2026-07-01T00:00:00Z"
PERIOD_END = "2026-08-01T00:00:00Z"


def _plan(tier: str = "standard") -> BillingPlan:
    catalog = json.loads(PLAN_CATALOG_FIXTURE.read_text())
    return from_plan_catalog_dict(catalog, tier)


def _all_records() -> tuple[Any, ...]:
    source = FixtureSource(FIXTURE)
    window = source.fixture_window()
    return build_usage_records(
        ingest_stats=source.ingest_stats(window),
        retentions=source.tenant_retention(window),
        query_stats=source.query_volume(window),
        window=window,
        collected_at="2026-07-10T01:05:00Z",
    )


def _acme_records() -> tuple[Any, ...]:
    return tuple(
        record
        for record in _all_records()
        if record.tenant_id == "acme-corp"
    )


def _build(generated_at: str) -> Any:
    return build_invoice(
        "acme-corp",
        _plan(),
        _acme_records(),
        PERIOD_START,
        PERIOD_END,
        generated_at=generated_at,
    )


def _synthetic_record(
    dimension: str, signal: str, value: float, unit: str, day: str
) -> UsageRecord:
    window = DayWindow.parse(day)
    return UsageRecord(
        record_id=f"acme-corp:{dimension}:{signal}:{day}",
        tenant_id="acme-corp",
        dimension=dimension,
        signal=signal,
        value=value,
        unit=unit,
        window_start=window.window_start,
        window_end=window.window_end,
        source_reference=SourceReference(
            source_type="opensearch-aggregation",
            indices=(f"tenant-acme-corp-{signal}-{window.index_suffix}",),
        ),
        collected_at="2026-07-10T01:05:00Z",
        collector_version="commercialsvc-0.1.0",
    )


def test_invoice_matches_schema_shape() -> None:
    schema = json.loads(SCHEMA.read_text())
    document = _build("2026-08-01T01:10:00Z").to_dict()
    assert set(document) == set(schema["properties"])
    assert set(schema["required"]) <= set(document)
    assert document["tier"] in schema["properties"]["tier"]["enum"]
    period_schema = schema["properties"]["billing_period"]
    assert set(document["billing_period"]) == set(
        period_schema["properties"]
    )
    item_schema = schema["properties"]["line_items"]["items"]
    assert document["line_items"]
    for item in document["line_items"]:
        assert set(item) == set(item_schema["properties"])
        assert (
            item["dimension"]
            in item_schema["properties"]["dimension"]["enum"]
        )
        assert (
            item["signal"]
            in item_schema["properties"]["signal"]["enum"]
        )
        assert item["unit"] in item_schema["properties"]["unit"]["enum"]
        assert item["quantity"] >= 0
        assert item["overage_units"] >= 0
        assert item["source_record_count"] >= 1


def test_invoice_id_is_deterministic_over_tenant_and_period() -> None:
    invoice = _build("2026-08-01T01:10:00Z")
    assert invoice.invoice_id == "acme-corp:2026-07-01:2026-08-01"
    assert invoice.invoice_id == invoice_id_for(
        "acme-corp", PERIOD_START, PERIOD_END
    )


def test_build_is_deterministic_apart_from_generated_at() -> None:
    first = _build("2026-08-01T01:10:00Z").to_dict()
    second = _build("2026-08-01T09:30:00Z").to_dict()
    assert first["generated_at"] != second["generated_at"]
    del first["generated_at"]
    del second["generated_at"]
    # Serialized comparison proves byte-identical output, not just
    # structural equality.
    assert json.dumps(first, sort_keys=True) == json.dumps(
        second, sort_keys=True
    )


def test_totals_equal_base_plus_line_item_overage() -> None:
    document = _build("2026-08-01T01:10:00Z").to_dict()
    totals = document["totals"]
    overage = sum(
        item["overage_units"] for item in document["line_items"]
    )
    assert totals["base_monthly_units"] == 400
    assert totals["overage_units"] == overage
    assert totals["total_units"] == 400 + overage
    ensure_invoice_consistent(document)


def test_ingest_overage_is_over_bound_times_rate() -> None:
    # plan-standard bound: quotas.ingest.max_gb_per_day max 100,
    # rate 2 units per gb over bound -> (112.4 - 100) * 2 = 24.8.
    record = _synthetic_record(
        "ingest_gb_per_day", "logs", 112.4, "gb", "2026-07-05"
    )
    invoice = build_invoice(
        "acme-corp",
        _plan(),
        (record,),
        PERIOD_START,
        PERIOD_END,
        generated_at="2026-08-01T01:10:00Z",
    )
    (item,) = invoice.line_items
    assert item.overage_units == 24.8
    assert item.quantity == 112.4


def test_retention_overage_uses_signal_specific_bound() -> None:
    # plan-standard bound: quotas.retention.logs_days max 30,
    # rate 1 unit per signal-day over bound -> (35 - 30) * 1 = 5.
    record = _synthetic_record(
        "retention_days", "logs", 35, "days", "2026-07-05"
    )
    invoice = build_invoice(
        "acme-corp",
        _plan(),
        (record,),
        PERIOD_START,
        PERIOD_END,
        generated_at="2026-08-01T01:10:00Z",
    )
    (item,) = invoice.line_items
    assert item.overage_units == 5


def test_query_volume_bills_every_started_block_of_1000() -> None:
    # Fixture: 5321 queries -> ceil(5321 / 1000) = 6 started blocks
    # at rate 1 (full-quantity basis; no tenant quota field exists).
    invoice = _build("2026-08-01T01:10:00Z")
    volume = [
        item
        for item in invoice.line_items
        if item.dimension == "query_volume"
    ]
    (item,) = volume
    assert item.quantity == 5321
    assert item.overage_units == 6


def test_active_tenants_rate_is_currently_zero() -> None:
    invoice = _build("2026-08-01T01:10:00Z")
    activity = [
        item
        for item in invoice.line_items
        if item.dimension == "active_tenants"
    ]
    (item,) = activity
    # Quantity is the count of active (value 1) days in the period.
    assert item.quantity == 1
    assert item.unit == "count"
    assert item.overage_units == 0


def test_foreign_tenant_record_is_rejected() -> None:
    # The fixture record set carries globex records too; an invoice is
    # single-tenant (TR-16 attribution), so the mixed set must raise.
    try:
        build_invoice(
            "acme-corp",
            _plan(),
            _all_records(),
            PERIOD_START,
            PERIOD_END,
            generated_at="2026-08-01T01:10:00Z",
        )
    except InvoiceExportError as error:
        assert "foreign tenant" in str(error)
    else:
        raise AssertionError("foreign tenant_id must be rejected")


def test_period_end_must_be_after_start() -> None:
    try:
        build_invoice(
            "acme-corp",
            _plan(),
            _acme_records(),
            PERIOD_END,
            PERIOD_START,
            generated_at="2026-08-01T01:10:00Z",
        )
    except InvoiceExportError as error:
        assert "strictly after" in str(error)
    else:
        raise AssertionError("inverted period must be rejected")


def test_valid_sample_is_internally_consistent() -> None:
    sample = json.loads(VALID_SAMPLE.read_text())
    ensure_invoice_consistent(sample)
    # Same top-level and line-item shape as the exporter emits.
    built = _build("2026-08-01T01:10:00Z").to_dict()
    assert set(sample) == set(built)
    for item in sample["line_items"]:
        assert set(item) == set(built["line_items"][0])
    assert sample["invoice_id"] == invoice_id_for(
        sample["tenant_id"],
        sample["billing_period"]["start"],
        sample["billing_period"]["end"],
    )
    totals = sample["totals"]
    overage = sum(
        item["overage_units"] for item in sample["line_items"]
    )
    assert totals["overage_units"] == overage
    assert (
        totals["total_units"]
        == totals["base_monthly_units"] + overage
    )


def test_plan_fixture_round_trips_all_four_tiers() -> None:
    catalog = json.loads(PLAN_CATALOG_FIXTURE.read_text())
    expected_base = {
        "starter": 100,
        "standard": 400,
        "premium": 1200,
        "enterprise": 4000,
    }
    expected_ingest_max = {
        "starter": 25,
        "standard": 100,
        "premium": 500,
        "enterprise": 5000,
    }
    for tier, base in expected_base.items():
        plan = from_plan_catalog_dict(catalog, tier)
        assert plan.plan_id == f"plan-{tier}"
        assert plan.tier == tier
        assert plan.base_monthly_units == base
        assert plan.ingest_gb_per_day_max == expected_ingest_max[tier]
        assert set(plan.retention_days_max) == {
            "logs",
            "metrics",
            "traces",
        }
        assert set(plan.overage_rate_units) == {
            "ingest_gb_per_day",
            "retention_days",
            "active_tenants",
            "query_volume",
        }
        # active_tenants rate is currently 0 in every plan.
        assert plan.overage_rate_units["active_tenants"] == 0


def test_unknown_tier_is_rejected() -> None:
    catalog = json.loads(PLAN_CATALOG_FIXTURE.read_text())
    try:
        from_plan_catalog_dict(catalog, "platinum")
    except InvoiceExportError as error:
        assert "platinum" in str(error)
    else:
        raise AssertionError("unknown tier must be rejected")


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
