import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasArgv, HasExitCode
from ambler.utils.args import ArgParser, UsageError
from ambler.utils.conventions import todo
from ambler.utils.fs import ProjectError, SystemScaffoldUtils

PYTEST_NO_TESTS_COLLECTED = 5


class Outcome(Enum):
    """Whether every check passed."""

    DONE = auto()
    FAILED = auto()


class State(HasArgv, HasExitCode, Protocol):
    pass


class Utils(Protocol):
    def sources(self) -> dict[str, str]:
        """The project's nodes, walks, utilities and tests: each path, relative to
        the project root, and its text."""
        ...

    def run(self, cmd: list[str]) -> int:
        """Runs ``cmd`` with inherited stdio and returns its exit code."""
        ...

    def print(self, message: str) -> None: ...

    def print_error(self, message: str) -> None: ...


class SystemUtils:
    def sources(self) -> dict[str, str]:
        fs = SystemScaffoldUtils()
        root = fs.root()
        folders = [root / "tests"]
        try:
            package = root / "src" / fs.package_name()
            folders += [package / "nodes", package / "walks", package / "utils"]
        except ProjectError:
            pass
        return {
            str(path.relative_to(root)): path.read_text(encoding="utf-8")
            for folder in folders
            if folder.is_dir()
            for path in sorted(folder.rglob("*.py"))
        }

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

        violations = [
            line
            for path, source in sorted(self.utils.sources().items())
            for line in todo(path, source)
        ]
        if violations:
            for line in violations:
                self.utils.print(line)
            plural = "" if len(violations) == 1 else "s"
            self.utils.print_error(
                f"Check failed: {len(violations)} convention violation{plural}"
            )
            state.exit_code = 1
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
