from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasArgv, HasCommand, HasExitCode


class Outcome(Enum):
    """Which handler the command selects."""

    NODE = auto()
    WALK = auto()
    UTIL = auto()
    CHECK = auto()
    HELP = auto()
    UNKNOWN = auto()


class State(HasArgv, HasCommand, HasExitCode, Protocol):
    pass


@dataclass(frozen=True)
class CliRoute:
    """Consumes the command from ``argv`` and picks the handler for it."""

    async def run(self, state: State) -> Outcome:
        command = state.argv.pop(0) if state.argv else None
        state.command = command

        match command:
            case "node":
                return Outcome.NODE
            case "walk":
                return Outcome.WALK
            case "util":
                return Outcome.UTIL
            case "check":
                return Outcome.CHECK
            case "help" | "--help" | "-h":
                state.exit_code = 0
                return Outcome.HELP
            case None:
                state.exit_code = 2
                return Outcome.HELP
            case _:
                return Outcome.UNKNOWN
