#!/usr/bin/env python3

import json
from pathlib import Path
import sys


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def main() -> None:
    trigger_flow = json.loads(
        Path(
            "tests/integration/khook_event_flows/TRIGGER_TO_SUMMARY_FLOW_V1.json"
        ).read_text(encoding="utf-8")
    )
    required_event_fields = {
        "event_id",
        "event_timestamp",
        "cluster",
        "namespace",
        "object_kind",
        "object_name",
        "reason",
        "message",
    }
    event = trigger_flow.get("event", {})
    missing_event = sorted(required_event_fields - set(event.keys()))
    if missing_event:
        fail(f"Trigger flow missing required event fields: {missing_event}")

    enriched = trigger_flow.get("enriched", {})
    required_enrichment = {
        "namespace",
        "owner",
        "criticality",
        "rollout_marker",
        "incident_correlation_key",
    }
    missing_enriched = sorted(required_enrichment - set(enriched.keys()))
    if missing_enriched:
        fail(f"Trigger flow missing enrichment fields: {missing_enriched}")

    if trigger_flow.get("dispatch_mode") != "read-only":
        fail("Trigger flow dispatch_mode must be read-only.")
    derivation = trigger_flow.get("enrichment_derivation", {})
    if derivation.get("strategy") != "stable-hash":
        fail("Trigger flow enrichment_derivation strategy must be stable-hash.")
    expected_inputs = {"cluster", "namespace", "object_kind", "object_name", "reason"}
    if set(derivation.get("inputs", [])) != expected_inputs:
        fail("Trigger flow enrichment_derivation inputs mismatch.")
    if int(trigger_flow.get("enriched_payload_bytes", 0)) <= 0:
        fail("Trigger flow must include positive enriched_payload_bytes.")

    outputs = trigger_flow.get("outputs", {})
    case_file = outputs.get("case_file", {})
    if case_file.get("attached") is not True:
        fail("Case-file output attachment must be true.")
    if len(case_file.get("evidence_handles", [])) < 1:
        fail("Case-file output must include evidence handles.")

    operator = outputs.get("operator_channel", {})
    if operator.get("attached") is not True:
        fail("Operator channel output attachment must be true.")

    reliability = trigger_flow.get("reliability", {})
    if reliability.get("delivery_guarantee") != "at-least-once":
        fail("Trigger flow must assert at-least-once delivery guarantee.")
    max_seconds = reliability.get("max_end_to_summary_seconds", -1)
    if not isinstance(max_seconds, int) or max_seconds <= 0 or max_seconds > 30:
        fail("Trigger flow max_end_to_summary_seconds must be in range [1,30].")
    retry_count = reliability.get("retry_count", -1)
    if not isinstance(retry_count, int) or retry_count < 0 or retry_count > 3:
        fail("Trigger flow retry_count must be in range [0,3].")

    burst = json.loads(
        Path(
            "tests/integration/khook_event_flows/BURST_RESILIENCE_FLOW_V1.json"
        ).read_text(encoding="utf-8")
    )
    results = burst.get("results", {})
    if results.get("new_investigations_created") != 1:
        fail("Burst flow must create exactly one new investigation.")
    if results.get("aggregated_overflow_summary_emitted") is not True:
        fail("Burst flow must emit aggregated overflow summary.")
    suppressed = results.get("suppressed_duplicates", -1)
    if not isinstance(suppressed, int) or suppressed < 1:
        fail("Burst flow must suppress at least one duplicate event.")
    summary = results.get("summary", {})
    for field in ["suppressed_event_count", "first_seen_at", "last_seen_at"]:
        if field not in summary:
            fail(f"Burst flow summary missing field: {field}")
    if summary.get("suppressed_event_count") != suppressed:
        fail("Burst flow suppressed_event_count must match suppressed_duplicates.")

    print("Khook trigger flow integration fixtures passed.")


if __name__ == "__main__":
    main()
