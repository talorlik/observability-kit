#!/usr/bin/env bash
#
# Batch 27 validator: demo workloads and observability playground
# (TR-27, ADR-0011).
#
# Structural and offline: validates the demo package WITHOUT a
# cluster, Docker, kubectl, or helm. Checks that ADR-0011 records the
# gated choices, that the package skeleton is complete and the
# deploy/teardown scripts are safe, that onboarding documents conform
# to the Batch 7 onboarding contract and the tenant descriptor to the
# tenant contract schema, that the manifests pin the product-owned
# image inside the ADR sizing budget with tenant scoping and admission
# labels intact, that the scenario contract validates and rejects the
# seeded samples through the loadgen's own validator, that the demo
# dashboards carry the standard filter dimensions, that the AI prompt
# pack is read-path by default with every tool in the MCP catalog,
# that the four offline demo test scripts pass, and that the
# playground guide and runbook exist and are registered. When kubectl
# or kustomize is available the kustomize root is also rendered as a
# bonus check; otherwise the structural fallback (every kustomization
# entry resolves to an existing file) stands alone.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# shellcheck source=scripts/ci/setup_python_env.sh
source scripts/ci/setup_python_env.sh

echo "Validating Batch 27 demo playground..."

python3 - <<'PY'
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path.cwd()
DEMO = ROOT / "demo"
BASE = DEMO / "gitops" / "base"
SCENARIOS_DIR = BASE / "scenarios"
SAVED_OBJECTS = ROOT / "gitops/platform/search/dashboards/saved-objects"
ERRORS: list[str] = []


def err(message: str) -> None:
    ERRORS.append(message)


_ERR_MARK = 0


def section(number: int, title: str) -> None:
    """Report the previous section's outcome via the error ledger."""
    global _ERR_MARK
    status = "OK" if len(ERRORS) == _ERR_MARK else "FAILED"
    print(f"check {number}: {title} ... {status}")
    _ERR_MARK = len(ERRORS)


# --------------------------------------------------------------
# check 1: ADR-0011 records the gated choices
# --------------------------------------------------------------
ADR_PATH = "docs/adr/ADR_0011_DEMO_PLAYGROUND_ARCHITECTURE.md"
# The plan gates these decisions on the ADR; each marker is the bold
# decision title in the Decision section.
ADR_MARKERS = [
    "Workload sourcing",
    "Load generation",
    "Sizing budget",
    "Tenant scoping",
]

adr_file = ROOT / ADR_PATH
if not adr_file.is_file():
    err(f"missing ADR: {ADR_PATH}")
else:
    adr_text = adr_file.read_text(encoding="utf-8")
    for marker in ADR_MARKERS:
        if marker not in adr_text:
            err(f"ADR-0011 does not record the gated choice: {marker}")
    for budget_term in ("1 CPU", "1 GiB", "100m", "128Mi"):
        if budget_term not in adr_text:
            err(f"ADR-0011 sizing budget does not state: {budget_term}")
section(1, "ADR-0011 exists and records the gated choices")

# --------------------------------------------------------------
# check 2: package skeleton complete, scripts safe
# --------------------------------------------------------------
SKELETON = [
    "demo/README.md",
    "demo/SCENARIOS.md",
    "demo/deploy.sh",
    "demo/teardown.sh",
    "demo/prompts/AI_PROMPT_PACK.md",
    "demo/services/SIGNAL_INVENTORY.md",
]

for rel in SKELETON:
    if not (ROOT / rel).is_file():
        err(f"missing demo package file: {rel}")

for rel in ("demo/deploy.sh", "demo/teardown.sh"):
    script = ROOT / rel
    if not script.is_file():
        continue
    if not os.access(script, os.X_OK):
        err(f"{rel} is not executable")
    text = script.read_text(encoding="utf-8")
    if "set -euo pipefail" not in text:
        err(f"{rel} lacks set -euo pipefail")
# ADR-0011 Decision 6: both entry points refuse to run against
# production, so the refusal is asserted on both scripts.
for rel in ("demo/deploy.sh", "demo/teardown.sh"):
    script = ROOT / rel
    if script.is_file():
        text = script.read_text(encoding="utf-8")
        if "production" not in text or "ENVIRONMENT" not in text:
            err(f"{rel} lacks the ENVIRONMENT=production refusal")
section(2, "demo package skeleton and script safety")

# --------------------------------------------------------------
# check 3: onboarding conformance (Batch 7 contract + tenant schema)
# --------------------------------------------------------------
ONBOARDING_SCHEMA = ROOT / "contracts/onboarding/ONBOARDING_SCHEMA.json"
TENANT_SCHEMA = ROOT / "contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json"
ONBOARDING_VALUES = DEMO / "onboarding" / "onboarding-values.yaml"
TENANT_DESCRIPTOR = DEMO / "onboarding" / "tenant-demo.json"

if not ONBOARDING_SCHEMA.is_file():
    err("missing contracts/onboarding/ONBOARDING_SCHEMA.json")
elif not ONBOARDING_VALUES.is_file():
    err("missing demo/onboarding/onboarding-values.yaml")
else:
    schema = json.loads(ONBOARDING_SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    required = schema["required"]
    owner_re = re.compile(props["owner"]["pattern"])
    docs = [
        d
        for d in yaml.safe_load_all(ONBOARDING_VALUES.read_text())
        if d is not None
    ]
    if len(docs) < 4:
        err(
            "onboarding-values.yaml must onboard the four demo "
            f"services; found {len(docs)} documents"
        )
    for i, doc in enumerate(docs):
        where = f"onboarding-values.yaml document {i + 1}"
        if not isinstance(doc, dict) or set(doc) != {"observability"}:
            err(f"{where}: must carry exactly the observability block")
            continue
        block = doc["observability"]
        if not isinstance(block, dict):
            err(f"{where}: observability block is not a mapping")
            continue
        for field in required:
            if field not in block:
                err(f"{where}: missing required field {field}")
        extra = set(block) - set(props)
        if extra:
            err(f"{where}: unknown fields {sorted(extra)}")
        for field in ("environment", "subscriptionMode"):
            allowed = props[field]["enum"]
            if field in block and block[field] not in allowed:
                err(
                    f"{where}: {field} {block[field]!r} not in "
                    f"{allowed}"
                )
        if "owner" in block and not owner_re.match(str(block["owner"])):
            err(f"{where}: owner {block['owner']!r} violates pattern")
        name = str(block.get("serviceName", ""))
        if len(name) < 2:
            err(f"{where}: serviceName too short: {name!r}")

if not TENANT_SCHEMA.is_file():
    err("missing contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json")
elif not TENANT_DESCRIPTOR.is_file():
    err("missing demo/onboarding/tenant-demo.json")
else:
    tenant_schema = json.loads(TENANT_SCHEMA.read_text(encoding="utf-8"))
    tenant = json.loads(TENANT_DESCRIPTOR.read_text(encoding="utf-8"))
    for field in tenant_schema["required"]:
        if field not in tenant:
            err(f"tenant-demo.json missing required field: {field}")
    tid_pattern = tenant_schema["properties"]["tenant_id"]["pattern"]
    tenant_id = str(tenant.get("tenant_id", ""))
    if not re.match(tid_pattern, tenant_id):
        err(
            f"tenant-demo.json tenant_id {tenant_id!r} violates "
            f"pattern {tid_pattern}"
        )
section(3, "onboarding documents conform to the contracts")

# --------------------------------------------------------------
# check 4: manifests (image pin, tenant scope, labels, budget)
# --------------------------------------------------------------
IMAGE = "ghcr.io/obskit/demo:0.1.0"
NAMESPACE = "tenant-demo"
ADMISSION_LABELS = ("service.name", "deployment.environment", "service.owner")
OTLP_ENDPOINT = "http://otel-gateway.observability.svc.cluster.local:4318"
CPU_BUDGET_MILLIS = 1000
MEM_BUDGET_MI = 1024
PER_CONTAINER_CPU_MILLIS = 100
PER_CONTAINER_MEM_MI = 128


def cpu_millis(value: object) -> float:
    text = str(value)
    if text.endswith("m"):
        return float(text[:-1])
    return float(text) * 1000.0


def mem_mi(value: object) -> float:
    text = str(value)
    units = {"Ki": 1 / 1024, "Mi": 1.0, "Gi": 1024.0, "Ti": 1024.0 * 1024}
    for suffix, factor in units.items():
        if text.endswith(suffix):
            return float(text[: -len(suffix)]) * factor
    return float(text) / (1024.0 * 1024)


def pod_spec(doc: dict) -> dict:
    if doc.get("kind") == "CronJob":
        return doc["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    return doc["spec"]["template"]["spec"]


kustomization_path = BASE / "kustomization.yaml"
manifests: list[dict] = []
if not kustomization_path.is_file():
    err("missing demo/gitops/base/kustomization.yaml")
else:
    kustomization = yaml.safe_load(kustomization_path.read_text())
    resource_files = list(kustomization.get("resources") or [])
    if not resource_files:
        err("kustomization.yaml lists no resources")
    # Structural fallback for the offline path: every file named by
    # the kustomization (resources and configMapGenerator inputs)
    # must exist and parse.
    for rel in resource_files:
        path = BASE / rel
        if not path.is_file():
            err(f"kustomization resource missing on disk: {rel}")
            continue
        try:
            for doc in yaml.safe_load_all(path.read_text()):
                if doc:
                    manifests.append(doc)
        except yaml.YAMLError as exc:
            err(f"unparseable manifest {rel}: {exc}")
    for generator in kustomization.get("configMapGenerator") or []:
        for rel in generator.get("files") or []:
            if not (BASE / rel).is_file():
                err(f"configMapGenerator file missing on disk: {rel}")

workloads = [m for m in manifests if m.get("kind") in ("Deployment", "CronJob")]
deployments = [m for m in workloads if m["kind"] == "Deployment"]
if len(workloads) != 5 or len(deployments) != 4:
    err(
        "expected 4 Deployments + 1 CronJob in demo/gitops/base; "
        f"found {len(deployments)} Deployments of {len(workloads)} "
        "workloads"
    )

namespaces = [m for m in manifests if m.get("kind") == "Namespace"]
if not any(m["metadata"]["name"] == NAMESPACE for m in namespaces):
    err(f"no Namespace object named {NAMESPACE}")
for doc in manifests:
    if doc.get("kind") == "Namespace":
        continue
    meta_ns = doc.get("metadata", {}).get("namespace")
    if meta_ns != NAMESPACE:
        err(
            f"{doc.get('kind')}/{doc.get('metadata', {}).get('name')} "
            f"is not scoped to {NAMESPACE}: {meta_ns!r}"
        )

total_cpu = 0.0
total_mem = 0.0
for doc in workloads:
    name = doc["metadata"].get("name", "<unnamed>")
    spec = pod_spec(doc)
    containers = spec.get("containers") or []
    if not containers:
        err(f"workload {name} has no containers")
    endpoint_seen = False
    for container in containers:
        if container.get("image") != IMAGE:
            err(
                f"workload {name} container {container.get('name')} "
                f"image is {container.get('image')!r}, expected {IMAGE}"
            )
        requests = (container.get("resources") or {}).get("requests") or {}
        if "cpu" not in requests or "memory" not in requests:
            err(f"workload {name} container lacks cpu/memory requests")
        else:
            cpu = cpu_millis(requests["cpu"])
            mem = mem_mi(requests["memory"])
            total_cpu += cpu
            total_mem += mem
            if cpu > PER_CONTAINER_CPU_MILLIS:
                err(
                    f"workload {name} requests {requests['cpu']} CPU; "
                    "ADR-0011 caps each container at 100m"
                )
            if mem > PER_CONTAINER_MEM_MI:
                err(
                    f"workload {name} requests {requests['memory']}; "
                    "ADR-0011 caps each container at 128Mi"
                )
        for env in container.get("env") or []:
            if env.get("name") == "OTEL_EXPORTER_OTLP_ENDPOINT":
                endpoint_seen = True
                if env.get("value") != OTLP_ENDPOINT:
                    err(
                        f"workload {name} OTLP endpoint is "
                        f"{env.get('value')!r}, expected {OTLP_ENDPOINT}"
                    )
    if not endpoint_seen:
        err(f"workload {name} sets no OTEL_EXPORTER_OTLP_ENDPOINT")
if total_cpu > CPU_BUDGET_MILLIS:
    err(f"total CPU requests {total_cpu}m exceed the 1 CPU budget")
if total_mem > MEM_BUDGET_MI:
    err(f"total memory requests {total_mem}Mi exceed the 1 GiB budget")

for doc in deployments:
    name = doc["metadata"].get("name", "<unnamed>")
    labels = (
        doc.get("spec", {})
        .get("template", {})
        .get("metadata", {})
        .get("labels", {})
    )
    for label in ADMISSION_LABELS:
        if label not in labels:
            err(f"Deployment {name} lacks admission label {label}")

# No demo component may address the telemetry stores directly
# (TR-02, TR-07): the collector is the only egress. Docs state the
# constraint legitimately, so *.md files, comment lines, and
# docstring lines are excluded - only live code and config count.
STORE_RE = re.compile(r"opensearch|neo4j", re.IGNORECASE)
for path in sorted(DEMO.rglob("*")):
    if not path.is_file() or path.suffix == ".md":
        continue
    if "__pycache__" in path.parts:
        continue
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    in_docstring = False
    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        quotes = stripped.count('"""') + stripped.count("'''")
        if in_docstring:
            if quotes % 2 == 1:
                in_docstring = False
            continue
        if quotes % 2 == 1:
            in_docstring = True
            continue
        if stripped.startswith("#"):
            continue
        if STORE_RE.search(line):
            err(
                "demo component references a telemetry store "
                f"directly: {path.relative_to(ROOT)}:{lineno}"
            )

# Bonus (live-tool) check: render the kustomize root when a renderer
# is on PATH. Offline runners fall back to the structural checks
# above, which is the supported CI posture.
renderer: list[str] | None = None
if shutil.which("kubectl"):
    renderer = ["kubectl", "kustomize", str(BASE)]
elif shutil.which("kustomize"):
    renderer = ["kustomize", "build", str(BASE)]
if renderer:
    result = subprocess.run(renderer, capture_output=True, text=True)
    if result.returncode != 0:
        err(
            f"kustomize render of demo/gitops/base failed: "
            f"{result.stderr.strip()[:300]}"
        )
else:
    print("  (no kubectl/kustomize on PATH; structural fallback only)")
section(4, "manifests: image pin, tenant scope, labels, sizing budget")

# --------------------------------------------------------------
# check 5: scenario contract and seeded samples
# --------------------------------------------------------------
SCHEMA_PATH = ROOT / "contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json"
SAMPLES = ROOT / "contracts/demo/samples"
SHIPPED = ("steady-baseline", "burst", "error-injection", "latency-injection")
FAULT_SCENARIOS = ("error-injection", "latency-injection")

validate_scenario = None
if not SCHEMA_PATH.is_file():
    err("missing contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json")
else:
    json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

loadgen_path = DEMO / "services" / "demosvc" / "loadgen.py"
if not loadgen_path.is_file():
    err("missing demo/services/demosvc/loadgen.py")
else:
    # Load the module file directly: loadgen keeps its otel import
    # lazy, so the file is import-safe without the demosvc package.
    # It must be registered in sys.modules before exec: dataclass
    # decorators resolve cls.__module__ there at class-creation time.
    spec = importlib.util.spec_from_file_location(
        "demo_loadgen", loadgen_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_loadgen"] = module
    spec.loader.exec_module(module)
    validate_scenario = module.validate_scenario

if validate_scenario is not None:
    valid_samples = sorted((SAMPLES / "valid").glob("*.json"))
    if len(valid_samples) < 2:
        err(f"need >=2 valid scenario samples; found {len(valid_samples)}")
    for sample in valid_samples:
        doc = json.loads(sample.read_text(encoding="utf-8"))
        problems = validate_scenario(doc)
        if problems:
            err(f"valid sample {sample.name} rejected: {problems}")

    invalid_samples = sorted((SAMPLES / "invalid").glob("*.json"))
    if len(invalid_samples) < 3:
        err(
            f"need >=3 invalid scenario samples; found "
            f"{len(invalid_samples)}"
        )
    for sample in invalid_samples:
        doc = json.loads(sample.read_text(encoding="utf-8"))
        if not validate_scenario(doc):
            err(f"seeded-invalid sample {sample.name} was accepted")

    found = sorted(p.stem for p in SCENARIOS_DIR.glob("*.json"))
    if found != sorted(SHIPPED):
        err(f"shipped scenarios drifted from {sorted(SHIPPED)}: {found}")
    for name in SHIPPED:
        path = SCENARIOS_DIR / f"{name}.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        problems = validate_scenario(doc)
        if problems:
            err(f"shipped scenario {name} invalid: {problems}")
        if doc.get("name") != name:
            err(f"scenario {name}.json declares name {doc.get('name')!r}")


def dashboard_objects(file_stem: str) -> list[dict]:
    path = SAVED_OBJECTS / f"{file_stem}.ndjson"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


for name in FAULT_SCENARIOS:
    path = SCENARIOS_DIR / f"{name}.json"
    if not path.is_file():
        continue
    doc = json.loads(path.read_text(encoding="utf-8"))
    expectations = doc.get("expectations") or {}
    if not expectations.get("dashboards") or not expectations.get(
        "ai_surfaces"
    ):
        err(f"fault scenario {name} has empty expectations")
        continue
    for entry in expectations["dashboards"]:
        file_stem, _, panel_slug = entry.partition("/")
        objects = dashboard_objects(file_stem)
        if not objects:
            err(f"{name}: expectation {entry!r} names unknown dashboard")
            continue
        vis_ids = {
            o["id"] for o in objects if o.get("type") == "visualization"
        }
        expected_id = f"demo-{panel_slug}"
        if expected_id not in vis_ids:
            err(
                f"{name}: expectation {entry!r} does not resolve to a "
                f"visualization id in {file_stem}.ndjson"
            )
            continue
        dashboards = [o for o in objects if o.get("type") == "dashboard"]
        panels = json.loads(
            dashboards[0]["attributes"]["panelsJSON"]
        ) if dashboards else []
        if expected_id not in {p.get("id") for p in panels}:
            err(
                f"{name}: panel {expected_id} is not composed on the "
                f"{file_stem} dashboard"
            )
section(5, "scenario contract, seeded samples, and fault expectations")

# --------------------------------------------------------------
# check 6: demo dashboards under the provisioning path
# --------------------------------------------------------------
DASHBOARD_FILES = (
    "DEMO_SERVICE_OVERVIEW",
    "DEMO_LOGS_EXPLORER",
    "DEMO_LATENCY_TRACES",
    "DEMO_ERRORS_ALERTS",
)
REQUIRED_DIMENSIONS = ("tenant_id", "service.name", "k8s.namespace.name")
SEVERITY_OR_STATUS = ("severity", "span.status_code", "http.response.status_code")

for file_stem in DASHBOARD_FILES:
    objects = dashboard_objects(file_stem)
    if not objects:
        err(f"missing or empty dashboard file: {file_stem}.ndjson")
        continue
    dashboards = [o for o in objects if o.get("type") == "dashboard"]
    if len(dashboards) != 1:
        err(f"{file_stem}.ndjson must carry exactly one dashboard object")
        continue
    raw_source = dashboards[0]["attributes"]["kibanaSavedObjectMeta"][
        "searchSourceJSON"
    ]
    for dimension in REQUIRED_DIMENSIONS:
        if dimension not in raw_source:
            err(f"{file_stem}: missing standard filter dimension {dimension}")
    if not any(marker in raw_source for marker in SEVERITY_OR_STATUS):
        err(f"{file_stem}: missing a severity or status dimension")
section(6, "demo dashboards ship with the standard filter dimensions")

# --------------------------------------------------------------
# check 7: AI prompt pack (read-path default, catalog-bound)
# --------------------------------------------------------------
PROMPT_PACK = DEMO / "prompts" / "AI_PROMPT_PACK.md"
MCP_CATALOG = ROOT / "contracts/mcp/MCP_CATALOG_V1.yaml"
TOOLS_RE = re.compile(r"^- Tools: `[a-z0-9.-]+`(?:, `[a-z0-9.-]+`)*$")
TOOL_NAME_RE = re.compile(r"`([a-z0-9.-]+)`")
SCENARIO_RE = re.compile(r"^- Scenario: `([a-z0-9-]+)`$")
PATH_RE = re.compile(r"^- Path: (read|write \(approval flow\))$")

if not PROMPT_PACK.is_file() or not MCP_CATALOG.is_file():
    err("missing AI_PROMPT_PACK.md or MCP_CATALOG_V1.yaml")
else:
    catalog = yaml.safe_load(MCP_CATALOG.read_text(encoding="utf-8"))
    catalog_tools = {
        tool["name"]
        for service in catalog.get("services") or []
        for tool in service.get("tools") or []
    }
    prompts = []
    current = None
    in_fence = False
    for line in PROMPT_PACK.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if current is not None:
                current["body"] += line.lower() + "\n"
            continue
        if line.startswith("### "):
            current = {
                "title": line[4:].strip(),
                "tools": [],
                "scenario": "",
                "path": "",
                "body": "",
            }
            prompts.append(current)
            continue
        if line.startswith("## "):
            current = None
            continue
        if current is None:
            continue
        if line.startswith("- Tools: "):
            if not TOOLS_RE.match(line):
                err(f"malformed Tools line under {current['title']!r}")
            current["tools"] = TOOL_NAME_RE.findall(line)
        elif line.startswith("- Scenario: "):
            match = SCENARIO_RE.match(line)
            if not match:
                err(f"malformed Scenario line under {current['title']!r}")
            else:
                current["scenario"] = match.group(1)
        elif line.startswith("- Path: "):
            match = PATH_RE.match(line)
            if not match:
                err(f"malformed Path line under {current['title']!r}")
            else:
                current["path"] = match.group(1)
    if len(prompts) < 10:
        err(f"prompt pack has {len(prompts)} prompts; expected >=10")
    for prompt in prompts:
        if not (prompt["tools"] and prompt["scenario"] and prompt["path"]):
            err(f"prompt {prompt['title']!r} lacks Tools/Scenario/Path")
            continue
        for tool in prompt["tools"]:
            if tool not in catalog_tools:
                err(
                    f"prompt {prompt['title']!r} names tool {tool!r} "
                    "absent from MCP_CATALOG_V1.yaml"
                )
        if prompt["scenario"] not in SHIPPED:
            err(
                f"prompt {prompt['title']!r} names unshipped scenario "
                f"{prompt['scenario']!r}"
            )
    writes = [p for p in prompts if p["path"].startswith("write")]
    if len(writes) != 1:
        err(f"expected exactly one write-path prompt; found {len(writes)}")
    elif "approval flow" not in writes[0]["body"]:
        err("the write-path prompt does not mention the approval flow")
section(7, "AI prompt pack is read-path by default and catalog-bound")

# --------------------------------------------------------------
# check 8: offline demo test scripts pass
# --------------------------------------------------------------
DEMO_TESTS = [
    "tests/demo/test_demo_services.py",
    "tests/demo/test_demo_scenarios.py",
    "tests/demo/test_demo_dashboards.py",
    "tests/demo/test_demo_prompts.py",
]

for rel in DEMO_TESTS:
    test_path = ROOT / rel
    if not test_path.is_file():
        err(f"missing demo test: {rel}")
        continue
    result = subprocess.run(
        [sys.executable, str(test_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-5:]
        err(f"{rel} failed: " + " | ".join(tail))
section(8, "offline demo test scripts pass")

# --------------------------------------------------------------
# check 9: playground guide and runbook exist and are registered
# --------------------------------------------------------------
GUIDE = ROOT / "docs/product/PLAYGROUND_GUIDE.md"
GUIDE_SECTIONS = [
    "Prerequisites",
    "Install the Platform",
    "Build and Load the Demo Image",
    "Deploy the Demo",
    "Run Traffic Scenarios",
    "Explore the Dashboards",
    "Ask the AI",
    "Tear Down",
]
INDEX = ROOT / "docs/product/INDEX.md"
RUNBOOK = ROOT / "docs/runbooks/DEMO_PLAYGROUND_RUNBOOK.md"
RUNBOOK_VALIDATOR = ROOT / "scripts/ci/validate_runbook_links.sh"

if not GUIDE.is_file():
    err("missing docs/product/PLAYGROUND_GUIDE.md")
else:
    guide_headings = [
        line.lstrip("#").strip()
        for line in GUIDE.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    ]
    for wanted in GUIDE_SECTIONS:
        if wanted not in guide_headings:
            err(f"PLAYGROUND_GUIDE.md lacks the section: {wanted}")

if not INDEX.is_file():
    err("missing docs/product/INDEX.md")
else:
    index_text = INDEX.read_text(encoding="utf-8")
    for anchor in ("## Audience Map", "## Document Tree"):
        _, _, region = index_text.partition(anchor)
        region = region.split("\n## ", 1)[0]
        if "PLAYGROUND_GUIDE.md" not in region:
            err(f"INDEX.md {anchor[3:]} does not register the guide")

if not RUNBOOK.is_file():
    err("missing docs/runbooks/DEMO_PLAYGROUND_RUNBOOK.md")
if (
    RUNBOOK_VALIDATOR.is_file()
    and "docs/runbooks/DEMO_PLAYGROUND_RUNBOOK.md"
    not in RUNBOOK_VALIDATOR.read_text(encoding="utf-8")
):
    err("validate_runbook_links.sh does not register the demo runbook")
section(9, "playground guide and runbook exist and are registered")


if ERRORS:
    print("Batch 27 demo playground validation FAILED:")
    for message in ERRORS:
        print(f"  - {message}")
    sys.exit(1)

print("Batch 27 demo playground structural checks passed.")
PY

echo "Batch 27 demo playground checks passed."
