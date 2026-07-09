"""Render step of the guided installer (Batch 18 Task 3, TR-19).

Turns a validated install contract (InstallAnswers) into the
environment overlay and the Argo CD bootstrap manifests, exactly as
contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml fixes for the
``render`` and ``argocd-bootstrap`` steps:

- rendered/overlays/<environment>/platform-core-values.yaml
- rendered/bootstrap/argocd/kustomization.yaml
- rendered/bootstrap/argocd/platform-core-application.yaml

Invariants (ADR-0002 and the propagation contract,
contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml):

- GitOps-only: pure file emission, no cluster API access of any kind.
- Deterministic: YAML is emitted from the fixed string templates
  below with deterministic substitution - no timestamps, no
  environment-dependent values, stable ordering - so re-rendering the
  same answers produces byte-identical files.
- Every rendered file's first line carries the generated-file header
  marker (models.GENERATED_FILE_HEADER) so hand edits are detectable.
- Substituted values are validated before substitution: a value that
  could break YAML structure (newlines, control characters, quotes,
  backslashes, braces) raises InstallFlowError. All substituted
  scalars are double-quoted in the templates via _yaml_scalar.
- After writing, every file is re-read and structurally self-checked
  (first-line marker, no template remnants, content round-trips);
  failure raises InstallFlowError, which is the flow contract's
  halt_if for both steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from obskit.install.models import (
    GENERATED_FILE_HEADER,
    RENDERED_DIRNAME,
    InstallAnswers,
    InstallFlowError,
    RenderResult,
)

# Deployment modes whose attached-service endpoints belong in the
# rendered overlay (the install contract schema requires
# attached_services for exactly these modes).
_ATTACH_MODES: tuple[str, ...] = ("attach", "hybrid")

# Characters that must never reach a template substitution: newlines
# and other control characters break YAML line structure, quotes and
# backslashes escape the double-quoted scalars the templates emit,
# and braces would defeat the no-template-remnant self-check.
_FORBIDDEN_CHARS: frozenset[str] = frozenset('"\\{}')

# --- Fixed string templates ---------------------------------------
#
# Templates are module-level constants and the only source of
# rendered YAML. Every {placeholder} receives an already-validated,
# already-quoted scalar from _yaml_scalar (or a validated bare token
# where a comment or path segment needs the raw value). Key order
# inside each template is fixed, which is what makes re-renders
# byte-identical.

_OVERLAY_TEMPLATE = """\
# {header}
# Environment overlay for gitops/charts/platform-core, layered over
# gitops/overlays/base/platform-core-values.yaml by the Argo CD
# bootstrap Application. Every value is derived from the validated
# install contract; this file carries no hand-maintained state.
# baseDomain, deploymentMode, environment, and profiles.* are contract
# metadata without a platform-core chart binding yet; the Batch 19
# configuration renderer binds them to native configs (TR-20).
baseDomain: {base_domain}
deploymentMode: {deployment_mode}
environment: {environment}
profiles:
  identity: {identity_profile}
  ingress: {ingress_profile}
  objectStorage: {object_storage_profile}
  secret: {secret_profile}
  storage: {storage_profile}
"""

# Attach/hybrid additions, appended after the profile block in a
# fixed order (attachedServices, opensearch). opensearch.endpoint
# overrides the key the chart's default values file declares - the
# one attach answer with a live chart binding today. The dashboards
# and OTLP endpoints have no platform-core chart key yet, so they are
# recorded verbatim under attachedServices for the Batch 19
# configuration renderer to bind (TR-20); shaping them as fake chart
# keys would imply a binding that does not exist.
_OVERLAY_ATTACHED_SERVICES_OPEN = """\
attachedServices:
  # Attach/hybrid endpoints recorded from the install contract.
  # Consumed by the Batch 19 configuration renderer; not yet bound
  # to platform-core chart keys.
"""

_OVERLAY_ATTACHED_DASHBOARDS_LINE = """\
  dashboardsEndpoint: {dashboards_endpoint}
"""

_OVERLAY_ATTACHED_OTLP_LINE = """\
  otlpEndpoint: {otlp_endpoint}
"""

_OVERLAY_ATTACHED_OPENSEARCH_TEMPLATE = """\
opensearch:
  # Attach/hybrid: point the platform at the existing OpenSearch.
  endpoint: {opensearch_endpoint}
"""

_KUSTOMIZATION_TEMPLATE = """\
# {header}
# Argo CD bootstrap for the {environment} environment, modeled on
# gitops/bootstrap/argocd/kustomization.yaml. Committing this
# rendered output to the GitOps repository and applying it is an
# operator action: the installer performs no cluster API writes
# (GitOps-only propagation, per
# contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml).
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: argocd
resources:
  - platform-core-application.yaml
"""

_APPLICATION_TEMPLATE = """\
# {header}
# Argo CD Application bootstrapping platform-core for the
# {environment} environment.
#
# Multi-source Application: the first source supplies the
# platform-core chart from the GitOps repository's kit tree; the
# second exposes the same repository under ref "values" so
# valueFiles can reference the committed overlay through Helm's
# $values mechanism (a bare $values path inside a single-source
# Application never resolves). Assumption, stated by the bootstrap
# instruction and the guided installation guide: the GitOps
# repository carries the kit's gitops/ tree (chart and base
# overlay), and the operator commits the CONTENTS of the rendered/
# directory under the contract's gitops_path.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform-core
  namespace: argocd
spec:
  project: default
  sources:
    - repoURL: {gitops_repo_url}
      targetRevision: main
      path: gitops/charts/platform-core
      helm:
        valueFiles:
          # Base first, environment overlay second: later files
          # override earlier ones.
          - "$values/gitops/overlays/base/platform-core-values.yaml"
          - {overlay_value_file}
    - repoURL: {gitops_repo_url}
      targetRevision: main
      ref: values
  destination:
    server: https://kubernetes.default.svc
    namespace: observability
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
"""


@dataclass(frozen=True)
class _RenderedFile:
    """One fully substituted file, before it is written and checked.

    relative_path is relative to the install output directory and
    always uses forward slashes, so RenderResult stays stable across
    output locations.
    """

    relative_path: str
    content: str


def _validate_scalar(field_name: str, value: object) -> str:
    """Validate one answer value destined for a template.

    Rejects anything that could break YAML structure or leave a fake
    template remnant; returns the raw (unquoted) validated string.
    """
    if not isinstance(value, str) or not value:
        raise InstallFlowError(
            f"render: {field_name} must be a non-empty string"
        )
    for char in value:
        if ord(char) < 0x20 or char in _FORBIDDEN_CHARS:
            raise InstallFlowError(
                f"render: {field_name} contains a newline, control"
                " character, quote, backslash, or brace that could"
                " break the rendered YAML structure"
            )
    return value


def _yaml_scalar(field_name: str, value: object) -> str:
    """Validate a value and return it as a double-quoted YAML scalar."""
    return f'"{_validate_scalar(field_name, value)}"'


def _environment_segment(environment: str) -> str:
    """Validate the environment name as a safe single path segment."""
    _validate_scalar("environment", environment)
    if (
        "/" in environment
        or environment in (".", "..")
        or any(char.isspace() for char in environment)
    ):
        raise InstallFlowError(
            "render: environment must be a single path segment with"
            " no separators or whitespace"
        )
    return environment


def _write_and_verify(
    output_dir: Path, rendered: tuple[_RenderedFile, ...]
) -> RenderResult:
    """Write rendered files, then run the structural self-check.

    The self-check is the flow contract's halt_if for the render and
    argocd-bootstrap steps: every written file is re-read and must
    carry the generated-file header marker as its first line, contain
    no template remnants, and round-trip byte-for-byte.
    """
    header_line = f"# {GENERATED_FILE_HEADER}"
    for item in rendered:
        target = output_dir / item.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" pins the byte-level line ending regardless of
        # platform, which the byte-identical rendering guarantee
        # depends on.
        target.write_text(item.content, encoding="utf-8", newline="\n")
        written = target.read_text(encoding="utf-8")
        first_line = written.split("\n", 1)[0]
        if first_line != header_line:
            raise InstallFlowError(
                f"render self-check failed: {item.relative_path} does"
                " not start with the generated-file header marker"
            )
        if "{" in written or "}" in written:
            raise InstallFlowError(
                f"render self-check failed: {item.relative_path}"
                " contains an unsubstituted template placeholder"
            )
        if written != item.content or not written.endswith("\n"):
            raise InstallFlowError(
                f"render self-check failed: {item.relative_path} did"
                " not round-trip the rendered content"
            )
    return RenderResult(
        files=tuple(item.relative_path for item in rendered)
    )


def _overlay_relative_path(environment: str) -> str:
    return (
        f"{RENDERED_DIRNAME}/overlays/{environment}/"
        "platform-core-values.yaml"
    )


def render_overlay(
    answers: InstallAnswers, output_dir: Path
) -> RenderResult:
    """Render the environment overlay from a validated contract.

    Writes <output_dir>/rendered/overlays/<environment>/
    platform-core-values.yaml and returns its path relative to
    output_dir. Pure file emission: no cluster API access. Raises
    InstallFlowError on values that could break YAML structure, on
    attach/hybrid answers missing attached_services, or on a failed
    structural self-check.
    """
    environment = _environment_segment(answers.environment)
    content = _OVERLAY_TEMPLATE.format(
        header=GENERATED_FILE_HEADER,
        base_domain=_yaml_scalar("base_domain", answers.base_domain),
        deployment_mode=_yaml_scalar(
            "deployment_mode", answers.deployment_mode
        ),
        environment=_yaml_scalar("environment", answers.environment),
        identity_profile=_yaml_scalar(
            "identity_profile", answers.identity_profile
        ),
        ingress_profile=_yaml_scalar(
            "ingress_profile", answers.ingress_profile
        ),
        object_storage_profile=_yaml_scalar(
            "object_storage_profile", answers.object_storage_profile
        ),
        secret_profile=_yaml_scalar(
            "secret_profile", answers.secret_profile
        ),
        storage_profile=_yaml_scalar(
            "storage_profile", answers.storage_profile
        ),
    )
    if answers.deployment_mode in _ATTACH_MODES:
        attached = answers.attached_services
        if attached is None:
            raise InstallFlowError(
                "render: deployment_mode"
                f" {answers.deployment_mode!r} requires"
                " attached_services (invalid answers must not reach"
                " the render step)"
            )
        if (
            attached.dashboards_endpoint is not None
            or attached.otlp_endpoint is not None
        ):
            content += _OVERLAY_ATTACHED_SERVICES_OPEN
            if attached.dashboards_endpoint is not None:
                content += _OVERLAY_ATTACHED_DASHBOARDS_LINE.format(
                    dashboards_endpoint=_yaml_scalar(
                        "attached_services.dashboards_endpoint",
                        attached.dashboards_endpoint,
                    )
                )
            if attached.otlp_endpoint is not None:
                content += _OVERLAY_ATTACHED_OTLP_LINE.format(
                    otlp_endpoint=_yaml_scalar(
                        "attached_services.otlp_endpoint",
                        attached.otlp_endpoint,
                    )
                )
        if attached.opensearch_endpoint is not None:
            content += _OVERLAY_ATTACHED_OPENSEARCH_TEMPLATE.format(
                opensearch_endpoint=_yaml_scalar(
                    "attached_services.opensearch_endpoint",
                    attached.opensearch_endpoint,
                )
            )
    rendered = (
        _RenderedFile(
            relative_path=_overlay_relative_path(environment),
            content=content,
        ),
    )
    return _write_and_verify(output_dir, rendered)


def render_bootstrap(
    answers: InstallAnswers, output_dir: Path
) -> RenderResult:
    """Render the Argo CD bootstrap manifests from a validated contract.

    Writes <output_dir>/rendered/bootstrap/argocd/kustomization.yaml
    and .../platform-core-application.yaml, pointing the Application
    at answers.gitops_repo_url / answers.gitops_path and at the
    rendered overlay for answers.environment. Emission only: applying
    the manifests is the operator's act (GitOps-only propagation).
    Raises InstallFlowError on structure-breaking values or a failed
    structural self-check.
    """
    environment = _environment_segment(answers.environment)
    gitops_path = _validate_scalar("gitops_path", answers.gitops_path)
    # Normalize a trailing slash away so the composed repo-root
    # value-file path never carries a double slash.
    overlay_value_file = (
        f"$values/{gitops_path.rstrip('/')}/overlays/{environment}/"
        "platform-core-values.yaml"
    )
    kustomization = _KUSTOMIZATION_TEMPLATE.format(
        header=GENERATED_FILE_HEADER,
        environment=environment,
    )
    application = _APPLICATION_TEMPLATE.format(
        header=GENERATED_FILE_HEADER,
        environment=environment,
        gitops_repo_url=_yaml_scalar(
            "gitops_repo_url", answers.gitops_repo_url
        ),
        overlay_value_file=_yaml_scalar(
            "overlay_value_file", overlay_value_file
        ),
    )
    rendered = (
        _RenderedFile(
            relative_path=(
                f"{RENDERED_DIRNAME}/bootstrap/argocd/"
                "kustomization.yaml"
            ),
            content=kustomization,
        ),
        _RenderedFile(
            relative_path=(
                f"{RENDERED_DIRNAME}/bootstrap/argocd/"
                "platform-core-application.yaml"
            ),
            content=application,
        ),
    )
    return _write_and_verify(output_dir, rendered)
