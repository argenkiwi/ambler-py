from dataclasses import dataclass, field
from typing import Protocol

USAGE = """Usage: ambler-cli <command> [options]

Ambler Python Tooling

Commands:
  node <name> (--outcomes <a,b> | --terminal) [--fallible] [--state <name[:type]>...]
                 Scaffold a node
  walk <name> --nodes <n1,n2> [--edge <node.OUTCOME=target>...] [--no-runner]
                 Wire a walk
  util <name>    Create a utility module
  check [--lint-only]
                 Verify conventions, lint, format, and tests

Options:
  -h, --help     Show this help message"""


class Utils(Protocol):
    def print(self, message: str) -> None: ...


class SystemUtils:
    def print(self, message: str) -> None:
        print(message)


@dataclass(frozen=True)
class CliHelp:
    """Prints the usage text."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: object) -> None:
        self.utils.print(USAGE)
