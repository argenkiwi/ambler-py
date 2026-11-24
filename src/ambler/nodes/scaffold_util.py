from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasArgv, HasExitCode
from ambler.utils.args import ArgParser, UsageError
from ambler.utils.fs import ProjectError
from ambler.utils.fs import ScaffoldUtils as Utils
from ambler.utils.fs import SystemScaffoldUtils as SystemUtils
from ambler.utils.naming import to_pascal, to_snake
from ambler.utils.templates import render_util


class Outcome(Enum):
    """Whether the util was written."""

    DONE = auto()
    FAILED = auto()


class State(HasArgv, HasExitCode, Protocol):
    pass


@dataclass(frozen=True)
class ScaffoldUtil:
    """Writes ``src/<pkg>/utils/<name>.py``."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> Outcome:
        parser = ArgParser()
        parser.add_argument("name")
        try:
            args = parser.parse_args(state.argv)
        except UsageError as e:
            return self._fail(state, 2, f"Error: {e}")

        try:
            pkg = self.utils.package_name()
        except ProjectError as e:
            return self._fail(state, 1, f"Error: {e}")

        name = to_snake(args.name)
        utils_dir = self.utils.root() / "src" / pkg / "utils"
        util_file = utils_dir / f"{name}.py"

        if self.utils.exists(util_file):
            return self._fail(
                state, 1, f"Error: Util {name} already exists at {util_file}"
            )

        self.utils.mkdir(utils_dir)
        self.utils.write_text(util_file, render_util(name, to_pascal(name)))
        self.utils.print(f"Created {util_file}")
        return Outcome.DONE

    def _fail(self, state: State, code: int, message: str) -> Outcome:
        self.utils.print_error(message)
        state.exit_code = code
        return Outcome.FAILED
