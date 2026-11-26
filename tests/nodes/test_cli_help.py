from dataclasses import dataclass, field

import pytest

from ambler.guides import TOPICS, guide
from ambler.nodes.cli_help import USAGE, CliHelp


class MockUtils:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.errors: list[str] = []

    def print(self, message: str) -> None:
        self.out.append(message)

    def print_error(self, message: str) -> None:
        self.errors.append(message)


@dataclass
class MockState:
    argv: list[str] = field(default_factory=list[str])
    command: str | None = None
    exit_code: int = 0


async def test_prints_usage_listing_every_command() -> None:
    utils = MockUtils()
    state = MockState(command="--help", exit_code=2)
    await CliHelp(utils).run(state)
    assert utils.out == [USAGE]
    assert state.exit_code == 2
    for command in ("node", "walk", "util", "check", "help"):
        assert command in USAGE


async def test_prints_the_general_guide_for_help_without_a_topic() -> None:
    utils = MockUtils()
    state = MockState(command="help")
    await CliHelp(utils).run(state)
    assert utils.out == [guide()]
    assert state.exit_code == 0


async def test_prints_the_guide_for_a_known_topic() -> None:
    utils = MockUtils()
    state = MockState(argv=["node-design"], command="help")
    await CliHelp(utils).run(state)
    assert utils.out == [guide("node-design")]
    assert state.exit_code == 0


async def test_lists_the_topics_for_an_unknown_one_and_exits_1() -> None:
    utils = MockUtils()
    state = MockState(argv=["bogus"], command="help")
    await CliHelp(utils).run(state)
    assert utils.out == []
    assert utils.errors == [f"No guide for bogus. Topics: {', '.join(TOPICS)}"]
    assert state.exit_code == 1


@pytest.mark.parametrize("topic", TOPICS)
def test_every_guide_names_the_projects_own_cli(topic: str) -> None:
    text = guide(topic)
    assert text
    for verb in ("node", "util", "walk", "check", "help"):
        assert f"`ambler {verb}" not in text
