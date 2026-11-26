from fakes import ROOT, FakeFs

from ambler.nodes.cli_error import CliError
from ambler.nodes.cli_help import CliHelp
from ambler.nodes.run_checks import RunChecks
from ambler.nodes.scaffold_node import ScaffoldNode
from ambler.nodes.scaffold_util import ScaffoldUtil
from ambler.nodes.scaffold_walk import ScaffoldWalk
from ambler.walks.cli import Cli, Id, State


class Recorder:
    """Implements the ``Utils`` protocol of every node in the walk."""

    def __init__(self) -> None:
        self.out: list[str] = []
        self.errors: list[str] = []
        self.ran: list[list[str]] = []

    def print(self, message: str) -> None:
        self.out.append(message)

    def print_error(self, message: str) -> None:
        self.errors.append(message)

    def run(self, cmd: list[str]) -> int:
        self.ran.append(cmd)
        return 0


def cli(rec: Recorder, fs: FakeFs) -> Cli:
    return Cli(
        scaffold_node=ScaffoldNode(fs),
        scaffold_walk=ScaffoldWalk(fs),
        scaffold_util=ScaffoldUtil(fs),
        run_checks=RunChecks(rec),
        cli_help=CliHelp(rec),
        cli_error=CliError(rec),
    )


async def run(
    argv: list[str], fs: FakeFs | None = None
) -> tuple[State, Recorder, FakeFs]:
    rec, fs = Recorder(), fs or FakeFs({ROOT / "pyproject.toml": "[project]\n"})
    state = State(argv=argv)
    await cli(rec, fs).run(Id.CLI_ROUTE, state)
    return state, rec, fs


async def test_no_command_prints_help_and_exits_2() -> None:
    state, rec, _ = await run([])
    assert state.exit_code == 2
    assert "Usage: uv run ambler" in rec.out[0]


async def test_help_flag_exits_0() -> None:
    state, rec, _ = await run(["--help"])
    assert state.exit_code == 0
    assert "Usage: uv run ambler" in rec.out[0]


async def test_help_prints_a_topic() -> None:
    state, rec, _ = await run(["help", "walk"])
    assert state.exit_code == 0
    assert rec.out[0].startswith("# uv run ambler walk")


async def test_help_for_an_unknown_topic_exits_1() -> None:
    state, rec, _ = await run(["help", "bogus"])
    assert state.exit_code == 1
    assert rec.out == []
    assert rec.errors[0].startswith("No guide for bogus")


async def test_unknown_command_is_reported_and_exits_2() -> None:
    state, rec, _ = await run(["bogus"])
    assert state.exit_code == 2
    assert rec.errors == ["Unknown command: bogus"]


async def test_check_runs_the_checks() -> None:
    state, rec, _ = await run(["check", "--lint-only"])
    assert state.exit_code == 0
    assert len(rec.ran) == 3


async def test_node_walk_and_util_scaffold_their_files() -> None:
    _, _, fs = await run(["node", "stop", "--terminal"])
    assert ROOT / "src" / "demo" / "nodes" / "stop.py" in fs.files

    _, _, fs = await run(["walk", "w", "--nodes", "stop"], fs)
    assert ROOT / "src" / "demo" / "walks" / "w.py" in fs.files

    _, _, fs = await run(["util", "terminal"])
    assert ROOT / "src" / "demo" / "utils" / "terminal.py" in fs.files


async def test_a_failing_scaffold_exit_code_reaches_the_state() -> None:
    state, _, _ = await run(["node", "stop"])
    assert state.exit_code == 2
