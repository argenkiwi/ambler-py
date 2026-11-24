from ambler.nodes.cli_help import USAGE, CliHelp


class MockUtils:
    def __init__(self) -> None:
        self.out: list[str] = []

    def print(self, message: str) -> None:
        self.out.append(message)


async def test_prints_usage_listing_every_command() -> None:
    utils = MockUtils()
    await CliHelp(utils).run(object())
    assert utils.out == [USAGE]
    for command in ("node", "walk", "util", "check"):
        assert command in USAGE
