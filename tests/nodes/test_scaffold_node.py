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


async def test_fallible_adds_error() -> None:
    fs = FakeFs()
    state = MockState(argv=["count", "--terminal", "--fallible", "--state", "x:int"])
    await ScaffoldNode(fs).run(state)
    assert "class Error(Exception)" in fs.files[NODE_FILE]


async def test_a_reused_field_takes_its_type_from_the_existing_protocol() -> None:
    init = (
        '"""Node package."""\n\nfrom typing import Protocol\n\n\n'
        "class HasName(Protocol):\n    name: str\n"
    )
    fs = FakeFs({INIT_FILE: init})
    state = MockState(argv=["count", "--terminal", "--state", "name"])

    assert await ScaffoldNode(fs).run(state) == Outcome.DONE

    assert fs.files[INIT_FILE] == init
    assert "from demo.nodes import HasName" in fs.files[NODE_FILE]
    assert '    name: str = ""\n' in fs.files[TEST_FILE]
    assert "object" not in fs.files[TEST_FILE]


async def test_a_reused_field_brings_the_imports_its_type_needs() -> None:
    init = (
        '"""Node package."""\n\n'
        "from pathlib import Path\nfrom typing import Protocol\n\n\n"
        "class HasPath(Protocol):\n    path: Path\n"
    )
    fs = FakeFs({INIT_FILE: init})
    state = MockState(argv=["count", "--terminal", "--state", "path"])

    await ScaffoldNode(fs).run(state)

    test = fs.files[TEST_FILE]
    assert (
        "from dataclasses import dataclass, field\nfrom pathlib import Path\n" in test
    )
    assert "    path: Path = field(default_factory=Path)\n" in test


async def test_a_field_without_a_type_and_no_protocol_fails_with_exit_code_2() -> None:
    fs = FakeFs()
    state = MockState(argv=["count", "--terminal", "--state", "x"])

    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED

    assert state.exit_code == 2
    assert fs.files == {}
    assert "--state x:<Type>" in fs.errors[0]


async def test_a_different_type_from_the_protocol_fails_with_exit_code_2() -> None:
    init = (
        "from typing import Protocol\n\n\nclass HasCount(Protocol):\n    count: int\n"
    )
    fs = FakeFs({INIT_FILE: init})
    state = MockState(argv=["count", "--terminal", "--state", "count:str"])

    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED

    assert state.exit_code == 2
    assert fs.files == {INIT_FILE: init}
    assert "int" in fs.errors[0] and "str" in fs.errors[0]


PKG_INIT = '"""Node package."""\n\nfrom typing import Protocol\n'


async def test_a_type_given_by_its_path_is_imported_into_the_nodes_package() -> None:
    fs = FakeFs({INIT_FILE: PKG_INIT})
    state = MockState(argv=["count", "--terminal", "--state", "board:demo.board.Board"])

    assert await ScaffoldNode(fs).run(state) == Outcome.DONE

    assert fs.files[INIT_FILE] == (
        '"""Node package."""\n\nfrom typing import Protocol\n'
        "from demo.board import Board\n\n\n"
        'class HasBoard(Protocol):\n    """A state that has a board field."""\n\n'
        "    board: Board\n"
    )
    test = fs.files[TEST_FILE]
    assert "from demo.board import Board\n" in test
    assert "    board: Board = field(default_factory=Board)\n" in test
    assert sorted(fs.formatted) == sorted([NODE_FILE, TEST_FILE, INIT_FILE])


async def test_a_generic_type_has_its_paths_shortened() -> None:
    fs = FakeFs({INIT_FILE: PKG_INIT})
    state = MockState(
        argv=["count", "--terminal", "--state", "boards:list[demo.board.Board] | None"]
    )

    await ScaffoldNode(fs).run(state)

    assert "from demo.board import Board\n" in fs.files[INIT_FILE]
    assert "    boards: list[Board] | None\n" in fs.files[INIT_FILE]
    assert "    boards: list[Board] | None = None\n" in fs.files[TEST_FILE]


async def test_a_type_given_by_its_path_matches_the_protocol_that_uses_it() -> None:
    init = (
        '"""Node package."""\n\nfrom typing import Protocol\n\n'
        "from demo.board import Board\n\n\n"
        "class HasBoard(Protocol):\n    board: Board\n"
    )
    fs = FakeFs({INIT_FILE: init})
    state = MockState(argv=["count", "--terminal", "--state", "board:demo.board.Board"])

    assert await ScaffoldNode(fs).run(state) == Outcome.DONE

    assert fs.files[INIT_FILE] == init
    assert "from demo.board import Board\n" in fs.files[TEST_FILE]


async def test_an_imported_type_needs_no_path() -> None:
    init = (
        '"""Node package."""\n\nfrom pathlib import Path\nfrom typing import Protocol\n'
    )
    fs = FakeFs({INIT_FILE: init})
    state = MockState(argv=["count", "--terminal", "--state", "path:Path"])

    assert await ScaffoldNode(fs).run(state) == Outcome.DONE

    assert fs.files[INIT_FILE].count("from pathlib import Path") == 1
    assert "from pathlib import Path\n" in fs.files[TEST_FILE]


async def test_a_type_that_is_not_a_builtin_or_imported_fails_with_exit_code_2() -> (
    None
):
    fs = FakeFs()
    state = MockState(argv=["count", "--terminal", "--state", "path:Path"])

    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED

    assert state.exit_code == 2
    assert fs.files == {}
    assert "--state path:<module>.Path" in fs.errors[0]


async def test_a_path_to_a_name_that_means_something_else_fails() -> None:
    init = '"""Node package."""\n\nfrom typing import Protocol\n\nfrom x import Board\n'
    fs = FakeFs({INIT_FILE: init})
    state = MockState(argv=["count", "--terminal", "--state", "board:demo.board.Board"])

    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED

    assert state.exit_code == 2
    assert fs.files == {INIT_FILE: init}


async def test_two_paths_to_the_same_name_fail() -> None:
    fs = FakeFs({INIT_FILE: PKG_INIT})
    state = MockState(
        argv=["count", "--terminal", "--state", "a:x.Board", "--state", "b:y.Board"]
    )

    assert await ScaffoldNode(fs).run(state) == Outcome.FAILED

    assert state.exit_code == 2
    assert fs.files == {INIT_FILE: PKG_INIT}


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
