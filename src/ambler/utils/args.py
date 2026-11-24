"""Command-line argument parsing that reports problems instead of exiting."""

import argparse
from typing import NoReturn


class UsageError(Exception):
    """The arguments do not match what the command accepts."""


class ArgParser(argparse.ArgumentParser):
    """An ``ArgumentParser`` that raises :class:`UsageError` rather than calling
    ``sys.exit``, so a node can report it and set the exit code itself."""

    def __init__(self) -> None:
        super().__init__(add_help=False)

    def error(self, message: str) -> NoReturn:
        raise UsageError(message)
