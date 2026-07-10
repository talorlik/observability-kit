"""Entrypoint dispatcher for the demo image (Batch 27, ADR-0011).

One image, five entrypoints selected by the first container arg:
``http-api``, ``worker``, ``scheduled-job``, ``datastore``,
``loadgen``. Imports are deferred into the dispatch arms so each
entrypoint only pays for (and only requires) its own module.
"""

from __future__ import annotations

import sys

_COMMANDS = ("http-api", "worker", "scheduled-job", "datastore", "loadgen")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in _COMMANDS:
        print(
            f"usage: python3 -m demosvc {{{'|'.join(_COMMANDS)}}}",
            file=sys.stderr,
        )
        return 2
    command = argv[1]
    if command == "http-api":
        from demosvc.http_api import main as entry
    elif command == "worker":
        from demosvc.worker import main as entry
    elif command == "scheduled-job":
        from demosvc.scheduled_job import main as entry
    elif command == "datastore":
        from demosvc.datastore import main as entry
    else:
        from demosvc.loadgen import main as entry
    entry()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
