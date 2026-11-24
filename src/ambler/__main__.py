"""The program this branch builds: runs its primary walk.

Run with ``uv run counter`` (or ``uv run python -m ambler``). Additional walks get
their own entry under ``[project.scripts]`` in ``pyproject.toml``.
"""

import asyncio
import sys

from ambler.walks import counter


def main() -> None:
    try:
        asyncio.run(counter.run())
    except counter.Error as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
