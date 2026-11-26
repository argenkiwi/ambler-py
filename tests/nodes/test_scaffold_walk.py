from dataclasses import dataclass, field
from pathlib import Path

from fakes import ROOT, FakeFs

from ambler.nodes.scaffold_walk import Outcome, ScaffoldWalk
from ambler.utils.templates import PACKAGE_INIT, render_node, render_protocols

NODES = ROOT / "src" / "demo" / "nodes"
WALK_FILE = ROOT / "src" / "demo" / "walks" / "counter.py"
TEST_FILE = ROOT / "tests" / "walks" / "test_counter.py"
SPEC_FILE = ROOT / "specs" / "counter.md"
PYPROJECT = ROOT / "pyproject.toml"
PYPROJECT_TEXT = '[project]\nname = "demo"\n'

START = render_node(
    "demo",
    "Start",
    terminal=False,
    fallible=True,
    outcomes=["SUCCESS", "INVALID_INPUT"],
    state_fields=[("count", "int")],
)

COUNT = '''from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum, auto
from typing import Protocol

from demo.nodes import HasCount, HasLog


class Outcome(Enum):
    AGAIN = auto()
    FINISHED = auto()


class State(HasCount, HasLog, Protocol):
    pass


class Utils(Protocol):
    async def sleep(self, duration: timedelta) -> None: ...

    def heads(self) -> bool:
        """Flips a coin."""
        ...


class SystemUtils:
    pass


@dataclass(frozen=True)
class Count:
    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> Outcome:
        return Outcome.AGAIN
'''

STOP = render_node(
    "demo",
    "Stop",
    terminal=True,
    fallible=False,
    outcomes=[],
    state_fields=[("count", "int")],
)

INIT = render_protocols(
    PACKAGE_INIT + "\nfrom pathlib import Path\n",
    [("count", "int"), ("log", "list[str]"), ("path", "Path"), ("note", "str | None")],
)


def project(**nodes: str) -> dict[Path, str]:
    files = {PYPROJECT: PYPROJECT_TEXT, NODES / "__init__.py": INIT}
    for name, source in (
        nodes or {"start": START, "count": COUNT, "stop": STOP}
    ).items():
        files[NODES / f"{name}.py"] = source
    return files


ARGV = [
    "counter",
    "--nodes",
    "start,count,stop",
    "--edge",
    "start.success=count,start.InvalidInput=start",
    "--edge",
    "count.AGAIN=count",
    "--edge",
    "count.finished=stop",
]


@dataclass
class MockState:
    argv: list[str] = field(default_factory=list[str])
    exit_code: int = 0


async def scaffold(fs: FakeFs, argv: list[str]) -> tuple[Outcome, MockState]:
    state = MockState(argv=argv)
    return await ScaffoldWalk(fs).run(state), state


async def test_writes_the_walk_from_the_nodes_it_reads() -> None:
    fs = FakeFs(project())

    outcome, state = await scaffold(fs, ARGV)

    assert outcome == Outcome.DONE
    assert state.exit_code == 0
    walk = fs.files[WALK_FILE]
    assert "from demo.engine import Walk" in walk
    assert "from demo.nodes import count, start" in walk
    assert "from demo.nodes.stop import Stop" in walk
    assert '__all__ = ["Error", "main", "run"]' in walk
    assert "Error = start.Error" in walk
    assert (
        "@dataclass\nclass State:\n"
        "    count: int = 0\n"
        "    log: list[str] = field(default_factory=list[str])\n"
    ) in walk
    assert (
        "class Id(Enum):\n    START = auto()\n    COUNT = auto()\n    STOP = auto()"
        in walk
    )
    assert "class Counter(Walk[Id, State]):" in walk
    assert "start: Start = field(default_factory=Start)" in walk
    assert (
        "                match await self.start.run(state):\n"
        "                    case start.Outcome.SUCCESS:\n"
        "                        return Id.COUNT\n"
        "                    case start.Outcome.INVALID_INPUT:\n"
        "                        return Id.START\n"
    ) in walk
    assert (
        "            case Id.STOP:\n"
        "                await self.stop.run(state)\n"
        "                return None\n"
    ) in walk
    assert "await Counter().run(Id.START, State())" in walk
    assert "except Error as e:" in walk
    assert "case _" not in walk


async def test_an_outcome_without_an_edge_is_left_unwired() -> None:
    fs = FakeFs(project())

    await scaffold(
        fs, ["counter", "--nodes", "start,count,stop", "--edge", "count.again=count"]
    )

    walk = fs.files[WALK_FILE]
    assert (
        "                    case count.Outcome.FINISHED:\n"
        + " " * 24
        + 'raise NotImplementedError("not yet wired: COUNT.FINISHED")\n'
    ) in walk
    assert 'raise NotImplementedError("not yet wired: START.SUCCESS")' in walk


async def test_halt_ends_the_walk_on_that_outcome() -> None:
    fs = FakeFs(project())

    await scaffold(fs, ["counter", "--nodes", "count", "--edge", "count.finished=halt"])

    assert (
        "                    case count.Outcome.FINISHED:\n"
        "                        return None\n"
    ) in fs.files[WALK_FILE]


async def test_a_walk_no_node_of_which_can_fail_has_no_error() -> None:
    fs = FakeFs(project())

    await scaffold(fs, ["counter", "--nodes", "count,stop"])

    walk = fs.files[WALK_FILE]
    assert '__all__ = ["main", "run"]' in walk
    assert "Error =" not in walk and "except Error" not in walk
    assert "    asyncio.run(run())" in walk


async def test_several_nodes_that_can_fail_give_a_tuple_of_errors() -> None:
    other = START.replace("class Start:", "class Other:")
    fs = FakeFs(project(start=START, other=other))

    await scaffold(fs, ["counter", "--nodes", "start,other"])

    assert "Error = (start.Error, other.Error)" in fs.files[WALK_FILE]


async def test_the_wiring_test_scripts_every_nodes_utils() -> None:
    fs = FakeFs(project())

    await scaffold(fs, ARGV)

    test = fs.files[TEST_FILE]
    assert (
        "from datetime import timedelta\n\nfrom demo.nodes.count import Count\n" in test
    )
    assert "from demo.walks.counter import Counter, Id, State" in test
    assert (
        "    async def sleep(self, duration: timedelta) -> None:\n"
        '        raise NotImplementedError("not yet implemented")\n'
    ) in test
    assert "    def heads(self) -> bool:\n" in test
    assert (
        "Counter(start=Start(script), count=Count(script), stop=Stop(script))"
        ".run(Id.START, state)"
    ) in test


async def test_state_fields_import_their_types_from_the_nodes_package() -> None:
    reader = render_node(
        "demo",
        "Read",
        terminal=True,
        fallible=False,
        outcomes=[],
        state_fields=[("path", "Path"), ("note", "str | None")],
    )
    fs = FakeFs(project(read=reader))

    await scaffold(fs, ["counter", "--nodes", "read"])

    walk = fs.files[WALK_FILE]
    assert "from pathlib import Path\n" in walk
    assert "    path: Path = field(default_factory=Path)\n" in walk
    assert "    note: str | None = None\n" in walk


async def test_writes_a_spec_with_a_section_per_node() -> None:
    fs = FakeFs(project())

    await scaffold(fs, ARGV)

    spec = fs.files[SPEC_FILE]
    assert spec.startswith("# Program Specifications\n")
    assert "\n## Nodes\n" in spec
    assert "### Start\n- Initial node.\n" in spec
    assert "- If `SUCCESS`, it transitions to `COUNT`." in spec
    assert "### Stop\n" in spec
    assert "- Terminates." in spec
    assert "## Shared State\n\nThe shared state consists of:\n- `count`:" in spec


async def test_adds_a_script_that_runs_the_walk() -> None:
    fs = FakeFs(project())

    await scaffold(fs, ARGV)

    assert fs.files[PYPROJECT] == (
        PYPROJECT_TEXT + '\n[project.scripts]\ncounter = "demo.walks.counter:main"\n'
    )
    assert fs.out == [
        f"Created {WALK_FILE}",
        f"Created {TEST_FILE}",
        f"Created {SPEC_FILE}",
        "Added the `counter` script to pyproject.toml: "
        "run `uv sync`, then `uv run counter`.",
    ]


async def test_adds_the_script_to_an_existing_scripts_table() -> None:
    files = project()
    files[PYPROJECT] = (
        '[project]\nname = "demo"\n\n[project.scripts]\nother = "x:y"\n\n[tool.x]\n'
    )
    fs = FakeFs(files)

    await scaffold(fs, ARGV)

    assert fs.files[PYPROJECT] == (
        '[project]\nname = "demo"\n\n[project.scripts]\n'
        'counter = "demo.walks.counter:main"\nother = "x:y"\n\n[tool.x]\n'
    )


async def test_no_runner_leaves_pyproject_alone() -> None:
    fs = FakeFs(project())

    outcome, _ = await scaffold(fs, [*ARGV, "--no-runner"])

    assert outcome == Outcome.DONE
    assert fs.files[PYPROJECT] == PYPROJECT_TEXT


async def test_keeps_an_existing_spec() -> None:
    files = project()
    files[SPEC_FILE] = "mine"
    fs = FakeFs(files)

    await scaffold(fs, ARGV)

    assert fs.files[SPEC_FILE] == "mine"


async def fails(files: dict[Path, str], argv: list[str], code: int) -> FakeFs:
    fs = FakeFs(files)
    before = dict(files)

    outcome, state = await scaffold(fs, argv)

    assert outcome == Outcome.FAILED
    assert state.exit_code == code
    assert fs.files == before
    assert len(fs.errors) == 1
    return fs


async def test_an_existing_walk_fails_with_exit_code_1() -> None:
    files = project()
    files[WALK_FILE] = "old"
    await fails(files, ARGV, 1)


async def test_an_existing_script_fails_with_exit_code_1() -> None:
    files = project()
    files[PYPROJECT] = (
        '[project]\nname = "demo"\n\n[project.scripts]\ncounter = "x:y"\n'
    )
    fs = await fails(files, ARGV, 1)
    assert "counter" in fs.errors[0]


async def test_missing_nodes_are_listed_with_the_commands_to_create_them() -> None:
    fs = await fails(project(count=COUNT), ["counter", "--nodes", "ask,count,greet"], 2)
    assert "uv run ambler node ask" in fs.errors[0]
    assert "uv run ambler node greet" in fs.errors[0]
    assert "node count" not in fs.errors[0]


async def test_bad_edges_fail_with_exit_code_2() -> None:
    for edge, reason in [
        ("nonsense", "nonsense"),
        ("ghost.done=count", "ghost"),
        ("count.sideways=count", "SIDEWAYS"),
        ("count.again=ghost", "ghost"),
        ("stop.done=count", "stop"),
    ]:
        fs = await fails(
            project(), ["counter", "--nodes", "start,count,stop", "--edge", edge], 2
        )
        assert reason in fs.errors[0], edge


async def test_fields_of_different_types_fail_with_exit_code_2() -> None:
    other_init = INIT + "\n\nclass HasTotal(Protocol):\n    count: str\n"
    other = STOP.replace("HasCount", "HasTotal").replace("class Stop:", "class Other:")
    files = project(stop=STOP, other=other)
    files[NODES / "__init__.py"] = other_init
    fs = await fails(files, ["counter", "--nodes", "stop,other"], 2)
    assert "count" in fs.errors[0]


async def test_a_node_that_cannot_be_read_fails_with_exit_code_2() -> None:
    await fails(project(count="def broken(:\n"), ["counter", "--nodes", "count"], 2)


async def test_missing_nodes_option_fails_with_exit_code_2() -> None:
    await fails(project(), ["counter"], 2)


async def test_empty_nodes_fail_with_exit_code_2() -> None:
    fs = await fails(project(), ["counter", "--nodes", ","], 2)
    assert fs.errors == ["Error: --nodes must contain at least one node name"]
