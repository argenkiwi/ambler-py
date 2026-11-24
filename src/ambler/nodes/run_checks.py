import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasArgv, HasExitCode
from ambler.utils.args import ArgParser, UsageError

PYTEST_NO_TESTS_COLLECTED = 5


class Outcome(Enum):
    """Whether every check passed."""

    DONE = auto()
    FAILED = auto()


class State(HasArgv, HasExitCode, Protocol):
    pass


class Utils(Protocol):
    def run(self, cmd: list[str]) -> int:
        """Runs ``cmd`` with inherited stdio and returns its exit code."""
        ...

    def print(self, message: str) -> None: ...

    def print_error(self, message: str) -> None: ...


class SystemUtils:
    def run(self, cmd: list[str]) -> int:
        return subprocess.run(cmd).returncode

    def print(self, message: str) -> None:
        print(message)

    def print_error(self, message: str) -> None:
        print(message, file=sys.stderr)


@dataclass(frozen=True)
class RunChecks:
    """Runs format, lint, type and test checks, stopping at the first failure."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> Outcome:
        parser = ArgParser()
        parser.add_argument("--lint-only", action="store_true")
        try:
            args = parser.parse_args(state.argv)
        except UsageError as e:
            self.utils.print_error(f"Error: {e}")
            state.exit_code = 2
            return Outcome.FAILED

        commands = [
            ["uv", "run", "ruff", "format", "--check", "."],
            ["uv", "run", "ruff", "check", "."],
            ["uv", "run", "pyright"],
        ]
        if not args.lint_only:
            commands.append(["uv", "run", "pytest"])

        for cmd in commands:
            step = " ".join(cmd)
            self.utils.print(f"Running {step}...")
            code = self.utils.run(cmd)
            if cmd[-1] == "pytest" and code == PYTEST_NO_TESTS_COLLECTED:
                continue
            if code != 0:
                self.utils.print_error(f"Check failed at step: {step}")
                state.exit_code = code
                return Outcome.FAILED

        self.utils.print("All Ambler checks passed.")
        return Outcome.DONE
