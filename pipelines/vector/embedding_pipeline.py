#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TMP_ROOT = Path(tempfile.gettempdir()).resolve()
SYSTEM_TMP = Path("/tmp").resolve()
ALLOWED_BASES = (PROJECT_ROOT, TMP_ROOT, SYSTEM_TMP)


def _is_within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _safe_read_path(user_path: str) -> Path:
    resolved = Path(user_path).expanduser().resolve(strict=True)
    if not any(_is_within(resolved, base) for base in ALLOWED_BASES):
        raise ValueError(f"Input path is outside allowed directories: {resolved}")
    return resolved


def _safe_write_path(user_path: str) -> Path:
    target = Path(user_path).expanduser()
    parent = target.parent if target.parent != Path("") else Path(".")
    parent_resolved = parent.resolve(strict=True)
    if not any(_is_within(parent_resolved, base) for base in ALLOWED_BASES):
        raise ValueError(f"Output path parent is outside allowed directories: {target}")
    resolved = target.resolve()
    if not any(_is_within(resolved, base) for base in ALLOWED_BASES):
        raise ValueError(f"Output path is outside allowed directories: {resolved}")
    return resolved


def pseudo_embedding(text: str, dimensions: int) -> list[float]:
    base = sum(ord(ch) for ch in text) % 1000
    return [((base + i) % 1000) / 1000.0 for i in range(dimensions)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate pseudo embeddings.")
    parser.add_argument("--input", required=True, help="Extraction snapshot JSON path")
    parser.add_argument("--output", required=True, help="Embedded output JSON path")
    parser.add_argument("--dimensions", type=int, default=8)
    args = parser.parse_args()

    input_path = _safe_read_path(args.input)
    snapshot = json.loads(input_path.read_text(encoding="utf-8"))
    embedded = []
    for record in snapshot.get("records", []):
        embedded.append(
            {
                "id": record["id"],
                "artifact_type": record["artifact_type"],
                "owner": record["owner"],
                "text": record["content"],
                "vector": pseudo_embedding(record["content"], args.dimensions),
            }
        )

    result = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "dimensions": args.dimensions,
        "target_index_pattern": "vectors-*",
        "embedded_records": embedded,
    }
    output_path = _safe_write_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
