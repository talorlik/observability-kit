"""Usage sinks: where validated usage records are written.

Every sink enforces the TR-16 plane separation before writing: usage
records are control-plane documents and the only legal destinations
match control-tenancy-*; the daily usage index is
control-tenancy-usage-v1-<YYYY.MM.DD> (METERING_CONTRACT_V1.yaml
`destination`). A write targeting any other index - in particular a
tenant data-plane index (tenant-<id>-<signal>-*) - is refused with
PlaneSeparationError.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Protocol, Sequence

from commercialsvc.models import (
    CONTROL_PLANE_INDEX_PREFIX,
    DayWindow,
    PlaneSeparationError,
    USAGE_INDEX_PREFIX,
    UsageRecord,
)


def usage_index_for(window: DayWindow) -> str:
    """Daily destination index: control-tenancy-usage-v1-YYYY.MM.DD."""
    return f"{USAGE_INDEX_PREFIX}{window.index_suffix}"


def ensure_control_plane_index(index: str) -> None:
    """Refuse any write target outside the control-plane store."""
    if not index.startswith(CONTROL_PLANE_INDEX_PREFIX):
        raise PlaneSeparationError(
            f"refusing to write usage records to {index!r}: usage "
            "records are control-plane documents and may only be "
            f"written to {CONTROL_PLANE_INDEX_PREFIX}* indices "
            "(TR-16 plane separation)"
        )


class UsageSink(Protocol):
    """Write-side destination for validated usage records."""

    def write(
        self, index: str, records: Sequence[UsageRecord]
    ) -> None: ...


class InMemorySink:
    """Test sink: retains written documents grouped by index."""

    def __init__(self) -> None:
        self.written: dict[str, list[dict[str, object]]] = {}

    def write(
        self, index: str, records: Sequence[UsageRecord]
    ) -> None:
        ensure_control_plane_index(index)
        documents = self.written.setdefault(index, [])
        documents.extend(record.to_dict() for record in records)


class FileSink:
    """Writes one JSON document array per index under a directory.

    Deterministic serialization (sorted keys, fixed separators) so a
    re-collected window produces a byte-identical file apart from
    collected_at.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(
        self, index: str, records: Sequence[UsageRecord]
    ) -> None:
        ensure_control_plane_index(index)
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{index}.json"
        payload = [record.to_dict() for record in records]
        path.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                separators=(",", ": "),
            )
            + "\n",
            encoding="utf-8",
        )


class OpenSearchBulkSink:
    """Live bulk writer over stdlib urllib (no third-party client).

    Never exercised by offline tests beyond construction and payload
    building; live evidence lands with the Batch 23 harness. The base
    URL comes from deployment configuration - nothing is hardcoded.
    """

    def __init__(self, base_url: str, timeout_seconds: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @staticmethod
    def build_bulk_payload(
        index: str, records: Sequence[UsageRecord]
    ) -> str:
        """Pure NDJSON _bulk body. _id is the deterministic record_id,
        so re-collecting a window upserts instead of duplicating."""
        ensure_control_plane_index(index)
        lines = []
        for record in records:
            lines.append(
                json.dumps(
                    {
                        "index": {
                            "_index": index,
                            "_id": record.record_id,
                        }
                    },
                    sort_keys=True,
                )
            )
            lines.append(json.dumps(record.to_dict(), sort_keys=True))
        return "\n".join(lines) + "\n"

    def write(
        self, index: str, records: Sequence[UsageRecord]
    ) -> None:
        ensure_control_plane_index(index)
        payload = self.build_bulk_payload(index, records)
        request = urllib.request.Request(
            f"{self._base_url}/_bulk",
            data=payload.encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-ndjson",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            request, timeout=self._timeout
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("errors"):
            # Fail loudly: a partially indexed window must be retried,
            # which is safe because record ids are deterministic.
            raise RuntimeError(
                f"bulk write to {index} reported item errors"
            )
