"""Tests for the guided installer render step (Batch 18 Task 3).

Run with: PYTHONPATH=tools/obskit python3 tests/installer/test_render_step.py

Plain python3, bare asserts, no pytest - same style as tests/executor/.
Covers the render-step invariants of
contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml: contracted output
paths, byte-identical re-rendering, the generated-file header marker,
attach-vs-standalone endpoint mapping, gitops answers in the
Application manifest, and the YAML-injection guard.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path

from obskit.install.models import (
    GENERATED_FILE_HEADER,
    InstallAnswers,
    InstallFlowError,
)
from obskit.install.render import render_bootstrap, render_overlay

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

KUSTOMIZATION_REL = "rendered/bootstrap/argocd/kustomization.yaml"
APPLICATION_REL = "rendered/bootstrap/argocd/platform-core-application.yaml"


def _load_answers(fixture_name: str) -> InstallAnswers:
    payload = json.loads(
        (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
    )
    return InstallAnswers.from_mapping(payload)


def _overlay_rel(environment: str) -> str:
    return f"rendered/overlays/{environment}/platform-core-values.yaml"


def _render_all(answers: InstallAnswers, output_dir: Path) -> tuple[str, ...]:
    overlay = render_overlay(answers, output_dir)
    bootstrap = render_bootstrap(answers, output_dir)
    return overlay.files + bootstrap.files


def test_standalone_renders_contracted_paths() -> None:
    answers = _load_answers("render_answers_standalone.json")
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        overlay = render_overlay(answers, output_dir)
        bootstrap = render_bootstrap(answers, output_dir)
        assert overlay.files == (_overlay_rel("dev"),)
        assert bootstrap.files == (KUSTOMIZATION_REL, APPLICATION_REL)
        for rel in overlay.files + bootstrap.files:
            assert (output_dir / rel).is_file(), rel


def test_rerender_is_byte_identical() -> None:
    for fixture in (
        "render_answers_standalone.json",
        "render_answers_attach.json",
    ):
        answers = _load_answers(fixture)
        with tempfile.TemporaryDirectory() as tmp_a, \
                tempfile.TemporaryDirectory() as tmp_b:
            dir_a, dir_b = Path(tmp_a), Path(tmp_b)
            files_a = _render_all(answers, dir_a)
            files_b = _render_all(answers, dir_b)
            # Relative paths are stable across output locations.
            assert files_a == files_b
            for rel in files_a:
                bytes_a = (dir_a / rel).read_bytes()
                bytes_b = (dir_b / rel).read_bytes()
                assert bytes_a == bytes_b, f"{fixture}: {rel} differs"


def test_generated_header_is_first_line_of_every_file() -> None:
    header_line = f"# {GENERATED_FILE_HEADER}"
    for fixture in (
        "render_answers_standalone.json",
        "render_answers_attach.json",
    ):
        answers = _load_answers(fixture)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            for rel in _render_all(answers, output_dir):
                text = (output_dir / rel).read_text(encoding="utf-8")
                assert text.split("\n", 1)[0] == header_line, rel
                assert text.endswith("\n"), rel


def test_attach_overlay_carries_attached_endpoints() -> None:
    answers = _load_answers("render_answers_attach.json")
    assert answers.attached_services is not None
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        render_overlay(answers, output_dir)
        overlay = (output_dir / _overlay_rel("staging")).read_text(
            encoding="utf-8"
        )
        attached = answers.attached_services
        assert f'endpoint: "{attached.opensearch_endpoint}"' in overlay
        assert "attachedServices:" in overlay
        assert (
            "dashboardsEndpoint:"
            f' "{attached.dashboards_endpoint}"' in overlay
        )
        assert f'otlpEndpoint: "{attached.otlp_endpoint}"' in overlay
        assert 'deploymentMode: "attach"' in overlay


def test_standalone_overlay_has_no_attached_endpoints() -> None:
    answers = _load_answers("render_answers_standalone.json")
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        render_overlay(answers, output_dir)
        overlay = (output_dir / _overlay_rel("dev")).read_text(
            encoding="utf-8"
        )
        assert "opensearch:" not in overlay
        assert "attachedServices:" not in overlay
        assert "otlpEndpoint:" not in overlay
        assert 'deploymentMode: "standalone"' in overlay
        # Answer-determined values land in the overlay.
        assert 'baseDomain: "dev.example.internal"' in overlay
        assert 'storage: "gp3"' in overlay
        assert 'identity: "oidc"' in overlay


def test_application_carries_gitops_repo_and_path() -> None:
    answers = _load_answers("render_answers_standalone.json")
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        render_bootstrap(answers, output_dir)
        application = (output_dir / APPLICATION_REL).read_text(
            encoding="utf-8"
        )
        assert f'repoURL: "{answers.gitops_repo_url}"' in application
        # Multi-source Application: the chart source points at the
        # kit tree; the second source exposes the repo as $values.
        assert "path: gitops/charts/platform-core" in application
        assert "ref: values" in application
        assert "sources:" in application
        assert "\n  source:" not in application
        # Base overlay layered first, then the rendered environment
        # overlay committed under gitops_path.
        assert (
            '- "$values/gitops/overlays/base/'
            'platform-core-values.yaml"' in application
        )
        expected_value_file = (
            f"$values/{answers.gitops_path}/overlays/"
            f"{answers.environment}/platform-core-values.yaml"
        )
        assert f'- "{expected_value_file}"' in application
        kustomization = (output_dir / KUSTOMIZATION_REL).read_text(
            encoding="utf-8"
        )
        assert "- platform-core-application.yaml" in kustomization


def test_newline_in_value_raises_install_flow_error() -> None:
    answers = _load_answers("render_answers_standalone.json")
    injected_overlay = dataclasses.replace(
        answers, base_domain="dev.example.internal\nevil: true"
    )
    injected_bootstrap = dataclasses.replace(
        answers,
        gitops_repo_url="https://github.com/example/x.git\nevil: true",
    )
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        for func, bad_answers in (
            (render_overlay, injected_overlay),
            (render_bootstrap, injected_bootstrap),
        ):
            try:
                func(bad_answers, output_dir)
            except InstallFlowError:
                pass
            else:
                raise AssertionError(
                    f"{func.__name__} accepted a newline-carrying value"
                )
        # Nothing may be left behind by the rejected renders.
        assert not list(output_dir.rglob("*.yaml"))


def test_attach_mode_without_attached_services_raises() -> None:
    answers = dataclasses.replace(
        _load_answers("render_answers_attach.json"),
        attached_services=None,
    )
    with tempfile.TemporaryDirectory() as tmp:
        try:
            render_overlay(answers, Path(tmp))
        except InstallFlowError:
            pass
        else:
            raise AssertionError(
                "render_overlay accepted attach mode without"
                " attached_services"
            )


if __name__ == "__main__":
    test_standalone_renders_contracted_paths()
    print("test_standalone_renders_contracted_paths passed")
    test_rerender_is_byte_identical()
    print("test_rerender_is_byte_identical passed")
    test_generated_header_is_first_line_of_every_file()
    print("test_generated_header_is_first_line_of_every_file passed")
    test_attach_overlay_carries_attached_endpoints()
    print("test_attach_overlay_carries_attached_endpoints passed")
    test_standalone_overlay_has_no_attached_endpoints()
    print("test_standalone_overlay_has_no_attached_endpoints passed")
    test_application_carries_gitops_repo_and_path()
    print("test_application_carries_gitops_repo_and_path passed")
    test_newline_in_value_raises_install_flow_error()
    print("test_newline_in_value_raises_install_flow_error passed")
    test_attach_mode_without_attached_services_raises()
    print("test_attach_mode_without_attached_services_raises passed")
