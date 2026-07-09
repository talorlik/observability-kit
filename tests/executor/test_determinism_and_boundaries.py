#!/usr/bin/env python3
"""Determinism and boundary guards for the obskit executor (Batch 17).

Covers the non-functional half of the executor contract
(contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml):

- TR-18 determinism: two chained runs over identical inputs produce
  byte-identical artifacts, for all six emitted files;
- lazy-import boundary: `kubernetes` is never imported at module level
  anywhere in tools/obskit/obskit/, and only reader.py's LiveReader
  path may import it lazily inside a function (static AST check);
- contract drift guard: the blocked-condition binding fails loudly in
  BOTH directions on a mutated copy of GRADING_RULES.json (a code the
  executor does not bind, and a bound code the contract dropped);
- read-only RBAC: tools/obskit/rbac/obskit-readonly-rbac.yaml grants
  exactly get/list/watch and never touches the secrets resource
  (parsed line-based, no PyYAML - the executor tests stay stdlib-only).

Owned by scripts/ci/validate_discovery_executor.sh.
"""

import ast
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "executor" / "fixtures"
CONTRACTS = ROOT / "contracts"
PACKAGE_DIR = ROOT / "tools" / "obskit" / "obskit"
RBAC_MANIFEST = ROOT / "tools" / "obskit" / "rbac" / "obskit-readonly-rbac.yaml"

sys.path.insert(0, str(ROOT / "tools" / "obskit"))

from obskit import evaluate as evaluate_module  # noqa: E402

EVALUATE_ARTIFACTS = [
    "capability_matrix.json",
    "compatibility_result.json",
    "mode_recommendation.json",
    "remediation_list.json",
]
ALLOWED_VERBS = ["get", "list", "watch"]
FORBIDDEN_VERBS = {
    "create", "update", "patch", "delete", "deletecollection",
    "escalate", "impersonate", "bind",
}


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "tools" / "obskit")
    return env


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", "-m", "obskit.cli", *args],
        cwd=ROOT,
        env=_cli_env(),
        capture_output=True,
        text=True,
    )


def _generate_inputs(workdir: Path) -> tuple[Path, Path]:
    preflight_path = workdir / "preflight_report.json"
    discovery_path = workdir / "discovery_probes.json"
    proc = _run_cli([
        "preflight",
        "--snapshot", str(FIXTURES / "snapshot_preflight_pass.json"),
        "--output", str(preflight_path),
    ])
    assert proc.returncode == 0, proc.stderr
    proc = _run_cli([
        "discover",
        "--snapshot", str(FIXTURES / "snapshot_discovery_reference.json"),
        "--output", str(discovery_path),
    ])
    assert proc.returncode == 0, proc.stderr
    return preflight_path, discovery_path


def test_chained_runs_are_byte_identical() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_a = base / "run_a"
        run_b = base / "run_b"
        run_a.mkdir()
        run_b.mkdir()

        preflight_a, discovery_a = _generate_inputs(run_a)
        preflight_b, discovery_b = _generate_inputs(run_b)
        assert preflight_a.read_bytes() == preflight_b.read_bytes(), (
            "preflight reports differ between identical runs"
        )
        assert discovery_a.read_bytes() == discovery_b.read_bytes(), (
            "discovery reports differ between identical runs"
        )

        # input_refs record the --preflight/--discovery paths exactly
        # as passed, so both evaluate runs must receive the same input
        # path strings; only --output-dir differs.
        for eval_dir in (run_a / "evaluation", run_b / "evaluation"):
            proc = _run_cli([
                "evaluate",
                "--preflight", str(preflight_a),
                "--discovery", str(discovery_a),
                "--contracts-dir", str(CONTRACTS),
                "--profiles", str(FIXTURES / "profiles_reference.json"),
                "--output-dir", str(eval_dir),
            ])
            assert proc.returncode == 0, proc.stderr

        for filename in EVALUATE_ARTIFACTS:
            bytes_a = (run_a / "evaluation" / filename).read_bytes()
            bytes_b = (run_b / "evaluation" / filename).read_bytes()
            assert bytes_a == bytes_b, (
                f"{filename} differs between identical evaluate runs"
            )


def test_no_module_level_kubernetes_import() -> None:
    checked = 0
    for source_path in sorted(PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                if module != "kubernetes" and not module.startswith(
                    "kubernetes."
                ):
                    continue
                assert source_path.name == "reader.py", (
                    f"{source_path.name} imports kubernetes; only the "
                    "lazy LiveReader path in reader.py may"
                )
                # Lazy means function-scoped: never at column 0.
                assert node.col_offset > 0, (
                    "reader.py imports kubernetes at module level; "
                    "the import must stay inside the LiveReader path"
                )
        checked += 1
    assert checked >= 7, f"expected the obskit modules, found {checked}"


def _mutated_contracts_dir(base: Path, mutate) -> Path:
    """Copy contracts/compatibility and apply `mutate` to GRADING_RULES."""
    target = base / "contracts"
    shutil.copytree(CONTRACTS / "compatibility", target / "compatibility")
    rules_path = target / "compatibility" / "GRADING_RULES.json"
    rules = json.loads(rules_path.read_text())
    mutate(rules)
    rules_path.write_text(json.dumps(rules, indent=2) + "\n")
    return target


def test_grading_rules_drift_guard_fails_both_directions() -> None:
    original = json.loads(
        (CONTRACTS / "compatibility" / "GRADING_RULES.json").read_text()
    )

    def add_unbound_code(rules: dict) -> None:
        rules["blocked_conditions"].append(
            {"code": "unbound_drift_code", "description": "seeded drift"}
        )

    def drop_bound_code(rules: dict) -> None:
        rules["blocked_conditions"] = [
            item for item in rules["blocked_conditions"]
            if item["code"] != "missing_prerequisite"
        ]

    # Library level: resolve_blocked_codes raises loudly either way.
    for mutate in (add_unbound_code, drop_bound_code):
        mutated = copy.deepcopy(original)
        mutate(mutated)
        try:
            evaluate_module.resolve_blocked_codes(mutated)
        except evaluate_module.EvaluationError:
            pass
        else:
            raise AssertionError(
                f"{mutate.__name__}: drift guard did not raise"
            )

    # CLI level: a mutated contracts dir must fail the evaluate run
    # with a non-zero exit and a loud blocked_conditions message.
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        preflight_path, discovery_path = _generate_inputs(base)
        for index, mutate in enumerate((add_unbound_code, drop_bound_code)):
            mutated_dir = _mutated_contracts_dir(base / f"m{index}", mutate)
            proc = _run_cli([
                "evaluate",
                "--preflight", str(preflight_path),
                "--discovery", str(discovery_path),
                "--contracts-dir", str(mutated_dir),
                "--output-dir", str(base / f"m{index}" / "evaluation"),
            ])
            assert proc.returncode != 0, (
                f"{mutate.__name__}: evaluate accepted drifted contract"
            )
            assert "blocked_conditions" in proc.stderr, proc.stderr


def _parse_rbac_rules(text: str) -> tuple[list[list[str]], list[str]]:
    """Line-based extraction of verbs lists and resource names."""
    verbs_lists: list[list[str]] = []
    resources: list[str] = []
    in_resources = False
    resources_indent = 0
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        if in_resources:
            if stripped.startswith("- ") and indent >= resources_indent:
                resources.append(stripped[2:].strip().strip("'\""))
                continue
            in_resources = False
        inline = re.match(r"verbs:\s*\[(?P<items>[^\]]*)\]\s*$", stripped)
        if inline:
            verbs_lists.append([
                item.strip().strip("'\"")
                for item in inline.group("items").split(",")
                if item.strip()
            ])
            continue
        assert stripped != "verbs:", (
            "block-style verbs list found; extend the parser before "
            "changing the manifest style"
        )
        if stripped == "resources:":
            in_resources = True
            resources_indent = indent
    return verbs_lists, resources


def test_rbac_manifest_is_read_only_and_secretless() -> None:
    verbs_lists, resources = _parse_rbac_rules(RBAC_MANIFEST.read_text())
    assert verbs_lists, "no verbs lists found in the RBAC manifest"
    assert resources, "no resources found in the RBAC manifest"
    for verbs in verbs_lists:
        assert verbs == ALLOWED_VERBS, (
            f"RBAC verbs {verbs} != contracted {ALLOWED_VERBS}"
        )
        assert not set(verbs) & FORBIDDEN_VERBS, verbs
    assert "secrets" not in resources, (
        "RBAC manifest must not grant any access to secrets"
    )


if __name__ == "__main__":
    test_chained_runs_are_byte_identical()
    print("test_chained_runs_are_byte_identical passed")
    test_no_module_level_kubernetes_import()
    print("test_no_module_level_kubernetes_import passed")
    test_grading_rules_drift_guard_fails_both_directions()
    print("test_grading_rules_drift_guard_fails_both_directions passed")
    test_rbac_manifest_is_read_only_and_secretless()
    print("test_rbac_manifest_is_read_only_and_secretless passed")
