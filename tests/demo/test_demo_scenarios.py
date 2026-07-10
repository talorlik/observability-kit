"""Offline tests for the demo traffic scenario contract (Batch 27).

Plain python3, stdlib only, bare asserts; owned by
scripts/ci/validate_demo_playground.sh. Covers:

- structural invariants of contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json
- validate_scenario() acceptance of the four shipped scenarios and the
  valid samples
- validate_scenario() rejection of every seeded-invalid sample
- fault scenarios' expectations arrays mirrored in demo/SCENARIOS.md
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json"
SAMPLES_DIR = REPO_ROOT / "contracts/demo/samples"
SCENARIOS_DIR = REPO_ROOT / "demo/gitops/base/scenarios"
SCENARIOS_DOC = REPO_ROOT / "demo/SCENARIOS.md"
LOADGEN_PATH = REPO_ROOT / "demo/services/demosvc/loadgen.py"

SHIPPED_SCENARIOS = (
    "steady-baseline",
    "burst",
    "error-injection",
    "latency-injection",
)
FAULT_SCENARIOS = ("error-injection", "latency-injection")
KIND_ENUM = [
    "steady-baseline",
    "burst",
    "error-injection",
    "latency-injection",
]


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_validate_scenario() -> Callable[[dict], list[str]]:
    """Import validate_scenario without requiring demosvc.otel.

    The parallel sample-services task owns demosvc/otel.py and the
    package __init__; loadgen.py keeps its otel import lazy (inside
    main()), so loading the module file directly always works even
    while the rest of the package is being written.
    """
    sys.path.insert(0, str(REPO_ROOT / "demo/services"))
    try:
        from demosvc.loadgen import validate_scenario
        return validate_scenario
    except Exception:
        spec = importlib.util.spec_from_file_location(
            "demosvc_loadgen_standalone", LOADGEN_PATH
        )
        assert spec is not None and spec.loader is not None, (
            f"cannot build import spec for {LOADGEN_PATH}"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate_scenario


def _assert_no_additional_properties(node: Any, where: str) -> None:
    """Every object schema node must set additionalProperties: false."""
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            assert node.get("additionalProperties") is False, (
                f"schema object at {where} must set "
                "additionalProperties: false"
            )
        for key, child in node.items():
            _assert_no_additional_properties(child, f"{where}.{key}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            _assert_no_additional_properties(child, f"{where}[{index}]")


def test_schema_structural_invariants() -> None:
    schema = _load_json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "DemoScenarioV1"
    assert schema["type"] == "object"
    assert schema["required"] == [
        "schema_version",
        "name",
        "kind",
        "description",
        "target",
        "load",
    ]

    properties = schema["properties"]
    assert properties["schema_version"]["const"] == "v1"
    assert properties["name"]["pattern"] == "^[a-z0-9][a-z0-9-]*$"
    assert properties["kind"]["enum"] == KIND_ENUM
    assert properties["description"]["minLength"] == 10

    load = properties["load"]
    assert load["properties"]["requests_per_second"]["exclusiveMinimum"] == 0
    assert load["properties"]["concurrency"]["minimum"] == 1
    assert load["properties"]["duration_seconds"]["minimum"] == 0

    fault = properties["fault"]["properties"]
    assert fault["error_ratio"]["exclusiveMinimum"] == 0
    assert fault["error_ratio"]["maximum"] == 1
    assert fault["latency_ms"]["minimum"] == 1

    expectations = properties["expectations"]
    assert expectations["required"] == ["dashboards", "ai_surfaces"]
    for key in ("dashboards", "ai_surfaces"):
        assert expectations["properties"][key]["minItems"] == 1

    # Kind-conditional structure: one if/then branch per scenario kind.
    conditional_kinds = [
        clause["if"]["properties"]["kind"]["const"]
        for clause in schema["allOf"]
    ]
    assert conditional_kinds == KIND_ENUM

    _assert_no_additional_properties(schema, "$")
    print("PASS test_schema_structural_invariants")


def test_shipped_scenarios_are_valid() -> None:
    validate_scenario = _load_validate_scenario()
    found = sorted(path.stem for path in SCENARIOS_DIR.glob("*.json"))
    assert found == sorted(SHIPPED_SCENARIOS), (
        f"shipped scenarios drifted: {found}"
    )
    for name in SHIPPED_SCENARIOS:
        doc = _load_json(SCENARIOS_DIR / f"{name}.json")
        errors = validate_scenario(doc)
        assert errors == [], f"shipped scenario {name} invalid: {errors}"
        assert doc["name"] == name, (
            f"scenario file {name}.json declares name {doc['name']!r}; "
            "DEMO_SCENARIO selects by filename so they must match"
        )
    print("PASS test_shipped_scenarios_are_valid")


def test_valid_samples_pass() -> None:
    validate_scenario = _load_validate_scenario()
    samples = sorted((SAMPLES_DIR / "valid").glob("*.json"))
    assert len(samples) >= 2, "at least two valid samples are required"
    for path in samples:
        errors = validate_scenario(_load_json(path))
        assert errors == [], f"valid sample {path.name} rejected: {errors}"
    print(f"PASS test_valid_samples_pass ({len(samples)} samples)")


def test_invalid_samples_are_rejected() -> None:
    validate_scenario = _load_validate_scenario()
    samples = sorted((SAMPLES_DIR / "invalid").glob("*.json"))
    assert len(samples) >= 3, "at least three seeded-invalid samples required"
    for path in samples:
        doc = _load_json(path)  # must stay well-formed JSON
        errors = validate_scenario(doc)
        assert errors, f"seeded-invalid sample {path.name} was accepted"
    print(f"PASS test_invalid_samples_are_rejected ({len(samples)} samples)")


def test_fault_expectations_mirrored_in_scenarios_doc() -> None:
    doc_text = SCENARIOS_DOC.read_text(encoding="utf-8")
    for name in FAULT_SCENARIOS:
        scenario = _load_json(SCENARIOS_DIR / f"{name}.json")
        expectations = scenario["expectations"]
        assert expectations["dashboards"], (
            f"{name}: expectations.dashboards must be non-empty"
        )
        assert expectations["ai_surfaces"], (
            f"{name}: expectations.ai_surfaces must be non-empty"
        )
        for surface in (
            expectations["dashboards"] + expectations["ai_surfaces"]
        ):
            assert surface in doc_text, (
                f"{name}: expectation '{surface}' missing from "
                "demo/SCENARIOS.md"
            )
    print("PASS test_fault_expectations_mirrored_in_scenarios_doc")


def test_validator_rejects_cross_kind_blocks() -> None:
    """The hand validator enforces the schema's kind conditionals."""
    validate_scenario = _load_validate_scenario()
    base = _load_json(SCENARIOS_DIR / "steady-baseline.json")

    with_fault = dict(base)
    with_fault["fault"] = {"error_ratio": 0.5}
    assert validate_scenario(with_fault), (
        "steady-baseline with a fault block must be rejected"
    )

    with_unknown = dict(base)
    with_unknown["surprise"] = True
    assert validate_scenario(with_unknown), (
        "unknown top-level fields must be rejected"
    )

    latency = _load_json(SCENARIOS_DIR / "latency-injection.json")
    mixed_fault = json.loads(json.dumps(latency))
    mixed_fault["fault"]["error_ratio"] = 0.2
    assert validate_scenario(mixed_fault), (
        "latency-injection carrying error_ratio must be rejected"
    )
    print("PASS test_validator_rejects_cross_kind_blocks")


def main() -> int:
    test_schema_structural_invariants()
    test_shipped_scenarios_are_valid()
    test_valid_samples_pass()
    test_invalid_samples_are_rejected()
    test_fault_expectations_mirrored_in_scenarios_doc()
    test_validator_rejects_cross_kind_blocks()
    print("All demo scenario tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
