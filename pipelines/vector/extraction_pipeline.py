#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile


CURATED_TYPES = [
    "incident_records",
    "incident_summaries",
    "runbook_documents",
]

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


def build_snapshot(snapshot_id: str, owner: str) -> dict:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = []
    for idx, artifact_type in enumerate(CURATED_TYPES, start=1):
        records.append(
            {
                "id": f"{snapshot_id}-{idx}",
                "artifact_type": artifact_type,
                "owner": owner,
                "source": "curated",
                "retention_days": 30,
                "content": f"sample {artifact_type} content",
                "generated_at": generated_at,
            }
        )

    return {
        "snapshot_id": snapshot_id,
        "version": "v1",
        "generated_at": generated_at,
        "record_count": len(records),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate curated extraction snapshot.")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--owner", default="platform-observability")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    snapshot = build_snapshot(args.snapshot_id, args.owner)
    output_path = _safe_write_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
