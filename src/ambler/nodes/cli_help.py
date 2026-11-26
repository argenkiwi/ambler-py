import sys
from dataclasses import dataclass, field
from typing import Protocol

from ambler.guides import TOPICS, guide
from ambler.nodes import HasArgv, HasCommand, HasExitCode

USAGE = """Usage: uv run ambler <command> [options]

Ambler Python Tooling

Commands:
  node <name> (--outcomes <a,b> | --terminal) [--fallible] [--state <name[:type]>...]
                 Scaffold a node
  walk <name> --nodes <n1,n2> [--edge <node.OUTCOME=target>...] [--no-runner]
                 Wire a walk
  util <name>    Create a utility module
  check [--lint-only]
                 Verify conventions, lint, format, and tests
  help [topic]   Print the guide for a topic, or the general guide

Options:
  -h, --help     Show this help message"""


class State(HasArgv, HasCommand, HasExitCode, Protocol):
    pass


class Utils(Protocol):
    def print(self, message: str) -> None: ...

    def print_error(self, message: str) -> None: ...


class SystemUtils:
    def print(self, message: str) -> None:
        print(message)

    def print_error(self, message: str) -> None:
        print(message, file=sys.stderr)


@dataclass(frozen=True)
class CliHelp:
    """Prints a guide for ``help [topic]``, or the usage text otherwise."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> None:
        if state.command != "help":
            self.utils.print(USAGE)
            return
        topic = state.argv[0] if state.argv else None
        text = guide(topic)
        if text is None:
            self.utils.print_error(f"No guide for {topic}. Topics: {', '.join(TOPICS)}")
            state.exit_code = 1
            return
        self.utils.print(text)
