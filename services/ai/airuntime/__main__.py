"""Entrypoint dispatcher: ``python3 -m airuntime <component>``."""

from __future__ import annotations

import os
import sys


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in (
        "kagent", "khook", "gateway", "mcpserver"
    ):
        print(
            "usage: python3 -m airuntime "
            "{kagent|khook|gateway|mcpserver}",
            file=sys.stderr,
        )
        return 2
    component = argv[0]
    env = dict(os.environ)
    if component == "kagent":
        from airuntime.kagent import run
    elif component == "khook":
        from airuntime.khook import run
    elif component == "gateway":
        from airuntime.gateway import run
    else:
        from airuntime.mcpserver import run
    return run(env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
