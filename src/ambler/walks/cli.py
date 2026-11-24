"""The native Ambler Tooling Protocol (ATP) command-line tool.

See ``specs/cli.md``. The public surface is ``run()``, which returns the process
exit code; the other names are exported only for the wiring test.
"""

from dataclasses import dataclass, field
from enum import Enum, auto

from ambler import Walk
from ambler.nodes import (
    cli_route,
    run_checks,
    scaffold_node,
    scaffold_util,
    scaffold_walk,
)
from ambler.nodes.cli_error import CliError
from ambler.nodes.cli_help import CliHelp
from ambler.nodes.cli_route import CliRoute
from ambler.nodes.run_checks import RunChecks
from ambler.nodes.scaffold_node import ScaffoldNode
from ambler.nodes.scaffold_util import ScaffoldUtil
from ambler.nodes.scaffold_walk import ScaffoldWalk

__all__ = ["run"]


@dataclass
class State:
    argv: list[str]
    command: str | None = None
    exit_code: int = 0


class Id(Enum):
    CLI_ROUTE = auto()
    SCAFFOLD_NODE = auto()
    SCAFFOLD_WALK = auto()
    SCAFFOLD_UTIL = auto()
    RUN_CHECKS = auto()
    CLI_HELP = auto()
    CLI_ERROR = auto()


@dataclass(frozen=True)
class Cli(Walk[Id, State]):
    cli_route: CliRoute = field(default_factory=CliRoute)
    scaffold_node: ScaffoldNode = field(default_factory=ScaffoldNode)
    scaffold_walk: ScaffoldWalk = field(default_factory=ScaffoldWalk)
    scaffold_util: ScaffoldUtil = field(default_factory=ScaffoldUtil)
    run_checks: RunChecks = field(default_factory=RunChecks)
    cli_help: CliHelp = field(default_factory=CliHelp)
    cli_error: CliError = field(default_factory=CliError)

    async def step(self, id: Id, state: State) -> Id | None:
        match id:
            case Id.CLI_ROUTE:
                match await self.cli_route.run(state):
                    case cli_route.Outcome.NODE:
                        return Id.SCAFFOLD_NODE
                    case cli_route.Outcome.WALK:
                        return Id.SCAFFOLD_WALK
                    case cli_route.Outcome.UTIL:
                        return Id.SCAFFOLD_UTIL
                    case cli_route.Outcome.CHECK:
                        return Id.RUN_CHECKS
                    case cli_route.Outcome.HELP:
                        return Id.CLI_HELP
                    case cli_route.Outcome.UNKNOWN:
                        return Id.CLI_ERROR
            case Id.SCAFFOLD_NODE:
                match await self.scaffold_node.run(state):
                    case scaffold_node.Outcome.DONE | scaffold_node.Outcome.FAILED:
                        return None
            case Id.SCAFFOLD_WALK:
                match await self.scaffold_walk.run(state):
                    case scaffold_walk.Outcome.DONE | scaffold_walk.Outcome.FAILED:
                        return None
            case Id.SCAFFOLD_UTIL:
                match await self.scaffold_util.run(state):
                    case scaffold_util.Outcome.DONE | scaffold_util.Outcome.FAILED:
                        return None
            case Id.RUN_CHECKS:
                match await self.run_checks.run(state):
                    case run_checks.Outcome.DONE | run_checks.Outcome.FAILED:
                        return None
            case Id.CLI_HELP:
                await self.cli_help.run(state)
                return None
            case Id.CLI_ERROR:
                await self.cli_error.run(state)
                return None


async def run(argv: list[str]) -> int:
    """Runs the CLI for ``argv`` and returns the process exit code."""
    state = State(argv=list(argv))
    await Cli().run(Id.CLI_ROUTE, state)
    return state.exit_code
