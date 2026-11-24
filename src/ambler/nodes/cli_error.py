import sys
from dataclasses import dataclass, field
from typing import Protocol

from ambler.nodes import HasCommand, HasExitCode


class Utils(Protocol):
    def print_error(self, message: str) -> None: ...


class SystemUtils:
    def print_error(self, message: str) -> None:
        print(message, file=sys.stderr)


class State(HasCommand, HasExitCode, Protocol):
    pass


@dataclass(frozen=True)
class CliError:
    """Reports an unknown command and sets the usage exit code."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> None:
        self.utils.print_error(f"Unknown command: {state.command}")
        state.exit_code = 2
