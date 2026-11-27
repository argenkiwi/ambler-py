"""Runs the counter example walk."""

import asyncio
import sys

from ambler.examples.counter.walks import counter


def main() -> None:
    try:
        asyncio.run(counter.run())
    except counter.Error as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
