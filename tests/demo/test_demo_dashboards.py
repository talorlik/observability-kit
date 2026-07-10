"""Offline tests for the demo playground dashboards (Batch 27, Task 4).

Plain python3, stdlib json only, bare asserts, no cluster. Verifies the
four DEMO_*.ndjson saved-object files under the platform dashboard
provisioning path:

- every line parses as JSON, no blank lines
- exactly one dashboard object, >=2 visualizations, >=1 index-pattern
  per file
- all intra-file references resolve (panelsJSON panel ids to
  visualization objects, searchSourceJSON index ids to index-pattern
  objects)
- every expectations panel named by the two fault scenarios resolves to
  a visualization id (demo- + panel slug) in the named file
- every dashboard's searchSourceJSON carries the standard filter
  dimensions (tenant_id, service.name, k8s.namespace.name) plus a
  severity or status dimension, and restores a default time range
- index-pattern objects carry timeFieldName @timestamp

Run: python3 tests/demo/test_demo_dashboards.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SAVED_OBJECTS_DIR = (
    REPO_ROOT / "gitops/platform/search/dashboards/saved-objects"
)
SCENARIOS_DIR = REPO_ROOT / "demo/gitops/base/scenarios"

DASHBOARD_FILES = (
    "DEMO_SERVICE_OVERVIEW.ndjson",
    "DEMO_LOGS_EXPLORER.ndjson",
    "DEMO_LATENCY_TRACES.ndjson",
    "DEMO_ERRORS_ALERTS.ndjson",
)
FAULT_SCENARIO_FILES = ("error-injection.json", "latency-injection.json")

# Standard filter dimensions the completion check requires on every
# dashboard: time range, tenant, service, namespace, severity/status.
REQUIRED_DIMENSIONS = ("tenant_id", "service.name", "k8s.namespace.name")
SEVERITY_OR_STATUS_MARKERS = (
    "severity",
    "span.status_code",
    "http.response.status_code",
)


def _load_ndjson(name: str) -> list[dict[str, Any]]:
    path = SAVED_OBJECTS_DIR / name
    assert path.exists(), f"{name}: missing under {SAVED_OBJECTS_DIR}"
    objects: list[dict[str, Any]] = []
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    for lineno, line in enumerate(lines, start=1):
        assert line.strip(), f"{name}:{lineno}: blank line in NDJSON"
        obj = json.loads(line)
        assert isinstance(obj, dict), f"{name}:{lineno}: not a JSON object"
        objects.append(obj)
    return objects


def _by_type(
    objects: list[dict[str, Any]], object_type: str
) -> list[dict[str, Any]]:
    return [o for o in objects if o.get("type") == object_type]


def _search_source(obj: dict[str, Any]) -> dict[str, Any]:
    raw = obj["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"]
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
    return parsed


def test_files_parse_and_have_expected_shape() -> None:
    for name in DASHBOARD_FILES:
        objects = _load_ndjson(name)
        dashboards = _by_type(objects, "dashboard")
        visualizations = _by_type(objects, "visualization")
        index_patterns = _by_type(objects, "index-pattern")
        assert len(dashboards) == 1, f"{name}: exactly one dashboard required"
        assert len(visualizations) >= 2, f"{name}: >=2 visualizations required"
        assert len(index_patterns) >= 1, f"{name}: >=1 index-pattern required"
        for obj in objects:
            assert "id" in obj and "type" in obj and "attributes" in obj, (
                f"{name}: object missing id/type/attributes"
            )


def test_object_ids_follow_demo_prefix_convention() -> None:
    for name in DASHBOARD_FILES:
        for obj in _load_ndjson(name):
            if obj["type"] == "index-pattern":
                continue
            object_id = obj["id"]
            assert object_id.startswith("demo-"), (
                f"{name}: id {object_id!r} must carry the demo- prefix"
            )
            assert object_id == object_id.lower(), (
                f"{name}: id {object_id!r} must be lowercase"
            )


def test_intra_file_references_resolve() -> None:
    for name in DASHBOARD_FILES:
        objects = _load_ndjson(name)
        vis_ids = {o["id"] for o in _by_type(objects, "visualization")}
        pattern_ids = {o["id"] for o in _by_type(objects, "index-pattern")}
        dashboard = _by_type(objects, "dashboard")[0]

        panels = json.loads(dashboard["attributes"]["panelsJSON"])
        assert panels, f"{name}: dashboard composes no panels"
        for panel in panels:
            assert panel["type"] == "visualization", (
                f"{name}: panel {panel.get('id')!r} is not a visualization"
            )
            assert panel["id"] in vis_ids, (
                f"{name}: panel {panel['id']!r} has no visualization object"
            )

        for vis in _by_type(objects, "visualization"):
            index_ref = _search_source(vis).get("index")
            assert index_ref in pattern_ids, (
                f"{name}: visualization {vis['id']!r} references index "
                f"{index_ref!r} not defined in the file"
            )


def test_scenario_expectations_resolve_to_visualizations() -> None:
    vis_ids_by_file: dict[str, set[str]] = {}
    for name in DASHBOARD_FILES:
        objects = _load_ndjson(name)
        vis_ids_by_file[name.removesuffix(".ndjson")] = {
            o["id"] for o in _by_type(objects, "visualization")
        }

    checked = 0
    for scenario_name in FAULT_SCENARIO_FILES:
        path = SCENARIOS_DIR / scenario_name
        assert path.exists(), f"missing fault scenario {path}"
        with path.open(encoding="utf-8") as handle:
            scenario = json.load(handle)
        entries = scenario["expectations"]["dashboards"]
        assert entries, f"{scenario_name}: empty dashboard expectations"
        for entry in entries:
            file_stem, panel_slug = entry.split("/", 1)
            assert file_stem in vis_ids_by_file, (
                f"{scenario_name}: expectation {entry!r} names unknown "
                f"dashboard file {file_stem!r}"
            )
            expected_vis_id = f"demo-{panel_slug}"
            assert expected_vis_id in vis_ids_by_file[file_stem], (
                f"{scenario_name}: expectation {entry!r} does not resolve: "
                f"{expected_vis_id!r} not in {file_stem}.ndjson"
            )
            checked += 1
    assert checked >= 6, "fault scenarios must name at least six panels"


def test_dashboards_carry_standard_filters() -> None:
    for name in DASHBOARD_FILES:
        objects = _load_ndjson(name)
        dashboard = _by_type(objects, "dashboard")[0]
        source = _search_source(dashboard)
        raw = json.dumps(source)

        for dimension in REQUIRED_DIMENSIONS:
            assert dimension in raw, (
                f"{name}: dashboard searchSourceJSON lacks the "
                f"{dimension!r} filter dimension"
            )
        assert any(m in raw for m in SEVERITY_OR_STATUS_MARKERS), (
            f"{name}: dashboard searchSourceJSON lacks a severity or "
            "status dimension"
        )
        assert isinstance(source.get("filter"), list) and source["filter"], (
            f"{name}: dashboard filter section must expose editable filters"
        )
        assert source.get("query", {}).get("language") == "kuery", (
            f"{name}: dashboard query must be a KQL query"
        )

        attrs = dashboard["attributes"]
        assert attrs.get("timeRestore") is True, (
            f"{name}: dashboard must restore a default time range"
        )
        assert attrs.get("timeFrom") and attrs.get("timeTo"), (
            f"{name}: dashboard must declare timeFrom/timeTo"
        )


def test_index_patterns_are_time_based() -> None:
    for name in DASHBOARD_FILES:
        for pattern in _by_type(_load_ndjson(name), "index-pattern"):
            attrs = pattern["attributes"]
            assert attrs.get("timeFieldName") == "@timestamp", (
                f"{name}: index-pattern {pattern['id']!r} must use "
                "@timestamp as its time field"
            )
            assert attrs.get("title") == pattern["id"], (
                f"{name}: index-pattern {pattern['id']!r} title mismatch"
            )


def main() -> None:
    tests = [
        (test_name, test_fn)
        for test_name, test_fn in sorted(globals().items())
        if test_name.startswith("test_") and callable(test_fn)
    ]
    for test_name, test_fn in tests:
        test_fn()
        print(f"PASS {test_name}")
    print(f"{len(tests)} demo dashboard tests passed.")


if __name__ == "__main__":
    main()
