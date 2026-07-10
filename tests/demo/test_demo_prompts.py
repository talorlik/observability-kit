"""Offline tests for the demo AI playground prompt pack (Batch 27).

Plain python3, stdlib only, bare asserts; owned by
scripts/ci/validate_demo_playground.sh. Covers:

- the machine-checkable per-prompt format (Tools/Scenario/Path lines)
- every named tool existing verbatim in contracts/mcp/MCP_CATALOG_V1.yaml
- every scenario matching a shipped demo/gitops/base/scenarios/ document
- read-path by default: exactly one write prompt, casefile-update only,
  in the Casefile Follow-Up section, mentioning the approval flow
- the required tool and AI-surface coverage over the fault scenarios
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PACK = REPO_ROOT / "demo/prompts/AI_PROMPT_PACK.md"
MCP_CATALOG = REPO_ROOT / "contracts/mcp/MCP_CATALOG_V1.yaml"
SCENARIOS_DIR = REPO_ROOT / "demo/gitops/base/scenarios"

WRITE_SECTION = "Casefile Follow-Up"
CASEFILE_TOOL = "incident-casefile"
FAULT_SCENARIOS = ("error-injection", "latency-injection")

# Exact machine-checkable line formats (see the Prompt Format section
# of the pack). A tools line is one line: backticked names, comma-sep.
TOOLS_RE = re.compile(r"^- Tools: `[a-z0-9.-]+`(?:, `[a-z0-9.-]+`)*$")
TOOL_NAME_RE = re.compile(r"`([a-z0-9.-]+)`")
SCENARIO_RE = re.compile(r"^- Scenario: `([a-z0-9-]+)`$")
PATH_RE = re.compile(r"^- Path: (read|write \(approval flow\))$")
CATALOG_NAME_RE = re.compile(r"^\s*-\s*name:\s*([A-Za-z0-9._-]+)\s*$")


@dataclass
class Prompt:
    """One parsed prompt entry from the pack."""

    title: str
    section: str
    tools: list[str] = field(default_factory=list)
    scenario: str = ""
    path: str = ""
    body: str = ""

    def searchable_text(self) -> str:
        return (self.title + "\n" + self.body).lower()


def _parse_catalog_tools() -> set[str]:
    names: set[str] = set()
    for line in MCP_CATALOG.read_text(encoding="utf-8").splitlines():
        match = CATALOG_NAME_RE.match(line)
        if match:
            names.add(match.group(1))
    assert names, "no tool names parsed from MCP_CATALOG_V1.yaml"
    return names


def _parse_prompts() -> list[Prompt]:
    lines = PROMPT_PACK.read_text(encoding="utf-8").splitlines()
    prompts: list[Prompt] = []
    section = ""
    current: Prompt | None = None
    in_fence = False

    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if current is not None:
                current.body += line + "\n"
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            current = None
            continue
        if line.startswith("### "):
            current = Prompt(title=line[4:].strip(), section=section)
            prompts.append(current)
            continue
        if current is None:
            continue
        if line.startswith("- Tools: "):
            assert TOOLS_RE.match(line), (
                f"malformed Tools line under {current.title!r}: {line!r}"
            )
            assert not current.tools, (
                f"duplicate Tools line under {current.title!r}"
            )
            current.tools = TOOL_NAME_RE.findall(line)
        elif line.startswith("- Scenario: "):
            match = SCENARIO_RE.match(line)
            assert match, (
                f"malformed Scenario line under {current.title!r}: "
                f"{line!r}"
            )
            assert not current.scenario, (
                f"duplicate Scenario line under {current.title!r}"
            )
            current.scenario = match.group(1)
        elif line.startswith("- Path: "):
            match = PATH_RE.match(line)
            assert match, (
                f"malformed Path line under {current.title!r}: {line!r}"
            )
            assert not current.path, (
                f"duplicate Path line under {current.title!r}"
            )
            current.path = match.group(1)
    return prompts


def test_pack_has_ten_well_formed_prompts() -> None:
    prompts = _parse_prompts()
    assert len(prompts) >= 10, (
        f"expected >=10 prompts, found {len(prompts)}"
    )
    for prompt in prompts:
        assert prompt.tools, f"{prompt.title!r} names no tools"
        assert prompt.scenario, f"{prompt.title!r} names no scenario"
        assert prompt.path, f"{prompt.title!r} has no Path line"
        assert prompt.body.strip(), (
            f"{prompt.title!r} has no fenced prompt text"
        )
    print("PASS test_pack_has_ten_well_formed_prompts")


def test_all_tools_exist_in_mcp_catalog() -> None:
    catalog = _parse_catalog_tools()
    for prompt in _parse_prompts():
        for tool in prompt.tools:
            assert tool in catalog, (
                f"{prompt.title!r} names tool {tool!r} not present in "
                "contracts/mcp/MCP_CATALOG_V1.yaml"
            )
    print("PASS test_all_tools_exist_in_mcp_catalog")


def test_all_scenarios_are_shipped_documents() -> None:
    shipped = {p.stem for p in SCENARIOS_DIR.glob("*.json")}
    assert shipped, "no scenario documents found"
    for prompt in _parse_prompts():
        assert prompt.scenario in shipped, (
            f"{prompt.title!r} names scenario {prompt.scenario!r} with "
            "no matching document in demo/gitops/base/scenarios/"
        )
    print("PASS test_all_scenarios_are_shipped_documents")


def test_read_path_default_single_gated_write() -> None:
    prompts = _parse_prompts()
    writes = [p for p in prompts if p.path.startswith("write")]
    assert len(writes) == 1, (
        f"expected exactly one write-path prompt, found {len(writes)}"
    )
    write = writes[0]
    assert write.section == WRITE_SECTION, (
        f"write-path prompt must live in the {WRITE_SECTION!r} section,"
        f" found in {write.section!r}"
    )
    assert write.tools == [CASEFILE_TOOL], (
        "the write path may use only the casefile update tool "
        f"({CASEFILE_TOOL!r}), found {write.tools!r}"
    )
    text = write.searchable_text()
    assert "approval flow" in text, (
        "write-path prompt must state it routes through the approval "
        "flow"
    )
    assert "approval_flow_v1" in text, (
        "write-path prompt must reference "
        "contracts/policy/APPROVAL_FLOW_V1.yaml"
    )
    assert "incident-casefile.update.v1" in text, (
        "write-path prompt must name the casefile update operation"
    )
    print("PASS test_read_path_default_single_gated_write")


def test_required_tool_coverage() -> None:
    prompts = _parse_prompts()
    used = {tool for prompt in prompts for tool in prompt.tools}
    for required in (
        "incident-search",
        "metrics-correlation",
        "trace-investigation",
        CASEFILE_TOOL,
    ):
        assert required in used, f"pack never exercises {required!r}"
    assert used & {"graph-analysis", "change-intelligence"}, (
        "pack must exercise graph-analysis or change-intelligence"
    )
    casefile_reads = [
        p
        for p in prompts
        if p.path == "read" and CASEFILE_TOOL in p.tools
    ]
    assert casefile_reads, (
        "pack must include a read-path prompt for the casefile tool"
    )
    print("PASS test_required_tool_coverage")


def test_fault_scenario_ai_surfaces_are_represented() -> None:
    prompts = _parse_prompts()

    def has(scenario: str, tool: str) -> bool:
        return any(
            p.scenario == scenario and tool in p.tools for p in prompts
        )

    # expectations.ai_surfaces of error-injection.json
    assert has("error-injection", "incident-search"), (
        "mcp:incident-search surface not exercised on error-injection"
    )
    # expectations.ai_surfaces of latency-injection.json
    assert has("latency-injection", "trace-investigation"), (
        "mcp:trace-investigation surface not exercised on "
        "latency-injection"
    )
    assert has("latency-injection", "metrics-correlation"), (
        "mcp:metrics-correlation surface not exercised on "
        "latency-injection"
    )
    # risk-scoring and assisted-rca as prompt topics per fault scenario
    for scenario in FAULT_SCENARIOS:
        fault_prompts = [p for p in prompts if p.scenario == scenario]
        assert fault_prompts, f"no prompts for scenario {scenario!r}"
        texts = [p.searchable_text() for p in fault_prompts]
        assert any(
            "risk-scoring" in t or "risk scoring" in t for t in texts
        ), f"risk-scoring topic missing for scenario {scenario!r}"
        assert any(
            "assisted-rca" in t or "assisted rca" in t for t in texts
        ), f"assisted-rca topic missing for scenario {scenario!r}"
    print("PASS test_fault_scenario_ai_surfaces_are_represented")


def test_expected_sections_present() -> None:
    sections = {p.section for p in _parse_prompts()}
    for required in (
        "Service Health",
        "Log Investigation",
        "Trace Investigation",
        "Fault RCA (error-injection)",
        "Fault RCA (latency-injection)",
        WRITE_SECTION,
    ):
        assert required in sections, (
            f"prompt pack is missing prompts in section {required!r}"
        )
    print("PASS test_expected_sections_present")


def main() -> int:
    test_pack_has_ten_well_formed_prompts()
    test_all_tools_exist_in_mcp_catalog()
    test_all_scenarios_are_shipped_documents()
    test_read_path_default_single_gated_write()
    test_required_tool_coverage()
    test_fault_scenario_ai_surfaces_are_represented()
    test_expected_sections_present()
    print("All demo prompt pack tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
