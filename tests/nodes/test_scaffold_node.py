from dataclasses import dataclass, field

from fakes import ROOT, FakeFs

from ambler.nodes.scaffold_node import Outcome, ScaffoldNode

NODES = ROOT / "src" / "demo" / "nodes"
NODE_FILE = NODES / "count.py"
INIT_FILE = NODES / "__init__.py"
TEST_FILE = ROOT / "tests" / "nodes" / "test_count.py"


@dataclass
class MockState:
    argv: list[str] = field(default_factory=list[str])
    exit_code: int = 0


async def test_writes_node_test_and_state_protocols() -> None:
    fs = FakeFs()
    state = MockState(
        argv=["count", "--outcomes", "again,finished", "--state", "count:int"]
    )
    assert await ScaffoldNode(fs).run(state) == Outcome.DONE

    node = fs.files[NODE_FILE]
    assert "AGAIN = auto()" in node
    assert "FINISHED = auto()" in node
    assert "class Count:" in node
    assert "from demo.nodes import HasCount" in node
    assert "class HasCount(Protocol):" in fs.files[INIT_FILE]
    assert "async def test_again_when_pending" in fs.files[TEST_FILE]
    assert fs.out == [f"Created {NODE_FILE}", f"Created {TEST_FILE}"]
    assert state.exit_code == 0


async def test_terminal_node_has_no_outcome_enum() -> None:
    fs = FakeFs()
    state = MockState(argv=["count", "--terminal"])
    assert await ScaffoldNode(fs).run(state) == Outcome.DONE
    assert "Outcome" not in fs.files[NODE_FILE]
    assert "-> None:" in fs.files[NODE_FILE]
    assert "async def test_finishes" in fs.files[TEST_FILE]


async def test_existing_protocol_is_not_declared_twice() -> None:
    init = "class HasCount(Protocol):\n    count: int\n"
    fs = FakeFs({INIT_FILE: init})
    state = MockState(argv=["count", "--terminal", "--state", "count:int"])
    await ScaffoldNode(fs).run(state)
    assert fs.files[INIT_FILE] == init


async def test_state_type_defaults_to_object_and_fallible_adds_error() -> None:
    fs = FakeFs()
    state = MockState(argv=["count", "--terminal", "--fallible", "--state", "x"])
    await ScaffoldNode(fs).run(state)
    assert "x: object" in fs.files[INIT_FILE]
    assert "class Error(Exception)" in fs.files[NODE_FILE]


async def test_existing_node_fails_with_exit_code_1() -> None:
    fs = FakeFs({NODE_FILE: "old"})
    state = MockState(argv=["count", "--terminal"])
    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED
    assert fs.files[NODE_FILE] == "old"
    assert state.exit_code == 1


async def test_needs_outcomes_or_terminal() -> None:
    fs = FakeFs()
    state = MockState(argv=["count"])
    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED
    assert state.exit_code == 2
    assert fs.errors == ["Error: Specify either --outcomes <a,b> or --terminal"]
    assert fs.files == {}


async def test_missing_name_fails_with_exit_code_2() -> None:
    fs = FakeFs()
    state = MockState(argv=["--terminal"])
    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED
    assert state.exit_code == 2
