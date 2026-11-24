"""Native Ambler CLI for Python projects adhering to the Ambler Tooling Protocol (ATP).

Thin entry point: the behaviour lives in ``specs/cli.md`` and ``ambler.walks.cli``.
"""

import asyncio
import sys

from ambler.walks import cli


def main() -> None:
    sys.exit(asyncio.run(cli.run(sys.argv[1:])))


if __name__ == "__main__":
    main()
