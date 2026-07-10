"""Wrap a live-check payload in the Batch 23 evidence envelope.

Every captured evidence artifact under artifacts/evidence/batch23/
carries the envelope keys fixed by
contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml
(artifact_kind, batch, captured_at, harness). Installer outputs stay
verbatim; their envelope is the sibling evidence_manifest.json written
with --payload-listing.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-kind", required=True)
    parser.add_argument("--output", required=True)
    payload = parser.add_mutually_exclusive_group(required=True)
    payload.add_argument(
        "--payload",
        help="JSON payload file embedded under the envelope's "
        "'payload' key",
    )
    payload.add_argument(
        "--payload-listing",
        help="directory whose *.json files are listed (not embedded) "
        "as verbatim sibling artifacts",
    )
    parser.add_argument("--status", required=True,
                        choices=("pass", "fail"))
    parser.add_argument("--check-command", required=True)
    parser.add_argument("--stack-profile", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--node-image", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    envelope: dict[str, Any] = {
        "artifact_kind": args.artifact_kind,
        "batch": 23,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "harness": {
            "stack_profile": args.stack_profile,
            "kubectl_context": args.context,
            "node_image": args.node_image,
        },
        "status": args.status,
        "check_command": args.check_command,
    }
    if args.payload:
        payload_path = Path(args.payload)
        if payload_path.is_file():
            envelope["payload"] = json.loads(
                payload_path.read_text()
            )
        else:
            envelope["payload"] = {
                "note": "check produced no payload file",
            }
    else:
        listing_dir = Path(args.payload_listing)
        envelope["artifacts"] = sorted(
            item.name
            for item in listing_dir.glob("*.json")
            if item.name != Path(args.output).name
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    )
    print(f"evidence written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
