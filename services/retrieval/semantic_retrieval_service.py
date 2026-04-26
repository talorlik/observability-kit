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


def similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def query_records(index_data: dict, query_vector: list[float], top_k: int) -> list[dict]:
    scored = []
    for item in index_data.get("embedded_records", []):
        score = similarity(query_vector, item.get("vector", []))
        scored.append(
            {
                "id": item["id"],
                "artifact_type": item["artifact_type"],
                "owner": item["owner"],
                "score": round(score, 6),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple semantic retrieval baseline.")
    parser.add_argument("--index-data", required=True, help="Embedded data JSON path")
    parser.add_argument("--query-vector", required=True, help="JSON list of floats")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    index_path = _safe_read_path(args.index_data)
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    query_vector = json.loads(args.query_vector)
    results = query_records(index_data, query_vector, args.top_k)

    output = {
        "query": {"top_k": args.top_k, "vector_length": len(query_vector)},
        "result_count": len(results),
        "results": results,
    }
    out = _safe_write_path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
