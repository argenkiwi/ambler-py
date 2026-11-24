from dataclasses import dataclass

from ambler.nodes.cli_error import CliError


@dataclass
class MockState:
    command: str | None = "bogus"
    exit_code: int = 0


class MockUtils:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def print_error(self, message: str) -> None:
        self.errors.append(message)


async def test_reports_the_unknown_command_with_exit_code_2() -> None:
    utils = MockUtils()
    state = MockState()
    await CliError(utils).run(state)
    assert utils.errors == ["Unknown command: bogus"]
    assert state.exit_code == 2
