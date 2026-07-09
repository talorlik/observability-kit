"""Allow `python3 -m obskit` as an alias for `python3 -m obskit.cli`."""

import sys

from obskit.cli import main

if __name__ == "__main__":
    sys.exit(main())
