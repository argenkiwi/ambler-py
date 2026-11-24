from dataclasses import dataclass, field

from ambler.nodes.run_checks import Outcome, RunChecks

FORMAT = "uv run ruff format --check ."
LINT = "uv run ruff check ."
TYPES = "uv run pyright"
TESTS = "uv run pytest"


@dataclass
class MockState:
    argv: list[str] = field(default_factory=list[str])
    exit_code: int = 0


class MockUtils:
    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.codes = codes or {}
        self.ran: list[str] = []
        self.out: list[str] = []
        self.errors: list[str] = []

    def run(self, cmd: list[str]) -> int:
        step = " ".join(cmd)
        self.ran.append(step)
        return self.codes.get(step, 0)

    def print(self, message: str) -> None:
        self.out.append(message)

    def print_error(self, message: str) -> None:
        self.errors.append(message)


async def test_runs_every_check_then_succeeds() -> None:
    utils = MockUtils()
    state = MockState()
    assert await RunChecks(utils).run(state) == Outcome.DONE
    assert utils.ran == [FORMAT, LINT, TYPES, TESTS]
    assert utils.out[-1] == "All Ambler checks passed."
    assert state.exit_code == 0


async def test_lint_only_skips_the_tests() -> None:
    utils = MockUtils()
    await RunChecks(utils).run(MockState(argv=["--lint-only"]))
    assert utils.ran == [FORMAT, LINT, TYPES]


async def test_stops_at_the_first_failure_with_its_exit_code() -> None:
    utils = MockUtils({LINT: 3})
    state = MockState()
    assert await RunChecks(utils).run(state) == Outcome.FAILED
    assert utils.ran == [FORMAT, LINT]
    assert utils.errors == [f"Check failed at step: {LINT}"]
    assert state.exit_code == 3


async def test_no_tests_collected_is_not_a_failure() -> None:
    utils = MockUtils({TESTS: 5})
    assert await RunChecks(utils).run(MockState()) == Outcome.DONE


async def test_other_pytest_failures_fail() -> None:
    state = MockState()
    assert await RunChecks(MockUtils({TESTS: 1})).run(state) == Outcome.FAILED
    assert state.exit_code == 1


async def test_unknown_option_is_a_usage_error() -> None:
    utils = MockUtils()
    state = MockState(argv=["--bogus"])
    assert await RunChecks(utils).run(state) == Outcome.FAILED
    assert state.exit_code == 2
    assert utils.ran == []
