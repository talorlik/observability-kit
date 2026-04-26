#!/usr/bin/env python3

import json
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def main() -> None:
    contract = yaml.safe_load(
        Path(
            "adapters/providers/EVENT_SOURCE_ADAPTER_COMPATIBILITY_V1.yaml"
        ).read_text(encoding="utf-8")
    )
    hook_catalog = yaml.safe_load(
        Path("triggers/khook/hooks/HOOK_CATALOG_V1.yaml").read_text(encoding="utf-8")
    )
    fixtures = json.loads(
        Path(
            "tests/integration/adapters/providers/PROVIDER_EVENT_SOURCE_ADAPTER_FIXTURES_V1.json"
        ).read_text(encoding="utf-8")
    )

    if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
        fail("Adapter contract must explicitly keep core contracts unchanged.")
    if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
        fail("Adapter contract must enforce read-only dispatch mode.")

    known_hooks = {item.get("id") for item in hook_catalog.get("hooks", [])}
    providers = contract.get("providers", [])
    if len(providers) < 1:
        fail("Provider adapter contract must include at least one provider.")

    provider_sources = {}
    provider_max_bytes = {}
    for provider in providers:
        name = provider.get("name")
        if not name:
            fail("Provider entry missing name.")
        required_fields = set(
            provider.get("normalization", {}).get("required_fields", [])
        )
        for field in [
            "provider",
            "source",
            "event_timestamp",
            "cluster",
            "namespace",
            "object_kind",
            "object_name",
            "reason",
            "message",
        ]:
            if field not in required_fields:
                fail(f"Provider {name} missing required normalization field: {field}")
        max_bytes = int(
            provider.get("normalization", {}).get("bounded_payload", {}).get(
                "max_bytes", 0
            )
        )
        if max_bytes <= 0:
            fail(f"Provider {name} must define positive payload max_bytes.")
        provider_max_bytes[name] = max_bytes

        src_map = {}
        for source in provider.get("supported_event_sources", []):
            src_name = source.get("source")
            hook_ids = set(source.get("normalized_hook_ids", []))
            if not src_name:
                fail(f"Provider {name} has source entry missing source name.")
            if not hook_ids:
                fail(f"Provider {name} source {src_name} must map at least one hook.")
            unknown = sorted(hook_ids - known_hooks)
            if unknown:
                fail(
                    f"Provider {name} source {src_name} maps unknown hooks: {unknown}"
                )
            src_map[src_name] = hook_ids
        provider_sources[name] = src_map

    for fixture in fixtures.get("fixtures", []):
        provider = fixture.get("provider")
        source = fixture.get("source")
        hook_id = fixture.get("normalized_hook_id")
        if provider not in provider_sources:
            fail(f"Fixture references unknown provider: {provider}")
        if source not in provider_sources[provider]:
            fail(f"Fixture references unknown source for provider {provider}: {source}")
        if hook_id not in provider_sources[provider][source]:
            fail(
                f"Fixture hook mapping invalid for {provider}/{source}: {hook_id}"
            )
        if fixture.get("dispatch_mode") != "read-only":
            fail("Fixture dispatch_mode must be read-only.")
        if int(fixture.get("payload_bytes", 0)) > provider_max_bytes[provider]:
            fail("Fixture payload exceeds provider bounded payload max_bytes.")

    for negative in fixtures.get("negative_fixtures", []):
        expected = negative.get("expected_result")
        if expected != "rejected":
            fail("Negative fixtures must expect rejected result.")
        if negative.get("dispatch_mode") == "approval-gated-write":
            continue
        provider = negative.get("provider")
        if provider and int(negative.get("payload_bytes", 0)) > provider_max_bytes.get(
            provider, 0
        ):
            continue
        fail("Negative fixture does not violate a bounded adapter rule.")

    print("Provider event-source adapter integration tests passed.")


if __name__ == "__main__":
    main()
