from dataclasses import dataclass, field

import pytest

from ambler.nodes.cli_route import CliRoute, Outcome


@dataclass
class MockState:
    argv: list[str] = field(default_factory=list[str])
    command: str | None = None
    exit_code: int = 0


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("node", Outcome.NODE),
        ("walk", Outcome.WALK),
        ("util", Outcome.UTIL),
        ("check", Outcome.CHECK),
        ("bogus", Outcome.UNKNOWN),
    ],
)
async def test_routes_the_command_and_leaves_the_options(
    command: str, expected: Outcome
) -> None:
    state = MockState(argv=[command, "name", "--flag"])
    assert await CliRoute().run(state) == expected
    assert state.command == command
    assert state.argv == ["name", "--flag"]
    assert state.exit_code == 0


@pytest.mark.parametrize("flag", ["--help", "-h"])
async def test_help_flag_shows_help_with_exit_code_0(flag: str) -> None:
    state = MockState(argv=[flag], exit_code=9)
    assert await CliRoute().run(state) == Outcome.HELP
    assert state.exit_code == 0


async def test_no_command_shows_help_with_exit_code_2() -> None:
    state = MockState()
    assert await CliRoute().run(state) == Outcome.HELP
    assert state.command is None
    assert state.exit_code == 2
