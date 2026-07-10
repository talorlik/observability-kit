#!/usr/bin/env bash
#
# Batch 26 validator: product documentation (TB-26 | TR-14, TR-26).
#
# Structural and offline: validates the docs/product/ tree WITHOUT a
# cluster, kind, or Docker. Checks that every required product
# document exists, that INDEX.md maps all five audiences and links
# every document in the tree, that the API reference is byte-identical
# to what scripts/dev/generate_api_reference.py renders from the
# tenant control plane contract (hand edits are a validation failure),
# that the docs-coverage matrix in
# contracts/docs/DOCS_COVERAGE_MATRIX_V1.yaml maps every Batch 17-25
# capability to an existing product doc section, that every relative
# link and in-tree anchor across docs/product/ resolves, and that the
# GA readiness review is a fully checked, evidence-linked, signed
# checklist.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# shellcheck source=scripts/ci/setup_python_env.sh
source scripts/ci/setup_python_env.sh

echo "Validating Batch 26 product documentation..."

python3 - <<'PY'
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path.cwd()
DOC_ROOT = ROOT / "docs" / "product"
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
# check 1: required product documents present
# --------------------------------------------------------------
REQUIRED_DOCS = [
    "INDEX.md",
    "GETTING_STARTED.md",
    "INSTALLATION_GUIDE.md",
    "CONFIGURATION_GUIDE.md",
    "OPERATIONS_GUIDE.md",
    "TENANT_ADMIN_GUIDE.md",
    "END_USER_GUIDE.md",
    "API_REFERENCE.md",
    "PRICING_AND_PACKAGING.md",
    "SUPPORT_AND_ONBOARDING.md",
    "GA_READINESS_REVIEW.md",
]

for name in REQUIRED_DOCS:
    if not (DOC_ROOT / name).is_file():
        err(f"missing required product document: docs/product/{name}")
section(1, "required product documents present")


# --------------------------------------------------------------
# Shared markdown helpers
# --------------------------------------------------------------
FENCE_RE = re.compile(r"^(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(<?([^)>\s]+)>?(?:\s+\"[^\"]*\")?\)")
REF_DEF_RE = re.compile(r"^\[([^\]]+)\]:\s+(\S+)")


def content_lines(text: str) -> list[str]:
    """Markdown lines with fenced code blocks and inline code removed."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        # Strip inline code spans so links inside backticks are ignored.
        out.append(re.sub(r"`[^`]*`", "", line))
    return out


def headings(path: Path) -> list[str]:
    """Heading titles from raw lines (fence-aware).

    Raw lines, not content_lines(): stripping inline code spans would
    mangle backticked headings and their anchor slugs.
    """
    result: list[str] = []
    in_fence = False
    for line in path.read_text().splitlines():
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            result.append(match.group(2).strip())
    return result


def anchors(path: Path) -> set[str]:
    """GitHub-style anchor slugs, with -N suffixes for duplicates."""
    seen: dict[str, int] = {}
    result: set[str] = set()
    for title in headings(path):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def links(path: Path) -> list[tuple[str, str]]:
    """(kind, target) pairs for inline links and reference definitions."""
    found: list[tuple[str, str]] = []
    for line in content_lines(path.read_text()):
        for match in LINK_RE.finditer(line):
            found.append(("inline", match.group(3)))
        ref = REF_DEF_RE.match(line)
        if ref:
            found.append(("refdef", ref.group(2)))
    return found


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:"))


# --------------------------------------------------------------
# check 2: INDEX.md audience map and full tree linkage
# --------------------------------------------------------------
AUDIENCES = [
    "evaluator",
    "installer and operator",
    "tenant administrator",
    "end user",
    "commercial administrator",
]

index_path = DOC_ROOT / "INDEX.md"
if not index_path.is_file():
    err("docs/product/INDEX.md missing; audience map cannot be checked")
else:
    index_text = index_path.read_text().lower()
    for audience in AUDIENCES:
        if audience not in index_text:
            err(f"INDEX.md audience map is missing audience: {audience}")
    linked = set()
    for _, target in links(index_path):
        if is_external(target):
            continue
        name = target.split("#", 1)[0]
        if name:
            linked.add((index_path.parent / name).resolve())
    for doc in sorted(DOC_ROOT.glob("*.md")):
        if doc.name == "INDEX.md":
            continue
        if doc.resolve() not in linked:
            err(f"INDEX.md does not link docs/product/{doc.name}")
section(2, "INDEX.md audience map and full tree linkage")


# --------------------------------------------------------------
# check 3: API reference generated-file marker and freshness
# --------------------------------------------------------------
api_ref = DOC_ROOT / "API_REFERENCE.md"
if not api_ref.is_file():
    err("docs/product/API_REFERENCE.md missing")
else:
    head = "\n".join(api_ref.read_text().splitlines()[:12])
    if "GENERATED by scripts/dev/generate_api_reference.py" not in head:
        err("API_REFERENCE.md lacks the generated-file header marker")
    # sys.executable is the venv python: this heredoc runs under the
    # interpreter activated by setup_python_env.sh, and the generator
    # needs the same PyYAML the venv provides.
    result = subprocess.run(
        [sys.executable, "scripts/dev/generate_api_reference.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        err(
            "API_REFERENCE.md drifts from the tenant control plane "
            f"contract (generator --check failed): {detail}"
        )
section(3, "API reference generated-file marker and freshness")


# --------------------------------------------------------------
# check 4: docs-coverage matrix maps every Batch 17-25 capability
# --------------------------------------------------------------
MATRIX_PATH = "contracts/docs/DOCS_COVERAGE_MATRIX_V1.yaml"
REQUIRED_BATCHES = [str(n) for n in range(17, 26)]

matrix_file = ROOT / MATRIX_PATH
if not matrix_file.is_file():
    err(f"missing docs-coverage matrix: {MATRIX_PATH}")
else:
    matrix = yaml.safe_load(matrix_file.read_text())
    if not isinstance(matrix, dict):
        err(f"docs-coverage matrix is not a YAML mapping: {MATRIX_PATH}")
        matrix = {}
    batches = {str(k): v for k, v in (matrix.get("batches") or {}).items()}
    for batch_id in REQUIRED_BATCHES:
        if batch_id not in batches:
            err(f"coverage matrix has no entry for batch {batch_id}")
            continue
        capabilities = (batches[batch_id] or {}).get("capabilities") or []
        if not capabilities:
            err(f"coverage matrix batch {batch_id} lists no capabilities")
    seen_ids: set[str] = set()
    for batch_id, batch in sorted(batches.items()):
        for cap in (batch or {}).get("capabilities") or []:
            if not isinstance(cap, dict):
                err(
                    f"coverage matrix batch {batch_id} has a "
                    f"non-mapping capability entry: {cap!r}"
                )
                continue
            cap_id = cap.get("id", "<missing id>")
            if cap_id in seen_ids:
                err(f"coverage matrix duplicates capability id {cap_id}")
            seen_ids.add(cap_id)
            for field in ("id", "summary", "doc", "section"):
                if not cap.get(field):
                    err(
                        f"coverage matrix capability {cap_id} "
                        f"(batch {batch_id}) is missing field: {field}"
                    )
            doc_rel = cap.get("doc") or ""
            if not doc_rel.startswith("docs/product/"):
                err(
                    f"capability {cap_id} maps outside docs/product/: "
                    f"{doc_rel}"
                )
                continue
            doc_path = ROOT / doc_rel
            if not doc_path.is_file():
                err(f"capability {cap_id} maps to missing doc: {doc_rel}")
                continue
            wanted = cap.get("section") or ""
            if wanted not in headings(doc_path):
                err(
                    f"capability {cap_id}: section heading not found "
                    f"verbatim in {doc_rel}: {wanted!r}"
                )
section(4, "docs-coverage matrix maps every Batch 17-25 capability")


# --------------------------------------------------------------
# check 5: relative links and in-tree anchors across docs/product/
# --------------------------------------------------------------
for doc in sorted(DOC_ROOT.glob("*.md")):
    for _, target in links(doc):
        if is_external(target):
            continue
        path_part, _, fragment = target.partition("#")
        if path_part:
            resolved = (doc.parent / path_part).resolve()
            if not resolved.exists():
                err(
                    f"broken link in docs/product/{doc.name}: "
                    f"{target} (missing {path_part})"
                )
                continue
        else:
            resolved = doc.resolve()
        if not fragment:
            continue
        # Anchor fragments are validated for in-tree markdown targets
        # only; anchors into external repo files are out of scope.
        in_tree = resolved.is_file() and DOC_ROOT.resolve() in resolved.parents
        if resolved == doc.resolve():
            in_tree = True
        if in_tree and resolved.suffix == ".md":
            if fragment.lower() not in anchors(resolved):
                err(
                    f"broken anchor in docs/product/{doc.name}: "
                    f"{target} (no heading for #{fragment})"
                )
section(5, "relative links and in-tree anchors across docs/product/")


# --------------------------------------------------------------
# check 6: GA readiness review is checked, evidence-linked, signed
# --------------------------------------------------------------
GA_PATH = DOC_ROOT / "GA_READINESS_REVIEW.md"
ITEM_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+(.*)$")
REPO_PATH_RE = re.compile(
    r"(?:^|[\s`(])"
    r"((?:docs|contracts|scripts|artifacts|gitops|services|tools|tests|"
    r"adapters|agents|pipelines|triggers|\.github)/[^\s`)\]]+)"
)

if not GA_PATH.is_file():
    err("docs/product/GA_READINESS_REVIEW.md missing")
else:
    lines = GA_PATH.read_text().splitlines()
    # Collect checklist items with their wrapped continuation lines, so
    # an evidence link on a wrapped line still counts for its item.
    items: list[tuple[str, str]] = []
    current: list[str] | None = None
    current_state = ""
    for line in lines:
        match = ITEM_RE.match(line)
        if match:
            if current is not None:
                items.append((current_state, " ".join(current)))
            current_state = match.group(1)
            current = [match.group(2)]
        elif current is not None and line.startswith("  ") and line.strip():
            current.append(line.strip())
        else:
            if current is not None:
                items.append((current_state, " ".join(current)))
            current = None
    if current is not None:
        items.append((current_state, " ".join(current)))

    if not items:
        err("GA_READINESS_REVIEW.md contains no checklist items")

    # The review must walk every numbered item of the plan's
    # definition of done (section 9), not a subset.
    plan_path = (
        ROOT / "docs" / "auxiliary" / "planning"
        / "SAAS_PRODUCTIZATION_PLAN.md"
    )
    dod_count = 0
    in_dod = False
    for line in plan_path.read_text().splitlines():
        if line.startswith("## "):
            in_dod = line.startswith("## 9. Definition of Done")
            continue
        if in_dod and re.match(r"^\d+\.\s", line):
            dod_count += 1
    if dod_count == 0:
        err("could not locate definition-of-done items in the plan")
    elif len(items) < dod_count:
        err(
            f"GA review walks {len(items)} checklist items but the "
            f"plan's definition of done has {dod_count}"
        )

    for state, text in items:
        label = text[:60]
        if state.lower() != "x":
            err(f"GA readiness item left unchecked: {label!r}")
        # A markdown link to committed evidence is required; a bare
        # repo path only supplements it (regenerable artifacts).
        if not LINK_RE.search(text):
            err(f"GA readiness item has no evidence link: {label!r}")

    # A "Signed" section with reviewer and date closes the review.
    signed_lines: list[str] = []
    in_signed = False
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            in_signed = bool(
                re.search(r"\bsigned\b|\bsign-?off\b", match.group(2).lower())
            )
            continue
        if in_signed:
            signed_lines.append(line)
    signed_text = "\n".join(signed_lines)
    if not signed_text.strip():
        err("GA_READINESS_REVIEW.md has no Signed section")
    else:
        if not re.search(r"reviewer", signed_text, re.IGNORECASE):
            err("GA readiness Signed section names no reviewer")
        if not re.search(r"\d{4}-\d{2}-\d{2}", signed_text):
            err("GA readiness Signed section carries no date (YYYY-MM-DD)")
section(6, "GA readiness review is checked, evidence-linked, and signed")


if ERRORS:
    print("Batch 26 product documentation validation FAILED:")
    for message in ERRORS:
        print(f"  - {message}")
    sys.exit(1)

print("Batch 26 product documentation structural checks passed.")
PY

echo "Product documentation validation passed."
